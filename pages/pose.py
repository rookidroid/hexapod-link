# What the workspace does (its layout is pages/workspace.py): set a pose,
# collect poses as keyframes -- and the robot's gaits, as theirs
# (hexapod/gait_keyframes.py) -- preview the sequence and run it on the robot.
#
# There is one pose: the robot's standby posture with two layers on top
# (hexapod/pose_layers.py):
#
#   feet  single feet moved away from where standby plants them, by dragging
#         them in the 3D view or typing where they go, or their leg's angles
#   body  the body moved and tilted over wherever the feet are planted, with
#         its sliders or by dragging it in the 3D view
#
# The layers add up, so neither undoes the other: tilt the body, move a foot,
# and both stay. Which one is being adjusted is whatever is picked -- the
# body, or a foot -- by clicking it in the view or its button in the overlay
# on the view, which then shows its controls; picking changes nothing else.
# Out of the layers come the joint angles, what is streamed to the robot and
# what a keyframe keeps.
#
# The 3D view (assets/hexapod_view.js) reports what is picked through the
# POSE_SELECTION_ID store, and a dragged foot or body through the
# POSE_FOOT_TARGET_ID and POSE_BODY_TARGET_ID stores; it draws whatever lands
# in the view's scene store, or a frame of the sequence while previewing. The
# kinematics all happen here.
#
# What is being edited lives in session stores, so it survives a reload:
#
#   pose       {"robot", "state": the layers, "feet": 6x3 in the body frame,
#               "seq", "at"}; "at" says, for a pose taken from where playback
#               came to rest between two keyframes, where that is:
#               {"after": keyframe index, "ms": into the move from it}
#   keyframes  {"robot", "keyframes": [...]}   see hexapod/keyframes.py
#   selected   index of the keyframe the pose was loaded from, or None
#
# Foot positions only fit the robot they were placed on, so the stores carry
# that robot's name, and a different robot connecting starts the editor
# afresh.
#
# The robot modelled is the connected one (or the last one, or Nougat, the
# default), measured as the Dimensions panel has it: they start on the
# robot's own and can be edited to try another body. Feet and keyframes are
# moves from standby and keep their meaning on the resized body; what is
# streamed to the robot is solved on it too.

