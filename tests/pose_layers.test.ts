// The pose in layers: the body moves over feet that stay planted, and a moved
// foot stays where it was put while the body moves. Then a sequence made of
// layered keyframes plays as the layers say.
import { describe, expect, it } from "vitest";
import * as kf from "../src/shared/keyframes";
import type { Pose } from "../src/shared/path_generator";
import * as pl from "../src/shared/pose_layers";
import {
    DEFAULT_CONFIG,
    getSimulatorDimensions,
    type RobotConfig,
    withDimensions,
} from "../src/shared/robot_config";
import { cross, dot, type Vec3 } from "../src/shared/util";
import { allClose, ROBOT_CONFIGS, ROBOTS } from "./golden";

const TILT = {
    percent_x: 0.15,
    percent_y: -0.1,
    percent_z: 0.2,
    rot_x: 7.5,
    rot_y: -6.0,
    rot_z: 6.0,
};
const ZERO: Vec3[] = Array.from({ length: 6 }, () => [0, 0, 0]);
const tilted = () => pl.makeState(TILT, ZERO);
const JOINTS = ["coxia", "femur", "tibia"] as const;

function drawnFeet(state: pl.PoseState, robot: RobotConfig): Vec3[] {
    const [, pose] = pl.solve(state, robot);
    return pl.scene(state, pose, robot).feet;
}

const heldInReach = (state: pl.PoseState, robot: RobotConfig) =>
    kf.feetToPose(pl.bodyFeet(state, robot), robot, pl.BODY_LIMIT_MARGIN_DEG)[1].length === 0;

function turned(point: Vec3, pivot: Vec3, axisIn: Vec3, degrees: number): Vec3 {
    const n = Math.hypot(...axisIn);
    const axis = axisIn.map((c) => c / n);
    const r = point.map((c, i) => c - pivot[i]);
    const t = (degrees * Math.PI) / 180;
    const c = cross(axis, r);
    const d = dot(axis, r);
    return [0, 1, 2].map(
        (i) => pivot[i] + r[i] * Math.cos(t) + c[i] * Math.sin(t) + axis[i] * d * (1 - Math.cos(t)),
    ) as Vec3;
}

