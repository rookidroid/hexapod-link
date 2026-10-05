# The pose editor: drag the feet in 3D, collect the poses as keyframes, preview
# the sequence and run it on the robot.
#
# The 3D view is assets/poser.js (three.js), not a Plotly graph -- Plotly's 3D
# plot cannot drag a point. It reports a dragged foot through the
# POSER_FOOT_TARGET_ID store and draws whatever lands in POSER_SCENE_STORE_ID;
# everything in between, the kinematics included, happens here.
#
# What is being edited lives in three session stores, so it survives a visit
# to another page:
#
#   feet       {"robot", "feet": 6x3, "seq"}   the pose in the editor
#   keyframes  {"robot", "keyframes": [...]}   see hexapod/keyframes.py
#   selected   index of the keyframe the editor was loaded from, or None
#
# Foot positions only fit the robot they were placed on, so both carry that
# robot's name, and a different robot connecting starts the editor afresh.

import base64

from dash import (
    ALL,
    callback,
    clientside_callback,
    ctx,
    html,
    no_update,
)
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from hexapod import keyframes as kf
from hexapod.naming import leg_label
from hexapod.robot_config import get_sequence_fps
from hexapod.robot_link import ROBOT_LINK
from pages import helpers
from style_settings import (
    BODY_COLOR,
    BODY_MESH_COLOR,
    COG_COLOR,
    GROUND_COLOR,
    HEAD_COLOR,
    LEG_COLOR,
    PAPER_BG_COLOR,
    SUPPORT_POLYGON_MESH_COLOR,
)
from widgets.poser_ui import (
    MODE_EDIT,
    MODE_PREVIEW,
    POSER_ADD_BTN_ID,
    POSER_ANGLES_ID,
    POSER_DELETE_BTN_ID,
    POSER_DOWN_BTN_ID,
    POSER_DOWNLOAD_ID,
    POSER_DURATION_ID,
    POSER_EASE_ID,
    POSER_FEET_STORE_ID,
    POSER_FOOT_TARGET_ID,
    POSER_FRAME_DISPLAY_ID,
    POSER_FRAME_SLIDER_ID,
    POSER_INTERVAL_ID,
    POSER_KEYFRAMES_STORE_ID,
    POSER_KF_ITEM_TYPE,
    POSER_KF_LIST_ID,
    POSER_KF_SUMMARY_ID,
    POSER_LOOP_ID,
    POSER_MESSAGE_ID,
    POSER_MODE_ID,
    POSER_PLAY_BTN_ID,
    POSER_PLAY_STATE_STORE_ID,
    POSER_PREVIEW_MESSAGE_ID,
    POSER_PREVIEW_STORE_ID,
    POSER_RENDER_ACK_ID,
    POSER_RESET_BTN_ID,
    POSER_RESET_VIEW_BTN_ID,
    POSER_ROBOT_CONTROLS_ID,
    POSER_ROBOT_MESSAGE_ID,
    POSER_ROBOT_POLL_INTERVAL_ID,
    POSER_RUN_BTN_ID,
    POSER_SAVE_BTN_ID,
    POSER_SCENE_STORE_ID,
    POSER_SELECTED_KF_STORE_ID,
    POSER_SELECTED_LEG_ID,
    POSER_SELECTION_ID,
    POSER_STOP_BTN_ID,
    POSER_UP_BTN_ID,
    POSER_UPDATE_BTN_ID,
    POSER_UPLOAD_ID,
    POSER_VIEWER_ID,
    POSER_WIDGETS_SECTION,
    PREVIEW_FPS,
)
from widgets.robot_link_ui import (
    ROBOT_CONFIG_STORE_ID,
    SECTION_CONTROLS_CLASS,
    SECTION_CONTROLS_OFFLINE_CLASS,
)

