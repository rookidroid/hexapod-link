// The robot's gaits as foot paths, and the inverse kinematics that turns them
// into joint angles: a port of the firmware repo's path_tool, which bakes the
// same paths into the LUTs the robot plays from flash.
//
// Geometry and gait parameters differ between robots and are read from the
// robot itself; see robot_config.ts.
import { LEG_NAMES } from "./naming";
import { DEFAULT_CONFIG, type Geometry, getLegSigns, type RobotConfig } from "./robot_config";
import { degrees, matMul, matVec, type Vec3 } from "./util";

/** One frame of a path: six feet. */
export type Stance = Vec3[];
/** Frames of six feet. */
export type Path = Stance[];

export interface LegPose {
    id: number;
    name: string;
    coxia: number;
    femur: number;
    tibia: number;
}
/** A pose: each leg's joint angles in degrees, in leg order. */
export type Pose = LegPose[];

const PI = Math.PI;

function zeros(steps: number): Vec3[] {
    return Array.from({ length: steps }, () => [0, 0, 0] as Vec3);
}

/** np.roll along the first axis. */
function roll<T>(rows: readonly T[], shift: number): T[] {
    const n = rows.length;
    return rows.map((_, i) => rows[(((i - shift) % n) + n) % n]);
}

function copyRows(rows: readonly Vec3[]): Vec3[] {
    return rows.map((r) => [...r] as Vec3);
}

/** np.linspace, as numpy computes it. */
function linspace(start: number, stop: number, num: number): number[] {
    const step = (stop - start) / (num - 1);
    const out = Array.from({ length: num }, (_, i) => i * step + start);
    out[num - 1] = stop;
    return out;
}

// --- Path Library Functions (from path_tool/path_lib.py) ---

export function semicircleGenerator(radius: number, steps: number, reverse = false): Vec3[] {
    if (steps % 4 !== 0) {
        throw new Error("steps must be a multiple of 4");
    }
    const halfsteps = Math.trunc(steps / 2);
    const stepAngle = PI / halfsteps;
    let result = zeros(steps);
    for (let i = 0; i < halfsteps; i++) {
        result[i][1] = radius - (i * radius * 2) / halfsteps;
        const angle = PI - stepAngle * i;
        result[halfsteps + i][1] = radius * Math.cos(angle);
        result[halfsteps + i][2] = radius * Math.sin(angle);
    }
    result = roll(result, Math.trunc(steps / 4));
    if (reverse) {
        result = roll([...result].reverse(), 1);
    }
    return copyRows(result);
}

export function semicircle2Generator(
    steps: number,
    yRadius: number,
    zRadius: number,
    xRadius: number,
    reverse = false,
): Vec3[] {
    if (steps % 4 !== 0) {
        throw new Error("steps must be a multiple of 4");
    }
    const halfsteps = Math.trunc(steps / 2);
    const stepAngle = PI / halfsteps;
    let result = zeros(steps);
    for (let i = 0; i < halfsteps; i++) {
        result[i][1] = yRadius - (i * yRadius * 2) / halfsteps;
        const angle = PI - stepAngle * i;
        result[halfsteps + i][0] = xRadius * Math.sin(angle);
        result[halfsteps + i][1] = yRadius * Math.cos(angle);
        result[halfsteps + i][2] = zRadius * Math.sin(angle);
    }
    result = roll(result, Math.trunc(steps / 4));
    if (reverse) {
        result = roll([...result].reverse(), 1);
    }
    return copyRows(result);
}

export function rotateXMatrix(angle: number): number[][] {
    const a = (angle * PI) / 180;
    return [
        [1, 0, 0, 0],
        [0, Math.cos(a), -Math.sin(a), 0],
        [0, Math.sin(a), Math.cos(a), 0],
        [0, 0, 0, 1],
    ];
}

export function rotateYMatrix(angle: number): number[][] {
    const a = (angle * PI) / 180;
    return [
        [Math.cos(a), 0, Math.sin(a), 0],
        [0, 1, 0, 0],
        [-Math.sin(a), 0, Math.cos(a), 0],
        [0, 0, 0, 1],
    ];
}

