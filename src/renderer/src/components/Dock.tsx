// The dock, across the bottom of the window: the sequence -- the track of
// keyframes, poses and moves put in as theirs -- and an editor for the one
// selected. Its Library button, or the empty track's, calls up the library
// over the window: the robot's gaits and one's own saved moves, to put into
// the sequence.

import { useCallback, useEffect, useRef, useState } from "react";
import * as kf from "../../../shared/keyframes";
import { GAIT_LABELS, GAIT_MENU } from "../../../shared/motions";
import { api } from "../api";
import { previewOf, useStore } from "../state/store";
import { MAX_NAME_LENGTH_HINT } from "./limits";
import { Button, FieldLabel, NumberInput, Segmented } from "./widgets";

const INSERT_TITLE = "Add it to the sequence, after the keyframe selected or at the end";
const REPLACE_TITLE = "Replace the whole sequence with it";

function Section({
    title,
    head,
    className,
    children,
}: {
    title: string;
    head?: React.ReactNode;
    className: string;
    children: React.ReactNode;
}) {
    return (
        <section className={`dock-section ${className}`}>
            <div className="dock-section-head">
                <h6 className="dock-section-title">{title}</h6>
                {head}
            </div>
            {children}
        </section>
    );
}

function LibraryRow({
    gait,
    label,
    note,
    onInsert,
    onReplace,
    extra,
}: {
    gait?: string;
    label: string;
    note?: string;
    onInsert: () => void;
    onReplace: () => void;
    extra?: React.ReactNode;
}) {
    return (
        <div className="dock-gait-row" data-gait={gait}>
            <div className="dock-gait-text">
                <span className="dock-gait-name">{label}</span>
                {note && <span className="dock-gait-note">{note}</span>}
            </div>
            <Button outline className="dock-gait-btn" title={INSERT_TITLE} onClick={onInsert}>
                +
            </Button>
            <Button outline className="dock-gait-btn" title={REPLACE_TITLE} onClick={onReplace}>
                ⇄
            </Button>
            {extra}
        </div>
    );
}

/** The library, over the whole window: the robot's gaits, body moves and
 * postures, and one's own saved moves. Putting one into the sequence closes
 * it, so the new keyframes are in sight; so does Esc, ×, or a click beside it. */
