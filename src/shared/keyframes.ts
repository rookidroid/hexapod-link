// Keyframed leg motion for the workspace.
//
// A pose here is where the six feet are, not what the joints are doing: a 6x3
// list of foot tip positions in the robot's body frame, the same frame the path
// tool and path_generator.ts work in (x right, y forward, z up, origin at the
// body's centre, millimetres). Dragging a foot sets its position and the
// joints are solved from it, so a keyframe says what the user actually placed.
//
// A keyframe is {feet: [[x, y, z] * 6], duration_ms}, where the duration is
// the time taken to reach that pose from the keyframe before it. The first
// keyframe's duration is only used when the sequence loops, for the move from
// the last keyframe back round to it. A keyframe made in the workspace also
// keeps the layers the pose was built from, as `state` (pose_layers.ts); this
// module carries it along without looking in it.
//
// A keyframe also says whether the move into it starts and stops gently, as
// `ease` (left out when it does, the default). A gait's keyframes
// (gait_keyframes.ts) do not: each is one point on a path the feet keep moving
// along, and easing into it would stop them there.
//
// Each keyframe in a sequence carries a number, given when it is made and kept
// from then on: moving a keyframe earlier or later, or deleting another, does
// not renumber the rest, so "#3" stays the keyframe it named. numbered() gives
// one to each keyframe that has none; renumbered() numbers them afresh.
//
// Nothing here settles the body onto the ground: the body is held still and the
// feet move around it. That is how the robot sees it too -- it has no idea where
// the floor is, it only places its feet.

import { VirtualHexapod } from "./models";
import { genPosture, inverseKinematics, type Pose, servoAnglesToPose } from "./path_generator";
import {
    getJointLimits,
    getLegSigns,
    getSimulatorDimensions,
    type JointLimits,
    type RobotConfig,
} from "./robot_config";
import { hexapodToScene, type Scene, xyz } from "./scene";
import { cross, dot, pyMod, pyRound, radians, type Vec3 } from "./util";

export const FILE_FORMAT = "hexapod-link-keyframes";
export const FILE_VERSION = 1;

export const DEFAULT_DURATION_MS = 500;
// Down to a single frame of the fastest robot's gaits (12 ms).
export const MIN_DURATION_MS = 10;
export const MAX_DURATION_MS = 60000;

/** A foot this close to the ground plane (mm) counts as standing on it. */
export const GROUND_TOLERANCE = 2.0;

// Some slack on the joint limits, so a pose that sits exactly on a limit is not
// refused for floating point noise.
const LIMIT_SLACK = 1e-6;

/** How far inside a joint's limit (degrees) a pose that asks for more is held:
 * a straight move between two poses on the limit bulges past it a little, and
 * this keeps the whole move inside. About a servo tick. */
export const LIMIT_MARGIN_DEG = 0.5;

// The nearest (mm) a foot held in reach comes to its coxia's axis.
const MIN_RADIUS = 1.0;

export const BODY_KEYS = ["percent_x", "percent_y", "percent_z", "rot_x", "rot_y", "rot_z"] as const;
export type BodyKey = (typeof BODY_KEYS)[number];
export type Body = Record<BodyKey, number>;

/** One pose in two layers on top of standby (pose_layers.ts). */
export interface PoseState {
    body: Body;
    offsets: Vec3[];
}

export interface Keyframe {
    feet: Vec3[];
    duration_ms: number;
    state?: PoseState;
    ease?: false;
    number?: number;
}

export class KeyframeFileError extends Error {
    override name = "KeyframeFileError";
}

/** Six foot positions as plain numbers, to a thousandth of a millimetre. */
export function cleanFeet(feet: readonly (readonly number[])[]): Vec3[] {
    return feet.map((foot) => foot.map((c) => pyRound(Number(c), 3)) as Vec3);
}

/** Foot positions of the robot's standby posture. */
export function standbyFeet(robot: RobotConfig): Vec3[] {
    const [j2, j3] = robot.gait.standby_posture;
    return cleanFeet(genPosture(j2, j3, robot.config));
}