# The CAD view's colours, the same as the Plotly pages use (style_settings.py).
VIEWER_COLORS = {
    "background": PAPER_BG_COLOR,
    "ground": GROUND_COLOR,
    "body": BODY_MESH_COLOR,
    "bodyOutline": BODY_COLOR,
    "leg": LEG_COLOR,
    "joint": BODY_COLOR,
    "foot": SUPPORT_POLYGON_MESH_COLOR,
    "footSelected": HEAD_COLOR,
    "head": HEAD_COLOR,
    "cog": COG_COLOR,
    "support": SUPPORT_POLYGON_MESH_COLOR,
}


# ......................
# Page layout
# ......................

# The same two columns as the other pages (pages/shared.py), with the three.js
# view where they have their Plotly graph.
layout = dbc.Row(
    [
        dbc.Col(
            dbc.Card(
                dbc.CardBody(POSER_WIDGETS_SECTION),
                className="ind-card page-panel flex-grow-1",
            ),
            width=12,
            lg=4,
            className="page-sidebar mb-3 mb-lg-0 d-flex flex-column",
        ),
        dbc.Col(
            html.Div(
                html.Div(id=POSER_VIEWER_ID, className="poser-viewer"),
                className="graph-container flex-grow-1",
            ),
            width=12,
            lg=8,
            className="page-plot d-flex flex-column",
        ),
    ],
    className="page-row flex-grow-1 m-0",
)


# ......................
# Editor state
# ......................


def _robot():
    return ROBOT_LINK.robot_config


def _fresh_feet(robot_config, seq=0):
    return {
        "robot": robot_config["name"],
        "feet": kf.standby_feet(robot_config),
        "seq": seq,
    }


def _fresh_keyframes(robot_config):
    return {"robot": robot_config["name"], "keyframes": []}


def _valid(store, robot_config):
    return isinstance(store, dict) and store.get("robot") == robot_config["name"]


def _decode_upload(contents):
    # dcc.Upload hands over a data URL: "data:<type>;base64,<payload>"
    _, _, payload = contents.partition(",")
    return base64.b64decode(payload).decode("utf-8")


