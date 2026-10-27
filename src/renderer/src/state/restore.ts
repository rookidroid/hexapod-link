// Opening the workspace as it was left when the app was last closed.
//
// The pose and the sequence being edited, which keyframe is selected, and the
// controls of the dock, the view and playback are kept with the preferences
// (main/storage.ts saveWorkspace) each time one changes, under the same names
// and in the same shapes the Python version of the app kept them, so a
// workspace left by it opens here too.
//
// A value that is not usable, from an older version or edited by hand, is
// dropped, and the control keeps its default. The pose and the sequence carry
// the robot they were made on, and the store starts afresh on another.

import * as kf from "../../../shared/keyframes";
import * as pl from "../../../shared/pose_layers";
import { DIMENSION_NAMES, type DimensionName } from "../../../shared/robot_config";

function number(value: unknown, low: number, high: number): number | null {
    return typeof value === "number" && Number.isFinite(value) && value >= low && value <= high
        ? value
        : null;
}

function finiteFeet(feet: unknown): boolean {
    return (
        Array.isArray(feet) &&
        feet.length === 6 &&
        feet.every(
            (f) => Array.isArray(f) && f.length === 3 && f.every((c) => Number.isFinite(Number(c))),
        )
    );
}

export interface SavedPose {
    robot: string;
    state: pl.PoseState;
    feet: number[][];
    seq: number;
    at?: { after: number; ms: number };
}

export function savedPose(store: unknown): SavedPose | null {
    if (typeof store !== "object" || store === null) return null;
    const s = store as Record<string, unknown>;
    if (typeof s.robot !== "string" || !pl.isState(s.state) || !finiteFeet(s.feet)) return null;
    const at = s.at as SavedPose["at"] | undefined;
    const atOk =
        at && typeof at === "object" && Number.isInteger(at.after) && typeof at.ms === "number";
    return {
        robot: s.robot,
        state: pl.makeState(s.state.body, s.state.offsets),
        feet: s.feet as number[][],
        seq: typeof s.seq === "number" ? s.seq : 0,
        ...(atOk ? { at } : {}),
    };
}

/** The keyframes store, its keyframes as a saved file would have them. */
export function savedKeyframes(store: unknown): { robot: string; keyframes: kf.Keyframe[] } | null {
    if (typeof store !== "object" || store === null) return null;
    const s = store as Record<string, unknown>;
    if (typeof s.robot !== "string") return null;
    try {
        const keyframes = kf.load(
            {
                format: kf.FILE_FORMAT,
                version: kf.FILE_VERSION,
                robot: s.robot,
                keyframes: s.keyframes,
            },
            { name: s.robot },
        );
        return { robot: s.robot, keyframes };
    } catch {
        return null;
    }
}

const choice =
    <T extends string>(...options: T[]) =>
    (value: unknown): T | null =>
        options.includes(value as T) ? (value as T) : null;

const text = (most: number) => (value: unknown) =>
    typeof value === "string" && value.length <= most ? value : null;

/** What is kept, by the name it is kept under, and what a usable value is. */
const FIELDS = {
    pose: savedPose,
    keyframes: savedKeyframes,
    selected: (v: unknown) => (Number.isInteger(v) && (v as number) >= 0 ? (v as number) : null),
    body_mode: choice("translate", "rotate"),
    gait_source: choice("builtin", "mine"),
    gait_name: text(40),
    duration: (v: unknown) => number(v, kf.MIN_DURATION_MS, kf.MAX_DURATION_MS),
    ease: choice("ease", "linear"),
    speed: (v: unknown) => number(v, 25, 200),
    loop: (v: unknown) =>
        Array.isArray(v) && v.every((item) => item === "loop") ? (v as string[]) : null,
    robot_ip: text(253),
    max_step: (v: unknown) => number(v, 1, 1000),
    drive_speed: (v: unknown) => number(v, 1, 1000),
};

export type Saved = { [K in keyof typeof FIELDS]?: NonNullable<ReturnType<(typeof FIELDS)[K]>> };

/** The usable saved values, by name; one missing or unusable is left out. */
export function savedValues(saved: Record<string, unknown>): Saved {
    const values: Record<string, unknown> = {};
    for (const [name, check] of Object.entries(FIELDS)) {
        if (name in saved) {
            const value = (check as (v: unknown) => unknown)(saved[name]);
            if (value !== null) values[name] = value;
        }
    }
    return values as Saved;
}

/** The Dimensions panel's measurements as they were left on this robot, or
 * null. */
export function savedDimensions(
    saved: Record<string, unknown>,
    robotName: string,
): Record<DimensionName, number> | null {
    const d = saved.dimensions as { robot?: unknown; values?: Record<string, unknown> } | undefined;
    if (
        !d ||
        typeof d !== "object" ||
        d.robot !== robotName ||
        typeof d.values !== "object" ||
        !d.values
    ) {
        return null;
    }
    const out: Partial<Record<DimensionName, number>> = {};
    for (const name of DIMENSION_NAMES) {
        const value = number(d.values[name], 0, 10_000);
        if (value === null) return null;
        out[name] = value;
    }
    return out as Record<DimensionName, number>;
}
