// What the workspace is editing, and everything that changes it.
//
// There is one pose: the robot's standby posture with two layers on top
// (shared/pose_layers.ts):
//
//   feet  single feet moved away from where standby plants them, by dragging
//         them in the 3D view or typing where they go, or their leg's angles
//   body  the body moved and tilted over wherever the feet are planted, with
//         its sliders or by dragging it in the 3D view
//
// The layers add up, so neither undoes the other. Which one is being adjusted
// is whatever is picked -- the body, a foot or a joint -- by clicking it in the
// view or its button in the overlay on the view, which then shows its
// controls; picking changes nothing else. Out of the layers come the joint
// angles, what is streamed to the robot and what a keyframe keeps.
//
// The keyframes collect poses -- and the robot's gaits, as theirs
// (shared/gait_keyframes.ts) -- into a sequence, previewed in the view and run
// on the robot.
//
//   pose       {robot, state: the layers, feet: 6x3 in the body frame, seq,
//              at}; `at` says, for a pose taken from where playback came to
//              rest between two keyframes, where that is: {after: keyframe
//              index, ms: into the move from it}
//   keyframes  see shared/keyframes.ts, with the robot they were made on
//   selected   index of the keyframe the pose was loaded from, or null
//
// Foot positions only fit the robot they were placed on, so the pose and the
// keyframes carry that robot's name, and a different robot connecting starts
// the editor afresh.
//
// The robot modelled is the connected one (or the last one, or Nougat, the
// default), measured as the Dimensions panel has it: they start on the
// robot's own and can be edited to try another body.
//
// Each action below is one thing the person did; all of them run here, in the
// page, at once -- the kinematics are local, so nothing waits on anything.

import { create } from "zustand";
import type { GaitSummary, LinkStatus, Theme } from "../../../shared/api";
import { gaitKeyframes } from "../../../shared/gait_keyframes";
import type { Keyframe } from "../../../shared/keyframes";
import * as kf from "../../../shared/keyframes";
import { JOINT_NAMES, type JointName, legLabel } from "../../../shared/naming";
import type { Pose } from "../../../shared/path_generator";
import * as pl from "../../../shared/pose_layers";
import {
    DIMENSION_NAMES,
    type DimensionName,
    getSequenceFps,
    getSimulatorDimensions,
    type RobotConfig,
    withDimensions,
} from "../../../shared/robot_config";
import type { Scene } from "../../../shared/scene";
import {
    BODY_MAX_ANGLE,
    ROBOT_DEFAULT_IP,
    SLIDER_ANGLE_RESOLUTION,
} from "../../../shared/settings";
import { deepEqual, pyRound, type Vec3 } from "../../../shared/util";
import { api } from "../api";
import type { Picked } from "../view/hexapodView";
import { type SavedPose, savedDimensions, savedValues } from "./restore";

// ......................
// Constants
// ......................

export const SELECT_BODY = "body";
/** Frames a second the preview is drawn at. The robot gets its own, faster,
 * frames: see runOnRobot(). */
export const PREVIEW_FPS = 25;
export const SPEED_MIN_PCT = 25;
export const SPEED_MAX_PCT = 200;
export const SPEED_DEFAULT_PCT = 60;

/** How far the body's shift sliders go either way: a fraction of its size. */
export const MAX_SHIFT = 1.0;
/** How far its rotation sliders go: trimmed to a whole number of steps, so a
 * step lands on 0 and the body can be set level again. */
export const MAX_ANGLE =
    SLIDER_ANGLE_RESOLUTION * Math.floor(BODY_MAX_ANGLE / SLIDER_ANGLE_RESOLUTION);
/** How far each of BODY_KEYS goes either way. */
export const BODY_RANGES: Record<pl.BodyKey, number> = {
    percent_x: MAX_SHIFT,
    percent_y: MAX_SHIFT,
    percent_z: MAX_SHIFT,
    rot_x: MAX_ANGLE,
    rot_y: MAX_ANGLE,
    rot_z: MAX_ANGLE,
};

// A dragged foot put this far (mm) short of the cursor was held at its leg's
// limit; nearer is only rounding.
const FOOT_HELD_MM = 0.01;
const BODY_HELD_ALERT = "The body is as far as its legs can reach.";

export type Mode = "edit" | "preview";
export type BodyMode = "translate" | "rotate";
export type GaitSource = "builtin" | "mine";
export type Dims = Record<DimensionName, number | null>;
export type PanelKey = "pose" | "controller" | "dimensions";

export interface PoseStore {
    robot: string;
    state: pl.PoseState;
    feet: Vec3[];
    seq: number;
    at?: { after: number; ms: number };
}

export interface Preview {
    states: pl.PoseState[];
    poses: Pose[];
    times: [number, number, number][];
    count: number;
    fps: number;
    badFrames: number[];
    scene(frame: number): Scene;
}

export interface Solved {
    feet: Vec3[];
    pose: Pose;
    bad: number[];
    scene: Scene;
}

