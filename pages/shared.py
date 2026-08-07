import json
import dash_bootstrap_components as dbc
from dash import dcc, html
from dash.dependencies import Output, Input, State
from app import app
from widgets.dimensions_ui import (
    DIMENSION_CALLBACK_INPUTS,
    DIMENSION_WIDGET_IDS,
    DIMENSIONS_WIDGETS_SECTION,
)
from widgets.robot_link_ui import (
    ROBOT_LINK_WIDGETS_SECTION,
    ROBOT_MOTION_WIDGETS_SECTION,
    ROBOT_PROFILE_SELECT_ID,
    ROBOT_IP_INPUT_ID,
    ROBOT_CONNECT_BTN_ID,
    ROBOT_STREAM_SWITCH_ID,
    ROBOT_MAX_STEP_SLIDER_ID,
    ROBOT_RELAX_BTN_ID,
    ROBOT_STATUS_ID,
    ROBOT_POLL_INTERVAL_ID,
    ROBOT_MOTION_SELECT_ID,
    ROBOT_MOTION_MODE_ID,
    ROBOT_MOTION_LOOP_ID,
    ROBOT_MOTION_RUN_BTN_ID,
    ROBOT_MOTION_STOP_BTN_ID,
    ROBOT_MOTION_MESSAGE_ID,
)
from hexapod.const import BASE_FIGURE
from hexapod.path_generator import generate_poses
from hexapod.robot_link import ROBOT_LINK, MOTION_COMMANDS
from hexapod.robot_profiles import get_profile, get_simulator_dimensions


# ......................
# Update hexapod dimensions callback
# ......................

DIMENSIONS_HIDDEN_SECTION_ID = "hexapod-dimensions-values"
DIMENSIONS_HIDDEN_SECTION = html.Div(
    id=DIMENSIONS_HIDDEN_SECTION_ID, style={"display": "none"}
)
DIMS_JSON_CALLBACK_INPUT = Input(DIMENSIONS_HIDDEN_SECTION_ID, "children")
DIMS_JSON_CALLBACK_OUTPUT = Output(DIMENSIONS_HIDDEN_SECTION_ID, "children")


@app.callback(DIMS_JSON_CALLBACK_OUTPUT, DIMENSION_CALLBACK_INPUTS)
def update_dimensions(front, side, middle, coxia, femur, tibia):
    dimensions = {
        "front": front or 0,
        "side": side or 0,
        "middle": middle or 0,
        "coxia": coxia or 0,
        "femur": femur or 0,
        "tibia": tibia or 0,
    }
    return json.dumps(dimensions)


# ......................
# Make uniform layout
# Graph on the right, controls on the left
# ......................


def make_standard_page_layout(graph_id, sidebar_sections):
    sidebar = dbc.Col(
        dbc.Card(
            dbc.CardBody(sidebar_sections),
            className="scifi-card flex-grow-1",
            style={"overflowY": "auto", "minHeight": 0},
        ),
        width=12,
        lg=4,
        className="mb-3 mb-lg-0 d-flex flex-column",
        style={"minHeight": 0}
    )
    graph = dbc.Col(
        html.Div(
            dcc.Graph(
                id=graph_id,
                figure=BASE_FIGURE,
                responsive=True,
                style={"height": "100%", "width": "100%"},
            ),
            className="graph-container flex-grow-1",
            style={"minHeight": 0},
        ),
        width=12,
        lg=8,
        className="d-flex flex-column",
        style={"minHeight": 0}
    )

    layout = dbc.Row([sidebar, graph], className="flex-grow-1 m-0 h-100", style={"minHeight": 0})
    return layout


# ......................
# Make standard sidebar
# ......................


def make_standard_page_sidebar(
    message_section_id, params_hidden_section_id, params_widgets_section
):
    """Sidebar holding only what is specific to one page.

    Robot dimensions and everything that talks to the hardware are deliberately
    absent: they live in GLOBAL_CONTROLS_PANEL, mounted once for the whole app.
    """
    params_hidden_section = html.Div(
        id=params_hidden_section_id, style={"display": "none"}
    )
    message_section = html.Div(id=message_section_id)

    return [
        params_widgets_section,
        message_section,
        params_hidden_section,
    ]


# ......................
# Global controls panel
#
# Dimensions and the robot link describe one robot, not one page, so they are
# mounted once outside the routed page content. Keeping them here means their
# values survive navigation instead of being rebuilt at defaults on every page
# change, and there is only ever one connect button, one profile, one stream
# switch.
#
# It is a drawer rather than a column so that no page has to give up layout
# space for it and the landing page can reach it too.
#
# Deliberately not a dbc.Offcanvas: that unmounts its children while closed, so
# every callback wired to these widgets -- including the one that publishes the
# dimensions the pages plot from -- would stop firing whenever the drawer was
# shut. This one is always mounted and only slid out of view by CSS.
# ......................

