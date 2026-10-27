// The Python app's own results, recorded by tools/dump_golden.py before the
// port, for the robots in tests/fixtures/robot_config.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect } from "vitest";
import { parseRobotConfig, type RobotConfig } from "../src/shared/robot_config";

export const ROBOT_NAMES = ["nougat", "mochi", "macaroon"] as const;
const FIXTURES = join(__dirname, "fixtures");

export function loadPayload(name: string): Record<string, unknown> {
    return JSON.parse(readFileSync(join(FIXTURES, "robot_config", `${name}.json`), "utf-8"));
}

export function robotConfig(name: string): RobotConfig {
    return parseRobotConfig(loadPayload(name));
}

export const ROBOT_CONFIGS = Object.fromEntries(
    ROBOT_NAMES.map((name) => [name, robotConfig(name)]),
) as Record<(typeof ROBOT_NAMES)[number], RobotConfig>;

const cache = new Map<string, any>();
export function golden(name: string): any {
    if (!cache.has(name)) {
        cache.set(
            name,
            JSON.parse(readFileSync(join(FIXTURES, "golden", `${name}.json`), "utf-8")),
        );
    }
    return cache.get(name);
}

/** Every number in `actual` within `tol` of the one in `expected`; NaN is
 * recorded as null. Structure and everything else equal. */
export function expectClose(actual: unknown, expected: unknown, tol = 1e-6, path = "$"): void {
    if (typeof expected === "number" || expected === null) {
        if (expected === null && (actual === null || actual === undefined)) {
            return;
        }
        if (expected === null) {
            expect(Number.isNaN(actual), `${path}: ${actual} is not NaN`).toBe(true);
            return;
        }
        expect(typeof actual, `${path}`).toBe("number");
        const diff = Math.abs((actual as number) - expected);
        if (!(diff <= tol)) {
            expect.fail(`${path}: ${actual} != ${expected} (off by ${diff})`);
        }
        return;
    }
    if (Array.isArray(expected)) {
        expect(Array.isArray(actual), `${path} is an array`).toBe(true);
        expect((actual as unknown[]).length, `${path}.length`).toBe(expected.length);
        expected.forEach((e, i) => expectClose((actual as unknown[])[i], e, tol, `${path}[${i}]`));
        return;
    }
    if (typeof expected === "object") {
        expect(typeof actual, `${path} is an object`).toBe("object");
        const keys = Object.keys(expected as object);
        expect(Object.keys(actual as object).sort(), `${path} keys`).toEqual([...keys].sort());
        for (const key of keys) {
            expectClose(
                (actual as Record<string, unknown>)[key],
                (expected as Record<string, unknown>)[key],
                tol,
                `${path}.${key}`,
            );
        }
        return;
    }
    expect(actual, path).toEqual(expected);
}

export const poseList = (pose: { coxia: number; femur: number; tibia: number }[]) =>
    pose.map((leg) => [leg.coxia, leg.femur, leg.tibia]);

import { DEFAULT_CONFIG } from "../src/shared/robot_config";

/** The fixture robots and the default, as the Python tests ran them. */
export const ROBOTS: [string, RobotConfig][] = [
    ...ROBOT_NAMES.map((name) => [name, ROBOT_CONFIGS[name]] as [string, RobotConfig]),
    ["default", DEFAULT_CONFIG],
];

/** numpy.testing.assert_allclose(actual, expected, atol), shapes included. */
export function allClose(actual: unknown, expected: unknown, atol: number, where = ""): void {
    expectClose(actual, expected, atol, where || "$");
}

/** Every number in a nested array. */
export function numbers(value: unknown): number[] {
    if (Array.isArray(value)) return value.flatMap(numbers);
    if (typeof value === "number") return [value];
    if (value && typeof value === "object") return Object.values(value).flatMap(numbers);
    return [];
}
