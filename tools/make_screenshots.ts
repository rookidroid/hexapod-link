// Capture the README's screenshots and animations.
//
//     npm run screenshots              # all of them
//     npm run screenshots -- app pose  # only those
//
// Builds the app, connects it to a stand-in robot (tools/fake_robot.ts) so that
// nothing in it is greyed out, and drives it the way a person would -- picking
// the body, adding gaits to the sequence, playing it -- taking a picture at
// each step. What it writes to docs/images/:
//
//     app         app.png                 the whole window
//                 controller.png          the controller, cut out of it
//     walk        walk.gif                a walk cycle, in the 3D view alone
//     pose        pose.gif                posing the body and a foot
//     sequence    sequence.gif            building a sequence and playing it
//
// All in the dark theme (THEME). They are therefore always of the current
// UI: rerun this after a theme or
// layout change rather than editing the images by hand. The stand-in robot
// listens on the robot's UDP port, so no real robot session can be running on
// this machine at the same time. The preferences, robot cache and gaits of this
// machine are neither read nor written. Without a display, run it under
// xvfb-run.

import { mkdirSync, mkdtempSync, rmSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import gifenc from "gifenc";
import { _electron, type ElectronApplication, type Page } from "playwright-core";
import sharp, { type Sharp } from "sharp";
import { FakeRobot, UDP_PORT } from "./fake_robot.ts";

const { GIFEncoder, quantize, applyPalette } = gifenc;

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT_DIR = join(ROOT, "docs", "images");
const electronPath = createRequire(import.meta.url)("electron") as unknown as string;

// Captured at 2x and downsampled, which is what makes text in the shots crisp
// on the ~900 px column GitHub renders a README into.
const SCALE = 2;
// The app is one screen that never scrolls: the window is the picture. This is
// the size the desktop app opens at.
const APP_WINDOW: [number, number] = [1440, 900];
const APP_WIDTH = 1600;
// The animations are of a smaller window, so that what is in them is still
// readable at the width a README shows them.
const POSE_WINDOW: [number, number] = [1120, 860];
const SEQUENCE_WINDOW: [number, number] = [1200, 720];
const GIF_WIDTH = 840;
const WALK_WIDTH = 760;

// The theme every shot is taken in.
const THEME = "dark";

// What the whole-window shot shows instead of the neutral start-up pose: one
// foot lifted, under a body shifted and tilted off centre, all well within
// reach, as the second keyframe of a sequence that goes on into a gait.
const POSED_BODY = {
    percent_x: 0.15,
    percent_y: -0.1,
    percent_z: 0.2,
    rot_x: 7.5,
    rot_y: -6.0,
    rot_z: 6.0,
};
// The leg whose foot is lifted (Right Leg 1), and how far: across, forward, up.
const POSED_LEG = 0;
const POSED_FOOT = [15, 20, 35];
const POSED_GAIT = "twist";

// The animated hero on the README: one cycle of this gait, looped, at a
// quarter speed -- a step in a third of a second is a blur at 25 frames a
// second.
const WALK_GAIT = "walk_0";
const WALK_SPEED_PCT = 25;
const WALK_FRAME_MS = 40;
// The foot lifted in the animation of posing: Right Leg 3's, nearest the camera.
const POSE_GIF_LEG = "right-back";
// What the animation of a sequence puts into it, from the robot's gaits.
const SEQUENCE_GAITS = ["walk_0", "turn_left", "twist"];
// How long a frame of the other animations is shown, in ms, unless held longer.
const STEP_FRAME_MS = 80;
// How long the mark that shows where a click lands is up before the click.
const CLICK_MS = 450;

type Box = { x: number; y: number; width: number; height: number };

// ................................
// The app, as the shots start from it
// ................................

class Shooter {
    private app: ElectronApplication | null = null;
    page!: Page;
    private scratch = mkdtempSync(join(tmpdir(), "hexapod-link-shots-"));
    private robot: FakeRobot;

    constructor(robot: FakeRobot) {
        this.robot = robot;
    }

    /** A fresh window of the size given, connected to the stand-in robot,
     * with the overlays named in `panels` open. */
    async open(window: [number, number], panels: string[] = []): Promise<Page> {
        await this.close();
        const preferences = {
            theme: THEME,
            panels: Object.fromEntries(
                ["pose", "controller", "dimensions"].map((k) => [k, panels.includes(k)]),
            ),
            window: { x: 0, y: 0, width: window[0], height: window[1], maximized: false },
        };
        writeFileSync(join(this.scratch, "preferences.json"), JSON.stringify(preferences));
        rmSync(join(this.scratch, "robot_config.json"), { force: true });
        this.app = await _electron.launch({
            executablePath: electronPath,
            args: [
                ROOT,
                "--no-sandbox",
                `--force-device-scale-factor=${SCALE}`,
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
            ],
            env: {
                ...process.env,
                HEXAPOD_LINK_PREFERENCES: join(this.scratch, "preferences.json"),
                HEXAPOD_LINK_CONFIG_CACHE: join(this.scratch, "robot_config.json"),
                HEXAPOD_LINK_GAITS: join(this.scratch, "gaits"),
            },
        });
        this.page = await this.app.firstWindow();
        await this.app.evaluate(({ BrowserWindow }, [w, h]) => {
            BrowserWindow.getAllWindows()[0].setContentSize(w, h);
        }, window);
        await this.page.waitForSelector(".hexapod-view canvas");
        await this.run(`(async () => {
            const { store } = window.hexapodApp;
            store.getState().set({ robotIp: ${JSON.stringify(this.robot.address)} });
            await store.getState().toggleConnection();
            // The stand-in is on this machine; the shots show the address a robot has.
            store.getState().set({ robotIp: "192.168.4.1" });
        })()`);
        await this.drawn();
        return this.page;
    }

    async close(): Promise<void> {
        await this.app?.close();
        this.app = null;
    }

    async dispose(): Promise<void> {
        await this.close();
        rmSync(this.scratch, { recursive: true, force: true });
    }

    run<T = unknown>(script: string): Promise<T> {
        return this.page.evaluate(script) as Promise<T>;
    }

    /** Call one of the store's actions, as using its control does. */
    async act(action: string, ...args: unknown[]): Promise<void> {
        await this.run(
            `Promise.resolve(window.hexapodApp.store.getState()[${JSON.stringify(action)}](...${JSON.stringify(args)}))`,
        );
        await this.drawn();
    }

    /** Pick the body ("body") or a leg's foot (its id) up in the view, or let
     * go (null), as clicking it there does. */
    async pick(what: string | number | null): Promise<void> {
        await this.run(`window.hexapodApp.view.select("view-pose", ${JSON.stringify(what)})`);
        await this.page.waitForTimeout(50);
        await this.drawn();
    }

    /** Wait until what was just done has been drawn. */
    async drawn(): Promise<void> {
        await this.run(`new Promise((resolve) => {
            const done = () => resolve(true);
            requestAnimationFrame(() => requestAnimationFrame(done));
            setTimeout(done, 400);
        })`);
    }

    async click(selector: string): Promise<void> {
        await this.page.locator(selector).first().click();
        await this.drawn();
    }

    /** Ring an element, to show where the next click lands: a shot has no
     * mouse pointer in it. With none given, take the ring away. */
    async mark(selector: string | null): Promise<void> {
        await this.run(`(() => {
            document.getElementById("shot-mark")?.remove();
            const selector = ${JSON.stringify(selector)};
            if (!selector) return;
            const element = document.querySelector(selector);
            element.scrollIntoView({ block: "nearest" });
            const box = element.getBoundingClientRect();
            const ring = document.createElement("div");
            ring.id = "shot-mark";
            ring.style.cssText = "position: fixed; width: 30px; height: 30px; z-index: 99999;"
                + "border-radius: 50%; border: 3px solid #f7c600; box-sizing: border-box;"
                + "background: rgba(247, 198, 0, 0.3); pointer-events: none;"
                + "left: " + (box.left + box.width / 2 - 15) + "px;"
                + "top: " + (box.top + box.height / 2 - 15) + "px;";
            document.body.appendChild(ring);
        })()`);
        await this.drawn();
    }

    /** Add a rule or two to the page, to leave something out of a shot. */
    async style(css: string): Promise<void> {
        await this.page.addStyleTag({ content: css });
        await this.drawn();
    }

    async box(selector: string): Promise<Box> {
        const box = await this.page.locator(selector).first().boundingBox();
        if (!box) throw new Error(`nothing at ${selector}`);
        return box;
    }

    /** Turn the mouse wheel over a point: in the view, that zooms. */
    async wheel(x: number, y: number, delta: number, times = 1): Promise<void> {
        await this.page.mouse.move(x, y);
        for (let i = 0; i < times; i++) await this.page.mouse.wheel(0, delta);
        await this.drawn();
    }

    /** Drag a mouse button from one point to another. In the view, away from
     * the robot, the left one orbits and the right one pans. */
    async drag(
        start: [number, number],
        end: [number, number],
        button: "left" | "right" = "left",
    ): Promise<void> {
        const mouse = this.page.mouse;
        await mouse.move(...start);
        await mouse.down({ button });
        await mouse.move(...end, { steps: 8 });
        await mouse.up({ button });
        await this.drawn();
    }

    /** A picture of the window, or of `box` of it, at SCALE. */
    async shot(box?: Box): Promise<Buffer> {
        return this.page.screenshot({ clip: box, scale: "device" });
    }
}

// ................................
// Pictures
// ................................

async function scaled(png: Buffer, width: number): Promise<Sharp> {
    return sharp(png).resize({ width, kernel: "lanczos3" }).removeAlpha();
}

async function save(png: Buffer, file: string, width?: number): Promise<void> {
    const path = join(OUT_DIR, file);
    const image = width ? await scaled(png, width) : sharp(png).removeAlpha();
    const info = await image.png({ compressionLevel: 9 }).toFile(path);
    report(path, info.width, info.height);
}

function report(path: string, width: number, height: number, note = ""): void {
    const kb = Math.floor(statSync(path).size / 1024);
    console.log(
        `  docs/images/${path.split("/").pop()?.padEnd(20)} ${width}x${height}  ${kb} KB  ${note}`,
    );
}

/** The frames of an animation: pictures of one box of the window. */
class Recorder {
    frames: { rgba: Uint8Array; width: number; height: number }[] = [];
    durations: number[] = [];
    private shooter: Shooter;
    private box: Box | undefined;
    private width: number;

    constructor(shooter: Shooter, box: Box | undefined, width: number) {
        this.shooter = shooter;
        this.box = box;
        this.width = width;
    }

    async frame(ms = STEP_FRAME_MS): Promise<void> {
        const image = await scaled(await this.shooter.shot(this.box), this.width);
        const { data, info } = await image
            .ensureAlpha()
            .raw()
            .toBuffer({ resolveWithObject: true });
        this.frames.push({ rgba: new Uint8Array(data), width: info.width, height: info.height });
        this.durations.push(ms);
    }

    /** Click something, shown first with a ring on it, and hold what comes of
     * it for `thenMs`. */
    async press(selector: string, thenMs: number): Promise<void> {
        await this.shooter.mark(selector);
        await this.frame(CLICK_MS);
        await this.shooter.mark(null);
        await this.shooter.click(selector);
        await this.frame(thenMs);
    }

    save(file: string): void {
        // One palette for every frame, taken from all of them together:
        // quantised each on its own, the background would shimmer, and a
        // colour that only turns up later would have none to be drawn in.
        const total = this.frames.reduce((n, f) => n + f.rgba.length, 0);
        const sheet = new Uint8Array(total);
        let at = 0;
        for (const f of this.frames) {
            sheet.set(f.rgba, at);
            at += f.rgba.length;
        }
        // One palette entry is kept back for "unchanged": after the first
        // frame, a pixel the same as the frame before is left transparent,
        // which shows the one before through it and makes the GIF far
        // smaller.
        const palette = quantize(sheet, 255, { format: "rgb565" });
        const clear = palette.length;
        const full = [...palette, [0, 0, 0]];
        const gif = GIFEncoder();
        let before: Uint8Array | null = null;
        this.frames.forEach((f, i) => {
            const index = applyPalette(f.rgba, palette, "rgb565");
            let written = index;
            if (before) {
                written = index.map((v, k) => (v === before![k] ? clear : v));
            }
            before = index;
            gif.writeFrame(written, f.width, f.height, {
                palette: i === 0 ? full : undefined,
                delay: this.durations[i],
                repeat: 0,
                transparent: i > 0,
                transparentIndex: clear,
                dispose: 1,
            });
        });
        gif.finish();
        const path = join(OUT_DIR, file);
        writeFileSync(path, gif.bytes());
        report(path, this.frames[0].width, this.frames[0].height, `${this.frames.length} frames`);
    }
}

/** How far along a move is at `step` of `steps`, starting and stopping gently. */
function eased(step: number, steps: number): number {
    const t = step / steps;
    return t * t * (3 - 2 * t);
}

const gaitButton = (gait: string, kind: "Add" | "Replace") =>
    `#pose-gait-list-builtin .dock-gait-row[data-gait="${gait}"] button[title^="${kind}"]`;

/** Record the sequence, a frame of the preview at a time, stepped from here
 * so that each frame is in the animation once. The last frame's number. */
async function play(shooter: Shooter, recorder: Recorder, frameMs: number): Promise<number> {
    const last = await shooter.run<number>(
        `Number(document.querySelector("#pose-frame-slider [role=slider]").getAttribute("aria-valuemax"))`,
    );
    for (let frame = 0; frame <= last; frame++) {
        await shooter.act("scrub", frame);
        await recorder.frame(frameMs);
    }
    return last;
}

// ................................
// The shots
// ................................

/** The whole window, and the controller cut out of it. */
async function shootApp(shooter: Shooter): Promise<void> {
    await shooter.open(APP_WINDOW, ["pose", "controller"]);
    // Standby, then the pose, then a gait: a sequence with the pose selected
    // in it, and the body picked up.
    await shooter.act("addPose");
    await shooter.pick("body");
    for (const [key, value] of Object.entries(POSED_BODY))
        await shooter.act("bodySlider", key, value);
    await shooter.pick(POSED_LEG);
    const foot = await shooter.run<number[]>(
        `["x", "y", "up"].map((k) => Number(document.getElementById("pose-foot-" + k).value))`,
    );
    await shooter.act(
        "footFields",
        foot.map((c, i) => c + POSED_FOOT[i]),
    );
    await shooter.act("addPose");
    await shooter.click(gaitButton(POSED_GAIT, "Add"));
    await shooter.act("selectKeyframe", 1);
    await shooter.pick("body");

    await save(await shooter.shot(), "app.png", APP_WIDTH);
    const box = await shooter.box("#drive-hud");
    const margin = 10;
    await save(
        await shooter.shot({
            x: box.x - margin,
            y: box.y - margin,
            width: box.width + 2 * margin,
            height: box.height + 2 * margin,
        }),
        "controller.png",
    );
}

/** One cycle of a walk, looped, with nothing in the picture but the view. */
async function shootWalk(shooter: Shooter): Promise<void> {
    await shooter.open(APP_WINDOW);
    await shooter.style(
        ".hexapod-view-overlay, .hexapod-view-hud, .hexapod-view-controls," +
            ".hexapod-view-drive, .hexapod-view-tool, .hexapod-view-playback," +
            ".hexapod-view-hint, .topbar { display: none !important; }",
    );
    // The gait as the whole sequence, with the move from its last keyframe
    // back to its first: a cycle that repeats.
    await shooter.click(gaitButton(WALK_GAIT, "Replace"));
    await shooter.act("setSpeed", WALK_SPEED_PCT);
    await shooter.act("setLoop", true);
    await shooter.act("grabScrubber");
    const view = await shooter.box(".hexapod-view-frame");
    await shooter.wheel(view.x + view.width / 2, view.y + view.height / 2, -100, 5);
    // A band across the view, the robot in the middle of it.
    const band = {
        x: view.x + view.width * 0.17,
        y: view.y + view.height * 0.1,
        width: view.width * 0.66,
        height: view.height * 0.76,
    };
    const recorder = new Recorder(shooter, band, WALK_WIDTH);
    await play(shooter, recorder, WALK_FRAME_MS);
    // Looped, the sequence ends where it starts: one of the two is enough.
    const first = recorder.frames[0].rgba;
    const last = recorder.frames[recorder.frames.length - 1].rgba;
    if (first.length === last.length && first.every((v, i) => v === last[i])) {
        recorder.frames.pop();
        recorder.durations.pop();
    }
    recorder.save("walk.gif");
}

/** Posing the robot in the view: the body moved and turned, a foot lifted. */
async function shootPose(shooter: Shooter): Promise<void> {
    await shooter.open(POSE_WINDOW, ["pose"]);
    const view = await shooter.box(".hexapod-view-frame");
    // The pose's controls take the view's left side; the robot is moved clear
    // of them, as one would with the right mouse button.
    const centre: [number, number] = [view.x + view.width / 2, view.y + view.height * 0.3];
    await shooter.drag(
        centre,
        [centre[0] + view.width * 0.16, centre[1] + view.height * 0.04],
        "right",
    );
    const recorder = new Recorder(shooter, view, GIF_WIDTH);

    const slide = async (key: string, start: number, stop: number, resolution: number) => {
        for (let step = 1; step <= 8; step++) {
            const value = start + (stop - start) * eased(step, 8);
            await shooter.act(
                "bodySlider",
                key,
                Number((Math.round(value / resolution) * resolution).toFixed(4)),
            );
            await recorder.frame();
        }
    };
    const slideFoot = async (axis: number, start: number, stop: number) => {
        for (let step = 1; step <= 8; step++) {
            const value = Math.round(start + (stop - start) * eased(step, 8));
            await shooter.act(
                "footFields",
                [0, 1, 2].map((i) => (i === axis ? value : null)),
            );
            await recorder.frame();
        }
    };

    await recorder.frame(900);
    // The body: moved by its arrows, then turned by its rings.
    await recorder.press("#pose-pick-body", 800);
    await slide("percent_z", 0, 0.3, 0.05);
    await slide("percent_x", 0, -0.25, 0.05);
    await recorder.frame(500);
    await recorder.press("#pose-body-mode .form-check:nth-child(2) label", 800);
    await slide("rot_x", 0, 12, 1.5);
    await slide("rot_z", 0, -15, 1.5);
    await recorder.frame(700);
    // A foot: the one nearest the camera, lifted and put forward.
    await recorder.press(`#pose-pick-${POSE_GIF_LEG}`, 800);
    const up = await shooter.run<number>(`Number(document.getElementById("pose-foot-up").value)`);
    const forward = await shooter.run<number>(
        `Number(document.getElementById("pose-foot-y").value)`,
    );
    await slideFoot(2, up, up + 50);
    await slideFoot(1, forward, forward + 40);
    await recorder.frame(700);
    await shooter.pick(null);
    await recorder.frame(2000);
    recorder.save("pose.gif");
}

/** A sequence put together from the robot's gaits, then played. */
async function shootSequence(shooter: Shooter): Promise<void> {
    await shooter.open(SEQUENCE_WINDOW);
    const view = await shooter.box(".hexapod-view-frame");
    await shooter.wheel(view.x + view.width / 2, view.y + view.height / 2, -100, 2);
    const recorder = new Recorder(shooter, undefined, GIF_WIDTH);
    await recorder.frame(1000);
    for (const gait of SEQUENCE_GAITS) {
        await recorder.press(gaitButton(gait, "Add"), 700);
    }
    await shooter.mark("#pose-play-btn");
    await recorder.frame(CLICK_MS);
    await shooter.mark(null);
    // Shown playing, but stepped from here.
    await shooter.run(`window.hexapodApp.store.setState({ mode: "preview", frame: 0 })`);
    const last = await play(shooter, recorder, STEP_FRAME_MS);
    // Run out where it ends, which makes that frame the pose.
    await shooter.act("playhead", last);
    await recorder.frame(2000);
    recorder.save("sequence.gif");
}

const SHOTS: Record<string, (shooter: Shooter) => Promise<void>> = {
    app: shootApp,
    walk: shootWalk,
    pose: shootPose,
    sequence: shootSequence,
};

async function main(): Promise<void> {
    const wanted = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(SHOTS);
    const unknown = wanted.filter((name) => !(name in SHOTS));
    if (unknown.length) {
        throw new Error(
            `no such shot: ${unknown.join(", ")} (there are: ${Object.keys(SHOTS).join(", ")})`,
        );
    }
    mkdirSync(OUT_DIR, { recursive: true });
    const robot = await FakeRobot.fromFixture("nougat", { udpPort: UDP_PORT }).start();
    const shooter = new Shooter(robot);
    try {
        for (const name of wanted) {
            console.log(`${name} ...`);
            await SHOTS[name](shooter);
        }
    } finally {
        await shooter.dispose();
        await robot.stop();
    }
}

main().catch((error) => {
    console.error(error);
    process.exit(1);
});
