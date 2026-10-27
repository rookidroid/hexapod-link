// Keyframes: solving joints from feet and back, and timing. The workspace
// places feet in the path tool's body frame and draws them with the linkage
// model, so first those two must agree; the rest covers what a sequence turns
// into on its way to the robot.
import { describe, expect, it } from "vitest";
import * as kf from "../src/shared/keyframes";
import {
    KeyframeFileError,
    LIMIT_MARGIN_DEG,
    makeKeyframe,
    standbyFeet,
} from "../src/shared/keyframes";
import { LEG_NAMES } from "../src/shared/naming";
import { generatePoses, type Pose } from "../src/shared/path_generator";
import { poseToTicks } from "../src/shared/protocol";
import {
    DEFAULT_CONFIG,
    getJointLimits,
    getSequenceFps,
    type RobotConfig,
} from "../src/shared/robot_config";
import type { Vec3 } from "../src/shared/util";
import { allClose, numbers, ROBOT_CONFIGS, ROBOTS } from "./golden";

const uniformPose = (coxia: number, femur: number, tibia: number): Pose =>
    LEG_NAMES.map((name, id) => ({ id, name, coxia, femur, tibia }));

const lifted = (feet: Vec3[], leg: number, dz: number): Vec3[] =>
    feet.map((f, i) => (i === leg ? [f[0], f[1], f[2] + dz] : [...f]) as Vec3);

const plus = (a: readonly number[], b: readonly number[]): Vec3 => [
    a[0] + b[0],
    a[1] + b[1],
    a[2] + b[2],
];
const norm = (v: readonly number[]) => Math.hypot(...v);

function solvedLeg(foot: readonly number[], leg: number, robot: RobotConfig) {
    const feet = standbyFeet(robot);
    feet[leg] = [...foot] as Vec3;
    const [pose, bad] = kf.feetToPose(feet, robot);
    return [pose[leg], bad.includes(leg)] as const;
}

const reachOf = (r: RobotConfig) =>
    r.config.legJoint1ToJoint2 + r.config.legJoint2ToJoint3 + r.config.legJoint3ToTip;

// Every mix of right or left, forward or back, and up or down.
const DRAGS: Vec3[] = [];
for (let i = 0; i < 3; i++)
    for (let j = 0; j < 3; j++)
        for (let k = 0; k < 3; k++)
            if (!(i === 1 && j === 1 && k === 1)) DRAGS.push([i - 1, j - 1, k - 1]);

const JOINTS = ["coxia", "femur", "tibia"] as const;

function linspace(a: number, b: number, n: number): number[] {
    return Array.from({ length: n }, (_, i) => a + ((b - a) * i) / (n - 1));
}

