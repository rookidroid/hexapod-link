// What belongs to the robot rather than to the pose, over the view:
//
// * StreamHud switches streaming on and limits its speed.
// * DimensionsHud names the robot modelled and its measurements, which follow
//   the connected robot and can be edited to try another body.
// * DriveHud is the controller: hold a pad and the robot plays that one of its
//   own gaits from flash, let go and it stands.
//
// Nothing in the robot's sections can do anything without a robot, so while
// it is offline they are dimmed and made inert.

import { useEffect, useRef, useState } from "react";
import { DRIVE_BODY_PAD, DRIVE_LABELS, DRIVE_MOVE_PAD } from "../../../shared/motions";
import { DIMENSION_NAMES, type DimensionName, describe } from "../../../shared/robot_config";
import { INPUT_DIMENSIONS_RESOLUTION } from "../../../shared/settings";
import { api } from "../api";
import { useStore } from "../state/store";
import { FieldGrid, FieldLabel, GroupHeader, Hud, NumberField, Slider } from "./widgets";

export const controlsClass = (offline: boolean) =>
    offline ? "robot-section-controls is-offline" : "robot-section-controls";

export function StreamHud() {
    const connected = useStore((s) => s.status.connected);
    const streaming = useStore((s) => s.status.streaming);
    const maxStep = useStore((s) => s.maxStep);
    const { setStreaming, setMaxStep } = useStore.getState();
    const offline = !connected;
    return (
        <div
            id="robot-stream-hud"
            className="hud-panel stream-hud"
            title="Sends every reachable pose to the servos as it changes. Put the hexapod on a stand first: a pose that stands up here will not necessarily stand up on the floor."
        >
            <div id="robot-stream-controls" className={controlsClass(offline)}>
                <div className="form-check form-switch mb-0">
                    <input
                        id="robot-stream-switch"
                        className="form-check-input"
                        type="checkbox"
                        disabled={offline}
                        checked={streaming}
                        onChange={(e) => void setStreaming(e.target.checked)}
                    />
                    <label className="form-check-label form-label" htmlFor="robot-stream-switch">
                        Stream to robot
                    </label>
                </div>
                <div
                    className="ind-inline-slider"
                    title="Max joint speed, in servo ticks per cycle: how fast any servo may slew"
                >
                    <FieldLabel>Max speed</FieldLabel>
                    <Slider
                        id="robot-max-step-slider"
                        min={1}
                        max={30}
                        step={1}
                        value={maxStep}
                        disabled={offline}
                        onChange={setMaxStep}
                    />
                </div>
            </div>
        </div>
    );
}

const DIMENSION_LABEL = (name: string) => name[0].toUpperCase() + name.slice(1);

export function DimensionsHud() {
    const open = useStore((s) => s.panels.dimensions);
    const dims = useStore((s) => s.dims);
    const robotConfig = useStore((s) => s.robotConfig);
    const { setDims, setPanel } = useStore.getState();
    const field = (name: DimensionName) => (
        <NumberField
            key={name}
            id={`widget-dimension-${name}`}
            label={DIMENSION_LABEL(name)}
            value={dims[name]}
            min={0}
            step={INPUT_DIMENSIONS_RESOLUTION}
            onCommit={(v) => setDims(name, v)}
        />
    );
    return (
        <Hud
            id="dimensions-hud"
            className="hud-panel dims-hud"
            open={open}
            onToggle={(o) => setPanel("dimensions", o, true)}
            summary="Dimensions"
        >
            {/* Which robot the model is: the one connected, the last one, or
                the default. The measurements below start on its own. */}
            <div id="robot-info" className="dims-robot">
                {describe(robotConfig)}
            </div>
            <GroupHeader>Body (mm)</GroupHeader>
            <FieldGrid oneRow>{DIMENSION_NAMES.slice(0, 3).map(field)}</FieldGrid>
            <GroupHeader>Leg (mm)</GroupHeader>
            <FieldGrid oneRow>{DIMENSION_NAMES.slice(3).map(field)}</FieldGrid>
            <div className="dims-note">
                Follow the connected robot; edit them to try another body.
            </div>
        </Hud>
    );
}

// ......................
// The controller's pads, after the Android app's control screen: a body pad
// of moves on the spot, and a move pad of walks round standby, one shape per
// motion, so where a press lands is exactly what it shows.
//
// A pad drives the robot while it is held: the motion is sent on the press,
// on sliding onto another, and again every RENEW_MS to renew the hold; letting
// go sends standby. If the renewals stop without that -- the window closed --
// the robot stands on its own once the hold runs out (ROBOT_DRIVE_HOLD_S).
// ......................

// Well inside ROBOT_DRIVE_HOLD_S (600 ms), so a late renewal or two does not
// stop the robot mid-stride.
const RENEW_MS = 200;
const IDLE_TEXT = "Hold a pad to move";

/** A point at radius r and bearing deg: 0 is up (forward), clockwise. */
function polar(r: number, deg: number): string {
    const rad = (deg * Math.PI) / 180;
    return `${r * Math.sin(rad)},${-r * Math.cos(rad)}`;
}

