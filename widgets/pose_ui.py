# Controls of the workspace (pages/workspace.py, pages/pose.py).
#
# The pose is set on the view itself. In its corner, the joint angles are read
# out and can be typed, and under them are the controls of whatever is picked
# -- by clicking it in the view, or its button here:
#
#   the body  inverse kinematics: move and tilt it over the planted feet, with
#             its sliders or by dragging its handles in the view
#   a foot    move it, by dragging it in the view or typing where it goes
#
# Over the view too, the pose and the camera can be reset; streaming to the
# robot and the robot's dimensions are there as well (widgets/robot_link_ui.py,
# widgets/dimensions_ui.py). Along the bottom, the dock builds a sequence of
# keyframes -- poses collected here, and gaits from its library: the robot's,
# and sequences saved as gaits of one's own -- and plays it: previewing it in
# the view, and running it on the robot.
import dash_bootstrap_components as dbc
from dash import dcc, html

from hexapod.keyframes import DEFAULT_DURATION_MS, MAX_DURATION_MS, MIN_DURATION_MS
from hexapod.naming import JOINT_NAMES, LEG_NAMES, joint_label, joint_number, leg_label
from widgets.body_ui import ROTATE_WIDGETS, TRANSLATE_WIDGETS
from widgets.robot_link_ui import SECTION_CONTROLS_OFFLINE_CLASS
from widgets.components import (
    LEG_SIDES,
    field_label,
    make_field_grid,
    make_joint_grid,
    make_number_field,
    make_splitter,
    short_leg_name,
)

# --- Element IDs ---
# Written by assets/hexapod_view.js through set_props; keep the two in step.
# Where a foot, or the body, has been dragged to; and what is picked: a leg's
# id, SELECT_BODY, or nothing.
POSE_FOOT_TARGET_ID = "pose-foot-target"
POSE_BODY_TARGET_ID = "pose-body-target"
POSE_SELECTION_ID = "pose-selection"
SELECT_BODY = "body"

POSE_VIEW_ID = "view-pose"

POSE_STATE_STORE_ID = "pose-state"
POSE_KEYFRAMES_STORE_ID = "pose-keyframes"
POSE_SELECTED_KF_STORE_ID = "pose-selected-keyframe"
POSE_PREVIEW_STORE_ID = "pose-preview"
POSE_PLAY_STATE_STORE_ID = "pose-play-state"
POSE_INTERVAL_ID = "pose-interval"

# The buttons that pick what to adjust, as clicking it in the view does: the
# body's, and each leg's, in id order (LEG_NAMES).
POSE_PICK_BODY_ID = "pose-pick-body"
POSE_PICK_LEG_IDS = [f"pose-pick-{leg_name}" for leg_name in LEG_NAMES]
PICK_BTN_CLASS = "hud-pick"

# What is shown under the angles: a hint with nothing picked, or the controls
# of the body or of the foot picked.
POSE_ADJUST_HINT_ID = "pose-adjust-hint"
POSE_ADJUST_BODY_ID = "pose-adjust-body"
POSE_ADJUST_FOOT_ID = "pose-adjust-foot"

# Which handles the body picked has in the view, to drag it by: arrows that
# move it, or rings that turn it. The values are the view's names for them.
POSE_BODY_MODE_ID = "pose-body-mode"
BODY_MODE_MOVE = "translate"
BODY_MODE_ROTATE = "rotate"

# Where the foot picked is, and which one it is.
POSE_FOOT_TITLE_ID = "pose-foot-title"
POSE_FOOT_X_ID = "pose-foot-x"
POSE_FOOT_Y_ID = "pose-foot-y"
POSE_FOOT_UP_ID = "pose-foot-up"
POSE_FOOT_FIELD_IDS = (POSE_FOOT_X_ID, POSE_FOOT_Y_ID, POSE_FOOT_UP_ID)


# The joint angles: one field per leg and joint, e.g.
# "pose-joint-left-front-coxia".
def pose_joint_id(leg_name, joint_name):
    return f"pose-joint-{leg_name}-{joint_name}"


