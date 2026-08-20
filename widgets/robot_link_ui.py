# Widgets for connecting to and driving the physical hexapod.
#
# Split by scope, because these controls do not all belong to the same place:
#
# * ROBOT LINK describes the robot itself -- which one, where it is, whether the
#   session is up. It is mounted once in the global panel, next to the
#   dimensions, so link state survives page navigation and there is only ever
#   one connect button.
# * Streaming and RUN ON ROBOT act on what a particular page is showing, so they
#   are built per page by the factories below and live in that page's sidebar.
import dash_bootstrap_components as dbc
from dash import dcc, html

from settings import ROBOT_DEFAULT_MAX_STEP
from hexapod.robot_profiles import DEFAULT_PROFILE, PROFILE_OPTIONS, get_profile

# --- Element IDs ---
ROBOT_PROFILE_SELECT_ID = "robot-profile-select"
ROBOT_IP_INPUT_ID = "robot-ip-input"
ROBOT_CONNECT_BTN_ID = "robot-connect-btn"
ROBOT_STATUS_ID = "robot-status"
ROBOT_STATE_STORE_ID = "robot-state-store"
ROBOT_POLL_INTERVAL_ID = "robot-poll-interval"

ROBOT_MOTION_MODE_ID = "robot-motion-mode"
ROBOT_MOTION_LOOP_ID = "robot-motion-loop"
ROBOT_MOTION_RUN_BTN_ID = "robot-motion-run-btn"
ROBOT_MOTION_STOP_BTN_ID = "robot-motion-stop-btn"
ROBOT_MOTION_MESSAGE_ID = "robot-motion-message"

ROBOT_MOTION_CONTROLS_ID = "robot-motion-controls"
ROBOT_MOTION_POLL_INTERVAL_ID = "robot-motion-poll-interval"

# Poll the link often enough that the status badge feels live, but not so often
# that it adds noticeable callback traffic.
STATUS_POLL_MS = 1000

# Nothing in these sections can do anything without an open session, so while
# the robot is offline they are dimmed and made inert. The controls keep their
# own `disabled` flags as well -- the class is what a person reads, `disabled`
# is what the widget honours.
SECTION_CONTROLS_CLASS = "robot-section-controls"
SECTION_CONTROLS_OFFLINE_CLASS = "robot-section-controls is-offline"


# ................................
# ROBOT LINK (global panel)
#
# Which robot, at which address, and is the session up. Nothing here depends on
# what any page is drawing.
# ................................

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
                "Streaming and gait controls are on the pages that use them.",
                className="text-muted small mb-3",
            ),
            profile_select,
            connection_row,
            status_display,
            hidden_components,
        ]
    ),
    className="mb-3 scifi-card",
)


# ................................
# STREAM TO ROBOT (per page)
#
# Sending the pose only means something where a pose is being solved, so this is
# built into the sidebar of each such page rather than the global panel. Every
# instance drives the same single link, so the ids are page-scoped and the
# widgets are re-seeded from the link's own state by the sync callback in
# pages/shared.py -- otherwise a switch left on when leaving one page would
# render off on the next while the robot was still being driven.
# ................................


def make_stream_control_ids(page_key):
    return {
        "switch": f"robot-stream-switch-{page_key}",
        "max_step": f"robot-max-step-slider-{page_key}",
        "relax": f"robot-relax-btn-{page_key}",
        "controls": f"robot-stream-controls-{page_key}",
        "status": f"robot-stream-status-{page_key}",
        "interval": f"robot-stream-sync-{page_key}",
    }


def make_stream_controls_section(ids):
    # Everything starts disabled because the app starts with no session; the
    # sync callback in pages/shared.py opens them up once one is connected.
    stream_row = dbc.Row(
        [
            dbc.Col(
                dbc.Switch(
                    id=ids["switch"],
                    label="Stream pose to robot",
                    value=False,
                    disabled=True,
                    className="fw-bold mb-0",
                ),
                width=7,
            ),
            dbc.Col(
                dbc.Button(
                    "RELAX",
                    id=ids["relax"],
                    color="danger",
                    disabled=True,
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
                id=ids["max_step"],
                min=1,
                max=30,
                step=1,
                value=ROBOT_DEFAULT_MAX_STEP,
                disabled=True,
                marks={1: "1", 8: "8", 15: "15", 30: "30"},
                tooltip={"placement": "bottom", "always_visible": False},
            ),
        ],
        className="mb-3",
    )

    return dbc.Card(
        dbc.CardBody(
            [
                html.H6("STREAM TO ROBOT", className="mb-2"),
                html.P(
                    "Put the hexapod on a stand before streaming.",
                    className="text-muted small mb-3",
                ),
                # The heading, the blurb and the status line stay at full
                # strength while offline -- they are what explains why the rest
                # is greyed out.
                html.Div(
                    [stream_row, max_step_slider],
                    id=ids["controls"],
                    className=SECTION_CONTROLS_OFFLINE_CLASS,
                ),
                html.Div(
                    "Disconnected",
                    id=ids["status"],
                    className="small text-muted font-monospace text-center",
                ),
                dcc.Interval(
                    id=ids["interval"], interval=STATUS_POLL_MS, n_intervals=0
                ),
            ]
        ),
        className="mb-3 scifi-card",
    )


# ................................
# RUN ON ROBOT (motion page)
#
# Commands the hardware to play a whole gait, which only the motion page has a
# motion to name -- it supplies the selection from its own dropdown, so there is
# no second motion list to keep in step with the one being previewed.
# ................................

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
                disabled=True,
                className="w-100 fw-bold",
            ),
            width=7,
        ),
        dbc.Col(
            dbc.Button(
                "■ Standby",
                id=ROBOT_MOTION_STOP_BTN_ID,
                color="secondary",
                disabled=True,
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
            html.P(
                "Runs the motion selected above on the hardware.",
                className="text-muted small mb-3",
            ),
            html.Div(
                [motion_mode, motion_loop, motion_buttons],
                id=ROBOT_MOTION_CONTROLS_ID,
                className=SECTION_CONTROLS_OFFLINE_CLASS,
            ),
            html.Div(
                "Connect a robot to run this on the hardware.",
                id=ROBOT_MOTION_MESSAGE_ID,
                className="small text-muted font-monospace text-center mt-2",
            ),
            # Its own interval rather than the global one: this section is
            # mounted with the motion page, and a callback whose output is not
            # on the current page has nothing to write to.
            dcc.Interval(
                id=ROBOT_MOTION_POLL_INTERVAL_ID,
                interval=STATUS_POLL_MS,
                n_intervals=0,
            ),
        ]
    ),
    className="mb-3 scifi-card",
)