/** The ring sector between radii r0 < r1 and bearings a0 < a1. */
function sector(r0: number, r1: number, a0: number, a1: number): string {
    const large = a1 - a0 > 180 ? 1 : 0;
    return [
        "M",
        polar(r1, a0),
        "A",
        r1,
        r1,
        0,
        large,
        1,
        polar(r1, a1),
        "L",
        polar(r0, a1),
        "A",
        r0,
        r0,
        0,
        large,
        0,
        polar(r0, a0),
        "Z",
    ].join(" ");
}

const CENTRE_R = 27;
const WALK_R = 64;
const OUTER_R = 98;
const CELL = 60;
const BODY_GLYPHS: Record<string, string> = {
    rotate_y: "↔",
    rotate_x: "↕",
    rotate_z: "⟳",
    climb_forward: "▲",
    twist: "∞",
    climb_backward: "▼",
};

function Zone({
    motion,
    active,
    children,
}: {
    motion: string;
    active: boolean;
    children: React.ReactNode;
}) {
    return (
        <g className={`drive-zone${active ? " is-active" : ""}`} data-motion={motion}>
            <title>{DRIVE_LABELS[motion] ?? motion}</title>
            {children}
        </g>
    );
}

function MovePad({ active }: { active: string | null }) {
    return (
        <svg viewBox="-100 -100 200 200" className="drive-svg">
            <title>Walks and turns</title>
            {DRIVE_MOVE_PAD.outer.map((motion, i) => {
                const bearing = i * 90;
                // Drawn at the top and turned into place; the left turn is the
                // right one mirrored, so it curves the other way round.
                const transform = `rotate(${bearing})${bearing === 270 ? " scale(-1,1)" : ""}`;
                return (
                    <Zone motion={motion} active={active === motion} key={motion}>
                        <path
                            d={sector(WALK_R, OUTER_R, bearing - 45, bearing + 45)}
                            className="drive-face drive-face-outer"
                        />
                        <g transform={transform} className="drive-icon">
                            {bearing % 180 === 0 ? (
                                <path d="M0,-92 L9,-82 L-9,-82 Z M0,-83 L9,-73 L-9,-73 Z" />
                            ) : (
                                <>
                                    <path
                                        d={[
                                            "M",
                                            polar(82, -32),
                                            "A",
                                            82,
                                            82,
                                            0,
                                            0,
                                            1,
                                            polar(82, 26),
                                        ].join(" ")}
                                        className="drive-stroke"
                                    />
                                    <path
                                        d={[
                                            "M",
                                            polar(82, 37),
                                            "L",
                                            polar(73, 25),
                                            "L",
                                            polar(91, 25),
                                            "Z",
                                        ].join(" ")}
                                    />
                                </>
                            )}
                        </g>
                    </Zone>
                );
            })}
            {DRIVE_MOVE_PAD.walk.map((motion, i) => {
                const bearing = i * 45;
                return (
                    <Zone motion={motion} active={active === motion} key={motion}>
                        <path
                            d={sector(CENTRE_R, WALK_R, bearing - 22.5, bearing + 22.5)}
                            className="drive-face drive-face-walk"
                        />
                        <path
                            d="M0,-55 L7,-43 L-7,-43 Z"
                            transform={`rotate(${bearing})`}
                            className="drive-icon"
                        />
                    </Zone>
                );
            })}
            <Zone motion={DRIVE_MOVE_PAD.centre} active={active === DRIVE_MOVE_PAD.centre}>
                <circle r={CENTRE_R - 2} className="drive-face drive-face-centre" />
                {/* Standby: a pause sign, as on the Android app. */}
                <path d="M-8,-10 h5 v20 h-5 Z M3,-10 h5 v20 h-5 Z" className="drive-icon" />
            </Zone>
        </svg>
    );
}

function BodyPad({ active }: { active: string | null }) {
    const glyph = (x: number, y: number, text: string, size: number, extra = "") => (
        <text
            x={x}
            y={y}
            fontSize={size}
            className={`drive-glyph${extra ? ` ${extra}` : ""}`}
            textAnchor="middle"
            dominantBaseline="central"
        >
            {text}
        </text>
    );
    return (
        <svg viewBox={`0 0 ${2 * CELL} ${DRIVE_BODY_PAD.length * CELL}`} className="drive-svg">
            <title>Moves on the spot</title>
            {DRIVE_BODY_PAD.flatMap((row, r) =>
                row.map(([motion, name], c) => {
                    const x = c * CELL;
                    const y = r * CELL;
                    return (
                        <Zone motion={motion} active={active === motion} key={motion}>
                            <rect
                                x={x + 1}
                                y={y + 1}
                                width={CELL - 2}
                                height={CELL - 2}
                                className="drive-face"
                            />
                            {glyph(x + CELL / 2, y + CELL / 2 - 6, BODY_GLYPHS[motion] ?? "•", 22)}
                            {glyph(
                                x + CELL / 2,
                                y + CELL - 11,
                                name.toUpperCase(),
                                9,
                                "drive-name",
                            )}
                        </Zone>
                    );
                }),
            )}
        </svg>
    );
}

