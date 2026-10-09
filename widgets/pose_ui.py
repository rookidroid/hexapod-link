# Controls of the pose page (pages/page_pose.py).
#
# The control panel picks one of two tools, each setting part of the same
# pose, and shows that tool's controls:
#
#   Body  inverse kinematics: move and tilt the body over planted feet
#   Feet  move each foot, by dragging it in the 3D view or typing where
#
# Under the view, the dock reads the pose's joint angles out and holds the
# keyframe timeline: collecting poses, previewing the sequence, running it on
# the robot, saving it.
import dash_bootstrap_components as dbc
from dash import dcc, html

from hexapod.const import NAMES_JOINT, NAMES_LEG
from hexapod.keyframes import DEFAULT_DURATION_MS, MAX_DURATION_MS, MIN_DURATION_MS
from hexapod.naming import leg_label
from widgets.ik_ui import IK_WIDGETS
from widgets.robot_link_ui import SECTION_CONTROLS_OFFLINE_CLASS, STATUS_POLL_MS
from widgets.section_maker import (
    LEG_SIDES,
    field_label,
    group_header,
    make_field_grid,
    make_leg_sides,
    make_number_field,
    panel_section,
)

# --- Element IDs ---
# Written by assets/hexapod_view.js through set_props; keep the two in step.
POSE_FOOT_TARGET_ID = "pose-foot-target"
POSE_SELECTED_LEG_ID = "pose-selected-leg"

POSE_VIEW_ID = "view-pose"

POSE_TOOL_ID = "pose-tool"
POSE_TOOL_STORE_ID = "pose-tool-store"
TOOL_BODY = "body"
TOOL_FEET = "feet"
TOOLS = (TOOL_BODY, TOOL_FEET)
POSE_TOOL_PANEL_IDS = {tool: f"pose-panel-{tool}" for tool in TOOLS}

POSE_STATE_STORE_ID = "pose-state"
POSE_KEYFRAMES_STORE_ID = "pose-keyframes"
POSE_SELECTED_KF_STORE_ID = "pose-selected-keyframe"
POSE_PREVIEW_STORE_ID = "pose-preview"
POSE_PLAY_STATE_STORE_ID = "pose-play-state"
POSE_INTERVAL_ID = "pose-interval"

POSE_SELECTION_ID = "pose-selection"
# The Feet tool's picker and fields: which foot, and where it is.
POSE_FOOT_LEG_ID = "pose-foot-leg"
POSE_FOOT_X_ID = "pose-foot-x"
POSE_FOOT_Y_ID = "pose-foot-y"
POSE_FOOT_UP_ID = "pose-foot-up"
POSE_FOOT_FIELD_IDS = (POSE_FOOT_X_ID, POSE_FOOT_Y_ID, POSE_FOOT_UP_ID)


# The Feet tool's joint grid, as the Kinematics page had it: one field per
# leg and joint, e.g. "pose-joint-left-front-coxia".
def pose_joint_id(leg_name, joint_name):
    return f"pose-joint-{leg_name}-{joint_name}"


# Leg by leg in id order (NAMES_LEG), joints coxia, femur, tibia.
POSE_JOINT_FIELDS = [
    (leg_id, joint_name, pose_joint_id(leg_name, joint_name))
    for leg_id, leg_name in enumerate(NAMES_LEG)
    for joint_name in NAMES_JOINT
]
POSE_JOINT_FIELD_IDS = [field_id for _, _, field_id in POSE_JOINT_FIELDS]
POSE_ANGLES_ID = "pose-angles"
POSE_MESSAGE_ID = "pose-message"
POSE_RESET_BTN_ID = "pose-reset-btn"
POSE_CLEAR_FEET_BTN_ID = "pose-clear-feet-btn"
POSE_RESET_VIEW_BTN_ID = "pose-reset-view-btn"

POSE_DURATION_ID = "pose-duration"
POSE_ADD_BTN_ID = "pose-add-btn"
POSE_UPDATE_BTN_ID = "pose-update-btn"
POSE_DELETE_BTN_ID = "pose-delete-btn"
POSE_EARLIER_BTN_ID = "pose-earlier-btn"
POSE_LATER_BTN_ID = "pose-later-btn"
POSE_KF_LIST_ID = "pose-keyframe-list"
POSE_KF_SUMMARY_ID = "pose-keyframe-summary"
# Pattern-matching id of one entry in the keyframe list.
POSE_KF_ITEM_TYPE = "pose-keyframe-item"

POSE_VIEW_MODE_ID = "pose-view-mode"
POSE_LOOP_ID = "pose-loop"
POSE_EASE_ID = "pose-ease"
POSE_PLAY_BTN_ID = "pose-play-btn"
POSE_FRAME_SLIDER_ID = "pose-frame-slider"
POSE_FRAME_DISPLAY_ID = "pose-frame-display"
POSE_PREVIEW_MESSAGE_ID = "pose-preview-message"

POSE_ROBOT_CONTROLS_ID = "pose-robot-controls"
POSE_RUN_BTN_ID = "pose-run-btn"
POSE_STOP_BTN_ID = "pose-stop-btn"
POSE_ROBOT_MESSAGE_ID = "pose-robot-message"
POSE_ROBOT_POLL_INTERVAL_ID = "pose-robot-poll-interval"