import base64
import json
import numpy as np
from dash import ALL, callback, clientside_callback, ctx, html, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from hexapod import gait_library
from hexapod import keyframes as kf
from hexapod.gait_keyframes import gait_keyframes
from hexapod import pose_layers as pl
from hexapod.naming import LEG_LABELS, leg_label
from hexapod.robot_config import get_sequence_fps, with_dimensions
from hexapod.robot_link import ROBOT_LINK
from pages.shell import view_ack_id, view_store_id
from widgets.body_ui import BODY_RANGES, BODY_SLIDER_IDS
from widgets.dimensions_ui import DIMENSIONS_JSON_ID
from widgets.pose_ui import (
    MODE_EDIT,
    MODE_PREVIEW,
    POSE_HUD_CLASS,
    POSE_HUD_ID,
    GAIT_SOURCES,
    PICK_BTN_CLASS,
    POSE_ADD_BTN_ID,
    POSE_ADJUST_BODY_ID,
    POSE_ADJUST_FOOT_ID,
    POSE_ADJUST_HINT_ID,
    POSE_ANGLES_ID,
    POSE_BODY_MODE_ID,
    POSE_BODY_TARGET_ID,
    POSE_BODY_TOOL_ID,
    POSE_CLEAR_FEET_BTN_ID,
    POSE_DELETE_BTN_ID,
    POSE_DOWNLOAD_ID,
    POSE_DURATION_ID,
    POSE_EARLIER_BTN_ID,
    POSE_FOOT_FIELD_IDS,
    POSE_FOOT_TITLE_ID,
    POSE_JOINT_FIELDS,
    POSE_JOINT_FIELD_IDS,
    POSE_FOOT_TARGET_ID,
    POSE_FRAME_DISPLAY_ID,
    POSE_FRAME_SLIDER_ID,
    POSE_GAIT_ITEM_TYPE,
    POSE_GAIT_LIST_IDS,
    POSE_GAIT_REPLACE_TYPE,
    POSE_GAIT_SOURCE_ID,
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
    POSE_PLAYHEAD_ID,
    POSE_PICK_BODY_ID,
    POSE_PICK_LEG_IDS,
    POSE_PREVIEW_MESSAGE_ID,
    POSE_PREVIEW_STORE_ID,
    POSE_RESET_BTN_ID,
    POSE_RESET_VIEW_BTN_ID,
    POSE_ROBOT_CONTROLS_ID,
    POSE_ROBOT_MESSAGE_ID,
    POSE_RUN_BTN_ID,
    POSE_SAVE_BTN_ID,
    POSE_SELECTED_KF_STORE_ID,
    POSE_SELECTION_ID,
    POSE_STATE_STORE_ID,
    POSE_SPEED_ID,
    POSE_STOP_BTN_ID,
    POSE_UPDATE_BTN_ID,
    POSE_UPLOAD_ID,
    POSE_USER_GAIT_DELETE_TYPE,
    POSE_USER_GAIT_ITEM_TYPE,
    POSE_USER_GAIT_LIST_ID,
    POSE_USER_GAIT_MESSAGE_ID,
    POSE_USER_GAIT_NAME_ID,
    POSE_USER_GAIT_REPLACE_TYPE,
    POSE_USER_GAIT_SAVE_BTN_ID,
    POSE_USER_GAITS_VERSION_ID,
    POSE_VIEW_ID,
    POSE_VIEW_MODE_ID,
    PREVIEW_FPS,
    SELECT_BODY,
    SPEED_DEFAULT_PCT,
    SPEED_MAX_PCT,
    SPEED_MIN_PCT,
    USER_GAITS_EMPTY,
    user_gait_row,
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
# The view and what is picked
# ......................

POSE_SCENE_STORE_ID = view_store_id(POSE_VIEW_ID)
POSE_RENDER_ACK_ID = view_ack_id(POSE_VIEW_ID)

# The buttons that pick: the body's, then each leg's by id.
PICK_IDS = [POSE_PICK_BODY_ID, *POSE_PICK_LEG_IDS]


# Show the controls of what is picked, the body's or a foot's, and light its
# button; with the body's, the toggle over the view that says how it is
# dragged. The others are only hidden, so their sliders keep their values.
clientside_callback(
    """
    function(picked) {
        var labels = %s;
        var show = {}, hide = {display: "none"};
        var body = picked === "%s";
        var foot = typeof picked === "number";
        var lit = [body];
        for (var leg = 0; leg < labels.length; leg++) {
            lit.push(picked === leg);
        }
        return [
            body || foot ? hide : show,
            body ? show : hide,
            foot ? show : hide,
            body ? show : hide,
            foot ? labels[picked] + " foot" : window.dash_clientside.no_update,
        ].concat(lit.map(function (on) { return on ? "%s is-picked" : "%s"; }));
    }
    """
    % (json.dumps(list(LEG_LABELS)), SELECT_BODY, PICK_BTN_CLASS, PICK_BTN_CLASS),
    Output(POSE_ADJUST_HINT_ID, "style"),
    Output(POSE_ADJUST_BODY_ID, "style"),
    Output(POSE_ADJUST_FOOT_ID, "style"),
    Output(POSE_BODY_TOOL_ID, "style"),
    Output(POSE_FOOT_TITLE_ID, "children"),
    *[Output(button_id, "className") for button_id in PICK_IDS],
    Input(POSE_SELECTION_ID, "data"),
)

# A button picks in the view, as clicking the body or the foot there does;
# the view reports it back, which is what lights the button. Clicked again,
# it lets go.
clientside_callback(
    """
    function() {
        var ids = %s;
        var picked = arguments[ids.length];
        var index = ids.indexOf(window.dash_clientside.callback_context.triggered_id);
        if (index >= 0 && window.hexapodView) {
            var what = index === 0 ? "%s" : index - 1;
            window.hexapodView.select("%s", what === picked ? null : what);
        }
        return window.dash_clientside.no_update;
    }
    """
    % (json.dumps(PICK_IDS), SELECT_BODY, POSE_VIEW_ID),
    Output(POSE_RENDER_ACK_ID, "data", allow_duplicate=True),
    *[Input(button_id, "n_clicks") for button_id in PICK_IDS],
    State(POSE_SELECTION_ID, "data"),
    prevent_initial_call=True,
)

# Picking the body or a foot in the view, or dragging it, opens the pose
# overlay if it is folded away: the joint angles it moves, and its controls,
# are in there. Set on the element itself rather than through Dash, which never
# hears of one folded by hand and so would not open it again.
clientside_callback(
    """
    function() {
        var moving = window.dash_clientside.callback_context.triggered.some(
            function (trigger) { return trigger.value !== null && trigger.value !== undefined; }
        );
        var hud = document.getElementById("%s");
        if (moving && hud) {
            hud.open = true;
        }
        return window.dash_clientside.no_update;
    }
    """
    % POSE_HUD_ID,
    Output(POSE_RENDER_ACK_ID, "data", allow_duplicate=True),
    Input(POSE_SELECTION_ID, "data"),
    Input(POSE_FOOT_TARGET_ID, "data"),
    Input(POSE_BODY_TARGET_ID, "data"),
    prevent_initial_call=True,
)

# Which handles the body picked is dragged by in the view.
clientside_callback(
    """
    function(mode) {
        if (window.hexapodView) {
            window.hexapodView.setBodyMode("%s", mode);
        }
        return window.dash_clientside.no_update;
    }
    """
    % POSE_VIEW_ID,
    Output(POSE_RENDER_ACK_ID, "data", allow_duplicate=True),
    Input(POSE_BODY_MODE_ID, "value"),
    prevent_initial_call=True,
)


# ......................
# Editor state
# ......................

# Which layer each slider sets, and how far each goes either way.
BODY_WIDGET_KEYS = dict(zip(BODY_SLIDER_IDS, pl.BODY_KEYS))
BODY_KEY_RANGES = dict(zip(pl.BODY_KEYS, BODY_RANGES))
# The leg and joint each joint field sets.
JOINT_FIELD_KEYS = {field_id: (leg, joint) for leg, joint, field_id in POSE_JOINT_FIELDS}
# A dragged foot put this far (mm) short of the cursor was held at its leg's
# limit; nearer is only rounding.
FOOT_HELD_MM = 0.01


# The Dimensions panel's measurements, as JSON (pages/robot.py).
DIMENSIONS_INPUT = Input(DIMENSIONS_JSON_ID, "children")
DIMENSIONS_STATE = State(DIMENSIONS_JSON_ID, "children")


def _robot(dimensions_json=None):
    """The robot the workspace models: the connected one's config, measured as
    the Dimensions panel has it (robot_config.with_dimensions)."""
    try:
        dimensions = json.loads(dimensions_json) if dimensions_json else None
    except (TypeError, ValueError):
        dimensions = None
    return with_dimensions(ROBOT_LINK.robot_config, dimensions)


def _pose_store(robot_config, state, seq=0, at=None):
    store = {
        "robot": robot_config["name"],
        "state": state,
        "feet": pl.body_feet(state, robot_config),
        "seq": seq,
    }
    if at is not None:
        store["at"] = at
    return store


def _at_ms(frames, at):
    """When a pose "at" a point of the sequence (see the stores above) is,
    from the first keyframe, in ms."""
    return kf.keyframe_times_ms(frames)[at["after"]] + at["ms"]


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


def _alert(alert, class_name="mb-3"):
    return html.Div(f"⚠ {alert}", className=f"ind-alert {class_name}".strip())


def _pose_alert(alert):
    """An alert about the pose, for the overlay on the view."""
    return _alert(alert, class_name="")


def _reach_warning(bad_legs):
    """Says which legs (ids) cannot be posed: their foot is out of reach or a
    joint is past its limit, so their angles mean nothing. Nothing for none."""
    if not bad_legs:
        return None
    labels = ", ".join(leg_label(leg) for leg in bad_legs)
    return html.Div(f"⚠ Out of reach or past a joint limit: {labels}", className="ind-alert")


def _picked_leg(selection):
    """The id of the leg whose foot is picked, or None: the view's selection
    is a leg's id, SELECT_BODY, or nothing."""
    if isinstance(selection, int) and not isinstance(selection, bool) and 0 <= selection < 6:
        return selection
    return None


def _triple(values):
    """Three finite numbers out of what the view sent, or None."""
    try:
        numbers = [float(value) for value in values]
    except (TypeError, ValueError):
        return None
    return numbers if len(numbers) == 3 and np.isfinite(numbers).all() else None


def _dragged_body(origin, rot, robot_config):
    """The body layer for a body dragged in the view to `origin`, turned by
    `rot`: held to what its sliders can say, in steps fine enough to follow
    the pointer."""
    body = pl.body_at(origin, rot, robot_config)
    held = {}
    for index, key in enumerate(pl.BODY_KEYS):
        most = BODY_KEY_RANGES[key]
        held[key] = round(min(max(body[key], -most), most), 2 if index < 3 else 1)
    return held


BODY_HELD_ALERT = "The body is as far as its legs can reach."


def _moved_body(state, body, robot_config):
    """(state, held) for the body moved to `body`, or as far that way as its
    legs can follow (pl.with_body_near): the state, and whether it was held
    short of what was asked."""
    moved = pl.with_body_near(state, body, robot_config)
    return moved, moved != pl.make_state(body, state["offsets"])


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
        mode=Output(POSE_VIEW_MODE_ID, "data", allow_duplicate=True),
        body_sliders=[Output(widget_id, "value") for widget_id in BODY_SLIDER_IDS],
        foot_fields=[Output(field_id, "value") for field_id in POSE_FOOT_FIELD_IDS],
        joint_fields=[Output(field_id, "value") for field_id in POSE_JOINT_FIELD_IDS],
    ),
    inputs=dict(
        foot_target=Input(POSE_FOOT_TARGET_ID, "data"),
        body_target=Input(POSE_BODY_TARGET_ID, "data"),
        _reset=Input(POSE_RESET_BTN_ID, "n_clicks"),
        _clear_feet=Input(POSE_CLEAR_FEET_BTN_ID, "n_clicks"),
        _add=Input(POSE_ADD_BTN_ID, "n_clicks"),
        _update=Input(POSE_UPDATE_BTN_ID, "n_clicks"),
        _delete=Input(POSE_DELETE_BTN_ID, "n_clicks"),
        _earlier=Input(POSE_EARLIER_BTN_ID, "n_clicks"),
        _later=Input(POSE_LATER_BTN_ID, "n_clicks"),
        _item_clicks=Input({"type": POSE_KF_ITEM_TYPE, "index": ALL}, "n_clicks"),
        _gait_clicks=Input({"type": POSE_GAIT_ITEM_TYPE, "index": ALL}, "n_clicks"),
        _user_gait_clicks=Input({"type": POSE_USER_GAIT_ITEM_TYPE, "index": ALL}, "n_clicks"),
        _gait_replaces=Input({"type": POSE_GAIT_REPLACE_TYPE, "index": ALL}, "n_clicks"),
        _user_gait_replaces=Input(
            {"type": POSE_USER_GAIT_REPLACE_TYPE, "index": ALL}, "n_clicks"
        ),
        upload=Input(POSE_UPLOAD_ID, "contents"),
        _config_store=Input(ROBOT_CONFIG_STORE_ID, "data"),
        body_values=[Input(widget_id, "value") for widget_id in BODY_SLIDER_IDS],
        # Picking a foot shows where it is.
        selection=Input(POSE_SELECTION_ID, "data"),
        foot_values=[Input(field_id, "value") for field_id in POSE_FOOT_FIELD_IDS],
        joint_values=[Input(field_id, "value") for field_id in POSE_JOINT_FIELD_IDS],
        duration=Input(POSE_DURATION_ID, "value"),
        ease_values=Input(POSE_KF_EASE_ID, "value"),
        playhead=Input(POSE_PLAYHEAD_ID, "data"),
        # Resizing the robot moves every foot field and joint.
        dimensions_json=DIMENSIONS_INPUT,
    ),
    state=dict(
        pose_store=State(POSE_STATE_STORE_ID, "data"),
        keyframes_store=State(POSE_KEYFRAMES_STORE_ID, "data"),
        selected=State(POSE_SELECTED_KF_STORE_ID, "data"),
        preview=State(POSE_PREVIEW_STORE_ID, "data"),
    ),
    prevent_initial_call="initial_duplicate",
)
def edit(
    foot_target,
    body_target,
    _reset,
    _clear_feet,
    _add,
    _update,
    _delete,
    _earlier,
    _later,
    _item_clicks,
    _gait_clicks,
    _user_gait_clicks,
    _gait_replaces,
    _user_gait_replaces,
    upload,
    _config_store,
    body_values,
    selection,
    foot_values,
    joint_values,
    duration,
    ease_values,
    playhead,
    dimensions_json,
    pose_store,
    keyframes_store,
    selected,
    preview,
):
    """Every change to the pose, the keyframes or which keyframe is selected.

    One callback rather than one per control, because they all write the same
    stores and each needs to see what the others last left there. It also
    writes the sliders and the foot and joint fields, which it reads: whenever
    the pose comes from somewhere other than a slider -- a keyframe, a reset,
    the body dragged in the view, the page being opened -- the sliders are set
    to show it, and the fields always show where the picked foot is and what
    every joint is at. Written anywhere else, they would set the pose off
    again.
    """
    robot_config = _robot(dimensions_json)
    trigger = ctx.triggered_id
    # A keyframe in the list reports in with a dict id, which cannot be looked
    # up among the sliders'.
    slider = trigger if isinstance(trigger, str) else None
    foot_leg = _picked_leg(selection)

    out_pose = out_keyframes = out_selected = no_update
    message = no_update
    # Whether the slider moved asked for more than the body could do.
    slider_held = False
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
    if trigger in (None, DIMENSIONS_JSON_ID) and selected is not None:
        # Back on the page with a keyframe selected: show its time, not the
        # input's default. (The dimensions arriving can be what runs this
        # first on a page load.)
        out_duration = frames[selected]["duration_ms"]

    state = pose_store["state"]

    def bump(new_state, at=pose_store.get("at")):
        # The sequence number makes the pose differ from the one before even
        # when the feet do not, so a foot dropped past its leg's reach is
        # still redrawn, and goes to where its leg ends. A pose edited stays
        # where in the sequence it was taken from.
        return _pose_store(robot_config, new_state, pose_store.get("seq", 0) + 1, at)

    def set_frames(new_frames):
        return {"robot": robot_config["name"], "keyframes": new_frames}

    if trigger == POSE_FOOT_TARGET_ID and foot_target:
        leg = foot_target.get("leg")
        target = foot_target.get("foot")
        if not isinstance(leg, int) or not 0 <= leg < 6 or not target or len(target) != 3:
            raise PreventUpdate
        # A foot dragged past what its leg can reach is held as near as the
        # leg gets, so the leg follows the cursor along the edge of its reach
        # rather than stopping until the cursor comes back.
        moved = pl.with_foot_near(state, leg, target, robot_config)
        final = bool(foot_target.get("final"))
        if moved is None or leg in pl.solve(moved, robot_config)[2]:
            message = _pose_alert(
                f"{leg_label(leg)} cannot reach there, or a joint would pass its limit."
            )
            # While dragging the foot is left where the cursor has it; once
            # dropped it goes back to the last place it could reach.
            out_pose = bump(state) if final else no_update
        else:
            short = np.subtract(pl.view_feet(moved, robot_config)[leg], target)
            held = np.linalg.norm(short) > FOOT_HELD_MM
            message = _pose_alert(f"{leg_label(leg)} is at its limit.") if held else ""
            # Held where it already is, there is nothing new to draw, or to
            # send the robot, until it is dropped: then the foot, left under
            # the cursor while dragging, goes to where its leg ends.
            out_pose = bump(moved) if final or moved != state else no_update

    elif trigger == POSE_SELECTION_ID:
        # Something else picked: what was said of the last move is stale.
        message = ""

    elif trigger == POSE_BODY_TARGET_ID and body_target:
        # The body dragged in the view. Like its sliders, it goes where it is
        # put, within their range and as far as its legs can follow.
        origin = _triple(body_target.get("origin"))
        rot = _triple(body_target.get("rot"))
        if origin is None or rot is None:
            raise PreventUpdate
        moved, held = _moved_body(state, _dragged_body(origin, rot, robot_config), robot_config)
        message = _pose_alert(BODY_HELD_ALERT) if held else ""
        # Held where it already is, there is nothing new to draw until it is
        # dropped: then its handle, left under the cursor while dragging,
        # goes back to it.
        out_pose = bump(moved) if body_target.get("final") or moved != state else no_update
        out_mode = MODE_EDIT

    elif slider in POSE_FOOT_FIELD_IDS:
        if foot_leg is None:
            raise PreventUpdate
        leg = foot_leg
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
            message = _pose_alert(
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
            message = _pose_alert(
                f"{leg_label(leg)}: {joint} {float(value):+.1f}° is past the joint's limit."
            )
            # The fields go back to the angles the leg still has.
        else:
            out_pose = bump(moved)
            message = ""
        out_mode = MODE_EDIT

    elif slider in BODY_WIDGET_KEYS:
        # Only the slider moved is read: the others show the pose already.
        value = body_values[BODY_SLIDER_IDS.index(slider)]
        body = {**state["body"], BODY_WIDGET_KEYS[slider]: value}
        moved, slider_held = _moved_body(state, body, robot_config)
        message = _pose_alert(BODY_HELD_ALERT) if slider_held else ""
        if moved != state:
            out_pose = bump(moved)
        out_mode = MODE_EDIT

    elif trigger == POSE_RESET_BTN_ID:
        out_pose = bump(pl.standby_state())
        out_mode = MODE_EDIT
        message = ""

    elif trigger == POSE_CLEAR_FEET_BTN_ID:
        out_pose = bump(pl.make_state(state["body"], np.zeros((6, 3))))
        out_mode = MODE_EDIT
        message = ""

    elif trigger == POSE_ADD_BTN_ID:
        feet = pl.body_feet(state, robot_config)
        eased = bool(ease_values) and "ease" in ease_values
        at = pose_store.get("at")
        if selected is None and at and 0 <= at["after"] < len(frames):
            # Taken from where playback came to rest: it goes in there,
            # splitting the move it was on. The time field is its share of the
            # move, as far in as it was; the keyframe after it keeps the rest,
            # so everything after is reached when it was. It eases as that
            # move did.
            index = at["after"] + 1
            following = frames[index % len(frames)]
            share = kf.clamp_duration(duration)
            rest = kf.clamp_duration(following["duration_ms"] - share)
            frames[index % len(frames)] = {**following, "duration_ms": rest}
            frames.insert(index, kf.make_keyframe(feet, share, state, ease=kf.eases(following)))
        else:
            index = len(frames) if selected is None else selected + 1
            frames.insert(index, kf.make_keyframe(feet, duration, state, ease=eased))
        out_keyframes = set_frames(frames)
        out_selected = index
        out_duration = frames[index]["duration_ms"]
        message = ""

    elif trigger == POSE_PLAYHEAD_ID and playhead:
        # Playback came to rest: the frame it stopped on becomes the pose. On
        # a keyframe, that keyframe is selected, as if clicked; between two,
        # nothing is, and the pose remembers where it is in the sequence, for
        # + Add pose to put it there.
        frame = playhead.get("frame")
        if (
            not isinstance(preview, dict)
            or preview.get("count") != len(frames)
            or not isinstance(frame, int)
            or not 0 <= frame < len(preview.get("states", []))
        ):
            raise PreventUpdate
        start, end, ms = preview["times"][frame]
        move_ms = kf.clamp_duration(frames[end]["duration_ms"])
        on_keyframe = start if ms < 0.5 else end if move_ms - ms < 0.5 else None
        if on_keyframe is not None:
            out_selected = on_keyframe
            out_pose = bump(_keyframe_state(frames[on_keyframe], robot_config), at=None)
        else:
            raw = preview["states"][frame]
            out_selected = None
            out_pose = bump(
                pl.make_state(raw["body"], raw["offsets"]),
                at={"after": start, "ms": round(ms, 1)},
            )
        out_mode = MODE_EDIT
        message = ""

    elif isinstance(trigger, dict) and trigger.get("type") in (
        POSE_GAIT_ITEM_TYPE,
        POSE_USER_GAIT_ITEM_TYPE,
        POSE_GAIT_REPLACE_TYPE,
        POSE_USER_GAIT_REPLACE_TYPE,
    ):
        # A gait from the library, the robot's or one's own, as its
        # keyframes. Its + puts them in where a pose would go, after the one
        # selected, selecting the last so another follows on. Its ⇄ makes
        # them the whole sequence, selecting the last too, which becomes the
        # pose, so a gait added next goes on after it. The lists' buttons are
        # there with no clicks when they are drawn; only a real click counts.
        if not ctx.triggered or not ctx.triggered[0]["value"]:
            raise PreventUpdate
        try:
            if trigger["type"] in (POSE_GAIT_ITEM_TYPE, POSE_GAIT_REPLACE_TYPE):
                inserted = gait_keyframes(trigger["index"], robot_config)
            else:
                inserted = gait_library.load_gait(trigger["index"], robot_config)
        except kf.KeyframeFileError as error:
            inserted = []
            message = _pose_alert(error)
        if inserted and trigger["type"] in (POSE_GAIT_REPLACE_TYPE, POSE_USER_GAIT_REPLACE_TYPE):
            frames = list(inserted)
            out_keyframes = set_frames(frames)
            out_selected = len(frames) - 1
            out_pose = bump(_keyframe_state(frames[-1], robot_config))
            out_duration = frames[-1]["duration_ms"]
            out_mode = MODE_EDIT
            message = ""
        elif inserted:
            index = len(frames) if selected is None else selected + 1
            frames[index:index] = inserted
            out_keyframes = set_frames(frames)
            out_selected = index + len(inserted) - 1
            out_duration = frames[out_selected]["duration_ms"]
            message = ""

    elif trigger == POSE_UPDATE_BTN_ID:
        if selected is None:
            message = _pose_alert("Pick a keyframe to update.")
        else:
            # It keeps its time and easing.
            feet = pl.body_feet(state, robot_config)
            frames[selected] = kf.remade(frames[selected], feet, state)
            out_keyframes = set_frames(frames)
            message = ""

    elif trigger == POSE_DELETE_BTN_ID:
        if selected is None:
            message = _pose_alert("Pick a keyframe to delete.")
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
            message = _pose_alert(error)
        else:
            out_keyframes = set_frames(loaded)
            out_selected = 0 if loaded else None
            if loaded:
                out_pose = bump(_keyframe_state(loaded[0], robot_config))
                out_duration = loaded[0]["duration_ms"]
            out_mode = MODE_EDIT
            message = ""

    # The sliders always show the pose -- except while one is being moved,
    # when writing its own value back would fight the drag. Unless it was
    # pushed further than the body could go: then it is put back where the
    # body is.
    shown_pose = pose_store if out_pose is no_update else out_pose
    body_sliders = [shown_pose["state"]["body"][key] for key in pl.BODY_KEYS]
    if slider in BODY_WIDGET_KEYS:
        body_sliders = [
            value if slider_held and widget_id == slider else no_update
            for widget_id, value in zip(BODY_SLIDER_IDS, body_sliders)
        ]

    if foot_leg is not None:
        foot = pl.view_feet(shown_pose["state"], robot_config)[foot_leg]
        foot_fields = [_field_value(value) for value in foot]
    else:
        foot_fields = [None] * 3

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

    # A pose stays "at" its point of the sequence only while the keyframes
    # are as they were and none is selected; then the bar is the keyframe it
    # would become: as far into its move as it is, easing as the move does.
    at = (pose_store if out_pose is no_update else out_pose).get("at")
    if at and (out_keyframes is not no_update or shown_selected is not None):
        out_pose = {key: value for key, value in shown_pose.items() if key != "at"}
    elif at and trigger == POSE_PLAYHEAD_ID:
        out_duration = max(kf.MIN_DURATION_MS, round(at["ms"]))
        following = frames[(at["after"] + 1) % len(frames)]
        out_ease = ["ease"] if kf.eases(following) else []

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
    Output(POSE_HUD_ID, "className"),
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
    # Marked when a leg is out of reach, so the overlay says so even folded
    # away, when the warning inside it cannot be seen.
    hud_class = f"{POSE_HUD_CLASS} is-bad" if bad_legs else POSE_HUD_CLASS
    return scene, _reach_warning(bad_legs), hud_class


# Hands the scene to the view: the pose, whose body and feet can be picked
# and dragged, or a frame of the sequence while previewing, which cannot.
clientside_callback(
    """
    function(scene, frame, mode, preview) {
        if (!window.hexapodView) {
            return window.dash_clientside.no_update;
        }
        var previewing = mode === "%s" && preview && preview.scenes.length;
        if (previewing) {
            var index = Math.min(Math.max(frame || 0, 0), preview.scenes.length - 1);
            window.hexapodView.render("%s", preview.scenes[index], {editable: false});
        } else if (scene) {
            window.hexapodView.render("%s", scene, {editable: true});
        }
        return window.dash_clientside.no_update;
    }
    """
    % (MODE_PREVIEW, POSE_VIEW_ID, POSE_VIEW_ID),
    Output(POSE_RENDER_ACK_ID, "data"),
    Input(POSE_SCENE_STORE_ID, "data"),
    Input(POSE_FRAME_SLIDER_ID, "value"),
    Input(POSE_VIEW_MODE_ID, "data"),
    Input(POSE_PREVIEW_STORE_ID, "data"),
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
            "No keyframes yet: pose the robot in the view, then + Add pose.",
            className="dock-empty",
        )
        summary = ""

    if selected is None:
        return items, summary, "Save pose", True, True, True, True

    number = selected + 1
    last = selected == len(frames) - 1
    return items, summary, f"Save pose to #{number}", False, False, selected == 0, last


@callback(
    Output(POSE_KF_EDITOR_LABEL_ID, "children"),
    Output(POSE_ADD_BTN_ID, "children"),
    Input(POSE_KEYFRAMES_STORE_ID, "data"),
    Input(POSE_SELECTED_KF_STORE_ID, "data"),
    Input(POSE_STATE_STORE_ID, "data"),
)
def label_editor(keyframes_store, selected, pose_store):
    """What the bar is about, and where + Add pose puts the pose: after the
    keyframe selected, at the point of the sequence the pose was taken from,
    or at the end."""
    frames = keyframes_store["keyframes"] if isinstance(keyframes_store, dict) else []
    at = pose_store.get("at") if isinstance(pose_store, dict) else None
    if selected is not None and 0 <= selected < len(frames):
        number = selected + 1
        last = selected == len(frames) - 1
        return f"Keyframe #{number}", "+ Add pose" if last else f"+ Insert after #{number}"
    if at and 0 <= at["after"] < len(frames):
        seconds = _at_ms(frames, at) / 1000.0
        return f"New keyframe at {seconds:.2f} s", f"+ Add pose at {seconds:.2f} s"
    return "New keyframe", "+ Add pose"


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
# The Gaits library
# ......................

# Show the list picked, the robot's gaits or one's own. The other is only
# hidden, so its buttons stay put.
clientside_callback(
    """
    function(source) {
        var show = {}, hide = {display: "none"};
        return [%s];
    }
    """
    % ", ".join(f'source === "{source}" ? show : hide' for source in GAIT_SOURCES),
    *[Output(POSE_GAIT_LIST_IDS[source], "style") for source in GAIT_SOURCES],
    Input(POSE_GAIT_SOURCE_ID, "value"),
)


@callback(
    Output(POSE_USER_GAIT_LIST_ID, "children"),
    Input(POSE_USER_GAITS_VERSION_ID, "data"),
    Input(ROBOT_CONFIG_STORE_ID, "data"),
)
def list_user_gaits(_version, _config_store):
    """One's own gaits for the robot modelled; a gait belongs to the robot it
    was made on."""
    gaits = gait_library.list_gaits(_robot())
    return [user_gait_row(gait) for gait in gaits] if gaits else USER_GAITS_EMPTY


@callback(
    Output(POSE_USER_GAITS_VERSION_ID, "data"),
    Output(POSE_USER_GAIT_NAME_ID, "value"),
    Output(POSE_USER_GAIT_MESSAGE_ID, "children"),
    Input(POSE_USER_GAIT_SAVE_BTN_ID, "n_clicks"),
    Input(POSE_USER_GAIT_NAME_ID, "n_submit"),
    State(POSE_USER_GAIT_NAME_ID, "value"),
    State(POSE_KEYFRAMES_STORE_ID, "data"),
    State(POSE_USER_GAITS_VERSION_ID, "data"),
    prevent_initial_call=True,
)
def save_user_gait(_n_clicks, _n_submit, name, keyframes_store, version):
    """Keep the whole sequence as a gait of one's own, under the name typed
    (or Enter pressed in it)."""
    robot_config = _robot()
    frames = keyframes_store["keyframes"] if _valid(keyframes_store, robot_config) else []
    try:
        gait_library.save_gait(name, frames, robot_config)
    except ValueError as error:
        return no_update, no_update, _alert(error)
    except OSError as error:
        return no_update, no_update, _alert(f"Could not save the gait: {error}")
    return (version or 0) + 1, "", ""


@callback(
    Output(POSE_USER_GAITS_VERSION_ID, "data", allow_duplicate=True),
    Output(POSE_USER_GAIT_MESSAGE_ID, "children", allow_duplicate=True),
    Input({"type": POSE_USER_GAIT_DELETE_TYPE, "index": ALL}, "submit_n_clicks"),
    State(POSE_USER_GAITS_VERSION_ID, "data"),
    prevent_initial_call=True,
)
def delete_user_gait(_confirmed, version):
    """Delete a gait of one's own, once its dialog is confirmed. The list is
    drawn afresh with nothing confirmed; only a real confirmation counts."""
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    try:
        gait_library.delete_gait(ctx.triggered_id["index"])
    except OSError as error:
        return no_update, _alert(f"Could not delete the gait: {error}")
    return (version or 0) + 1, ""


# ......................
# Preview
# ......................


def _speed_pct(value):
    """The playback speed a typed value stands for: a whole percent, within
    range; the default for one that is not a number."""
    try:
        return int(min(max(round(float(value)), SPEED_MIN_PCT), SPEED_MAX_PCT))
    except (TypeError, ValueError):
        return SPEED_DEFAULT_PCT


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
    and the default for a box left empty."""
    applied = _speed_pct(speed_pct)
    return no_update if applied == speed_pct else applied


def _bad_frames_message(bad_frames, total):
    return _alert(
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
    # With each frame's layers and where it falls among the keyframes, so a
    # frame playback comes to rest on can become the pose (edit()).
    preview = {
        "scenes": scenes,
        "fps": PREVIEW_FPS,
        "states": states,
        "times": kf.frame_times(frames, PREVIEW_FPS, loop, speed),
        "count": len(frames),
    }
    return preview, max(len(scenes) - 1, 1), 0, message


# Play/Pause. Playing always shows the sequence, so it switches to it; pausing
# makes the frame it stopped on the pose.
clientside_callback(
    """
    function(n_clicks, is_playing, frame, max_frame) {
        var playing = !is_playing;
        var next = frame;
        if (playing && frame >= max_frame) {
            next = 0;
        }
        var skip = window.dash_clientside.no_update;
        return [
            playing,
            playing ? "⏸ Pause" : "▶ Play",
            playing ? "danger" : "primary",
            !playing,
            next,
            playing ? "%s" : skip,
            // Paused: the frame it stopped on becomes the pose.
            playing ? skip : {frame: frame, n: Date.now()},
        ];
    }
    """
    % MODE_PREVIEW,
    Output(POSE_PLAY_STATE_STORE_ID, "data"),
    Output(POSE_PLAY_BTN_ID, "children"),
    Output(POSE_PLAY_BTN_ID, "color"),
    Output(POSE_INTERVAL_ID, "disabled"),
    Output(POSE_FRAME_SLIDER_ID, "value", allow_duplicate=True),
    Output(POSE_VIEW_MODE_ID, "data", allow_duplicate=True),
    Output(POSE_PLAYHEAD_ID, "data", allow_duplicate=True),
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
                // Run out: the last frame becomes the pose.
                var rest = {frame: max_frame, n: Date.now()};
                return [max_frame, false, "▶ Play", "primary", true, rest];
            }
        }
        var skip = window.dash_clientside.no_update;
        return [next, skip, skip, skip, skip, skip];
    }
    """,
    Output(POSE_FRAME_SLIDER_ID, "value", allow_duplicate=True),
    Output(POSE_PLAY_STATE_STORE_ID, "data", allow_duplicate=True),
    Output(POSE_PLAY_BTN_ID, "children", allow_duplicate=True),
    Output(POSE_PLAY_BTN_ID, "color", allow_duplicate=True),
    Output(POSE_INTERVAL_ID, "disabled", allow_duplicate=True),
    Output(POSE_PLAYHEAD_ID, "data", allow_duplicate=True),
    Input(POSE_INTERVAL_ID, "n_intervals"),
    State(POSE_FRAME_SLIDER_ID, "value"),
    State(POSE_FRAME_SLIDER_ID, "max"),
    State(POSE_LOOP_ID, "value"),
    prevent_initial_call=True,
)

