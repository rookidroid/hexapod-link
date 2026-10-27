// The bridge between the page and the main process (shared/api.ts), as
// `window.hexapod`. It also puts the saved theme and workspace sizes on <html>
// before the page is first drawn, so a dark start never flashes light and a
// resized dock never jumps.

import { contextBridge, ipcRenderer } from "electron";
import type { HexapodApi, Startup } from "../shared/api";

const startup: Startup = ipcRenderer.sendSync("startup");

function applyStartup(): void {
    const root = document.documentElement;
    root.setAttribute("data-theme", startup.theme);
    root.setAttribute("data-bs-theme", startup.theme);
    if (startup.frameless) {
        root.setAttribute("data-window", "frameless");
    }
    root.setAttribute("data-platform", startup.platform);
    if (startup.layout.dock_h) root.style.setProperty("--dock-h", `${startup.layout.dock_h}px`);
    if (startup.layout.lib_w) root.style.setProperty("--lib-w", `${startup.layout.lib_w}px`);
}
if (document.documentElement) {
    applyStartup();
} else {
    document.addEventListener("readystatechange", applyStartup, { once: true });
}

const api: HexapodApi = {
    startup,
    connect: (address) => ipcRenderer.invoke("link:connect", address),
    disconnect: () => ipcRenderer.invoke("link:disconnect"),
    status: () => ipcRenderer.invoke("link:status"),
    setStreaming: (on) => ipcRenderer.invoke("link:streaming", on),
    setMaxStep: (maxStep) => ipcRenderer.invoke("link:max-step", maxStep),
    setMotionSpeed: (pct) => ipcRenderer.invoke("link:speed", pct),
    sendPose: (pose) => ipcRenderer.send("link:pose", pose),
    playSequence: (poses, loop, fps) => ipcRenderer.invoke("link:play", poses, loop, fps),
    stopSequence: () => ipcRenderer.invoke("link:stop"),
    sendMotion: (motion) => ipcRenderer.invoke("link:motion", motion),
    drive: (motion) => ipcRenderer.invoke("link:drive", motion),

    saveTheme: (theme) => ipcRenderer.send("prefs:theme", theme),
    saveLayout: (sizes) => ipcRenderer.send("prefs:layout", sizes),
    savePanels: (states) => ipcRenderer.send("prefs:panels", states),
    saveWorkspace: (values) => ipcRenderer.send("prefs:workspace", values),
    listGaits: (robot) => ipcRenderer.invoke("gaits:list", robot),
    loadGait: (id, robot) => ipcRenderer.invoke("gaits:load", id, robot),
    saveGait: (name, keyframes, robot) => ipcRenderer.invoke("gaits:save", name, keyframes, robot),
    deleteGait: (id) => ipcRenderer.invoke("gaits:delete", id),

    openKeyframes: () => ipcRenderer.invoke("files:open"),
    saveKeyframes: (defaultName, text) => ipcRenderer.invoke("files:save", defaultName, text),

    minimize: () => ipcRenderer.send("window:minimize"),
    toggleMaximize: () => ipcRenderer.send("window:maximize"),
    close: () => ipcRenderer.send("window:close"),
    onMaximized: (listener) => {
        const handler = (_event: unknown, maximized: boolean) => listener(maximized);
        ipcRenderer.on("window:maximized", handler);
        return () => ipcRenderer.removeListener("window:maximized", handler);
    },
};

contextBridge.exposeInMainWorld("hexapod", api);