export function rotateZMatrix(angle: number): number[][] {
    const a = (angle * PI) / 180;
    return [
        [Math.cos(a), -Math.sin(a), 0, 0],
        [Math.sin(a), Math.cos(a), 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ];
}

/** Each point moved by a 4x4 frame. */
function transformPoints(m: number[][], points: readonly Vec3[]): Vec3[] {
    return points.map((p) => matVec(m, [p[0], p[1], p[2], 1]).slice(0, 3) as Vec3);
}

export function pathRotateZ(path: readonly Vec3[], angle: number): Vec3[] {
    return transformPoints(rotateZMatrix(angle), path);
}

/** Servo angles (j1, j2, j3 per leg, degrees, 90 the servo's middle) that put
 * the six feet at `dest`; NaN for a foot out of reach. */
export function inverseKinematics(dest: readonly (readonly number[])[], config: Geometry): Vec3[] {
    const rootJ1 = config.legRootToJoint1;
    const j1j2 = config.legJoint1ToJoint2;
    const j2j3 = config.legJoint2ToJoint3;
    const j3Tip = config.legJoint3ToTip;
    return dest.map((target, leg) => {
        const mountAngle = (config.legMountAngle[leg] / 180) * PI;
        const tx = target[0] - config.legMountX[leg];
        const ty = target[1] - config.legMountY[leg];
        const tz = target[2] - 0;
        const lx = tx * Math.cos(mountAngle) + ty * Math.sin(mountAngle);
        const ly = tx * Math.sin(mountAngle) - ty * Math.cos(mountAngle);
        const lz = tz;
        const scale = config.legScale[leg][1];

        let x = lx - rootJ1;
        let y = ly;
        const a0 = -((Math.atan2(y, x) * 180) / PI) + 90;
        x = Math.sqrt(x * x + y * y) - j1j2;
        y = lz;
        const ar = Math.atan2(y, x);
        const lr2 = x * x + y * y;
        const lr = Math.sqrt(lr2);
        const a1 = Math.acos((lr2 + j2j3 * j2j3 - j3Tip * j3Tip) / (2 * j2j3 * lr));
        const a2 = Math.acos((lr2 - j2j3 * j2j3 + j3Tip * j3Tip) / (2 * j3Tip * lr));
        return [
            a0,
            90 - (((ar + a1) * 180) / PI) * scale,
            (90 - ((a1 + a2) * 180) / PI) * scale + 90,
        ] as Vec3;
    });
}

// --- Path Generation Functions (from path_tool/path_tool.py) ---

export function genPosture(j2Angle: number, j3Angle: number, config: Geometry): Stance {
    const rootJ1 = config.legRootToJoint1;
    const j1j2 = config.legJoint1ToJoint2;
    const j2j3 = config.legJoint2ToJoint3;
    const j3Tip = config.legJoint3ToTip;
    const j2 = (j2Angle / 180) * PI;
    const j3 = (j3Angle / 180) * PI;
    return config.legMountAngle.map((angleDeg, leg) => {
        const mountAngle = (angleDeg / 180) * PI;
        const reach = rootJ1 + j1j2 + j2j3 * Math.sin(j2) + j3Tip * Math.cos(j3);
        return [
            config.legMountX[leg] + reach * Math.cos(mountAngle),
            config.legMountY[leg] + reach * Math.sin(mountAngle),
            j2j3 * Math.cos(j2) - j3Tip * Math.sin(j3),
        ] as Vec3;
    });
}

/** Six legs' strokes (each steps x 3) plus the standby stance: steps x 6 x 3. */
function legsPath(strokes: Vec3[][], standby: Stance): Path {
    const steps = strokes[0].length;
    return Array.from({ length: steps }, (_, step) =>
        strokes.map((stroke, leg) => [
            stroke[step][0] + standby[leg][0],
            stroke[step][1] + standby[leg][1],
            stroke[step][2] + standby[leg][2],
        ]),
    ) as Path;
}

export function genWalkPath(standby: Stance, gSteps = 28, gRadius = 30, direction = 0): Path {
    const halfsteps = Math.trunc(gSteps / 2);
    const semi = pathRotateZ(semicircleGenerator(gRadius, gSteps), direction);
    const mir = roll(semi, halfsteps);
    return legsPath([semi, mir, semi, mir, semi, mir], standby);
}

export function genFastwalkPath(
    standby: Stance,
    gSteps = 20,
    yRadius = 50,
    zRadius = 40,
    xRadius = 15,
    reverse = false,
): Path {
    const halfsteps = Math.trunc(gSteps / 2);
    const r = semicircle2Generator(gSteps, yRadius, zRadius, xRadius, reverse);
    const l = semicircle2Generator(gSteps, yRadius, zRadius, -xRadius, reverse);
    const rMir = roll(r, halfsteps);
    const lMir = roll(l, halfsteps);
    return legsPath([r, rMir, r, lMir, l, lMir], standby);
}

export function genTurnPath(standby: Stance, gSteps = 28, gRadius = 35, direction = "left"): Path {
    // semicircleGenerator strokes along +y, so rotating a leg's stroke by that
    // leg's azimuth from the cog aims it tangent to the turn circle. The
    // azimuth is read off the standby stance rather than hardcoded, which is
    // right whatever the body's proportions.
    const halfsteps = Math.trunc(gSteps / 2);
    const semi = semicircleGenerator(gRadius, gSteps);
    const mir = roll(semi, halfsteps);
    const azimuths = standby.map((foot) => degrees(Math.atan2(foot[1], foot[0])));
    // An unrecognised direction leaves the path at zero, i.e. standing by.
    const strokes = standby.map((_, leg) => {
        if (direction !== "left" && direction !== "right") {
            return zeros(gSteps);
        }
        const offset = direction === "left" ? 0 : 180;
        const stroke = leg === 0 || leg === 2 || leg === 4 ? semi : mir;
        return pathRotateZ(stroke, azimuths[leg] + offset);
    });
    return legsPath(strokes, standby);
}

export function genClimbPath(
    standby: Stance,
    gSteps = 28,
    yRadius = 20,
    zRadius = 80,
    xRadius = 30,
    zShift = -30,
    reverse = false,
): Path {
    const halfsteps = Math.trunc(gSteps / 2);
    const r = semicircle2Generator(gSteps, yRadius, zRadius, xRadius, reverse);
    const l = semicircle2Generator(gSteps, yRadius, zRadius, -xRadius, reverse);
    for (const p of [...r, ...l]) {
        p[2] = p[2] + zShift;
    }
    const rMir = roll(r, halfsteps);
    const lMir = roll(l, halfsteps);
    return legsPath([r, rMir, r, lMir, l, lMir], standby);
}

/** The swaying gaits: the stance moved by a frame per step. */
function swayPath(standby: Stance, frames: number[][][]): Path {
    return frames.map((m) => transformPoints(m, standby));
}

function swing(
    standby: Stance,
    gSteps: number,
    swingAngle: number,
    radius: number,
    rotate: (angle: number) => number[][],
): Path {
    const quarter = Math.trunc(gSteps / 4);
    const stepAngle = swingAngle / quarter;
    const stepOffset = radius / quarter;
    const frames: number[][][] = [];
    const at = (angle: number, offset: number) => {
        const m = rotate(angle);
        m[1][3] = offset;
        frames.push(m);
    };
    for (let i = 0; i < quarter; i++) at(swingAngle - i * stepAngle, -i * stepOffset);
    for (let i = 0; i < quarter; i++) at(-i * stepAngle, -radius + i * stepOffset);
    for (let i = 0; i < quarter; i++) at(i * stepAngle - swingAngle, i * stepOffset);
    for (let i = 0; i < quarter; i++) at(i * stepAngle, radius - i * stepOffset);
    const path = swayPath(standby, frames);
    // A step count that is not a multiple of four leaves the last frames at
    // zero, as path_tool does.
    while (path.length < gSteps) {
        path.push(zeros(6));
    }
    return path;
}

export function genRotatexPath(standby: Stance, gSteps = 28, swingAngle = 15, yRadius = 15): Path {
    return swing(standby, gSteps, swingAngle, yRadius, rotateXMatrix);
}

export function genRotateyPath(standby: Stance, gSteps = 28, swingAngle = 15, xRadius = 15): Path {
    return swing(standby, gSteps, swingAngle, xRadius, rotateYMatrix);
}

export function genRotatezPath(standby: Stance, gSteps = 28, zLift = 4.5, xyRadius = 1): Path {
    const stepAngle = (2 * PI) / gSteps;
    const frames = Array.from({ length: gSteps }, (_, i) => {
        const x = xyRadius * Math.cos(i * stepAngle);
        const y = xyRadius * Math.sin(i * stepAngle);
        return matMul(
            rotateYMatrix((Math.atan2(x, zLift) * 180) / PI),
            rotateXMatrix((Math.atan2(y, zLift) * 180) / PI),
        );
    });
    return swayPath(standby, frames);
}

export function genTwistPath(
    standby: Stance,
    gSteps = 28,
    raiseAngle = 3,
    twistXAngle = 20,
    twistYAngle = 12,
): Path {
    const quarter = Math.trunc(gSteps / 4);
    const stepX = twistXAngle / quarter;
    const stepY = twistYAngle / quarter;
    const m = rotateXMatrix(raiseAngle);
    const frame = (z: number, x: number) => matMul(matMul(m, rotateZMatrix(z)), rotateXMatrix(x));
    const frames: number[][][] = [];
    for (let i = 0; i < quarter; i++) frames.push(frame(i * stepX, i * stepY));
    for (let i = 0; i < quarter; i++)
        frames.push(frame((quarter - i) * stepX, (quarter - i) * stepY));
    for (let i = 0; i < quarter; i++) frames.push(frame(-i * stepX, i * stepY));
    for (let i = 0; i < quarter; i++)
        frames.push(frame((-quarter + i) * stepX, (quarter - i) * stepY));
    const path = swayPath(standby, frames);
    while (path.length < gSteps) {
        path.push(zeros(6));
    }
    return path;
}

export function genStandupPath(standby: Stance, laydownIn: Stance, steps = 28): Path {
    const laydown = copyRows(laydownIn);
    const liftUpSize = 10;
    const adjustLegSize = Math.trunc((steps - liftUpSize) / 2);
    const lut: Path = Array.from({ length: steps }, () => zeros(6));
    linspace(laydown[0][2], standby[0][2], liftUpSize).forEach((z, idx) => {
        for (const foot of laydown) {
            foot[2] = z;
        }
        lut[idx] = copyRows(laydown);
    });
    const radius = (lut[liftUpSize - 1][1][0] - standby[1][0]) / 2;
    const stepAngle = PI / adjustLegSize;
    const centreOffset: Vec3[] = Array.from({ length: adjustLegSize }, (_, k) => {
        const angle = (k + 1) * stepAngle;
        return [radius * Math.cos(angle) - radius, 0, radius * Math.sin(angle)];
    });
    // The reposition arc for the centre-right leg, which lies along +x, turned
    // into the direction each foot travels between laydown and standby.
    const azimuths = laydown.map((foot, leg) =>
        degrees(Math.atan2(foot[1] - standby[leg][1], foot[0] - standby[leg][0])),
    );
    const legOffset = azimuths.map((azimuth) => pathRotateZ(centreOffset, azimuth));
    // The two tripods reposition in turn, each holding still while the other
    // moves, so a tripod's run starts from the pose the previous one left.
    let start = liftUpSize;
    for (const tripod of [
        [3, 1, 5],
        [0, 4, 2],
    ]) {
        const base = copyRows(lut[start - 1]);
        for (let idx = 0; idx < adjustLegSize; idx++) {
            const stance = copyRows(base);
            for (const leg of tripod) {
                stance[leg] = [
                    stance[leg][0] + legOffset[leg][idx][0],
                    stance[leg][1] + legOffset[leg][idx][1],
                    stance[leg][2] + legOffset[leg][idx][2],
                ];
            }
            lut[start + idx] = stance;
        }
        start += adjustLegSize;
    }
    return lut;
}

// --- Bridge to the app ---

/** The path of a motion for a robot, one stance per frame. */
export function motionPath(motionName: string, robot: RobotConfig = DEFAULT_CONFIG): Path {
    const config = robot.config;
    const gait = robot.gait;
    const standby = genPosture(gait.standby_posture[0], gait.standby_posture[1], config);
    const laydown = genPosture(gait.laydown_posture[0], gait.laydown_posture[1], config);
    const walk = (direction: number) => genWalkPath(standby, 28, gait.walk_radius, direction);
    const f = gait.fastwalk;
    switch (motionName) {
        case "walk_0":
            return walk(0);
        case "walk_180":
            return walk(180);
        case "walk_r45":
            return walk(315);
        case "walk_r90":
            return walk(270);
        case "walk_r135":
            return walk(225);
        case "walk_l45":
            return walk(45);
        case "walk_l90":
            return walk(90);
        case "walk_l135":
            return walk(135);
        case "fast_forward":
            return genFastwalkPath(standby, f.g_steps, f.y_radius, f.z_radius, f.x_radius);
        case "fast_backward":
            return genFastwalkPath(standby, f.g_steps, f.y_radius, f.z_radius, f.x_radius, true);
        case "turn_left":
            return genTurnPath(standby, 28, gait.turn_radius, "left");
        case "turn_right":
            return genTurnPath(standby, 28, gait.turn_radius, "right");
        case "climb_forward":
            return genClimbPath(standby);
        case "climb_backward":
            return genClimbPath(standby, 28, 20, 80, 30, -30, true);
        case "rotate_x":
            return genRotatexPath(
                standby,
                gait.rotate_x.g_steps,
                gait.rotate_x.swing_angle,
                gait.rotate_x.y_radius,
            );
        case "rotate_y":
            return genRotateyPath(
                standby,
                gait.rotate_y.g_steps,
                gait.rotate_y.swing_angle,
                gait.rotate_y.x_radius,
            );
        case "rotate_z":
            return genRotatezPath(
                standby,
                gait.rotate_z.g_steps,
                gait.rotate_z.z_lift,
                gait.rotate_z.xy_radius ?? 1,
            );
        case "twist":
            return genTwistPath(standby, gait.twist.g_steps);
        case "standup":
            return genStandupPath(standby, laydown, gait.standup_steps);
        default:
            return [standby];
    }
}

/** The poses of a motion for a robot, one per frame. Robots differ in leg
 * geometry and in stride and turn radii, so a path baked for one is wrong for
 * another. */
export function generatePoses(motionName: string, robot: RobotConfig = DEFAULT_CONFIG): Pose[] {
    const signs = getLegSigns(robot);
    return motionPath(motionName, robot).map((stance) =>
        servoAnglesToPose(inverseKinematics(stance, robot.config), signs),
    );
}

/** Map path-tool servo angles (6x3, j1/j2/j3 per leg) to a pose:
 *
 *   j1 = 90 + alpha              (every leg; the mirroring is already folded
 *                                 into the path tool's local frame)
 *   j2 = 90 - sign * beta
 *   j3 = 90 + sign * gamma       sign = the leg's legScale
 */
export function servoAnglesToPose(angles: readonly (readonly number[])[], signs: number[]): Pose {
    return angles.map(([j1, j2, j3], leg) => ({
        id: leg,
        name: LEG_NAMES[leg],
        coxia: j1 - 90,
        femur: signs[leg] * (90 - j2),
        tibia: signs[leg] * (j3 - 90),
    }));
}