# Leg by leg in id order (LEG_NAMES), joints coxia, femur, tibia.
POSE_JOINT_FIELDS = [
    (leg_id, joint_name, pose_joint_id(leg_name, joint_name))
    for leg_id, leg_name in enumerate(LEG_NAMES)
    for joint_name in JOINT_NAMES
]
POSE_JOINT_FIELD_IDS = [field_id for _, _, field_id in POSE_JOINT_FIELDS]
# Says which legs are out of reach, under the angles.
POSE_ANGLES_ID = "pose-angles"
ANGLES_HUD_ID = "pose-angles-hud"
# The update_pose callback (pages/pose.py) adds "is-bad" to it while a
# leg is out of reach.
ANGLES_HUD_CLASS = "hud-panel angles-hud"
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
POSE_KF_EDITOR_LABEL_ID = "pose-keyframe-editor-label"
# Pattern-matching id of one entry in the keyframe list.
POSE_KF_ITEM_TYPE = "pose-keyframe-item"

# What the view shows, MODE_EDIT or MODE_PREVIEW: the pose, or the sequence.
# Nothing picks it by hand: Play and grabbing the scrubber show the sequence
# (assets/sequence_scrubber.js), editing the pose or loading a keyframe shows
# the pose.
POSE_VIEW_MODE_ID = "pose-view-mode"
# Where playback came to rest, as {"frame", "n"}: written when it is paused or
# runs out, and when the scrubber is let go (assets/sequence_scrubber.js).
# That frame becomes the pose (edit() in pages/pose.py).
POSE_PLAYHEAD_ID = "pose-playhead"
POSE_LOOP_ID = "pose-loop"
POSE_KF_EASE_ID = "pose-keyframe-ease"
POSE_PLAY_BTN_ID = "pose-play-btn"
POSE_FRAME_SLIDER_ID = "pose-frame-slider"
POSE_FRAME_DISPLAY_ID = "pose-frame-display"
POSE_PREVIEW_MESSAGE_ID = "pose-preview-message"

POSE_ROBOT_CONTROLS_ID = "pose-robot-controls"
POSE_RUN_BTN_ID = "pose-run-btn"
POSE_STOP_BTN_ID = "pose-stop-btn"
POSE_ROBOT_MESSAGE_ID = "pose-robot-message"

# The dock's Gaits library: which list it shows, the robot's built-in gaits or
# one's own.
POSE_GAIT_SOURCE_ID = "pose-gait-source"
GAIT_SOURCE_BUILTIN = "builtin"
GAIT_SOURCE_MINE = "mine"
GAIT_SOURCES = (GAIT_SOURCE_BUILTIN, GAIT_SOURCE_MINE)
POSE_GAIT_LIST_IDS = {source: f"pose-gait-list-{source}" for source in GAIT_SOURCES}
# Pattern-matching ids of a built-in gait's buttons, by its motion name: + puts
# it into the sequence, ⇄ makes it the whole sequence.
POSE_GAIT_ITEM_TYPE = "pose-gait-item"
POSE_GAIT_REPLACE_TYPE = "pose-gait-replace"
# One's own gaits (hexapod/gait_library.py): the name to save the sequence
# under, the list, and, by gait id, each one's add, replace and delete
# buttons. The version store is bumped by a save or a delete, to list them
# again.
POSE_USER_GAIT_NAME_ID = "pose-user-gait-name"
POSE_USER_GAIT_SAVE_BTN_ID = "pose-user-gait-save-btn"
POSE_USER_GAIT_LIST_ID = "pose-user-gait-list"
POSE_USER_GAIT_MESSAGE_ID = "pose-user-gait-message"
POSE_USER_GAIT_ITEM_TYPE = "pose-user-gait-item"
POSE_USER_GAIT_REPLACE_TYPE = "pose-user-gait-replace"
POSE_USER_GAIT_DELETE_TYPE = "pose-user-gait-delete"
POSE_USER_GAITS_VERSION_ID = "pose-user-gaits-version"
# How fast the sequence plays, in percent: in the preview and on the robot.
POSE_SPEED_ID = "pose-speed"
SPEED_MIN_PCT = 25
SPEED_MAX_PCT = 200

