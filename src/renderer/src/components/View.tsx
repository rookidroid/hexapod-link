// The 3D view in the middle of the workspace, and what is laid over it:
//
//   [stream]                  [move | rotate]         [reset pose][reset view]
//   [dimensions]                 3D view
//   [pose: angles, what is picked]    [playback]                  [controller]
//
// The view draws the pose -- whose body, feet and joints can be picked and
// dragged -- or a frame of the sequence while previewing, which cannot.

import { useEffect, useRef } from "react";
import { previewOf, solvedOf, useStore } from "../state/store";
import { hexapodView } from "../view/hexapodView";
import { PlaybackHud } from "./PlaybackHud";
import { BodyTool, PoseHud } from "./PoseHud";
import { DimensionsHud, DriveHud, StreamHud } from "./RobotHuds";
import { Button } from "./widgets";

export const VIEW_ID = "view-pose";

const VIEW_HINT =
    "Click a foot, a joint or the body to move it · Drag: orbit · Right-drag: pan · Wheel: zoom";

function View3D() {
    useEffect(() => {
        const store = useStore.getState();
        const offs = [
            hexapodView.on("pose-selection", (what) => store.setSelection(what)),
            hexapodView.on("pose-foot-target", (t) => store.footTarget(t)),
            hexapodView.on("pose-body-target", (t) => store.bodyTarget(t)),
            hexapodView.on("pose-joint-target", (t) => store.jointTarget(t)),
        ];
        let shown: unknown = null;
        const draw = () => {
            const s = useStore.getState();
            const preview = previewOf(s);
            if (s.mode === "preview" && preview.states.length) {
                const scene = preview.scene(s.frame);
                if (scene !== shown) hexapodView.render(VIEW_ID, scene, { editable: false });
                shown = scene;
            } else {
                const scene = solvedOf(s).scene;
                if (scene !== shown) hexapodView.render(VIEW_ID, scene, { editable: true });
                shown = scene;
            }
        };
        draw();
        hexapodView.setBodyMode(VIEW_ID, useStore.getState().bodyMode);
        const unsubscribe = useStore.subscribe((s, prev) => {
            if (s.bodyMode !== prev.bodyMode) hexapodView.setBodyMode(VIEW_ID, s.bodyMode);
            draw();
        });
        return () => {
            unsubscribe();
            for (const off of offs) off();
        };
    }, []);
    return <div id={VIEW_ID} className="hexapod-view" />;
}

export function View() {
    const frame = useRef<HTMLDivElement>(null);
    const { resetPose } = useStore.getState();

    // How tall the playback bar is, as --playback-h on the frame: the pose
    // and the controller, opened, go up above it by that much.
    useEffect(() => {
        const bar = frame.current?.querySelector(".playback-hud") as HTMLElement | null;
        if (!bar) return;
        const observer = new ResizeObserver(() => {
            frame.current?.style.setProperty("--playback-h", `${bar.offsetHeight}px`);
        });
        observer.observe(bar);
        return () => observer.disconnect();
    }, []);

    return (
        <div className="hexapod-view-frame" ref={frame}>
            <View3D />
            <div className="hexapod-view-overlay">
                <Button
                    id="pose-reset-btn"
                    outline
                    className="view-btn"
                    title="Back to the robot's standby posture: undoes every move of the body and the feet"
                    onClick={resetPose}
                >
                    Reset pose
                </Button>
                <Button
                    id="pose-reset-view-btn"
                    outline
                    className="view-btn"
                    title="Frame the robot again"
                    onClick={() => hexapodView.resetCamera(VIEW_ID)}
                >
                    Reset view
                </Button>
            </div>
            <div className="hexapod-view-hud">
                <PoseHud />
            </div>
            <div className="hexapod-view-controls">
                <StreamHud />
                <DimensionsHud />
            </div>
            <div className="hexapod-view-drive">
                <DriveHud />
            </div>
            <div className="hexapod-view-tool">
                <BodyTool />
            </div>
            <div className="hexapod-view-playback">
                <PlaybackHud />
            </div>
            <div className="hexapod-view-hint">{VIEW_HINT}</div>
        </div>
    );
}
