// One pose in two layers on top of the robot's standby posture, as the
// workspace edits it:
//
//   offsets  how far each foot has been moved from where standby plants it,
//            in the world (6x3, mm).
//   body     how the body is moved and tilted over the planted feet: a shift
//            as a fraction of the body's size, and rotations in degrees, as
//            the body's sliders set them.
//
// The layers add up rather than replace each other, so the body's controls and
// a foot's keep meaning what they say whichever was used last: tilting the
// body keeps the feet where they were put, and moving a foot keeps the tilt.
//
// Out of the layers come the feet in the body frame (keyframes.ts) -- what the
// joints are solved from, what is streamed to the robot -- and the scene,
// drawn in the world with the floor at z = 0.
//
// The world here is the body frame of the robot at standby: x right, y
// forward, z up, the floor at groundHeight(). The view's frame is the same
// raised to put the floor at z = 0.

import * as kf from "./keyframes";
import { BODY_KEYS, type Body, type BodyKey, type Keyframe, type PoseState } from "./keyframes";
import type { Pose } from "./path_generator";
import { frameRotxyz } from "./points";
import {
    getJointLimits,
    getSimulatorDimensions,
    type JointLimits,
    type RobotConfig,
} from "./robot_config";
import { orderAroundCentre, type Scene, type SceneJoint, transformScene } from "./scene";
import { deepEqual, type Mat3, matVec, pyRound, rotationOf, type Vec3 } from "./util";

export { BODY_KEYS, type Body, type BodyKey, type PoseState };

/** The steps a body held within its legs' reach is moved back by, for each of
 * BODY_KEYS: a hundredth of the body's size, a tenth of a degree. */
export const BODY_STEPS = [0.01, 0.01, 0.01, 0.1, 0.1, 0.1];
/** How far inside its limit (degrees) every joint is kept by a body held
 * within reach. Half what a dragged foot keeps, so a pose with a foot held at
 * its own margin is one the body can still be moved from. */
export const BODY_LIMIT_MARGIN_DEG = kf.LIMIT_MARGIN_DEG / 2;

function number(value: unknown): number {
    return pyRound(Number(value || 0), 4);
}

export function makeState(
    body: Partial<Record<BodyKey, unknown>>,
    offsets: readonly (readonly number[])[],
): PoseState {
    return {
        body: Object.fromEntries(BODY_KEYS.map((key) => [key, number(body[key])])) as Body,
        offsets: kf.cleanFeet(offsets),
    };
}

const ZEROS: Vec3[] = Array.from({ length: 6 }, () => [0, 0, 0]);

/** The robot's standby posture, with nothing moved. */
export function standbyState(): PoseState {
    return makeState({}, ZEROS);
}

/** Whether `state` is a pose in layers, e.g. one read back from a file. */
export function isState(state: unknown): state is PoseState {
    if (typeof state !== "object" || state === null) {
        return false;
    }
    const s = state as Record<string, any>;
    if (typeof s.body !== "object" || s.body === null || !Array.isArray(s.offsets)) {
        return false;
    }
    const numbers = BODY_KEYS.map((key) => s.body[key]);
    if (!numbers.every((n) => typeof n === "number" && Number.isFinite(n))) {
        return false;
    }
    return (
        s.offsets.length === 6 &&
        s.offsets.every(
            (o: unknown) =>
                Array.isArray(o) &&
                o.length === 3 &&
                o.every((c) => typeof c === "number" && Number.isFinite(c)),
        )
    );
}

interface Placement {
    planted: Vec3[];
    rotation: Mat3;
    origin: Vec3;
}

/** Where the feet are planted in the world, and the body's frame in it. A
 * point p in the body frame is at rotation @ p + origin in the world. */
export function placement(state: PoseState, robot: RobotConfig): Placement {
    const dimensions = getSimulatorDimensions(robot);
    const body = state.body;
    const rotation = rotationOf(frameRotxyz(body.rot_x, body.rot_y, body.rot_z));
    const origin: Vec3 = [
        body.percent_x * dimensions.middle,
        body.percent_y * dimensions.side,
        body.percent_z * dimensions.tibia,
    ];
    const standby = kf.standbyFeet(robot);
    const planted = standby.map((foot, leg) => [
        foot[0] + state.offsets[leg][0],
        foot[1] + state.offsets[leg][1],
        foot[2] + state.offsets[leg][2],
    ]) as Vec3[];
    return { planted, rotation, origin };
}

