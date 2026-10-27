// The gait generator, ported from path_tool: every motion the UI offers
// produces well-formed poses, the IK inverts the posture builder it is paired
// with, and the robots really do get different paths.
import { describe, expect, it } from "vitest";
import { MOTION_TYPES } from "../src/shared/motions";
import { LEG_NAMES } from "../src/shared/naming";
import {
    generatePoses,
    genPosture,
    inverseKinematics,
    pathRotateZ,
    semicircleGenerator,
} from "../src/shared/path_generator";
import { getLegSigns } from "../src/shared/robot_config";
import { pyRound } from "../src/shared/util";
import { expectClose, golden, poseList, ROBOT_CONFIGS, ROBOT_NAMES } from "./golden";

const UI_MOTIONS = MOTION_TYPES.map((m) => m.value);
// Every gait is baked at 28 frames; only standby is a single held posture.
const GAIT_STEPS = 28;
const robots = Object.entries(ROBOT_CONFIGS);

describe.each(ROBOT_NAMES)("%s against Python", (name) => {
    it("generates every gait as the Python path tool did", () => {
        const expected = golden(name).generate_poses as Record<string, number[][][]>;
        for (const [motion, poses] of Object.entries(expected)) {
            expectClose(
                generatePoses(motion, ROBOT_CONFIGS[name]).map(poseList),
                poses,
                1e-9,
                motion,
            );
        }
    });
});

describe("path generator", () => {
    it("generates well-formed poses for every motion the UI offers", () => {
        for (const [name, robot] of robots) {
            for (const motion of UI_MOTIONS) {
                const poses = generatePoses(motion, robot);
                expect(poses.length, `${name}/${motion}`).toBe(
                    motion === "standby" ? 1 : GAIT_STEPS,
                );
                poses.forEach((pose, i) => {
                    expect(pose.length).toBe(6);
                    pose.forEach((leg, id) => {
                        expect(leg.id).toBe(id);
                        expect(leg.name).toBe(LEG_NAMES[id]);
                        for (const j of [leg.coxia, leg.femur, leg.tibia]) {
                            expect(Number.isFinite(j), `${name}/${motion} frame ${i}`).toBe(true);
                        }
                    });
                });
            }
        }
    });

    it("falls back to standby for an unknown motion", () => {
        for (const [, robot] of robots) {
            expect(generatePoses("no-such-motion", robot)).toEqual(generatePoses("standby", robot));
        }
    });

    it("gives each robot its own path", () => {
        const firsts = robots.map(([, robot]) => generatePoses("walk_0", robot)[0][0].femur);
        expect(new Set(firsts).size).toBe(firsts.length);
    });

    it("inverts the standby posture", () => {
        for (const [, robot] of robots) {
            const [j2, j3] = robot.gait.standby_posture;
            const angles = inverseKinematics(genPosture(j2, j3, robot.config), robot.config);
            getLegSigns(robot).forEach((sign, leg) => {
                const expected = sign === 1 ? [90, j2, j3] : [90, 180 - j2, 180 - j3];
                expectClose(angles[leg], expected, 1e-9);
            });
        }
    });

    it("does not round trip laydown", () => {
        for (const [, robot] of robots) {
            const [j2, j3] = robot.gait.laydown_posture;
            const angles = inverseKinematics(genPosture(j2, j3, robot.config), robot.config);
            expect(Math.abs(angles[1][1] - j2)).toBeLessThan(1e-9);
            expect(Math.abs(angles[1][2] - j3)).toBeGreaterThan(1e-6);
        }
    });

    it("stands level, laydown above standby", () => {
        for (const [, robot] of robots) {
            for (const posture of [robot.gait.standby_posture, robot.gait.laydown_posture]) {
                const zs = genPosture(posture[0], posture[1], robot.config).map((f) => f[2]);
                expect(Math.max(...zs) - Math.min(...zs)).toBeLessThan(1e-9);
            }
            const standby = genPosture(...robot.gait.standby_posture, robot.config);
            const laydown = genPosture(...robot.gait.laydown_posture, robot.config);
            expect(laydown[0][2]).toBeGreaterThan(standby[0][2]);
        }
    });

    it("lifts the foot in a semicircle without sideways drift", () => {
        const path = semicircleGenerator(30, GAIT_STEPS);
        expect(path.length).toBe(GAIT_STEPS);
        expect(path.every((p) => Math.abs(p[0]) < 1e-12)).toBe(true);
        const zs = path.map((p) => p[2]);
        const ys = path.map((p) => p[1]);
        expect(Math.min(...zs)).toBeCloseTo(0);
        expect(Math.max(...zs)).toBeCloseTo(30);
        expect(Math.min(...ys)).toBeCloseTo(-30);
        expect(Math.max(...ys)).toBeCloseTo(30);
        expect(zs.filter((z) => z === 0).length).toBe(GAIT_STEPS / 2);
    });

    it("retraces the stroke backwards", () => {
        const forward = semicircleGenerator(30, GAIT_STEPS);
        const reverse = semicircleGenerator(30, GAIT_STEPS, true);
        for (const axis of [1, 2]) {
            const a = forward.map((p) => p[axis]).sort((x, y) => x - y);
            const b = reverse.map((p) => p[axis]).sort((x, y) => x - y);
            expectClose(b, a, 1e-9);
        }
    });

    it("needs a step count it can quarter", () => {
        for (const steps of [27, 26, 30]) {
            expect(() => semicircleGenerator(30, steps)).toThrow();
        }
    });

    it("turns the stroke in the ground plane", () => {
        const path = semicircleGenerator(30, GAIT_STEPS);
        const turned = pathRotateZ(path, 90);
        path.forEach((p, i) => {
            expect(Math.hypot(turned[i][0], turned[i][1])).toBeCloseTo(Math.hypot(p[0], p[1]), 9);
            expect(turned[i][2]).toBeCloseTo(p[2], 9);
        });
        expectClose(pathRotateZ(path, 360), path, 1e-9);
    });

    it("swaps legs, rather than negating one, for opposite walks", () => {
        const forward = generatePoses("walk_0", ROBOT_CONFIGS.mochi);
        const backward = generatePoses("walk_180", ROBOT_CONFIGS.mochi);
        const sweep = (poses: typeof forward, leg: number, sign = 1) =>
            poses.map((p) => pyRound(sign * p[leg].coxia, 6)).sort((a, b) => a - b);
        expect(sweep(forward, 0)).toEqual(sweep(backward, 2, -1));
        expect(sweep(forward, 0)).not.toEqual(sweep(backward, 0, -1));
        const f = forward.map((p) => p[0].coxia);
        const b = backward.map((p) => p[0].coxia);
        expect(Math.min(...f)).toBeCloseTo(Math.min(...b));
        expect(Math.max(...f)).toBeCloseTo(Math.max(...b));
    });
});
