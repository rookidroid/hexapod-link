# What the workspace does (its layout is pages/workspace.py): set a pose,
# collect poses as keyframes -- and the robot's gaits, as theirs
# (hexapod/gait_keyframes.py) -- preview the sequence and run it on the robot.
#
# There is one pose: the robot's standby posture with two layers on top
# (hexapod/pose_layers.py), and a tool on the rail for each:
#
#   Feet  moving single feet away from where standby plants them, by dragging
#         them in the 3D view or typing where they go
#   Body  moving and tilting the body over wherever the feet are planted
#
# The layers add up, so neither tool undoes the other: tilt the body, move a
# foot, and both stay. The Body sliders always show the pose as it is, and
# both tools draw it the same way, in the world, so switching tools changes
# nothing but which controls are showing and whether the feet can be
# dragged. Out of the layers come the joint angles, what is
# streamed to the robot and what a keyframe keeps.
#
# The 3D view (assets/hexapod_view.js) reports a dragged foot through the POSE_FOOT_TARGET_ID store and draws
# whatever lands in the view's scene store, or a frame of the sequence while
# previewing; the kinematics all happen here.
#
# What is being edited lives in session stores, so it survives a reload:
#
#   pose       {"robot", "state": the layers, "feet": 6x3 in the body frame,
#               "seq"}
#   keyframes  {"robot", "keyframes": [...]}   see hexapod/keyframes.py
#   selected   index of the keyframe the pose was loaded from, or None
#
# Foot positions only fit the robot they were placed on, so the stores carry
# that robot's name, and a different robot connecting starts the editor
# afresh.
#
# The robot modelled is the connected one (or the last one, or the generic
# model), measured as the Robot panel's dimensions have it: they start on the
# robot's own and can be edited to try another body. Feet and keyframes are
# moves from standby and keep their meaning on the resized body; what is
# streamed to the robot is solved on it too.

import base64
import json
import numpy as np
from dash import ALL, callback, clientside_callback, ctx, html, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from hexapod import keyframes as kf
from hexapod.gait_keyframes import gait_keyframes
from hexapod import pose_layers as pl
from hexapod.const import NAMES_LEG
from hexapod.naming import leg_index, leg_label
from hexapod.robot_config import get_sequence_fps, with_dimensions
from hexapod.robot_link import ROBOT_LINK
from pages import helpers, shared
from widgets.ik_ui import IK_WIDGETS_IDS
from widgets.pose_ui import (
    MODE_EDIT,
    MODE_PREVIEW,
    ANGLES_HUD_CLASS,
    ANGLES_HUD_ID,
    POSE_ADD_BTN_ID,
    POSE_ANGLES_ID,
    POSE_CLEAR_FEET_BTN_ID,
    POSE_DELETE_BTN_ID,
    POSE_DOWNLOAD_ID,
    POSE_DURATION_ID,
    POSE_EARLIER_BTN_ID,
    POSE_FOOT_FIELD_IDS,
    POSE_JOINT_FIELDS,
    POSE_JOINT_FIELD_IDS,
    POSE_FOOT_LEG_ID,
    POSE_FOOT_TARGET_ID,
    POSE_FRAME_DISPLAY_ID,
    POSE_FRAME_SLIDER_ID,
    POSE_GAIT_ITEM_TYPE,
    POSE_INTERVAL_ID,
    POSE_KEYFRAMES_STORE_ID,
    POSE_KF_EASE_ID,
    POSE_KF_EDITOR_LABEL_ID,
    POSE_KF_ITEM_TYPE,
    POSE_KF_LIST_ID,
    POSE_KF_SUMMARY_ID,
    POSE_LATER_BTN_ID,
    POSE_LOOP_ID,
    POSE_MESSAGE_ID,
    POSE_PLAY_BTN_ID,
    POSE_PLAY_STATE_STORE_ID,
    POSE_PREVIEW_MESSAGE_ID,
    POSE_PREVIEW_STORE_ID,
    POSE_RESET_BTN_ID,
    POSE_RESET_VIEW_BTN_ID,
    POSE_ROBOT_CONTROLS_ID,
    POSE_ROBOT_MESSAGE_ID,
    POSE_RUN_BTN_ID,
    POSE_SAVE_BTN_ID,
    POSE_SELECTED_KF_STORE_ID,
    POSE_SELECTED_LEG_ID,
    POSE_STATE_STORE_ID,
    POSE_SPEED_ID,
    POSE_STOP_BTN_ID,
    POSE_TOOL_ID,
    POSE_TOOL_PANEL_IDS,
    POSE_UPDATE_BTN_ID,
    POSE_UPLOAD_ID,
    POSE_VIEW_ID,
    POSE_VIEW_MODE_ID,
    PREVIEW_FPS,
    SPEED_MAX_PCT,
    SPEED_MIN_PCT,
    TOOL_FEET,
    TOOLS,
)
from widgets.robot_link_ui import (
    DRIVE_BODY_CLASS,
    DRIVE_CONTROLS_ID,
    DRIVE_SPEED_ID,
    ROBOT_CONFIG_STORE_ID,
    ROBOT_POLL_INTERVAL_ID,
    SECTION_CONTROLS_CLASS,
    SECTION_CONTROLS_OFFLINE_CLASS,
)

# ......................
# The view and the tools
# ......................

POSE_SCENE_STORE_ID = shared.view_store_id(POSE_VIEW_ID)
POSE_RENDER_ACK_ID = f"{POSE_VIEW_ID}-ack"