describe.each(ROBOTS)("%s", (_name, robot) => {
    it("round trips standby and moved feet through the linkage model", () => {
        const feet = standbyFeet(robot);
        const [pose, bad] = kf.feetToPose(feet, robot);
        expect(bad).toEqual([]);
        allClose(kf.poseToScene(pose, robot).feet, feet, 1e-2);

        const moved = feet.map((f) => [...f] as Vec3);
        moved[0] = plus(moved[0], [10, 15, 20]);
        moved[4] = plus(moved[4], [-12, 8, 5]);
        const [p2, b2] = kf.feetToPose(moved, robot);
        expect(b2).toEqual([]);
        allClose(kf.poseToScene(p2, robot).feet, moved, 1e-2);

        const third = standbyFeet(robot);
        third[2] = plus(third[2], [8, -6, 25]);
        const [p3, b3] = kf.feetToPose(third, robot);
        expect(b3).toEqual([]);
        allClose(kf.poseToFeet(p3, robot), third, 1e-2);
    });

    it("keeps a leg pattern through feet, and standby solves to standby", () => {
        const poses = uniformPose(5, 20, -10);
        const [pose, bad] = kf.feetToPose(kf.poseToFeet(poses, robot), robot);
        expect(bad).toEqual([]);
        pose.forEach((leg, id) => {
            for (const j of JOINTS) expect(Math.abs(leg[j] - poses[id][j])).toBeLessThan(1e-2);
        });
        const [standby] = kf.feetToPose(standbyFeet(robot), robot);
        const expected = generatePoses("standby", robot)[0];
        standby.forEach((leg, id) => {
            for (const j of JOINTS) expect(Math.abs(leg[j] - expected[id][j])).toBeLessThan(1e-2);
        });
    });

    it("finds a foot within reach to be its own nearest", () => {
        const feet = standbyFeet(robot);
        for (let leg = 0; leg < 6; leg++) {
            for (const moved of [feet[leg], plus(feet[leg], [8, -6, 25])]) {
                expect(kf.nearestReachableFoot(moved, leg, robot)).toEqual(moved);
            }
        }
    });

    it("holds a foot out of reach where its leg can put it", () => {
        const feet = standbyFeet(robot);
        const limits = getJointLimits(robot);
        let held = 0;
        for (let leg = 0; leg < 6; leg++) {
            for (const drag of DRAGS) {
                for (const far of [0.5, 1.5, 6.0]) {
                    const target = plus(
                        feet[leg],
                        drag.map((d) => d * far * reachOf(robot)),
                    );
                    const foot = kf.nearestReachableFoot(target, leg, robot)!;
                    const [joints, bad] = solvedLeg(foot, leg, robot);
                    expect(bad).toBe(false);
                    if (foot.some((c, i) => c !== target[i])) {
                        held += 1;
                        for (const j of JOINTS) {
                            expect(Math.abs(joints[j])).toBeLessThanOrEqual(
                                limits[j] - LIMIT_MARGIN_DEG + 1e-3,
                            );
                        }
                        const [, targetBad] = solvedLeg(target, leg, robot);
                        expect(
                            targetBad ||
                                JOINTS.some(
                                    (j) =>
                                        Math.abs(joints[j]) > limits[j] - LIMIT_MARGIN_DEG - 1e-3,
                                ),
                        ).toBe(true);
                    }
                }
            }
        }
        expect(held).toBeGreaterThan(100);
    });

    it("holds a foot as near as the linkage model can put one", () => {
        const limits = getJointLimits(robot);
        const most = (j: (typeof JOINTS)[number]) => limits[j] - LIMIT_MARGIN_DEG;
        const grid: [Vec3[], number[]][] = [];
        for (const coxia of linspace(-most("coxia"), most("coxia"), 7))
            for (const femur of linspace(-most("femur"), most("femur"), 9))
                for (const tibia of linspace(-most("tibia"), most("tibia"), 9)) {
                    const feet = kf.poseToFeet(uniformPose(coxia, femur, tibia), robot);
                    grid.push([feet, kf.feetToPose(feet, robot)[1]]);
                }
        const feet = standbyFeet(robot);
        for (let leg = 0; leg < 6; leg++) {
            const reachable = grid.filter(([, bad]) => !bad.includes(leg)).map(([f]) => f[leg]);
            for (const drag of DRAGS) {
                const target = plus(
                    feet[leg],
                    drag.map((d) => d * 1.5 * reachOf(robot)),
                );
                const foot = kf.nearestReachableFoot(target, leg, robot)!;
                const nearest = Math.min(
                    ...reachable.map((r) => norm(r.map((c, i) => c - target[i]))),
                );
                expect(norm(foot.map((c, i) => c - target[i]))).toBeLessThanOrEqual(nearest + 1e-2);
            }
        }
    });

    it("slides a foot dragged out of reach without a jump", () => {
        const step = 2.0;
        const feet = standbyFeet(robot);
        for (let leg = 0; leg < 6; leg++) {
            const h = Math.hypot(feet[leg][0], feet[leg][1]);
            const outward: Vec3 = [feet[leg][0] / h, feet[leg][1] / h, 0];
            const up: Vec3 = [0, 0, 1];
            const diag = plus(outward, up).map((c) => c / Math.SQRT2);
            for (const direction of [outward, up, [0, 0, -1], diag]) {
                let last: readonly number[] = feet[leg];
                for (let dragged = step; dragged < 1.5 * reachOf(robot); dragged += step) {
                    const target = feet[leg].map((c, i) => c + dragged * direction[i]);
                    const foot = kf.nearestReachableFoot(target, leg, robot)!;
                    expect(norm(foot.map((c, i) => c - last[i]))).toBeLessThan(2 * step);
                    last = foot;
                }
            }
        }
    });

    it("stores no negative zero", () => {
        const hasNegativeZero = (v: unknown) => numbers(v).some((n) => Object.is(n, -0));
        expect(hasNegativeZero([[-0, 1, 2]])).toBe(true);
        expect(hasNegativeZero(standbyFeet(robot))).toBe(false);
        expect(hasNegativeZero(makeKeyframe(Array(6).fill([-0, -0, -0])).feet)).toBe(false);
        const [pose] = kf.feetToPose(standbyFeet(robot), robot);
        expect(hasNegativeZero(kf.poseToScene(pose, robot).legs[4])).toBe(false);
    });
});

