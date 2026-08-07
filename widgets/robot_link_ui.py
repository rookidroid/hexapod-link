# Widgets for connecting to and driving the physical hexapod.
import dash_bootstrap_components as dbc
from dash import dcc, html

from settings import ROBOT_DEFAULT_MAX_STEP
from hexapod.robot_profiles import DEFAULT_PROFILE, PROFILE_OPTIONS, get_profile

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
