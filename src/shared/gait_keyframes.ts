// The robot's gaits worked out as keyframes. Once in a sequence they are
// keyframes like any other -- nothing marks where they came from -- to
// retime, edit, mix with poses of one's own or put in twice.
//
// A gait from the path generator (path_generator.ts) is a pose every frame of
// the robot's own timing -- 20 to 28 to a cycle -- with the feet on
// semicircles. Each pose is first held to the robot's joint limits, as the
// robot holds it when it plays the gait itself: some robots' gaits ask for a
// little more (Mochi's walk takes its femurs a few ticks past). Then each
// frame is turned into layers (pose_layers.ts):
//
//   * a frame in which the six feet are the standby stance moved as one -- the
//     Rotate gaits and Twist -- is the body moving over planted feet, so it
//     goes into the body layer, and is drawn and edited as a tilt;
//   * any other is feet moving, so it goes into the offsets, the body raised
//     or lowered to keep the lowest foot on the floor (Climb lowers them all).
//
// Then only the frames needed are kept: as few as leave every foot within
// TOLERANCE_MM of the gait's own path, and every joint within its limits, when
// the sequence is played, which moves in straight lines between them. The
// times between them are the robot's own, at full speed, and none of the moves
// is eased, so a sequence played at 100 % walks as the robot does, and looping
// a cycle has no seam.

import type { Keyframe, PoseState } from "./keyframes";
import * as kf from "./keyframes";
import { generatePoses, type Pose } from "./path_generator";
import * as pl from "./pose_layers";
import {
    getJointLimits,
    getSequenceFps,
    getSimulatorDimensions,
    type RobotConfig,
} from "./robot_config";
import { degrees, identity3, type Mat3, matVec, type Vec3 } from "./util";

/** How far (mm) a foot may stray from the gait's own path between keyframes. */
export const TOLERANCE_MM = 1.0;

/** How closely (mm) the six feet must fit the stance moved as one for a frame
 * to count as the body moving. */
export const RIGID_MM = 2.0;

/** Gaits that are not cycles: played once, from the first frame to the last. */
export const ONE_SHOT = new Set(["standup"]);

/** Points checked against the joints' limits between two frames of the gait,
 * since a sequence played at another speed or frame rate lands between them. */
const LIMIT_CHECKS_PER_FRAME = 4;

/** The gait's poses, each joint held to the robot's limits. */
export function robotPoses(motionName: string, robot: RobotConfig): Pose[] {
    const limits = getJointLimits(robot);
    const poses = generatePoses(motionName, robot);
    for (const pose of poses) {
        for (const leg of pose) {
            for (const joint of ["coxia", "femur", "tibia"] as const) {
                const limit = limits[joint] - kf.LIMIT_MARGIN_DEG;
                leg[joint] = Math.min(Math.max(leg[joint], -limit), limit);
            }
        }
    }
    return poses;
}

/** (rot_x, rot_y, rot_z) in degrees, with frameRotxyz() of them being
 * `rotation`: Rx @ Ry @ Rz. */
function rotationAngles(r: Mat3): Vec3 {
    const rotY = degrees(Math.asin(Math.min(Math.max(r[0][2], -1.0), 1.0)));
    const rotX = degrees(Math.atan2(-r[1][2], r[2][2]));
    const rotZ = degrees(Math.atan2(-r[0][1], r[0][0]));
    return [rotX, rotY, rotZ];
}