describe("keyframes", () => {
    it("reports an unreachable foot and one past a joint limit", () => {
        const nougat = ROBOT_CONFIGS.nougat;
        const feet = standbyFeet(nougat);
        feet[2] = feet[2].map((c) => c * 10) as Vec3;
        expect(kf.feetToPose(feet, nougat)[1]).toEqual([2]);

        const mochi = ROBOT_CONFIGS.mochi;
        const m = standbyFeet(mochi);
        const [x, y, z] = m[1];
        const r = Math.hypot(x, y);
        const a = (70 * Math.PI) / 180;
        m[1] = [r * Math.cos(a), r * Math.sin(a), z];
        expect(kf.feetToPose(m, mochi)[1]).toEqual([1]);
    });

    it("reports a joint near its limit with a margin", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const limit = getJointLimits(robot).tibia;
        const feet = kf.poseToFeet(uniformPose(0, 20, limit - 0.2), robot);
        expect(kf.feetToPose(feet, robot)[1]).toEqual([]);
        expect(kf.feetToPose(feet, robot, 0.1)[1]).toEqual([]);
        expect(kf.feetToPose(feet, robot, 0.5)[1]).toEqual([0, 1, 2, 3, 4, 5]);
    });

    it("marks lifted feet off the ground in the scene", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const [pose] = kf.feetToPose(lifted(standbyFeet(robot), 3, 30), robot);
        const scene = kf.poseToScene(pose, robot);
        expect(scene.support.length).toBe(5);
        expect(scene.support.every((p) => p[2] === kf.groundHeight(robot))).toBe(true);
        expect(scene.legs.length).toBe(6);
        expect(scene.legs.every((leg) => leg.length === 4)).toBe(true);
    });

    it("interpolates with the right frame count and end points", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const start = standbyFeet(robot);
        const keyframes = [makeKeyframe(start, 500), makeKeyframe(lifted(start, 0, 40), 500)];
        const frames = kf.interpolateFeet(keyframes, 20);
        expect(frames.length).toBe(11);
        allClose(frames[0], keyframes[0].feet, 1e-9);
        allClose(frames.at(-1), keyframes[1].feet, 1e-9);
        const lift = frames.map((f) => f[0][2] - start[0][2]);
        expect(lift[1] - lift[0]).toBeLessThan(lift[6] - lift[5]);
    });

    it("closes the loop without repeating the first frame", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const start = standbyFeet(robot);
        const keyframes = [makeKeyframe(start, 250), makeKeyframe(lifted(start, 0, 40), 500)];
        const frames = kf.interpolateFeet(keyframes, 20, true, false);
        expect(frames.length).toBe(1 + 10 + 4);
        allClose(frames[10], keyframes[1].feet, 1e-9);
        expect(Math.abs(frames.at(-1)![0][2] - (start[0][2] + 40 / 5))).toBeLessThan(1e-2);
    });

    it("plays a single keyframe as one frame", () => {
        const keyframes = [makeKeyframe(standbyFeet(ROBOT_CONFIGS.mochi))];
        expect(kf.interpolateFeet(keyframes, 50, true).length).toBe(1);
        expect(kf.interpolateFeet([], 50)).toEqual([]);
    });

    it("reports frames that pass out of reach", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const start = standbyFeet(robot);
        const solved = (frames: kf.Keyframe[], fps: number) =>
            kf.solveFrames(kf.interpolateFeet(frames, fps), robot);
        const [poses, bad] = solved([makeKeyframe(start)], 50);
        expect(poses.length).toBe(1);
        expect(bad).toEqual([]);
        const far = start.map((f) => [...f] as Vec3);
        far[5] = far[5].map((c) => c * 10) as Vec3;
        const [, bad2] = solved([makeKeyframe(start), makeKeyframe(far, 100)], 50);
        expect(bad2.at(-1)).toBe(5);
    });

    it("plays poses on the robot link", () => {
        const robot = ROBOT_CONFIGS.macaroon;
        const start = standbyFeet(robot);
        const keyframes = [makeKeyframe(start), makeKeyframe(lifted(start, 1, 20), 300)];
        const fps = getSequenceFps(robot);
        const [poses, bad] = kf.solveFrames(kf.interpolateFeet(keyframes, fps), robot);
        expect(bad).toEqual([]);
        expect(poses.length).toBe(1 + Math.round(0.3 * fps));
        expect(poses.every((p) => poseToTicks(p, robot).length === 18)).toBe(true);
    });

    it("clamps and sums durations", () => {
        const feet = standbyFeet(DEFAULT_CONFIG);
        expect(makeKeyframe(feet, 1).duration_ms).toBe(kf.MIN_DURATION_MS);
        expect(makeKeyframe(feet, 1e9).duration_ms).toBe(kf.MAX_DURATION_MS);
        expect(makeKeyframe(feet, null).duration_ms).toBe(500);
        const keyframes = [
            makeKeyframe(feet, 100),
            makeKeyframe(feet, 200),
            makeKeyframe(feet, 300),
        ];
        expect(kf.sequenceDurationMs(keyframes)).toBe(500);
        expect(kf.sequenceDurationMs(keyframes, true)).toBe(600);
        expect(kf.sequenceDurationMs([])).toBe(0);
    });

    it("round trips files, numbers and easing", () => {
        const robot = ROBOT_CONFIGS.mochi;
        const start = standbyFeet(robot);
        const keyframes = [makeKeyframe(start, 400), makeKeyframe(lifted(start, 2, 25), 700)];
        expect(kf.load(kf.dump(keyframes, robot), robot)).toEqual(kf.numbered(keyframes));
        const numberedFrames = [
            makeKeyframe(start, 400, null, true, 7),
            makeKeyframe(start, 700, null, true, 2),
        ];
        expect(kf.load(kf.dump(numberedFrames, robot), robot).map(kf.numberOf)).toEqual([7, 2]);

        const eased = [makeKeyframe(start, 300), makeKeyframe(start, 24, null, false)];
        const loaded = kf.load(kf.dump(eased, robot), robot);
        expect("ease" in loaded[0]).toBe(false);
        expect(loaded[1].ease).toBe(false);
        const doc = JSON.parse(kf.dump(eased, robot));
        doc.keyframes[1].ease = "no";
        expect(() => kf.load(JSON.stringify(doc), robot)).toThrow(KeyframeFileError);
    });

    it("refuses a bad number, another robot's file, and malformed files", () => {
        const robot = ROBOT_CONFIGS.mochi;
        const doc = JSON.parse(kf.dump([makeKeyframe(standbyFeet(robot))], robot));
        doc.keyframes[0].number = 0;
        expect(() => kf.load(JSON.stringify(doc), robot)).toThrow(/number/);
        const text = kf.dump([makeKeyframe(standbyFeet(robot))], robot);
        expect(() => kf.load(text, ROBOT_CONFIGS.nougat)).toThrow(/mochi/);
        const base = { format: "hexapod-link-keyframes", version: 1, robot: "nougat" };
        for (const bad of [
            "not json",
            JSON.stringify([1, 2, 3]),
            JSON.stringify({ format: "something-else" }),
            JSON.stringify({ ...base, version: 99 }),
            JSON.stringify(base),
            JSON.stringify({
                ...base,
                keyframes: [{ feet: Array(5).fill([0, 0, 0]), duration_ms: 100 }],
            }),
            JSON.stringify({ ...base, keyframes: [{ feet: Array(6).fill([0, 0, 0]) }] }),
        ]) {
            expect(() => kf.load(bad, ROBOT_CONFIGS.nougat)).toThrow(KeyframeFileError);
        }
    });

    it("numbers keyframes and keeps their numbers", () => {
        const feet = standbyFeet(ROBOT_CONFIGS.mochi);
        const frames = [
            makeKeyframe(feet, 500, null, true, 3),
            makeKeyframe(feet),
            makeKeyframe(feet, 500, null, true, 1),
            makeKeyframe(feet, 500, null, true, 3),
        ];
        expect(kf.numbered(frames).map(kf.numberOf)).toEqual([3, 4, 1, 5]);

        const three = kf.numbered([makeKeyframe(feet), makeKeyframe(feet), makeKeyframe(feet)]);
        const moved = [three[1], three[0]];
        expect(kf.numbered(moved).map((f) => kf.label(f))).toEqual(["#2", "#1"]);
        expect(kf.renumbered(moved).map((f) => kf.label(f))).toEqual(["#1", "#2"]);
        expect(kf.unnumbered([makeKeyframe(feet, 500, null, true, 4)])).toEqual([
            makeKeyframe(feet),
        ]);

        const frame = makeKeyframe(feet, 300, null, true, 5);
        expect(kf.numberOf(kf.withEase(frame, false))).toBe(5);
        expect(kf.eases(kf.withEase(frame, false))).toBe(false);
        expect(kf.numberOf(kf.remade(frame, feet))).toBe(5);
    });

    it("moves into a keyframe without easing when asked", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const start = standbyFeet(robot);
        const end = start.map((f) => [f[0], f[1] + 20, f[2]] as Vec3);
        const ySteps = (frames: kf.Keyframe[]) => {
            const ys = kf.interpolateFeet(frames, 20, false, true).map((f) => f[0][1]);
            return ys.slice(1).map((y, i) => y - ys[i]);
        };
        for (const s of ySteps([makeKeyframe(start), makeKeyframe(end, 500, null, false)])) {
            expect(s).toBeCloseTo(2.0, 6);
        }
        const gentle = ySteps([makeKeyframe(start), makeKeyframe(end, 500)]);
        expect(gentle[0]).toBeLessThan(gentle[5]);
    });

    it("scales the whole sequence by speed, keeping short moves' time", () => {
        const feet = standbyFeet(ROBOT_CONFIGS.nougat);
        const keyframes = [
            makeKeyframe(feet, 100),
            makeKeyframe(feet, 400),
            makeKeyframe(feet, 600),
        ];
        expect(kf.sequenceDurationMs(keyframes, false, 2.0)).toBe(500);
        expect(kf.sequenceDurationMs(keyframes, true, 0.5)).toBe(2200);
        expect(kf.interpolateFeet(keyframes, 20, false, true, 2.0).length).toBe(1 + 4 + 6);
        expect(kf.interpolateFeet(keyframes, 20).length).toBe(1 + 8 + 12);

        const gait = Array.from({ length: 30 }, () => makeKeyframe(feet, 12, null, false));
        expect(kf.interpolateFeet(gait, 25, true).length).toBe(Math.round(30 * 0.012 * 25));
        expect(kf.interpolateFeet(gait, 25, true, true, 0.5).length).toBe(
            Math.round(30 * 0.024 * 25),
        );
    });

    it.each([false, true])(
        "knows where each frame falls in the keyframes' time (loop %s)",
        (loop) => {
            const feet = standbyFeet(ROBOT_CONFIGS.nougat);
            const keyframes = [
                makeKeyframe(feet, 100),
                makeKeyframe(feet, 400),
                makeKeyframe(feet, 200),
            ];
            for (const speed of [1.0, 2.0]) {
                const times = kf.frameTimes(keyframes, 20, loop, speed);
                expect(times.length).toBe(
                    kf.interpolateFeet(keyframes, 20, loop, true, speed).length,
                );
                expect(times[0]).toEqual([0, 0, 0]);
                expect(
                    times.some(([s, e, ms]) => s === 0 && e === 1 && Math.abs(ms - 200) < 1e-6),
                ).toBe(true);
                if (!loop) {
                    const [s, e, ms] = times.at(-1)!;
                    expect([s, e]).toEqual([1, 2]);
                    expect(ms).toBeCloseTo(200);
                }
            }
            if (loop) {
                const [s, e, ms] = kf.frameTimes(keyframes, 20, true).at(-1)!;
                expect([s, e]).toEqual([2, 0]);
                expect(ms).toBeCloseTo(50);
            }
            expect(kf.keyframeTimesMs(keyframes)).toEqual([0, 400, 600]);
        },
    );
});
