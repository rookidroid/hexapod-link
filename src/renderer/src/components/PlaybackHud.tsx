// Over the middle of the view's bottom edge: play the sequence in the view, or
// scrub through it, and how fast and whether it loops; then run it on the
// robot, or stand the robot down. What came of that last is a line under them.

import { useEffect } from "react";
import { maxFrameOf, previewOf, SPEED_MAX_PCT, SPEED_MIN_PCT, useStore } from "../state/store";
import { controlsClass } from "./RobotHuds";
import { Button, Check, FieldLabel, NumberInput, Slider } from "./widgets";

export function PlaybackHud() {
    const playing = useStore((s) => s.playing);
    const frame = useStore((s) => s.frame);
    const maxFrame = useStore(maxFrameOf);
    const preview = useStore(previewOf);
    const speed = useStore((s) => s.speed);
    const loop = useStore((s) => s.loop);
    const connected = useStore((s) => s.status.connected);
    const robotMessage = useStore((s) => s.robotMessage);
    const store = useStore.getState();

    // One preview frame per tick while playing.
    useEffect(() => {
        if (!playing) return;
        const timer = setInterval(() => useStore.getState().tick(), 1000 / preview.fps);
        return () => clearInterval(timer);
    }, [playing, preview.fps]);

    const last = Math.max(preview.states.length - 1, 0);
    const at = Math.min(frame, last);

    return (
        <section className="hud-panel playback-hud" aria-label="Playback">
            <Button
                id="pose-play-btn"
                color={playing ? "danger" : "primary"}
                className="ind-play-btn"
                onClick={store.play}
            >
                {playing ? "⏸ Pause" : "▶ Play"}
            </Button>
            <div className="ind-dock-scrubber">
                <Slider
                    id="pose-frame-slider"
                    min={0}
                    max={maxFrame}
                    step={1}
                    value={frame}
                    input={false}
                    onGrab={store.grabScrubber}
                    onChange={store.scrub}
                    onRelease={store.releaseScrubber}
                />
            </div>
            <div id="pose-frame-display" className="dock-note text-nowrap">
                {at}/{last} · {(at / preview.fps).toFixed(2)} s
            </div>
            <div
                className="dock-inline-field"
                title={`How fast the whole sequence plays, in the preview and on the robot, ${SPEED_MIN_PCT} to ${SPEED_MAX_PCT} %. At 100 % a gait plays at the robot's own speed.`}
            >
                <FieldLabel>Speed</FieldLabel>
                <div className="ind-duration-input input-group input-group-sm">
                    <NumberInput
                        id="pose-speed"
                        className="form-control"
                        value={speed}
                        onCommit={store.setSpeed}
                    />
                    <span className="input-group-text">%</span>
                </div>
            </div>
            <Check
                id="pose-loop"
                label="Loop"
                checked={loop}
                onChange={store.setLoop}
                className="dock-check"
            />
            <div
                className="playback-robot"
                title="Run the sequence on the robot, or stop it and stand the robot up."
            >
                <div
                    id="pose-robot-controls"
                    className={`d-flex gap-2 ${controlsClass(!connected)}`}
                >
                    <Button
                        id="pose-run-btn"
                        color="success"
                        disabled={!connected}
                        onClick={() => void store.runOnRobot()}
                    >
                        ▶ Run on robot
                    </Button>
                    <Button
                        id="pose-stop-btn"
                        outline
                        disabled={!connected}
                        onClick={() => void store.stopOnRobot()}
                    >
                        ■ Standby
                    </Button>
                </div>
            </div>
            <div id="pose-robot-message" className="dock-note playback-message">
                {robotMessage}
            </div>
        </section>
    );
}
