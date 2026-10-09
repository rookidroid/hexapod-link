# Controls of the workspace (pages/workspace.py, pages/page_pose.py).
#
# The rail down the left picks one tool and shows its panel:
#
#   Body   inverse kinematics: move and tilt the body over planted feet
#   Feet   move each foot, by dragging it in the 3D view or typing where
#   Robot  the link, streaming and the robot's dimensions (assembled in
#          pages/workspace.py, since its parts live elsewhere)
#
# Over the view, the joint angles are read out and the pose and the camera
# can be reset. Along the bottom, the dock plays a sequence, which is either
# the keyframes collected here or one of the robot's gaits: previewing it in
# the view, and running it on the robot.
import dash_bootstrap_components as dbc
from dash import dcc, html

from hexapod.const import NAMES_JOINT, NAMES_LEG
from hexapod.keyframes import DEFAULT_DURATION_MS, MAX_DURATION_MS, MIN_DURATION_MS
from hexapod.naming import leg_label
from widgets.ik_ui import IK_WIDGETS
from hexapod.robot_link import ROBOT_LINK
from widgets.robot_link_ui import SECTION_CONTROLS_OFFLINE_CLASS
from widgets.section_maker import (
    LEG_SIDES,
    field_label,
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
TOOL_BODY = "body"
TOOL_FEET = "feet"
TOOL_ROBOT = "robot"
TOOLS = (TOOL_BODY, TOOL_FEET, TOOL_ROBOT)
POSE_TOOL_PANEL_IDS = {tool: f"pose-panel-{tool}" for tool in TOOLS}

POSE_STATE_STORE_ID = "pose-state"
POSE_KEYFRAMES_STORE_ID = "pose-keyframes"
POSE_SELECTED_KF_STORE_ID = "pose-selected-keyframe"
POSE_PREVIEW_STORE_ID = "pose-preview"
POSE_PLAY_STATE_STORE_ID = "pose-play-state"
POSE_INTERVAL_ID = "pose-interval"

# The Feet tool's picker and fields: which foot, and where it is.
POSE_FOOT_LEG_ID = "pose-foot-leg"
POSE_FOOT_X_ID = "pose-foot-x"
POSE_FOOT_Y_ID = "pose-foot-y"
POSE_FOOT_UP_ID = "pose-foot-up"
POSE_FOOT_FIELD_IDS = (POSE_FOOT_X_ID, POSE_FOOT_Y_ID, POSE_FOOT_UP_ID)


# The Feet tool's joint grid: one field per leg and joint, e.g.
# "pose-joint-left-front-coxia".
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
ANGLES_HUD_ID = "pose-angles-hud"
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

# What the dock plays: the keyframes, or one of the robot's gaits.
POSE_SOURCE_ID = "pose-source"
SOURCE_KEYFRAMES = "keyframes"
SOURCE_GAIT = "gait"
SOURCES = (SOURCE_KEYFRAMES, SOURCE_GAIT)
# The part of the dock that belongs to each source, shown only with it.
POSE_SOURCE_PART_IDS = {
    SOURCE_KEYFRAMES: "pose-keyframes-part",
    SOURCE_GAIT: "pose-gait-part",
}
POSE_GAIT_ID = "pose-gait"
POSE_GAIT_MODE_ID = "pose-gait-mode"
POSE_GAIT_SPEED_ID = "pose-gait-speed"
GAIT_NATIVE = "native"
GAIT_STREAM = "stream"

POSE_SAVE_BTN_ID = "pose-save-btn"
POSE_DOWNLOAD_ID = "pose-download"
POSE_UPLOAD_ID = "pose-upload"

# Most frames a second the preview is drawn at in the browser. Keyframes are
# previewed at this rate; a gait at its own, every so many frames if that is
# faster. The robot gets its own, faster, frames: see run_on_robot() in
# pages/page_pose.py.
PREVIEW_FPS = 25

# The gaits the path tool generates (hexapod/path_generator.py), by the
# simulator's name for each; the robot's own command list says which it can
# also play from flash.
MOTION_TYPES = [
    {"label": "Standby (reset)", "value": "standby"},
    {"label": "Walk forward", "value": "walk_0"},
    {"label": "Walk backward", "value": "walk_180"},
    {"label": "Walk right 45°", "value": "walk_r45"},
    {"label": "Walk right 90°", "value": "walk_r90"},
    {"label": "Walk right 135°", "value": "walk_r135"},
    {"label": "Walk left 45°", "value": "walk_l45"},
    {"label": "Walk left 90°", "value": "walk_l90"},
    {"label": "Walk left 135°", "value": "walk_l135"},
    {"label": "Fast forward", "value": "fast_forward"},
    {"label": "Fast backward", "value": "fast_backward"},
    {"label": "Turn left", "value": "turn_left"},
    {"label": "Turn right", "value": "turn_right"},
    {"label": "Climb forward", "value": "climb_forward"},
    {"label": "Climb backward", "value": "climb_backward"},
    {"label": "Rotate X (pitch)", "value": "rotate_x"},
    {"label": "Rotate Y (roll)", "value": "rotate_y"},
    {"label": "Rotate Z (wobble)", "value": "rotate_z"},
    {"label": "Twist (figure-8)", "value": "twist"},
    {"label": "Stand up", "value": "standup"},
]

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
        className=class_name,
        **props,
    )


