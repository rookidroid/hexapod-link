import { describe, it } from "vitest";
import { generatePoses } from "../src/shared/path_generator";
import { expectClose, golden, poseList, ROBOT_CONFIGS, ROBOT_NAMES } from "./golden";

describe.each(ROBOT_NAMES)("%s", (name) => {
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