# Show the tool's panel. The others are only hidden, so their sliders keep
# their values.
clientside_callback(
    """
    function(tool) {
        var show = {}, hide = {display: "none"};
        return [%s];
    }
    """
    % ", ".join(f'tool === "{tool}" ? show : hide' for tool in TOOLS),
    *[Output(POSE_TOOL_PANEL_IDS[tool], "style") for tool in TOOLS],
    Input(POSE_TOOL_ID, "value"),
)


# ......................
# Editor state
# ......................

# Which layer each slider sets.
BODY_WIDGET_KEYS = dict(zip(IK_WIDGETS_IDS, pl.BODY_KEYS))
# The leg and joint each joint field sets.
JOINT_FIELD_KEYS = {field_id: (leg, joint) for leg, joint, field_id in POSE_JOINT_FIELDS}


# The Robot panel's dimensions, as JSON (pages/shared.py).
DIMENSIONS_INPUT = Input(shared.DIMENSIONS_HIDDEN_SECTION_ID, "children")
DIMENSIONS_STATE = State(shared.DIMENSIONS_HIDDEN_SECTION_ID, "children")


def _robot(dimensions_json=None):
    """The robot this page models: the connected one's config, measured as
    the Robot panel has it (robot_config.with_dimensions)."""
    try:
        dimensions = json.loads(dimensions_json) if dimensions_json else None
    except (TypeError, ValueError):
        dimensions = None
    return with_dimensions(ROBOT_LINK.robot_config, dimensions)


def _pose_store(robot_config, state, seq=0):
    return {
        "robot": robot_config["name"],
        "state": state,
        "feet": pl.body_feet(state, robot_config),
        "seq": seq,
    }


def _fresh_keyframes(robot_config):
    return {"robot": robot_config["name"], "keyframes": []}


def _valid(store, robot_config):
    return isinstance(store, dict) and store.get("robot") == robot_config["name"]


def _valid_pose(store, robot_config):
    return _valid(store, robot_config) and pl.is_state(store.get("state"))


def _decode_upload(contents):
    # dcc.Upload hands over a data URL: "data:<type>;base64,<payload>"
    _, _, payload = contents.partition(",")
    return base64.b64decode(payload).decode("utf-8")


def _field_value(mm):
    """A foot coordinate or joint angle as its field shows it."""
    return round(mm, 1) + 0.0


def _keyframe_state(keyframe, robot_config):
    """The layers a keyframe was made from, or, for one that did not keep them
    (saved before keyframes did), its feet as moves from standby."""
    if pl.is_state(keyframe.get("state")):
        return pl.make_state(keyframe["state"]["body"], keyframe["state"]["offsets"])
    return pl.from_feet(keyframe["feet"], robot_config)


