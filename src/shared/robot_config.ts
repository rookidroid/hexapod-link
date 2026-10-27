// The config of the physical hexapod being driven.
//
// The firmware serves its own at GET /robot_config -- its name and access
// point, servo range, LUT frame delay, playback speed limits, the motion
// commands it knows, and its geometry, which is the robot's
// software/path_tool/robots/<name>.json compiled into the firmware. The link
// fetches that on every connect (main/robot_link.ts), so the app always models
// the robot that is actually on the other end.
//
// The last config received is cached to disk (main/storage.ts), so the app
// still shows that robot when started without one. Before any robot has ever
// connected it falls back to DEFAULT_PAYLOAD below: Nougat.
//
// A payload is parsed into the RobotConfig the rest of the app works with.
// This module does no I/O, so the page, the main process and the tests all
// use it.

import { pyMod } from "./util";

/** Highest GET /robot_config protocol this app understands. */
export const SUPPORTED_PROTOCOL = 1;

/** The firmware's motion names in RobotCommand order, for configs that predate
 * the robot listing them. */
export const FIRMWARE_COMMANDS = [
    "standby",
    "walk0",
    "walk180",
    "walkr45",
    "walkr90",
    "walkr135",
    "walkl45",
    "walkl90",
    "walkl135",
    "fastforward",
    "fastbackward",
    "turnleft",
    "turnright",
    "climbforward",
    "climbbackward",
    "rotatex",
    "rotatey",
    "rotatez",
    "twist",
];

export const DEFAULT_SPEED = { min: 20, max: 100, default: 60 };
export const DEFAULT_JOINT_LIMITS = { coxia: 45, femur: 75, tibia: 75 };

// Gait parameters path_tool's generate_motion.py bakes into every robot's LUTs
// without reading them from the robot's JSON. The JSON's own "gait" block (walk
// and turn radii, fast-walk radii) is laid over these.
const FIXED_GAIT = {
    fastwalk_g_steps: 28,
    rotate_x: { g_steps: 28, swing_angle: 10, y_radius: 10 },
    rotate_y: { g_steps: 28, swing_angle: 10, x_radius: 10 },
    rotate_z: { g_steps: 28, z_lift: 7 },
    twist: { g_steps: 28 },
    standup_steps: 28,
};

export interface Geometry {
    name?: string;
    label?: string;
    legMountX: number[];
    legMountY: number[];
    legMountAngle: number[];
    legScale: number[][];
    legRootToJoint1: number;
    legJoint1ToJoint2: number;
    legJoint2ToJoint3: number;
    legJoint3ToTip: number;
    [key: string]: unknown;
}

export interface Gait {
    standby_posture: [number, number];
    laydown_posture: [number, number];
    walk_radius: number;
    turn_radius: number;
    fastwalk: { g_steps: number; y_radius: number; z_radius: number; x_radius: number };
    standup_steps: number;
    rotate_x: { g_steps: number; swing_angle: number; y_radius: number };
    rotate_y: { g_steps: number; swing_angle: number; x_radius: number };
    rotate_z: { g_steps: number; z_lift: number; xy_radius?: number };
    twist: { g_steps: number };
}

export interface JointLimits {
    coxia: number;
    femur: number;
    tibia: number;
}

export interface Firmware {
    version: string;
    build: string;
    protocol: number;
}

export interface RobotConfig {
    name: string;
    label: string;
    ssid: string;
    protocol: number;
    firmware: Firmware | null;
    source: "robot" | "cache" | "default";
    delay_ms: number;
    servo_min: number;
    servo_max: number;
    speed: { min: number; max: number; default: number; current: number };
    commands: string[];
    config: Geometry;
    gait: Gait;
    joint_limits: JointLimits;
    payload: Record<string, unknown>;
}

