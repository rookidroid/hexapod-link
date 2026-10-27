// The gaits' foot paths as the app draws them: the leg mounts it poses the
// legs around, and how the feet on the floor move while they stay down.
import { describe, expect, it } from "vitest";
import { VirtualHexapod } from "../src/shared/models";
import { generatePoses } from "../src/shared/path_generator";
import { getSimulatorDimensions } from "../src/shared/robot_config";
import { pyMod, type Vec3 } from "../src/shared/util";
import { ROBOT_CONFIGS } from "./golden";

// Gaits whose stance stroke is a straight line in one direction, so the feet
// that stay planted must stay put relative to each other. The turns sweep each
// foot along a chord, so their polygon may only scale (TURN_GAITS).
const STRAIGHT_GAITS = [
    "walk_0",
    "walk_180",
    "walk_l45",
    "walk_l90",
    "walk_l135",
    "walk_r45",
    "walk_r90",
    "walk_r135",
    "fast_forward",
    "fast_backward",
];
const TURN_GAITS = ["turn_left", "turn_right"];
// The robots' `side` is a rounded value, which leaves a sub-micron residue.
const TOL_MM = 1e-3;
const robots = Object.entries(ROBOT_CONFIGS);

type Contacts = Map<number, Vec3>;

function footFrames(motion: string, name: string): Vec3[][] {
    const robot = ROBOT_CONFIGS[name as keyof typeof ROBOT_CONFIGS];
    const hexapod = new VirtualHexapod(getSimulatorDimensions(robot));
    return generatePoses(motion, robot).map((pose) => {
        pose.forEach((j, id) => {
            hexapod.legs[id].changePose(j.coxia, j.femur, j.tibia);
        });
        return hexapod.legs.map((leg) => {
            const f = leg.footTip();
            return [f.x, f.y, f.z] as Vec3;
        });
    });
}

function planted(feet: Vec3[]): Contacts {
    const floor = Math.min(...feet.map((f) => f[2]));
    const out: Contacts = new Map();
    feet.forEach((f, leg) => {
        if (f[2] - floor < TOL_MM) out.set(leg, [f[0], f[1], f[2] - floor]);
    });
    return out;
}

function stanceRuns(motion: string, name: string): Contacts[][] {
    const runs: Contacts[][] = [];
    for (const feet of footFrames(motion, name)) {
        const contacts = planted(feet);
        const last = runs[runs.length - 1];
        const keys = (c: Contacts) => [...c.keys()].sort().join();
        if (last && keys(last[last.length - 1]) === keys(contacts)) {
            last.push(contacts);
        } else {
            runs.push([contacts]);
        }
    }
    return runs;
}

function* consecutive(motions: string[]): Generator<[string, Contacts, Contacts]> {
    for (const [name] of robots) {
        for (const motion of motions) {
            for (const run of stanceRuns(motion, name)) {
                for (let i = 1; i < run.length; i++)
                    yield [`${name}/${motion}`, run[i - 1], run[i]];
            }
        }
    }
}

const dist = (a: Vec3, b: Vec3) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

function sides(c: Contacts): number[] {
    const legs = [...c.keys()].sort();
    const out: number[] = [];
    for (let i = 0; i < legs.length; i++)
        for (let j = i + 1; j < legs.length; j++) out.push(dist(c.get(legs[i])!, c.get(legs[j])!));
    return out;
}

describe("motion", () => {
    it("mounts each leg where the robot does", () => {
        for (const [name, robot] of robots) {
            const hexapod = new VirtualHexapod(getSimulatorDimensions(robot));
            const expected = robot.config.legMountAngle.map((a) => pyMod(a, 360));
            hexapod.body.coxiaAxes.forEach((a, i) => {
                expect(Math.abs(a - expected[i]), name).toBeLessThan(0.01);
            });
        }
    });

    it("knows Nougat's legs are not radial", () => {
        for (const [name, robot] of robots) {
            const radial = new VirtualHexapod(getSimulatorDimensions(robot, false));
            const expected = robot.config.legMountAngle.map((a) => pyMod(a, 360));
            const worst = Math.max(
                ...radial.body.coxiaAxes.map((a, i) => Math.abs(a - expected[i])),
            );
            if (name === "nougat") {
                expect(Math.abs(worst - (59.07 - 45))).toBeLessThan(0.05);
            } else {
                expect(worst).toBeLessThan(0.01);
            }
        }
    });

    it("puts a square body's corner legs on the diagonals", () => {
        const hexapod = new VirtualHexapod({
            front: 100,
            side: 100,
            middle: 100,
            coxia: 100,
            femur: 100,
            tibia: 100,
        });
        [45, 0, 315, 135, 180, 225].forEach((a, i) => {
            expect(hexapod.body.coxiaAxes[i]).toBeCloseTo(a, 9);
        });
    });

    it("keeps the support polygon's shape, and moves planted feet as one", () => {
        for (const [where, before, after] of consecutive(STRAIGHT_GAITS)) {
            const legs = [...before.keys()];
            for (let i = 0; i < legs.length; i++) {
                for (let j = i + 1; j < legs.length; j++) {
                    const was = dist(before.get(legs[i])!, before.get(legs[j])!);
                    const now = dist(after.get(legs[i])!, after.get(legs[j])!);
                    expect(Math.abs(now - was), where).toBeLessThan(TOL_MM);
                }
            }
            const deltas = legs.map((leg) =>
                after.get(leg)!.map((c, k) => c - before.get(leg)![k]),
            );
            for (let k = 0; k < 3; k++) {
                const values = deltas.map((d) => d[k]);
                expect(Math.max(...values) - Math.min(...values), where).toBeLessThan(TOL_MM);
            }
        }
    });

    it("stands up into the standby stance without dragging a foot", () => {
        for (const [name] of robots) {
            const landed = footFrames("standup", name).at(-1)!;
            const standing = footFrames("standby", name)[0];
            landed.forEach((f, leg) => {
                expect(dist(f, standing[leg]), name).toBeLessThan(TOL_MM);
            });
        }
        for (const [where, before, after] of consecutive(["standup"])) {
            for (const [leg, p] of before) {
                expect(dist(after.get(leg)!, p), where).toBeLessThan(TOL_MM);
            }
        }
    });

    it("lets a turn's support polygon breathe, but not shear", () => {
        for (const [where, before, after] of consecutive(TURN_GAITS)) {
            const was = sides(before);
            const now = sides(after);
            const mean = (v: number[]) => v.reduce((a, b) => a + b, 0) / v.length;
            const drift = Math.max(
                ...now.map((n, i) => Math.abs(n / mean(now) - was[i] / mean(was))),
            );
            expect(drift, where).toBeLessThan(where.startsWith("nougat/") ? 2e-3 : 1e-5);
        }
        for (const [name] of robots) {
            for (const motion of TURN_GAITS) {
                for (const run of stanceRuns(motion, name)) {
                    const scales = run.map((c) => {
                        const s = sides(c);
                        return s.reduce((a, b) => a + b, 0) / s.length;
                    });
                    expect(Math.max(...scales) / Math.min(...scales) - 1).toBeLessThan(0.02);
                }
            }
        }
    });
});