function LibraryDialog({ onClose }: { onClose: () => void }) {
    const source = useStore((s) => s.gaitSource);
    const gaitName = useStore((s) => s.gaitName);
    const userGaits = useStore((s) => s.userGaits);
    const message = useStore((s) => s.userGaitMessage);
    const robotName = useStore((s) => s.robotConfig.name);
    const robotLabel = useStore((s) => s.robotConfig.label || s.robotConfig.name);
    const empty = useStore((s) => !s.keyframes.length);
    const store = useStore.getState();
    const panel = useRef<HTMLDivElement>(null);

    // One's own moves for the robot modelled, read afresh each time it opens;
    // a saved move belongs to the robot it was made on.
    useEffect(() => {
        void useStore.getState().listUserGaits();
    }, [robotName]);

    useEffect(() => {
        panel.current?.focus();
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                e.stopPropagation();
                onClose();
            }
        };
        document.addEventListener("keydown", onKey, true);
        return () => document.removeEventListener("keydown", onKey, true);
    }, [onClose]);

    const pick = (kind: "builtin" | "mine", id: string, replace: boolean) => {
        void store.insertGait(kind, id, replace);
        onClose();
    };

    return (
        <div
            className="library-backdrop"
            onPointerDown={(e) => {
                if (e.target === e.currentTarget) onClose();
            }}
        >
            <div
                id="library-dialog"
                className="library-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="library-dialog-title"
                tabIndex={-1}
                ref={panel}
            >
                <div className="dock-section-head">
                    <h6 id="library-dialog-title" className="dock-section-title">
                        Library
                    </h6>
                    <Segmented
                        id="pose-gait-source"
                        className="dock-seg dock-push"
                        options={[
                            { label: "Built in", value: "builtin" },
                            { label: "Saved", value: "mine" },
                        ]}
                        value={source}
                        onChange={(gaitSource) => store.set({ gaitSource })}
                    />
                    <Button
                        id="library-close-btn"
                        outline
                        className="library-close"
                        title="Close the library"
                        onClick={onClose}
                    >
                        ×
                    </Button>
                </div>
                <p className="library-hint">
                    + puts it after the keyframe selected, or at the end; ⇄ swaps the whole sequence
                    for it.
                </p>
                {source === "builtin" ? (
                    <div id="pose-gait-list-builtin" className="dock-gait-list">
                        {GAIT_MENU.map(([group, motions]) => [
                            <div className="dock-gait-group" key={group}>
                                {group}
                            </div>,
                            ...motions.map((motion) => (
                                <LibraryRow
                                    key={motion}
                                    gait={motion}
                                    label={GAIT_LABELS[motion]}
                                    onInsert={() => pick("builtin", motion, false)}
                                    onReplace={() => pick("builtin", motion, true)}
                                />
                            )),
                        ])}
                    </div>
                ) : (
                    <div id="pose-gait-list-mine" className="dock-gait-mine">
                        {/* Keeps the whole sequence under the name; a saved move
                            of that name already there is replaced. */}
                        <div className="dock-gait-save">
                            <input
                                id="pose-user-gait-name"
                                className="form-control-sm form-control"
                                placeholder="Name"
                                maxLength={MAX_NAME_LENGTH_HINT}
                                value={gaitName}
                                onChange={(e) => store.set({ gaitName: e.target.value })}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter") void store.saveUserGait();
                                }}
                            />
                            <Button
                                id="pose-user-gait-save-btn"
                                color="primary"
                                disabled={empty}
                                title="Keep the current sequence in the library"
                                onClick={() => void store.saveUserGait()}
                            >
                                Save current
                            </Button>
                        </div>
                        <div id="pose-user-gait-message" className="dock-message">
                            {message && <div className="ind-alert mb-3">⚠ {message}</div>}
                        </div>
                        <div id="pose-user-gait-list" className="dock-gait-list">
                            {userGaits.length ? (
                                userGaits.map((gait) => (
                                    <LibraryRow
                                        key={gait.id}
                                        label={gait.name}
                                        note={`${gait.count} keyframe${gait.count !== 1 ? "s" : ""} · ${(gait.duration_ms / 1000).toFixed(2)} s`}
                                        onInsert={() => pick("mine", gait.id, false)}
                                        onReplace={() => pick("mine", gait.id, true)}
                                        extra={
                                            // It asks first: the file is gone for good.
                                            <Button
                                                outline
                                                className="dock-gait-btn dock-gait-delete"
                                                title="Delete this saved move"
                                                onClick={() => {
                                                    if (
                                                        window.confirm(
                                                            `Delete the saved move '${gait.name}'? This cannot be undone.`,
                                                        )
                                                    ) {
                                                        void store.deleteUserGait(gait.id);
                                                    }
                                                }}
                                            >
                                                ×
                                            </Button>
                                        }
                                    />
                                ))
                            ) : (
                                <div className="dock-empty">
                                    Save the current sequence to reuse it. Saved moves are kept for{" "}
                                    {robotLabel} and listed here.
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

function EaseIcon({ eased }: { eased: boolean }) {
    return <span className={`ind-ease-icon ${eased ? "is-eased" : "is-linear"}`} />;
}

function EaseChoice({
    id,
    ease,
    onChange,
}: {
    id: string;
    ease: boolean;
    onChange: (ease: boolean) => void;
}) {
    return (
        <div title="Ease: start and stop the move into this keyframe gently. Linear: run it at a steady speed, as a gait's moves do.">
            <Segmented
                id={id}
                options={[
                    {
                        label: (
                            <>
                                <EaseIcon eased />
                                Ease
                            </>
                        ),
                        value: "ease",
                    },
                    {
                        label: (
                            <>
                                <EaseIcon eased={false} />
                                Linear
                            </>
                        ),
                        value: "linear",
                    },
                ]}
                value={ease ? "ease" : "linear"}
                onChange={(v) => onChange(v === "ease")}
            />
        </div>
    );
}

type Confirming = "add" | "save" | "delete";

/** Asks before the pose is added, saved over a keyframe, or a keyframe is
 * deleted. Adding or saving also asks how the keyframe is reached: its time
 * and easing, starting from the bar's. Enter confirms; Esc, Cancel or a click
 * beside it does nothing. */
function ConfirmDialog({
    kind,
    title,
    message,
    action,
    duration: initialDuration,
    ease: initialEase,
    durationLabel,
    onConfirm,
    onClose,
}: {
    kind: Confirming;
    title: string;
    message: string;
    action: string;
    duration: number;
    ease: boolean;
    durationLabel: string;
    onConfirm: (how: { duration: number; ease: boolean }) => void;
    onClose: () => void;
}) {
    const [duration, setDuration] = useState(initialDuration);
    const [ease, setEase] = useState(initialEase);
    const panel = useRef<HTMLDivElement>(null);
    const timed = kind !== "delete";
    const confirm = () => {
        onConfirm({ duration, ease });
        onClose();
    };
    const confirmRef = useRef(confirm);
    confirmRef.current = confirm;

    useEffect(() => {
        panel.current?.focus();
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                e.stopPropagation();
                onClose();
            } else if (e.key === "Enter" && !(e.target instanceof HTMLInputElement)) {
                // In the time field, Enter only takes the time typed.
                e.preventDefault();
                e.stopPropagation();
                confirmRef.current();
            }
        };
        document.addEventListener("keydown", onKey, true);
        return () => document.removeEventListener("keydown", onKey, true);
    }, [onClose]);

    return (
        <div
            className="library-backdrop"
            onPointerDown={(e) => {
                if (e.target === e.currentTarget) onClose();
            }}
        >
            <div
                id="confirm-dialog"
                className="library-dialog confirm-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="confirm-dialog-title"
                aria-describedby="confirm-dialog-message"
                data-kind={kind}
                tabIndex={-1}
                ref={panel}
            >
                <div className="dock-section-head">
                    <h6 id="confirm-dialog-title" className="dock-section-title">
                        {title}
                    </h6>
                </div>
                <p id="confirm-dialog-message" className="confirm-message">
                    {message}
                </p>
                {timed && (
                    <div className="confirm-fields">
                        <div
                            className="dock-inline-field"
                            title={`Time to reach this keyframe from the one before it, ${kf.MIN_DURATION_MS} to ${kf.MAX_DURATION_MS} ms.`}
                        >
                            <FieldLabel id="confirm-duration-label">{durationLabel}</FieldLabel>
                            <div className="ind-duration-input input-group input-group-sm">
                                <NumberInput
                                    id="confirm-duration"
                                    className="form-control"
                                    value={duration}
                                    onCommit={(v) =>
                                        setDuration(
                                            v === null || !Number.isFinite(v)
                                                ? duration
                                                : kf.clampDuration(v),
                                        )
                                    }
                                />
                                <span className="input-group-text">ms</span>
                            </div>
                        </div>
                        <EaseChoice id="confirm-ease" ease={ease} onChange={setEase} />
                    </div>
                )}
                <div className="confirm-actions">
                    <Button id="confirm-cancel-btn" outline onClick={onClose}>
                        Cancel
                    </Button>
                    <Button
                        id="confirm-ok-btn"
                        color={kind === "delete" ? "danger" : "primary"}
                        onClick={confirm}
                    >
                        {action}
                    </Button>
                </div>
            </div>
        </div>
    );
}

function linkTitle(frames: kf.Keyframe[], index: number, loop: boolean): string {
    const frame = frames[index];
    const how = kf.eases(frame) ? "eased" : "linear";
    const name = kf.label(frame);
    if (index) {
        return `${kf.label(frames[index - 1])} to ${name}: ${frame.duration_ms} ms, ${how}`;
    }
    if (frames.length < 2) {
        return `Back round to ${name}: used when the sequence loops`;
    }
    const back = `Back from ${kf.label(frames[frames.length - 1])} to ${name}: ${frame.duration_ms} ms, ${how}`;
    return loop ? back : `${back}. Only used when Loop is on.`;
}

/** The keyframe track: each keyframe behind the arrow into it -- how long the
 * move takes, and whether it eases -- with when it is reached. While the
 * sequence plays in the view, or is scrubbed, the arrow into the keyframe it
 * is heading for fills as it goes, and the keyframe it is on is marked. */
function Track({ onLibrary }: { onLibrary: () => void }) {
    const frames = useStore((s) => s.keyframes);
    const selected = useStore((s) => s.selected);
    const loop = useStore((s) => s.loop);
    const mode = useStore((s) => s.mode);
    const frame = useStore((s) => s.frame);
    const preview = useStore(previewOf);
    const strip = useRef<HTMLDivElement>(null);

    let playing: { index: number; progress: number } | null = null;
    if (mode === "preview" && preview.count === frames.length && preview.times.length) {
        const [start, end, ms] =
            preview.times[Math.min(Math.max(frame, 0), preview.times.length - 1)];
        const move = Math.max(frames[end].duration_ms, 1);
        playing = { index: end, progress: start === end ? 1 : Math.min(ms / move, 1) };
    }

    // Keep the keyframe playing in sight in the track, which scrolls down a
    // long sequence.
    useEffect(() => {
        if (!playing || !strip.current) return;
        const item = strip.current.querySelector(
            `[data-kf="${playing.index}"]`,
        ) as HTMLElement | null;
        const s = strip.current;
        if (!item) return;
        const top = item.offsetTop;
        if (top < s.scrollTop || top + item.offsetHeight > s.scrollTop + s.clientHeight) {
            s.scrollTop = top - 4;
        }
    });

    if (!frames.length) {
        return (
            <div id="pose-keyframe-list" className="ind-kf-strip" ref={strip}>
                <div className="dock-empty">
                    No keyframes yet: pose the robot in the view and + Add pose, or start from a
                    built-in or saved move in the library.
                    <div className="mt-2">
                        <Button id="pose-library-start-btn" outline onClick={onLibrary}>
                            Start from the library…
                        </Button>
                    </div>
                </div>
            </div>
        );
    }
    const times = kf.keyframeTimesMs(frames);
    return (
        <div id="pose-keyframe-list" className="ind-kf-strip" ref={strip}>
            {frames.map((f, index) => {
                const first = index === 0;
                const eased = kf.eases(f);
                const idle = first && (!loop || frames.length < 2);
                const linkClass = ["ind-kf-link", eased ? "is-eased" : "is-linear"];
                if (first) linkClass.push("is-loop");
                if (idle) linkClass.push("is-idle");
                const isPlaying = playing?.index === index;
                return (
                    <button
                        type="button"
                        key={f.number ?? index}
                        className={`ind-kf-item${index === selected ? " active" : ""}`}
                        data-kf={index}
                        {...(isPlaying
                            ? { "data-playing": playing!.progress >= 0.999 ? "at" : "moving" }
                            : {})}
                        style={
                            isPlaying
                                ? ({
                                      "--kf-progress": playing!.progress.toFixed(3),
                                  } as React.CSSProperties)
                                : undefined
                        }
                        onClick={() => useStore.getState().selectKeyframe(index)}
                    >
                        <span
                            className={linkClass.join(" ")}
                            title={linkTitle(frames, index, loop)}
                        >
                            <span className="ind-kf-link-label">
                                {first && <span className="ind-kf-loop">↺</span>}
                                {`${f.duration_ms} ms`}
                            </span>
                            <span className="ind-kf-link-line">
                                <EaseIcon eased={eased} />
                                <span className="ind-kf-arrow" />
                            </span>
                        </span>
                        <span
                            className="ind-kf-card"
                            title={`Keyframe ${kf.label(f)}: load it into the pose`}
                        >
                            <span className="ind-kf-index">{kf.label(f)}</span>
                            <span className="ind-kf-time">
                                {(times[index] / 1000).toFixed(2)} s
                            </span>
                        </span>
                    </button>
                );
            })}
        </div>
    );
}

/** The bar beside the track: the keyframe selected -- what it is and how it
 * is reached -- then what can be done to it, then adding the pose after it.
 * With none selected, the time and easing are the next one's. */
function Editor() {
    const frames = useStore((s) => s.keyframes);
    const selected = useStore((s) => s.selected);
    const at = useStore((s) => s.pose.at);
    const duration = useStore((s) => s.duration);
    const ease = useStore((s) => s.ease);
    const store = useStore.getState();

    let label = "New keyframe";
    let position = "";
    let field = "Transition";
    let add = "+ Add pose";
    if (selected !== null && selected < frames.length) {
        const name = kf.label(frames[selected]);
        label = `Keyframe ${name}`;
        position = `${selected + 1} of ${frames.length}`;
        // The first keyframe's time is the move back round to it.
        field = selected === 0 ? "Loop back" : "Transition";
        add = selected === frames.length - 1 ? "+ Add pose" : `+ Insert after ${name}`;
    } else if (at && at.after >= 0 && at.after < frames.length) {
        const seconds = ((kf.keyframeTimesMs(frames)[at.after] + at.ms) / 1000).toFixed(2);
        label = `New keyframe at ${seconds} s`;
        add = `+ Add pose at ${seconds} s`;
    }
    const none = selected === null;
    const name = none ? "" : kf.label(frames[selected]);
    const [confirming, setConfirming] = useState<Confirming | null>(null);
    const closeConfirm = useCallback(() => setConfirming(null), []);

    let dialog: React.ReactNode = null;
    if (confirming === "add") {
        const where =
            add === "+ Add pose"
                ? "at the end of the sequence"
                : add.replace(/^\+ (Insert|Add pose) /, "");
        dialog = (
            <ConfirmDialog
                kind="add"
                title="Add pose"
                message={`Record the pose as a new keyframe ${where}?`}
                action="Add pose"
                durationLabel="Transition"
                duration={duration ?? kf.DEFAULT_DURATION_MS}
                ease={ease}
                onConfirm={(how) => store.addPose(how)}
                onClose={closeConfirm}
            />
        );
    } else if (confirming === "save" && !none) {
        dialog = (
            <ConfirmDialog
                kind="save"
                title={`Save pose to ${name}`}
                message={`Overwrite keyframe ${name} with the pose?`}
                action="Save"
                durationLabel={selected === 0 ? "Loop back" : "Transition"}
                duration={frames[selected].duration_ms}
                ease={kf.eases(frames[selected])}
                onConfirm={(how) => store.updateKeyframe(how)}
                onClose={closeConfirm}
            />
        );
    } else if (confirming === "delete" && !none) {
        dialog = (
            <ConfirmDialog
                kind="delete"
                title={`Delete ${name}`}
                message={`Delete keyframe ${name} from the sequence?`}
                action="Delete"
                durationLabel=""
                duration={0}
                ease
                onConfirm={() => store.deleteKeyframe()}
                onClose={closeConfirm}
            />
        );
    }

    return (
        <div className="dock-kf-editor">
            {dialog}
            <div className="dock-kf-title">
                <span id="pose-keyframe-editor-label" className="dock-kf-label">
                    {label}
                </span>
                <span id="pose-keyframe-position" className="dock-note">
                    {position}
                </span>
            </div>
            <div
                className="dock-inline-field"
                title={`Time to reach this keyframe from the one before it, ${kf.MIN_DURATION_MS} to ${kf.MAX_DURATION_MS} ms. The first keyframe's is the move back round to it, used when looping.`}
            >
                <FieldLabel id="pose-duration-label">{field}</FieldLabel>
                <div className="ind-duration-input input-group input-group-sm">
                    <NumberInput
                        id="pose-duration"
                        className="form-control"
                        value={duration}
                        onCommit={store.setDuration}
                    />
                    <span className="input-group-text">ms</span>
                </div>
            </div>
            <EaseChoice id="pose-keyframe-ease" ease={ease} onChange={store.setEase} />
            <div className="dock-group">
                <Button
                    id="pose-update-btn"
                    outline
                    disabled={none}
                    title="Overwrite the selected keyframe with the pose"
                    onClick={() => setConfirming("save")}
                >
                    {none ? "Save pose" : `Save pose to ${name}`}
                </Button>
                <div className="btn-group">
                    <Button
                        id="pose-earlier-btn"
                        outline
                        disabled={none || selected === 0}
                        title="Move earlier in the sequence; it keeps its number"
                        onClick={() => store.moveKeyframe(-1)}
                    >
                        ◀
                    </Button>
                    <Button
                        id="pose-later-btn"
                        outline
                        disabled={none || selected === frames.length - 1}
                        title="Move later in the sequence; it keeps its number"
                        onClick={() => store.moveKeyframe(1)}
                    >
                        ▶
                    </Button>
                </div>
                <Button
                    id="pose-delete-btn"
                    color="danger"
                    outline
                    disabled={none}
                    title="Delete the selected keyframe"
                    onClick={() => setConfirming("delete")}
                >
                    Delete
                </Button>
            </div>
            <Button
                id="pose-add-btn"
                color="primary"
                className="dock-add-btn dock-push"
                title="Record the pose as a keyframe"
                onClick={() => setConfirming("add")}
            >
                {add}
            </Button>
        </div>
    );
}

function Sequence({ onLibrary }: { onLibrary: () => void }) {
    const frames = useStore((s) => s.keyframes);
    const loop = useStore((s) => s.loop);
    const preview = useStore(previewOf);
    const store = useStore.getState();
    const total = kf.sequenceDurationMs(frames, loop) / 1000;
    const summary = frames.length
        ? `${frames.length} keyframe${frames.length !== 1 ? "s" : ""} · ${total.toFixed(2)} s`
        : "";
    const inOrder = frames.every((f, i) => kf.numberOf(f) === i + 1);
    const bad = preview.badFrames;
    return (
        <Section
            title="Sequence"
            className="dock-sequence"
            head={
                <>
                    <div id="pose-keyframe-summary" className="dock-note">
                        {summary}
                    </div>
                    <div className="dock-group dock-push">
                        <Button
                            id="pose-library-btn"
                            color="primary"
                            title="Add a built-in or saved move to the sequence, or save the sequence as one"
                            onClick={onLibrary}
                        >
                            Library…
                        </Button>
                        <Button
                            id="pose-renumber-btn"
                            outline
                            disabled={inOrder}
                            title="Number the keyframes 1, 2, 3… in their order"
                            onClick={store.renumber}
                        >
                            Renumber
                        </Button>
                        <Button
                            id="pose-load-btn"
                            outline
                            title="Load keyframes from a file"
                            onClick={async () => {
                                const text = await api.openKeyframes();
                                if (text !== null) store.loadKeyframes(text);
                            }}
                        >
                            Load…
                        </Button>
                        <Button
                            id="pose-save-btn"
                            outline
                            title="Save the keyframes to a file"
                            onClick={() => void store.saveKeyframes()}
                        >
                            Save…
                        </Button>
                    </div>
                </>
            }
        >
            <div className="dock-part dock-part-stack">
                <Track onLibrary={onLibrary} />
                <Editor />
            </div>
            <div id="pose-preview-message" className="dock-message">
                {bad.length > 0 && (
                    <div className="ind-alert mb-3">
                        ⚠ {bad.length} of {preview.poses.length} frames pass out of reach between
                        keyframes. Add a keyframe in between to route the feet around.
                    </div>
                )}
            </div>
        </Section>
    );
}

export function Dock() {
    const [library, setLibrary] = useState(false);
    const open = useCallback(() => setLibrary(true), []);
    const close = useCallback(() => setLibrary(false), []);
    return (
        <div className="dock">
            <div className="dock-col dock-col-sequence">
                <Sequence onLibrary={open} />
            </div>
            {library && <LibraryDialog onClose={close} />}
        </div>
    );
}