/** Height of the floor in the body frame: where the feet stand at standby. */
export function groundHeight(robot: RobotConfig): number {
    return Math.min(...standbyFeet(robot).map((foot) => foot[2]));
}

const JOINTS = ["coxia", "femur", "tibia"] as const;

/** Solve the joints for six foot positions: [pose, badLegs]. The bad legs
 * cannot put their foot there -- out of reach, or a joint past the robot's
 * limits, or with `margin` nearer than that many degrees to them. A bad leg's
 * angles are not meaningful. */
export function feetToPose(
    feet: readonly (readonly number[])[],
    robot: RobotConfig,
    margin = 0.0,
): [Pose, number[]] {
    const angles = inverseKinematics(feet, robot.config);
    const pose = servoAnglesToPose(
        angles.map((row) => row.map((a) => (Number.isNaN(a) ? 0 : a))),
        getLegSigns(robot),
    );
    // Round off the float noise of the solve, which would otherwise show up as
    // "-0.00" in the angle readout.
    for (const leg of pose) {
        for (const joint of JOINTS) {
            leg[joint] = pyRound(leg[joint], 6);
        }
    }
    const limits = getJointLimits(robot);
    const bad: number[] = [];
    for (let leg = 0; leg < 6; leg++) {
        if (angles[leg].some(Number.isNaN)) {
            bad.push(leg);
            continue;
        }
        if (JOINTS.some((j) => Math.abs(pose[leg][j]) > limits[j] - margin + LIMIT_SLACK)) {
            bad.push(leg);
        }
    }
    return [pose, bad];
}

/** `angle` (radians) as the same direction within half a turn of zero. */
function wrapped(angle: number): number {
    return pyMod(angle + Math.PI, 2 * Math.PI) - Math.PI;
}

/** `angle` (radians), turned no further than `most` either way. */
function held(angle: number, most: number): number {
    return Math.min(Math.max(wrapped(angle), -most), most);
}

type Plane = [number, number];

/** Where a leg's femur and tibia (radians) put its foot in the leg's own
 * plane: (out from the femur's joint, up). */
function planeFoot(femur: number, tibia: number, femurLength: number, tibiaLength: number): Plane {
    return [
        femurLength * Math.cos(femur) + tibiaLength * Math.sin(femur + tibia),
        femurLength * Math.sin(femur) - tibiaLength * Math.cos(femur + tibia),
    ];
}

/** planeFoot() run backwards, as inverseKinematics() does it: (femur, tibia),
 * or null for a foot the two cannot reach. */
function planeAngles(out: number, up: number, femurLength: number, tibiaLength: number): Plane | null {
    const reach2 = out * out + up * up;
    const reach = Math.sqrt(reach2);
    if (reach < 1e-9) {
        return null;
    }
    const f2 = femurLength * femurLength;
    const t2 = tibiaLength * tibiaLength;
    const cos1 = (reach2 + f2 - t2) / (2 * femurLength * reach);
    const cos2 = (reach2 - f2 + t2) / (2 * tibiaLength * reach);
    if (Math.abs(cos1) > 1 || Math.abs(cos2) > 1) {
        return null;
    }
    const a1 = Math.acos(cos1);
    const a2 = Math.acos(cos2);
    return [Math.atan2(up, out) + a1, Math.PI / 2 - (a1 + a2)];
}

/** The closest spot to (out, up) in a leg's plane that its femur and tibia can
 * put the foot, turning no further than `maxFemur` and `maxTibia` (radians)
 * and coming no nearer the coxia's axis than `minOut`; null if there is none.
 *
 * A spot the leg cannot reach has its closest on the edge of what it can: with
 * one of the two joints at its limit, or at `minOut`. Each of those is an arc
 * or a line, whose closest point is known outright. */
