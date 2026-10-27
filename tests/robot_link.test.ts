// The wire format between the app and the ESP32, and the link built on it.
// Everything here mirrors something in the firmware repo -- SERVOMIN/SERVOMAX
// and the packed structs in protocol.h, the RobotCommand enum, the baked motion
// LUTs -- and none of it is checked at runtime: a wrong tick is a servo driven
// into a hard stop, and a wrong layout a packet the firmware silently misreads.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { RobotLink } from "../src/main/robot_link";
import { DRIVE_BODY_PAD, DRIVE_LABELS, DRIVE_MOVE_PAD, MOTION_TYPES } from "../src/shared/motions";
import { generatePoses } from "../src/shared/path_generator";
import {
    clampPoseAngles,
    jointAnglesToServoAngles,
    MAGIC_MOTION,
    MAGIC_POSE,
    MAGIC_VERSION,
    motionPacket,
    parseVersionReply,
    posePacket,
    poseToTicks,
    STANDBY_POSE,
    servoAngleToTicks,
    sessionPacket,
    versionRequest,
} from "../src/shared/protocol";
import {
    commandId,
    DEFAULT_CONFIG,
    FIRMWARE_COMMANDS,
    getJointLimits,
    getLegSigns,
    getSequenceFps,
    type RobotConfig,
} from "../src/shared/robot_config";
import { ROBOT_DRIVE_HOLD_S } from "../src/shared/settings";
import { ROBOT_CONFIGS } from "./golden";

const MOTION_COMMANDS: Record<string, number> = {
    standby: 0,
    walk_0: 1,
    walk_180: 2,
    walk_r45: 3,
    walk_r90: 4,
    walk_r135: 5,
    walk_l45: 6,
    walk_l90: 7,
    walk_l135: 8,
    fast_forward: 9,
    fast_backward: 10,
    turn_left: 11,
    turn_right: 12,
    climb_forward: 13,
    climb_backward: 14,
    rotate_x: 15,
    rotate_y: 16,
    rotate_z: 17,
    twist: 18,
};
const MIN = 102;
const MAX = 512;
const UNMIRRORED = [307, 239, 273];
const MIRRORED = [307, 375, 341];

const luts = (name: string) =>
    JSON.parse(readFileSync(join(__dirname, "fixtures", "firmware_luts", `${name}.json`), "utf-8"))
        .luts;

/** A link whose packets are captured rather than sent, on a clock of its own. */
function capturing(robot: RobotConfig) {
    const sent: Uint8Array[] = [];
    const clock = { now: 100.0 };
    const link = new RobotLink(robot, {
        send: (p) => {
            sent.push(p);
            return true;
        },
        clock: () => clock.now,
        cache: false,
    });
    return { link, sent, clock };
}

const motionsSent = (sent: Uint8Array[]) => {
    const names = Object.fromEntries(Object.entries(MOTION_COMMANDS).map(([k, v]) => [v, k]));
    return sent.filter((p) => p[0] === MAGIC_MOTION).map((p) => names[p[1]]);
};