/** Eigenvector of the largest eigenvalue of a symmetric 4x4 (Jacobi). */
function principalEigenvector(input: number[][]): number[] {
    const a = input.map((row) => [...row]);
    const v: number[][] = [0, 1, 2, 3].map((i) => [0, 1, 2, 3].map((j) => (i === j ? 1 : 0)));
    for (let sweep = 0; sweep < 100; sweep++) {
        let off = 0;
        for (let p = 0; p < 4; p++) for (let q = p + 1; q < 4; q++) off += a[p][q] * a[p][q];
        if (off < 1e-30) break;
        for (let p = 0; p < 4; p++) {
            for (let q = p + 1; q < 4; q++) {
                if (Math.abs(a[p][q]) < 1e-300) continue;
                const theta = (a[q][q] - a[p][p]) / (2 * a[p][q]);
                const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
                const c = 1 / Math.sqrt(t * t + 1);
                const s = t * c;
                for (let k = 0; k < 4; k++) {
                    const akp = a[k][p];
                    const akq = a[k][q];
                    a[k][p] = c * akp - s * akq;
                    a[k][q] = s * akp + c * akq;
                }
                for (let k = 0; k < 4; k++) {
                    const apk = a[p][k];
                    const aqk = a[q][k];
                    a[p][k] = c * apk - s * aqk;
                    a[q][k] = s * apk + c * aqk;
                }
                for (let k = 0; k < 4; k++) {
                    const vkp = v[k][p];
                    const vkq = v[k][q];
                    v[k][p] = c * vkp - s * vkq;
                    v[k][q] = s * vkp + c * vkq;
                }
            }
        }
    }
    let best = 0;
    for (let i = 1; i < 4; i++) if (a[i][i] > a[best][best]) best = i;
    return [0, 1, 2, 3].map((k) => v[k][best]);
}

/** The rotation R and origin o that best put `feet` on `standby`, R @ f + o
 * (least squares, a proper rotation: Horn's quaternion form of Kabsch), and
 * how far from it the worst foot is left. */
function rigidFit(feet: Vec3[], standby: Vec3[]): [Mat3, Vec3, number] {
    const mean = (points: Vec3[]) =>
        [0, 1, 2].map((i) => points.reduce((s, p) => s + p[i], 0) / points.length) as Vec3;
    const fc = mean(feet);
    const sc = mean(standby);
    const h = [0, 1, 2].map(() => [0, 0, 0]);
    feet.forEach((f, n) => {
        for (let i = 0; i < 3; i++)
            for (let j = 0; j < 3; j++) h[i][j] += (f[i] - fc[i]) * (standby[n][j] - sc[j]);
    });
    const [[sxx, sxy, sxz], [syx, syy, syz], [szx, szy, szz]] = h;
    const n = [
        [sxx + syy + szz, syz - szy, szx - sxz, sxy - syx],
        [syz - szy, sxx - syy - szz, sxy + syx, szx + sxz],
        [szx - sxz, sxy + syx, -sxx + syy - szz, syz + szy],
        [sxy - syx, szx + sxz, syz + szy, -sxx - syy + szz],
    ];
    const [w, x, y, z] = principalEigenvector(n);
    const rotation: Mat3 = [
        [w * w + x * x - y * y - z * z, 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), w * w - x * x + y * y - z * z, 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), w * w - x * x - y * y + z * z],
    ];
    const turned = matVec(rotation, fc);
    const origin = [sc[0] - turned[0], sc[1] - turned[1], sc[2] - turned[2]] as Vec3;
    let error = 0;
    feet.forEach((f, k) => {
        const moved = matVec(rotation, f);
        for (let i = 0; i < 3; i++) {
            error = Math.max(error, Math.abs(moved[i] + origin[i] - standby[k][i]));
        }
    });
    return [rotation, origin, error];
}

/** The layers of a gait frame given by its feet in the body frame: the body
 * moved over standby if the stance moved as one, else feet moved. */