@callback(
    output=dict(
        pose=Output(POSE_STATE_STORE_ID, "data"),
        keyframes=Output(POSE_KEYFRAMES_STORE_ID, "data"),
        selected=Output(POSE_SELECTED_KF_STORE_ID, "data"),
        message=Output(POSE_MESSAGE_ID, "children"),
        duration=Output(POSE_DURATION_ID, "value"),
        ease=Output(POSE_KF_EASE_ID, "value"),
        mode=Output(POSE_VIEW_MODE_ID, "value", allow_duplicate=True),
        body_sliders=[Output(widget_id, "value") for widget_id in IK_WIDGETS_IDS],
        foot_fields=[Output(field_id, "value") for field_id in POSE_FOOT_FIELD_IDS],
        foot_fields_off=[Output(field_id, "disabled") for field_id in POSE_FOOT_FIELD_IDS],
        joint_fields=[Output(field_id, "value") for field_id in POSE_JOINT_FIELD_IDS],
    ),
    inputs=dict(
        foot_target=Input(POSE_FOOT_TARGET_ID, "data"),
        _reset=Input(POSE_RESET_BTN_ID, "n_clicks"),
        _clear_feet=Input(POSE_CLEAR_FEET_BTN_ID, "n_clicks"),
        _add=Input(POSE_ADD_BTN_ID, "n_clicks"),
        _update=Input(POSE_UPDATE_BTN_ID, "n_clicks"),
        _delete=Input(POSE_DELETE_BTN_ID, "n_clicks"),
        _earlier=Input(POSE_EARLIER_BTN_ID, "n_clicks"),
        _later=Input(POSE_LATER_BTN_ID, "n_clicks"),
        _item_clicks=Input({"type": POSE_KF_ITEM_TYPE, "index": ALL}, "n_clicks"),
        _gait_clicks=Input({"type": POSE_GAIT_ITEM_TYPE, "index": ALL}, "n_clicks"),
        upload=Input(POSE_UPLOAD_ID, "contents"),
        _config_store=Input(ROBOT_CONFIG_STORE_ID, "data"),
        body_values=[Input(widget_id, "value") for widget_id in IK_WIDGETS_IDS],
        foot_leg=Input(POSE_FOOT_LEG_ID, "value"),
        foot_values=[Input(field_id, "value") for field_id in POSE_FOOT_FIELD_IDS],
        joint_values=[Input(field_id, "value") for field_id in POSE_JOINT_FIELD_IDS],
        duration=Input(POSE_DURATION_ID, "value"),
        ease_values=Input(POSE_KF_EASE_ID, "value"),
        # Resizing the robot moves every foot field and joint.
        dimensions_json=DIMENSIONS_INPUT,
    ),
    state=dict(
        pose_store=State(POSE_STATE_STORE_ID, "data"),
        keyframes_store=State(POSE_KEYFRAMES_STORE_ID, "data"),
        selected=State(POSE_SELECTED_KF_STORE_ID, "data"),
    ),
    prevent_initial_call="initial_duplicate",
)
def edit(
    foot_target,
    _reset,
    _clear_feet,
    _add,
    _update,
    _delete,
    _earlier,
    _later,
    _item_clicks,
    _gait_clicks,
    upload,
    _config_store,
    body_values,
    foot_leg,
    foot_values,
    joint_values,
    duration,
    ease_values,
    dimensions_json,
    pose_store,
    keyframes_store,
    selected,
):
    """Every change to the pose, the keyframes or which keyframe is selected.

    One callback rather than one per control, because they all write the same
    stores and each needs to see what the others last left there. It also
    writes the sliders and the foot and joint fields, which it reads: whenever
    the pose comes from somewhere other than a slider -- a keyframe, a reset,
    the page being opened -- the sliders are set to show it, and the fields
    always show where the picked foot is and what every joint is at. Written anywhere else, they would set the
    pose off again.
    """
    robot_config = _robot(dimensions_json)
    trigger = ctx.triggered_id
    # A keyframe in the list reports in with a dict id, which cannot be looked
    # up among the sliders'.
    slider = trigger if isinstance(trigger, str) else None

    out_pose = out_keyframes = out_selected = no_update
    message = no_update
    out_duration = no_update
    out_mode = no_update

    if trigger in (None, ROBOT_CONFIG_STORE_ID):
        # Page load, or a robot connecting. A pose already in the session for
        # this robot is passed on anyway: Dash skips a callback whose input
        # came back as no_update during the initial round, so without this
        # the view would stay empty until the pose was next changed.
        if _valid_pose(pose_store, robot_config):
            out_pose = pose_store
    if not _valid_pose(pose_store, robot_config):
        # A different robot (or none yet): start over on this one.
        pose_store = out_pose = _pose_store(robot_config, pl.standby_state())
    if not _valid(keyframes_store, robot_config):
        keyframes_store = out_keyframes = _fresh_keyframes(robot_config)
        selected = out_selected = None

    frames = list(keyframes_store["keyframes"])
    if selected is not None and not 0 <= selected < len(frames):
        selected = out_selected = None
    if trigger in (None, shared.DIMENSIONS_HIDDEN_SECTION_ID) and selected is not None:
        # Back on the page with a keyframe selected: show its time, not the
        # input's default. (The Robot panel's dimensions arriving can be what runs
        # this first on a page load.)
        out_duration = frames[selected]["duration_ms"]

    state = pose_store["state"]

    def bump(new_state):
        # The sequence number makes the pose differ from the one before even
        # when the feet do not, so a refused drag is still redrawn and the
        # foot springs back to where it was.
        return _pose_store(robot_config, new_state, pose_store.get("seq", 0) + 1)

    def set_frames(new_frames):
        return {"robot": robot_config["name"], "keyframes": new_frames}

    if trigger == POSE_FOOT_TARGET_ID and foot_target:
        leg = foot_target.get("leg")
        target = foot_target.get("foot")
        if not isinstance(leg, int) or not 0 <= leg < 6 or not target or len(target) != 3:
            raise PreventUpdate
        moved = pl.with_foot_at(state, leg, target, robot_config)
        _, _, bad_legs = pl.solve(moved, robot_config)
        if leg in bad_legs:
            message = helpers.make_alert_message(
                f"{leg_label(leg)} cannot reach there, or a joint would pass its limit."
            )
            # While dragging the foot is left where the cursor has it; once
            # dropped it goes back to the last place it could reach.
            out_pose = bump(state) if foot_target.get("final") else no_update
        else:
            out_pose = bump(moved)
            message = ""

    elif slider in POSE_FOOT_FIELD_IDS:
        if not foot_leg:
            raise PreventUpdate
        leg = leg_index(foot_leg)
        # A field left empty, or still showing the rounded value it was given,
        # keeps that coordinate exactly, so typing one does not nudge the
        # others by their rounding.
        here = pl.view_feet(state, robot_config)[leg]
        target = [
            here[i] if value is None or float(value) == _field_value(here[i]) else float(value)
            for i, value in enumerate(foot_values)
        ]
        moved = pl.with_foot_at(state, leg, target, robot_config)
        _, _, bad_legs = pl.solve(moved, robot_config)
        if leg in bad_legs:
            message = helpers.make_alert_message(
                f"{leg_label(leg)} cannot reach there, or a joint would pass its limit."
            )
            # The fields go back to where the foot still is.
        else:
            out_pose = bump(moved)
            message = ""
        out_mode = MODE_EDIT

    elif slider in JOINT_FIELD_KEYS:
        leg, joint = JOINT_FIELD_KEYS[slider]
        value = joint_values[POSE_JOINT_FIELD_IDS.index(slider)]
        if value is None:
            raise PreventUpdate
        moved = pl.with_leg_angles(state, leg, {joint: float(value)}, robot_config)
        _, _, bad_legs = pl.solve(moved, robot_config)
        if leg in bad_legs:
            message = helpers.make_alert_message(
                f"{leg_label(leg)}: {joint} {float(value):+.1f}° is past the joint's limit."
            )
            # The fields go back to the angles the leg still has.
        else:
            out_pose = bump(moved)
            message = ""
        out_mode = MODE_EDIT

    elif slider in BODY_WIDGET_KEYS:
        body = dict(zip(pl.BODY_KEYS, body_values))
        out_pose = bump(pl.make_state(body, state["offsets"]))
        out_mode = MODE_EDIT
        message = ""

    elif trigger == POSE_RESET_BTN_ID:
        out_pose = bump(pl.standby_state())
        out_mode = MODE_EDIT
        message = ""

    elif trigger == POSE_CLEAR_FEET_BTN_ID:
        out_pose = bump(pl.make_state(state["body"], np.zeros((6, 3))))
        out_mode = MODE_EDIT
        message = ""

    elif trigger == POSE_ADD_BTN_ID:
        index = len(frames) if selected is None else selected + 1
        feet = pl.body_feet(state, robot_config)
        eased = bool(ease_values) and "ease" in ease_values
        frames.insert(index, kf.make_keyframe(feet, duration, state, ease=eased))
        out_keyframes = set_frames(frames)
        out_selected = index
        out_duration = frames[index]["duration_ms"]
        message = ""

    elif isinstance(trigger, dict) and trigger.get("type") == POSE_GAIT_ITEM_TYPE:
        # The menu's items are there from the start, with no clicks; only a
        # real click puts a gait in, as its keyframes -- where a pose would
        # go, after the one selected, and selecting its last so another
        # follows on.
        if not ctx.triggered or not ctx.triggered[0]["value"]:
            raise PreventUpdate
        inserted = gait_keyframes(trigger["index"], robot_config)
        index = len(frames) if selected is None else selected + 1
        frames[index:index] = inserted
        out_keyframes = set_frames(frames)
        out_selected = index + len(inserted) - 1
        out_duration = frames[out_selected]["duration_ms"]
        message = ""

    elif trigger == POSE_UPDATE_BTN_ID:
        if selected is None:
            message = helpers.make_alert_message("Pick a keyframe to update.")
        else:
            # It keeps its time and easing.
            feet = pl.body_feet(state, robot_config)
            frames[selected] = kf.remade(frames[selected], feet, state)
            out_keyframes = set_frames(frames)
            message = ""

    elif trigger == POSE_DELETE_BTN_ID:
        if selected is None:
            message = helpers.make_alert_message("Pick a keyframe to delete.")
        else:
            del frames[selected]
            out_keyframes = set_frames(frames)
            out_selected = min(selected, len(frames) - 1) if frames else None
            message = ""

    elif trigger == POSE_DURATION_ID:
        # Retimes the selected keyframe, and nothing else about it. With none
        # selected, the time waits for the next + Add. The field shows the
        # time as it is kept: in range, and a field left empty goes back to
        # what it was.
        if duration is None:
            out_duration = (
                kf.DEFAULT_DURATION_MS if selected is None else frames[selected]["duration_ms"]
            )
        else:
            duration_ms = kf.clamp_duration(duration)
            if duration_ms != duration:
                out_duration = duration_ms
            if selected is not None and frames[selected]["duration_ms"] != duration_ms:
                frames[selected] = {**frames[selected], "duration_ms": duration_ms}
                out_keyframes = set_frames(frames)

    elif trigger == POSE_KF_EASE_ID:
        # Whether the move into the selected keyframe eases. With none
        # selected, it waits for the next + Add.
        if selected is None:
            raise PreventUpdate
        eased = bool(ease_values) and "ease" in ease_values
        if kf.eases(frames[selected]) != eased:
            frame = frames[selected]
            frames[selected] = kf.make_keyframe(
                frame["feet"], frame["duration_ms"], frame.get("state"), ease=eased
            )
            out_keyframes = set_frames(frames)

    elif trigger in (POSE_EARLIER_BTN_ID, POSE_LATER_BTN_ID):
        step = -1 if trigger == POSE_EARLIER_BTN_ID else 1
        if selected is None or not 0 <= selected + step < len(frames):
            raise PreventUpdate
        frames[selected], frames[selected + step] = frames[selected + step], frames[selected]
        out_keyframes = set_frames(frames)
        out_selected = selected + step

    elif isinstance(trigger, dict) and trigger.get("type") == POSE_KF_ITEM_TYPE:
        # The list is rebuilt whenever the keyframes change, and new entries
        # report in with no clicks; only a real click selects one.
        if not ctx.triggered or not ctx.triggered[0]["value"]:
            raise PreventUpdate
        index = trigger["index"]
        if not 0 <= index < len(frames):
            raise PreventUpdate
        out_selected = index
        out_pose = bump(_keyframe_state(frames[index], robot_config))
        out_duration = frames[index]["duration_ms"]
        out_mode = MODE_EDIT
        message = ""

    elif trigger == POSE_UPLOAD_ID and upload:
        try:
            loaded = kf.load(_decode_upload(upload), robot_config)
        except (kf.KeyframeFileError, ValueError) as error:
            message = helpers.make_alert_message(error)
        else:
            out_keyframes = set_frames(loaded)
            out_selected = 0 if loaded else None
            if loaded:
                out_pose = bump(_keyframe_state(loaded[0], robot_config))
                out_duration = loaded[0]["duration_ms"]
            out_mode = MODE_EDIT
            message = ""

    # The sliders always show the pose -- except while one is being moved,
    # when writing its own value back would fight the drag.
    shown_pose = pose_store if out_pose is no_update else out_pose
    if slider in BODY_WIDGET_KEYS:
        body_sliders = [no_update] * len(IK_WIDGETS_IDS)
    else:
        body_sliders = [shown_pose["state"]["body"][key] for key in pl.BODY_KEYS]

    if foot_leg:
        foot = pl.view_feet(shown_pose["state"], robot_config)[leg_index(foot_leg)]
        foot_fields = [_field_value(value) for value in foot]
        foot_fields_off = [False] * 3
    else:
        foot_fields = [None] * 3
        foot_fields_off = [True] * 3

    # What every joint is at; nothing for a leg that cannot reach its foot,
    # whose angles mean nothing.
    _, shown_angles, shown_bad = pl.solve(shown_pose["state"], robot_config)
    joint_fields = [
        None if leg in shown_bad else _field_value(shown_angles[leg][joint])
        for leg, joint, _ in POSE_JOINT_FIELDS
    ]

    # The easing box shows the selected keyframe's, as the time field shows
    # its time -- except while it is being clicked.
    shown_frames = frames if out_keyframes is no_update else out_keyframes["keyframes"]
    shown_selected = selected if out_selected is no_update else out_selected
    out_ease = no_update
    if trigger != POSE_KF_EASE_ID and shown_selected is not None:
        if 0 <= shown_selected < len(shown_frames):
            out_ease = ["ease"] if kf.eases(shown_frames[shown_selected]) else []
    if out_selected is None:
        # Nothing selected any more: the bar is the next keyframe's again,
        # starting from the usual time and easing rather than the last
        # keyframe's.
        out_duration = kf.DEFAULT_DURATION_MS
        out_ease = ["ease"]

    return dict(
        pose=out_pose,
        keyframes=out_keyframes,
        selected=out_selected,
        message=message,
        duration=out_duration,
        ease=out_ease,
        mode=out_mode,
        body_sliders=body_sliders,
        foot_fields=foot_fields,
        foot_fields_off=foot_fields_off,
        joint_fields=joint_fields,
    )