@callback(
    Output(POSER_FEET_STORE_ID, "data"),
    Output(POSER_KEYFRAMES_STORE_ID, "data"),
    Output(POSER_SELECTED_KF_STORE_ID, "data"),
    Output(POSER_MESSAGE_ID, "children"),
    Output(POSER_DURATION_ID, "value"),
    Output(POSER_MODE_ID, "value", allow_duplicate=True),
    Input(POSER_FOOT_TARGET_ID, "data"),
    Input(POSER_RESET_BTN_ID, "n_clicks"),
    Input(POSER_ADD_BTN_ID, "n_clicks"),
    Input(POSER_UPDATE_BTN_ID, "n_clicks"),
    Input(POSER_DELETE_BTN_ID, "n_clicks"),
    Input(POSER_UP_BTN_ID, "n_clicks"),
    Input(POSER_DOWN_BTN_ID, "n_clicks"),
    Input({"type": POSER_KF_ITEM_TYPE, "index": ALL}, "n_clicks"),
    Input(POSER_UPLOAD_ID, "contents"),
    Input(ROBOT_CONFIG_STORE_ID, "data"),
    State(POSER_FEET_STORE_ID, "data"),
    State(POSER_KEYFRAMES_STORE_ID, "data"),
    State(POSER_SELECTED_KF_STORE_ID, "data"),
    State(POSER_DURATION_ID, "value"),
    prevent_initial_call="initial_duplicate",
)
def edit(
    foot_target,
    _reset,
    _add,
    _update,
    _delete,
    _up,
    _down,
    _item_clicks,
    upload,
    _config_store,
    feet_store,
    keyframes_store,
    selected,
    duration,
):
    """Every change to the pose, the keyframes or which keyframe is selected.

    One callback rather than one per button, because they all write the same
    stores and each needs to see what the others last left there.
    """
    robot_config = _robot()
    trigger = ctx.triggered_id

    # A different robot (or none yet): start over on this one.
    out_feet = out_keyframes = out_selected = no_update
    if trigger in (None, ROBOT_CONFIG_STORE_ID) and _valid(feet_store, robot_config):
        # Page load (or the same robot reconnecting) with a pose already in
        # the session: pass it on anyway. Dash skips a callback whose input
        # came back as no_update during the initial round, so without this
        # the view would stay empty until the pose was next changed.
        out_feet = feet_store
    if not _valid(feet_store, robot_config):
        feet_store = out_feet = _fresh_feet(robot_config)
    if not _valid(keyframes_store, robot_config):
        keyframes_store = out_keyframes = _fresh_keyframes(robot_config)
        selected = out_selected = None

    message = no_update
    out_duration = no_update
    out_mode = no_update
    frames = list(keyframes_store["keyframes"])
    if selected is not None and not 0 <= selected < len(frames):
        selected = out_selected = None

    def bump(feet):
        # The sequence number makes the scene differ from the one before even
        # when the feet do not, so a refused drag is still redrawn and the
        # foot springs back to where it was.
        return {
            **feet_store,
            "feet": kf.clean_feet(feet),
            "seq": feet_store.get("seq", 0) + 1,
        }

    def set_frames(new_frames):
        return {"robot": robot_config["name"], "keyframes": new_frames}

    if trigger == POSER_FOOT_TARGET_ID and foot_target:
        leg = foot_target.get("leg")
        target = foot_target.get("foot")
        if not isinstance(leg, int) or not 0 <= leg < 6 or not target or len(target) != 3:
            raise PreventUpdate
        feet = [list(foot) for foot in feet_store["feet"]]
        feet[leg] = [float(c) for c in target]
        _, bad_legs = kf.feet_to_pose(feet, robot_config)
        if leg in bad_legs:
            message = helpers.make_alert_message(
                f"{leg_label(leg)} cannot reach there, or a joint would pass its limit."
            )
            # While dragging the foot is left where the cursor has it; once
            # dropped it goes back to the last place it could reach.
            out_feet = bump(feet_store["feet"]) if foot_target.get("final") else no_update
        else:
            out_feet = bump(feet)
            message = ""

    elif trigger == POSER_RESET_BTN_ID:
        out_feet = bump(kf.standby_feet(robot_config))
        out_mode = MODE_EDIT
        message = ""

    elif trigger == POSER_ADD_BTN_ID:
        index = len(frames) if selected is None else selected + 1
        frames.insert(index, kf.make_keyframe(feet_store["feet"], duration))
        out_keyframes = set_frames(frames)
        out_selected = index
        out_duration = frames[index]["duration_ms"]
        message = ""

    elif trigger == POSER_UPDATE_BTN_ID:
        if selected is None:
            message = helpers.make_alert_message("Pick a keyframe in the list to update.")
        else:
            frames[selected] = kf.make_keyframe(feet_store["feet"], duration)
            out_keyframes = set_frames(frames)
            out_duration = frames[selected]["duration_ms"]
            message = ""

    elif trigger == POSER_DELETE_BTN_ID:
        if selected is None:
            message = helpers.make_alert_message("Pick a keyframe in the list to delete.")
        else:
            del frames[selected]
            out_keyframes = set_frames(frames)
            out_selected = min(selected, len(frames) - 1) if frames else None
            message = ""

    elif trigger in (POSER_UP_BTN_ID, POSER_DOWN_BTN_ID):
        step = -1 if trigger == POSER_UP_BTN_ID else 1
        if selected is None or not 0 <= selected + step < len(frames):
            raise PreventUpdate
        frames[selected], frames[selected + step] = frames[selected + step], frames[selected]
        out_keyframes = set_frames(frames)
        out_selected = selected + step

    elif isinstance(trigger, dict) and trigger.get("type") == POSER_KF_ITEM_TYPE:
        # The list is rebuilt whenever the keyframes change, and new entries
        # report in with no clicks; only a real click selects one.
        if not ctx.triggered or not ctx.triggered[0]["value"]:
            raise PreventUpdate
        index = trigger["index"]
        if not 0 <= index < len(frames):
            raise PreventUpdate
        out_selected = index
        out_feet = bump(frames[index]["feet"])
        out_duration = frames[index]["duration_ms"]
        out_mode = MODE_EDIT
        message = ""

    elif trigger == POSER_UPLOAD_ID and upload:
        try:
            loaded = kf.load(_decode_upload(upload), robot_config)
        except (kf.KeyframeFileError, ValueError) as error:
            message = helpers.make_alert_message(error)
        else:
            out_keyframes = set_frames(loaded)
            out_selected = 0 if loaded else None
            if loaded:
                out_feet = bump(loaded[0]["feet"])
                out_duration = loaded[0]["duration_ms"]
            out_mode = MODE_EDIT
            message = ""

    return out_feet, out_keyframes, out_selected, message, out_duration, out_mode