function nearestInPlane(
    out: number,
    up: number,
    femurLength: number,
    tibiaLength: number,
    maxFemur: number,
    maxTibia: number,
    minOut: number,
): Plane | null {
    const within = (angles: Plane | null) =>
        angles !== null &&
        Math.abs(angles[0]) <= maxFemur + LIMIT_SLACK &&
        Math.abs(angles[1]) <= maxTibia + LIMIT_SLACK;

    if (out >= minOut && within(planeAngles(out, up, femurLength, tibiaLength))) {
        return [out, up];
    }

    const angles: Plane[] = [];
    const atLeast = planeAngles(minOut, up, femurLength, tibiaLength);
    if (within(atLeast)) {
        angles.push(atLeast as Plane);
    }
    for (const tibia of [-maxTibia, maxTibia]) {
        // The tibia held: the foot swings about the femur's joint, at a
        // distance, and ahead of the femur by an angle, that do not change.
        const [aheadOut, aheadUp] = planeFoot(0.0, tibia, femurLength, tibiaLength);
        const lead = Math.atan2(aheadUp, aheadOut);
        const radius = Math.hypot(aheadOut, aheadUp);
        const femurs = [Math.atan2(up, out) - lead, -maxFemur, maxFemur];
        if (radius > Math.abs(minOut)) {
            const swing = Math.acos(minOut / radius);
            femurs.push(swing - lead, -swing - lead);
        }
        for (const femur of femurs) {
            angles.push([held(femur, maxFemur), tibia]);
        }
    }
    for (const femur of [-maxFemur, maxFemur]) {
        // The femur held: the foot swings about the knee.
        const kneeOut = femurLength * Math.cos(femur);
        const kneeUp = femurLength * Math.sin(femur);
        const tibias = [Math.atan2(out - kneeOut, kneeUp - up) - femur];
        if (Math.abs(minOut - kneeOut) < tibiaLength) {
            const swing = Math.asin((minOut - kneeOut) / tibiaLength);
            tibias.push(swing - femur, Math.PI - swing - femur);
        }
        for (const tibia of tibias) {
            angles.push([femur, held(tibia, maxTibia)]);
        }
    }

    // Only what solves back to the angles it was made from: a foot folded
    // round behind its own femur solves to a whole turn more.
    const spots = angles
        .map(([femur, tibia]) => planeFoot(femur, tibia, femurLength, tibiaLength))
        .filter(
            (spot) =>
                spot[0] >= minOut - LIMIT_SLACK &&
                within(planeAngles(spot[0], spot[1], femurLength, tibiaLength)),
        );
    if (!spots.length) {
        return null;
    }
    let best = spots[0];
    let bestDistance = Math.hypot(best[0] - out, best[1] - up);
    for (const spot of spots.slice(1)) {
        const distance = Math.hypot(spot[0] - out, spot[1] - up);
        if (distance < bestDistance) {
            best = spot;
            bestDistance = distance;
        }
    }
    return best;
}

/** The closest spot to `foot`, in the body frame, that leg `leg` can put its
 * foot: `foot` itself when the leg can reach it with every joint
 * LIMIT_MARGIN_DEG inside its limit, else where the leg ends up following it
 * as far as its joints go. How a dragged foot slides along the edge of its
 * leg's reach instead of stopping at it. null when the leg can reach nowhere
 * near, which no robot's does. */
export function nearestReachableFoot(
    foot: readonly number[],
    leg: number,
    robot: RobotConfig,
): Vec3 | null {
    const config = robot.config;
    const limits = getJointLimits(robot);
    const most = (joint: keyof JointLimits) =>
        radians(Math.max(limits[joint] - LIMIT_MARGIN_DEG, 0.0));
    const coxiaLength = config.legJoint1ToJoint2;
    const femurLength = config.legJoint2ToJoint3;
    const tibiaLength = config.legJoint3ToTip;

    // Into the leg's own frame and back, as inverseKinematics() has it: the
    // same turn-and-mirror both ways.
    const mx = config.legMountX[leg];
    const my = config.legMountY[leg];
    const angle = radians(config.legMountAngle[leg]);
    const c = Math.cos(angle);
    const s = Math.sin(angle);

    const [x, y, z] = foot.map(Number);
    const dx = x - mx;
    const dy = y - my;
    let along = c * dx + s * dy;
    const across = s * dx + -c * dy;
    along -= config.legRootToJoint1;

    const asked = -Math.atan2(across, along);
    const coxia = Math.min(Math.max(asked, -most("coxia")), most("coxia"));
    const out = along * Math.cos(coxia) - across * Math.sin(coxia) - coxiaLength;
    // Not past straight or folded flat, whatever the tibia's limit: beyond
    // either the same feet come round again.
    const spot = nearestInPlane(
        out,
        z,
        femurLength,
        tibiaLength,
        most("femur"),
        Math.min(most("tibia"), Math.PI / 2),
        MIN_RADIUS - coxiaLength,
    );
    if (spot === null) {
        return null;
    }
    if (coxia === asked && spot[0] === out && spot[1] === z) {
        return [x, y, z];
    }
    const radius = spot[0] + coxiaLength;
    const lx = radius * Math.cos(coxia) + config.legRootToJoint1;
    const ly = -radius * Math.sin(coxia);
    return [c * lx + s * ly + mx, s * lx + -c * ly + my, spot[1]];
}

