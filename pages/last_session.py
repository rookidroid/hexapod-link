"""Open the workspace as it was left when the app was last closed.

The pose and the sequence being edited, which keyframe is selected, and the
controls of the dock, the view and playback are kept with the preferences
(load_workspace in hexapod/preferences.py) each time one changes, and put
into the layout as each page is served (hexapod_link.py). The browser cannot
keep them: the desktop window runs in pywebview's private mode, on a fresh
port each launch, so its session storage starts empty every time.

What belongs to the robot link rather than to the page -- the stream's speed
limit and the controller's speed -- is given back to the link as the app
starts (restore_robot_link); the page then shows the link's. Streaming itself
is never switched back on: the robot would start moving the moment it
connected.

A value that is not usable, from an older version or edited by hand, is
dropped, and the control keeps its default. The pose and the sequence carry
the robot they were made on, and pages/pose.py starts afresh on another.
"""

import json
import math

from dash import Input, callback, ctx

from hexapod import keyframes as kf
from hexapod import pose_layers as pl
from hexapod.preferences import load_workspace, save_workspace
from hexapod.robot_link import ROBOT_LINK
from widgets.dimensions_ui import DIMENSION_WIDGET_IDS, WIDGET_NAMES
from widgets.pose_ui import (
    BODY_MODE_MOVE,
    BODY_MODE_ROTATE,
    GAIT_SOURCES,
    POSE_BODY_MODE_ID,
    POSE_DURATION_ID,
    POSE_GAIT_SOURCE_ID,
    POSE_KEYFRAMES_STORE_ID,
    POSE_KF_EASE_ID,
    POSE_LOOP_ID,
    POSE_SELECTED_KF_STORE_ID,
    POSE_SPEED_ID,
    POSE_STATE_STORE_ID,
    POSE_USER_GAIT_NAME_ID,
    SPEED_MAX_PCT,
    SPEED_MIN_PCT,
)
from widgets.robot_link_ui import DRIVE_SPEED_ID, ROBOT_IP_INPUT_ID, STREAM_MAX_STEP_ID

# ......................
# Checking what was saved
# ......................


def _number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or not low <= value <= high:
        return None
    return value


def _choice(options):
    return lambda value: value if value in options else None


def _ticks(options):
    """A checklist's value: the options ticked."""

    def check(value):
        if isinstance(value, list) and all(item in options for item in value):
            return value
        return None

    return check


def _text(most):
    def check(value):
        return value if isinstance(value, str) and len(value) <= most else None

    return check


def _feet(feet):
    try:
        feet = [[float(v) for v in foot] for foot in feet]
    except (TypeError, ValueError):
        return False
    return len(feet) == 6 and all(len(f) == 3 and all(map(math.isfinite, f)) for f in feet)


def _pose(store):
    """The pose store (pages/pose.py): the robot, the layers and the feet."""
    if not isinstance(store, dict) or not isinstance(store.get("robot"), str):
        return None
    if not pl.is_state(store.get("state")) or not _feet(store.get("feet")):
        return None
    return store


def _keyframes(store):
    """The keyframes store, its keyframes as a saved file would have them."""
    if not isinstance(store, dict) or not isinstance(store.get("robot"), str):
        return None
    document = {
        "format": kf.FILE_FORMAT,
        "version": kf.FILE_VERSION,
        "robot": store["robot"],
        "keyframes": store.get("keyframes"),
    }
    try:
        kf.load(json.dumps(document), {"name": store["robot"]})
    except (kf.KeyframeFileError, TypeError, ValueError):
        return None
    return store


def _selected(index):
    if index is None:
        return None
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        return None
    return index


