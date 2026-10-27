// The pose, in the view's corner: the joint angles -- read out, and typed --
// under the buttons that pick what to adjust, then the controls of whatever
// is picked, by clicking it in the view or its button here:
//
//   the body  move and tilt it over the planted feet, with its sliders or by
//             dragging its handles in the view
//   a foot    move it, by dragging it in the view or typing where it goes
//   a joint   turn it, by dragging the ring on it in the view
//
// Legs and joints are named the way the robot firmware names them, so a value
// can be read straight onto the robot's calibration page.

import { useShallow } from "zustand/react/shallow";
import {
    JOINT_NAMES,
    jointLabel,
    jointNumber,
    legIndex,
    legLabel,
    shortLegName,
} from "../../../shared/naming";
import * as pl from "../../../shared/pose_layers";
import {
    BODY_RANGES,
    fieldValue,
    pickedLeg,
    robotOf,
    SELECT_BODY,
    solvedOf,
    useStore,
} from "../state/store";
import { hexapodView } from "../view/hexapodView";
import {
    Button,
    FieldGrid,
    FieldLabel,
    GroupHeader,
    Hud,
    NumberInput,
    Segmented,
    Slider,
} from "./widgets";

// Left legs then right, front to back.
const ANGLE_COLUMNS = [
    "left-front",
    "left-middle",
    "left-back",
    "right-front",
    "right-middle",
    "right-back",
] as const;

const BODY_SLIDERS: [pl.BodyKey, string, string][] = [
    ["percent_x", "X", "widget-percent-x"],
    ["percent_y", "Y", "widget-percent-y"],
    ["percent_z", "Z", "widget-percent-z"],
    ["rot_x", "X", "widget-rot-x"],
    ["rot_y", "Y", "widget-rot-y"],
    ["rot_z", "Z", "widget-rot-z"],
];

const VIEW_ID = "view-pose";

/** A button that picks in the view, as clicking the body or the foot there
 * does; the view reports it back, which is what lights the button. Clicked
 * again, it lets go. */
function PickButton({
    what,
    label,
    title,
    id,
}: {
    what: "body" | number;
    label: string;
    title: string;
    id: string;
}) {
    const picked = useStore((s) => s.selection === what);
    return (
        <button
            type="button"
            id={id}
            className={`hud-pick${picked ? " is-picked" : ""}`}
            title={title}
            onClick={() => hexapodView.select(VIEW_ID, picked ? null : what)}
        >
            {label}
        </button>
    );
}

function AngleTable() {
    const { pose, bad } = useStore(
        useShallow((s) => {
            const solved = solvedOf(s);
            return { pose: solved.pose, bad: solved.bad };
        }),
    );
    const jointField = useStore.getState().jointField;
    return (
        <table className="ind-joint-grid ind-angle-strip mb-0 table table-sm table-borderless">
            <thead>
                <tr>
                    <th>
                        <PickButton
                            id="pose-pick-body"
                            what={SELECT_BODY}
                            label="Body"
                            title="Pick the body, to move and tilt it"
                        />
                    </th>
                    {ANGLE_COLUMNS.map((name) => (
                        <th className="text-center" key={name}>
                            <PickButton
                                id={`pose-pick-${name}`}
                                what={legIndex(name)}
                                label={shortLegName(name)}
                                title={`${legLabel(name)}: pick its foot, to move it`}
                            />
                        </th>
                    ))}
                </tr>
            </thead>
            <tbody>
                {JOINT_NAMES.map((joint) => (
                    <tr key={joint}>
                        <th className="text-nowrap align-middle">
                            <span title={`${jointLabel(joint)}, in degrees`}>
                                J{jointNumber(joint)}
                            </span>
                        </th>
                        {ANGLE_COLUMNS.map((name) => {
                            const leg = legIndex(name);
                            // Empty for a leg that cannot reach its foot, whose
                            // angles mean nothing.
                            const value = bad.includes(leg) ? null : fieldValue(pose[leg][joint]);
                            return (
                                <td key={name}>
                                    <NumberInput
                                        id={`pose-joint-${name}-${joint}`}
                                        value={value}
                                        step={0.1}
                                        placeholder="—"
                                        onCommit={(v) => jointField(leg, joint, v)}
                                    />
                                </td>
                            );
                        })}
                    </tr>
                ))}
            </tbody>
        </table>
    );
}

function BodySliders() {
    const body = useStore((s) => s.pose.state.body);
    const bodySlider = useStore.getState().bodySlider;
    const slider = ([key, label, id]: (typeof BODY_SLIDERS)[number]) => {
        const shift = key.startsWith("percent");
        const most = BODY_RANGES[key];
        return (
            <div className="ind-inline-slider" title={`${-most} to ${most}`} key={key}>
                <FieldLabel>{label}</FieldLabel>
                <Slider
                    id={id}
                    min={-most}
                    max={most}
                    step={shift ? 0.05 : 1.5}
                    value={body[key]}
                    onChange={(v) => bodySlider(key, v)}
                />
            </div>
        );
    };
    return (
        <div className="hud-body-sliders">
            <div>
                <GroupHeader>Translate (× body size)</GroupHeader>
                {BODY_SLIDERS.slice(0, 3).map(slider)}
            </div>
            <div>
                <GroupHeader>Rotate (°)</GroupHeader>
                {BODY_SLIDERS.slice(3).map(slider)}
            </div>
        </div>
    );
}

