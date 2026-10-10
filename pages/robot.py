"""What the robot link's controls do: connecting, following the connected
robot's geometry, the status pill, and the stream controls. Their widgets are
in widgets/robot_link_ui.py and widgets/dimensions_ui.py.
"""

import json

from dash import callback, no_update
from dash.dependencies import Input, Output, State

from hexapod.robot_config import describe, describe_firmware, get_simulator_dimensions
from hexapod.robot_link import ROBOT_LINK
from widgets.dimensions_ui import (
    DIMENSION_CALLBACK_INPUTS,
    DIMENSION_WIDGET_IDS,
    DIMENSIONS_JSON_ID,
)
from widgets.robot_link_ui import (
    ROBOT_CONFIG_STORE_ID,
    ROBOT_CONNECT_BTN_ID,
    ROBOT_INFO_ID,
    ROBOT_IP_INPUT_ID,
    ROBOT_POLL_INTERVAL_ID,
    SECTION_CONTROLS_CLASS,
    SECTION_CONTROLS_OFFLINE_CLASS,
    STATUS_PILL_ID,
    STREAM_CONTROLS_ID,
    STREAM_MAX_STEP_ID,
    STREAM_SWITCH_ID,
    status_pill_class,
)


# ......................
# The robot's dimensions
# ......................


@callback(Output(DIMENSIONS_JSON_ID, "children"), DIMENSION_CALLBACK_INPUTS)
def update_dimensions(front, side, middle, coxia, femur, tibia):
    dimensions = {
        "front": front or 0,
        "side": side or 0,
        "middle": middle or 0,
        "coxia": coxia or 0,
        "femur": femur or 0,
        "tibia": tibia or 0,
    }

    # A real robot's legs are mounted at the angles it reports, whatever the
    # body measurements are edited to. The generic model has no robot behind
    # it, so its legs keep pointing out from the cog as the body is resized.
    robot_config = ROBOT_LINK.robot_config
    if robot_config["source"] != "generic":
        dimensions["mount_angles"] = get_simulator_dimensions(robot_config)[
            "mount_angles"
        ]
    return json.dumps(dimensions)


# ......................
# Connecting, and the status pill
# ......................


@callback(
    Output(ROBOT_CONNECT_BTN_ID, "children"),
    Output(ROBOT_CONNECT_BTN_ID, "color"),
    Output(ROBOT_CONFIG_STORE_ID, "data"),
    Input(ROBOT_CONNECT_BTN_ID, "n_clicks"),
    State(ROBOT_IP_INPUT_ID, "value"),
    State(ROBOT_CONFIG_STORE_ID, "data"),
    prevent_initial_call=True,
)
def toggle_robot_connection(_n_clicks, ip, config_store):
    """Connect or disconnect. Connecting reads the robot's config first."""
    if ROBOT_LINK.connected:
        ROBOT_LINK.disconnect()
    else:
        ROBOT_LINK.connect(ip)

    # Only a successful connect loads a config; tell everything drawn from the
    # robot's geometry when it has changed.
    version = ROBOT_LINK.config_version
    store = no_update
    if not config_store or config_store.get("version") != version:
        store = {"version": version, "name": ROBOT_LINK.robot_config["name"]}

    if ROBOT_LINK.connected:
        return "Disconnect", "secondary", store
    return "Connect", "primary", store


@callback(
    [Output(widget_id, "value") for widget_id in DIMENSION_WIDGET_IDS]
    + [Output(ROBOT_INFO_ID, "children")],
    Input(ROBOT_CONFIG_STORE_ID, "data"),
)
def follow_robot_config(_config_store):
    """Match the simulator's dimensions to the robot's reported geometry.

    Runs on load as well as on connect: the layout is built once at import, so
    a browser refresh would otherwise show the dimensions of whichever robot
    was known when the app started rather than the one connected since.
    """
    robot_config = ROBOT_LINK.robot_config
    dimensions = get_simulator_dimensions(robot_config)
    return [
        dimensions["front"],
        dimensions["side"],
        dimensions["middle"],
        dimensions["coxia"],
        dimensions["femur"],
        dimensions["tibia"],
        describe(robot_config),
    ]


