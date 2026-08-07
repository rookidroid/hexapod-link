# Widgets for connecting to and driving the physical hexapod.
#
# Every widget here is mounted once, in the global panel, so the link's UI state
# survives page navigation and cannot disagree with itself across pages.
import dash_bootstrap_components as dbc
from dash import dcc, html

from settings import ROBOT_DEFAULT_MAX_STEP
from hexapod.robot_profiles import DEFAULT_PROFILE, PROFILE_OPTIONS, get_profile
from widgets.motion_ui import MOTION_TYPES

# --- Element IDs ---
ROBOT_PROFILE_SELECT_ID = "robot-profile-select"
ROBOT_IP_INPUT_ID = "robot-ip-input"
ROBOT_CONNECT_BTN_ID = "robot-connect-btn"
ROBOT_STREAM_SWITCH_ID = "robot-stream-switch"
ROBOT_MAX_STEP_SLIDER_ID = "robot-max-step-slider"
ROBOT_RELAX_BTN_ID = "robot-relax-btn"
ROBOT_STATUS_ID = "robot-status"
ROBOT_STATE_STORE_ID = "robot-state-store"
ROBOT_POLL_INTERVAL_ID = "robot-poll-interval"

ROBOT_MOTION_SELECT_ID = "robot-motion-select"
ROBOT_MOTION_MODE_ID = "robot-motion-mode"
ROBOT_MOTION_LOOP_ID = "robot-motion-loop"
ROBOT_MOTION_RUN_BTN_ID = "robot-motion-run-btn"
ROBOT_MOTION_STOP_BTN_ID = "robot-motion-stop-btn"
ROBOT_MOTION_MESSAGE_ID = "robot-motion-message"

# Poll the link often enough that the status badge feels live, but not so often
# that it adds noticeable callback traffic.
STATUS_POLL_MS = 1000


profile_select = dbc.Select(
    id=ROBOT_PROFILE_SELECT_ID,
    options=PROFILE_OPTIONS,
    value=DEFAULT_PROFILE,
    className="mb-3 form-control",
)

connection_row = dbc.Row(
    [
        dbc.Col(
            dbc.Input(
                id=ROBOT_IP_INPUT_ID,
                type="text",
                value=get_profile(DEFAULT_PROFILE)["ip"],
                debounce=True,
                placeholder="192.168.4.1",
            ),
            width=7,
        ),
        dbc.Col(
            dbc.Button(
                "Connect",
                id=ROBOT_CONNECT_BTN_ID,
                color="primary",
                className="w-100 fw-bold",
            ),
            width=5,
        ),
    ],
    className="mb-3 g-2",
)

stream_row = dbc.Row(
    [
        dbc.Col(
            dbc.Switch(
                id=ROBOT_STREAM_SWITCH_ID,
                label="Stream pose to robot",
                value=False,
                className="fw-bold mb-0",
            ),
            width=7,
        ),
        dbc.Col(
            dbc.Button(
                "RELAX",
                id=ROBOT_RELAX_BTN_ID,
                color="danger",
                className="w-100 fw-bold",
            ),
            width=5,
        ),
    ],
    className="mb-3 g-2 align-items-center",
)

max_step_slider = html.Div(
    [
        html.Label("Max joint speed (ticks/cycle)", className="fw-bold mb-1"),
        dcc.Slider(
            id=ROBOT_MAX_STEP_SLIDER_ID,
            min=1,
            max=30,
            step=1,
            value=ROBOT_DEFAULT_MAX_STEP,
            marks={1: "1", 8: "8", 15: "15", 30: "30"},
            tooltip={"placement": "bottom", "always_visible": False},
        ),
    ],
    className="mb-3",
)

status_display = html.Div(
    "Disconnected",
    id=ROBOT_STATUS_ID,
    className="small text-muted font-monospace text-center",
)

hidden_components = html.Div(
    [
        dcc.Store(id=ROBOT_STATE_STORE_ID, data={"connected": False}),
        dcc.Interval(id=ROBOT_POLL_INTERVAL_ID, interval=STATUS_POLL_MS, n_intervals=0),
    ]
)

ROBOT_LINK_WIDGETS_SECTION = dbc.Card(
    dbc.CardBody(
        [
            html.H6("ROBOT LINK", className="mb-2"),
            html.P(
                "Pick your robot, join its WiFi access point, then connect. "
                "Put the hexapod on a stand before streaming.",
                className="text-muted small mb-3",
            ),
            profile_select,
            connection_row,
            stream_row,
            max_step_slider,
            status_display,
            hidden_components,
        ]
    ),
    className="mb-3 scifi-card",
)


# ................................
# RUN ON ROBOT
#
# Commands the hardware directly, independent of whatever the simulator is
# drawing. The motion page keeps its own dropdown for on-screen playback and
# pushes its selection here, so picking a motion there still runs it here.
# ................................

motion_select = dbc.Select(
    id=ROBOT_MOTION_SELECT_ID,
    options=MOTION_TYPES,
    value="walk_0",
    className="mb-3 form-control",
)

motion_mode = dbc.RadioItems(
    id=ROBOT_MOTION_MODE_ID,
    options=[
        {"label": " Robot's own gait (recommended)", "value": "native"},
        {"label": " Stream frames from simulator", "value": "stream"},
    ],
    value="native",
    className="mb-2",
)

motion_loop = dcc.Checklist(
    id=ROBOT_MOTION_LOOP_ID,
    options=[{"label": " Loop streamed frames", "value": "loop"}],
    value=["loop"],
    className="fw-bold mb-3",
)

motion_buttons = dbc.Row(
    [
        dbc.Col(
            dbc.Button(
                "▶ Run on Robot",
                id=ROBOT_MOTION_RUN_BTN_ID,
                color="success",
                className="w-100 fw-bold",
            ),
            width=7,
        ),
        dbc.Col(
            dbc.Button(
                "■ Standby",
                id=ROBOT_MOTION_STOP_BTN_ID,
                color="secondary",
                className="w-100 fw-bold",
            ),
            width=5,
        ),
    ],
    className="g-2",
)

ROBOT_MOTION_WIDGETS_SECTION = dbc.Card(
    dbc.CardBody(
        [
            html.H6("RUN ON ROBOT", className="mb-2"),
            motion_select,
            motion_mode,
            motion_loop,
            motion_buttons,
            html.Div(
                id=ROBOT_MOTION_MESSAGE_ID,
                className="small text-muted font-monospace text-center mt-2",
            ),
        ]
    ),
    className="mb-3 scifi-card",
)