GLOBAL_PANEL_ID = "global-controls-panel"
GLOBAL_PANEL_TOGGLE_ID = "global-controls-toggle"
GLOBAL_PANEL_CLOSE_ID = "global-controls-close"

# The navbar button is also the app's status readout: ONLINE means the link to
# the hexapod is up, OFFLINE means it is not. The state modifier drives the LED
# and the accent bar in scifi.css.
_TOGGLE_BASE_CLASS = "scifi-status-btn"


def _toggle_label(state):
    return f"ROBOT: {state}"


def _toggle_class(state):
    return f"{_TOGGLE_BASE_CLASS} {state}"


GLOBAL_PANEL_TOGGLE_LABEL = _toggle_label("OFFLINE")
GLOBAL_PANEL_TOGGLE_CLASS = _toggle_class("is-offline")

_PANEL_CLASS = "global-drawer"
_PANEL_CLASS_OPEN = "global-drawer global-drawer-open"

_panel_header = html.Div(
    [
        html.H6("ROBOT", className="mb-0"),
        dbc.Button(
            "✕",
            id=GLOBAL_PANEL_CLOSE_ID,
            color="link",
            className="p-0 fw-bold text-decoration-none",
        ),
    ],
    className="d-flex justify-content-between align-items-center mb-3",
)

GLOBAL_CONTROLS_PANEL = html.Div(
    [
        _panel_header,
        DIMENSIONS_WIDGETS_SECTION,
        ROBOT_LINK_WIDGETS_SECTION,
        ROBOT_MOTION_WIDGETS_SECTION,
        DIMENSIONS_HIDDEN_SECTION,
    ],
    id=GLOBAL_PANEL_ID,
    className=_PANEL_CLASS,
)


@app.callback(
    Output(GLOBAL_PANEL_ID, "className"),
    Input(GLOBAL_PANEL_TOGGLE_ID, "n_clicks"),
    Input(GLOBAL_PANEL_CLOSE_ID, "n_clicks"),
    State(GLOBAL_PANEL_ID, "className"),
    prevent_initial_call=True,
)
def toggle_global_panel(_toggle_clicks, _close_clicks, class_name):
    if class_name == _PANEL_CLASS_OPEN:
        return _PANEL_CLASS
    return _PANEL_CLASS_OPEN


# ......................
# Physical robot link callbacks
#
# Registered once here, against the single set of widgets in the global panel.
# ......................


@app.callback(
    [Output(widget_id, "value") for widget_id in DIMENSION_WIDGET_IDS]
    + [
        Output(ROBOT_IP_INPUT_ID, "value"),
        Output(ROBOT_CONNECT_BTN_ID, "children", allow_duplicate=True),
        Output(ROBOT_CONNECT_BTN_ID, "color", allow_duplicate=True),
    ],
    Input(ROBOT_PROFILE_SELECT_ID, "value"),
    prevent_initial_call=True,
)
def select_robot_profile(profile_name):
    """Point the link at a different robot and match the simulator to it.

    The two robots have different leg geometry, so the simulator's dimensions
    are set from the profile as well; leaving them at the previous robot's
    values would make the on-screen hexapod disagree with the hardware.
    """
    ROBOT_LINK.set_profile(profile_name)

    dimensions = get_simulator_dimensions(profile_name)
    dimension_values = [
        dimensions["front"],
        dimensions["side"],
        dimensions["middle"],
        dimensions["coxia"],
        dimensions["femur"],
        dimensions["tibia"],
    ]

    # set_profile() drops any open session, so the button must reflect that.
    return dimension_values + [get_profile(profile_name)["ip"], "Connect", "primary"]


@app.callback(
    Output(ROBOT_CONNECT_BTN_ID, "children"),
    Output(ROBOT_CONNECT_BTN_ID, "color"),
    Input(ROBOT_CONNECT_BTN_ID, "n_clicks"),
    State(ROBOT_IP_INPUT_ID, "value"),
    prevent_initial_call=True,
)
def toggle_robot_connection(_n_clicks, ip):
    if ROBOT_LINK.connected:
        ROBOT_LINK.disconnect()
    else:
        ROBOT_LINK.connect(ip)

    if ROBOT_LINK.connected:
        return "Disconnect", "secondary"
    return "Connect", "primary"


@app.callback(
    Output(ROBOT_STREAM_SWITCH_ID, "value"),
    Input(ROBOT_STREAM_SWITCH_ID, "value"),
    prevent_initial_call=True,
)
def toggle_robot_streaming(streaming):
    ROBOT_LINK.set_streaming(streaming)
    # Reflect back what the link accepted; streaming cannot be enabled while
    # disconnected, so the switch must not appear on in that case.
    return ROBOT_LINK.streaming


