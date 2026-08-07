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
    ROBOT_PROFILE_SELECT_ID,
    ROBOT_IP_INPUT_ID,
    ROBOT_CONNECT_BTN_ID,
    ROBOT_STREAM_SWITCH_ID,
    ROBOT_MAX_STEP_SLIDER_ID,
    ROBOT_RELAX_BTN_ID,
    ROBOT_STATUS_ID,
    ROBOT_POLL_INTERVAL_ID,
)
from hexapod.const import BASE_FIGURE
from hexapod.robot_link import ROBOT_LINK
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
    params_hidden_section = html.Div(
        id=params_hidden_section_id, style={"display": "none"}
    )
    message_section = html.Div(id=message_section_id)

    return [
        DIMENSIONS_WIDGETS_SECTION,
        params_widgets_section,
        ROBOT_LINK_WIDGETS_SECTION,
        message_section,
        DIMENSIONS_HIDDEN_SECTION,
        params_hidden_section,
    ]


# ......................
# Physical robot link callbacks
#
# Registered once here because the robot link panel is part of the shared
# sidebar. suppress_callback_exceptions is on, so these are inert on any page
# that does not render the panel.
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
    Input(ROBOT_POLL_INTERVAL_ID, "n_intervals"),
)
def update_robot_status(_n_intervals):
    status = ROBOT_LINK.status()
    base_class = "small font-monospace text-center "

    if status["last_error"]:
        return f"⚠ {status['last_error']}", base_class + "text-danger"

    if not status["connected"]:
        return "Disconnected", base_class + "text-muted"

    mode = "STREAMING" if status["streaming"] else "IDLE (holding)"
    text = f"● {status['ip']} — {mode} — {status['packets_sent']} pkts"
    return text, base_class + ("text-success" if status["streaming"] else "text-info")


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