export interface State {
    robotConfig: RobotConfig;
    dims: Dims;
    pose: PoseStore;
    keyframes: Keyframe[];
    selected: number | null;
    selection: Picked;
    message: string;
    bodyMode: BodyMode;
    duration: number | null;
    ease: boolean;
    mode: Mode;
    playing: boolean;
    frame: number;
    loop: boolean;
    speed: number;
    gaitSource: GaitSource;
    gaitName: string;
    userGaits: GaitSummary[];
    userGaitMessage: string;
    robotMessage: string;
    status: LinkStatus;
    robotIp: string;
    maxStep: number;
    driveSpeed: number;
    theme: Theme;
    panels: Record<PanelKey, boolean>;
    connecting: boolean;
}

// ......................
// Derived: the robot, the solved pose, the preview
// ......................

function memo<A extends unknown[], R>(fn: (...args: A) => R): (...args: A) => R {
    let lastArgs: A | null = null;
    let last: R;
    return (...args: A) => {
        if (!lastArgs || args.some((a, i) => a !== lastArgs![i])) {
            lastArgs = args;
            last = fn(...args);
        }
        return last;
    };
}

const robotFrom = memo((config: RobotConfig, dims: Dims) => withDimensions(config, dims));

/** The robot the workspace models: the connected one's config, measured as
 * the Dimensions panel has it. */
export const robotOf = (s: Pick<State, "robotConfig" | "dims">) => robotFrom(s.robotConfig, s.dims);

const solvedFrom = memo((state: pl.PoseState, robot: RobotConfig): Solved => {
    const [feet, pose, bad] = pl.solve(state, robot);
    return { feet, pose, bad, scene: pl.scene(state, pose, robot) };
});

export const solvedOf = (s: State) => solvedFrom(s.pose.state, robotOf(s));

const previewFrom = memo(
    (keyframes: Keyframe[], loop: boolean, speedPct: number, robot: RobotConfig): Preview => {
        const speed = speedPct / 100;
        const seq = pl.sequence(keyframes, robot, PREVIEW_FPS, loop, true, speed);
        // Keyframes that did not keep their layers are drawn with the body unmoved.
        const states = seq.states ?? seq.feet.map((feet) => pl.fromFeet(feet, robot));
        const scenes = new Map<number, Scene>();
        return {
            states,
            poses: seq.poses,
            times: kf.frameTimes(keyframes, PREVIEW_FPS, loop, speed),
            count: keyframes.length,
            fps: PREVIEW_FPS,
            badFrames: seq.badFrames,
            scene(frame: number) {
                const at = Math.min(Math.max(frame, 0), states.length - 1);
                let scene = scenes.get(at);
                if (!scene) {
                    scene = pl.scene(states[at], seq.poses[at], robot);
                    scenes.set(at, scene);
                }
                return scene;
            },
        };
    },
);

/** The frames the view plays as the sequence. */
export const previewOf = (s: State) =>
    previewFrom(s.keyframes, s.loop, speedPct(s.speed), robotOf(s));

/** The scrubber's last frame. */
export const maxFrameOf = (s: State) => Math.max(previewOf(s).states.length - 1, 1);

// ......................
// Helpers
// ......................

/** The playback speed a typed value stands for: a whole percent, within
 * range; the default for one that is not a number. */
export function speedPct(value: unknown): number {
    const n = Number(value);
    if (value === null || value === "" || !Number.isFinite(n)) {
        return SPEED_DEFAULT_PCT;
    }
    return Math.trunc(Math.min(Math.max(pyRound(n), SPEED_MIN_PCT), SPEED_MAX_PCT));
}

/** A foot coordinate or joint angle as its field shows it. */
export const fieldValue = (mm: number) => pyRound(mm, 1);

function makePose(
    robot: RobotConfig,
    state: pl.PoseState,
    seq = 0,
    at?: PoseStore["at"],
): PoseStore {
    return {
        robot: robot.name,
        state,
        feet: pl.bodyFeet(state, robot),
        seq,
        ...(at ? { at } : {}),
    };
}

/** The layers a keyframe was made from, or, for one that did not keep them,
 * its feet as moves from standby. */
function keyframeState(keyframe: Keyframe, robot: RobotConfig): pl.PoseState {
    if (pl.isState(keyframe.state)) {
        return pl.makeState(keyframe.state.body, keyframe.state.offsets);
    }
    return pl.fromFeet(keyframe.feet, robot);
}

/** The id of the leg whose foot is picked, or null. */
export function pickedLeg(selection: Picked): number | null {
    return typeof selection === "number" && selection >= 0 && selection < 6 ? selection : null;
}

/** The body layer for a body dragged in the view, held to what its sliders
 * can say, in steps fine enough to follow the pointer. */
function draggedBody(origin: number[], rot: number[], robot: RobotConfig): pl.Body {
    const body = pl.bodyAt(origin, rot, robot);
    const held = {} as pl.Body;
    pl.BODY_KEYS.forEach((key, index) => {
        const most = BODY_RANGES[key];
        held[key] = pyRound(Math.min(Math.max(body[key], -most), most), index < 3 ? 2 : 1);
    });
    return held;
}