/** rotation.T @ p, as numpy computes p @ rotation. */
function intoBody(p: readonly number[], rotation: Mat3): Vec3 {
    return [0, 1, 2].map(
        (j) => p[0] * rotation[0][j] + p[1] * rotation[1][j] + p[2] * rotation[2][j],
    ) as Vec3;
}

/** The feet in the body frame: what the joints are solved from. */
export function bodyFeet(state: PoseState, robot: RobotConfig): Vec3[] {
    const { planted, rotation, origin } = placement(state, robot);
    return kf.cleanFeet(
        planted.map((p) =>
            intoBody([p[0] - origin[0], p[1] - origin[1], p[2] - origin[2]], rotation),
        ),
    );
}

/** [feet, pose, badLegs] for a state; see feetToPose(). */
export function solve(state: PoseState, robot: RobotConfig): [Vec3[], Pose, number[]] {
    const feet = bodyFeet(state, robot);
    const [pose, bad] = kf.feetToPose(feet, robot);
    return [feet, pose, bad];
}

/** Where the feet are planted, in the view's coordinates (floor at z = 0). */
export function viewFeet(state: PoseState, robot: RobotConfig): Vec3[] {
    const { planted } = placement(state, robot);
    const ground = kf.groundHeight(robot);
    return kf.cleanFeet(planted.map((p) => [p[0], p[1], p[2] - ground]));
}

function withOffset(state: PoseState, leg: number, offset: readonly number[]): PoseState {
    const offsets = state.offsets.map((o) => [...o]);
    offsets[leg] = [...offset];
    return makeState(state.body, offsets);
}

/** The state with one foot moved to `target`, in the view's coordinates. */
export function withFootAt(
    state: PoseState,
    leg: number,
    target: readonly number[],
    robot: RobotConfig,
): PoseState {
    const ground = kf.groundHeight(robot);
    const standby = kf.standbyFeet(robot)[leg];
    return withOffset(state, leg, [
        target[0] + 0.0 - standby[0],
        target[1] + 0.0 - standby[1],
        target[2] + ground - standby[2],
    ]);
}

function backToWorld(foot: readonly number[], p: Placement, standby: Vec3): Vec3 {
    const turned = matVec(p.rotation, foot);
    return [
        turned[0] + p.origin[0] - standby[0],
        turned[1] + p.origin[1] - standby[1],
        turned[2] + p.origin[2] - standby[2],
    ];
}

/** withFootAt() for a foot being dragged: at `target` if its leg can reach
 * it, else as near as the leg gets, so the leg follows along the edge of its
 * reach. null if it gets nowhere. */
export function withFootNear(
    state: PoseState,
    leg: number,
    target: readonly number[],
    robot: RobotConfig,
): PoseState | null {
    const p = placement(state, robot);
    const ground = kf.groundHeight(robot);
    const world = [target[0] + 0.0, target[1] + 0.0, target[2] + ground];
    const local = intoBody(
        [world[0] - p.origin[0], world[1] - p.origin[1], world[2] - p.origin[2]],
        p.rotation,
    );
    const foot = kf.nearestReachableFoot(local, leg, robot);
    if (foot === null) {
        return null;
    }
    return withOffset(state, leg, backToWorld(foot, p, kf.standbyFeet(robot)[leg]));
}

/** The state with one leg's joints set, for those given: its foot goes
 * wherever those angles put it, the body staying. */
export function withLegAngles(
    state: PoseState,
    leg: number,
    angles: Partial<Record<keyof JointLimits, number>>,
    robot: RobotConfig,
): PoseState {
    const [, solved] = solve(state, robot);
    const pose = solved.map((joints) => ({ ...joints }));
    Object.assign(pose[leg], angles);
    const foot = kf.poseToFeet(pose, robot)[leg];
    return withOffset(
        state,
        leg,
        backToWorld(foot, placement(state, robot), kf.standbyFeet(robot)[leg]),
    );
}