# ......................
# Drawing the pose being edited
# ......................


@callback(
    Output(POSER_SCENE_STORE_ID, "data"),
    Output(POSER_ANGLES_ID, "children"),
    Input(POSER_FEET_STORE_ID, "data"),
)
def update_scene(feet_store):
    robot_config = _robot()
    if not _valid(feet_store, robot_config):
        raise PreventUpdate

    pose, _ = kf.feet_to_pose(feet_store["feet"], robot_config)
    scene = kf.pose_to_scene(pose, robot_config)
    scene["colors"] = VIEWER_COLORS
    scene["seq"] = feet_store.get("seq", 0)
    return scene, helpers.make_poses_message(pose)


@callback(
    Output(POSER_SELECTION_ID, "children"),
    Input(POSER_SELECTED_LEG_ID, "data"),
    Input(POSER_FEET_STORE_ID, "data"),
)
def describe_selection(leg, feet_store):
    if leg is None or not isinstance(feet_store, dict):
        return "Click a foot to pick it up, then drag the arrows to move it."
    x, y, z = feet_store["feet"][leg]
    return f"{leg_label(leg)} · foot at x {x:+.1f}, y {y:+.1f}, z {z:+.1f} mm"


# Hands the scene to assets/poser.js: the pose being edited, or a frame of the
# sequence while previewing.
clientside_callback(
    """
    function(scene, frame, mode, preview) {
        if (!window.hexapodPoser) {
            return window.dash_clientside.no_update;
        }
        var previewing = mode === "preview" && preview && preview.scenes.length;
        if (previewing) {
            var index = Math.min(Math.max(frame || 0, 0), preview.scenes.length - 1);
            window.hexapodPoser.render("%s", preview.scenes[index], false);
        } else if (scene) {
            window.hexapodPoser.render("%s", scene, true);
        }
        return window.dash_clientside.no_update;
    }
    """ % (POSER_VIEWER_ID, POSER_VIEWER_ID),
    Output(POSER_RENDER_ACK_ID, "data"),
    Input(POSER_SCENE_STORE_ID, "data"),
    Input(POSER_FRAME_SLIDER_ID, "value"),
    Input(POSER_MODE_ID, "value"),
    Input(POSER_PREVIEW_STORE_ID, "data"),
)