// Nougat's geometry: the firmware repo's software/path_tool/robots/nougat.json.
const NOUGAT_GEOMETRY = {
    name: "nougat",
    label: "Nougat",
    legMountX: [44.82, 61.03, 44.82, -44.82, -61.03, -44.82],
    legMountY: [74.82, 0, -74.82, 74.82, 0, -74.82],
    legMountAngle: [45, 0, -45, -225, -180, -135],
    legScale: [
        [1, -1, -1],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 1],
        [1, -1, -1],
        [1, -1, -1],
    ],
    legRootToJoint1: 0,
    legJoint1ToJoint2: 38.0,
    legJoint2ToJoint3: 54.06,
    legJoint3ToTip: 93.53,
    servoMin: 102,
    servoMax: 512,
    jointLimits: { ...DEFAULT_JOINT_LIMITS },
    standbyPosture: [60, 75],
    laydownPosture: [25, 25],
    gait: {
        walk_radius: 40,
        fastwalk_y_radius: 50,
        fastwalk_z_radius: 40,
        fastwalk_x_radius: 15,
        turn_radius: 35,
    },
};

/** Stands in for a robot until one has connected: Nougat, as its firmware
 * reports itself, so it goes through the same parser. */
export const DEFAULT_PAYLOAD = {
    protocol: SUPPORTED_PROTOCOL,
    name: "nougat",
    ssid: "",
    delay_ms: 12,
    servo: { min: 102, mid: 307, max: 512 },
    speed: { ...DEFAULT_SPEED },
    commands: [...FIRMWARE_COMMANDS],
    geometry: NOUGAT_GEOMETRY,
};

export class RobotConfigError extends Error {
    override name = "RobotConfigError";
}

// ----------------------------------------------------------------- parsing

type Json = Record<string, any>;