POSE_SAVE_BTN_ID = "pose-save-btn"
POSE_DOWNLOAD_ID = "pose-download"
POSE_UPLOAD_ID = "pose-upload"

# Frames a second the preview is drawn at in the browser. The robot gets its
# own, faster, frames: see run_on_robot() in pages/pose.py.
PREVIEW_FPS = 25

# The gaits the path tool generates (hexapod/path_generator.py), by the
# simulator's name for each. Put into the sequence from the Gaits library, a gait
# becomes keyframes (hexapod/gait_keyframes.py) and is streamed to the robot
# with the rest; the robot's own, played from its flash, are driven from the
# controller over the view (DRIVE_HUD in widgets/robot_link_ui.py).
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
GAIT_LABELS = {option["value"]: option["label"] for option in MOTION_TYPES}

# The library's built-in gaits, in groups.
GAIT_MENU = [
    (
        "Walk",
        ["walk_0", "walk_180", "walk_l45", "walk_l90", "walk_l135"]
        + ["walk_r45", "walk_r90", "walk_r135"],
    ),
    (
        "Fast, turn and climb",
        ["fast_forward", "fast_backward", "turn_left", "turn_right"]
        + ["climb_forward", "climb_backward"],
    ),
    ("Body", ["rotate_x", "rotate_y", "rotate_z", "twist"]),
    ("Posture", ["standby", "standup"]),
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


# ................................
# OVER THE VIEW
# ................................

VIEW_OVERLAY = [
    _button(
        "Reset pose",
        POSE_RESET_BTN_ID,
        outline=True,
        class_name="view-btn",
        title="Back to the robot's standby posture: undoes every move of the body and the feet",
    ),
    _button(
        "Reset view",
        POSE_RESET_VIEW_BTN_ID,
        outline=True,
        class_name="view-btn",
        title="Frame the robot again",
    ),
]


# ................................
# THE POSE
#
# In the view's corner: the joint angles, under the buttons that pick what to
# adjust, then the controls of what is picked. All of them stay mounted, so
# their fields keep their values and their callbacks keep firing; those of
# what is not picked are only hidden.
# ................................

# Left legs then right, front to back.
ANGLE_COLUMNS = [name for _, legs in LEG_SIDES for name in legs]


def _joint_field(joint_index, column):
    # Applied when the field is left or Enter is pressed, not per digit. Left
    # empty for a leg that cannot reach its foot, whose angles mean nothing.
    return dbc.Input(
        id=pose_joint_id(ANGLE_COLUMNS[column], JOINT_NAMES[joint_index]),
        type="number",
        step=0.1,
        debounce=True,
        size="sm",
        placeholder="—",
    )


def _pick_button(label, button_id, title):
    return html.Button(label, id=button_id, className=PICK_BTN_CLASS, title=title)


# Legs and joints are named the way the robot firmware names them, so a value
# can be read straight onto the robot's calibration page: a column per leg
# under the button that picks its foot, a row per joint. Typing an angle puts
# the leg's foot where it leads.
angle_table = make_joint_grid(
    [
        (index, html.Span(f"J{joint_number(joint)}", title=joint_label(joint)))
        for index, joint in enumerate(JOINT_NAMES)
    ],
    [
        _pick_button(
            short_leg_name(name),
            POSE_PICK_LEG_IDS[LEG_NAMES.index(name)],
            f"{leg_label(name)}: pick its foot, to move it",
        )
        for name in ANGLE_COLUMNS
    ],
    _joint_field,
    class_name="ind-angle-strip mb-0",
    corner=_pick_button("Body", POSE_PICK_BODY_ID, "Pick the body, to move and tilt it"),
)

ADJUST_HINT = html.Div(
    "Click the body or a foot, in the view or above, to adjust it.",
    id=POSE_ADJUST_HINT_ID,
    className="hud-hint",
)

body_mode_toggle = dbc.RadioItems(
    id=POSE_BODY_MODE_ID,
    options=[
        {"label": "Move", "value": BODY_MODE_MOVE},
        {"label": "Rotate", "value": BODY_MODE_ROTATE},
    ],
    value=BODY_MODE_MOVE,
    className="dock-seg",
    inputClassName="btn-check",
    labelClassName="dock-seg-item",
    labelCheckedClassName="active",
)

ADJUST_BODY = html.Div(
    [
        html.Div(
            [
                html.Span("Body", className="hud-adjust-title"),
                html.Div(
                    [field_label("Drag to"), body_mode_toggle],
                    className="hud-adjust-mode",
                    title="What dragging the body in the view does: its arrows move it, its rings turn it",
                ),
            ],
            className="hud-adjust-head",
        ),
        # The joints are solved to keep the feet planted.
        html.Div(
            [html.Div(TRANSLATE_WIDGETS), html.Div(ROTATE_WIDGETS)],
            className="hud-body-sliders",
        ),
    ],
    id=POSE_ADJUST_BODY_ID,
    style={"display": "none"},
)

ADJUST_FOOT = html.Div(
    [
        html.Div(
            [
                html.Span("Foot", id=POSE_FOOT_TITLE_ID, className="hud-adjust-title"),
                _button(
                    "Put feet back",
                    POSE_CLEAR_FEET_BTN_ID,
                    outline=True,
                    class_name="view-btn",
                    title="Put every foot back where standby has it, keeping the body move",
                ),
            ],
            className="hud-adjust-head",
        ),
        # In the view's coordinates: x right, y forward, up from the floor.
        # Applied when the field is left or Enter is pressed, not per digit.
        # A moved foot stays put while the body moves over it.
        make_field_grid(
            [
                make_number_field(field_id, label, step=1, debounce=True)
                for field_id, label in zip(POSE_FOOT_FIELD_IDS, ("X (mm)", "Y (mm)", "Up (mm)"))
            ],
            one_row=True,
        ),
    ],
    id=POSE_ADJUST_FOOT_ID,
    style={"display": "none"},
)

# A native <details>, so it folds away without a callback.
ANGLES_HUD = html.Details(
    [
        html.Summary("Joint angles (°)"),
        angle_table,
        html.Div(id=POSE_ANGLES_ID, className="hud-message"),
        html.Div(id=POSE_MESSAGE_ID, className="hud-message"),
        html.Div([ADJUST_HINT, ADJUST_BODY, ADJUST_FOOT], className="hud-adjust"),
    ],
    id=ANGLES_HUD_ID,
    open=True,
    className=ANGLES_HUD_CLASS,
)


# ................................
# DOCK
#
# Three columns across the bottom of the window. On the left, the library of
# gaits to put into the sequence: the robot's, and one's own. In the middle,
# the sequence: the track of keyframes -- poses, and gaits put in as theirs --
# and an editor for the one selected. On the right, playing it: in the view,
# then on the robot. The side columns' widths can be dragged; the middle one
# takes what is left.
# ................................


def _section(title, children, head=None, class_name=""):
    """A titled block of the dock: the title, with `head` beside it, over the
    block's rows."""
    head_row = html.Div(
        [html.H6(title, className="dock-section-title"), *(head or [])],
        className="dock-section-head",
    )
    return html.Section(
        [head_row, *children],
        className=f"dock-section {class_name}".strip(),
    )


# Beside the title: the keyframes' count and length, and their file.
sequence_tools = [
    html.Div(id=POSE_KF_SUMMARY_ID, className="dock-note"),
    html.Div(
        [
            dcc.Upload(
                _button("Load…", outline=True, title="Load keyframes from a file"),
                id=POSE_UPLOAD_ID,
                accept=".json,application/json",
            ),
            _button(
                "Save…", POSE_SAVE_BTN_ID, outline=True, title="Save the keyframes to a file"
            ),
            dcc.Download(id=POSE_DOWNLOAD_ID),
        ],
        className="dock-group dock-push",
    ),
]


# ---- The Gaits library ----

INSERT_TITLE = "Add it to the sequence, after the keyframe selected or at the end"
REPLACE_TITLE = "Replace the whole sequence with it"


def _gait_row(label, insert_id, replace_id, note=None, extra=None):
    """A gait in the library: its name, a note under it, and the buttons that
    add it to the sequence or make it the sequence (and any others, after
    them)."""
    return html.Div(
        [
            html.Div(
                [
                    html.Span(label, className="dock-gait-name"),
                    *([html.Span(note, className="dock-gait-note")] if note else []),
                ],
                className="dock-gait-text",
            ),
            _button(
                "+", outline=True, class_name="dock-gait-btn", id=insert_id, title=INSERT_TITLE
            ),
            _button(
                "⇄", outline=True, class_name="dock-gait-btn", id=replace_id, title=REPLACE_TITLE
            ),
            *(extra or []),
        ],
        className="dock-gait-row",
    )


def _builtin_gait_list():
    items = []
    for group, motions in GAIT_MENU:
        items.append(html.Div(group, className="dock-gait-group"))
        items.extend(
            _gait_row(
                GAIT_LABELS[motion],
                {"type": POSE_GAIT_ITEM_TYPE, "index": motion},
                {"type": POSE_GAIT_REPLACE_TYPE, "index": motion},
            )
            for motion in motions
        )
    return items


def user_gait_row(gait):
    """One of one's own gaits, as listed by hexapod/gait_library.py. Its delete
    button asks first: the file is gone for good."""
    count = gait["count"]
    note = f"{count} keyframe{'s' if count != 1 else ''} · {gait['duration_ms'] / 1000:.2f} s"
    delete = dcc.ConfirmDialogProvider(
        _button(
            "×",
            outline=True,
            class_name="dock-gait-btn dock-gait-delete",
            title="Delete this gait",
        ),
        id={"type": POSE_USER_GAIT_DELETE_TYPE, "index": gait["id"]},
        message=f"Delete the gait '{gait['name']}'? This cannot be undone.",
    )
    return _gait_row(
        gait["name"],
        {"type": POSE_USER_GAIT_ITEM_TYPE, "index": gait["id"]},
        {"type": POSE_USER_GAIT_REPLACE_TYPE, "index": gait["id"]},
        note=note,
        extra=[delete],
    )


USER_GAITS_EMPTY = html.Div(
    "None yet: build a sequence, name it and save it here.",
    className="dock-empty",
)

# Which list shows is remembered for the session, as the tool is.
gait_source_toggle = dbc.RadioItems(
    id=POSE_GAIT_SOURCE_ID,
    options=[
        {"label": "Built-in", "value": GAIT_SOURCE_BUILTIN},
        {"label": "Mine", "value": GAIT_SOURCE_MINE},
    ],
    value=GAIT_SOURCE_BUILTIN,
    className="dock-seg dock-push",
    inputClassName="btn-check",
    labelClassName="dock-seg-item",
    labelCheckedClassName="active",
    persistence=True,
    persistence_type="session",
)

# Both lists stay mounted; the one not picked is only hidden.
library_section = _section(
    "Gaits",
    [
        html.Div(
            _builtin_gait_list(),
            id=POSE_GAIT_LIST_IDS[GAIT_SOURCE_BUILTIN],
            className="dock-gait-list",
        ),
        html.Div(
            [
                # Keeps the whole sequence under the name; a gait of that
                # name already there is replaced.
                html.Div(
                    [
                        dbc.Input(
                            id=POSE_USER_GAIT_NAME_ID,
                            placeholder="Name",
                            maxLength=40,
                            size="sm",
                        ),
                        _button(
                            "Save sequence",
                            POSE_USER_GAIT_SAVE_BTN_ID,
                            color="primary",
                            title="Keep the whole sequence as a gait of your own",
                        ),
                    ],
                    className="dock-gait-save",
                ),
                html.Div(id=POSE_USER_GAIT_MESSAGE_ID, className="dock-message"),
                html.Div(USER_GAITS_EMPTY, id=POSE_USER_GAIT_LIST_ID, className="dock-gait-list"),
            ],
            id=POSE_GAIT_LIST_IDS[GAIT_SOURCE_MINE],
            className="dock-gait-mine",
            style={"display": "none"},
        ),
    ],
    head=[gait_source_toggle],
    class_name="dock-library",
)


# ---- The sequence ----

keyframes_part = html.Div(
    [
        # The keyframes in order, each with when it is reached and, on the
        # arrow into it, how long it takes to get there (list_keyframes in
        # pages/pose.py).
        html.Div(
            [
                html.Div(id=POSE_KF_LIST_ID, className="ind-kf-strip"),
                _button(
                    "+ Add pose",
                    POSE_ADD_BTN_ID,
                    color="primary",
                    class_name="dock-add-btn",
                    title="Record the pose as a keyframe",
                ),
            ],
            className="dock-track",
        ),
        # The keyframe selected; with none, the time and easing are the next
        # one's. Two rows: what it is and how it is reached, then what can be
        # done to it.
        html.Div(
            [
                html.Div(
                    [
                        html.Span(
                            "New keyframe", id=POSE_KF_EDITOR_LABEL_ID, className="dock-kf-label"
                        ),
                        html.Div(
                            [
                                field_label("Transition"),
                                dbc.InputGroup(
                                    [
                                        # Applied when the field is left or Enter is
                                        # pressed, not per digit. No min, max or step,
                                        # for the same reason as the speed's: the
                                        # range is kept by edit() in pages/pose.py.
                                        dbc.Input(
                                            id=POSE_DURATION_ID,
                                            type="number",
                                            value=DEFAULT_DURATION_MS,
                                            debounce=True,
                                        ),
                                        dbc.InputGroupText("ms"),
                                    ],
                                    size="sm",
                                    className="ind-duration-input",
                                ),
                            ],
                            className="dock-inline-field",
                            title=(
                                "Time to reach this keyframe from the one before it, "
                                f"{MIN_DURATION_MS} to {MAX_DURATION_MS} ms"
                            ),
                        ),
                        html.Div(
                            dcc.Checklist(
                                id=POSE_KF_EASE_ID,
                                options=[{"label": "Ease in", "value": "ease"}],
                                value=["ease"],
                                className="dock-check",
                            ),
                            title=(
                                "Start and stop the move into this keyframe gently. Off, "
                                "it runs at a steady speed, as a gait's moves do."
                            ),
                        ),
                    ],
                    className="dock-kf-row",
                ),
                html.Div(
                    [
                        _button(
                            "Save pose",
                            POSE_UPDATE_BTN_ID,
                            outline=True,
                            disabled=True,
                            title="Overwrite the selected keyframe with the pose",
                        ),
                        html.Div(
                            [
                                _button(
                                    "◀",
                                    POSE_EARLIER_BTN_ID,
                                    outline=True,
                                    disabled=True,
                                    title="Move earlier",
                                ),
                                _button(
                                    "▶",
                                    POSE_LATER_BTN_ID,
                                    outline=True,
                                    disabled=True,
                                    title="Move later",
                                ),
                            ],
                            className="btn-group",
                        ),
                        _button(
                            "Delete",
                            POSE_DELETE_BTN_ID,
                            color="danger",
                            outline=True,
                            disabled=True,
                            title="Delete the selected keyframe",
                            class_name="dock-push",
                        ),
                    ],
                    className="dock-kf-row",
                ),
            ],
            className="dock-kf-editor",
        ),
    ],
    className="dock-part dock-part-stack",
)

sequence_section = _section(
    "Sequence",
    [keyframes_part, html.Div(id=POSE_PREVIEW_MESSAGE_ID, className="dock-message")],
    head=sequence_tools,
    class_name="dock-sequence",
)

# The transport beside its title, then how it plays; the robot's buttons
# beside their title.
playback_section = _section(
    "Playback",
    [
        html.Div(
            [
                html.Div(
                    [
                        field_label("Speed"),
                        dbc.InputGroup(
                            [
                                dbc.Input(
                                    id=POSE_SPEED_ID,
                                    # No min, max or step: the browser hands
                                    # a number outside them over as empty, so
                                    # the range is kept by set_speed in
                                    # pages/pose.py instead.
                                    type="number",
                                    value=100,
                                    debounce=True,
                                ),
                                dbc.InputGroupText("%"),
                            ],
                            size="sm",
                            className="ind-duration-input",
                        ),
                    ],
                    className="dock-inline-field",
                    title=(
                        "How fast the whole sequence plays, in the preview and on "
                        f"the robot, {SPEED_MIN_PCT} to {SPEED_MAX_PCT} %. At 100 % "
                        "a gait plays at the robot's own speed."
                    ),
                ),
                # Loops the preview and what is run on the robot alike.
                dcc.Checklist(
                    id=POSE_LOOP_ID,
                    options=[{"label": "Loop", "value": "loop"}],
                    value=[],
                    className="dock-check",
                ),
            ],
            className="dock-group dock-group-wide",
        ),
    ],
    head=[
        _button("▶ Play", POSE_PLAY_BTN_ID, color="primary", class_name="ind-play-btn"),
        html.Div(
            dcc.Slider(
                id=POSE_FRAME_SLIDER_ID,
                min=0,
                max=1,
                step=1,
                value=0,
                marks=None,
                updatemode="drag",
                # The frame counter beside it already says where it is.
                allow_direct_input=False,
            ),
            className="ind-dock-scrubber",
        ),
        html.Div("0/0 · 0.00 s", id=POSE_FRAME_DISPLAY_ID, className="dock-note text-nowrap"),
    ],
)

robot_section = _section(
    "Robot",
    [
        html.Div(
            "Connect a robot to run this on the hardware.",
            id=POSE_ROBOT_MESSAGE_ID,
            className="dock-note dock-robot-message",
        ),
    ],
    head=[
        html.Div(
            [
                _button("▶ Run on robot", POSE_RUN_BTN_ID, color="success", disabled=True),
                _button("■ Standby", POSE_STOP_BTN_ID, outline=True, disabled=True),
            ],
            id=POSE_ROBOT_CONTROLS_ID,
            className=f"d-flex gap-2 {SECTION_CONTROLS_OFFLINE_CLASS}",
        ),
    ],
)

# The pose and the sequence being built live in session storage, so they
# survive a reload. Each store records which robot it was made on; see
# pages/pose.py.
hidden_components = html.Div(
    [
        dcc.Store(id=POSE_FOOT_TARGET_ID),
        dcc.Store(id=POSE_BODY_TARGET_ID),
        dcc.Store(id=POSE_SELECTION_ID),
        dcc.Store(id=POSE_STATE_STORE_ID, storage_type="session"),
        dcc.Store(id=POSE_KEYFRAMES_STORE_ID, storage_type="session"),
        dcc.Store(id=POSE_SELECTED_KF_STORE_ID, storage_type="session"),
        dcc.Store(id=POSE_PREVIEW_STORE_ID),
        dcc.Store(id=POSE_PLAY_STATE_STORE_ID, data=False),
        dcc.Store(id=POSE_VIEW_MODE_ID, data=MODE_EDIT),
        dcc.Store(id=POSE_PLAYHEAD_ID),
        dcc.Store(id=POSE_USER_GAITS_VERSION_ID, data=0),
        dcc.Interval(
            id=POSE_INTERVAL_ID,
            interval=1000 // PREVIEW_FPS,
            n_intervals=0,
            disabled=True,
        ),
    ],
    # Nothing to see, and kept out of the dock's grid.
    style={"display": "none"},
)

POSE_DOCK = html.Div(
    [
        html.Div(library_section, className="dock-col dock-col-library"),
        html.Div(sequence_section, className="dock-col dock-col-sequence"),
        html.Div([playback_section, robot_section], className="dock-col dock-col-run"),
        # On the lines between the columns; the sequence's takes what is left.
        make_splitter("lib", "vertical", "resize the Gaits library"),
        make_splitter("run", "vertical", "resize Playback and Robot"),
        hidden_components,
    ],
    className="dock",
)