describe("servo ticks", () => {
    it("reproduces each robot's firmware standby, mirroring and all", () => {
        const mirrored: Record<string, number[]> = {
            mochi: [3, 4, 5],
            macaroon: [3, 4, 5],
            nougat: [0, 4, 5],
        };
        for (const [name, robot] of Object.entries(ROBOT_CONFIGS)) {
            const ticks = poseToTicks(STANDBY_POSE, robot);
            expect(ticks).toEqual(luts(name).standby[0]);
            for (let leg = 0; leg < 6; leg++) {
                expect(ticks.slice(leg * 3, leg * 3 + 3)).toEqual(
                    mirrored[name].includes(leg) ? MIRRORED : UNMIRRORED,
                );
            }
        }
    });

    it.each(["nougat", "macaroon"] as const)("streams %s's walk as its own LUT", (name) => {
        const robot = ROBOT_CONFIGS[name];
        expect(generatePoses("walk_0", robot).map((p) => poseToTicks(p, robot))).toEqual(
            luts(name).walk_0,
        );
    });

    it("differs from Mochi's walk only where it is clamped", () => {
        const robot = ROBOT_CONFIGS.mochi;
        const ticks = generatePoses("walk_0", robot).map((p) => poseToTicks(p, robot));
        const lut = luts("mochi").walk_0 as number[][];
        const joints = new Set<number>();
        let worst = 0;
        ticks.forEach((frame, i) => {
            frame.forEach((t, j) => {
                const d = Math.abs(t - lut[i][j]);
                worst = Math.max(worst, d);
                if (d > 1) joints.add(j % 3);
            });
        });
        expect(worst).toBeLessThanOrEqual(4);
        expect([...joints]).toEqual([1]);
    });

    it("takes leg signs from legScale", () => {
        expect(getLegSigns(ROBOT_CONFIGS.mochi)).toEqual([1, 1, 1, -1, -1, -1]);
        expect(getLegSigns(ROBOT_CONFIGS.macaroon)).toEqual([1, 1, 1, -1, -1, -1]);
        expect(getLegSigns(ROBOT_CONFIGS.nougat)).toEqual([-1, 1, 1, 1, -1, -1]);
        expect(getLegSigns(DEFAULT_CONFIG)).toEqual([-1, 1, 1, 1, -1, -1]);
    });

    it("reflects mirrored legs about the centre, zero at 90", () => {
        for (const sign of [1, -1]) {
            const [j1, j2, j3] = jointAnglesToServoAngles(sign, 10, 20, -30);
            const [m1, m2, m3] = jointAnglesToServoAngles(-sign, 10, 20, -30);
            expect(j1).toBe(m1);
            expect(j2 - 90).toBe(90 - m2);
            expect(j3 - 90).toBe(90 - m3);
            expect(jointAnglesToServoAngles(sign, 0, 0, 0)).toEqual([90, 90, 90]);
        }
    });

    it("spans, follows and clamps to the servo range", () => {
        expect(servoAngleToTicks(0)).toBe(MIN);
        expect(servoAngleToTicks(180)).toBe(MAX);
        expect(Math.abs(servoAngleToTicks(90) - (MIN + MAX) / 2)).toBeLessThanOrEqual(1);
        expect(servoAngleToTicks(0, 150, 600)).toBe(150);
        expect(servoAngleToTicks(180, 150, 600)).toBe(600);
        expect(servoAngleToTicks(90, 150, 600)).toBe(375);
        for (const angle of [-1000, -0.1, 180.1, 1000]) {
            const t = servoAngleToTicks(angle);
            expect(Number.isInteger(t)).toBe(true);
            expect(t).toBeGreaterThanOrEqual(MIN);
            expect(t).toBeLessThanOrEqual(MAX);
        }
    });

    it("holds the mechanical limits", () => {
        for (const robot of Object.values(ROBOT_CONFIGS)) {
            const l = getJointLimits(robot);
            expect(clampPoseAngles(180, 180, 180, robot)).toEqual([l.coxia, l.femur, l.tibia]);
            expect(clampPoseAngles(-180, -180, -180, robot)).toEqual([
                -l.coxia,
                -l.femur,
                -l.tibia,
            ]);
            expect(clampPoseAngles(1, 2, 3, robot)).toEqual([1, 2, 3]);
        }
    });

    it("centres a missing leg, and never leaves the servo range", () => {
        const ticks = poseToTicks([]);
        expect(ticks.length).toBe(18);
        expect(new Set(ticks)).toEqual(new Set([servoAngleToTicks(90)]));
        expect(poseToTicks([{ coxia: 0 }]).length).toBe(18);
        for (const robot of Object.values(ROBOT_CONFIGS)) {
            for (const motion of ["walk_0", "turn_left", "twist", "standup"]) {
                for (const pose of generatePoses(motion, robot)) {
                    const t = poseToTicks(pose, robot);
                    expect(t.every((x) => x >= MIN && x <= MAX)).toBe(true);
                }
            }
        }
    });

    it("records the gaits that overrun the femur limit", () => {
        const overruns: Record<string, number> = {};
        for (const [name, robot] of Object.entries(ROBOT_CONFIGS)) {
            let worst = Number.NEGATIVE_INFINITY;
            for (const motion of ["walk_0", "walk_l90", "turn_left"])
                for (const pose of generatePoses(motion, robot))
                    for (const leg of pose)
                        worst = Math.max(worst, Math.abs(leg.femur) - robot.joint_limits.femur);
            overruns[name] = worst;
        }
        expect(Math.abs(overruns.mochi - 3.53)).toBeLessThan(0.1);
        expect(overruns.macaroon).toBeGreaterThan(0);
        expect(overruns.macaroon).toBeLessThan(1);
        expect(overruns.nougat).toBeLessThan(0);
    });
});

