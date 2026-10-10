# Widgets for connecting to and driving the physical hexapod.
#
# Split by where they sit in the workspace (pages/workspace.py):
#
# * TOPBAR_CONNECTION is the address and the connect button, in the top bar,
#   and STATUS_PILL beside it the link's readout.
# * STREAM_OVERLAY switches streaming on and limits its speed, over the view.
# * DRIVE_HUD is the controller over the view: hold a pad and the robot plays
#   that one of its own gaits.
#
# Which robot is modelled is named in the dimensions panel (ROBOT_INFO_ID,
# widgets/dimensions_ui.py), whose measurements follow it.
import json

import dash_bootstrap_components as dbc
from dash import dcc, html

from settings import ROBOT_DEFAULT_IP, ROBOT_DEFAULT_MAX_STEP
from hexapod.robot_link import ROBOT_LINK
from widgets.components import field_label

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

# The status pill is the app's link readout: whether the robot is reachable,
# which one it is, and whether it is being streamed to. The state modifier
# colours its LED (STATUS PILL in industrial.css); its tooltip has the detail.
STATUS_PILL_ID = "status-pill"


def status_pill_class(state):
    return f"status-pill {state}"


STATUS_PILL = html.Div(
    "Offline",
    id=STATUS_PILL_ID,
    className=status_pill_class("is-offline"),
    title="Disconnected",
    role="status",
)


# ................................
# OVER THE 3D VIEW
#
# Streaming sends the pose that is on screen, so its switch and speed limit
# sit on the view itself (pages/workspace.py). Only the inner block is dimmed
# while offline, so the card itself stays legible over the view.
# ................................

STREAM_HUD_ID = "robot-stream-hud"

STREAM_OVERLAY = html.Div(
    html.Div(
        # Everything starts disabled because the app starts with no session;
        # the sync callback in pages/robot.py opens it up once one is
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


# ................................
# CONTROLLER
#
# Over the view's bottom-right corner, the controls of the Android app's
# control screen: hold a pad and the robot plays that one of its own gaits
# from flash, let go and it stands. The pads are drawn, and held, by
# assets/drive_pads.js, from the layout below; it talks to the robot through
# the route in pages/drive.py.
# ................................

DRIVE_HUD_ID = "drive-hud"
DRIVE_CONTROLS_ID = "drive-controls"
DRIVE_SPEED_ID = "drive-speed"
# Read by assets/drive_pads.js; keep the two in step.
DRIVE_READOUT_ID = "drive-readout"
DRIVE_BODY_CLASS = "drive-body"

# The move pad: standby in the middle, around it a ring of eight walks
# (clockwise from forward), and outside that fast forward, the turns and fast
# backward.
DRIVE_MOVE_PAD = {
    "centre": "standby",
    "walk": [
        "walk_0",
        "walk_r45",
        "walk_r90",
        "walk_r135",
        "walk_180",
        "walk_l135",
        "walk_l90",
        "walk_l45",
    ],
    "outer": ["fast_forward", "turn_right", "fast_backward", "turn_left"],
}

# The body pad: moves on the spot, in rows of two as on the Android app, each
# with the short name it is labelled with.
DRIVE_BODY_PAD = [
    [["rotate_y", "Roll"], ["climb_forward", "Climb"]],
    [["rotate_x", "Pitch"], ["twist", "Twist"]],
    [["rotate_z", "Wobble"], ["climb_backward", "Climb"]],
]

# What each one is called in its tooltip, and in the readout while it is held.
DRIVE_LABELS = {
    "standby": "Standby",
    "walk_0": "Walk forward",
    "walk_180": "Walk backward",
    "walk_r45": "Walk right 45°",
    "walk_r90": "Walk right 90°",
    "walk_r135": "Walk right 135°",
    "walk_l45": "Walk left 45°",
    "walk_l90": "Walk left 90°",
    "walk_l135": "Walk left 135°",
    "fast_forward": "Fast forward",
    "fast_backward": "Fast backward",
    "turn_left": "Turn left",
    "turn_right": "Turn right",
    "climb_forward": "Climb forward",
    "climb_backward": "Climb backward",
    "rotate_x": "Rotate X (pitch)",
    "rotate_y": "Rotate Y (roll)",
    "rotate_z": "Rotate Z (wobble)",
    "twist": "Twist (figure-8)",
}

DRIVE_LAYOUT = {"move": DRIVE_MOVE_PAD, "body": DRIVE_BODY_PAD, "labels": DRIVE_LABELS}

# Gait speed, as a percent of the robot's tuned frame rate: the link's, set by
# set_drive_speed and kept on the link by sync_robot_controls in
# pages/pose.py.
_speed = ROBOT_LINK.robot_config["speed"]

# A native <details>, so it folds away without a callback; folded until
# wanted, or served as it was left (pages/workspace.py).
DRIVE_HUD = html.Details(
    [
        html.Summary(
            "Controller",
            title=(
                "Runs the robot's own gaits, played from its flash, for as "
                "long as a pad is held."
            ),
        ),
        html.Div(
            [
                html.Div(className="drive-pad drive-pad-body", **{"data-pad": "body"}),
                html.Div(className="drive-pad drive-pad-move", **{"data-pad": "move"}),
                html.Div(
                    [
                        html.Div(
                            "Hold a pad to move", id=DRIVE_READOUT_ID, className="drive-readout"
                        ),
                        html.Div(
                            [
                                field_label("Speed (%)"),
                                dcc.Slider(
                                    id=DRIVE_SPEED_ID,
                                    min=_speed["min"],
                                    max=_speed["max"],
                                    step=5,
                                    value=ROBOT_LINK.speed_pct,
                                    marks=None,
                                    allow_direct_input=True,
                                ),
                            ],
                            className="ind-inline-slider drive-speed",
                            title="How fast the robot plays its gaits, of its tuned rate",
                        ),
                    ],
                    className="drive-footer",
                ),
            ],
            id=DRIVE_CONTROLS_ID,
            # Dimmed and inert until a robot is connected (sync_robot_controls
            # in pages/pose.py).
            className=f"{DRIVE_BODY_CLASS} {SECTION_CONTROLS_OFFLINE_CLASS}",
            **{"data-layout": json.dumps(DRIVE_LAYOUT)},
        ),
    ],
    id=DRIVE_HUD_ID,
    className="hud-panel drive-hud",
)