describe.each(ROBOTS)("%s", (_name, robot) => {
    it("stands in the standby posture, on the floor", () => {
        const state = pl.standbyState();
        const [feet, , bad] = pl.solve(state, robot);
        expect(bad).toEqual([]);
        allClose(feet, kf.standbyFeet(robot), 1e-2);
        allClose(
            drawnFeet(state, robot).map((f) => f[2]),
            Array(6).fill(0),
            1e-2,
        );
    });

    it("keeps the feet planted as the body moves", () => {
        const state = tilted();
        expect(pl.solve(state, robot)[2]).toEqual([]);
        allClose(drawnFeet(state, robot), drawnFeet(pl.standbyState(), robot), 1e-2);
    });

    it("lowers the feet in the body frame as the body rises", () => {
        const raised = pl.makeState({ percent_z: 0.1 }, ZERO);
        const before = pl.bodyFeet(pl.standbyState(), robot);
        const after = pl.bodyFeet(raised, robot);
        allClose(
            after.map((f) => f.slice(0, 2)),
            before.map((f) => f.slice(0, 2)),
            1e-2,
        );
        after.forEach((f, i) => {
            expect(f[2]).toBeLessThan(before[i][2]);
        });
    });

    it("turns every coxia the other way as the body turns", () => {
        const [, pose, bad] = pl.solve(pl.makeState({ rot_z: 12.0 }, ZERO), robot);
        expect(bad).toEqual([]);
        expect(pose.every((leg) => leg.coxia < -1.0)).toBe(true);
    });

    it("puts a moved foot where it was put, and keeps it there", () => {
        const state = tilted();
        const t = drawnFeet(state, robot)[0];
        const target: Vec3 = [t[0] + 10, t[1] + 5, t[2] + 30];
        const moved = pl.withFootAt(state, 0, target, robot);
        expect(pl.solve(moved, robot)[2]).toEqual([]);
        allClose(drawnFeet(moved, robot)[0], target, 1e-2);
        allClose(pl.viewFeet(moved, robot)[0], target, 1e-2);
        const level = pl.makeState({}, moved.offsets);
        allClose(drawnFeet(level, robot)[0], target, 1e-2);
        allClose(
            drawnFeet(level, robot)
                .slice(1)
                .map((f) => f[2]),
            Array(5).fill(0),
            1e-2,
        );
    });

    it("holds a foot dragged past its leg's reach as near as it gets", () => {
        const state = tilted();
        const start = drawnFeet(state, robot)[0];
        const near: Vec3 = [start[0] + 10, start[1] + 5, start[2] + 30];
        expect(pl.withFootNear(state, 0, near, robot)).toEqual(
            pl.withFootAt(state, 0, near, robot),
        );

        const h = Math.hypot(start[0], start[1]);
        const target: Vec3 = [
            start[0] + (500 * start[0]) / h,
            start[1] + (500 * start[1]) / h,
            start[2],
        ];
        expect(pl.solve(pl.withFootAt(state, 0, target, robot), robot)[2]).toEqual([0]);
        const held = pl.withFootNear(state, 0, target, robot)!;
        expect(pl.solve(held, robot)[2]).toEqual([]);
        const foot = drawnFeet(held, robot)[0];
        allClose(pl.viewFeet(held, robot)[0], foot, 1e-2);
        const d = (a: readonly number[], b: readonly number[]) =>
            Math.hypot(...a.map((c, i) => c - b[i]));
        expect(d(foot, start)).toBeGreaterThan(10);
        expect(d(foot, target)).toBeLessThan(d(start, target));
        expect(held.body).toEqual(state.body);
        allClose(drawnFeet(held, robot).slice(1), drawnFeet(state, robot).slice(1), 1e-2);
        expect(pl.withFootNear(held, 0, target, robot)).toEqual(held);
    });

    it("puts a body moved within reach where it is put", () => {
        expect(pl.withBodyNear(pl.standbyState(), TILT, robot)).toEqual(tilted());
    });

    it.each(pl.BODY_KEYS.flatMap((key) => [-1, 1].map((way) => [key, way] as const)))(
        "stops a body pushed past reach (%s %d)",
        (key, way) => {
            const start = tilted();
            const asked = { ...TILT, [key]: way * (key.startsWith("percent") ? 1.0 : 39.0) };
            expect(pl.solve(pl.makeState(asked, start.offsets), robot)[2]).not.toEqual([]);
            const held = pl.withBodyNear(start, asked, robot);
            expect(heldInReach(held, robot)).toBe(true);
            expect(held.offsets).toEqual(start.offsets);
            for (const k of pl.BODY_KEYS) if (k !== key) expect(held.body[k]).toBe(start.body[k]);
            const step = pl.BODY_STEPS[pl.BODY_KEYS.indexOf(key)];
            const back = ((asked[key] - held.body[key]) * way) / step;
            expect(Math.abs(back - Math.round(back))).toBeLessThan(1e-6);
            expect(back).toBeGreaterThanOrEqual(1 - 1e-9);
            expect((held.body[key] - start.body[key]) * way).toBeGreaterThan(0);
            const further = pl.makeState(
                { ...held.body, [key]: held.body[key] + way * step },
                held.offsets,
            );
            expect(heldInReach(further, robot)).toBe(false);
            expect(pl.withBodyNear(held, asked, robot)).toEqual(held);
        },
    );

    it("moves a body pushed two ways the way it can", () => {
        const held = pl.withBodyNear(tilted(), { ...TILT, percent_x: 0.1, percent_z: 1.0 }, robot);
        expect(heldInReach(held, robot)).toBe(true);
        expect(held.body.percent_x).toBeCloseTo(0.1);
        expect(held.body.percent_z).toBeGreaterThan(TILT.percent_z);
        expect(held.body.percent_z).toBeLessThan(1.0);
    });

    it("lets a body whose legs are out of reach go where it is put", () => {
        const offsets = ZERO.map((o) => [...o] as Vec3);
        offsets[2] = [0, 0, 1000];
        const start = pl.makeState({}, offsets);
        expect(pl.solve(start, robot)[2]).toEqual([2]);
        expect(pl.withBodyNear(start, TILT, robot)).toEqual(pl.makeState(TILT, offsets));
    });

    it("moves a body from a foot held at its limit", () => {
        const start = pl.standbyState();
        const foot = drawnFeet(start, robot)[0];
        const h = Math.hypot(foot[0], foot[1]);
        const away = [foot[0] / h, foot[1] / h, 0];
        const stretched = pl.withFootNear(
            start,
            0,
            foot.map((c, i) => c + 500 * away[i]),
            robot,
        )!;
        expect(heldInReach(stretched, robot)).toBe(true);
        const side = getSimulatorDimensions(robot).middle;
        const back = { percent_x: (-30.0 * away[0]) / side };
        expect(
            Math.abs(pl.withBodyNear(stretched, back, robot).body.percent_x - back.percent_x),
        ).toBeGreaterThan(1e-6);
        const towards = { percent_x: 0.05 * Math.sign(away[0]) };
        expect(pl.withBodyNear(stretched, towards, robot).body.percent_x).toBeCloseTo(
            towards.percent_x,
        );
    });

    it("moves only that foot when a leg's joints are set", () => {
        const state = tilted();
        const [, before] = pl.solve(state, robot);
        const moved = pl.withLegAngles(state, 4, { coxia: 10.0, femur: 45.0 }, robot);
        const [, after, bad] = pl.solve(moved, robot);
        expect(bad).toEqual([]);
        expect(Math.abs(after[4].coxia - 10)).toBeLessThan(1e-2);
        expect(Math.abs(after[4].femur - 45)).toBeLessThan(1e-2);
        expect(Math.abs(after[4].tibia - before[4].tibia)).toBeLessThan(1e-2);
        expect(moved.body).toEqual(state.body);
        for (const leg of [0, 1, 2, 3, 5])
            for (const j of JOINTS)
                expect(Math.abs(after[leg][j] - before[leg][j])).toBeLessThan(1e-2);
        const drawn = drawnFeet(moved, robot);
        allClose(
            [0, 1, 2, 3, 5].map((i) => drawn[i][2]),
            Array(5).fill(0),
            1e-2,
        );
        expect(drawn[4][2]).toBeGreaterThan(1.0);
    });

    it("turns each joint about the axis the view rings it by", () => {
        const state = tilted();
        const [, pose] = pl.solve(state, robot);
        const drawn = pl.scene(state, pose, robot);
        for (let leg = 0; leg < 6; leg++) {
            const points = drawn.legs[leg];
            JOINTS.forEach((joint, index) => {
                const info = drawn.joints![leg][index];
                expect(Math.abs(info.angle - pose[leg][joint])).toBeLessThan(1e-3);
                expect(info.axis).not.toBeNull();
                const moved = pl.withLegAngles(
                    state,
                    leg,
                    { [joint]: pose[leg][joint] + 3.0 },
                    robot,
                );
                allClose(
                    pl.viewFeet(moved, robot)[leg],
                    turned(points[3], points[index], info.axis!, 3),
                    0.05,
                );
            });
        }
    });

    it("finds the same body where its frame is", () => {
        const state = tilted();
        const frame = pl.bodyFrame(state, robot);
        const body = pl.bodyAt(frame.origin, frame.rot, robot);
        allClose(pl.makeState(body, state.offsets).body, state.body, 1e-3);
        const [, pose] = pl.solve(state, robot);
        const drawn = pl.scene(state, pose, robot);
        expect(drawn.frame).toEqual(frame);
        allClose(drawn.frame!.origin, drawn.cog, 1e-2);
    });

    it("leaves the robot as it is for unchanged dimensions", () => {
        const d = getSimulatorDimensions(robot, false);
        expect(withDimensions(robot, d)).toBe(robot);
        expect(withDimensions(robot, null)).toBe(robot);
        expect(
            withDimensions(robot, { front: 0, side: 0, middle: 0, coxia: 0, femur: 0, tibia: 0 }),
        ).toBe(robot);
    });

    it("measures a resized robot as asked, and still poses it", () => {
        const d = getSimulatorDimensions(robot, false);
        const asked = { ...d, front: d.front * 1.2, femur: d.femur * 1.1 };
        const resized = withDimensions(robot, asked);
        allClose(getSimulatorDimensions(resized, false), asked, 1e-9);
        expect(resized.config.legScale).toEqual(robot.config.legScale);
        expect(resized.joint_limits).toEqual(robot.joint_limits);
        expect(resized.name).toBe(robot.name);
        expect(resized.config.legMountAngle).toEqual(robot.config.legMountAngle);
        const state = tilted();
        expect(pl.solve(state, resized)[2]).toEqual([]);
        allClose(
            drawnFeet(state, resized).map((f) => f[2]),
            Array(6).fill(0),
            1e-2,
        );
        allClose(pl.bodyFeet(pl.standbyState(), resized), kf.standbyFeet(resized), 1e-2);
    });
});

