// What the page can ask of the main process: the bridge the preload script
// puts on `window.hexapod` (src/preload/index.ts), answered in
// src/main/ipc.ts. The page does everything else itself.

import type { Keyframe } from "./keyframes";
import type { Pose } from "./path_generator";
import type { RobotConfig } from "./robot_config";

export type Theme = "light" | "dark";

export interface LinkStatus {
    connected: boolean;
    streaming: boolean;
    ip: string;
    packets_sent: number;
    last_error: string | null;
    max_step: number;
    speed_pct: number;
    robot_name: string;
    robot_label: string;
    config_source: string;
    config_version: number;
    firmware: { version: string; build: string; protocol: number } | null;
}

export interface GaitSummary {
    id: string;
    name: string;
    count: number;
    duration_ms: number;
}

/** What the page starts from, read before it is first drawn. */
export interface Startup {
    version: string;
    platform: string;
    frameless: boolean;
    theme: Theme;
    layout: { dock_h: number | null; lib_w: number | null };
    panels: { pose: boolean; controller: boolean; dimensions: boolean };
    workspace: Record<string, unknown>;
    robotConfig: RobotConfig;
    status: LinkStatus;
}

/** The link's state after something changed it, with the robot it models. */
export interface LinkUpdate {
    status: LinkStatus;
    robotConfig: RobotConfig;
}

export interface HexapodApi {
    startup: Startup;

    // The robot link.
    connect(address: string): Promise<LinkUpdate>;
    disconnect(): Promise<LinkUpdate>;
    status(): Promise<LinkStatus>;
    setStreaming(on: boolean): Promise<boolean>;
    setMaxStep(maxStep: number): Promise<void>;
    setMotionSpeed(pct: number): Promise<number>;
    sendPose(pose: Pose): void;
    playSequence(poses: Pose[], loop: boolean, fps: number): Promise<boolean>;
    stopSequence(): Promise<void>;
    sendMotion(motion: string): Promise<boolean>;
    drive(motion: string): Promise<{ ok: boolean; message: string }>;

    // Kept on disk.
    saveTheme(theme: Theme): void;
    saveLayout(sizes: Partial<Record<"dock_h" | "lib_w", number | null>>): void;
    savePanels(states: Partial<Record<"pose" | "controller" | "dimensions", boolean>>): void;
    saveWorkspace(values: Record<string, unknown>): void;
    listGaits(robot: string): Promise<GaitSummary[]>;
    loadGait(id: string, robot: string): Promise<{ keyframes?: Keyframe[]; error?: string }>;
    saveGait(
        name: string,
        keyframes: Keyframe[],
        robot: string,
    ): Promise<{ id?: string; error?: string }>;
    deleteGait(id: string): Promise<boolean>;

    // Keyframe files, through the system's dialogs.
    openKeyframes(): Promise<string | null>;
    saveKeyframes(defaultName: string, text: string): Promise<boolean>;

    // The frameless window's own buttons.
    minimize(): void;
    toggleMaximize(): void;
    close(): void;
    onMaximized(listener: (maximized: boolean) => void): () => void;
}
