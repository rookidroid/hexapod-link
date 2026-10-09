# Widgets for connecting to and driving the physical hexapod.
#
# Split by scope, because these controls do not all belong to the same place:
#
# * ROBOT LINK describes the robot itself -- where it is, which one answered
#   there, whether the session is up. It is mounted once in the global panel, next to the
#   dimensions, so link state survives page navigation and there is only ever
#   one connect button.
# * Streaming and RUN ON ROBOT act on what a particular page is showing, so they
#   are built per page by the factories below and live in that page's sidebar.
import dash_bootstrap_components as dbc
from dash import dcc, html

from settings import ROBOT_DEFAULT_IP, ROBOT_DEFAULT_MAX_STEP
from hexapod.robot_config import describe
from hexapod.robot_link import ROBOT_LINK
from widgets.section_maker import make_slider_field, panel_section

# --- Element IDs ---
ROBOT_INFO_ID = "robot-info"
ROBOT_FIRMWARE_ID = "robot-firmware"
ROBOT_CONFIG_STORE_ID = "robot-config-store"
ROBOT_IP_INPUT_ID = "robot-ip-input"
ROBOT_CONNECT_BTN_ID = "robot-connect-btn"
ROBOT_STATUS_ID = "robot-status"
ROBOT_STATE_STORE_ID = "robot-state-store"
ROBOT_POLL_INTERVAL_ID = "robot-poll-interval"

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
# At which address, which robot answered there, and is the session up. Nothing
# here depends on what any page is drawing.
#
# There is no robot picker: connecting reads the robot's own config, and that
# is what the simulator then models (hexapod/robot_config.py).
# ................................

robot_info = html.Div(
    describe(ROBOT_LINK.robot_config),
    id=ROBOT_INFO_ID,
    className="small fw-bold text-center mb-2",
)

# Filled in by the status poll while a robot is connected.
robot_firmware = html.Div(
    id=ROBOT_FIRMWARE_ID,
    className="small text-muted font-monospace text-center mb-2",
)

# The ind-wrap-row pieces share a line while there is room for both and stack
# when there is not; see SIDEBAR FIELDS in industrial.css.
connection_row = html.Div(
    [
        dbc.Input(
            id=ROBOT_IP_INPUT_ID,
            type="text",
            value=ROBOT_DEFAULT_IP,
            debounce=True,
            placeholder=ROBOT_DEFAULT_IP,
            className="ind-wrap-main",
        ),
        dbc.Button(
            "Connect",
            id=ROBOT_CONNECT_BTN_ID,
            color="primary",
            className="fw-bold ind-wrap-side",
        ),
    ],
    className="ind-wrap-row mb-3",
)

status_display = html.Div(
    "Disconnected",
    id=ROBOT_STATUS_ID,
    className="small text-muted font-monospace text-center",
)

hidden_components = html.Div(
    [
        dcc.Store(id=ROBOT_STATE_STORE_ID, data={"connected": False}),
        # Which robot config the simulator is on; written when a connect loads
        # one, and read by everything drawn from the robot's geometry.
        dcc.Store(
            id=ROBOT_CONFIG_STORE_ID,
            data={
                "version": ROBOT_LINK.config_version,
                "name": ROBOT_LINK.robot_config["name"],
            },
        ),
        dcc.Interval(id=ROBOT_POLL_INTERVAL_ID, interval=STATUS_POLL_MS, n_intervals=0),
    ]
)

ROBOT_LINK_WIDGETS_SECTION = dbc.Card(
    dbc.CardBody(
        [
            html.H6("Robot link", className="mb-2"),
            html.P(
                "Join the robot's WiFi access point, then connect. The robot "
                "reports its own size and gaits, and the simulator follows. "
                "Streaming and gait controls are on the pages that use them.",
                className="text-muted small mb-3",
            ),
            robot_info,
            robot_firmware,
            connection_row,
            status_display,
            hidden_components,
        ]
    ),
    className="mb-3 ind-card",
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
    stream_row = html.Div(
        [
            dbc.Switch(
                id=ids["switch"],
                label="Stream pose to robot",
                value=False,
                disabled=True,
                className="fw-bold mb-0 ind-wrap-main",
            ),
            dbc.Button(
                "Relax",
                id=ids["relax"],
                color="danger",
                disabled=True,
                className="fw-bold ind-wrap-side",
            ),
        ],
        className="ind-wrap-row mb-3",
    )

    max_step_slider = make_slider_field(
        ids["max_step"],
        "Max joint speed (ticks/cycle)",
        1,
        30,
        1,
        ROBOT_DEFAULT_MAX_STEP,
        disabled=True,
    )

    return panel_section(
        "Stream to robot",
        [
            # The heading, the blurb and the status line stay at full strength
            # while offline -- they are what explains why the rest is greyed
            # out.
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
            dcc.Interval(id=ids["interval"], interval=STATUS_POLL_MS, n_intervals=0),
        ],
        blurb="Put the hexapod on a stand before streaming.",
    )