describe("pose layers", () => {
    it("keeps scene joints within the ring's range", () => {
        const state = tilted();
        const [, pose] = pl.solve(state, DEFAULT_CONFIG);
        const joints = pl.scene(state, pose, DEFAULT_CONFIG).joints!;
        expect(JSON.parse(JSON.stringify(joints))).toEqual(joints);
        expect(joints.map((leg) => leg.length)).toEqual(Array(6).fill(3));
        for (const leg of joints)
            JOINTS.forEach((name, i) => {
                expect(leg[i].most).toBeCloseTo(
                    DEFAULT_CONFIG.joint_limits[name] - kf.LIMIT_MARGIN_DEG,
                    3,
                );
            });
    });

    it("turns keyframe feet into moves from standby", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const feet = kf.standbyFeet(robot);
        feet[2] = [feet[2][0] + 5, feet[2][1] - 5, feet[2][2] + 20];
        const state = pl.fromFeet(feet, robot);
        allClose(pl.bodyFeet(state, robot), feet, 1e-2);
        expect(state.offsets.flat().filter((c) => Math.abs(c) > 1e-6).length).toBe(3);
    });

    it("recognises a state", () => {
        expect(pl.isState(JSON.parse(JSON.stringify(tilted())))).toBe(true);
        expect(pl.isState({ body: {}, offsets: [] })).toBe(false);
        expect(pl.isState(null)).toBe(false);
    });

    it("tilts the body over planted feet in a layered sequence", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const standby = pl.standbyState();
        const keyframes = [standby, tilted()].map((s) =>
            kf.makeKeyframe(pl.bodyFeet(s, robot), 400, s),
        );
        const { feet, states, poses, badFrames } = pl.sequence(keyframes, robot, 20);
        expect(badFrames).toEqual([]);
        expect(feet.length).toBe(9);
        expect(states!.length).toBe(9);
        allClose(feet.at(-1), keyframes[1].feet, 1e-2);
        states!.forEach((state, i) => {
            allClose(
                pl.scene(state, poses[i] as Pose, robot).feet,
                drawnFeet(standby, robot),
                1e-2,
            );
        });
    });

    it("moves feet in straight lines without layers", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const start = kf.standbyFeet(robot);
        const end = start.map((f, i) => (i === 0 ? [f[0], f[1], f[2] + 30] : [...f]) as Vec3);
        const keyframes = [kf.makeKeyframe(start), kf.makeKeyframe(end, 500)];
        const { feet, states, badFrames } = pl.sequence(keyframes, robot, 20, false, false);
        expect(states).toBeNull();
        expect(badFrames).toEqual([]);
        allClose(feet, kf.interpolateFeet(keyframes, 20, false, false), 1e-9);
    });

    it("keeps a keyframe's layers in its file", () => {
        const robot = ROBOT_CONFIGS.macaroon;
        const state = tilted();
        const keyframes = [kf.makeKeyframe(pl.bodyFeet(state, robot), 300, state)];
        expect(kf.load(kf.dump(keyframes, robot), robot)[0].state).toEqual(state);
    });
});