describe("packets", () => {
    it("lay out as the firmware's packed structs", () => {
        expect(motionPacket(1, 2, 3).length).toBe(7);
        expect(posePacket(Array(18).fill(307), 1, 8).length).toBe(44);
        expect(sessionPacket(1, 2).length).toBe(6);
        expect(versionRequest(1).length).toBe(5);
    });

    it("round trips a pose packet", () => {
        const ticks = poseToTicks(STANDBY_POSE);
        const p = posePacket(ticks, 42, 8, true);
        const v = new DataView(p.buffer);
        expect([p[0], p[1], v.getUint16(2, true), v.getUint32(4, true)]).toEqual([
            MAGIC_POSE,
            1,
            8,
            42,
        ]);
        expect(Array.from({ length: 18 }, (_, i) => v.getInt16(8 + 2 * i, true))).toEqual(ticks);
    });

    it("decodes a version reply, and ignores another query's", () => {
        const reply = (seq: number, build: string) => {
            const head = new Uint8Array(9);
            const v = new DataView(head.buffer);
            v.setUint8(0, MAGIC_VERSION);
            v.setUint32(1, seq, true);
            head.set([1, 3, 2, 0], 5);
            return new Uint8Array([...head, ...new TextEncoder().encode(build)]);
        };
        expect(parseVersionReply(reply(7, "v3.2.0"), 7)).toEqual({
            version: "3.2.0",
            build: "v3.2.0",
            protocol: 1,
        });
        expect(parseVersionReply(reply(6, "dev"), 7)).toBeNull();
        expect(parseVersionReply(reply(6, "dev").slice(0, 8), 6)).toBeNull();
        expect(parseVersionReply(new TextEncoder().encode("Got 5 bytes of data"), 6)).toBeNull();
    });
});

