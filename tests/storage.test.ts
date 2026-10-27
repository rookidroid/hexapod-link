// What is kept on disk: the preferences, and gaits of one's own -- each a
// keyframe file, which loads back as it was, and only for the robot it was
// made on. Every test works in a folder of its own.
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import * as storage from "../src/main/storage";
import { gaitKeyframes } from "../src/shared/gait_keyframes";
import * as kf from "../src/shared/keyframes";
import type { RobotConfig } from "../src/shared/robot_config";
import { GAITS_ENV, PREFERENCES_ENV } from "../src/shared/settings";
import { ROBOT_CONFIGS } from "./golden";

const NOUGAT = ROBOT_CONFIGS.nougat;
const MOCHI = ROBOT_CONFIGS.mochi;
let folder = "";
let prefs = "";
let gaits = "";

beforeEach(() => {
    folder = mkdtempSync(join(tmpdir(), "hexapod-link-tests-"));
    prefs = join(folder, "preferences.json");
    gaits = join(folder, "gaits");
    process.env[PREFERENCES_ENV] = prefs;
    process.env[GAITS_ENV] = gaits;
});

function frames(robot: RobotConfig, count = 3): kf.Keyframe[] {
    return Array.from({ length: count }, (_, i) =>
        kf.makeKeyframe(
            kf.standbyFeet(robot).map(([x, y, z]) => [x, y, z + 10 * i]),
            400 + 100 * i,
            null,
            i % 2 === 0,
        ),
    );
}

describe("preferences", () => {
    it("defaults to dark, and round trips the theme keeping the rest", () => {
        expect(storage.loadTheme()).toBe("dark");
        expect(storage.saveTheme("dark")).toBe(true);
        expect(storage.preferencesPath()).toBe(prefs);
        expect(JSON.parse(readFileSync(prefs, "utf-8"))).toEqual({ theme: "dark" });
        storage.saveTheme("light");
        expect(storage.loadTheme()).toBe("light");
        storage.savePreference("other", 42);
        storage.saveTheme("dark");
        expect(JSON.parse(readFileSync(prefs, "utf-8"))).toEqual({ theme: "dark", other: 42 });
    });

    it.each(["not json", "[1, 2]", '{"theme": "purple"}', '{"theme": null}'])(
        "falls back to dark for %s",
        (contents) => {
            writeFileSync(prefs, contents);
            expect(storage.loadTheme()).toBe("dark");
        },
    );

    it("refuses an unknown theme", () => {
        expect(() => storage.saveTheme("purple" as never)).toThrow();
        expect(existsSync(prefs)).toBe(false);
    });

    it("saves layout sizes one at a time", () => {
        expect(storage.loadLayout()).toEqual({ dock_h: null, lib_w: null });
        storage.saveTheme("dark");
        storage.saveLayout({ lib_w: 412.4, n: 123 });
        storage.saveLayout({ dock_h: 260 });
        expect(storage.loadLayout()).toEqual({ lib_w: 412, dock_h: 260 });
        expect(storage.loadTheme()).toBe("dark");
        storage.saveLayout({ lib_w: null });
        expect(storage.loadLayout()).toEqual({ dock_h: 260, lib_w: null });
    });

    it.each([null, "300", true, -5, 50, 10_000, Number.NaN])("does not keep size %s", (value) => {
        storage.saveLayout({ dock_h: 300 });
        storage.saveLayout({ dock_h: value });
        expect(storage.loadLayout().dock_h).toBeNull();
    });

    it.each([
        '{"layout": [1]}',
        '{"layout": {"lib_w": "wide", "dock_h": {}}}',
        '{"layout": {"panel_w": 400}}',
    ])("ignores an unusable layout %s", (contents) => {
        writeFileSync(prefs, contents);
        expect(storage.loadLayout()).toEqual({ dock_h: null, lib_w: null });
    });

    it("keeps panels folded until opened, one at a time", () => {
        const folded = { pose: false, controller: false, dimensions: false };
        expect(storage.loadPanels()).toEqual(folded);
        storage.savePanels({ pose: true, n: 123 });
        storage.savePanels({ controller: true });
        expect(storage.loadPanels()).toEqual({ ...folded, pose: true, controller: true });
        storage.savePanels({ pose: false });
        expect(storage.loadPanels()).toEqual({ ...folded, controller: true });
        writeFileSync(prefs, '{"panels": {"pose": "yes", "controller": 1, "other": true}}');
        expect(storage.loadPanels()).toEqual(folded);
    });

    it("keeps the workspace and the window", () => {
        storage.saveWorkspace({ speed: 80 });
        storage.saveWorkspace({ loop: ["loop"] });
        expect(storage.loadWorkspace()).toEqual({ speed: 80, loop: ["loop"] });
        storage.saveWindow({ x: 10, y: 20, width: 1200, height: 800, maximized: true });
        expect(storage.loadWindow()).toEqual({
            x: 10,
            y: 20,
            width: 1200,
            height: 800,
            maximized: true,
        });
        writeFileSync(prefs, '{"window": {"x": 5, "width": 50}}');
        expect(storage.loadWindow()).toEqual({
            x: null,
            y: null,
            width: null,
            height: null,
            maximized: false,
        });
    });
});

