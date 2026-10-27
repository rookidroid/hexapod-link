// Reading the robot's config from the robot, and the HTTP routes around it.
// The app keeps no robot definitions: connecting asks the robot for its config,
// and that is what the app then models. The real HTTP client runs against
// tools/fake_robot.ts, which answers the way the firmware does.
import { existsSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { robotUrl, setSpeed, splitAddress } from "../src/main/robot_http";
import { fetchRobotConfig, RobotLink } from "../src/main/robot_link";
import {
    cachePath,
    loadCachedConfig,
    loadStartupConfig,
    saveCachedConfig,
} from "../src/main/storage";
import {
    commandId,
    DEFAULT_CONFIG,
    describeFirmware,
    describe as describeRobot,
    getSimulatorDimensions,
    parseRobotConfig,
    RobotConfigError,
} from "../src/shared/robot_config";
import { ROBOT_CONFIG_CACHE_ENV } from "../src/shared/settings";
import { FakeRobot } from "../tools/fake_robot";
import { loadPayload, ROBOT_CONFIGS, ROBOT_NAMES } from "./golden";

let cacheFile = "";
const robots: FakeRobot[] = [];
const links: RobotLink[] = [];

beforeEach(() => {
    cacheFile = join(mkdtempSync(join(tmpdir(), "hexapod-link-tests-")), "robot_config.json");
    process.env[ROBOT_CONFIG_CACHE_ENV] = cacheFile;
});

afterEach(async () => {
    for (const link of links.splice(0)) link.disconnect();
    for (const robot of robots.splice(0)) await robot.stop();
});

async function fake(payload?: Record<string, any>, options: Record<string, unknown> = {}) {
    const robot = await new FakeRobot(payload ?? loadPayload("nougat"), {
        udpPort: 0,
        ...options,
    }).start();
    robots.push(robot);
    return robot;
}

/** An address nothing answers on. */
async function nowhere(): Promise<string> {
    const robot = await new FakeRobot(loadPayload("nougat")).start();
    const address = robot.address;
    await robot.stop();
    return address;
}

function linkTo(robot: FakeRobot): RobotLink {
    const link = new RobotLink(DEFAULT_CONFIG, { udpPort: robot.udpPort ?? undefined });
    links.push(link);
    return link;
}

describe("parsing", () => {
    it("parses every robot's payload", () => {
        for (const name of ROBOT_NAMES) {
            const robot = parseRobotConfig(loadPayload(name));
            expect(robot.name).toBe(name);
            expect(robot.label).toBe(name[0].toUpperCase() + name.slice(1));
            expect(robot.source).toBe("robot");
            expect([robot.servo_min, robot.servo_max]).toEqual([102, 512]);
        }
    });

    it("carries the robot's own values", () => {
        const mochi = ROBOT_CONFIGS.mochi;
        expect(mochi.ssid).toBe("hexapod");
        expect(mochi.delay_ms).toBe(12);
        expect(mochi.joint_limits).toEqual({ coxia: 45, femur: 75, tibia: 75 });
        expect(mochi.gait.walk_radius).toBe(30);
        expect(mochi.gait.fastwalk).toEqual({
            g_steps: 28,
            y_radius: 40,
            z_radius: 30,
            x_radius: 15,
        });
        expect(ROBOT_CONFIGS.macaroon.delay_ms).toBe(25);
        expect(ROBOT_CONFIGS.nougat.config.legMountAngle).toEqual([45, 0, -45, -225, -180, -135]);
        const gait = ROBOT_CONFIGS.nougat.gait;
        expect(gait.rotate_x).toEqual({ g_steps: 28, swing_angle: 10, y_radius: 10 });
        expect(gait.rotate_z).toEqual({ g_steps: 28, z_lift: 7 });
        expect(gait.twist).toEqual({ g_steps: 28 });
        expect(gait.standby_posture).toEqual([60, 75]);
    });

    it("parses configs that share no state", () => {
        const a = parseRobotConfig(loadPayload("mochi"));
        const b = parseRobotConfig(loadPayload("mochi"));
        a.gait.rotate_x.g_steps = 99;
        a.config.legMountX[0] = 0;
        expect(b.gait.rotate_x.g_steps).toBe(28);
        expect(b.config.legMountX[0]).not.toBe(0);
    });

    it.each([
        [(p: any) => delete p.geometry, "geometry"],
        [(p: any) => delete p.protocol, "protocol"],
        [(p: any) => (p.protocol = 2), "Update Hexapod Link"],
        [(p: any) => (p.delay_ms = 0), "delay_ms"],
        [(p: any) => (p.geometry.legMountX = [1, 2, 3]), "legMountX"],
        [(p: any) => p.geometry.legScale.pop(), "legScale"],
        [(p: any) => (p.geometry.legScale[0][1] = 2), "legScale"],
        [(p: any) => (p.geometry.legJoint3ToTip = 0), "legJoint3ToTip"],
        [(p: any) => delete p.geometry.gait.walk_radius, "walk_radius"],
        [(p: any) => (p.servo = { min: 500, max: 100 }), "servo"],
    ])("refuses a malformed payload (%#: %s)", (mutate, message) => {
        const payload = loadPayload("nougat");
        mutate(payload);
        expect(() => parseRobotConfig(payload)).toThrow(RobotConfigError);
        expect(() => parseRobotConfig(payload)).toThrow(message);
    });

    it("defaults what the payload leaves out, and follows its command list", () => {
        const payload: any = loadPayload("nougat");
        delete payload.speed;
        delete payload.commands;
        delete payload.servo;
        delete payload.geometry.jointLimits;
        const robot = parseRobotConfig(payload);
        expect(robot.speed).toEqual({ min: 20, max: 100, default: 60, current: 60 });
        expect(commandId(robot, "twist")).toBe(18);
        expect(robot.joint_limits).toEqual({ coxia: 45, femur: 75, tibia: 75 });

        const reordered: any = loadPayload("nougat");
        reordered.commands = ["standby", "twist", "walk0"];
        const r = parseRobotConfig(reordered);
        expect(commandId(r, "twist")).toBe(1);
        expect(commandId(r, "walk_0")).toBe(2);
        expect(commandId(r, "turn_left")).toBeNull();
    });

    it("measures the default as Nougat, mount angles and all", () => {
        const dims = getSimulatorDimensions(ROBOT_CONFIGS.nougat);
        expect(dims).toEqual({
            front: 44.82,
            side: 74.82,
            middle: 61.03,
            coxia: 38.0,
            femur: 54.06,
            tibia: 93.53,
            mount_angles: [45, 0, 315, 135, 180, 225],
        });
        expect("mount_angles" in getSimulatorDimensions(ROBOT_CONFIGS.nougat, false)).toBe(false);
        expect(getSimulatorDimensions(DEFAULT_CONFIG)).toEqual(dims);
        expect(DEFAULT_CONFIG.config.legScale).toEqual(ROBOT_CONFIGS.nougat.config.legScale);
        expect([DEFAULT_CONFIG.name, DEFAULT_CONFIG.label, DEFAULT_CONFIG.source]).toEqual([
            "nougat",
            "Nougat",
            "default",
        ]);
    });

    it("reads the firmware from the payload", () => {
        expect(parseRobotConfig(loadPayload("nougat")).firmware).toEqual({
            version: "3.2.0",
            build: "dev",
            protocol: 1,
        });
        const old: any = loadPayload("nougat");
        delete old.firmware;
        expect(parseRobotConfig(old).firmware).toBeNull();
        expect(DEFAULT_CONFIG.firmware).toBeNull();
        const firmware = { version: "3.2.0", build: "v3.2.0-4-gabc", protocol: 1 };
        expect(describeFirmware(firmware)).toBe("Firmware 3.2.0 (v3.2.0-4-gabc) · protocol 1");
        expect(describeFirmware({ ...firmware, build: "" })).toBe("Firmware 3.2.0 · protocol 1");
        expect(describeFirmware(null)).toBe("Firmware version not reported");
    });
});

describe("cache", () => {
    it("round trips, and starts on the default without one", () => {
        expect(loadStartupConfig()).toBe(DEFAULT_CONFIG);
        expect(loadCachedConfig()).toBeNull();
        expect(saveCachedConfig(ROBOT_CONFIGS.nougat)).toBe(true);
        expect(cachePath()).toBe(cacheFile);
        const cached = loadCachedConfig()!;
        expect(cached.source).toBe("cache");
        expect(cached.config).toEqual(ROBOT_CONFIGS.nougat.config);
        expect(loadStartupConfig().name).toBe("nougat");
        expect(describeRobot(cached)).toContain("last connected");
        expect(describeRobot(ROBOT_CONFIGS.nougat)).toBe("Nougat · hexapod_nougat");
        expect(describeRobot(DEFAULT_CONFIG).startsWith("Nougat (default)")).toBe(true);
    });

    it("ignores an unreadable cache", () => {
        writeFileSync(cacheFile, "{not json");
        expect(loadCachedConfig()).toBeNull();
        writeFileSync(cacheFile, JSON.stringify({ protocol: 1 }));
        expect(loadCachedConfig()).toBeNull();
    });
});

describe("HTTP and connecting", () => {
    it("lets an address carry an HTTP port", () => {
        expect(splitAddress("192.168.4.1")).toEqual(["192.168.4.1", 80]);
        expect(splitAddress(" 127.0.0.1:8080 ")).toEqual(["127.0.0.1", 8080]);
        expect(robotUrl("192.168.4.1", "/robot_config")).toBe("http://192.168.4.1/robot_config");
        expect(robotUrl("127.0.0.1:8080", "/x")).toBe("http://127.0.0.1:8080/x");
    });

    it("reads the robot's config, and explains a robot that is not there", async () => {
        const robot = await fake();
        expect((await fetchRobotConfig(robot.address)).config).toEqual(ROBOT_CONFIGS.nougat.config);
        await expect(fetchRobotConfig(await nowhere(), 0.5)).rejects.toThrow(
            "Couldn't read the robot's config",
        );
    });

    it("sets the speed", async () => {
        const robot = await fake();
        expect(await setSpeed(robot.address, 75)).toBe(75);
        expect(robot.speed).toBe(75);
        expect(await setSpeed(robot.address, 5)).toBe(20);
    });

    it("connects, loading and caching the robot's config and speed", async () => {
        const robot = await fake();
        robot.speed = 45;
        const link = linkTo(robot);
        expect(await link.connect(robot.address)).toBe(true);
        expect(link.connected).toBe(true);
        expect(link.robotConfig.name).toBe("nougat");
        expect(link.configVersion).toBe(1);
        expect(link.status().robot_label).toBe("Nougat");
        expect(loadCachedConfig()!.name).toBe("nougat");
        expect(link.speedPct).toBe(45);
        await link.setMotionSpeed(90);
        expect(robot.speed).toBe(90);
    });

    it("does not connect to a robot that does not answer", async () => {
        const link = new RobotLink(DEFAULT_CONFIG);
        expect(await link.connect(await nowhere())).toBe(false);
        expect(link.connected).toBe(false);
        expect(link.status().last_error).toContain("Couldn't read the robot's config");
        expect(link.robotConfig).toBe(DEFAULT_CONFIG);
        expect(link.configVersion).toBe(0);
        expect(existsSync(cacheFile)).toBe(false);
    });

    it("asks the firmware its version over UDP", async () => {
        const robot = await fake();
        delete robot.payload.firmware;
        const link = linkTo(robot);
        expect(await link.connect(robot.address)).toBe(true);
        expect(link.robotConfig.firmware).toBeNull();
        expect(link.firmware).toEqual({ version: "0.0.0", build: "fake", protocol: 1 });
        expect(link.status().firmware).toEqual(link.firmware);
        link.disconnect();
        expect(link.firmware).toBeNull();
    });

    it("falls back to the config's firmware without a UDP answer", async () => {
        const robot = await fake(undefined, { answerVersion: false });
        const link = linkTo(robot);
        expect(await link.connect(robot.address)).toBe(true);
        expect(link.firmware).toEqual({ version: "3.2.0", build: "dev", protocol: 1 });

        const old: any = loadPayload("nougat");
        delete old.firmware;
        const older = await fake(old, { answerVersion: false });
        const link2 = linkTo(older);
        expect(await link2.connect(older.address)).toBe(true);
        expect(link2.firmware).toBeNull();
    });

    it("streams to the robot once connected, and leaves real-time mode on disconnect", async () => {
        const robot = await fake();
        const link = linkTo(robot);
        await link.connect(robot.address);
        link.setStreaming(true);
        link.sendPose([{ id: 0, name: "", coxia: 5, femur: 30, tibia: -15 }]);
        await new Promise((r) => setTimeout(r, 120));
        link.disconnect();
        await new Promise((r) => setTimeout(r, 100));
        const kinds = robot.packets.map((p) => p[0]);
        expect(kinds[0]).toBe(0xa7); // RT_ENTER
        expect(robot.packets[0][1]).toBe(1);
        expect(kinds.filter((k) => k === 0xa6).length).toBeGreaterThan(3);
        const last = robot.packets.at(-1)!;
        expect([last[0], last[1]]).toEqual([0xa7, 0]); // RT_EXIT
    });
});