# ......................
# The pose: its angles, the robot, and the scene
# ......................

# The robot is only sent a pose that has changed, not the same one again each
# time the page is opened: sending cancels a sequence the robot is running
# (RobotLink.send_pose).
_last_sent = {"key": None}


@callback(
    Output(POSE_SCENE_STORE_ID, "data"),
    Output(POSE_ANGLES_ID, "children"),
    Output(ANGLES_HUD_ID, "className"),
    Input(POSE_STATE_STORE_ID, "data"),
    DIMENSIONS_INPUT,
)
def update_pose(pose_store, dimensions_json):
    robot_config = _robot(dimensions_json)
    if not _valid_pose(pose_store, robot_config):
        raise PreventUpdate

    state = pose_store["state"]
    _, pose, bad_legs = pl.solve(state, robot_config)

    key = (pose_store["robot"], pose_store.get("seq", 0), dimensions_json)
    if key != _last_sent["key"] and not bad_legs:
        _last_sent["key"] = key
        ROBOT_LINK.send_pose(pose)

    scene = pl.scene(state, pose, robot_config)
    scene["seq"] = pose_store.get("seq", 0)
    # Marked when a leg is out of reach, so the readout says so even folded
    # away, when the warning inside it cannot be seen.
    hud_class = f"{ANGLES_HUD_CLASS} is-bad" if bad_legs else ANGLES_HUD_CLASS
    return scene, helpers.make_angle_strip(pose, bad_legs), hud_class


