// The port against what the Python app computed (tools/dump_golden.py).
import { describe, expect, it } from "vitest";
import { gaitKeyframes, robotPoses } from "../src/shared/gait_keyframes";
import * as kf from "../src/shared/keyframes";
import type { Pose } from "../src/shared/path_generator";
import * as pl from "../src/shared/pose_layers";
import { poseToTicks } from "../src/shared/protocol";
import { getSimulatorDimensions, withDimensions } from "../src/shared/robot_config";
import { expectClose, golden, poseList, ROBOT_CONFIGS, ROBOT_NAMES } from "./golden";

const toPose = (angles: number[][]): Pose =>
    angles.map(([coxia, femur, tibia], id) => ({ id, name: "", coxia, femur, tibia }));

// Values the Python code rounded to a thousandth can land a step away when the
// last bit of a sum differs.
const ROUNDED = 1.01e-3;

describe.each(ROBOT_NAMES)("%s", (name) => {
    const robot = ROBOT_CONFIGS[name];
    const g = golden(name);

    it("parses the config", () => {
        const { payload: _, ...parsed } = robot;
        expectClose(parsed, g.parsed_config, 0);
        expectClose(getSimulatorDimensions(robot), g.dimensions, 0);
    });

    it("stands where Python stood it", () => {
        expectClose(kf.standbyFeet(robot), g.standby_feet, 0);
        expect(kf.groundHeight(robot)).toBe(g.ground_height);
    });

    it("holds gait poses to the joint limits", () => {
        for (const [motion, poses] of Object.entries(g.robot_poses)) {
            expectClose(robotPoses(motion, robot).map(poseList), poses, 1e-9, motion);
        }
    });

    it("solves feet to joints", () => {
        for (const c of g.feet_to_pose) {
            const [pose, bad] = kf.feetToPose(c.feet, robot, c.margin);
            expect(bad).toEqual(c.bad);
            expectClose(poseList(pose), c.pose, 2e-6);
        }
    });

    it("finds the nearest reachable foot", () => {
        for (const c of g.nearest_reachable_foot) {
            expectClose(kf.nearestReachableFoot(c.foot, c.leg, robot), c.out, 1e-7);
        }
    });

    it("poses feet, axes, scenes and ticks", () => {
        for (const c of g.poses) {
            const pose = toPose(c.pose);
            expectClose(kf.poseToFeet(pose, robot), c.feet, ROUNDED);
            expectClose(kf.jointAxes(pose, robot), c.axes, 1e-12);
            expectClose(kf.poseToScene(pose, robot), c.scene, ROUNDED);
            expect(poseToTicks(pose, robot)).toEqual(c.ticks);
        }
    });

    it("layers poses as Python did", () => {
        for (const c of g.layers) {
            const state = c.state;
            const [feet, pose, bad] = pl.solve(state, robot);
            expectClose(feet, c.body_feet, ROUNDED);
            expectClose(poseList(pose), c.pose, 1e-5);
            expect(bad).toEqual(c.bad);
            expectClose(pl.viewFeet(state, robot), c.view_feet, ROUNDED);
            expectClose(pl.scene(state, pose, robot), c.scene, ROUNDED);
            expectClose(pl.bodyFrame(state, robot), c.frame, ROUNDED);
            expectClose(pl.bodyAt(c.frame.origin, c.frame.rot, robot), c.body_at, 1e-9);
            expectClose(pl.withFootAt(state, c.leg, c.target, robot), c.with_foot_at, ROUNDED);
            expectClose(pl.withFootNear(state, c.leg, c.target, robot), c.with_foot_near, ROUNDED);
            expectClose(
                pl.withLegAngles(state, c.leg, c.angles, robot),
                c.with_leg_angles,
                ROUNDED,
            );
            expectClose(pl.withBodyNear(state, c.new_body, robot), c.with_body_near, 1.01e-4);
            expectClose(pl.fromFeet(feet, robot), c.from_feet, ROUNDED);
        }
    });

    it("plays sequences", () => {
        const keyframes = g.sequence_keyframes;
        const legacy = keyframes.map(({ state: _, ...rest }: kf.Keyframe) => rest);
        const sets: Record<string, kf.Keyframe[]> = {
            layers: keyframes,
            legacy,
            one: keyframes.slice(0, 1),
        };
        for (const c of g.sequences) {
            const frames = sets[c.keyframes];
            const s = pl.sequence(frames, robot, c.fps, c.loop, c.ease, c.speed);
            const where = `${c.keyframes} loop=${c.loop} speed=${c.speed}`;
            expectClose(s.feet, c.feet, ROUNDED, where);
            expectClose(s.states, c.states, 1.01e-4, where);
            expectClose(s.poses.map(poseList), c.poses, 1e-3, where);
            expect(s.badFrames, where).toEqual(c.bad);
            expectClose(kf.frameTimes(frames, c.fps, c.loop, c.speed), c.times, 1e-9, where);
            expectClose(kf.sequenceDurationMs(frames, c.loop, c.speed), c.duration, 1e-9);
        }
        expectClose(JSON.parse(kf.dump(keyframes, robot)), g.dump, 0);
    });

    it("works the gaits out as keyframes", () => {
        for (const [motion, expected] of Object.entries(g.gait_keyframes)) {
            const actual = gaitKeyframes(motion, robot);
            expect(actual.length, motion).toBe((expected as unknown[]).length);
            expectClose(actual, expected, 2.01e-3, motion);
        }
    });

    it("resizes the body", () => {
        const w = g.with_dimensions;
        const resized = withDimensions(robot, w.dimensions);
        expectClose(resized.config, w.config, 1e-12);
        expectClose(kf.standbyFeet(resized), w.standby_feet, ROUNDED);
        const state = pl.standbyState();
        expectClose(pl.scene(state, pl.solve(state, resized)[1], resized), w.scene, ROUNDED);
    });
});