/** [state, held] for the body moved to `body`, or as far that way as its legs
 * can follow: the state, and whether it was held short of what was asked. */
function movedBody(
    state: pl.PoseState,
    body: pl.Body,
    robot: RobotConfig,
): [pl.PoseState, boolean] {
    const moved = pl.withBodyNear(state, body, robot);
    return [moved, !deepEqual(moved, pl.makeState(body, state.offsets))];
}

const finite = (value: unknown): number | null => {
    const n = typeof value === "number" ? value : Number.NaN;
    return Number.isFinite(n) ? n : null;
};

function dimsOf(robot: RobotConfig): Dims {
    const d = getSimulatorDimensions(robot, false);
    return Object.fromEntries(DIMENSION_NAMES.map((n) => [n, d[n]])) as Dims;
}

// ......................
// The store
// ......................

/** What an edit changes; anything left out stays as it was. */
interface Out {
    pose?: PoseStore;
    keyframes?: Keyframe[];
    selected?: number | null;
    message?: string;
    duration?: number | null;
    ease?: boolean;
    mode?: Mode;
}

type Trigger = "ease" | "playhead" | "other";

interface Actions {
    // The pose.
    footTarget(target: { leg: number; foot: number[]; final: boolean }): void;
    jointTarget(target: { leg: number; joint: string; angle: number; final: boolean }): void;
    bodyTarget(target: { origin: number[]; rot: number[]; final: boolean }): void;
    setSelection(selection: Picked): void;
    footFields(values: (number | null)[]): void;
    jointField(leg: number, joint: JointName, value: number | null): void;
    bodySlider(key: pl.BodyKey, value: number): void;
    resetPose(): void;
    clearFeet(): void;
    // The sequence.
    addPose(): void;
    updateKeyframe(): void;
    deleteKeyframe(): void;
    moveKeyframe(step: -1 | 1): void;
    renumber(): void;
    selectKeyframe(index: number): void;
    setDuration(value: number | null): void;
    setEase(ease: boolean): void;
    insertGait(source: GaitSource, id: string, replace: boolean): Promise<void>;
    loadKeyframes(text: string): void;
    saveKeyframes(): Promise<void>;
    // Playback.
    play(): void;
    tick(): void;
    scrub(frame: number): void;
    grabScrubber(): void;
    releaseScrubber(): void;
    playhead(frame: number): void;
    setLoop(loop: boolean): void;
    setSpeed(value: number | null): void;
    // The robot.
    setDims(name: DimensionName, value: number | null): void;
    toggleConnection(): Promise<void>;
    pollStatus(): Promise<void>;
    setStreaming(on: boolean): Promise<void>;
    setMaxStep(maxStep: number): void;
    setDriveSpeed(pct: number): Promise<void>;
    runOnRobot(): Promise<void>;
    stopOnRobot(): Promise<void>;
    // The rest.
    set(values: Partial<State>): void;
    listUserGaits(): Promise<void>;
    saveUserGait(): Promise<void>;
    deleteUserGait(id: string): Promise<void>;
    toggleTheme(): void;
    setPanel(key: PanelKey, open: boolean, keep: boolean): void;
}

export type Store = State & Actions;

/** The workspace as the app opens: as it was left, on the robot it models. */
function initialState(): State {
    const startup = api.startup;
    const robotConfig = startup.robotConfig;
    const saved = savedValues(startup.workspace);
    const dims = {
        ...dimsOf(robotConfig),
        ...(savedDimensions(startup.workspace, robotConfig.name) ?? {}),
    };
    const robot = withDimensions(robotConfig, dims);

    let pose: PoseStore = makePose(robot, pl.standbyState());
    let keyframes: Keyframe[] = [];
    let selected: number | null = null;
    if (saved.pose && saved.pose.robot === robot.name) {
        const p = saved.pose as SavedPose;
        pose = makePose(robot, p.state, p.seq, p.at);
    }
    if (saved.keyframes && saved.keyframes.robot === robot.name) {
        keyframes = kf.numbered(saved.keyframes.keyframes);
        if (saved.selected !== undefined && saved.selected < keyframes.length) {
            selected = saved.selected;
        }
    }
    const duration =
        selected !== null
            ? keyframes[selected].duration_ms
            : (saved.duration ?? kf.DEFAULT_DURATION_MS);
    const ease = selected !== null ? kf.eases(keyframes[selected]) : saved.ease !== "linear";

    return {
        robotConfig,
        dims,
        pose,
        keyframes,
        selected,
        selection: null,
        message: "",
        bodyMode: saved.body_mode ?? "translate",
        duration,
        ease,
        mode: "edit",
        playing: false,
        frame: 0,
        loop: (saved.loop ?? []).includes("loop"),
        speed: saved.speed !== undefined ? speedPct(saved.speed) : SPEED_DEFAULT_PCT,
        gaitSource: saved.gait_source ?? "builtin",
        gaitName: saved.gait_name ?? "",
        userGaits: [],
        userGaitMessage: "",
        robotMessage: "",
        status: startup.status,
        robotIp: saved.robot_ip ?? ROBOT_DEFAULT_IP,
        maxStep: startup.status.max_step,
        driveSpeed: startup.status.speed_pct,
        theme: startup.theme,
        panels: { ...startup.panels },
        connecting: false,
    };
}