function FootFields({ leg }: { leg: number }) {
    const state = useStore((s) => s.pose.state);
    const robot = useStore(robotOf);
    const foot = pl.viewFeet(state, robot)[leg];
    const footFields = useStore.getState().footFields;
    const ids = ["pose-foot-x", "pose-foot-y", "pose-foot-up"];
    const labels = ["X (mm)", "Y (mm)", "Up (mm)"];
    return (
        <FieldGrid oneRow>
            {ids.map((id, i) => (
                <div className="ind-number-field" key={id}>
                    <FieldLabel>{labels[i]}</FieldLabel>
                    <NumberInput
                        id={id}
                        step={1}
                        value={fieldValue(foot[i])}
                        onCommit={(v) => footFields(foot.map((_, k) => (k === i ? v : null)))}
                    />
                </div>
            ))}
        </FieldGrid>
    );
}

export function PoseHud() {
    const selection = useStore((s) => s.selection);
    const open = useStore((s) => s.panels.pose);
    const message = useStore((s) => s.message);
    const bad = useStore((s) => solvedOf(s).bad);
    const { setPanel, clearFeet } = useStore.getState();

    const body = selection === SELECT_BODY;
    const leg = pickedLeg(selection);
    const joint = selection !== null && typeof selection === "object" ? selection : null;

    return (
        <Hud
            id="pose-hud"
            // Marked when a leg is out of reach, so the overlay says so even
            // folded away, when the warning inside it cannot be seen.
            className={`hud-panel pose-hud${bad.length ? " is-bad" : ""}`}
            open={open}
            onToggle={(o) => setPanel("pose", o, true)}
            summary="Pose"
            summaryTitle="The joint angles, and the controls of the body or foot picked"
        >
            <AngleTable />
            <div id="pose-angles" className="hud-message">
                {bad.length > 0 && (
                    <div className="ind-alert">
                        ⚠ Out of reach or past a joint limit:{" "}
                        {bad.map((l) => legLabel(l)).join(", ")}
                    </div>
                )}
            </div>
            <div id="pose-message" className="hud-message">
                {message && <div className="ind-alert">⚠ {message}</div>}
            </div>
            <div className="hud-adjust">
                {!body && leg === null && !joint && (
                    <div id="pose-adjust-hint" className="hud-hint">
                        Click the body, a foot or a joint, in the view or above, to adjust it.
                    </div>
                )}
                <div id="pose-adjust-body" style={body ? undefined : { display: "none" }}>
                    <div className="hud-adjust-head">
                        <span className="hud-adjust-title">Body</span>
                    </div>
                    <BodySliders />
                </div>
                {leg !== null && (
                    <div id="pose-adjust-foot">
                        <div className="hud-adjust-head">
                            <span id="pose-foot-title" className="hud-adjust-title">
                                {legLabel(leg)} foot
                            </span>
                            <Button
                                id="pose-clear-feet-btn"
                                outline
                                className="view-btn"
                                title="Put every foot back where standby has it, keeping the body move"
                                onClick={clearFeet}
                            >
                                Put feet back
                            </Button>
                        </div>
                        <FootFields leg={leg} />
                    </div>
                )}
                {joint && (
                    <div id="pose-adjust-joint">
                        <div className="hud-adjust-head">
                            <span id="pose-joint-title" className="hud-adjust-title">
                                {legLabel(joint.leg)} · {jointLabel(joint.joint)}
                            </span>
                        </div>
                        <div className="hud-hint">
                            Drag the ring on it in the view to turn it, or type its angle above.
                        </div>
                    </div>
                )}
            </div>
        </Hud>
    );
}

/** Over the view's top edge while the body is picked: what dragging it does,
 * by the handles it is dragged with. */
export function BodyTool() {
    const shown = useStore((s) => s.selection === SELECT_BODY);
    const bodyMode = useStore((s) => s.bodyMode);
    return (
        <div
            id="pose-body-tool"
            className="hud-panel view-tool"
            title="What dragging the body in the view does: its arrows move it, its rings turn it"
            style={shown ? undefined : { display: "none" }}
        >
            <FieldLabel>Drag body to</FieldLabel>
            <Segmented
                id="pose-body-mode"
                options={[
                    { label: "Move", value: "translate" },
                    { label: "Rotate", value: "rotate" },
                ]}
                value={bodyMode}
                onChange={(mode) => useStore.getState().set({ bodyMode: mode })}
            />
        </div>
    );
}