# Back to the pose -- the pose edited, or a keyframe loaded -- stops playback.
clientside_callback(
    """
    function(mode) {
        if (mode === "%s") {
            return [false, "▶ Play", "primary", true];
        }
        return window.dash_clientside.no_update;
    }
    """
    % MODE_EDIT,
    Output(POSE_PLAY_STATE_STORE_ID, "data", allow_duplicate=True),
    Output(POSE_PLAY_BTN_ID, "children", allow_duplicate=True),
    Output(POSE_PLAY_BTN_ID, "color", allow_duplicate=True),
    Output(POSE_INTERVAL_ID, "disabled", allow_duplicate=True),
    Input(POSE_VIEW_MODE_ID, "data"),
    prevent_initial_call=True,
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


@callback(
    output=dict(
        controls_class=Output(POSE_ROBOT_CONTROLS_ID, "className"),
        drive_class=Output(DRIVE_CONTROLS_ID, "className"),
        run_off=Output(POSE_RUN_BTN_ID, "disabled"),
        stop_off=Output(POSE_STOP_BTN_ID, "disabled"),
        message=Output(POSE_ROBOT_MESSAGE_ID, "children", allow_duplicate=True),
        speed_min=Output(DRIVE_SPEED_ID, "min"),
        speed_max=Output(DRIVE_SPEED_ID, "max"),
        speed=Output(DRIVE_SPEED_ID, "value", allow_duplicate=True),
    ),
    inputs=dict(_n_intervals=Input(ROBOT_POLL_INTERVAL_ID, "n_intervals")),
    state=dict(
        message=State(POSE_ROBOT_MESSAGE_ID, "children"),
        speed=State(DRIVE_SPEED_ID, "value"),
        speed_min=State(DRIVE_SPEED_ID, "min"),
        speed_max=State(DRIVE_SPEED_ID, "max"),
    ),
    prevent_initial_call="initial_duplicate",
)
def sync_robot_controls(_n_intervals, message, speed, speed_min, speed_max):
    """Grey the robot controls -- the dock's and the controller's -- out while
    there is no robot, and keep the controller's speed on the link's.

    The slider's range is the connected robot's, and its value the link's
    -- the page may have been rendered before either was known. They are
    only written when they differ, so the speed callback is not retriggered
    every second.
    """
    limits = ROBOT_LINK.robot_config["speed"]
    link_speed = ROBOT_LINK.speed_pct

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
        speed_min=no_update if speed_min == limits["min"] else limits["min"],
        speed_max=no_update if speed_max == limits["max"] else limits["max"],
        speed=no_update if speed == link_speed else link_speed,
    )