export function frameState(feet: Vec3[], robot: RobotConfig): PoseState {
    const standby = kf.standbyFeet(robot);
    let [rotation, origin, error] = rigidFit(feet, standby);
    if (error > RIGID_MM) {
        rotation = identity3();
        const standbyLow = Math.min(...standby.map((f) => f[2]));
        const feetLow = Math.min(...feet.map((f) => f[2]));
        origin = [0.0, 0.0, standbyLow - feetLow];
    }
    const d = getSimulatorDimensions(robot);
    const [rotX, rotY, rotZ] = rotationAngles(rotation);
    const body = {
        percent_x: origin[0] / d.middle,
        percent_y: origin[1] / d.side,
        percent_z: origin[2] / d.tibia,
        rot_x: rotX,
        rot_y: rotY,
        rot_z: rotZ,
    };
    // The offsets are taken from the body as it is kept, rounded, so the two
    // layers still put the feet exactly where the gait has them.
    const kept = pl.placement(
        pl.makeState(
            body,
            Array.from({ length: 6 }, () => [0, 0, 0]),
        ),
        robot,
    );
    return pl.makeState(
        body,
        feet.map((f, leg) => {
            const moved = matVec(kept.rotation, f);
            return [0, 1, 2].map((i) => moved[i] + kept.origin[i] - standby[leg][i]);
        }),
    );
}

/** Whether the move from frame `start` to frame `end`, with only those two
 * kept, passes every frame in between within `tolerance` of where the gait
 * has it, and stays within the joints' limits all the way. */
function fits(
    vectors: number[][],
    feet: Vec3[][],
    robot: RobotConfig,
    start: number,
    end: number,
    tolerance: number,
): boolean {
    const a = vectors[start];
    const b = vectors[end % vectors.length];
    const steps = (end - start) * LIMIT_CHECKS_PER_FRAME;
    for (let step = 1; step < steps; step++) {
        const t = step / steps;
        const played = pl.bodyFeet(pl.vectorToState(a.map((v, i) => v + (b[i] - v) * t)), robot);
        if (step % LIMIT_CHECKS_PER_FRAME === 0) {
            const index = start + step / LIMIT_CHECKS_PER_FRAME;
            const target = feet[index];
            const off = played.some((foot, leg) =>
                foot.some((c, i) => Math.abs(c - target[leg][i]) > tolerance),
            );
            if (off) {
                return false;
            }
        }
        if (kf.feetToPose(played, robot)[1].length) {
            return false;
        }
    }
    return true;
}

/** The keyframes of one cycle of a gait, for `robot`.
 *
 * None is eased into, but the first of a one-off gait (standing up), from
 * wherever the sequence was. The first one's time is the move into it from
 * the end of the cycle, so a cycle put in twice, or looped, runs on without a
 * seam. */
export function gaitKeyframes(
    motionName: string,
    robot: RobotConfig,
    tolerance = TOLERANCE_MM,
): Keyframe[] {
    const poses = robotPoses(motionName, robot);
    const feet = poses.map((pose) => kf.poseToFeet(pose, robot));
    const states = feet.map((f) => frameState(f, robot));
    const count = states.length;

    if (count === 1) {
        const state = states[0];
        return [kf.makeKeyframe(pl.bodyFeet(state, robot), kf.DEFAULT_DURATION_MS, state)];
    }

    const cyclic = !ONE_SHOT.has(motionName);
    // A cycle closes on its first frame again, as frame `count`.
    const last = cyclic ? count : count - 1;
    const vectors = states.map(pl.stateToVector);
    const kept = [0];
    while (kept[kept.length - 1] < last) {
        const from = kept[kept.length - 1];
        let end = from + 1;
        while (end < last && fits(vectors, feet, robot, from, end + 1, tolerance)) {
            end += 1;
        }
        kept.push(end);
    }

    const periodMs = 1000.0 / getSequenceFps(robot, 100);
    let firstMs: number;
    if (cyclic) {
        kept.pop();
        firstMs = (count - kept[kept.length - 1]) * periodMs;
    } else {
        firstMs = kf.DEFAULT_DURATION_MS;
    }

    return kept.map((index, position) => {
        const state = states[index];
        const durationMs = position === 0 ? firstMs : (index - kept[position - 1]) * periodMs;
        // Into a one-off from wherever the sequence was, gently.
        return kf.makeKeyframe(
            pl.bodyFeet(state, robot),
            durationMs,
            state,
            position === 0 && !cyclic,
        );
    });
}