export const useStore = create<Store>()((set, get) => {
    /** Apply what an edit changed, then keep the bar beside the keyframes and
     * the pose's place in the sequence in step with it. */
    function commit(out: Out, trigger: Trigger = "other"): void {
        const s = get();
        const frames = out.keyframes ?? s.keyframes;
        const selected = out.selected !== undefined ? out.selected : s.selected;
        let { duration, ease } = out;
        let pose = out.pose;

        // The easing toggle shows the selected keyframe's, as the time field
        // shows its time -- except while it is being clicked.
        if (trigger !== "ease" && selected !== null && selected >= 0 && selected < frames.length) {
            ease = kf.eases(frames[selected]);
        }
        if ("selected" in out && out.selected === null) {
            // Nothing selected any more: the bar is the next keyframe's again,
            // from the usual time and easing.
            duration = kf.DEFAULT_DURATION_MS;
            ease = true;
        }
        // A pose stays "at" its point of the sequence only while the keyframes
        // are as they were and none is selected; then the bar is the keyframe
        // it would become: as far into its move as it is, easing as it does.
        const shown = pose ?? s.pose;
        if (shown.at && (out.keyframes !== undefined || selected !== null)) {
            const { at: _, ...rest } = shown;
            pose = rest;
        } else if (shown.at && trigger === "playhead" && frames.length) {
            duration = Math.max(kf.MIN_DURATION_MS, pyRound(shown.at.ms));
            ease = kf.eases(frames[(shown.at.after + 1) % frames.length]);
        }

        const next: Partial<State> = {};
        if (pose !== undefined) next.pose = pose;
        if (out.keyframes !== undefined) next.keyframes = out.keyframes;
        if (out.selected !== undefined) next.selected = out.selected;
        if (out.message !== undefined) next.message = out.message;
        if (duration !== undefined) next.duration = duration;
        if (ease !== undefined) next.ease = ease;
        if (out.mode !== undefined) {
            next.mode = out.mode;
            // Back to the pose stops playback.
            if (out.mode === "edit") next.playing = false;
        }
        set(next);
    }

    /** A new pose: the sequence number makes it differ from the one before
     * even when the feet do not, so a foot dropped past its leg's reach is
     * still redrawn. A pose edited stays where in the sequence it was taken
     * from. */
    function bump(
        state: pl.PoseState,
        at: PoseStore["at"] | null = get().pose.at ?? null,
    ): PoseStore {
        const s = get();
        return makePose(robotOf(s), state, s.pose.seq + 1, at ?? undefined);
    }

    const robot = () => robotOf(get());
    const frames = () => [...get().keyframes];

    return {
        ...initialState(),

        // ......................
        // The pose
        // ......................

        footTarget({ leg, foot, final }) {
            if (!Number.isInteger(leg) || leg < 0 || leg > 5 || !foot || foot.length !== 3) return;
            const s = get();
            const r = robot();
            const state = s.pose.state;
            // A foot dragged past what its leg can reach is held as near as
            // the leg gets, so the leg follows the cursor along the edge of
            // its reach rather than stopping until the cursor comes back.
            const moved = pl.withFootNear(state, leg, foot, r);
            if (moved === null || pl.solve(moved, r)[2].includes(leg)) {
                // While dragging the foot is left where the cursor has it;
                // once dropped it goes back to the last place it could reach.
                commit({
                    message: `${legLabel(leg)} cannot reach there, or a joint would pass its limit.`,
                    ...(final ? { pose: bump(state) } : {}),
                });
                return;
            }
            const at = pl.viewFeet(moved, r)[leg];
            const held =
                Math.hypot(at[0] - foot[0], at[1] - foot[1], at[2] - foot[2]) > FOOT_HELD_MM;
            commit({
                message: held ? `${legLabel(leg)} is at its limit.` : "",
                ...(final || !deepEqual(moved, state) ? { pose: bump(moved) } : {}),
            });
        },

        jointTarget({ leg, joint, angle, final }) {
            // Like its field, a joint turned by its ring moves the leg's foot
            // to wherever the angle puts it; turned past its limit, it is held
            // a little inside it, so the leg follows the ring up to there.
            const value = finite(angle);
            if (
                !Number.isInteger(leg) ||
                leg < 0 ||
                leg > 5 ||
                !JOINT_NAMES.includes(joint as JointName)
            )
                return;
            if (value === null) return;
            const r = robot();
            const state = get().pose.state;
            const name = joint as JointName;
            const most = pl.jointMost(name, r);
            const held = Math.abs(value) > most;
            const clamped = pyRound(Math.min(Math.max(value, -most), most), 1);
            const moved = pl.withLegAngles(state, leg, { [name]: clamped }, r);
            if (pl.solve(moved, r)[2].includes(leg)) {
                commit({
                    message: `${legLabel(leg)}: ${name} cannot turn there.`,
                    mode: "edit",
                    ...(final ? { pose: bump(state) } : {}),
                });
                return;
            }
            commit({
                message: held ? `${legLabel(leg)}: ${name} is at its limit.` : "",
                mode: "edit",
                ...(final || !deepEqual(moved, state) ? { pose: bump(moved) } : {}),
            });
        },

        bodyTarget({ origin, rot, final }) {
            // Like its sliders, the body dragged in the view goes where it is
            // put, within their range and as far as its legs can follow.
            if (origin?.length !== 3 || rot?.length !== 3) return;
            if (![...origin, ...rot].every((c) => finite(c) !== null)) return;
            const r = robot();
            const state = get().pose.state;
            const [moved, held] = movedBody(state, draggedBody(origin, rot, r), r);
            commit({
                message: held ? BODY_HELD_ALERT : "",
                mode: "edit",
                ...(final || !deepEqual(moved, state) ? { pose: bump(moved) } : {}),
            });
        },

        setSelection(selection) {
            // Something else picked: what was said of the last move is stale.
            const opens = selection !== null;
            set({ selection, message: "" });
            // Picking the body, a foot or a joint opens the pose overlay: the
            // joint angles it moves, and its controls, are in there.
            if (opens && !get().panels.pose) {
                get().setPanel("pose", true, false);
            }
        },

        footFields(values) {
            const leg = pickedLeg(get().selection);
            if (leg === null) return;
            const r = robot();
            const state = get().pose.state;
            // A field left empty, or still showing the rounded value it was
            // given, keeps that coordinate exactly, so typing one does not
            // nudge the others by their rounding.
            const here = pl.viewFeet(state, r)[leg];
            const target = here.map((c, i) => {
                const v = values[i];
                return v === null || v === undefined || v === fieldValue(c) ? c : v;
            });
            const moved = pl.withFootAt(state, leg, target, r);
            if (pl.solve(moved, r)[2].includes(leg)) {
                // The fields go back to where the foot still is.
                commit({
                    message: `${legLabel(leg)} cannot reach there, or a joint would pass its limit.`,
                    mode: "edit",
                    pose: { ...get().pose },
                });
                return;
            }
            commit({ pose: bump(moved), message: "", mode: "edit" });
        },

        jointField(leg, joint, value) {
            if (value === null || !Number.isFinite(value)) {
                set({ pose: { ...get().pose } });
                return;
            }
            const r = robot();
            const moved = pl.withLegAngles(get().pose.state, leg, { [joint]: value }, r);
            if (pl.solve(moved, r)[2].includes(leg)) {
                const sign = value >= 0 ? "+" : "-";
                commit({
                    message: `${legLabel(leg)}: ${joint} ${sign}${Math.abs(value).toFixed(1)}° is past the joint's limit.`,
                    mode: "edit",
                    // The fields go back to the angles the leg still has.
                    pose: { ...get().pose },
                });
                return;
            }
            commit({ pose: bump(moved), message: "", mode: "edit" });
        },

        bodySlider(key, value) {
            const r = robot();
            const state = get().pose.state;
            const body = { ...state.body, [key]: value };
            const [moved, held] = movedBody(state, body, r);
            commit({
                message: held ? BODY_HELD_ALERT : "",
                mode: "edit",
                ...(!deepEqual(moved, state)
                    ? { pose: bump(moved) }
                    : held
                      ? { pose: { ...get().pose } }
                      : {}),
            });
        },

        resetPose() {
            commit({ pose: bump(pl.standbyState()), mode: "edit", message: "" });
        },

        clearFeet() {
            const zero = Array.from({ length: 6 }, () => [0, 0, 0]);
            commit({
                pose: bump(pl.makeState(get().pose.state.body, zero)),
                mode: "edit",
                message: "",
            });
        },

        // ......................
        // The sequence
        // ......................

        addPose() {
            const s = get();
            const r = robot();
            const list = frames();
            const state = s.pose.state;
            const feet = pl.bodyFeet(state, r);
            const at = s.pose.at;
            let index: number;
            if (s.selected === null && at && at.after >= 0 && at.after < list.length) {
                // Taken from where playback came to rest: it goes in there,
                // splitting the move it was on. The time field is its share
                // of the move; the keyframe after it keeps the rest, so
                // everything after is reached when it was. It eases as that
                // move did.
                index = at.after + 1;
                const following = list[index % list.length];
                const share = kf.clampDuration(s.duration);
                const rest = kf.clampDuration(following.duration_ms - share);
                list[index % list.length] = { ...following, duration_ms: rest };
                list.splice(index, 0, kf.makeKeyframe(feet, share, state, kf.eases(following)));
            } else {
                index = s.selected === null ? list.length : s.selected + 1;
                list.splice(
                    index,
                    0,
                    kf.makeKeyframe(feet, s.duration ?? kf.DEFAULT_DURATION_MS, state, s.ease),
                );
            }
            const keyframes = kf.numbered(list);
            commit({
                keyframes,
                selected: index,
                duration: keyframes[index].duration_ms,
                message: "",
            });
        },

        updateKeyframe() {
            const s = get();
            if (s.selected === null) {
                commit({ message: "Pick a keyframe to update." });
                return;
            }
            // It keeps its time and easing.
            const list = frames();
            list[s.selected] = kf.remade(
                list[s.selected],
                pl.bodyFeet(s.pose.state, robot()),
                s.pose.state,
            );
            commit({ keyframes: kf.numbered(list), message: "" });
        },

        deleteKeyframe() {
            const s = get();
            if (s.selected === null) {
                commit({ message: "Pick a keyframe to delete." });
                return;
            }
            const list = frames();
            list.splice(s.selected, 1);
            commit({
                keyframes: kf.numbered(list),
                selected: list.length ? Math.min(s.selected, list.length - 1) : null,
                message: "",
            });
        },

        moveKeyframe(step) {
            // It keeps its number, wherever it goes.
            const s = get();
            if (
                s.selected === null ||
                s.selected + step < 0 ||
                s.selected + step >= s.keyframes.length
            )
                return;
            const list = frames();
            [list[s.selected], list[s.selected + step]] = [
                list[s.selected + step],
                list[s.selected],
            ];
            commit({ keyframes: kf.numbered(list), selected: s.selected + step });
        },

        renumber() {
            if (get().keyframes.length) {
                commit({ keyframes: kf.renumbered(get().keyframes) });
            }
        },

        selectKeyframe(index) {
            const list = get().keyframes;
            if (index < 0 || index >= list.length) return;
            commit({
                selected: index,
                pose: bump(keyframeState(list[index], robot())),
                duration: list[index].duration_ms,
                mode: "edit",
                message: "",
            });
        },

        setDuration(value) {
            // Retimes the selected keyframe, and nothing else about it. With
            // none selected, the time waits for the next + Add. The field shows
            // the time as it is kept: in range, and a field left empty goes
            // back to what it was.
            const s = get();
            if (value === null || !Number.isFinite(value)) {
                commit({
                    duration:
                        s.selected === null
                            ? kf.DEFAULT_DURATION_MS
                            : s.keyframes[s.selected].duration_ms,
                });
                return;
            }
            const durationMs = kf.clampDuration(value);
            const out: Out = { duration: durationMs };
            if (s.selected !== null && s.keyframes[s.selected].duration_ms !== durationMs) {
                const list = frames();
                list[s.selected] = { ...list[s.selected], duration_ms: durationMs };
                out.keyframes = kf.numbered(list);
            }
            commit(out);
        },

        setEase(ease) {
            // Whether the move into the selected keyframe eases. With none
            // selected, it waits for the next + Add.
            const s = get();
            if (s.selected === null) {
                set({ ease });
                return;
            }
            const out: Out = { ease };
            if (kf.eases(s.keyframes[s.selected]) !== ease) {
                const list = frames();
                list[s.selected] = kf.withEase(list[s.selected], ease);
                out.keyframes = kf.numbered(list);
            }
            commit(out, "ease");
        },

        async insertGait(source, id, replace) {
            // A gait from the library, the robot's or one's own, as its
            // keyframes. Its + puts them in where a pose would go, after the
            // one selected, selecting the last so another follows on. Its ⇄
            // makes them the whole sequence, selecting the last too, which
            // becomes the pose, so a gait added next goes on after it.
            const r = robot();
            let inserted: Keyframe[] = [];
            if (source === "builtin") {
                inserted = gaitKeyframes(id, r);
            } else {
                const loaded = await api.loadGait(id, r.name);
                if (loaded.error || !loaded.keyframes) {
                    commit({ message: loaded.error ?? "Could not read the gait." });
                    return;
                }
                inserted = loaded.keyframes;
            }
            if (!inserted.length) return;
            if (replace) {
                const keyframes = kf.numbered(inserted);
                const last = keyframes.length - 1;
                commit({
                    keyframes,
                    selected: last,
                    pose: bump(keyframeState(keyframes[last], r)),
                    duration: keyframes[last].duration_ms,
                    mode: "edit",
                    message: "",
                });
                return;
            }
            // Put into a sequence, they are numbered after what is there.
            const s = get();
            const list = frames();
            const index = s.selected === null ? list.length : s.selected + 1;
            list.splice(index, 0, ...kf.unnumbered(inserted));
            const keyframes = kf.numbered(list);
            const selected = index + inserted.length - 1;
            commit({ keyframes, selected, duration: keyframes[selected].duration_ms, message: "" });
        },

        loadKeyframes(text) {
            const r = robot();
            let loaded: Keyframe[];
            try {
                loaded = kf.load(text, r);
            } catch (error) {
                commit({ message: (error as Error).message });
                return;
            }
            commit({
                keyframes: loaded,
                selected: loaded.length ? 0 : null,
                ...(loaded.length
                    ? { pose: bump(keyframeState(loaded[0], r)), duration: loaded[0].duration_ms }
                    : {}),
                mode: "edit",
                message: "",
            });
        },

        async saveKeyframes() {
            const s = get();
            if (!s.keyframes.length) return;
            await api.saveKeyframes(
                `${s.robotConfig.name}-keyframes.json`,
                kf.dump(s.keyframes, s.robotConfig),
            );
        },

        // ......................
        // Playback
        // ......................

        play() {
            // Playing always shows the sequence; pausing makes the frame it
            // stopped on the pose.
            const s = get();
            const playing = !s.playing;
            if (playing) {
                set({ playing, mode: "preview", frame: s.frame >= maxFrameOf(s) ? 0 : s.frame });
            } else {
                set({ playing });
                get().playhead(s.frame);
            }
        },

        tick() {
            // One preview frame per tick, stopping at the end unless looping.
            const s = get();
            const max = maxFrameOf(s);
            const next = s.frame + 1;
            if (next <= max) {
                set({ frame: next });
            } else if (s.loop) {
                set({ frame: 0 });
            } else {
                // Run out: the last frame becomes the pose.
                set({ frame: max, playing: false });
                get().playhead(max);
            }
        },

        scrub(frame) {
            set({ frame });
        },

        grabScrubber() {
            // Grabbing the scrubber is asking to see the sequence, as Play is.
            set({ mode: "preview" });
        },

        releaseScrubber() {
            // Letting go makes the frame it was left on the pose, as pausing does.
            get().playhead(get().frame);
        },

        playhead(frame) {
            // Playback came to rest: the frame it stopped on becomes the pose.
            // On a keyframe, that keyframe is selected, as if clicked; between
            // two, nothing is, and the pose remembers where it is in the
            // sequence, for + Add pose to put it there.
            const s = get();
            const preview = previewOf(s);
            const list = s.keyframes;
            if (preview.count !== list.length || frame < 0 || frame >= preview.states.length)
                return;
            const [start, end, ms] = preview.times[frame];
            const moveMs = kf.clampDuration(list[end].duration_ms);
            const onKeyframe = ms < 0.5 ? start : moveMs - ms < 0.5 ? end : null;
            if (onKeyframe !== null) {
                commit(
                    {
                        selected: onKeyframe,
                        pose: bump(keyframeState(list[onKeyframe], robot()), null),
                        duration: list[onKeyframe].duration_ms,
                        mode: "edit",
                        message: "",
                    },
                    "playhead",
                );
                return;
            }
            const raw = preview.states[frame];
            commit(
                {
                    selected: null,
                    pose: bump(pl.makeState(raw.body, raw.offsets), {
                        after: start,
                        ms: pyRound(ms, 1),
                    }),
                    mode: "edit",
                    message: "",
                },
                "playhead",
            );
        },

        setLoop(loop) {
            set({ loop, frame: 0 });
        },

        setSpeed(value) {
            set({ speed: speedPct(value), frame: 0 });
        },

        // ......................
        // The robot
        // ......................

        setDims(name, value) {
            set({ dims: { ...get().dims, [name]: value }, frame: 0 });
        },

        async toggleConnection() {
            const s = get();
            set({ connecting: true });
            try {
                const update = s.status.connected
                    ? await api.disconnect()
                    : await api.connect(s.robotIp);
                const next: Partial<State> = {
                    status: update.status,
                    maxStep: update.status.max_step,
                };
                if (update.status.config_version !== s.status.config_version) {
                    // A robot connecting brings its own measurements, and the
                    // editor starts afresh on a robot other than the last.
                    const config = update.robotConfig;
                    next.robotConfig = config;
                    next.dims = dimsOf(config);
                    next.driveSpeed = update.status.speed_pct;
                    if (config.name !== s.robotConfig.name) {
                        next.pose = makePose(withDimensions(config, next.dims), pl.standbyState());
                        next.keyframes = [];
                        next.selected = null;
                        next.duration = kf.DEFAULT_DURATION_MS;
                        next.ease = true;
                        next.mode = "edit";
                        next.playing = false;
                        next.frame = 0;
                    }
                }
                set(next);
            } finally {
                set({ connecting: false });
            }
        },

        async pollStatus() {
            const status = await api.status();
            const s = get();
            const next: Partial<State> = { status };
            if (!status.connected && s.robotMessage) {
                // What came of the last run no longer holds once the robot
                // is gone.
                next.robotMessage = "";
            }
            if (status.speed_pct !== s.driveSpeed) next.driveSpeed = status.speed_pct;
            if (status.max_step !== s.maxStep) next.maxStep = status.max_step;
            set(next);
        },

        async setStreaming(on) {
            // Streaming cannot be switched on while disconnected, so the
            // switch shows what the link accepted.
            const streaming = await api.setStreaming(on);
            set({ status: { ...get().status, streaming } });
        },

        setMaxStep(maxStep) {
            set({ maxStep });
            void api.setMaxStep(maxStep);
        },

        async setDriveSpeed(pct) {
            // How fast the robot plays its own gaits: sent to it now, and
            // carried by every motion command. Set without a robot too, so the
            // next one connected starts at it.
            set({ driveSpeed: pct });
            const applied = await api.setMotionSpeed(pct);
            set({ driveSpeed: applied });
        },

        async runOnRobot() {
            const s = get();
            if (!s.status.connected) {
                set({ robotMessage: "Not connected — connect to a robot first." });
                return;
            }
            const r = robot();
            if (!s.keyframes.length) {
                set({ robotMessage: "Add a pose or a gait first." });
                return;
            }
            // The robot gets frames at the rate it plays its own gaits at full
            // speed, so the sequence is as smooth as they are, and in real
            // time: the durations as asked, scaled by the playback speed.
            const speed = speedPct(s.speed) / 100;
            const fps = getSequenceFps(r, 100);
            const { poses, badFrames } = pl.sequence(s.keyframes, r, fps, s.loop, true, speed);
            if (badFrames.length) {
                set({
                    robotMessage:
                        "Not sent: part of the sequence is out of reach (see the preview).",
                });
                return;
            }
            if (!(await api.playSequence(poses, s.loop, fps))) {
                set({ robotMessage: "Nothing to send." });
                return;
            }
            const seconds = kf.sequenceDurationMs(s.keyframes, s.loop, speed) / 1000;
            set({
                robotMessage:
                    `Streaming ${s.keyframes.length} keyframes — ${seconds.toFixed(2)} s` +
                    `${speed !== 1 ? ` at ${Math.round(speed * 100)} %` : ""}` +
                    `${s.loop ? ", looping" : ""}.`,
            });
        },

        async stopOnRobot() {
            if (!get().status.connected) {
                set({ robotMessage: "Not connected." });
                return;
            }
            await api.stopSequence();
            await api.sendMotion("standby");
            set({ robotMessage: "Robot returning to standby." });
        },

        // ......................
        // The rest
        // ......................

        set(values) {
            set(values);
        },

        async listUserGaits() {
            set({ userGaits: await api.listGaits(get().robotConfig.name) });
        },

        async saveUserGait() {
            // Keep the whole sequence as a gait of one's own, under the name typed.
            const s = get();
            const result = await api.saveGait(s.gaitName, s.keyframes, s.robotConfig.name);
            if (result.error) {
                set({ userGaitMessage: result.error });
                return;
            }
            set({ gaitName: "", userGaitMessage: "" });
            await get().listUserGaits();
        },

        async deleteUserGait(id) {
            await api.deleteGait(id);
            set({ userGaitMessage: "" });
            await get().listUserGaits();
        },

        toggleTheme() {
            const theme = get().theme === "dark" ? "light" : "dark";
            const root = document.documentElement;
            root.setAttribute("data-theme", theme);
            root.setAttribute("data-bs-theme", theme);
            api.saveTheme(theme);
            set({ theme });
        },

        setPanel(key, open, keep) {
            set({ panels: { ...get().panels, [key]: open } });
            // Only one folded or opened by hand is kept; one opened by picking
            // something starts folded again the next time.
            if (keep) {
                api.savePanels({ [key]: open });
            }
        },
    };
});

