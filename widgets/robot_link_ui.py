# Widgets for connecting to and driving the physical hexapod.
#
# Split by where they sit in the workspace (pages/workspace.py):
#
# * TOPBAR_CONNECTION is the address and the connect button, in the top bar,
#   so the link can be brought up from whatever tool is showing.
# * ROBOT_INFO_SECTION and the stream section describe the robot and what is
#   being sent to it; they are the first two blocks of the Robot tool panel.
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
ROBOT_POLL_INTERVAL_ID = "robot-poll-interval"

# The stream section's controls.
STREAM_SWITCH_ID = "robot-stream-switch"
STREAM_MAX_STEP_ID = "robot-max-step-slider"
STREAM_RELAX_BTN_ID = "robot-relax-btn"
STREAM_CONTROLS_ID = "robot-stream-controls"

# Poll the link often enough that the status pill feels live, but not so often
# that it adds noticeable callback traffic. Every readout of the link's state
# runs off this one interval.
STATUS_POLL_MS = 1000

# Nothing in these sections can do anything without an open session, so while
# the robot is offline they are dimmed and made inert. The controls keep their
# own `disabled` flags as well -- the class is what a person reads, `disabled`
# is what the widget honours.
SECTION_CONTROLS_CLASS = "robot-section-controls"
SECTION_CONTROLS_OFFLINE_CLASS = "robot-section-controls is-offline"


# ................................
# TOP BAR
#
# There is no robot picker: connecting reads the robot's own config, and that
# is what the simulator then models (hexapod/robot_config.py).
# ................................

TOPBAR_CONNECTION = html.Div(
    [
        dbc.Input(
            id=ROBOT_IP_INPUT_ID,
            type="text",
            value=ROBOT_DEFAULT_IP,
            debounce=True,
            placeholder=ROBOT_DEFAULT_IP,
            size="sm",
            className="topbar-ip",
        ),
        dbc.Button(
            "Connect",
            id=ROBOT_CONNECT_BTN_ID,
            color="primary",
            size="sm",
        ),
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
    ],
    className="topbar-connection",
)


# ................................
# ROBOT PANEL
# ................................

ROBOT_INFO_SECTION = panel_section(
    "Robot",
    [
        html.Div(
            describe(ROBOT_LINK.robot_config),
            id=ROBOT_INFO_ID,
            className="robot-info",
        ),
        # Filled in by the status poll while a robot is connected.
        html.Div(id=ROBOT_FIRMWARE_ID, className="robot-detail"),
        html.Div("Disconnected", id=ROBOT_STATUS_ID, className="robot-detail text-muted"),
    ],
    blurb=(
        "Join the robot's WiFi access point, then connect from the top bar. "
        "The robot reports its own size and gaits, and the model follows."
    ),
)


def make_stream_section():
    # Everything starts disabled because the app starts with no session; the
    # sync callback in pages/shared.py opens it up once one is connected.
    stream_row = html.Div(
        [
            dbc.Switch(
                id=STREAM_SWITCH_ID,
                label="Stream pose to robot",
                value=False,
                disabled=True,
                className="mb-0 ind-wrap-main",
            ),
            dbc.Button(
                "Relax",
                id=STREAM_RELAX_BTN_ID,
                color="danger",
                outline=True,
                size="sm",
                disabled=True,
                className="ind-wrap-side",
                title="Cut drive to the servos so the legs go limp",
            ),
        ],
        className="ind-wrap-row mb-3",
    )

    max_step_slider = make_slider_field(
        STREAM_MAX_STEP_ID,
        "Max joint speed (ticks/cycle)",
        1,
        30,
        1,
        ROBOT_DEFAULT_MAX_STEP,
        disabled=True,
    )

    return panel_section(
        "Stream",
        html.Div(
            [stream_row, max_step_slider],
            id=STREAM_CONTROLS_ID,
            className=SECTION_CONTROLS_OFFLINE_CLASS,
        ),
        blurb="Sends every reachable pose to the servos as it changes.",
    )
