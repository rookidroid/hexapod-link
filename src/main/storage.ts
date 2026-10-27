// What the app keeps on disk between launches, under ~/.hexapod-link/:
//
//   preferences.json   the theme, the workspace's sizes, which overlays are
//                      open, the window's place, and the workspace as it was
//                      closed (HEXAPOD_LINK_PREFERENCES moves it)
//   robot_config.json  the last robot's config, so the app still models it
//                      when started offline (HEXAPOD_LINK_CONFIG_CACHE)
//   gaits/             gaits of one's own, one keyframe file each
//                      (HEXAPOD_LINK_GAITS)
//
// All best effort: a missing or broken file just means the defaults. Writes go
// to a file aside and are swapped in, so a reader never sees half a file.

import {
    mkdirSync,
    readdirSync,
    readFileSync,
    renameSync,
    unlinkSync,
    writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import * as kf from "../shared/keyframes";
import { DEFAULT_CONFIG, parseRobotConfig, type RobotConfig } from "../shared/robot_config";
import {
    DATA_DIR_NAME,
    GAITS_ENV,
    PREFERENCES_ENV,
    ROBOT_CONFIG_CACHE_ENV,
} from "../shared/settings";

function dataPath(env: string, name: string): string {
    return process.env[env] || join(homedir(), DATA_DIR_NAME, name);
}

export const preferencesPath = () => dataPath(PREFERENCES_ENV, "preferences.json");
export const cachePath = () => dataPath(ROBOT_CONFIG_CACHE_ENV, "robot_config.json");
export const gaitsDir = () => dataPath(GAITS_ENV, "gaits");

function writeAtomically(path: string, text: string): void {
    mkdirSync(dirname(path), { recursive: true });
    const partial = `${path}.tmp`;
    writeFileSync(partial, text, "utf-8");
    renameSync(partial, path);
}

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

// ............................................................ preferences

/** The saved preferences, empty if there are none. */
export function loadPreferences(): Record<string, unknown> {
    const path = preferencesPath();
    let text: string;
    try {
        text = readFileSync(path, "utf-8");
    } catch {
        return {};
    }
    try {
        const preferences = JSON.parse(text);
        return isObject(preferences) ? preferences : {};
    } catch (error) {
        console.warn(`Ignoring the preferences at ${path}: ${(error as Error).message}`);
        return {};
    }
}

/** Store one preference, keeping the others. Best effort. */
export function savePreference(key: string, value: unknown): boolean {
    const path = preferencesPath();
    const preferences = loadPreferences();
    preferences[key] = value;
    try {
        writeAtomically(path, JSON.stringify(preferences, null, 2));
        return true;
    } catch (error) {
        console.warn(`Could not save the preferences to ${path}: ${(error as Error).message}`);
        return false;
    }
}

export const THEMES = ["light", "dark"] as const;
export type Theme = (typeof THEMES)[number];
export const DEFAULT_THEME: Theme = "dark";

export function loadTheme(): Theme {
    const theme = loadPreferences().theme;
    return THEMES.includes(theme as Theme) ? (theme as Theme) : DEFAULT_THEME;
}

export function saveTheme(theme: Theme): boolean {
    if (!THEMES.includes(theme)) {
        throw new Error(`unknown theme: ${theme}`);
    }
    return savePreference("theme", theme);
}

// The workspace's sizes, set by dragging its splitters: the height of the dock
// and the width of the Gaits library, in CSS pixels. null for one never
// dragged, which leaves it to the stylesheet.
export const LAYOUT_SIZES = ["dock_h", "lib_w"] as const;
export type LayoutSizes = Record<(typeof LAYOUT_SIZES)[number], number | null>;
const LAYOUT_MIN_PX = 100;
const LAYOUT_MAX_PX = 4000;

function layoutSize(value: unknown): number | null {
    if (typeof value !== "number" || !(value >= LAYOUT_MIN_PX && value <= LAYOUT_MAX_PX)) {
        return null;
    }
    return Math.round(value);
}

export function loadLayout(): LayoutSizes {
    const saved = loadPreferences().layout;
    const s = isObject(saved) ? saved : {};
    return { dock_h: layoutSize(s.dock_h), lib_w: layoutSize(s.lib_w) };
}

/** Store the sizes given, keeping a saved one not among them; one that is not
 * a size in range clears it. */
export function saveLayout(sizes: Partial<Record<string, unknown>>): boolean {
    const layout = loadLayout();
    for (const key of LAYOUT_SIZES) {
        if (key in sizes) {
            layout[key] = layoutSize(sizes[key]);
        }
    }
    return savePreference("layout", layout);
}

// The overlays on the view that fold away: whether each was left open. They
// all start folded, so the view starts clear.
export const PANELS = ["pose", "controller", "dimensions"] as const;
export type Panels = Record<(typeof PANELS)[number], boolean>;

export function loadPanels(): Panels {
    const saved = loadPreferences().panels;
    const s = isObject(saved) ? saved : {};
    return {
        pose: s.pose === true,
        controller: s.controller === true,
        dimensions: s.dimensions === true,
    };
}

export function savePanels(states: Partial<Record<string, unknown>>): boolean {
    const panels = loadPanels();
    for (const key of PANELS) {
        if (key in states) {
            panels[key] = states[key] === true;
        }
    }
    return savePreference("panels", panels);
}

/** What the workspace was left showing, by name; each value is checked as it
 * is put back (renderer/src/state/restore.ts), not here. */
export function loadWorkspace(): Record<string, unknown> {
    const saved = loadPreferences().workspace;
    return isObject(saved) ? saved : {};
}

/** Store the values given, keeping a saved one not among them. */
export function saveWorkspace(values: Record<string, unknown>): boolean {
    return savePreference("workspace", { ...loadWorkspace(), ...values });
}

// The window's size and place on the desktop: the size it had out of
// maximized, and whether it was left maximized. null for one never saved.
const WINDOW_MIN_PX = 100;
const WINDOW_MAX_PX = 20000;
// Screens to the left of or above the primary one have negative coordinates.
const WINDOW_MAX_OFFSET_PX = 50000;

export interface SavedWindow {
    x: number | null;
    y: number | null;
    width: number | null;
    height: number | null;
    maximized: boolean;
}

function wholeNumber(value: unknown, low: number, high: number): number | null {
    if (typeof value !== "number" || !(value >= low && value <= high)) {
        return null;
    }
    return Math.round(value);
}

export function loadWindow(): SavedWindow {
    const saved = loadPreferences().window;
    const s = isObject(saved) ? saved : {};
    let x = wholeNumber(s.x, -WINDOW_MAX_OFFSET_PX, WINDOW_MAX_OFFSET_PX);
    let y = wholeNumber(s.y, -WINDOW_MAX_OFFSET_PX, WINDOW_MAX_OFFSET_PX);
    // A place without both its x and its y is no place.
    if (x === null || y === null) {
        x = y = null;
    }
    return {
        x,
        y,
        width: wholeNumber(s.width, WINDOW_MIN_PX, WINDOW_MAX_PX),
        height: wholeNumber(s.height, WINDOW_MIN_PX, WINDOW_MAX_PX),
        maximized: s.maximized === true,
    };
}

export function saveWindow(window: SavedWindow): boolean {
    return savePreference("window", { ...window, maximized: window.maximized === true });
}

// ............................................................ robot config

/** Remember a robot's config for the next offline start. Best effort. */
export function saveCachedConfig(robot: RobotConfig): boolean {
    const path = cachePath();
    try {
        writeAtomically(path, JSON.stringify(robot.payload, null, 2));
        return true;
    } catch (error) {
        console.warn(`Could not cache the robot config to ${path}: ${(error as Error).message}`);
        return false;
    }
}

/** The last robot's config, or null if there is none (or it is unreadable). */
export function loadCachedConfig(): RobotConfig | null {
    const path = cachePath();
    let text: string;
    try {
        text = readFileSync(path, "utf-8");
    } catch {
        return null;
    }
    try {
        return parseRobotConfig(JSON.parse(text), "cache");
    } catch (error) {
        console.warn(`Ignoring the cached robot config at ${path}: ${(error as Error).message}`);
        return null;
    }
}

/** The config to model before any robot connects: cached, else Nougat's. */
export function loadStartupConfig(): RobotConfig {
    return loadCachedConfig() ?? DEFAULT_CONFIG;
}

// ............................................................ gait library
//
// Gaits of one's own: a whole sequence saved under a name, to be put into
// another sequence the way one of the robot's gaits is. Each is a keyframe
// file, as Save… writes it, with its name added. So a gait's file loads with
// Load… too, and a keyframe file dropped in the folder shows up as a gait.
// Foot positions only fit the robot they were placed on, so a gait belongs to
// one robot: the others' are not listed, and are refused if asked for.

export const MAX_NAME_LENGTH = 40;

// A gait's id is a file name in the folder, without a path separator or a
// leading dot, so it cannot point anywhere else.
const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.-]*$/;