export interface BodyFrame {
    origin: Vec3;
    rot: Vec3;
}

/** Where the body is, as the view's handle on it has it: origin in the view's
 * coordinates, and its rotations about x, y and z in degrees. */
export function bodyFrame(state: PoseState, robot: RobotConfig): BodyFrame {
    const { origin } = placement(state, robot);
    const ground = kf.groundHeight(robot);
    return {
        origin: [pyRound(origin[0], 3), pyRound(origin[1], 3), pyRound(origin[2] - ground, 3)],
        rot: [state.body.rot_x, state.body.rot_y, state.body.rot_z],
    };
}

/** The body layer that puts the body at `origin`, turned by `rot`: what
 * bodyFrame() gives back. Not held to any range; that is the caller's. */
export function bodyAt(
    origin: readonly number[],
    rot: readonly number[],
    robot: RobotConfig,
): Body {
    const d = getSimulatorDimensions(robot);
    const ground = kf.groundHeight(robot);
    const world = [origin[0] + 0.0, origin[1] + 0.0, origin[2] + ground];
    const sizes = [d.middle, d.side, d.tibia];
    const shift = world.map((c, i) => (sizes[i] ? c / sizes[i] : 0.0));
    const values = [...shift, ...rot.map(Number)];
    return Object.fromEntries(BODY_KEYS.map((key, i) => [key, values[i]])) as Body;
}

/** Whether every leg reaches its foot, each joint `margin` degrees inside its
 * limit. */
function reaches(state: PoseState, robot: RobotConfig, margin: number): boolean {
    return kf.feetToPose(bodyFeet(state, robot), robot, margin)[1].length === 0;
}

/** The state with the body moved to `body`, or as far that way as its legs
 * can follow: how a body dragged, or slid, past what they reach stops there
 * instead of leaving them behind.
 *
 * Each of the body's moves and turns goes as far towards `body` as the legs
 * reach, one after the other in BODY_STEPS, so a body pushed two ways at once
 * still goes the way it can. A body whose legs are out of reach already goes
 * where it is put: there is nothing to hold it to. */
export function withBodyNear(state: PoseState, body: Partial<Body>, robot: RobotConfig): PoseState {
    const target = makeState(body, state.offsets);
    const margins = [BODY_LIMIT_MARGIN_DEG, 0.0].filter((m) => reaches(state, robot, m));
    if (!margins.length || reaches(target, robot, margins[0])) {
        return target;
    }
    const held: Body = { ...state.body };
    const fits = (key: BodyKey, value: number) =>
        reaches(makeState({ ...held, [key]: value }, state.offsets), robot, margins[0]);

    BODY_KEYS.forEach((key, index) => {
        const step = BODY_STEPS[index];
        const start = held[key];
        const goal = target.body[key];
        // Back from where it was asked to go, a step at a time, to where it
        // is: the fewest steps back that the legs reach, found by halving.
        const steps = Math.ceil(Math.abs(goal - start) / step);
        const back = start > goal ? step : -step;
        const stepped = (count: number) => (count >= steps ? start : goal + count * back);
        let fewest = 0;
        let most = steps;
        while (fewest < most) {
            const middle = Math.floor((fewest + most) / 2);
            if (fits(key, stepped(middle))) {
                most = middle;
            } else {
                fewest = middle + 1;
            }
        }
        held[key] = stepped(fewest);
    });
    return makeState(held, state.offsets);
}

/** A state for feet given only in the body frame (a keyframe saved before
 * keyframes kept their layers): the body unmoved, the feet as moves from
 * standby. */
export function fromFeet(feet: readonly (readonly number[])[], robot: RobotConfig): PoseState {
    const standby = kf.standbyFeet(robot);
    return makeState(
        {},
        feet.map((f, leg) => [
            f[0] - standby[leg][0],
            f[1] - standby[leg][1],
            f[2] - standby[leg][2],
        ]),
    );
}

/** How far either way (degrees) a joint is turned by its ring in the view: a
 * little inside its limit, so the leg can still be solved. */
