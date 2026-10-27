// The main process's side of the bridge to the page (shared/api.ts): the
// robot link, what is kept on disk, file dialogs and the window's buttons.

import { readFileSync, writeFileSync } from "node:fs";
import { type BrowserWindow, dialog, ipcMain } from "electron";
import type { LinkUpdate, Startup } from "../shared/api";
import type { Keyframe } from "../shared/keyframes";
import type { Pose } from "../shared/path_generator";
import type { RobotLink } from "./robot_link";
import * as storage from "./storage";

export function registerIpc(
    link: RobotLink,
    window: () => BrowserWindow | null,
    startup: () => Startup,
): void {
    const update = (): LinkUpdate => ({ status: link.status(), robotConfig: link.robotConfig });
    const robot = (name: string) => ({ name });

    // Read synchronously by the preload script, so the page is drawn in the
    // saved theme and sizes from its first paint.
    ipcMain.on("startup", (event) => {
        event.returnValue = startup();
    });

    ipcMain.handle("link:connect", async (_e, address: string) => {
        if (link.connected) {
            link.disconnect();
        }
        await link.connect(address);
        return update();
    });
    ipcMain.handle("link:disconnect", () => {
        link.disconnect();
        return update();
    });
    ipcMain.handle("link:status", () => link.status());
    ipcMain.handle("link:streaming", (_e, on: boolean) => {
        link.setStreaming(on);
        return link.streaming;
    });
    ipcMain.handle("link:max-step", (_e, maxStep: number) => link.setMaxStep(maxStep));
    ipcMain.handle("link:speed", (_e, pct: number) => link.setMotionSpeed(pct));
    ipcMain.on("link:pose", (_e, pose: Pose) => link.sendPose(pose));
    ipcMain.handle("link:play", (_e, poses: Pose[], loop: boolean, fps: number) =>
        link.playSequence(poses, loop, fps),
    );
    ipcMain.handle("link:stop", () => link.stopSequence());
    ipcMain.handle("link:motion", (_e, motion: string) => link.sendMotionCommand(motion));
    // The controller over the view runs the robot's own gaits for as long as a
    // pad is held: repeated while held, "standby" when let go.
    ipcMain.handle("link:drive", (_e, motion: unknown) => {
        if (!link.connected) {
            return { ok: false, message: "Connect a robot to drive it." };
        }
        if (typeof motion !== "string" || !link.drive(motion)) {
            return { ok: false, message: `The robot has no '${motion}' gait.` };
        }
        return { ok: true, message: "" };
    });

    ipcMain.on("prefs:theme", (_e, theme) => storage.saveTheme(theme));
    ipcMain.on("prefs:layout", (_e, sizes) => storage.saveLayout(sizes));
    ipcMain.on("prefs:panels", (_e, states) => storage.savePanels(states));
    ipcMain.on("prefs:workspace", (_e, values) => storage.saveWorkspace(values));

    ipcMain.handle("gaits:list", (_e, name: string) => storage.listGaits(robot(name)));
    ipcMain.handle("gaits:load", (_e, id: string, name: string) => {
        try {
            return { keyframes: storage.loadGait(id, robot(name)) };
        } catch (error) {
            return { error: (error as Error).message };
        }
    });
    ipcMain.handle("gaits:save", (_e, gaitName: string, keyframes: Keyframe[], name: string) => {
        try {
            return { id: storage.saveGait(gaitName, keyframes, robot(name)) };
        } catch (error) {
            const message = (error as Error).message;
            const code = (error as NodeJS.ErrnoException).code;
            return { error: code ? `Could not save the gait: ${message}` : message };
        }
    });
    ipcMain.handle("gaits:delete", (_e, id: string) => storage.deleteGait(id));

    const jsonFilter = [{ name: "Keyframes", extensions: ["json"] }];
    ipcMain.handle("files:open", async () => {
        const win = window();
        const result = win
            ? await dialog.showOpenDialog(win, { filters: jsonFilter, properties: ["openFile"] })
            : await dialog.showOpenDialog({ filters: jsonFilter, properties: ["openFile"] });
        if (result.canceled || !result.filePaths.length) {
            return null;
        }
        return readFileSync(result.filePaths[0], "utf-8");
    });
    ipcMain.handle("files:save", async (_e, defaultName: string, text: string) => {
        const win = window();
        const options = { defaultPath: defaultName, filters: jsonFilter };
        const result = win
            ? await dialog.showSaveDialog(win, options)
            : await dialog.showSaveDialog(options);
        if (result.canceled || !result.filePath) {
            return false;
        }
        writeFileSync(result.filePath, text, "utf-8");
        return true;
    });

    ipcMain.on("window:minimize", () => window()?.minimize());
    ipcMain.on("window:maximize", () => {
        const win = window();
        if (win) {
            win.isMaximized() ? win.unmaximize() : win.maximize();
        }
    });
    ipcMain.on("window:close", () => window()?.close());
}
