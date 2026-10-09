"""Home page: a console for the whole app rather than a brochure.

It answers the three things someone arriving here needs: what state the link to
the hexapod is in, which tool does what, and how to get a real robot moving.

There is no marketing artwork. The hero is the simulator's own render of the
hexapod, in the same 3D view the tool pages use (BASE_SCENE), so the page
shows the actual thing and keeps working with no network -- which is the normal
case here, since driving the robot means joining its access point instead of
the internet.
"""

import dash_bootstrap_components as dbc
from dash import callback, dcc, html
from dash.dependencies import Output, Input

from hexapod.const import BASE_SCENE
from hexapod.robot_link import ROBOT_LINK
from pages import shared
from texts import (
    MOTION_PAGE_PATH,
    POSE_PAGE_PATH,
    URL_BUILD_GUIDE,
)

# --- Element IDs ---
LANDING_VIEW_ID = "view-landing"
LANDING_STATUS_ID = "landing-link-status"
LANDING_STATE_ID = "landing-link-state"
LANDING_FIRMWARE_ID = "landing-link-firmware"
LANDING_OPEN_PANEL_BTN_ID = "landing-open-robot-panel"
LANDING_POLL_INTERVAL_ID = "landing-poll-interval"

STATUS_POLL_MS = 1000


# ......................
# Hero: link state on the left, the robot itself on the right
# ......................

_link_state = html.Div(
    [
        html.Div(
            [
                html.Span("Link", className="landing-status-label"),
                html.Span("OFFLINE", id=LANDING_STATE_ID, className="landing-state is-offline"),
            ],
            className="d-flex align-items-center gap-2 mb-2",
        ),
        html.Div(
            "Disconnected",
            id=LANDING_STATUS_ID,
            className="landing-status-line text-muted",
        ),
        html.Div(id=LANDING_FIRMWARE_ID, className="landing-status-line text-muted"),
        dbc.Button(
            "Open robot panel",
            id=LANDING_OPEN_PANEL_BTN_ID,
            color="primary",
            className="fw-bold mt-3",
        ),
        dcc.Interval(
            id=LANDING_POLL_INTERVAL_ID, interval=STATUS_POLL_MS, n_intervals=0
        ),
    ],
    className="landing-link-panel",
)

# The wheel stays with the page: a view this size in a scrolling page would
# otherwise swallow every scroll.
shared.register_view(LANDING_VIEW_ID, zoom=False)

hero = dbc.Row(
    [
        dbc.Col(
            html.Div(
                [
                    html.H1("HEXAPOD LINK", className="ind-hero-title"),
                    html.Div(className="ind-hero-hr"),
                    html.P(
                        "Pose a hexapod in 3D and, when one is connected, drive "
                        "the real machine with the same controls — from a "
                        "single joint up to a whole gait.",
                        className="landing-lede",
                    ),
                    _link_state,
                ],
                className="glass-panel-light p-4 h-100",
            ),
            width=12,
            lg=6,
            className="mb-3 mb-lg-0",
        ),
        dbc.Col(
            html.Div(
                shared.make_view(LANDING_VIEW_ID, BASE_SCENE),
                className="graph-container landing-stage",
            ),
            width=12,
            lg=6,
        ),
    ],
    className="g-3 align-items-stretch",
)


# ......................
# Tools
#
# Each card says what the page does on screen and what it does to the hardware,
# because those are different questions and the second one is easy to get
# wrong: the pose page streams as you pose, and the motion page commands the
# robot's own gait.
# ......................


def _tool(index, title, desc, hardware, href, on_hardware=True):
    return dbc.Col(
        html.A(
            html.Div(
                [
                    html.Div(f"{index:02d}", className="tool-index"),
                    html.Div(title, className="tool-title"),
                    html.Div(desc, className="tool-desc"),
                    html.Div(
                        hardware,
                        className="tool-hardware"
                        + ("" if on_hardware else " is-sim-only"),
                    ),
                ],
                className="tool-card",
            ),
            href=href,
            className="tool-link",
        ),
        width=12,
        md=6,
        # Equal shares of one row on a wide screen, however many cards there are.
        xl=True,
        className="mb-3",
    )


tools = html.Div(
    [
        html.H5("Control surfaces", className="landing-section-title"),
        dbc.Row(
            [
                _tool(
                    1,
                    "Pose",
                    "Tilt and shift the body, move the feet, then string the "
                    "poses into a timed sequence.",
                    "Streams each reachable pose; the sequence on Run",
                    POSE_PAGE_PATH,
                ),
                _tool(
                    2,
                    "Motion",
                    "Play the generated gaits frame by frame and scrub them.",
                    "Runs the robot's own gait from flash",
                    MOTION_PAGE_PATH,
                ),
            ],
            className="g-3",
        ),
    ],
    className="mt-4",
)


# ......................
# Getting a real robot moving
# ......................


build_link = html.A(
    html.Div(
        [
            html.Div(
                [
                    html.Div("Build one", className="build-title"),
                    html.Div(
                        "Frames, parts, firmware and the story of how the "
                        "hexapod got here — every revision, on rookidroid.com.",
                        className="build-desc",
                    ),
                ]
            ),
            html.Div("rookidroid.com ↗", className="build-cue"),
        ],
        className="build-card",
    ),
    href=URL_BUILD_GUIDE,
    target="_blank",
    className="build-link",
)


hardware = html.Div(
    [
        html.H5("Driving a real hexapod", className="landing-section-title"),
        build_link,
        html.Div(
            [
                html.Div("⚠ Before you stream", className="safety-title"),
                html.Ul(
                    [
                        html.Li(
                            "Put the hexapod on a stand. A pose that stands up "
                            "in the simulator will not necessarily stand up on "
                            "the floor."
                        ),
                        html.Li(
                            "Joint angles are clamped to the robot's "
                            "mechanical limits before being sent — the "
                            "simulator allows far more travel than the servos "
                            "have."
                        ),
                        html.Li(
                            "If the stream stops, the robot eases back to "
                            "standby on its own after a second."
                        ),
                    ],
                    className="safety-list",
                ),
            ],
            className="safety-callout",
        ),
    ],
    className="mt-4",
)


layout = shared.make_scrollable_page(
    dbc.Container([hero, tools, hardware], fluid=True, className="landing pb-4")
)


# ......................
# Callbacks
# ......................

shared.register_open_panel_button(LANDING_OPEN_PANEL_BTN_ID)


@callback(
    Output(LANDING_STATUS_ID, "children"),
    Output(LANDING_STATUS_ID, "className"),
    Output(LANDING_STATE_ID, "children"),
    Output(LANDING_STATE_ID, "className"),
    Output(LANDING_FIRMWARE_ID, "children"),
    Input(LANDING_POLL_INTERVAL_ID, "n_intervals"),
)
def update_landing_status(_n_intervals):
    """Same readout as the drawer, on its own interval.

    Its own rather than the global one because this page is unmounted whenever
    the user is anywhere else, and a callback cannot write to an output that is
    not on the current page.
    """
    status = ROBOT_LINK.status()
    text, colour_class = shared.link_status_text(status)

    if status["last_error"]:
        state, modifier = "FAULT", "is-fault"
    elif not status["connected"]:
        state, modifier = "OFFLINE", "is-offline"
    elif status["streaming"]:
        state, modifier = "STREAMING", "is-streaming"
    else:
        state, modifier = "ONLINE", "is-online"

    return (
        text,
        "landing-status-line " + colour_class,
        state,
        "landing-state " + modifier,
        shared.firmware_status_text(status),
    )