/** The pose as the robot link gets it, when it changes and can be posed. */
export function followPose(): () => void {
    let lastKey = "";
    return useStore.subscribe((s) => {
        const solved = solvedOf(s);
        const key = `${s.pose.robot}|${s.pose.seq}|${JSON.stringify(s.dims)}`;
        // Only a pose that has changed: sending cancels a sequence the robot
        // is running.
        if (key !== lastKey && !solved.bad.length) {
            lastKey = key;
            api.sendPose(solved.pose);
        }
    });
}

/** Keep what the workspace shows with the preferences as it changes, under
 * the names (and in the shapes) the app has always kept them. */
export function keepWorkspace(): () => void {
    const kept = (s: State): Record<string, unknown> => ({
        pose: s.pose,
        keyframes: { robot: s.pose.robot, keyframes: s.keyframes },
        selected: s.selected,
        body_mode: s.bodyMode,
        gait_source: s.gaitSource,
        gait_name: s.gaitName,
        duration: s.duration,
        ease: s.ease ? "ease" : "linear",
        speed: s.speed,
        loop: s.loop ? ["loop"] : [],
        robot_ip: s.robotIp,
        max_step: s.maxStep,
        drive_speed: s.driveSpeed,
        dimensions: { robot: s.robotConfig.name, values: s.dims },
    });
    let last = kept(useStore.getState());
    let timer: ReturnType<typeof setTimeout> | null = null;
    let pending: Record<string, unknown> = {};
    return useStore.subscribe((s) => {
        const now = kept(s);
        for (const [key, value] of Object.entries(now)) {
            if (value !== last[key] && !deepEqual(value, last[key])) {
                pending[key] = value;
            }
        }
        last = now;
        if (Object.keys(pending).length && !timer) {
            timer = setTimeout(() => {
                api.saveWorkspace(pending);
                pending = {};
                timer = null;
            }, 300);
        }
    });
}