/** The app's linkage model with its legs set to `pose`, body unmoved. */
function posedModel(pose: Pose, robot: RobotConfig): VirtualHexapod {
    const hexapod = new VirtualHexapod(getSimulatorDimensions(robot));
    pose.forEach((leg, id) => {
        hexapod.legs[id].changePose(leg.coxia, leg.femur, leg.tibia);
    });
    return hexapod;
}

/** Where a pose puts the six feet, in the body frame: feetToPose run
 * backwards. How a pose made from joint angles -- typed into the joint
 * fields, or one of a gait's -- becomes feet that can be dragged and kept. */
export function poseToFeet(pose: Pose, robot: RobotConfig): Vec3[] {
    return cleanFeet(posedModel(pose, robot).legs.map((leg) => xyz(leg.footTip())));
}

// How far (degrees) each joint is nudged to find which way it turns.
const AXIS_NUDGE_DEG = 1.0;

/** What each joint turns about, in the body frame: per leg, per joint (coxia,
 * femur, tibia), the unit vector a positive angle turns it about by the
 * right-hand rule, or null where that cannot be told.
 *
 * The hip turns about the body's z, the knee and ankle about the leg's own y.
 * Which way round each is, is found by turning the joint a little and seeing
 * which way the foot goes, so it holds whatever the signs of the angles are on
 * each side of the robot. */
export function jointAxes(pose: Pose, robot: RobotConfig): (Vec3 | null)[][] {
    const base = posedModel(pose, robot);
    const axes: (Vec3 | null)[][] = Array.from({ length: 6 }, () => [null, null, null]);
    JOINTS.forEach((joint, index) => {
        const nudged = pose.map((leg) => ({ ...leg, [joint]: leg[joint] + AXIS_NUDGE_DEG }));
        const turned = posedModel(nudged, robot);
        for (let id = 0; id < 6; id++) {
            const leg = base.legs[id];
            let axis: Vec3;
            if (index === 0) {
                axis = [0.0, 0.0, 1.0];
            } else {
                const heading = radians(leg.coxiaAxis + leg.alpha);
                axis = [-Math.sin(heading), Math.cos(heading), 0.0];
            }
            const points = leg.allPoints;
            const pivot = points[index];
            const tip = turned.legs[id].footTip();
            const before = [points[3].x - pivot.x, points[3].y - pivot.y, points[3].z - pivot.z];
            const after = [tip.x - pivot.x, tip.y - pivot.y, tip.z - pivot.z];
            // Turned the right-hand way about `axis`, before x after points
            // along it.
            const way = dot(cross(before, after), axis);
            if (Math.abs(way) > 1e-9) {
                const sign = Math.sign(way);
                axes[id][index] = axis.map((c) => sign * c) as Vec3;
            }
        }
    });
    return axes;
}

/** The scene the 3D view draws for a pose. The legs are posed by the app's own
 * linkage model rather than by the path tool's IK, so what is drawn is a check
 * on what was solved. */
export function poseToScene(pose: Pose, robot: RobotConfig): Scene {
    const hexapod = posedModel(pose, robot);
    const ground = groundHeight(robot);
    const feet = hexapod.legs.map((leg) => xyz(leg.footTip()));
    const standing = feet.filter((foot) => foot[2] <= ground + GROUND_TOLERANCE);
    return hexapodToScene(hexapod, ground, standing);
}