export interface GaitSummary {
    id: string;
    name: string;
    count: number;
    duration_ms: number;
}

/** The name a gait is kept under: trimmed, its spaces collapsed, and not too
 * long. Throws for one with nothing in it. */
export function cleanName(name: unknown): string {
    const cleaned = String(name ?? "")
        .split(/\s+/)
        .filter(Boolean)
        .join(" ")
        .slice(0, MAX_NAME_LENGTH)
        .trim();
    if (!cleaned) {
        throw new Error("Give the gait a name.");
    }
    return cleaned;
}

const slug = (text: string) =>
    text
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");

/** The gait's id, its file's name without the .json: the robot's name and
 * the gait's. A gait saved under the name of one already there replaces it. */
export function gaitId(name: string, robot: { name: string }): string {
    return `${slug(String(robot.name))}--${slug(cleanName(name)) || "gait"}`;
}

function gaitPath(id: unknown): string {
    if (typeof id !== "string" || !ID_PATTERN.test(id)) {
        throw new kf.KeyframeFileError("No such gait.");
    }
    return join(gaitsDir(), `${id}.json`);
}

function readGait(path: string, stem: string, robot: { name: string }): [string, kf.Keyframe[]] {
    const text = readFileSync(path, "utf-8");
    const keyframes = kf.load(text, robot);
    const name = JSON.parse(text).name;
    return [typeof name === "string" && name.trim() ? name : stem, keyframes];
}