POSE_SAVE_BTN_ID = "pose-save-btn"
POSE_DOWNLOAD_ID = "pose-download"
POSE_UPLOAD_ID = "pose-upload"

# Frame rate of the preview in the browser. The robot gets its own, faster,
# frames: see run_on_robot() in pages/page_pose.py.
PREVIEW_FPS = 25

MODE_EDIT = "edit"
MODE_PREVIEW = "preview"


def _button(label, button_id=None, color="secondary", outline=False, class_name="", **props):
    if button_id is not None:
        props["id"] = button_id
    return dbc.Button(
        label,
        color=color,
        outline=outline,
        size="sm",
        className=f"fw-bold {class_name}".strip(),
        **props,
    )


def _row(children, class_name=""):
    return html.Div(children, className=f"ind-dock-row {class_name}".strip())


# ................................
# CONTROL PANEL
# ................................

tool_section = panel_section(
    "Pose",
    [
        dbc.RadioItems(
            id=POSE_TOOL_ID,
            options=[
                {"label": "Body", "value": TOOL_BODY},
                {"label": "Feet", "value": TOOL_FEET},
            ],
            value=TOOL_BODY,
            className="ind-segmented ind-segmented-fill mb-3",
            inputClassName="btn-check",
            labelClassName="btn btn-sm btn-outline-secondary",
            labelCheckedClassName="active",
        ),
        _button(
            "Reset to standby",
            POSE_RESET_BTN_ID,
            title="Back to the robot's standby posture: undoes both tools",
        ),
    ],
    blurb=(
        "One pose, built from two layers that add up: Feet moves single feet "
        "from standby, and Body moves the body over wherever the feet are "
        "planted. Switching tools keeps both."
    ),
)

# All three panels stay mounted, so their sliders keep their values and their
# callbacks keep firing; the one not in use is only hidden.
body_panel = panel_section(
    "Body",
    IK_WIDGETS,
    blurb="Move and tilt the body; the joints are solved to keep the feet planted.",
    id=POSE_TOOL_PANEL_IDS[TOOL_BODY],
)

def _joint_field(leg_name, joint_index):
    # Applied when the field is left or Enter is pressed, not per digit.
    return dbc.Input(
        id=pose_joint_id(leg_name, NAMES_JOINT[joint_index]),
        type="number",
        step=0.1,
        debounce=True,
        size="sm",
    )


feet_panel = panel_section(
    "Feet",
    [
        html.Div(
            "Click a foot to pick it up and drag its arrows, or pick it here and "
            "type where it goes.",
            id=POSE_SELECTION_ID,
            className="small text-muted mb-3",
        ),
        html.Div(
            [
                field_label("Foot"),
                dbc.Select(
                    id=POSE_FOOT_LEG_ID,
                    # Left legs then right, front to back, as in the angle table.
                    options=[
                        {"label": leg_label(name), "value": name}
                        for _, legs in LEG_SIDES
                        for name in legs
                    ],
                    value="",
                    placeholder="Pick a foot",
                    size="sm",
                ),
            ],
            className="mb-2",
        ),
        # In the view's coordinates: x right, y forward, up from the floor.
        # Applied when the field is left or Enter is pressed, not per digit.
        make_field_grid(
            [
                make_number_field(field_id, label, step=1, debounce=True, disabled=True)
                for field_id, label in zip(
                    POSE_FOOT_FIELD_IDS, ("X (mm)", "Y (mm)", "Up (mm)")
                )
            ],
            one_row=True,
        ),
        group_header("Joints (°)"),
        html.Div(
            "Or set a leg's joints: its foot goes where they put it.",
            className="small text-muted mb-2",
        ),
        make_leg_sides(_joint_field),
        _button(
            "Put feet back",
            POSE_CLEAR_FEET_BTN_ID,
            title="Put every foot back where standby has it, keeping the body move",
        ),
    ],
    blurb=(
        "A moved foot stays where it was put in the world while the body moves "
        "over it."
    ),
    id=POSE_TOOL_PANEL_IDS[TOOL_FEET],
    style={"display": "none"},
)

POSE_PANEL_SECTIONS = [
    tool_section,
    body_panel,
    feet_panel,
    html.Div(id=POSE_MESSAGE_ID),
]

RESET_VIEW_BUTTON = _button(
    "Reset view", POSE_RESET_VIEW_BTN_ID, outline=True, title="Frame the robot again"
)


# ................................
# DOCK
# ................................

angles_block = html.Div(
    [
        html.H6("Joint angles (°)", className="mb-2"),
        html.Div(id=POSE_ANGLES_ID),
    ],
    className="ind-dock-angles",
)

_loop_ease = html.Div(
    [
        dcc.Checklist(
            id=POSE_LOOP_ID,
            options=[{"label": " Loop", "value": "loop"}],
            value=[],
            className="fw-bold",
        ),
        dcc.Checklist(
            id=POSE_EASE_ID,
            options=[{"label": " Ease", "value": "ease"}],
            value=["ease"],
            className="fw-bold",
        ),
    ],
    className="d-flex gap-3",
)

