"""Servo calibration: edit the robot's offsets through its own HTTP routes.

Nothing is simulated here. The page talks to the connected robot only, over the
same routes its built-in calibration page uses (hexapod/robot_http.py).
"""

import dash_bootstrap_components as dbc
from dash import ctx, html, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from app import app
from hexapod import robot_http
from hexapod.robot_http import RobotHttpError
from hexapod.robot_link import ROBOT_LINK
from pages import shared
from widgets.calibration_ui import (
    CALIBRATION_APPLY_BTN_ID,
    CALIBRATION_CONTROLS_ID,
    CALIBRATION_ENTER_BTN_ID,
    CALIBRATION_EXIT_BTN_ID,
    CALIBRATION_MAX_OFFSET,
    CALIBRATION_MESSAGE_ID,
    CALIBRATION_MODE_STORE_ID,
    CALIBRATION_POLL_INTERVAL_ID,
    CALIBRATION_RELOAD_BTN_ID,
    CALIBRATION_SAVE_BTN_ID,
    CALIBRATION_STATUS_ID,
    CALIBRATION_WIDGETS_SECTION,
    OFFSET_INPUT_IDS,
)
from widgets.robot_link_ui import SECTION_CONTROLS_CLASS, SECTION_CONTROLS_OFFLINE_CLASS

layout = shared.make_scrollable_page(
    dbc.Container(
        dbc.Row(dbc.Col(CALIBRATION_WIDGETS_SECTION, width=12, lg=7, xl=6)),
        fluid=True,
        className="pb-4",
    )
)


# ......................
# Offsets <-> the 18 inputs
#
# The firmware's layout is {"left": [3 legs][3 joints], "right": ...}, legs
# front to back. The inputs are leg-major in simulator order, right legs first
# (hexapod/naming.py), so leg n of a side is row n of that side's table.
# ......................


def offsets_to_values(offsets):
    """Firmware offsets JSON -> the 18 input values."""
    values = []
    for side in ("right", "left"):
        for leg in offsets[side]:
            values.extend(int(v) for v in leg)
    if len(values) != len(OFFSET_INPUT_IDS):
        raise ValueError("offsets must be 3 legs x 3 joints per side")
    return values


def values_to_offsets(values):
    """The 18 input values -> firmware offsets JSON, blanks as 0, clamped."""
    ticks = [
        max(-CALIBRATION_MAX_OFFSET, min(CALIBRATION_MAX_OFFSET, int(round(v or 0))))
        for v in values
    ]
    rows = [ticks[i : i + 3] for i in range(0, len(ticks), 3)]
    return {"right": rows[0:3], "left": rows[3:6]}


def _ok(text):
    return html.Span(text, className="text-success")


def _error(text):
    return html.Span(f"⚠ {text}", className="text-danger")


# ......................
# Buttons
#
# One callback for all five, so the inputs, the message and the mode flag each
# have a single writer.
# ......................


@app.callback(
    [Output(input_id, "value") for input_id in OFFSET_INPUT_IDS]
    + [
        Output(CALIBRATION_MESSAGE_ID, "children"),
        Output(CALIBRATION_MODE_STORE_ID, "data"),
    ],
    [
        Input(CALIBRATION_ENTER_BTN_ID, "n_clicks"),
        Input(CALIBRATION_EXIT_BTN_ID, "n_clicks"),
        Input(CALIBRATION_RELOAD_BTN_ID, "n_clicks"),
        Input(CALIBRATION_APPLY_BTN_ID, "n_clicks"),
        Input(CALIBRATION_SAVE_BTN_ID, "n_clicks"),
    ],
    [State(input_id, "value") for input_id in OFFSET_INPUT_IDS],
    prevent_initial_call=True,
)
def handle_calibration_buttons(*args):
    values = list(args[5:])
    unchanged = [no_update] * len(OFFSET_INPUT_IDS)

    if not ROBOT_LINK.connected:
        return unchanged + [_error("Not connected."), no_update]

    ip = ROBOT_LINK.ip
    button = ctx.triggered_id
    try:
        if button == CALIBRATION_ENTER_BTN_ID:
            # The firmware puts calibration ahead of everything else, so a gait
            # left streaming would only fight it for no effect.
            ROBOT_LINK.stop_sequence()
            ROBOT_LINK.set_streaming(False)
            offsets = robot_http.enter_calibration(ip)
            return offsets_to_values(offsets) + [
                _ok("Calibration mode — the robot is holding its calibration posture."),
                True,
            ]

        if button == CALIBRATION_EXIT_BTN_ID:
            robot_http.exit_calibration(ip)
            return unchanged + [_ok("Left calibration mode."), False]

        if button == CALIBRATION_RELOAD_BTN_ID:
            offsets = robot_http.get_offsets(ip)
            return offsets_to_values(offsets) + [
                _ok("Loaded the robot's current offsets."),
                no_update,
            ]

        if button == CALIBRATION_APPLY_BTN_ID:
            offsets = values_to_offsets(values)
            reply = robot_http.set_offsets(ip, offsets)
            applied = offsets_to_values(offsets)
            if any(v is not None and v != a for v, a in zip(values, applied)):
                reply += f" (limited to ±{CALIBRATION_MAX_OFFSET} ticks)"
            return applied + [_ok(reply), no_update]

        if button == CALIBRATION_SAVE_BTN_ID:
            reply = robot_http.save_offsets(ip)
            return unchanged + [_ok(reply), no_update]
    except (RobotHttpError, ValueError, KeyError, TypeError) as error:
        return unchanged + [_error(str(error)), no_update]

    raise PreventUpdate


# ......................
# Enable what can be used
# ......................


@app.callback(
    [
        Output(CALIBRATION_CONTROLS_ID, "className"),
        Output(CALIBRATION_STATUS_ID, "children"),
        Output(CALIBRATION_STATUS_ID, "className"),
        Output(CALIBRATION_ENTER_BTN_ID, "disabled"),
        Output(CALIBRATION_EXIT_BTN_ID, "disabled"),
        Output(CALIBRATION_RELOAD_BTN_ID, "disabled"),
        Output(CALIBRATION_APPLY_BTN_ID, "disabled"),
        Output(CALIBRATION_SAVE_BTN_ID, "disabled"),
    ]
    + [Output(input_id, "disabled") for input_id in OFFSET_INPUT_IDS],
    [
        Input(CALIBRATION_POLL_INTERVAL_ID, "n_intervals"),
        Input(CALIBRATION_MODE_STORE_ID, "data"),
    ],
)
def sync_calibration_controls(_n_intervals, calibrating):
    """Offline, nothing here has a robot to talk to; the robot only accepts new
    offsets in calibration mode, so Apply and the grid wait for that."""
    status = ROBOT_LINK.status()
    offline = not status["connected"]
    calibrating = bool(calibrating) and not offline

    if offline:
        text, colour = "Connect a robot to calibrate it.", "text-muted"
    elif calibrating:
        text, colour = f"● {status['robot_label']} — CALIBRATING", "text-warning"
    else:
        text, colour = f"● {status['robot_label']} — not in calibration mode", "text-info"

    return [
        SECTION_CONTROLS_OFFLINE_CLASS if offline else SECTION_CONTROLS_CLASS,
        text,
        "small font-monospace text-center mt-2 " + colour,
        offline,
        not calibrating,
        offline,
        not calibrating,
        offline,
    ] + [not calibrating] * len(OFFSET_INPUT_IDS)