export function clampDuration(durationMs: unknown): number {
    let duration = Number.NaN;
    if (typeof durationMs === "number" || (typeof durationMs === "string" && durationMs.trim())) {
        duration = pyRound(Number(durationMs));
    }
    if (!Number.isFinite(duration)) {
        duration = DEFAULT_DURATION_MS;
    }
    return Math.min(Math.max(duration, MIN_DURATION_MS), MAX_DURATION_MS);
}

function isNumber(value: unknown): value is number {
    return typeof value === "number" && Number.isInteger(value) && value >= 1;
}

export function makeKeyframe(
    feet: readonly (readonly number[])[],
    durationMs: unknown = DEFAULT_DURATION_MS,
    state?: PoseState | null,
    ease = true,
    number?: number | null,
): Keyframe {
    const keyframe: Keyframe = { feet: cleanFeet(feet), duration_ms: clampDuration(durationMs) };
    if (state && typeof state === "object" && !Array.isArray(state)) {
        keyframe.state = state;
    }
    if (ease === false) {
        keyframe.ease = false;
    }
    if (isNumber(number)) {
        keyframe.number = number;
    }
    return keyframe;
}

/** Whether the move into `keyframe` starts and stops gently. */
export function eases(keyframe: Keyframe): boolean {
    return keyframe.ease !== false;
}

/** The keyframe's number, or null for one not numbered yet. */
export function numberOf(keyframe: Keyframe): number | null {
    return isNumber(keyframe.number) ? keyframe.number : null;
}

/** `keyframe` with a new pose, keeping its time, easing and number. */
export function remade(keyframe: Keyframe, feet: readonly (readonly number[])[], state?: PoseState): Keyframe {
    return makeKeyframe(feet, keyframe.duration_ms, state, eases(keyframe), numberOf(keyframe));
}

/** `keyframe` easing into it, or not, and otherwise as it was. */
export function withEase(keyframe: Keyframe, ease: boolean): Keyframe {
    return makeKeyframe(keyframe.feet, keyframe.duration_ms, keyframe.state, ease, numberOf(keyframe));
}

/** The keyframes without their numbers: how keyframes taken from elsewhere
 * (a gait) go into a sequence, to be numbered after the ones already there. */
export function unnumbered(keyframes: readonly Keyframe[]): Keyframe[] {
    return keyframes.map(({ number: _, ...rest }) => rest);
}

/** The keyframes, each with a number of its own. Those that have one keep it;
 * the rest -- and any that repeat one already taken -- get the next numbers
 * after the highest, in order. */
export function numbered(keyframes: readonly Keyframe[]): Keyframe[] {
    const taken = new Set<number>();
    for (const frame of keyframes) {
        const n = numberOf(frame);
        if (n !== null) {
            taken.add(n);
        }
    }
    let next = Math.max(0, ...taken) + 1;
    const seen = new Set<number>();
    return keyframes.map((frame) => {
        let n = numberOf(frame);
        if (n === null || seen.has(n)) {
            n = next;
            next += 1;
            frame = { ...frame, number: n };
        }
        seen.add(n);
        return frame;
    });
}

/** The keyframes numbered 1, 2, 3... in their order. */
export function renumbered(keyframes: readonly Keyframe[]): Keyframe[] {
    return keyframes.map((frame, index) => ({ ...frame, number: index + 1 }));
}

/** How a keyframe is named in the editor: "#" and its number. */
export function label(keyframe: Keyframe, fallbackIndex?: number): string {
    let n = numberOf(keyframe);
    if (n === null && fallbackIndex !== undefined) {
        n = fallbackIndex + 1;
    }
    return `#${n === null ? "None" : n}`;
}

/** Smoothstep: start and stop each move gently instead of with a jolt. */
function ease(t: number): number {
    return t * t * (3.0 - 2.0 * t);
}

type Sample = [start: number, end: number, t: number];

