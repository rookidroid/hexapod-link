# Widgets for connecting to and driving the physical hexapod.
#
# Split by where they sit in the workspace (pages/workspace.py):
#
# * TOPBAR_CONNECTION is the address and the connect button, in the top bar,
#   so the link can be brought up from whatever tool is showing.
# * STREAM_OVERLAY switches streaming on and limits its speed, over the view.
#
# Which robot is modelled is named in the dimensions panel (ROBOT_INFO_ID,
# widgets/dimensions_ui.py), whose measurements follow it.
import dash_bootstrap_components as dbc
from dash import dcc, html

from settings import ROBOT_DEFAULT_IP, ROBOT_DEFAULT_MAX_STEP
from hexapod.robot_link import ROBOT_LINK
from widgets.section_maker import field_label

# --- Element IDs ---
ROBOT_INFO_ID = "robot-info"
ROBOT_CONFIG_STORE_ID = "robot-config-store"
ROBOT_IP_INPUT_ID = "robot-ip-input"
ROBOT_CONNECT_BTN_ID = "robot-connect-btn"
ROBOT_POLL_INTERVAL_ID = "robot-poll-interval"

# The stream section's controls.
STREAM_SWITCH_ID = "robot-stream-switch"
STREAM_MAX_STEP_ID = "robot-max-step-slider"
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
# OVER THE 3D VIEW
#
# Streaming sends the pose that is on screen, so its switch and speed limit
# sit on the view itself (pages/workspace.py), where they can be reached from
# either tool. Only the inner block is dimmed while offline, so the card
# itself stays legible over the view.
# ................................

STREAM_HUD_ID = "robot-stream-hud"

STREAM_OVERLAY = html.Div(
    html.Div(
        # Everything starts disabled because the app starts with no session;
        # the sync callback in pages/shared.py opens it up once one is
        # connected.
        [
            dbc.Switch(
                id=STREAM_SWITCH_ID,
                label="Stream to robot",
                value=False,
                disabled=True,
                className="mb-0",
            ),
            html.Div(
                [
                    field_label("Max speed"),
                    dcc.Slider(
                        id=STREAM_MAX_STEP_ID,
                        min=1,
                        max=30,
                        step=1,
                        value=ROBOT_DEFAULT_MAX_STEP,
                        marks=None,
                        disabled=True,
                        allow_direct_input=True,
                    ),
                ],
                className="ind-inline-slider",
                title="Max joint speed, in servo ticks per cycle: how fast any servo may slew",
            ),
        ],
        id=STREAM_CONTROLS_ID,
        className=SECTION_CONTROLS_OFFLINE_CLASS,
    ),
    id=STREAM_HUD_ID,
    className="hud-panel stream-hud",
    title=(
        "Sends every reachable pose to the servos as it changes. Put the "
        "hexapod on a stand first: a pose that stands up here will not "
        "necessarily stand up on the floor."
    ),
)
