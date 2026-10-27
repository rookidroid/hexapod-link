// The dock: two columns across the bottom of the window. On the left, the
// library of gaits to put into the sequence: the robot's, and one's own. On
// the right, the sequence: the track of keyframes -- poses, and gaits put in
// as theirs -- and an editor for the one selected. The library's width can be
// dragged; the sequence takes what is left.

import { useEffect, useRef } from "react";
import * as kf from "../../../shared/keyframes";
import { GAIT_LABELS, GAIT_MENU } from "../../../shared/motions";
import { api } from "../api";
import { previewOf, useStore } from "../state/store";
import { MAX_NAME_LENGTH_HINT } from "./limits";
import { Splitter } from "./Splitter";
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

function GaitRow({
    label,
    note,
    onInsert,
    onReplace,
    extra,
}: {
    label: string;
    note?: string;
    onInsert: () => void;
    onReplace: () => void;
    extra?: React.ReactNode;
}) {
    return (
        <div className="dock-gait-row">
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

function Library() {
    const source = useStore((s) => s.gaitSource);
    const gaitName = useStore((s) => s.gaitName);
    const userGaits = useStore((s) => s.userGaits);
    const message = useStore((s) => s.userGaitMessage);
    const robotName = useStore((s) => s.robotConfig.name);
    const store = useStore.getState();

    // One's own gaits for the robot modelled; a gait belongs to the robot it
    // was made on.
    useEffect(() => {
        void useStore.getState().listUserGaits();
    }, [robotName]);

    return (
        <Section
            title="Gaits"
            className="dock-library"
            head={
                <Segmented
                    id="pose-gait-source"
                    className="dock-seg dock-push"
                    options={[
                        { label: "Built-in", value: "builtin" },
                        { label: "Mine", value: "mine" },
                    ]}
                    value={source}
                    onChange={(gaitSource) => store.set({ gaitSource })}
                />
            }
        >
            {/* Both lists stay mounted; the one not picked is only hidden. */}
            <div
                id="pose-gait-list-builtin"
                className="dock-gait-list"
                style={source === "builtin" ? undefined : { display: "none" }}
            >
                {GAIT_MENU.map(([group, motions]) => [
                    <div className="dock-gait-group" key={group}>
                        {group}
                    </div>,
                    ...motions.map((motion) => (
                        <GaitRow
                            key={motion}
                            label={GAIT_LABELS[motion]}
                            onInsert={() => void store.insertGait("builtin", motion, false)}
                            onReplace={() => void store.insertGait("builtin", motion, true)}
                        />
                    )),
                ])}
            </div>
            <div
                id="pose-gait-list-mine"
                className="dock-gait-mine"
                style={source === "mine" ? undefined : { display: "none" }}
            >
                {/* Keeps the whole sequence under the name; a gait of that name
                    already there is replaced. */}
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
                        title="Keep the whole sequence as a gait of your own"
                        onClick={() => void store.saveUserGait()}
                    >
                        Save sequence
                    </Button>
                </div>
                <div id="pose-user-gait-message" className="dock-message">
                    {message && <div className="ind-alert mb-3">⚠ {message}</div>}
                </div>
                <div id="pose-user-gait-list" className="dock-gait-list">
                    {userGaits.length ? (
                        userGaits.map((gait) => (
                            <GaitRow
                                key={gait.id}
                                label={gait.name}
                                note={`${gait.count} keyframe${gait.count !== 1 ? "s" : ""} · ${(gait.duration_ms / 1000).toFixed(2)} s`}
                                onInsert={() => void store.insertGait("mine", gait.id, false)}
                                onReplace={() => void store.insertGait("mine", gait.id, true)}
                                extra={
                                    // It asks first: the file is gone for good.
                                    <Button
                                        outline
                                        className="dock-gait-btn dock-gait-delete"
                                        title="Delete this gait"
                                        onClick={() => {
                                            if (
                                                window.confirm(
                                                    `Delete the gait '${gait.name}'? This cannot be undone.`,
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
                            None yet: build a sequence, name it and save it here.
                        </div>
                    )}
                </div>
            </div>
        </Section>
    );
}

function EaseIcon({ eased }: { eased: boolean }) {
    return <span className={`ind-ease-icon ${eased ? "is-eased" : "is-linear"}`} />;
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
function Track() {
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
                    No keyframes yet: pose the robot in the view, then + Add pose, or add a gait
                    from the library.
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

    return (
        <div className="dock-kf-editor">
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
            <div title="Ease: start and stop the move into this keyframe gently. Linear: run it at a steady speed, as a gait's moves do.">
                <Segmented
                    id="pose-keyframe-ease"
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
                    onChange={(v) => store.setEase(v === "ease")}
                />
            </div>
            <div className="dock-group">
                <Button
                    id="pose-update-btn"
                    outline
                    disabled={none}
                    title="Overwrite the selected keyframe with the pose"
                    onClick={store.updateKeyframe}
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
                    onClick={store.deleteKeyframe}
                >
                    Delete
                </Button>
            </div>
            <Button
                id="pose-add-btn"
                color="primary"
                className="dock-add-btn dock-push"
                title="Record the pose as a keyframe"
                onClick={store.addPose}
            >
                {add}
            </Button>
        </div>
    );
}

function Sequence() {
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
                <Track />
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
    return (
        <div className="dock">
            <div className="dock-col dock-col-library">
                <Library />
            </div>
            <div className="dock-col dock-col-sequence">
                <Sequence />
            </div>
            {/* On the line between the columns; the sequence takes what is left. */}
            <Splitter kind="lib" />
        </div>
    );
}