/** Where each frame of a sequence falls, as [start, end, t]: on the move from
 * keyframe `start` to keyframe `end`, a fraction `t` of the way.
 *
 * Frames are spread evenly in time, at about `fps`, over the moves' total
 * time, so a sequence keeps its timing whatever the frame rate. Without
 * looping the last frame is the last keyframe; looping, the move back to the
 * first keyframe is included but not the first keyframe again, so the frames
 * play round without a seam. */
function samples(keyframes: readonly Keyframe[], fps: number, loop: boolean, speed: number): Sample[] {
    const count = keyframes.length;
    const pairs: [number, number][] = [];
    for (let i = 1; i < count; i++) {
        pairs.push([i - 1, i]);
    }
    if (loop && count > 1) {
        pairs.push([count - 1, 0]);
    }
    const seconds = pairs.map(([, end]) => clampDuration(keyframes[end].duration_ms) / 1000.0 / speed);
    const total = seconds.reduce((a, b) => a + b, 0);

    const out: Sample[] = [[0, 0, 0.0]];
    if (!pairs.length) {
        return out;
    }
    const frames = Math.max(1, pyRound(total * fps));
    let move = 0;
    let moveStart = 0.0;
    const last = loop ? frames : frames + 1;
    for (let frame = 1; frame < last; frame++) {
        const time = (frame * total) / frames;
        while (move < pairs.length - 1 && time > moveStart + seconds[move] + 1e-12) {
            moveStart += seconds[move];
            move += 1;
        }
        const [start, end] = pairs[move];
        out.push([start, end, Math.min(1.0, (time - moveStart) / seconds[move])]);
    }
    return out;
}

/** interpolateFeet() for any values: one flat array per keyframe, timed by the
 * keyframes' durations. Returns the arrays, one per frame. */
export function interpolateArrays(
    points: readonly (readonly number[])[],
    keyframes: readonly Keyframe[],
    fps: number,
    loop = false,
    easeMoves = true,
    speed = 1.0,
): number[][] {
    if (!keyframes.length) {
        return [];
    }
    return samples(keyframes, fps, loop, speed).map(([start, end, t]) => {
        if (easeMoves && eases(keyframes[end])) {
            t = ease(t);
        }
        const a = points[start];
        const b = points[end];
        return a.map((value, i) => value + (b[i] - value) * t);
    });
}

const flat = (feet: readonly (readonly number[])[]) => feet.flatMap((f) => [...f]);
const unflat = (values: readonly number[]): Vec3[] =>
    Array.from({ length: values.length / 3 }, (_, i) => values.slice(i * 3, i * 3 + 3) as Vec3);

/** Foot positions frame by frame, at `fps`, through the keyframes. Each foot
 * moves in a straight line from one keyframe to the next. Each move starts
 * and stops gently into a keyframe that eases; `ease` false makes every move
 * steady. `speed` scales every duration: 2 plays the sequence twice as fast. */
export function interpolateFeet(
    keyframes: readonly Keyframe[],
    fps: number,
    loop = false,
    easeMoves = true,
    speed = 1.0,
): Vec3[][] {
    const points = keyframes.map((k) => flat(k.feet));
    return interpolateArrays(points, keyframes, fps, loop, easeMoves, speed).map(unflat);
}

/** For each frame interpolateArrays() gives, where it falls in the keyframes'
 * own time, whatever the speed: [start, end, ms], `ms` into the move from
 * keyframe `start` to keyframe `end`. The first frame is [0, 0, 0]. */
export function frameTimes(
    keyframes: readonly Keyframe[],
    fps: number,
    loop = false,
    speed = 1.0,
): [number, number, number][] {
    if (!keyframes.length) {
        return [];
    }
    return samples(keyframes, fps, loop, speed).map(([start, end, t]) => [
        start,
        end,
        t ? t * clampDuration(keyframes[end].duration_ms) : 0.0,
    ]);
}

/** When each keyframe is reached, from the first, in ms. */
export function keyframeTimesMs(keyframes: readonly Keyframe[]): number[] {
    let total = 0;
    return keyframes.map((frame, index) => {
        if (index) {
            total += clampDuration(frame.duration_ms);
        }
        return total;
    });
}

/** Poses for each frame of feet: [poses, badFrames]. A straight line between
 * two reachable foot positions can pass out of reach, so this is checked frame
 * by frame rather than assumed from the keyframes being valid. */