# The foot picker and the view follow each other: clicking a foot picks it in
# the picker, and picking one there picks it up in the view, ready to drag.
clientside_callback(
    """
    function(leg) {
        var names = %s;
        return leg === null || leg === undefined ? "" : names[leg];
    }
    """
    % json.dumps(list(NAMES_LEG)),
    Output(POSE_FOOT_LEG_ID, "value"),
    Input(POSE_SELECTED_LEG_ID, "data"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(name) {
        var names = %s;
        var leg = names.indexOf(name);
        if (window.hexapodView) {
            window.hexapodView.selectFoot("%s", leg < 0 ? null : leg);
        }
        return window.dash_clientside.no_update;
    }
    """
    % (json.dumps(list(NAMES_LEG)), POSE_VIEW_ID),
    Output(POSE_RENDER_ACK_ID, "data", allow_duplicate=True),
    Input(POSE_FOOT_LEG_ID, "value"),
    prevent_initial_call=True,
)


# Hands the scene to the view: the pose, which can be dragged with the Feet
# tool, or a frame of the sequence while previewing, which cannot.
clientside_callback(
    """
    function(scene, frame, mode, preview, tool) {
        if (!window.hexapodView) {
            return window.dash_clientside.no_update;
        }
        var previewing = mode === "%s" && preview && preview.scenes.length;
        if (previewing) {
            var index = Math.min(Math.max(frame || 0, 0), preview.scenes.length - 1);
            window.hexapodView.render("%s", preview.scenes[index], {editable: false});
        } else if (scene) {
            window.hexapodView.render("%s", scene, {editable: tool === "%s"});
        }
        return window.dash_clientside.no_update;
    }
    """
    % (MODE_PREVIEW, POSE_VIEW_ID, POSE_VIEW_ID, TOOL_FEET),
    Output(POSE_RENDER_ACK_ID, "data"),
    Input(POSE_SCENE_STORE_ID, "data"),
    Input(POSE_FRAME_SLIDER_ID, "value"),
    Input(POSE_VIEW_MODE_ID, "value"),
    Input(POSE_PREVIEW_STORE_ID, "data"),
    Input(POSE_TOOL_ID, "value"),
)

clientside_callback(
    """
    function(n_clicks) {
        if (window.hexapodView) {
            window.hexapodView.resetCamera("%s");
        }
        return window.dash_clientside.no_update;
    }
    """
    % POSE_VIEW_ID,
    Output(POSE_RENDER_ACK_ID, "data", allow_duplicate=True),
    Input(POSE_RESET_VIEW_BTN_ID, "n_clicks"),
    prevent_initial_call=True,
)


# ......................
# The keyframe list
# ......................


def _kf_link(label, arrow, title):
    """The arrow from one keyframe to the next, with how long the move takes."""
    return html.Span(
        [
            html.Span(label, className="ind-kf-link-label"),
            html.Span(arrow, className="ind-kf-arrow"),
        ],
        className="ind-kf-link",
        title=title,
    )


@callback(
    Output(POSE_KF_LIST_ID, "children"),
    Output(POSE_KF_SUMMARY_ID, "children"),
    Output(POSE_KF_EDITOR_LABEL_ID, "children"),
    Output(POSE_ADD_BTN_ID, "children"),
    Output(POSE_UPDATE_BTN_ID, "children"),
    Output(POSE_UPDATE_BTN_ID, "disabled"),
    Output(POSE_DELETE_BTN_ID, "disabled"),
    Output(POSE_EARLIER_BTN_ID, "disabled"),
    Output(POSE_LATER_BTN_ID, "disabled"),
    Input(POSE_KEYFRAMES_STORE_ID, "data"),
    Input(POSE_SELECTED_KF_STORE_ID, "data"),
    Input(POSE_LOOP_ID, "value"),
)
def list_keyframes(keyframes_store, selected, loop_values):
    """The keyframe track, and the editor's buttons for the keyframe selected:
    each one is only enabled when there is something for it to do."""
    frames = keyframes_store["keyframes"] if isinstance(keyframes_store, dict) else []
    if selected is not None and not 0 <= selected < len(frames):
        selected = None
    loop = bool(loop_values) and "loop" in loop_values

    if frames:
        # Each keyframe with when it is reached; on the arrow into it, how
        # long it takes to get there from the one before.
        items = []
        at_ms = 0
        for index, frame in enumerate(frames):
            if index:
                at_ms += frame["duration_ms"]
                items.append(
                    _kf_link(
                        f"{frame['duration_ms']} ms",
                        "▸",
                        f"#{index} to #{index + 1} in {frame['duration_ms']} ms",
                    )
                )
            items.append(
                html.Button(
                    [
                        html.Span(f"#{index + 1}", className="ind-kf-index"),
                        html.Span(f"{at_ms / 1000:.2f} s", className="ind-kf-time"),
                    ],
                    id={"type": POSE_KF_ITEM_TYPE, "index": index},
                    className="ind-kf-card active" if index == selected else "ind-kf-card",
                    title="Load this keyframe into the pose",
                )
            )
        if loop and len(frames) > 1:
            # Looping, the move back to the start takes the first keyframe's
            # time (hexapod/keyframes.py).
            first_ms = frames[0]["duration_ms"]
            items.append(
                _kf_link(f"{first_ms} ms", "↺", f"Back to #1 in {first_ms} ms, then again")
            )
        total = kf.sequence_duration_ms(frames, loop) / 1000.0
        summary = f"{len(frames)} keyframe{'s' if len(frames) != 1 else ''} · {total:.2f} s"
    else:
        items = html.Div(
            "No keyframes yet: pose the robot with Body or Feet, then + Add pose.",
            className="dock-empty",
        )
        summary = ""

    if selected is None:
        return items, summary, "New keyframe", "+ Add pose", "Save pose", True, True, True, True

    number = selected + 1
    last = selected == len(frames) - 1
    return (
        items,
        summary,
        f"Keyframe #{number}",
        "+ Add pose" if last else f"+ Insert after #{number}",
        f"Save pose to #{number}",
        False,
        False,
        selected == 0,
        last,
    )


@callback(
    Output(POSE_DOWNLOAD_ID, "data"),
    Input(POSE_SAVE_BTN_ID, "n_clicks"),
    State(POSE_KEYFRAMES_STORE_ID, "data"),
    prevent_initial_call=True,
)
def save_keyframes(_n_clicks, keyframes_store):
    robot_config = _robot()
    if not _valid(keyframes_store, robot_config) or not keyframes_store["keyframes"]:
        raise PreventUpdate
    return {
        "content": kf.dump(keyframes_store["keyframes"], robot_config),
        "filename": f"{robot_config['name']}-keyframes.json",
        "type": "application/json",
    }


# ......................
# Preview
# ......................


def _speed_pct(value):
    """The playback speed a typed value stands for: a whole percent, within
    range; 100 for one that is not a number."""
    try:
        return int(min(max(round(float(value)), SPEED_MIN_PCT), SPEED_MAX_PCT))
    except (TypeError, ValueError):
        return 100


def _options(loop_values, speed_pct):
    """(loop, speed) from the dock's controls; speed as a factor."""
    loop = bool(loop_values) and "loop" in loop_values
    return loop, _speed_pct(speed_pct) / 100.0


@callback(
    Output(POSE_SPEED_ID, "value"),
    Input(POSE_SPEED_ID, "value"),
    prevent_initial_call=True,
)
def set_speed(speed_pct):
    """Show the playback speed as it is played: in range, a whole percent,
    and 100 for a box left empty."""
    applied = _speed_pct(speed_pct)
    return no_update if applied == speed_pct else applied


def _bad_frames_message(bad_frames, total):
    return helpers.make_alert_message(
        f"{len(bad_frames)} of {total} frames pass out of reach between "
        "keyframes. Add a keyframe in between to route the feet around."
    )


@callback(
    Output(POSE_PREVIEW_STORE_ID, "data"),
    Output(POSE_FRAME_SLIDER_ID, "max"),
    Output(POSE_FRAME_SLIDER_ID, "value"),
    Output(POSE_PREVIEW_MESSAGE_ID, "children"),
    Input(POSE_KEYFRAMES_STORE_ID, "data"),
    Input(POSE_LOOP_ID, "value"),
    Input(POSE_SPEED_ID, "value"),
    DIMENSIONS_INPUT,
)
def build_preview(keyframes_store, loop_values, speed_pct, dimensions_json):
    """The frames the view plays in Sequence."""
    robot_config = _robot(dimensions_json)
    loop, speed = _options(loop_values, speed_pct)
    frames = keyframes_store["keyframes"] if _valid(keyframes_store, robot_config) else []
    feet, states, poses, bad_frames = pl.sequence(
        frames, robot_config, PREVIEW_FPS, loop, speed=speed
    )
    if states is None:
        # Keyframes that did not keep their layers: drawn with the body
        # unmoved.
        states = [pl.from_feet(frame_feet, robot_config) for frame_feet in feet]
    scenes = [pl.scene(state, pose, robot_config) for state, pose in zip(states, poses)]
    message = _bad_frames_message(bad_frames, len(poses)) if bad_frames else ""
    preview = {"scenes": scenes, "fps": PREVIEW_FPS}
    return preview, max(len(scenes) - 1, 1), 0, message


# Play/Pause. Playing always shows the sequence, so it switches to it.
clientside_callback(
    """
    function(n_clicks, is_playing, frame, max_frame) {
        var playing = !is_playing;
        var next = frame;
        if (playing && frame >= max_frame) {
            next = 0;
        }
        return [
            playing,
            playing ? "⏸ Pause" : "▶ Play",
            playing ? "danger" : "primary",
            !playing,
            next,
            playing ? "%s" : window.dash_clientside.no_update,
        ];
    }
    """
    % MODE_PREVIEW,
    Output(POSE_PLAY_STATE_STORE_ID, "data"),
    Output(POSE_PLAY_BTN_ID, "children"),
    Output(POSE_PLAY_BTN_ID, "color"),
    Output(POSE_INTERVAL_ID, "disabled"),
    Output(POSE_FRAME_SLIDER_ID, "value", allow_duplicate=True),
    Output(POSE_VIEW_MODE_ID, "value", allow_duplicate=True),
    Input(POSE_PLAY_BTN_ID, "n_clicks"),
    State(POSE_PLAY_STATE_STORE_ID, "data"),
    State(POSE_FRAME_SLIDER_ID, "value"),
    State(POSE_FRAME_SLIDER_ID, "max"),
    prevent_initial_call=True,
)

# One preview frame per tick, stopping at the end unless looping.
clientside_callback(
    """
    function(n_intervals, frame, max_frame, loop_values) {
        var loop = loop_values && loop_values.includes("loop");
        var next = frame + 1;
        if (next > max_frame) {
            if (loop) {
                next = 0;
            } else {
                return [max_frame, false, "▶ Play", "primary", true];
            }
        }
        var skip = window.dash_clientside.no_update;
        return [next, skip, skip, skip, skip];
    }
    """,
    Output(POSE_FRAME_SLIDER_ID, "value", allow_duplicate=True),
    Output(POSE_PLAY_STATE_STORE_ID, "data", allow_duplicate=True),
    Output(POSE_PLAY_BTN_ID, "children", allow_duplicate=True),
    Output(POSE_PLAY_BTN_ID, "color", allow_duplicate=True),
    Output(POSE_INTERVAL_ID, "disabled", allow_duplicate=True),
    Input(POSE_INTERVAL_ID, "n_intervals"),
    State(POSE_FRAME_SLIDER_ID, "value"),
    State(POSE_FRAME_SLIDER_ID, "max"),
    State(POSE_LOOP_ID, "value"),
    prevent_initial_call=True,
)

# Back to the pose stops playback; the scrubber only means something while
# the sequence is shown.
clientside_callback(
    """
    function(mode) {
        if (mode === "%s") {
            return [false, "▶ Play", "primary", true, true];
        }
        var skip = window.dash_clientside.no_update;
        return [skip, skip, skip, skip, false];
    }
    """
    % MODE_EDIT,
    Output(POSE_PLAY_STATE_STORE_ID, "data", allow_duplicate=True),
    Output(POSE_PLAY_BTN_ID, "children", allow_duplicate=True),
    Output(POSE_PLAY_BTN_ID, "color", allow_duplicate=True),
    Output(POSE_INTERVAL_ID, "disabled", allow_duplicate=True),
    Output(POSE_FRAME_SLIDER_ID, "disabled"),
    Input(POSE_VIEW_MODE_ID, "value"),
    prevent_initial_call="initial_duplicate",
)

clientside_callback(
    """
    function(frame, preview) {
        var frames = preview && preview.scenes ? preview.scenes.length : 0;
        var fps = (preview && preview.fps) || %d;
        var last = Math.max(frames - 1, 0);
        var at = Math.min(frame || 0, last);
        return at + "/" + last + " · " + (at / fps).toFixed(2) + " s";
    }
    """
    % PREVIEW_FPS,
    Output(POSE_FRAME_DISPLAY_ID, "children"),
    Input(POSE_FRAME_SLIDER_ID, "value"),
    Input(POSE_PREVIEW_STORE_ID, "data"),
)


# ......................
# Run on robot
# ......................


@callback(
    Output(POSE_ROBOT_MESSAGE_ID, "children"),
    Input(POSE_RUN_BTN_ID, "n_clicks"),
    State(POSE_KEYFRAMES_STORE_ID, "data"),
    State(POSE_LOOP_ID, "value"),
    State(POSE_SPEED_ID, "value"),
    DIMENSIONS_STATE,
    prevent_initial_call=True,
)
def run_on_robot(_n_clicks, keyframes_store, loop_values, speed_pct, dimensions_json):
    if not ROBOT_LINK.connected:
        return "Not connected — connect to a robot first."

    robot_config = _robot(dimensions_json)
    loop, speed = _options(loop_values, speed_pct)
    frames = keyframes_store["keyframes"] if _valid(keyframes_store, robot_config) else []
    if not frames:
        return "Add a pose or a gait first."

    # The robot gets frames at the rate it plays its own gaits at full speed,
    # so the sequence is as smooth as they are, and in real time: the durations
    # are what was asked for, scaled by the playback speed.
    fps = get_sequence_fps(robot_config, 100)
    _, _, poses, bad_frames = pl.sequence(frames, robot_config, fps, loop, speed=speed)
    if bad_frames:
        return "Not sent: part of the sequence is out of reach (see the preview)."

    if not ROBOT_LINK.play_sequence(poses, loop=loop, fps=fps):
        return "Nothing to send."
    seconds = kf.sequence_duration_ms(frames, loop, speed) / 1000.0
    return (
        f"Streaming {len(frames)} keyframes — {seconds:.2f} s"
        f"{f' at {round(speed * 100)} %' if speed != 1 else ''}"
        f"{', looping' if loop else ''}."
    )


@callback(
    Output(DRIVE_SPEED_ID, "value"),
    Input(DRIVE_SPEED_ID, "value"),
    prevent_initial_call=True,
)
def set_drive_speed(speed_pct):
    """The controller's speed, how fast the robot plays its own gaits: sent to
    it now, and carried by every motion command. Set without a robot too, so
    the next one connected starts at it."""
    if speed_pct is None:
        raise PreventUpdate
    applied = ROBOT_LINK.set_motion_speed(speed_pct)
    return no_update if applied == speed_pct else applied


@callback(
    Output(POSE_ROBOT_MESSAGE_ID, "children", allow_duplicate=True),
    Input(POSE_STOP_BTN_ID, "n_clicks"),
    prevent_initial_call=True,
)
def stop_on_robot(_n_clicks):
    if not ROBOT_LINK.connected:
        return "Not connected."
    ROBOT_LINK.stop_sequence()
    ROBOT_LINK.send_motion_command("standby")
    return "Robot returning to standby."


OFFLINE_MESSAGE = "Connect a robot to run this on the hardware."


# The speed sliders that are the link's speed: the controller's.
SPEED_SLIDER_IDS = (DRIVE_SPEED_ID,)


@callback(
    output=dict(
        controls_class=Output(POSE_ROBOT_CONTROLS_ID, "className"),
        drive_class=Output(DRIVE_CONTROLS_ID, "className"),
        run_off=Output(POSE_RUN_BTN_ID, "disabled"),
        stop_off=Output(POSE_STOP_BTN_ID, "disabled"),
        message=Output(POSE_ROBOT_MESSAGE_ID, "children", allow_duplicate=True),
        speed_mins=[Output(slider_id, "min") for slider_id in SPEED_SLIDER_IDS],
        speed_maxes=[Output(slider_id, "max") for slider_id in SPEED_SLIDER_IDS],
        speed_values=[
            Output(slider_id, "value", allow_duplicate=True) for slider_id in SPEED_SLIDER_IDS
        ],
    ),
    inputs=dict(_n_intervals=Input(ROBOT_POLL_INTERVAL_ID, "n_intervals")),
    state=dict(
        message=State(POSE_ROBOT_MESSAGE_ID, "children"),
        speed_values=[State(slider_id, "value") for slider_id in SPEED_SLIDER_IDS],
        speed_mins=[State(slider_id, "min") for slider_id in SPEED_SLIDER_IDS],
        speed_maxes=[State(slider_id, "max") for slider_id in SPEED_SLIDER_IDS],
    ),
    prevent_initial_call="initial_duplicate",
)
def sync_robot_controls(_n_intervals, message, speed_values, speed_mins, speed_maxes):
    """Grey the robot controls -- the dock's and the controller's -- out while
    there is no robot, and keep the controller's speed on the link's.

    The slider's range is the connected robot's, and its value the link's
    -- the page may have been rendered before either was known. They are
    only written when they differ, so the speed callback is not retriggered
    every second.
    """
    speed = ROBOT_LINK.robot_config["speed"]
    link_speed = ROBOT_LINK.speed_pct
    mins_out = [no_update if value == speed["min"] else speed["min"] for value in speed_mins]
    maxes_out = [no_update if value == speed["max"] else speed["max"] for value in speed_maxes]
    values_out = [no_update if value == link_speed else link_speed for value in speed_values]

    offline = not ROBOT_LINK.connected
    if offline:
        new_message = no_update if message == OFFLINE_MESSAGE else OFFLINE_MESSAGE
    else:
        new_message = "" if message == OFFLINE_MESSAGE else no_update
    controls_class = SECTION_CONTROLS_OFFLINE_CLASS if offline else SECTION_CONTROLS_CLASS
    return dict(
        controls_class=f"d-flex gap-2 {controls_class}",
        drive_class=f"{DRIVE_BODY_CLASS} {controls_class}",
        run_off=offline,
        stop_off=offline,
        message=new_message,
        speed_mins=mins_out,
        speed_maxes=maxes_out,
        speed_values=values_out,
    )