describe("robot link", () => {
    it("carries the speed in a motion command, within the robot's range", async () => {
        const { link, sent } = capturing(ROBOT_CONFIGS.nougat);
        await link.setMotionSpeed(80);
        expect(link.sendMotionCommand("walk_l90")).toBe(true);
        const last = sent.at(-1)!;
        expect([last[0], last[1], last[6]]).toEqual([MAGIC_MOTION, MOTION_COMMANDS.walk_l90, 80]);
        expect(await link.setMotionSpeed(5)).toBe(20);
        expect(await link.setMotionSpeed(250)).toBe(100);
    });

    it("plays streamed gaits at the robot's speed", async () => {
        for (const robot of Object.values(ROBOT_CONFIGS)) {
            expect(getSequenceFps(robot, 50)).toBeCloseTo(1000 / robot.delay_ms / 2);
        }
        const { link } = capturing(ROBOT_CONFIGS.macaroon);
        await link.setMotionSpeed(40);
        link.playSequence(generatePoses("walk_0", ROBOT_CONFIGS.macaroon));
        expect(link.sequenceFps).toBeCloseTo((1000 / 25) * 0.4);
        await link.setMotionSpeed(100);
        expect(link.sequenceFps).toBeCloseTo(1000 / 25);
    });

    it("does not send a motion the robot does not have", () => {
        const { link, sent } = capturing(ROBOT_CONFIGS.nougat);
        expect(link.sendMotionCommand("standup")).toBe(false);
        expect(link.drive("standup")).toBe(false);
        expect(sent).toEqual([]);
    });

    it("resolves every motion from the robot's own command list", () => {
        for (const robot of [...Object.values(ROBOT_CONFIGS), DEFAULT_CONFIG]) {
            expect(robot.commands).toEqual(FIRMWARE_COMMANDS);
            for (const [motion, id] of Object.entries(MOTION_COMMANDS))
                expect(commandId(robot, motion)).toBe(id);
        }
        const ui = new Set(MOTION_TYPES.map((m) => m.value));
        for (const motion of Object.keys(MOTION_COMMANDS)) expect(ui.has(motion)).toBe(true);
        expect([...ui].filter((m) => !(m in MOTION_COMMANDS))).toEqual(["standup"]);
    });

    it("sends a held gait once however often it is renewed", () => {
        const { link, sent } = capturing(ROBOT_CONFIGS.nougat);
        for (let i = 0; i < 5; i++) expect(link.drive("walk_0")).toBe(true);
        link.drive("turn_left");
        link.drive("standby");
        expect(motionsSent(sent)).toEqual(["walk_0", "turn_left", "standby"]);
    });

    it("ends a drive that is not renewed in standby", () => {
        const { link, sent, clock } = capturing(ROBOT_CONFIGS.nougat);
        link.drive("walk_0");
        clock.now += ROBOT_DRIVE_HOLD_S / 2;
        link.drive("walk_0");
        clock.now += ROBOT_DRIVE_HOLD_S * 0.9;
        link.expireDrive();
        expect(motionsSent(sent)).toEqual(["walk_0"]);
        clock.now += ROBOT_DRIVE_HOLD_S;
        link.expireDrive();
        link.expireDrive();
        expect(motionsSent(sent)).toEqual(["walk_0", "standby"]);
    });

    it.each([
        ["pose", (link: RobotLink) => link.sendPose(STANDBY_POSE)],
        ["sequence", (link: RobotLink) => link.playSequence([generatePoses("standby")[0]])],
    ])("lets go of a drive when a %s takes over", (_name, takeover) => {
        const { link, sent, clock } = capturing(ROBOT_CONFIGS.nougat);
        link.drive("walk_0");
        takeover(link);
        clock.now += ROBOT_DRIVE_HOLD_S * 2;
        link.expireDrive();
        expect(motionsSent(sent)).toEqual(["walk_0"]);
    });

    it("reaches every robot command once from the controller", () => {
        const pads = [
            DRIVE_MOVE_PAD.centre,
            ...DRIVE_MOVE_PAD.walk,
            ...DRIVE_MOVE_PAD.outer,
            ...DRIVE_BODY_PAD.flat().map(([m]) => m),
        ];
        expect(new Set(pads).size).toBe(pads.length);
        expect(new Set(pads)).toEqual(new Set(Object.keys(MOTION_COMMANDS)));
        expect(new Set(Object.keys(DRIVE_LABELS))).toEqual(new Set(Object.keys(MOTION_COMMANDS)));
    });

    it("plays a sequence frame by frame, skipping frames it woke too late for", () => {
        const robot = ROBOT_CONFIGS.nougat;
        const { link, sent, clock } = capturing(robot);
        link.connected = true;
        const poses = generatePoses("walk_0", robot);
        link.playSequence(poses, false, 50);
        link.tick();
        clock.now += 0.02;
        link.tick();
        clock.now += 0.065; // three frames due
        link.tick();
        const poseTicks = sent
            .filter((p) => p[0] === MAGIC_POSE)
            .map((p) => {
                const v = new DataView(p.buffer);
                return Array.from({ length: 18 }, (_, i) => v.getInt16(8 + 2 * i, true));
            });
        expect(poseTicks.length).toBe(3);
        expect(poseTicks[0]).toEqual(poseToTicks(poses[0], robot));
        expect(poseTicks[1]).toEqual(poseToTicks(poses[1], robot));
        expect(poseTicks[2]).toEqual(poseToTicks(poses[4], robot));
    });
});