# What is kept, by the name it is kept under: the component and property it
# is read from and put back into, and what a usable value is.
FIELDS = {
    "pose": (POSE_STATE_STORE_ID, "data", _pose),
    "keyframes": (POSE_KEYFRAMES_STORE_ID, "data", _keyframes),
    "selected": (POSE_SELECTED_KF_STORE_ID, "data", _selected),
    "body_mode": (POSE_BODY_MODE_ID, "value", _choice((BODY_MODE_MOVE, BODY_MODE_ROTATE))),
    "gait_source": (POSE_GAIT_SOURCE_ID, "value", _choice(GAIT_SOURCES)),
    "gait_name": (POSE_USER_GAIT_NAME_ID, "value", _text(40)),
    "duration": (
        POSE_DURATION_ID,
        "value",
        lambda v: _number(v, kf.MIN_DURATION_MS, kf.MAX_DURATION_MS),
    ),
    "ease": (POSE_KF_EASE_ID, "value", _ticks(("ease",))),
    "speed": (POSE_SPEED_ID, "value", lambda v: _number(v, SPEED_MIN_PCT, SPEED_MAX_PCT)),
    "loop": (POSE_LOOP_ID, "value", _ticks(("loop",))),
    "robot_ip": (ROBOT_IP_INPUT_ID, "value", _text(253)),
}

# Kept from the link's controls, but given back to the link rather than to
# the page.
LINK_FIELDS = {
    "max_step": (STREAM_MAX_STEP_ID, "value"),
    "drive_speed": (DRIVE_SPEED_ID, "value"),
}

# The Dimensions panel's measurements, with the robot they were set on.
DIMENSIONS_KEY = "dimensions"


def saved_values():
    """The usable saved values, by name; one missing or unusable is left out."""
    saved = load_workspace()
    values = {}
    for name, (_id, _prop, check) in FIELDS.items():
        if name in saved:
            value = check(saved[name])
            if value is not None or (name == "selected" and saved[name] is None):
                values[name] = value
    return values


# ......................
# Putting it back
# ......................

_defaults = {}


def restore(layout):
    """Set the layout's components to what was saved, and the rest back to
    their defaults: the layout is built once and served again on each load."""
    values = saved_values()
    for name, (component_id, prop, _check) in FIELDS.items():
        component = layout[component_id]
        if name not in _defaults:
            _defaults[name] = getattr(component, prop, None)
        setattr(component, prop, values.get(name, _defaults[name]))
    return layout


def saved_dimensions(robot_name):
    """The Dimensions panel's measurements as they were left on this robot,
    by WIDGET_NAMES, or None."""
    saved = load_workspace().get(DIMENSIONS_KEY)
    if not isinstance(saved, dict) or saved.get("robot") != robot_name:
        return None
    values = saved.get("values")
    if not isinstance(values, dict):
        return None
    dimensions = {name: _number(values.get(name), 0, 10_000) for name in WIDGET_NAMES}
    return dimensions if None not in dimensions.values() else None


def restore_robot_link():
    """Give the link its stream speed limit and controller speed as left."""
    saved = load_workspace()
    max_step = _number(saved.get("max_step"), 1, 1000)
    if max_step is not None:
        ROBOT_LINK.set_max_step(max_step)
    speed = _number(saved.get("drive_speed"), 1, 1000)
    if speed is not None:
        ROBOT_LINK.set_motion_speed(speed)


# ......................
# Keeping it
# ......................

_KEPT = {**{name: field[:2] for name, field in FIELDS.items()}, **LINK_FIELDS}
_BY_PROP = {f"{component_id}.{prop}": name for name, (component_id, prop) in _KEPT.items()}


@callback(
    [Input(component_id, prop) for component_id, prop in _KEPT.values()],
    prevent_initial_call=True,
)
def keep_workspace(*_values):
    """Keep what changed, under its name."""
    changed = {
        _BY_PROP[prop_id]: value
        for prop_id, value in ctx.inputs.items()
        if prop_id in ctx.triggered_prop_ids
    }
    if changed:
        save_workspace(changed)


@callback(
    [Input(widget_id, "value") for widget_id in DIMENSION_WIDGET_IDS],
    prevent_initial_call=True,
)
def keep_dimensions(*values):
    """Keep the measurements, with the robot they were set on."""
    save_workspace(
        {
            DIMENSIONS_KEY: {
                "robot": ROBOT_LINK.robot_config["name"],
                "values": dict(zip(WIDGET_NAMES, values)),
            }
        }
    )
