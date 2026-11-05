// The top bar, which is also the window's title bar: the app's name, the
// robot -- a split pill: the link's status, which opens to connect, and a
// Stream toggle beside it -- the theme, and in the
// frameless window its own minimize, maximize and close buttons. It lies over
// the top of the 3D view, see-through so the view shows behind it.

import { useEffect, useRef, useState } from "react";
import { describeFirmware } from "../../../shared/robot_config";
import { APP_TITLE, ROBOT_DEFAULT_IP } from "../../../shared/settings";
import { api } from "../api";
import { useStore } from "../state/store";
import { Button, FieldLabel, Slider } from "./widgets";

// What the theme button offers is the other theme, so it shows that one's icon.
const THEME_ICON = { light: "☾", dark: "☀" };
const THEME_TITLE = { light: "Switch to dark theme", dark: "Switch to light theme" };

function linkText(status: ReturnType<typeof useStore.getState>["status"]): string {
    if (status.last_error) return `⚠ ${status.last_error}`;
    if (!status.connected) return "Disconnected";
    const mode = status.streaming ? "STREAMING" : "IDLE (holding)";
    return `${status.robot_label} @ ${status.ip} — ${mode} — ${status.packets_sent} pkts`;
}

/** The link's readout: a status pill that opens a dropdown with the robot's
 * address, Connect, how fast streaming may move the joints, and the link's
 * detail. A click outside it, or Esc, closes it. */
function LinkMenu() {
    const status = useStore((s) => s.status);
    const robotIp = useStore((s) => s.robotIp);
    const connecting = useStore((s) => s.connecting);
    const maxStep = useStore((s) => s.maxStep);
    const { set, toggleConnection, setMaxStep } = useStore.getState();
    const [open, setOpen] = useState(false);
    const menu = useRef<HTMLDetailsElement>(null);
    const input = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (!open) return;
        input.current?.focus();
        input.current?.select();
        const away = (e: PointerEvent) => {
            if (menu.current && !menu.current.contains(e.target as Node)) setOpen(false);
        };
        const esc = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                setOpen(false);
                menu.current?.querySelector("summary")?.focus();
            }
        };
        document.addEventListener("pointerdown", away);
        document.addEventListener("keydown", esc);
        return () => {
            document.removeEventListener("pointerdown", away);
            document.removeEventListener("keydown", esc);
        };
    }, [open]);

    let label: string;
    let state: string;
    if (status.last_error) {
        [label, state] = ["Fault", "is-fault"];
    } else if (!status.connected) {
        [label, state] = ["Offline", "is-offline"];
    } else {
        [label, state] = [`${status.robot_label} · Online`, "is-online"];
    }
    const firmware = status.connected ? describeFirmware(status.firmware) : "";
    const detail = firmware ? `${linkText(status)}\n${firmware}` : linkText(status);

    return (
        <details id="link-menu" className="link-menu" open={open} ref={menu}>
            <summary
                id="status-pill"
                className={`status-pill ${state}`}
                title={detail}
                onClick={(e) => {
                    e.preventDefault();
                    setOpen(!open);
                }}
            >
                {label}
            </summary>
            <div className="hud-panel link-panel">
                <FieldLabel>Robot address</FieldLabel>
                <div className="link-row">
                    <input
                        ref={input}
                        id="robot-ip-input"
                        type="text"
                        className="link-ip form-control-sm form-control"
                        placeholder={ROBOT_DEFAULT_IP}
                        value={robotIp}
                        onChange={(e) => set({ robotIp: e.target.value })}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !status.connected) void toggleConnection();
                        }}
                    />
                    <Button
                        id="robot-connect-btn"
                        color={status.connected ? "secondary" : "primary"}
                        className="link-connect"
                        disabled={connecting}
                        onClick={() => void toggleConnection()}
                    >
                        {status.connected ? "Disconnect" : connecting ? "Connecting…" : "Connect"}
                    </Button>
                </div>
                <div
                    className="ind-inline-slider link-speed"
                    title="How fast streaming may move any servo, in ticks per cycle"
                >
                    <FieldLabel>Max speed</FieldLabel>
                    <Slider
                        id="robot-max-step-slider"
                        min={1}
                        max={30}
                        step={1}
                        value={maxStep}
                        disabled={!status.connected}
                        onChange={setMaxStep}
                    />
                </div>
                <div id="link-detail" className="link-detail">
                    {detail}
                </div>
            </div>
        </details>
    );
}

/** The pill's other half: streams to the robot while on, and the view's edge
 * glows yellow. Only with a robot connected. */
function StreamToggle() {
    const connected = useStore((s) => s.status.connected);
    const streaming = useStore((s) => s.status.streaming);
    return (
        <button
            type="button"
            id="robot-stream-switch"
            className={`status-pill stream-toggle${streaming ? " is-on" : ""}`}
            aria-pressed={streaming}
            disabled={!connected}
            title={
                connected
                    ? "Stream to robot: sends every reachable pose to the servos as it changes, and the sequence as it plays. Put the hexapod on a stand first: a pose that stands up here will not necessarily stand up on the floor."
                    : "Stream to robot: connect to a robot first"
            }
            onClick={() => void useStore.getState().setStreaming(!streaming)}
        >
            Stream
        </button>
    );
}

function WindowButtons() {
    const [maximized, setMaximized] = useState(false);
    useEffect(
        () =>
            api.onMaximized((m) => {
                setMaximized(m);
                document.documentElement.classList.toggle("is-maximized", m);
            }),
        [],
    );
    const buttons: [string, string, () => void][] = [
        ["minimize", "Minimize", api.minimize],
        ["maximize", maximized ? "Restore" : "Maximize", api.toggleMaximize],
        ["close", "Close", api.close],
    ];
    return (
        <div className="window-buttons">
            {buttons.map(([action, title, onClick]) => (
                <button
                    type="button"
                    key={action}
                    className={`window-btn window-btn-${action}`}
                    title={title}
                    aria-label={title}
                    onClick={onClick}
                >
                    <span className="window-btn-icon" />
                </button>
            ))}
        </div>
    );
}

export function TopBar() {
    const theme = useStore((s) => s.theme);
    return (
        <header className="topbar">
            <div className="topbar-brand">
                <span className="topbar-title">{APP_TITLE}</span>
                <span className="topbar-version">v{api.startup.version}</span>
            </div>
            <div className="topbar-end">
                <div className="robot-link">
                    <LinkMenu />
                    <StreamToggle />
                </div>
                <button
                    type="button"
                    id="theme-toggle"
                    className="icon-btn"
                    title={THEME_TITLE[theme]}
                    onClick={() => useStore.getState().toggleTheme()}
                >
                    {THEME_ICON[theme]}
                </button>
                <WindowButtons />
            </div>
        </header>
    );
}