clientside_callback(
    """
    function(n_clicks) {
        if (window.hexapodPoser) {
            window.hexapodPoser.resetCamera();
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output(POSER_RENDER_ACK_ID, "data", allow_duplicate=True),
    Input(POSER_RESET_VIEW_BTN_ID, "n_clicks"),
    prevent_initial_call=True,
)


# ......................
# The keyframe list
# ......................


@callback(
    Output(POSER_KF_LIST_ID, "children"),
    Output(POSER_KF_SUMMARY_ID, "children"),
    Input(POSER_KEYFRAMES_STORE_ID, "data"),
    Input(POSER_SELECTED_KF_STORE_ID, "data"),
    Input(POSER_LOOP_ID, "value"),
)
def list_keyframes(keyframes_store, selected, loop_values):
    frames = keyframes_store["keyframes"] if isinstance(keyframes_store, dict) else []
    if not frames:
        return (
            html.Div("No keyframes yet.", className="small text-muted"),
            "",
        )

    loop = bool(loop_values) and "loop" in loop_values
    items = []
    for index, frame in enumerate(frames):
        if index == 0:
            timing = f"{frame['duration_ms']} ms from the last" if loop else "start"
        else:
            timing = f"{frame['duration_ms']} ms"
        items.append(
            dbc.ListGroupItem(
                f"#{index + 1} · {timing}",
                id={"type": POSER_KF_ITEM_TYPE, "index": index},
                action=True,
                active=index == selected,
                className="py-1 font-monospace small",
            )
        )

    total = kf.sequence_duration_ms(frames, loop) / 1000.0
    summary = f"{len(frames)} keyframe{'s' if len(frames) != 1 else ''} · {total:.2f} s"
    return dbc.ListGroup(items), summary


@callback(
    Output(POSER_DOWNLOAD_ID, "data"),
    Input(POSER_SAVE_BTN_ID, "n_clicks"),
    State(POSER_KEYFRAMES_STORE_ID, "data"),
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


def _options(loop_values, ease_values):
    loop = bool(loop_values) and "loop" in loop_values
    ease = bool(ease_values) and "ease" in ease_values
    return loop, ease


def _bad_frames_message(bad_frames, total):
    return helpers.make_alert_message(
        f"{len(bad_frames)} of {total} frames pass out of reach between "
        "keyframes. Add a keyframe in between to route the feet around."
    )


@callback(
    Output(POSER_PREVIEW_STORE_ID, "data"),
    Output(POSER_FRAME_SLIDER_ID, "max"),
    Output(POSER_FRAME_SLIDER_ID, "marks"),
    Output(POSER_FRAME_SLIDER_ID, "value"),
    Output(POSER_PREVIEW_MESSAGE_ID, "children"),
    Input(POSER_KEYFRAMES_STORE_ID, "data"),
    Input(POSER_LOOP_ID, "value"),
    Input(POSER_EASE_ID, "value"),
)
def build_preview(keyframes_store, loop_values, ease_values):
    robot_config = _robot()
    frames = keyframes_store["keyframes"] if _valid(keyframes_store, robot_config) else []
    loop, ease = _options(loop_values, ease_values)

    poses, bad_frames = kf.interpolate(frames, robot_config, PREVIEW_FPS, loop, ease)
    scenes = [kf.pose_to_scene(pose, robot_config) for pose in poses]

    last = max(len(scenes) - 1, 1)
    marks = {0: "0", last: str(last)}
    message = _bad_frames_message(bad_frames, len(poses)) if bad_frames else ""
    return {"scenes": scenes}, last, marks, 0, message


# Play/Pause. Playing always shows the sequence, so it switches to preview.
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
    """ % MODE_PREVIEW,
    Output(POSER_PLAY_STATE_STORE_ID, "data"),
    Output(POSER_PLAY_BTN_ID, "children"),
    Output(POSER_PLAY_BTN_ID, "color"),
    Output(POSER_INTERVAL_ID, "disabled"),
    Output(POSER_FRAME_SLIDER_ID, "value", allow_duplicate=True),
    Output(POSER_MODE_ID, "value", allow_duplicate=True),
    Input(POSER_PLAY_BTN_ID, "n_clicks"),
    State(POSER_PLAY_STATE_STORE_ID, "data"),
    State(POSER_FRAME_SLIDER_ID, "value"),
    State(POSER_FRAME_SLIDER_ID, "max"),
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
    Output(POSER_FRAME_SLIDER_ID, "value", allow_duplicate=True),
    Output(POSER_PLAY_STATE_STORE_ID, "data", allow_duplicate=True),
    Output(POSER_PLAY_BTN_ID, "children", allow_duplicate=True),
    Output(POSER_PLAY_BTN_ID, "color", allow_duplicate=True),
    Output(POSER_INTERVAL_ID, "disabled", allow_duplicate=True),
    Input(POSER_INTERVAL_ID, "n_intervals"),
    State(POSER_FRAME_SLIDER_ID, "value"),
    State(POSER_FRAME_SLIDER_ID, "max"),
    State(POSER_LOOP_ID, "value"),
    prevent_initial_call=True,
)