export function solveFrames(feetFrames: readonly Vec3[][], robot: RobotConfig): [Pose[], number[]] {
    const poses: Pose[] = [];
    const bad: number[] = [];
    feetFrames.forEach((feet, index) => {
        const [pose, badLegs] = feetToPose(feet, robot);
        poses.push(pose);
        if (badLegs.length) {
            bad.push(index);
        }
    });
    return [poses, bad];
}

/** How long one pass through the keyframes takes, at `speed`. */
export function sequenceDurationMs(keyframes: readonly Keyframe[], loop = false, speed = 1.0): number {
    if (!keyframes.length) {
        return 0;
    }
    const durations = keyframes.map((k) => clampDuration(k.duration_ms));
    const total =
        loop && keyframes.length > 1
            ? durations.reduce((a, b) => a + b, 0)
            : durations.slice(1).reduce((a, b) => a + b, 0);
    return total / speed;
}

export interface KeyframeDocument {
    format: string;
    version: number;
    robot: string;
    keyframes: Keyframe[];
    name?: string;
}

/** The keyframes as a document to save. */
export function dumpDocument(keyframes: readonly Keyframe[], robot: { name: string }): KeyframeDocument {
    return {
        format: FILE_FORMAT,
        version: FILE_VERSION,
        robot: robot.name,
        keyframes: keyframes.map((k) => remade(k, k.feet, k.state)),
    };
}

/** The keyframes as JSON text to save. */
export function dump(keyframes: readonly Keyframe[], robot: { name: string }): string {
    return JSON.stringify(dumpDocument(keyframes, robot), null, 2);
}

function finiteFeet(feet: unknown): feet is number[][] {
    return (
        Array.isArray(feet) &&
        feet.length === 6 &&
        feet.every(
            (foot) =>
                Array.isArray(foot) &&
                foot.length === 3 &&
                foot.every((c) => typeof c === "number" && Number.isFinite(c)),
        )
    );
}

/** Keyframes from a saved document (text, or already parsed).
 *
 * Foot positions only make sense on the robot they were placed for -- another
 * robot's legs are mounted elsewhere and are a different length -- so a file
 * saved for another robot is refused rather than played. */
export function load(text: string | unknown, robot: { name: string }): Keyframe[] {
    let document: any = text;
    if (typeof text === "string") {
        try {
            document = JSON.parse(text);
        } catch (error) {
            throw new KeyframeFileError(`Not a keyframe file: ${(error as Error).message}`);
        }
    }
    if (typeof document !== "object" || document === null || document.format !== FILE_FORMAT) {
        throw new KeyframeFileError("Not a keyframe file.");
    }
    if (document.version !== FILE_VERSION) {
        throw new KeyframeFileError(`Unsupported keyframe file version: ${document.version}.`);
    }
    if (document.robot !== robot.name) {
        throw new KeyframeFileError(
            `These keyframes were made for '${document.robot}', not for '${robot.name}'.`,
        );
    }
    const raw = document.keyframes;
    if (!Array.isArray(raw)) {
        throw new KeyframeFileError("The file has no keyframe list.");
    }
    const keyframes = raw.map((entry, index) => {
        const malformed = (why: string) =>
            new KeyframeFileError(`Keyframe ${index + 1} is malformed: ${why}`);
        if (typeof entry !== "object" || entry === null) {
            throw malformed("not an object");
        }
        if (!finiteFeet(entry.feet)) {
            throw malformed("feet must be six [x, y, z] positions");
        }
        if (!("duration_ms" in entry)) {
            throw malformed("'duration_ms'");
        }
        const easeValue = entry.ease ?? true;
        if (typeof easeValue !== "boolean") {
            throw malformed("ease must be true or false");
        }
        // A file saved before keyframes kept their numbers has none: they are
        // numbered in order.
        const n = entry.number;
        if (n !== undefined && n !== null && !isNumber(n)) {
            throw malformed("number must be a whole number from 1");
        }
        return makeKeyframe(entry.feet, entry.duration_ms, entry.state, easeValue, n);
    });
    return numbered(keyframes);
}
