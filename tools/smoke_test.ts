// Drive the built app the way a person would, against the stand-in robot
// (tools/fake_robot.ts), and check that each step does what it should:
//
//     npm run build && npm run smoke
//
// Connects, poses a leg, puts a gait into the sequence, plays it, runs it on
// the robot, drives the robot from the controller, closes the window, and
// opens it again to find the workspace as it was left. Nothing on this
// machine is read or written: the preferences, the robot cache and the gaits
// go to a folder of their own. The stand-in listens on the robot's UDP port,
// so no real robot session can be running here at the same time.
//
// On a machine without a display, run it under xvfb-run. With
// HEXAPOD_LINK_EXECUTABLE set to a packaged app (npm run dist), that is what
// is driven, rather than the build in out/.

import { strict as assert } from "node:assert";
import { mkdtempSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { _electron, type ElectronApplication, type Page } from "playwright-core";
import { FakeRobot, UDP_PORT } from "./fake_robot.ts";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const packaged = process.env.HEXAPOD_LINK_EXECUTABLE;
const electronPath = packaged || (createRequire(import.meta.url)("electron") as unknown as string);
const data = mkdtempSync(join(tmpdir(), "hexapod-link-smoke-"));
const env = {
    ...process.env,
    HEXAPOD_LINK_PREFERENCES: join(data, "preferences.json"),
    HEXAPOD_LINK_CONFIG_CACHE: join(data, "robot_config.json"),
    HEXAPOD_LINK_GAITS: join(data, "gaits"),
};
// A software WebGL, for machines without a GPU (CI, a virtual display).
const ARGS = [
    ...(packaged ? [] : [ROOT]),
    "--no-sandbox",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
];

async function launch(): Promise<[ElectronApplication, Page]> {
    const app = await _electron.launch({ executablePath: electronPath, args: ARGS, env });
    const page = await app.firstWindow();
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
        if (message.type() === "error") errors.push(message.text());
    });
    await page.waitForSelector(".hexapod-view canvas", { timeout: 20000 });
    (page as Page & { errors: string[] }).errors = errors;
    return [app, page];
}

const step = (text: string) => console.log(`· ${text}`);
const kinds = (robot: FakeRobot) => robot.packets.map((p) => p[0]);
const sessions = (robot: FakeRobot, action: number) =>
    robot.packets.filter((p) => p[0] === 0xa7 && p[1] === action).length;

