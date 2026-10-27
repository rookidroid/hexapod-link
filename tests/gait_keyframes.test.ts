// A gait put into a sequence is keyframes like any other, and has to play as
// the gait: every foot within tolerance of its own path, at the robot's own
// timing, with no seam, every joint within its limits whatever the speed, and
// written in the layers the editor shows.
import { describe, expect, it } from "vitest";
import { gaitKeyframes, ONE_SHOT, robotPoses, TOLERANCE_MM } from "../src/shared/gait_keyframes";
import * as kf from "../src/shared/keyframes";
import { GAIT_MENU, MOTION_TYPES } from "../src/shared/motions";
import { generatePoses } from "../src/shared/path_generator";
import * as pl from "../src/shared/pose_layers";
import { getSequenceFps, type RobotConfig } from "../src/shared/robot_config";
import type { Vec3 } from "../src/shared/util";
import { allClose, ROBOT_CONFIGS, ROBOTS } from "./golden";

const GAITS = MOTION_TYPES.map((m) => m.value);
const SWAYS = ["rotate_x", "rotate_y", "rotate_z", "twist"];

const gaitFeet = (motion: string, robot: RobotConfig) =>
    robotPoses(motion, robot).map((pose) => kf.poseToFeet(pose, robot));

const maxOff = (a: Vec3[][], b: Vec3[][]) =>
    Math.max(
        ...a.flatMap((frame, i) =>
            frame.flatMap((f, j) => f.map((c, k) => Math.abs(c - b[i][j][k]))),
        ),
    );

describe.each(ROBOTS)("%s", (_name, robot) => {
    it.each(GAITS)("plays %s on its own path at its own timing, within limits", (motion) => {
        const truth = gaitFeet(motion, robot);
        const keyframes = gaitKeyframes(motion, robot);
        const fps = getSequenceFps(robot, 100);
        const cyclic = !ONE_SHOT.has(motion);
        const { feet } = pl.sequence(keyframes, robot, fps, cyclic, true);
        expect(feet.length).toBe(truth.length);
        expect(maxOff(feet, truth)).toBeLessThanOrEqual(TOLERANCE_MM + 1e-6);
        if (cyclic && truth.length > 1) {
            expect(
                Math.abs(kf.sequenceDurationMs(keyframes, true) - (truth.length * 1000) / fps),
            ).toBeLessThanOrEqual(keyframes.length);
        }
        for (const [f, speed] of [
            [25, 1.0],
            [fps, 1.0],
            [fps, 0.33],
            [fps, 0.75],
            [fps, 2.0],
        ]) {
            expect(
                pl.sequence(keyframes, robot, f, cyclic, true, speed).badFrames,
                `${f} ${speed}`,
            ).toEqual([]);
        }
    });

    it("needs only some of a walk cycle's frames", () => {
        const count = gaitKeyframes("walk_0", robot).length;
        expect(count).toBeGreaterThan(4);
        expect(count).toBeLessThan(generatePoses("walk_0", robot).length);
    });

    it.each(SWAYS)("writes %s as the body moving over planted feet", (motion) => {
        const keyframes = gaitKeyframes(motion, robot);
        expect(
            keyframes.some((f) =>
                (["rot_x", "rot_y", "rot_z"] as const).some((k) => Math.abs(f.state!.body[k]) > 1),
            ),
        ).toBe(true);
        for (const frame of keyframes) {
            allClose(frame.state!.offsets, Array(6).fill([0, 0, 0]), 1.0);
            allClose(
                pl.viewFeet(frame.state!, robot).map((f) => f[2]),
                Array(6).fill(0),
                1.0,
            );
            allClose(pl.bodyFeet(frame.state!, robot), frame.feet, 0.01);
        }
    });

    it.each(["rotate_x", "rotate_y", "rotate_z", "twist", "climb_forward", "walk_0"])(
        "draws %s standing on the floor",
        (motion) => {
            const { states, poses } = pl.sequence(gaitKeyframes(motion, robot), robot, 25, true);
            states!.forEach((state, i) => {
                const zs = pl.scene(state, poses[i], robot).feet.map((f) => f[2]);
                expect(Math.min(...zs)).toBeGreaterThanOrEqual(-kf.GROUND_TOLERANCE);
                expect(zs.filter((z) => z <= kf.GROUND_TOLERANCE).length).toBeGreaterThanOrEqual(3);
            });
        },
    );
});

describe("gait keyframes", () => {
    it.each(["walk_0", "climb_forward", "fast_forward"])(
        "keeps the lowest foot of %s on the floor",
        (motion) => {
            const robot = ROBOT_CONFIGS.nougat;
            for (const frame of gaitKeyframes(motion, robot)) {
                const low = Math.min(...pl.viewFeet(frame.state!, robot).map((f) => f[2]));
                expect(Math.abs(low)).toBeLessThan(0.05);
            }
        },
    );

    it("makes plain keyframes that do not ease", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const keyframes = gaitKeyframes("turn_left", robot);
        expect(
            keyframes.every((f) => Object.keys(f).sort().join() === "duration_ms,ease,feet,state"),
        ).toBe(true);
        expect(keyframes.some(kf.eases)).toBe(false);
        const standup = gaitKeyframes("standup", robot);
        expect(kf.eases(standup[0])).toBe(true);
        expect(standup.slice(1).some(kf.eases)).toBe(false);
    });

    it("runs two cycles in a row without a seam", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const cycle = gaitKeyframes("walk_0", robot);
        const { feet } = pl.sequence([...cycle, ...cycle], robot, getSequenceFps(robot, 100), true);
        const truth = gaitFeet("walk_0", robot);
        expect(maxOff(feet, [...truth, ...truth])).toBeLessThanOrEqual(TOLERANCE_MM + 1e-6);
    });

    it("still catches a move of one's own past a limit", () => {
        const robot = ROBOT_CONFIGS.mochi;
        const walk = gaitKeyframes("walk_0", robot);
        const stretched = kf.standbyFeet(robot).map((f) => [f[0], f[1], f[2] - 200]);
        expect(
            pl.sequence([...walk, kf.makeKeyframe(stretched, 200)], robot, 50).badFrames.length,
        ).toBeGreaterThan(0);
    });

    it("offers every gait once in the menu", () => {
        const offered = GAIT_MENU.flatMap(([, motions]) => motions);
        expect([...offered].sort()).toEqual([...GAITS].sort());
    });
});