keyframe_header = _row(
    [
        html.H6("Keyframes", className="mb-0"),
        html.Div(id=POSE_KF_SUMMARY_ID, className="small text-muted font-monospace"),
        html.Div(
            [
                _loop_ease,
                _button("Save…", POSE_SAVE_BTN_ID, outline=True),
                dcc.Upload(
                    _button("Load…", outline=True),
                    id=POSE_UPLOAD_ID,
                    accept=".json,application/json",
                ),
                dcc.Download(id=POSE_DOWNLOAD_ID),
            ],
            className="d-flex align-items-center gap-2 ms-auto",
        ),
    ]
)

keyframe_edit = _row(
    [
        html.Div(
            dbc.InputGroup(
                [
                    dbc.Input(
                        id=POSE_DURATION_ID,
                        type="number",
                        min=MIN_DURATION_MS,
                        max=MAX_DURATION_MS,
                        step=10,
                        value=DEFAULT_DURATION_MS,
                    ),
                    dbc.InputGroupText("ms"),
                ],
                size="sm",
                className="ind-duration-input",
            ),
            title="Time to reach this pose from the keyframe before it",
        ),
        _button("+ Add", POSE_ADD_BTN_ID, color="primary", title="Add the pose after the selected keyframe"),
        _button("Update", POSE_UPDATE_BTN_ID, title="Overwrite the selected keyframe with the pose"),
        _button("Delete", POSE_DELETE_BTN_ID, color="danger"),
        _button("◀", POSE_EARLIER_BTN_ID, outline=True, title="Move earlier"),
        _button("▶", POSE_LATER_BTN_ID, outline=True, title="Move later"),
    ]
)

# The view shows the pose (which the tools edit) or the sequence (which plays).
transport = _row(
    [
        dbc.RadioItems(
            id=POSE_VIEW_MODE_ID,
            options=[
                {"label": "Pose", "value": MODE_EDIT},
                {"label": "Sequence", "value": MODE_PREVIEW},
            ],
            value=MODE_EDIT,
            className="ind-segmented",
            inputClassName="btn-check",
            labelClassName="btn btn-sm btn-outline-secondary",
            labelCheckedClassName="active",
        ),
        _button("▶ Play", POSE_PLAY_BTN_ID, color="primary", class_name="ind-play-btn"),
        html.Div(
            dcc.Slider(
                id=POSE_FRAME_SLIDER_ID,
                min=0,
                max=1,
                step=1,
                value=0,
                marks=None,
                disabled=True,
                updatemode="drag",
            ),
            className="ind-dock-scrubber",
        ),
        html.Div(
            "0/0 · 0.00 s",
            id=POSE_FRAME_DISPLAY_ID,
            className="small fw-bold font-monospace text-nowrap",
        ),
    ]
)

robot_row = _row(
    [
        html.Div(
            [
                _button("▶ Run on robot", POSE_RUN_BTN_ID, color="success", disabled=True),
                _button("■ Standby", POSE_STOP_BTN_ID, disabled=True),
            ],
            id=POSE_ROBOT_CONTROLS_ID,
            className=f"d-flex gap-2 {SECTION_CONTROLS_OFFLINE_CLASS}",
        ),
        html.Div(
            "Connect a robot to run this on the hardware.",
            id=POSE_ROBOT_MESSAGE_ID,
            className="small text-muted font-monospace",
        ),
        dcc.Interval(
            id=POSE_ROBOT_POLL_INTERVAL_ID,
            interval=STATUS_POLL_MS,
            n_intervals=0,
        ),
    ]
)

keyframes_block = html.Div(
    [
        keyframe_header,
        html.Div(id=POSE_KF_LIST_ID, className="ind-kf-strip"),
        keyframe_edit,
        transport,
        html.Div(id=POSE_PREVIEW_MESSAGE_ID),
        robot_row,
    ],
    className="ind-dock-keyframes",
)

# Session storage, so the pose and the sequence being built survive going to
# another page and back. Each store records which robot it was made on; see
# pages/page_pose.py.
hidden_components = html.Div(
    [
        dcc.Store(id=POSE_FOOT_TARGET_ID),
        dcc.Store(id=POSE_SELECTED_LEG_ID),
        dcc.Store(id=POSE_TOOL_STORE_ID, storage_type="session"),
        dcc.Store(id=POSE_STATE_STORE_ID, storage_type="session"),
        dcc.Store(id=POSE_KEYFRAMES_STORE_ID, storage_type="session"),
        dcc.Store(id=POSE_SELECTED_KF_STORE_ID, storage_type="session"),
        dcc.Store(id=POSE_PREVIEW_STORE_ID),
        dcc.Store(id=POSE_PLAY_STATE_STORE_ID, data=False),
        dcc.Interval(
            id=POSE_INTERVAL_ID,
            interval=1000 // PREVIEW_FPS,
            n_intervals=0,
            disabled=True,
        ),
    ]
)

POSE_DOCK = html.Div(
    [angles_block, keyframes_block, hidden_components],
    className="ind-card page-dock",
)