def _row(children, class_name=""):
    return html.Div(children, className=f"dock-row {class_name}".strip())


def _group(children, class_name=""):
    return html.Div(children, className=f"dock-group {class_name}".strip())


def _segmented(component_id, options, value, class_name="", **props):
    return dbc.RadioItems(
        id=component_id,
        options=options,
        value=value,
        className=f"ind-segmented {class_name}".strip(),
        inputClassName="btn-check",
        labelClassName="btn btn-sm btn-outline-secondary",
        labelCheckedClassName="active",
        **props,
    )


# ................................
# RAIL
# ................................

# Remembered for the session, so a reload opens on the tool last picked. The
# glyph over each label is drawn by the CSS (RAIL in assets/industrial.css).
TOOL_RAIL = dbc.RadioItems(
    id=POSE_TOOL_ID,
    options=[
        {"label": "Body", "value": TOOL_BODY},
        {"label": "Feet", "value": TOOL_FEET},
        {"label": "Robot", "value": TOOL_ROBOT},
    ],
    value=TOOL_BODY,
    className="tool-rail",
    inputClassName="btn-check",
    labelClassName="rail-item",
    labelCheckedClassName="active",
    persistence=True,
    persistence_type="session",
)


# ................................
# TOOL PANELS
#
# All of them stay mounted, so their sliders keep their values and their
# callbacks keep firing; the ones not in use are only hidden.
# ................................