async function main(): Promise<void> {
    const robot = await FakeRobot.fromFixture("nougat", { udpPort: UDP_PORT }).start();
    let app: ElectronApplication | null = null;
    try {
        let page: Page;
        [app, page] = await launch();
        step("the window opens on the default robot, in the dark theme");
        assert.equal(await page.getAttribute("html", "data-theme"), "dark");
        assert.match((await page.textContent("#status-pill")) ?? "", /Offline/);

        step("connecting reads the robot's config");
        await page.click("#status-pill");
        await page.fill("#robot-ip-input", robot.address);
        await page.click("#robot-connect-btn");
        await page.waitForFunction(() =>
            document.querySelector("#status-pill")?.textContent?.includes("Online"),
        );
        assert.ok(robot.requests.some(([m, path]) => m === "GET" && path === "/robot_config"));
        assert.ok(sessions(robot, 1) >= 1, "RT_ENTER sent");
        await page.keyboard.press("Escape");

        step("typing a joint angle moves its foot, and the fields follow");
        await page.click("#pose-hud > summary");
        const field = "#pose-joint-left-front-femur";
        const before = await page.inputValue(field);
        await page.fill(field, "45");
        await page.press(field, "Enter");
        await page.waitForFunction(
            (f) => (document.querySelector(f) as HTMLInputElement).value === "45",
            field,
        );
        assert.notEqual(before, "45");

        step("picking a foot shows where it is");
        await page.click("#pose-pick-left-front");
        await page.waitForSelector("#pose-adjust-foot");
        assert.match((await page.textContent("#pose-foot-title")) ?? "", /Left Leg 1 foot/);

        step("+ Add pose records a keyframe");
        await page.click("#pose-add-btn");
        await page.waitForSelector('[data-kf="0"]');

        step("a gait from the library goes in as keyframes");
        await page.click(
            '#pose-gait-list-builtin .dock-gait-row:has-text("Walk forward") button[title^="Add"]',
        );
        const count = await page.locator("[data-kf]").count();
        assert.ok(count > 5, `walk keyframes: ${count}`);

        step("playing the sequence moves through it, and pausing makes the frame the pose");
        // Looping, so it cannot run out before it is paused.
        await page.click("#pose-loop input");
        await page.click("#pose-play-btn");
        await page.waitForTimeout(250);
        await page.click("#pose-play-btn");
        assert.match((await page.textContent("#pose-play-btn")) ?? "", /Play/);
        const shown = (await page.textContent("#pose-frame-display")) ?? "";
        assert.doesNotMatch(shown, /^0\//, `frame display ${shown}`);
        // Between two keyframes, the pose remembers where it is.
        assert.match(
            (await page.textContent("#pose-add-btn")) ?? "",
            /at \d+\.\d\d s|Insert after|Add pose/,
        );

        step("played to the end, the last frame becomes the pose");
        await page.click("#pose-loop input");
        await page.click("#pose-play-btn");
        await page.waitForFunction(
            () => document.querySelector("#pose-play-btn")?.textContent?.includes("Play"),
            null,
            {
                timeout: 5000,
            },
        );
        assert.match((await page.textContent("#pose-keyframe-editor-label")) ?? "", /Keyframe #/);

        step("run on robot streams the sequence");
        const posesBefore = kinds(robot).filter((k) => k === 0xa6).length;
        await page.click("#pose-run-btn");
        await page.waitForFunction(() =>
            document.querySelector("#pose-robot-message")?.textContent?.startsWith("Streaming"),
        );
        await page.waitForTimeout(500);
        assert.ok(
            kinds(robot).filter((k) => k === 0xa6).length > posesBefore + 10,
            "pose packets streamed",
        );
        await page.click("#pose-stop-btn");

        step("holding a controller pad drives the robot, letting go stands it");
        await page.click("#drive-hud > summary");
        const zone = page.locator('.drive-pad-move [data-motion="walk_0"] path').first();
        const box = await zone.boundingBox();
        assert.ok(box);
        const motionsBefore = robot.packets.filter((p) => p[0] === 0xa5).length;
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        await page.mouse.down();
        await page.waitForTimeout(500);
        await page.mouse.up();
        await page.waitForTimeout(300);
        const motions = robot.packets
            .filter((p) => p[0] === 0xa5)
            .slice(motionsBefore)
            .map((p) => p[1]);
        assert.deepEqual(motions.slice(-2), [1, 0], `motions ${motions}`);

        step("the theme switches");
        await page.click("#theme-toggle");
        assert.equal(await page.getAttribute("html", "data-theme"), "light");

        const errors = (page as Page & { errors: string[] }).errors;
        assert.deepEqual(errors, [], "no errors in the page");

        step("closing the window leaves real-time mode");
        const exitsBefore = sessions(robot, 0);
        await page.waitForTimeout(500);
        await app.close();
        app = null;
        await new Promise((r) => setTimeout(r, 300));
        assert.ok(sessions(robot, 0) > exitsBefore, "RT_EXIT sent");

        step("reopened, the workspace is as it was left");
        const preferences = JSON.parse(readFileSync(env.HEXAPOD_LINK_PREFERENCES, "utf-8"));
        assert.equal(preferences.theme, "light");
        assert.equal(preferences.workspace.keyframes.keyframes.length, count);
        [app, page] = await launch();
        assert.equal(await page.getAttribute("html", "data-theme"), "light");
        assert.equal(await page.locator("[data-kf]").count(), count);
        assert.match((await page.textContent("#robot-info")) ?? "", /last connected/);
        console.log("smoke test passed");
    } finally {
        await app?.close();
        await robot.stop();
    }
}

main().catch((error) => {
    console.error(error);
    process.exit(1);
});