export function jointMost(
    joint: keyof JointLimits,
    robot: RobotConfig,
    limits?: JointLimits,
): number {
    limits = limits ?? getJointLimits(robot);
    return pyRound(Math.max(Number(limits[joint]) - kf.LIMIT_MARGIN_DEG, 0.0), 3);
}

/** Each joint as the view's ring on it has it: per leg, per joint, the axis a
 * positive angle turns it about in the world (null where that cannot be
 * told), where it is, and how far either way the ring turns it. */
export function sceneJoints(pose: Pose, rotation: Mat3, robot: RobotConfig): SceneJoint[][] {
    const axes = kf.jointAxes(pose, robot);
    const limits = getJointLimits(robot);
    return pose.map((leg, id) =>
        (["coxia", "femur", "tibia"] as const).map((name, index) => {
            const axis = axes[id][index];
            return {
                axis: axis ? (matVec(rotation, axis).map((c) => pyRound(c, 6)) as Vec3) : null,
                angle: pyRound(leg[name], 3),
                most: jointMost(name, robot, limits),
            };
        }),
    );
}

/** The pose drawn in the world, the floor at z = 0. The support polygon goes
 * through the feet standing on the floor. Nothing settles the body: as on the
 * robot, it is where the layers put it. With the body's frame, for the view's
 * handle on it. */
export function scene(state: PoseState, pose: Pose, robot: RobotConfig): Scene {
    const { rotation, origin } = placement(state, robot);
    const ground = kf.groundHeight(robot);
    const drawn = transformScene(kf.poseToScene(pose, robot), rotation, [
        origin[0] + 0.0,
        origin[1] + 0.0,
        origin[2] - ground,
    ]);
    const standing = drawn.feet.filter((foot) => foot[2] <= kf.GROUND_TOLERANCE);
    drawn.support = orderAroundCentre(standing).map(([x, y]) => [x, y, 0.0] as Vec3);
    drawn.ground = 0.0;
    drawn.frame = bodyFrame(state, robot);
    drawn.joints = sceneJoints(pose, rotation, robot);
    return drawn;
}

/** The layers as one flat array, to interpolate between states. */
export function stateToVector(state: PoseState): number[] {
    return [...BODY_KEYS.map((key) => state.body[key]), ...state.offsets.flat()];
}

/** stateToVector() run backwards. */
export function vectorToState(vector: readonly number[]): PoseState {
    const body = Object.fromEntries(BODY_KEYS.map((key, i) => [key, vector[i]])) as Body;
    const rest = vector.slice(BODY_KEYS.length);
    const offsets = Array.from({ length: 6 }, (_, i) => rest.slice(i * 3, i * 3 + 3));
    return makeState(body, offsets);
}

export interface Sequence {
    feet: Vec3[][];
    states: PoseState[] | null;
    poses: Pose[];
    badFrames: number[];
}

/** The frames of a sequence, played at `speed`.
 *
 * When every keyframe kept its layers, the layers are what is interpolated, so
 * a body tilting between two keyframes tilts over planted feet. Otherwise each
 * foot moves in a straight line in the body frame, and `states` is null. */
export function sequence(
    keyframes: readonly Keyframe[],
    robot: RobotConfig,
    fps: number,
    loop = false,
    ease = true,
    speed = 1.0,
): Sequence {
    let feet: Vec3[][];
    let states: PoseState[] | null;
    if (keyframes.length && keyframes.every((frame) => isState(frame.state))) {
        const vectors = keyframes.map((frame) => stateToVector(frame.state as PoseState));
        states = kf
            .interpolateArrays(vectors, keyframes, fps, loop, ease, speed)
            .map(vectorToState);
        feet = states.map((state) => bodyFeet(state, robot));
    } else {
        states = null;
        feet = kf.interpolateFeet(keyframes, fps, loop, ease, speed);
    }
    const [poses, badFrames] = kf.solveFrames(feet, robot);
    return { feet, states, poses, badFrames };
}

/** Whether two states are the same pose. */
export function sameState(a: PoseState, b: PoseState): boolean {
    return deepEqual(a, b);
}