def firmware_status_text(status):
    """The connected robot's firmware, or nothing while offline."""
    return describe_firmware(status["firmware"]) if status["connected"] else ""


def link_status_text(status):
    """One line describing the link, for the status pill's tooltip."""
    if status["last_error"]:
        return f"⚠ {status['last_error']}"

    if not status["connected"]:
        return "Disconnected"

    mode = "STREAMING" if status["streaming"] else "IDLE (holding)"
    return (
        f"{status['robot_label']} @ {status['ip']} — {mode} — "
        f"{status['packets_sent']} pkts"
    )


@callback(
    Output(STATUS_PILL_ID, "children"),
    Output(STATUS_PILL_ID, "className"),
    Output(STATUS_PILL_ID, "title"),
    Input(ROBOT_POLL_INTERVAL_ID, "n_intervals"),
)
def update_robot_status(_n_intervals):
    """Refresh the status pill in the top bar.

    It reads the summary -- which robot, and whether it is reachable and being
    streamed to -- and its tooltip the detail: the address, mode and packet
    count, and the robot's firmware version.
    """
    status = ROBOT_LINK.status()
    text = link_status_text(status)
    firmware = firmware_status_text(status)

    if status["last_error"]:
        label, state = "Fault", "is-fault"
    elif not status["connected"]:
        label, state = "Offline", "is-offline"
    elif status["streaming"]:
        label, state = f"{status['robot_label']} · Streaming", "is-streaming"
    else:
        label, state = f"{status['robot_label']} · Online", "is-online"

    tooltip = f"{text}\n{firmware}" if firmware else text
    return label, status_pill_class(state), tooltip


# ......................
# Stream-to-robot controls
#
# They all drive the one link, so the sync callback re-seeds them from the
# link's state rather than trusting the defaults they were rendered with.
# ......................


@callback(
    Output(STREAM_SWITCH_ID, "value"),
    Input(STREAM_SWITCH_ID, "value"),
    prevent_initial_call=True,
)
def toggle_robot_streaming(streaming):
    ROBOT_LINK.set_streaming(streaming)
    # Reflect back what the link accepted; streaming cannot be enabled while
    # disconnected, so the switch must not appear on in that case.
    return ROBOT_LINK.streaming


@callback(
    Output(STREAM_MAX_STEP_ID, "value"),
    Input(STREAM_MAX_STEP_ID, "value"),
    prevent_initial_call=True,
)
def update_robot_max_step(max_step):
    ROBOT_LINK.set_max_step(max_step)
    return max_step


@callback(
    Output(STREAM_CONTROLS_ID, "className"),
    Output(STREAM_SWITCH_ID, "disabled"),
    Output(STREAM_MAX_STEP_ID, "disabled"),
    Output(STREAM_SWITCH_ID, "value", allow_duplicate=True),
    Output(STREAM_MAX_STEP_ID, "value", allow_duplicate=True),
    Input(ROBOT_POLL_INTERVAL_ID, "n_intervals"),
    State(STREAM_SWITCH_ID, "value"),
    State(STREAM_MAX_STEP_ID, "value"),
    prevent_initial_call="initial_duplicate",
)
def sync_stream_controls(_n_intervals, switch_value, max_step_value):
    """Keep the stream controls honest about the link.

    Offline, none of them has anything to act on, so they are greyed out and
    disabled; the status line above them says why.

    The values are only written back when they disagree with the link -- the
    page was loaded showing its rendered default, or the link dropped
    streaming on its own -- so the ordinary case does not retrigger the
    toggle callbacks every second.
    """
    status = ROBOT_LINK.status()
    offline = not status["connected"]

    streaming = status["streaming"]
    switch = no_update if bool(switch_value) == streaming else streaming

    max_step = status["max_step"]
    max_step_out = no_update if max_step_value == max_step else max_step

    return (
        SECTION_CONTROLS_OFFLINE_CLASS if offline else SECTION_CONTROLS_CLASS,
        offline,
        offline,
        switch,
        max_step_out,
    )
