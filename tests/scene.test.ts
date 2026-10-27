// The scene handed to the 3D view: each leg's points are the linkage's own,
// the support polygon is drawn through the feet given, in order, and the
// whole thing survives JSON.
import { describe, expect, it } from "vitest";
import { poseToScene } from "../src/shared/keyframes";
import { VirtualHexapod } from "../src/shared/models";
import { generatePoses } from "../src/shared/path_generator";
import { getSimulatorDimensions, type RobotConfig } from "../src/shared/robot_config";
import { hexapodToScene, transformScene } from "../src/shared/scene";
import { VIEWER_COLORS } from "../src/shared/style";
import { matVec, type Vec3 } from "../src/shared/util";
import { allClose, numbers, ROBOT_CONFIGS, ROBOT_NAMES } from "./golden";

function posed(robot: RobotConfig, motion = "walk_0", frame = 3) {
    const hexapod = new VirtualHexapod(getSimulatorDimensions(robot));
    generatePoses(motion, robot)[frame].forEach((j, id) => {
        hexapod.legs[id].changePose(j.coxia, j.femur, j.tibia);
    });
    return hexapod;
}

describe("scene", () => {
    it.each(ROBOT_NAMES)("draws %s's legs at the linkage points", (name) => {
        const hexapod = posed(ROBOT_CONFIGS[name]);
        const scene = hexapodToScene(hexapod, -100, []);
        expect(scene.legs.length).toBe(6);
        hexapod.legs.forEach((leg, i) => {
            allClose(
                scene.legs[i],
                leg.allPoints.map((p) => [p.x, p.y, p.z]),
                1e-3,
            );
        });
        allClose(
            scene.body,
            hexapod.body.vertices.map((p) => [p.x, p.y, p.z]),
            1e-3,
        );
        expect(scene.feet).toEqual(scene.legs.map((l) => l[3]));
        expect(scene.colors).toEqual(VIEWER_COLORS);
    });

    it("draws the support polygon flat and in order", () => {
        const feet: Vec3[] = [
            [100, 0, -90],
            [-50, -87, -91],
            [-50, 87, -89],
            [0, 120, -90],
        ];
        const scene = hexapodToScene(posed(ROBOT_CONFIGS.nougat), -90, feet);
        const xy = (ps: readonly number[][]) => ps.map((p) => `${p[0]},${p[1]}`).sort();
        expect(xy(scene.support)).toEqual(xy(feet));
        expect(scene.support.every((p) => p[2] === -90)).toBe(true);
        const cx = scene.support.reduce((s, p) => s + p[0], 0) / 4;
        const cy = scene.support.reduce((s, p) => s + p[1], 0) / 4;
        const angles = scene.support.map((p) => Math.atan2(p[1] - cy, p[0] - cx));
        expect(angles).toEqual([...angles].sort((a, b) => a - b));
    });

    it("draws the body's own axes from the cog", () => {
        const hexapod = posed(ROBOT_CONFIGS.nougat);
        const scene = hexapodToScene(hexapod, 0, []);
        expect(scene.axes.map((a) => a.axis)).toEqual(["x", "y", "z"]);
        scene.axes.forEach((axis, i) => {
            expect(axis.from).toEqual(scene.cog);
            const expected = [...scene.cog];
            expected[i] += hexapod.dimensions.front / 2;
            allClose(axis.to, expected, 1e-3);
        });
    });

    it.each(ROBOT_NAMES)("survives JSON without negative zero (%s)", (name) => {
        const robot = ROBOT_CONFIGS[name];
        const scene = poseToScene(generatePoses("turn_left", robot)[7], robot);
        expect(JSON.parse(JSON.stringify(scene))).toEqual(scene);
        expect(numbers(scene).some((n) => Object.is(n, -0))).toBe(false);
    });

    it("moves every point rigidly when transformed", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const scene = poseToScene(generatePoses("walk_0", robot)[3], robot);
        const t = (30 * Math.PI) / 180;
        const rotation = [
            [Math.cos(t), -Math.sin(t), 0],
            [Math.sin(t), Math.cos(t), 0],
            [0, 0, 1],
        ];
        const shift = [10, -20, 50];
        const moved = transformScene(scene, rotation, shift);
        const points = (s: typeof scene) => [
            s.head,
            s.cog,
            ...s.body,
            ...s.feet,
            ...s.support,
            ...s.legs.flat(),
            ...s.axes.flatMap((a) => [a.from, a.to]),
        ];
        const before = points(scene);
        points(moved).forEach((after, i) => {
            const expected = matVec(rotation, before[i]).map((c, k) => c + shift[k]);
            allClose(after, expected, 1e-3);
        });
        expect(moved.ground).toBeCloseTo(scene.ground + 50);
        expect(moved.size).toBe(scene.size);
        expect(moved.labels).toEqual(scene.labels);
    });
});