function isObject(value: unknown): value is Json {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function required(mapping: unknown, key: string, where: string): any {
    if (!isObject(mapping) || !(key in mapping)) {
        throw new RobotConfigError(`Robot config is missing '${key}' in ${where}`);
    }
    return mapping[key];
}

function number(value: unknown, what: string): number {
    if (typeof value !== "number") {
        throw new RobotConfigError(`Robot config: ${what} must be a number`);
    }
    return value;
}

function six(values: unknown, what: string): number[] {
    if (!Array.isArray(values) || values.length !== 6) {
        throw new RobotConfigError(`Robot config: ${what} must list 6 legs`);
    }
    return values.map((v) => number(v, what));
}

function parseGeometry(geometry: Json): Geometry {
    const config = structuredClone(geometry) as Geometry;
    config.legMountX = six(required(geometry, "legMountX", "geometry"), "legMountX");
    config.legMountY = six(required(geometry, "legMountY", "geometry"), "legMountY");
    config.legMountAngle = six(required(geometry, "legMountAngle", "geometry"), "legMountAngle");

    const legScale = required(geometry, "legScale", "geometry");
    if (
        !(
            Array.isArray(legScale) &&
            legScale.length === 6 &&
            legScale.every((row) => Array.isArray(row) && row.length === 3)
        )
    ) {
        throw new RobotConfigError("Robot config: legScale must be 6 rows of 3");
    }
    for (const row of legScale) {
        for (const value of row) {
            if (value !== 1 && value !== -1) {
                throw new RobotConfigError("Robot config: legScale entries must be 1 or -1");
            }
        }
    }

    for (const key of ["legJoint1ToJoint2", "legJoint2ToJoint3", "legJoint3ToTip"]) {
        if (number(required(geometry, key, "geometry"), key) <= 0) {
            throw new RobotConfigError(`Robot config: ${key} must be positive`);
        }
    }
    config.legRootToJoint1 = number(geometry.legRootToJoint1 ?? 0, "legRootToJoint1");
    return config;
}

function parseGait(geometry: Json): Gait {
    const gait = required(geometry, "gait", "geometry");
    return {
        standby_posture: [...required(geometry, "standbyPosture", "geometry")] as [number, number],
        laydown_posture: [...required(geometry, "laydownPosture", "geometry")] as [number, number],
        walk_radius: number(required(gait, "walk_radius", "gait"), "walk_radius"),
        turn_radius: number(required(gait, "turn_radius", "gait"), "turn_radius"),
        fastwalk: {
            g_steps: FIXED_GAIT.fastwalk_g_steps,
            y_radius: number(required(gait, "fastwalk_y_radius", "gait"), "fastwalk_y_radius"),
            z_radius: number(required(gait, "fastwalk_z_radius", "gait"), "fastwalk_z_radius"),
            x_radius: number(required(gait, "fastwalk_x_radius", "gait"), "fastwalk_x_radius"),
        },
        standup_steps: FIXED_GAIT.standup_steps,
        rotate_x: { ...FIXED_GAIT.rotate_x },
        rotate_y: { ...FIXED_GAIT.rotate_y },
        rotate_z: { ...FIXED_GAIT.rotate_z },
        twist: { ...FIXED_GAIT.twist },
    };
}

/** The payload's {"version", "build"} block, or null for firmware that
 * predates reporting it. */
function parseFirmware(firmware: unknown, protocol: number): Firmware | null {
    if (!isObject(firmware) || typeof firmware.version !== "string") {
        return null;
    }
    return { version: firmware.version, build: String(firmware.build || ""), protocol };
}

function capitalize(text: string): string {
    return text ? text[0].toUpperCase() + text.slice(1).toLowerCase() : text;
}

/** Turn a GET /robot_config payload into the app's robot config. */
export function parseRobotConfig(
    payload: unknown,
    source: RobotConfig["source"] = "robot",
): RobotConfig {
    if (!isObject(payload)) {
        throw new RobotConfigError("Robot config is not a JSON object");
    }

    const protocol = required(payload, "protocol", "the payload");
    if (!Number.isInteger(protocol)) {
        throw new RobotConfigError("Robot config: protocol must be an integer");
    }
    if (protocol > SUPPORTED_PROTOCOL) {
        throw new RobotConfigError(
            `The robot speaks protocol ${protocol}, but this app only knows up to ` +
                `${SUPPORTED_PROTOCOL}. Update Hexapod Link.`,
        );
    }

    const geometry = required(payload, "geometry", "the payload");
    if (!isObject(geometry)) {
        throw new RobotConfigError("Robot config is missing 'legMountX' in geometry");
    }
    const name = String(payload.name || geometry.name || "robot");
    const label = String(geometry.label || capitalize(name));

    const delayMs = number(required(payload, "delay_ms", "the payload"), "delay_ms");
    if (delayMs <= 0) {
        throw new RobotConfigError("Robot config: delay_ms must be positive");
    }

    const servo = isObject(payload.servo) ? payload.servo : {};
    const servoMin = number(servo.min ?? geometry.servoMin ?? 102, "servo min");
    const servoMax = number(servo.max ?? geometry.servoMax ?? 512, "servo max");
    if (servoMax <= servoMin) {
        throw new RobotConfigError("Robot config: servo max must exceed servo min");
    }

    const speed: Record<string, number> = { ...DEFAULT_SPEED };
    for (const [k, v] of Object.entries(isObject(payload.speed) ? payload.speed : {})) {
        speed[k] = Math.trunc(number(v, `speed ${k}`));
    }
    if (!("current" in speed)) {
        speed.current = speed.default;
    }

    const commands = payload.commands || [...FIRMWARE_COMMANDS];
    if (!Array.isArray(commands) || !commands.every((c) => typeof c === "string")) {
        throw new RobotConfigError("Robot config: commands must be strings");
    }

    const jointLimits = { ...DEFAULT_JOINT_LIMITS, ...(geometry.jointLimits || {}) };

    return {
        name,
        label,
        ssid: String(payload.ssid || ""),
        protocol,
        firmware: parseFirmware(payload.firmware, protocol),
        source,
        delay_ms: delayMs,
        servo_min: servoMin,
        servo_max: servoMax,
        speed: speed as RobotConfig["speed"],
        commands: [...commands],
        config: parseGeometry(geometry),
        gait: parseGait(geometry),
        joint_limits: jointLimits,
        payload: structuredClone(payload),
    };
}

export const DEFAULT_CONFIG = parseRobotConfig(DEFAULT_PAYLOAD, "default");

// ----------------------------------------------------------------- helpers

export interface Dimensions {
    front: number;
    side: number;
    middle: number;
    coxia: number;
    femur: number;
    tibia: number;
    mount_angles?: number[];
}

export const DIMENSION_NAMES = ["front", "side", "middle", "coxia", "femur", "tibia"] as const;
export type DimensionName = (typeof DIMENSION_NAMES)[number];

/** Map a robot's geometry to the simulator's dimension format.
 *
 * `mountAngles` carries each leg's coxia axis azimuth. The simulator would
 * otherwise point every leg straight out from the cog, which is right for
 * Mochi and Macaroon but not for Nougat, whose corner legs are angled at 45
 * degrees while sitting at about 59. */
export function getSimulatorDimensions(robot: RobotConfig, mountAngles = true): Dimensions {
    const config = robot.config;
    const dimensions: Dimensions = {
        front: config.legMountX[0],
        side: config.legMountY[0],
        middle: config.legMountX[1],
        coxia: config.legJoint1ToJoint2,
        femur: config.legJoint2ToJoint3,
        tibia: config.legJoint3ToTip,
    };
    if (mountAngles) {
        dimensions.mount_angles = config.legMountAngle.map((a) => pyMod(a, 360));
    }
    return dimensions;
}

/** The robot's config with its body and legs measured as `dimensions`.
 *
 * The mounts move with front, side and middle, each leg keeping its own side
 * and mirroring; the legs take the new lengths and keep the angles they are
 * mounted at. Joint limits, gait and the rest are the robot's own. A
 * measurement that is missing or not positive keeps the robot's. */
export function withDimensions(
    robot: RobotConfig,
    dimensions: Partial<Record<DimensionName, unknown>> | null | undefined,
): RobotConfig {
    if (!isObject(dimensions)) {
        return robot;
    }
    const current = getSimulatorDimensions(robot, false);
    const measure = (name: DimensionName) => {
        const value = dimensions[name];
        return typeof value === "number" && value > 0 ? value : current[name];
    };
    const next = Object.fromEntries(DIMENSION_NAMES.map((n) => [n, measure(n)])) as Record<
        DimensionName,
        number
    >;
    if (DIMENSION_NAMES.every((n) => next[n] === current[n])) {
        return robot;
    }

    const rescaled = (value: number, old: number, newValue: number) =>
        old ? (value * newValue) / old : value;

    const config = structuredClone(robot.config);
    const xs = config.legMountX;
    const ys = config.legMountY;
    for (const leg of [0, 2, 3, 5]) {
        xs[leg] = rescaled(xs[leg], current.front, next.front);
        ys[leg] = rescaled(ys[leg], current.side, next.side);
    }
    for (const leg of [1, 4]) {
        xs[leg] = rescaled(xs[leg], current.middle, next.middle);
    }
    config.legJoint1ToJoint2 = next.coxia;
    config.legJoint2ToJoint3 = next.femur;
    config.legJoint3ToTip = next.tibia;
    return { ...robot, config };
}

/** +1 or -1 per leg: how the femur and tibia servos are mirrored (legScale). */
export function getLegSigns(robot: RobotConfig): number[] {
    return robot.config.legScale.map((row) => Math.trunc(row[1]));
}

/** Frame rate matching the robot's own LUT playback at a given speed. The
 * firmware stretches each LUT frame to DELAY_MS * 100 / speed_pct. */
export function getSequenceFps(robot: RobotConfig, speedPct = 100): number {
    return ((1000.0 / robot.delay_ms) * speedPct) / 100.0;
}

/** Mechanical travel limits in degrees. */
export function getJointLimits(robot: RobotConfig): JointLimits {
    return robot.joint_limits;
}

export function clampSpeed(robot: RobotConfig, pct: number): number {
    const speed = robot.speed;
    return Math.trunc(Math.min(Math.max(Math.trunc(pct), speed.min), speed.max));
}

/** The robot's command id for a simulator motion name, else null. The
 * simulator names motions with underscores ("walk_0"), the firmware without. */
export function commandId(robot: RobotConfig, motionName: string): number | null {
    const index = robot.commands.indexOf(motionName.replaceAll("_", ""));
    return index < 0 ? null : index;
}

/** One line naming the robot the app is modelling. */
export function describe(robot: RobotConfig): string {
    if (robot.source === "default") {
        return `${robot.label} (default) — connect a robot to load its config`;
    }
    const ssid = robot.ssid ? ` · ${robot.ssid}` : "";
    if (robot.source === "cache") {
        return `${robot.label}${ssid} (last connected)`;
    }
    return `${robot.label}${ssid}`;
}

/** One line naming the connected robot's firmware. */
export function describeFirmware(firmware: Firmware | null): string {
    if (!firmware) {
        return "Firmware version not reported";
    }
    const build = firmware.build ? ` (${firmware.build})` : "";
    return `Firmware ${firmware.version}${build} · protocol ${firmware.protocol}`;
}