@app.callback(
    Output(ROBOT_MAX_STEP_SLIDER_ID, "value"),
    Input(ROBOT_MAX_STEP_SLIDER_ID, "value"),
    prevent_initial_call=True,
)
def update_robot_max_step(max_step):
    ROBOT_LINK.set_max_step(max_step)
    return max_step


@app.callback(
    Output(ROBOT_STREAM_SWITCH_ID, "value", allow_duplicate=True),
    Input(ROBOT_RELAX_BTN_ID, "n_clicks"),
    prevent_initial_call=True,
)
def relax_robot(_n_clicks):
    ROBOT_LINK.relax()
    return False


@app.callback(
    Output(ROBOT_STATUS_ID, "children"),
    Output(ROBOT_STATUS_ID, "className"),
    Output(GLOBAL_PANEL_TOGGLE_ID, "children"),
    Output(GLOBAL_PANEL_TOGGLE_ID, "className"),
    Input(ROBOT_POLL_INTERVAL_ID, "n_intervals"),
)
def update_robot_status(_n_intervals):
    """Refresh the detail line in the panel and the navbar status readout.

    The navbar carries the summary -- whether the robot is reachable -- so link
    state is legible from any page without opening the drawer; the detail line
    inside the drawer carries the address, mode and packet count.
    """
    status = ROBOT_LINK.status()
    base_class = "small font-monospace text-center "

    if status["last_error"]:
        return (
            f"⚠ {status['last_error']}",
            base_class + "text-danger",
            _toggle_label("FAULT"),
            _toggle_class("is-fault"),
        )

    if not status["connected"]:
        return (
            "Disconnected",
            base_class + "text-muted",
            _toggle_label("OFFLINE"),
            _toggle_class("is-offline"),
        )

    mode = "STREAMING" if status["streaming"] else "IDLE (holding)"
    text = f"● {status['ip']} — {mode} — {status['packets_sent']} pkts"

    if status["streaming"]:
        return (
            text,
            base_class + "text-success",
            _toggle_label("ONLINE"),
            _toggle_class("is-streaming"),
        )
    return (
        text,
        base_class + "text-info",
        _toggle_label("ONLINE"),
        _toggle_class("is-online"),
    )


# ......................
# Run on robot
#
# Commands the hardware from the global panel, so a gait can be started or
# stopped without first navigating to the motion page.
# ......................


@app.callback(
    Output(ROBOT_MOTION_MESSAGE_ID, "children"),
    Input(ROBOT_MOTION_RUN_BTN_ID, "n_clicks"),
    State(ROBOT_MOTION_SELECT_ID, "value"),
    State(ROBOT_MOTION_MODE_ID, "value"),
    State(ROBOT_MOTION_LOOP_ID, "value"),
    State(ROBOT_PROFILE_SELECT_ID, "value"),
    prevent_initial_call=True,
)
def run_motion_on_robot(_n_clicks, motion_name, mode, loop_values, profile_name):
    if not ROBOT_LINK.connected:
        return "Not connected — connect in the ROBOT LINK panel first."

    loop = bool(loop_values) and "loop" in loop_values

    if mode == "native":
        if motion_name not in MOTION_COMMANDS:
            # "standup" is the firmware's boot sequence, not a motion LUT it
            # can be commanded into.
            return (
                f"'{motion_name}' has no built-in equivalent on the robot. "
                "Use 'Stream frames from simulator' instead."
            )
        if ROBOT_LINK.send_motion_command(motion_name):
            return f"Robot running its own '{motion_name}' gait."
        return "Failed to send motion command."

    frames = generate_poses(motion_name, profile_name)
    if not ROBOT_LINK.play_sequence(frames, loop=loop):
        return "Nothing to stream for this motion."
    return f"Streaming '{motion_name}' — {len(frames)} frames{' (looping)' if loop else ''}."


@app.callback(
    Output(ROBOT_MOTION_MESSAGE_ID, "children", allow_duplicate=True),
    Input(ROBOT_MOTION_STOP_BTN_ID, "n_clicks"),
    prevent_initial_call=True,
)
def stop_motion_on_robot(_n_clicks):
    if not ROBOT_LINK.connected:
        return "Not connected."

    ROBOT_LINK.stop_sequence()
    ROBOT_LINK.send_motion_command("standby")
    return "Robot returning to standby."


# ......................
# Make outputs, inputs, and states for page update callbacks
# .....................


def make_standard_page_callback_params(graph_id, params_section_id, message_section_id):

    message_callback_output = Output(message_section_id, "children")
    params_json_callback_input = Input(params_section_id, "children")
    outputs = [Output(graph_id, "figure"), message_callback_output]
    inputs = [DIMS_JSON_CALLBACK_INPUT, params_json_callback_input]
    states = [State(graph_id, "relayoutData"), State(graph_id, "figure")]
    return outputs, inputs, states