BODY_PANEL = html.Div(
    panel_section(
        "Body",
        IK_WIDGETS,
        blurb="Move and tilt the body; the joints are solved to keep the feet planted.",
    ),
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


FEET_PANEL = html.Div(
    [
        panel_section(
            "Feet",
            [
                html.Div(
                    [
                        field_label("Foot"),
                        dbc.Select(
                            id=POSE_FOOT_LEG_ID,
                            # Left legs then right, front to back, as in the
                            # angle table.
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
                # In the view's coordinates: x right, y forward, up from the
                # floor. Applied when the field is left or Enter is pressed,
                # not per digit.
                make_field_grid(
                    [
                        make_number_field(field_id, label, step=1, debounce=True, disabled=True)
                        for field_id, label in zip(
                            POSE_FOOT_FIELD_IDS, ("X (mm)", "Y (mm)", "Up (mm)")
                        )
                    ],
                    one_row=True,
                ),
                _button(
                    "Put feet back",
                    POSE_CLEAR_FEET_BTN_ID,
                    outline=True,
                    title="Put every foot back where standby has it, keeping the body move",
                ),
            ],
            blurb=(
                "Click a foot in the view and drag its arrows, or pick it here "
                "and type where it goes. A moved foot stays put while the body "
                "moves over it."
            ),
        ),
        panel_section(
            "Joints (°)",
            make_leg_sides(_joint_field),
            blurb="Or set a leg's joints: its foot goes where they put it.",
        ),
    ],
    id=POSE_TOOL_PANEL_IDS[TOOL_FEET],
    style={"display": "none"},
)

POSE_MESSAGE = html.Div(id=POSE_MESSAGE_ID, className="panel-message")


# ................................
# OVER THE VIEW
# ................................

VIEW_OVERLAY = [
    _button(
        "Reset pose",
        POSE_RESET_BTN_ID,
        outline=True,
        class_name="view-btn",
        title="Back to the robot's standby posture: undoes both Body and Feet",
    ),
    _button(
        "Reset view",
        POSE_RESET_VIEW_BTN_ID,
        outline=True,
        class_name="view-btn",
        title="Frame the robot again",
    ),
]

# A native <details>, so it folds away without a callback.
ANGLES_HUD = html.Details(
    [
        html.Summary("Joint angles (°)"),
        html.Div(id=POSE_ANGLES_ID),
    ],
    id=ANGLES_HUD_ID,
    open=True,
    className="angles-hud",
)


# ................................
# DOCK
#
# Two rows across the bottom of the window: what is played (the keyframes
# being collected, or a gait), then playing it -- in the view, and on the
# robot.
# ................................

keyframes_part = html.Div(
    [
        _group(
            [
                html.Div(id=POSE_KF_LIST_ID, className="ind-kf-strip"),
                html.Div(id=POSE_KF_SUMMARY_ID, className="dock-note"),
            ],
            "dock-grow",
        ),
        _group(
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
                _button(
                    "+ Add",
                    POSE_ADD_BTN_ID,
                    color="primary",
                    title="Add the pose after the selected keyframe",
                ),
                _button(
                    "Update",
                    POSE_UPDATE_BTN_ID,
                    outline=True,
                    title="Overwrite the selected keyframe with the pose",
                ),
                _button("Delete", POSE_DELETE_BTN_ID, color="danger", outline=True),
                html.Div(
                    [
                        _button("◀", POSE_EARLIER_BTN_ID, outline=True, title="Move earlier"),
                        _button("▶", POSE_LATER_BTN_ID, outline=True, title="Move later"),
                    ],
                    className="btn-group",
                ),
            ]
        ),
        _group(
            [
                dcc.Checklist(
                    id=POSE_EASE_ID,
                    options=[{"label": "Ease", "value": "ease"}],
                    value=["ease"],
                    className="dock-check",
                ),
                _button("Save…", POSE_SAVE_BTN_ID, outline=True),
                dcc.Upload(
                    _button("Load…", outline=True),
                    id=POSE_UPLOAD_ID,
                    accept=".json,application/json",
                ),
                dcc.Download(id=POSE_DOWNLOAD_ID),
            ]
        ),
    ],
    id=POSE_SOURCE_PART_IDS[SOURCE_KEYFRAMES],
    className="dock-part",
)

# Gait speed, as a percent of the robot's tuned frame rate: how fast the robot
# plays a gait, and so how fast it is previewed. Its range and value are
# re-seeded from the connected robot (sync_robot_controls in page_pose.py).
_speed = ROBOT_LINK.robot_config["speed"]
gait_part = html.Div(
    [
        _group(
            dbc.Select(id=POSE_GAIT_ID, options=MOTION_TYPES, value="walk_0", size="sm"),
            "dock-gait-select",
        ),
        _group(
            _segmented(
                POSE_GAIT_MODE_ID,
                [
                    {"label": "Robot's own", "value": GAIT_NATIVE},
                    {"label": "Stream frames", "value": GAIT_STREAM},
                ],
                GAIT_NATIVE,
            ),
            "dock-gait-mode",
        ),
        html.Div(
            [
                field_label("Speed (%)"),
                dcc.Slider(
                    id=POSE_GAIT_SPEED_ID,
                    min=_speed["min"],
                    max=_speed["max"],
                    step=5,
                    value=ROBOT_LINK.speed_pct,
                    marks=None,
                    allow_direct_input=True,
                ),
            ],
            className="ind-inline-slider dock-grow",
            title=(
                "How fast the robot plays the gait, of its tuned rate; the "
                "preview plays at the same speed. Played from flash, the "
                "robot's own gait is smoother than streamed frames."
            ),
        ),
    ],
    id=POSE_SOURCE_PART_IDS[SOURCE_GAIT],
    className="dock-part",
    style={"display": "none"},
)

sequence_row = _row(
    [
        _segmented(
            POSE_SOURCE_ID,
            [
                {"label": "Keyframes", "value": SOURCE_KEYFRAMES},
                {"label": "Gait", "value": SOURCE_GAIT},
            ],
            SOURCE_KEYFRAMES,
            class_name="dock-source",
            persistence=True,
            persistence_type="session",
        ),
        keyframes_part,
        gait_part,
    ]
)

# The view shows the pose (which the tools edit) or the sequence (which plays).
transport_row = _row(
    [
        _segmented(
            POSE_VIEW_MODE_ID,
            [
                {"label": "Pose", "value": MODE_EDIT},
                {"label": "Sequence", "value": MODE_PREVIEW},
            ],
            MODE_EDIT,
            class_name="dock-source",
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
                # The frame counter beside it already says where it is.
                allow_direct_input=False,
            ),
            className="ind-dock-scrubber",
        ),
        html.Div("0/0 · 0.00 s", id=POSE_FRAME_DISPLAY_ID, className="dock-note text-nowrap"),
        # Loops the preview and what is run on the robot alike.
        dcc.Checklist(
            id=POSE_LOOP_ID,
            options=[{"label": "Loop", "value": "loop"}],
            value=[],
            className="dock-check",
        ),
        html.Div(className="dock-divider"),
        html.Div(
            [
                _button("▶ Run on robot", POSE_RUN_BTN_ID, color="success", disabled=True),
                _button("■ Standby", POSE_STOP_BTN_ID, outline=True, disabled=True),
            ],
            id=POSE_ROBOT_CONTROLS_ID,
            className=f"d-flex gap-2 {SECTION_CONTROLS_OFFLINE_CLASS}",
        ),
        html.Div(
            "Connect a robot to run this on the hardware.",
            id=POSE_ROBOT_MESSAGE_ID,
            className="dock-note dock-robot-message",
        ),
    ]
)

# The pose and the sequence being built live in session storage, so they
# survive a reload. Each store records which robot it was made on; see
# pages/page_pose.py.
hidden_components = html.Div(
    [
        dcc.Store(id=POSE_FOOT_TARGET_ID),
        dcc.Store(id=POSE_SELECTED_LEG_ID),
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
    [
        sequence_row,
        transport_row,
        html.Div(id=POSE_PREVIEW_MESSAGE_ID, className="dock-message"),
        hidden_components,
    ],
    className="dock",
)