# Back to editing stops playback; the scrubber only means something while
# previewing.
clientside_callback(
    """
    function(mode) {
        if (mode === "%s") {
            return [false, "▶ Play", "primary", true, true];
        }
        var skip = window.dash_clientside.no_update;
        return [skip, skip, skip, skip, false];
    }
    """ % MODE_EDIT,
    Output(POSER_PLAY_STATE_STORE_ID, "data", allow_duplicate=True),
    Output(POSER_PLAY_BTN_ID, "children", allow_duplicate=True),
    Output(POSER_PLAY_BTN_ID, "color", allow_duplicate=True),
    Output(POSER_INTERVAL_ID, "disabled", allow_duplicate=True),
    Output(POSER_FRAME_SLIDER_ID, "disabled"),
    Input(POSER_MODE_ID, "value"),
    prevent_initial_call="initial_duplicate",
)

clientside_callback(
    """
    function(frame, preview) {
        var frames = preview && preview.scenes ? preview.scenes.length : 0;
        var fps = %d;
        var last = Math.max(frames - 1, 0);
        var at = Math.min(frame || 0, last);
        return "Frame " + at + "/" + last + " · " + (at / fps).toFixed(2) + " s";
    }
    """ % PREVIEW_FPS,
    Output(POSER_FRAME_DISPLAY_ID, "children"),
    Input(POSER_FRAME_SLIDER_ID, "value"),
    Input(POSER_PREVIEW_STORE_ID, "data"),
)


# ......................
# Run on robot
# ......................


@callback(
    Output(POSER_ROBOT_MESSAGE_ID, "children"),
    Input(POSER_RUN_BTN_ID, "n_clicks"),
    State(POSER_KEYFRAMES_STORE_ID, "data"),
    State(POSER_LOOP_ID, "value"),
    State(POSER_EASE_ID, "value"),
    prevent_initial_call=True,
)
def run_on_robot(_n_clicks, keyframes_store, loop_values, ease_values):
    if not ROBOT_LINK.connected:
        return "Not connected — connect in the Robot panel first."

    robot_config = _robot()
    frames = keyframes_store["keyframes"] if _valid(keyframes_store, robot_config) else []
    if not frames:
        return "Add a keyframe first."

    # The robot gets frames at the rate it plays its own gaits at full speed,
    # so the sequence is as smooth as they are, and in real time: the durations
    # are what was asked for, whatever the gait speed on the Motion page is.
    loop, ease = _options(loop_values, ease_values)
    fps = get_sequence_fps(robot_config, 100)
    poses, bad_frames = kf.interpolate(frames, robot_config, fps, loop, ease)
    if bad_frames:
        return "Not sent: part of the sequence is out of reach (see Preview)."

    if not ROBOT_LINK.play_sequence(poses, loop=loop, fps=fps):
        return "Nothing to send."
    seconds = kf.sequence_duration_ms(frames, loop) / 1000.0
    return (
        f"Streaming {len(frames)} keyframes — {seconds:.2f} s"
        f"{', looping' if loop else ''}."
    )


@callback(
    Output(POSER_ROBOT_MESSAGE_ID, "children", allow_duplicate=True),
    Input(POSER_STOP_BTN_ID, "n_clicks"),
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
    Output(POSER_ROBOT_CONTROLS_ID, "className"),
    Output(POSER_RUN_BTN_ID, "disabled"),
    Output(POSER_STOP_BTN_ID, "disabled"),
    Output(POSER_ROBOT_MESSAGE_ID, "children", allow_duplicate=True),
    Input(POSER_ROBOT_POLL_INTERVAL_ID, "n_intervals"),
    State(POSER_ROBOT_MESSAGE_ID, "children"),
    prevent_initial_call="initial_duplicate",
)
def sync_robot_controls(_n_intervals, message):
    """Grey the robot controls out while there is no robot, as on the Motion page."""
    offline = not ROBOT_LINK.connected
    if offline:
        new_message = no_update if message == OFFLINE_MESSAGE else OFFLINE_MESSAGE
    else:
        new_message = "" if message == OFFLINE_MESSAGE else no_update
    return (
        SECTION_CONTROLS_OFFLINE_CLASS if offline else SECTION_CONTROLS_CLASS,
        offline,
        offline,
        new_message,
    )
