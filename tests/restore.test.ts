// Opening the workspace as it was left: what the Python version of the app
// kept opens here too, and what cannot be used is dropped.
import { describe, expect, it } from "vitest";
import {
    savedDimensions,
    savedKeyframes,
    savedPose,
    savedValues,
} from "../src/renderer/src/state/restore";
import * as kf from "../src/shared/keyframes";
import * as pl from "../src/shared/pose_layers";
import { ROBOT_CONFIGS } from "./golden";

const NOUGAT = ROBOT_CONFIGS.nougat;

describe("restoring the workspace", () => {
    it("keeps usable values and drops the rest", () => {
        const state = pl.makeState(
            { rot_x: 5 },
            Array.from({ length: 6 }, () => [0, 0, 0]),
        );
        const pose = { robot: "nougat", state, feet: pl.bodyFeet(state, NOUGAT), seq: 3 };
        const keyframes = {
            robot: "nougat",
            keyframes: [kf.makeKeyframe(kf.standbyFeet(NOUGAT), 400)],
        };
        const values = savedValues({
            pose,
            keyframes,
            selected: 0,
            body_mode: "rotate",
            gait_source: "sideways",
            gait_name: "x".repeat(41),
            duration: 5,
            ease: "linear",
            speed: 80,
            loop: ["loop"],
            robot_ip: "10.0.0.2",
            max_step: "fast",
            drive_speed: 70,
        });
        expect(values.pose?.state).toEqual(state);
        expect(values.keyframes?.keyframes.length).toBe(1);
        expect(values.keyframes?.keyframes[0].number).toBe(1);
        expect(values).toMatchObject({
            selected: 0,
            body_mode: "rotate",
            ease: "linear",
            speed: 80,
            loop: ["loop"],
            robot_ip: "10.0.0.2",
            drive_speed: 70,
        });
        for (const dropped of ["gait_source", "gait_name", "duration", "max_step"]) {
            expect(dropped in values).toBe(false);
        }
    });

    it("refuses a pose or keyframes that are not", () => {
        expect(
            savedPose({ robot: "nougat", state: { body: {}, offsets: [] }, feet: [] }),
        ).toBeNull();
        expect(savedPose(null)).toBeNull();
        expect(savedKeyframes({ robot: "nougat", keyframes: [{ feet: [[0, 0, 0]] }] })).toBeNull();
        expect(savedKeyframes({ keyframes: [] })).toBeNull();
    });

    it("gives back the dimensions left on this robot only", () => {
        const values = { front: 50, side: 80, middle: 60, coxia: 40, femur: 55, tibia: 90 };
        const saved = { dimensions: { robot: "nougat", values } };
        expect(savedDimensions(saved, "nougat")).toEqual(values);
        expect(savedDimensions(saved, "mochi")).toBeNull();
        expect(
            savedDimensions(
                { dimensions: { robot: "nougat", values: { ...values, front: null } } },
                "nougat",
            ),
        ).toBeNull();
    });
});