function useDrivePads() {
    const [active, setActive] = useState<string | null>(null);
    const [readout, setReadout] = useState(IDLE_TEXT);
    const held = useRef<{ pointer: number; pad: Element; motion: string | null } | null>(null);
    const timer = useRef<ReturnType<typeof setInterval> | null>(null);

    const send = (motion: string) => {
        api.drive(motion).then(
            (reply) => {
                if (reply.message) setReadout(reply.message);
            },
            () => setReadout("The app is not answering."),
        );
    };
    const choose = (zone: Element) => {
        const h = held.current;
        const motion = zone.getAttribute("data-motion");
        if (!h || !motion || h.motion === motion) return;
        h.motion = motion;
        setActive(motion);
        setReadout(DRIVE_LABELS[motion] ?? motion);
        send(motion);
    };
    const release = () => {
        if (!held.current) return;
        held.current = null;
        if (timer.current) clearInterval(timer.current);
        timer.current = null;
        setActive(null);
        setReadout(IDLE_TEXT);
        // Now, rather than when the robot's hold runs out.
        send("standby");
    };
    const releaseRef = useRef(release);
    releaseRef.current = release;
    useEffect(() => {
        const onBlur = () => releaseRef.current();
        const onHide = () => {
            if (document.hidden) releaseRef.current();
        };
        window.addEventListener("blur", onBlur);
        document.addEventListener("visibilitychange", onHide);
        return () => {
            window.removeEventListener("blur", onBlur);
            document.removeEventListener("visibilitychange", onHide);
            releaseRef.current();
        };
    }, []);

    const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
        const zone = (e.target as Element).closest(".drive-zone");
        if (!zone || e.button !== 0 || e.currentTarget.closest(".is-offline")) return;
        e.preventDefault();
        release();
        held.current = { pointer: e.pointerId, pad: e.currentTarget, motion: null };
        // Keeps the moves and the release coming here, wherever the pointer
        // goes while the pad is held.
        try {
            e.currentTarget.setPointerCapture(e.pointerId);
        } catch {
            // A pointer the browser no longer knows; the release still comes.
        }
        choose(zone);
        timer.current = setInterval(() => {
            if (held.current?.motion) send(held.current.motion);
        }, RENEW_MS);
    };
    // Sliding onto another zone of the same pad changes gait; off the pad, the
    // last one keeps going, as on the Android app, until let go.
    const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
        const h = held.current;
        if (!h || e.pointerId !== h.pointer) return;
        const zone = document.elementFromPoint(e.clientX, e.clientY)?.closest(".drive-zone");
        if (zone && zone.closest(".drive-pad") === h.pad) choose(zone);
    };
    const onPointerEnd = (e: React.PointerEvent<HTMLDivElement>) => {
        if (held.current && e.pointerId === held.current.pointer) release();
    };
    const padProps = {
        onPointerDown,
        onPointerMove,
        onPointerUp: onPointerEnd,
        onPointerCancel: onPointerEnd,
        onLostPointerCapture: onPointerEnd,
    };

    return { active, readout, padProps };
}

export function DriveHud() {
    const open = useStore((s) => s.panels.controller);
    const connected = useStore((s) => s.status.connected);
    const driveSpeed = useStore((s) => s.driveSpeed);
    const speed = useStore((s) => s.robotConfig.speed);
    const { setPanel, setDriveSpeed } = useStore.getState();
    const { active, readout, padProps } = useDrivePads();
    return (
        <Hud
            id="drive-hud"
            className="hud-panel drive-hud"
            open={open}
            onToggle={(o) => setPanel("controller", o, true)}
            summary="Controller"
            summaryTitle="Runs the robot's own gaits, played from its flash, for as long as a pad is held."
        >
            <div id="drive-controls" className={`drive-body ${controlsClass(!connected)}`}>
                <div className="drive-pad drive-pad-body" data-pad="body" {...padProps}>
                    <BodyPad active={active} />
                </div>
                <div className="drive-pad drive-pad-move" data-pad="move" {...padProps}>
                    <MovePad active={active} />
                </div>
                <div className="drive-footer">
                    <div id="drive-readout" className="drive-readout">
                        {readout}
                    </div>
                    <div
                        className="ind-inline-slider drive-speed"
                        title="How fast the robot plays its gaits, of its tuned rate"
                    >
                        <FieldLabel>Speed (%)</FieldLabel>
                        <Slider
                            id="drive-speed"
                            min={speed.min}
                            max={speed.max}
                            step={5}
                            value={driveSpeed}
                            onChange={(v) => useStore.getState().set({ driveSpeed: v })}
                            onRelease={(v) => void setDriveSpeed(v)}
                        />
                    </div>
                </div>
            </div>
        </Hud>
    );
}