describe("gait library", () => {
    it("lists nothing without a folder", () => {
        expect(storage.gaitsDir()).toBe(gaits);
        expect(storage.listGaits(NOUGAT)).toEqual([]);
    });

    it("lists a saved gait and loads it back", () => {
        const f = frames(NOUGAT);
        const id = storage.saveGait("  Wave   hello ", f, NOUGAT);
        expect(storage.listGaits(NOUGAT)).toEqual([
            { id, name: "Wave hello", count: 3, duration_ms: kf.sequenceDurationMs(f) },
        ]);
        const loaded = storage.loadGait(id, NOUGAT);
        expect(loaded.map((k) => k.duration_ms)).toEqual([400, 500, 600]);
        expect(loaded.map(kf.eases)).toEqual([true, false, true]);
        expect(loaded.map((k) => k.feet)).toEqual(f.map((k) => k.feet));
    });

    it("writes a keyframe file", () => {
        const id = storage.saveGait("Twist", gaitKeyframes("twist", NOUGAT), NOUGAT);
        const text = readFileSync(join(gaits, `${id}.json`), "utf-8");
        expect(JSON.parse(text).name).toBe("Twist");
        expect(kf.load(text, NOUGAT).length).toBe(gaitKeyframes("twist", NOUGAT).length);
    });

    it("replaces a gait saved under the same name, and lists by name", () => {
        const first = storage.saveGait("Dance", frames(NOUGAT, 2), NOUGAT);
        expect(storage.saveGait("dance", frames(NOUGAT, 4), NOUGAT)).toBe(first);
        expect(storage.listGaits(NOUGAT).map((g) => g.count)).toEqual([4]);
        for (const name of ["walk b", "Alpha", "zig"])
            storage.saveGait(name, frames(NOUGAT), NOUGAT);
        expect(storage.listGaits(NOUGAT).map((g) => g.name)).toEqual([
            "Alpha",
            "dance",
            "walk b",
            "zig",
        ]);
    });

    it("keeps another robot's gaits to that robot", () => {
        const id = storage.saveGait("Mine", frames(NOUGAT), NOUGAT);
        storage.saveGait("Mochi's", frames(MOCHI), MOCHI);
        expect(storage.listGaits(NOUGAT).map((g) => g.name)).toEqual(["Mine"]);
        expect(storage.listGaits(MOCHI).map((g) => g.name)).toEqual(["Mochi's"]);
        expect(() => storage.loadGait(id, MOCHI)).toThrow(kf.KeyframeFileError);
    });

    it("leaves broken files out, and lists a keyframe file dropped in", () => {
        storage.saveGait("Good", frames(NOUGAT), NOUGAT);
        writeFileSync(join(gaits, "nougat--broken.json"), "{not json");
        writeFileSync(join(gaits, "nougat--other.json"), '{"format": "x"}');
        expect(storage.listGaits(NOUGAT).map((g) => g.name)).toEqual(["Good"]);
        writeFileSync(join(gaits, "Nougat_keyframes.json"), kf.dump(frames(NOUGAT), NOUGAT));
        const dropped = storage.listGaits(NOUGAT).find((g) => g.name === "Nougat_keyframes")!;
        expect(storage.loadGait(dropped.id, NOUGAT).length).toBe(3);
    });

    it("deletes a gait", () => {
        const id = storage.saveGait("Gone", frames(NOUGAT), NOUGAT);
        expect(storage.deleteGait(id)).toBe(true);
        expect(storage.listGaits(NOUGAT)).toEqual([]);
        expect(storage.deleteGait(id)).toBe(false);
        expect(() => storage.loadGait(id, NOUGAT)).toThrow(kf.KeyframeFileError);
    });

    it.each(["../preferences", "..", "a/b", "a\\b", ".hidden", "", null])(
        "keeps id %s inside the folder",
        (id) => {
            mkdirSync(gaits, { recursive: true });
            expect(() => storage.loadGait(id as string, NOUGAT)).toThrow(kf.KeyframeFileError);
            expect(storage.deleteGait(id as string)).toBe(false);
        },
    );

    it("needs a name and keyframes, and cuts a long name short", () => {
        expect(() => storage.saveGait("   ", frames(NOUGAT), NOUGAT)).toThrow();
        expect(() => storage.saveGait(null as never, frames(NOUGAT), NOUGAT)).toThrow();
        expect(() => storage.saveGait("Empty", [], NOUGAT)).toThrow();
        expect(existsSync(gaits)).toBe(false);
        storage.saveGait("x".repeat(100), frames(NOUGAT), NOUGAT);
        expect(storage.listGaits(NOUGAT)[0].name).toBe("x".repeat(storage.MAX_NAME_LENGTH));
    });
});
