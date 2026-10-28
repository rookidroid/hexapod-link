// Hexapod Link's main process: the window, the robot link and what is kept on
// disk. The page (src/renderer) does all the posing and the kinematics itself
// and asks for the rest over the bridge in ipc.ts.
//
// The window is frameless: the app's top bar, laid see-through over the 3D
// view, is its title bar, dragged by the system (-webkit-app-region), with its
// own minimize, maximize and close buttons. It reopens at the size and place
// it was closed at, and maximized if it was left so; a place on a screen since
// unplugged is dropped, and the window opens centred.
//
//     npm run dev            the app, reloading as the code changes
//     HEXAPOD_LINK_FRAMED=1  keep the system's own window frame

import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { app, BrowserWindow, screen, shell } from "electron";
import type { Startup } from "../shared/api";
import { APP_TITLE } from "../shared/settings";
import { VIEWER_THEMES } from "../shared/style";
import { registerIpc } from "./ipc";
import { RobotLink } from "./robot_link";
import * as storage from "./storage";
import { fitWindow } from "./window_state";

const here = fileURLToPath(new URL(".", import.meta.url));

const WINDOW_SIZE: [number, number] = [1440, 900];
const WINDOW_MIN_SIZE: [number, number] = [1024, 700];
const FRAMELESS = !process.env.HEXAPOD_LINK_FRAMED;

const link = new RobotLink();
let mainWindow: BrowserWindow | null = null;

function startup(): Startup {
    return {
        version: app.getVersion(),
        platform: process.platform,
        frameless: FRAMELESS,
        theme: storage.loadTheme(),
        layout: storage.loadLayout(),
        panels: storage.loadPanels(),
        workspace: storage.loadWorkspace(),
        robotConfig: link.robotConfig,
        status: link.status(),
    };
}

/** Give the link its stream speed limit and controller speed as left. Not
 * streaming itself: the robot would start moving the moment it connected. */
function restoreLink(): void {
    const saved = storage.loadWorkspace();
    const number = (value: unknown) =>
        typeof value === "number" && Number.isFinite(value) && value >= 1 && value <= 1000
            ? value
            : null;
    const maxStep = number(saved.max_step);
    if (maxStep !== null) {
        link.setMaxStep(maxStep);
    }
    const speed = number(saved.drive_speed);
    if (speed !== null) {
        void link.setMotionSpeed(speed);
    }
}

function iconPath(): string {
    return join(here, "../../resources", process.platform === "win32" ? "app.ico" : "icon.png");
}

function createWindow(): void {
    const saved = storage.loadWindow();
    const screens = screen.getAllDisplays().map((d) => d.workArea);
    const { x, y, width, height } = fitWindow(saved, WINDOW_SIZE, WINDOW_MIN_SIZE, screens);

    const win = new BrowserWindow({
        title: APP_TITLE,
        width,
        height,
        ...(x !== null && y !== null ? { x, y } : { center: true }),
        minWidth: WINDOW_MIN_SIZE[0],
        minHeight: WINDOW_MIN_SIZE[1],
        frame: !FRAMELESS,
        titleBarStyle: FRAMELESS && process.platform === "darwin" ? "hidden" : "default",
        backgroundColor: VIEWER_THEMES[storage.loadTheme()].background,
        icon: iconPath(),
        show: false,
        webPreferences: {
            preload: join(here, "../preload/index.cjs"),
            sandbox: true,
            contextIsolation: true,
        },
    });
    mainWindow = win;

    win.once("ready-to-show", () => {
        if (saved.maximized) {
            win.maximize();
        }
        win.show();
    });
    const tellMaximized = () => win.webContents.send("window:maximized", win.isMaximized());
    win.on("maximize", tellMaximized);
    win.on("unmaximize", tellMaximized);

    // The size and place it had out of maximized, and whether it was.
    win.on("close", () => {
        const bounds = win.getNormalBounds();
        storage.saveWindow({ ...bounds, maximized: win.isMaximized() });
    });
    win.on("closed", () => {
        mainWindow = null;
    });

    // Links open in the system's browser, not in the app's window.
    win.webContents.setWindowOpenHandler(({ url }) => {
        void shell.openExternal(url);
        return { action: "deny" };
    });

    if (process.env.ELECTRON_RENDERER_URL) {
        void win.loadURL(process.env.ELECTRON_RENDERER_URL);
    } else {
        void win.loadFile(join(here, "../renderer/index.html"));
    }
}

app.setName(APP_TITLE);
registerIpc(link, () => mainWindow, startup);
restoreLink();

app.whenReady().then(() => {
    createWindow();
    app.on("activate", () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

// Return the robot to LUT control before the process goes away, rather than
// leaving it holding the last pose until the firmware's failsafe fires.
app.on("before-quit", () => link.disconnect());

app.on("window-all-closed", () => {
    link.disconnect();
    // Let the RT_EXIT packet out before quitting.
    setTimeout(() => app.quit(), 100);
});