/** This robot's gaits, by name. */
export function listGaits(robot: { name: string }): GaitSummary[] {
    let files: string[];
    try {
        files = readdirSync(gaitsDir())
            .filter((f) => f.endsWith(".json"))
            .sort();
    } catch {
        return [];
    }
    const gaits: GaitSummary[] = [];
    for (const file of files) {
        const stem = file.slice(0, -".json".length);
        if (!ID_PATTERN.test(stem)) {
            continue;
        }
        try {
            const [name, keyframes] = readGait(join(gaitsDir(), file), stem, robot);
            if (keyframes.length) {
                gaits.push({
                    id: stem,
                    name,
                    count: keyframes.length,
                    duration_ms: kf.sequenceDurationMs(keyframes),
                });
            }
        } catch {
            // Not a gait of this robot, or unreadable: left out of the list.
        }
    }
    return gaits.sort((a, b) => {
        const byName = a.name.toLowerCase().localeCompare(b.name.toLowerCase());
        return byName || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
    });
}

/** A gait's keyframes. Throws KeyframeFileError for one that is not there or
 * not this robot's. */
export function loadGait(id: string, robot: { name: string }): kf.Keyframe[] {
    const path = gaitPath(id);
    try {
        return readGait(path, id, robot)[1];
    } catch (error) {
        if ((error as NodeJS.ErrnoException).code === "ENOENT") {
            throw new kf.KeyframeFileError("That gait is not there any more.");
        }
        if (error instanceof kf.KeyframeFileError) {
            throw error;
        }
        throw new kf.KeyframeFileError(`Could not read the gait: ${(error as Error).message}`);
    }
}

/** Keep the keyframes as a gait, replacing one of the same name; its id. */
export function saveGait(name: string, keyframes: kf.Keyframe[], robot: { name: string }): string {
    const cleaned = cleanName(name);
    if (!keyframes.length) {
        throw new Error("Build a sequence first: there is nothing to save.");
    }
    const document = { ...kf.dumpDocument(keyframes, robot), name: cleaned };
    const id = gaitId(cleaned, robot);
    writeAtomically(gaitPath(id), JSON.stringify(document, null, 2));
    return id;
}

/** Remove a gait; whether there was one to remove. */
export function deleteGait(id: string): boolean {
    try {
        unlinkSync(gaitPath(id));
        return true;
    } catch {
        return false;
    }
}
