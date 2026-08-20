"""Home page: a console for the whole app rather than a brochure.

It answers the three things someone arriving here needs: what state the link to
the hexapod is in, which tool does what, and how to get a real robot moving.

There is no marketing artwork. The hero is the simulator's own render of the
hexapod, drawn from the same BASE_FIGURE the tool pages start from, so the page
shows the actual thing and keeps working with no network -- which is the normal
case here, since driving the robot means joining its access point instead of
the internet.
"""

from copy import deepcopy

import dash_bootstrap_components as dbc
from dash import dcc, html
from dash.dependencies import Output, Input

from app import app
from hexapod.const import BASE_FIGURE
from hexapod.robot_link import ROBOT_LINK
from pages import shared
from texts import (
    KINEMATICS_PAGE_PATH,
    IK_PAGE_PATH,
    PATTERNS_PAGE_PATH,
    MOTION_PAGE_PATH,
    URL_BUILD_GUIDE,
)

# --- Element IDs ---
LANDING_GRAPH_ID = "landing-graph"
LANDING_STATUS_ID = "landing-link-status"
LANDING_STATE_ID = "landing-link-state"
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
                html.Span("LINK", className="landing-status-label"),
                html.Span("OFFLINE", id=LANDING_STATE_ID, className="landing-state is-offline"),
            ],
            className="d-flex align-items-center gap-2 mb-2",
        ),
        html.Div(
            "Disconnected",
            id=LANDING_STATUS_ID,
            className="landing-status-line text-muted",
        ),
        dbc.Button(
            "OPEN ROBOT PANEL",
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

hero = dbc.Row(
    [
        dbc.Col(
            html.Div(
                [
                    html.H1("HEXAPOD LINK", className="scifi-hero-title"),
                    html.Div(className="scifi-hero-hr"),
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
                dcc.Graph(
                    id=LANDING_GRAPH_ID,
                    # A copy: BASE_FIGURE is shared with the tool pages, and
                    # this one is never written back to.
                    figure=deepcopy(BASE_FIGURE),
                    responsive=True,
                    # No modebar, and the wheel stays with the page -- a plot
                    # this size would otherwise swallow every scroll.
                    config={"displayModeBar": False, "scrollZoom": False},
                    style={"height": "100%", "width": "100%"},
                ),
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
# wrong: two of these stream continuously, one commands the robot's own gait,
# and one never touches it.
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
        xl=3,
        className="mb-3",
    )


tools = html.Div(
    [
        html.H5("CONTROL SURFACES", className="landing-section-title"),
        dbc.Row(
            [
                _tool(
                    1,
                    "Kinematics",
                    "Set all 18 joint angles by hand and watch the body follow.",
                    "Streams every pose to the servos",
                    KINEMATICS_PAGE_PATH,
                ),
                _tool(
                    2,
                    "Inverse Kinematics",
                    "Translate and rotate the body; the solver finds the joints.",
                    "Streams once the pose is reachable",
                    IK_PAGE_PATH,
                ),
                _tool(
                    3,
                    "Leg Patterns",
                    "Sweep all six legs together through one set of angles.",
                    "Simulator only",
                    PATTERNS_PAGE_PATH,
                    on_hardware=False,
                ),
                _tool(
                    4,
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
                    html.Div("BUILD ONE", className="build-title"),
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
        html.H5("DRIVING A REAL HEXAPOD", className="landing-section-title"),
        build_link,
        html.Div(
            [
                html.Div("⚠ BEFORE YOU STREAM", className="safety-title"),
                html.Ul(
                    [
                        html.Li(
                            "Put the hexapod on a stand. A pose that stands up "
                            "in the simulator will not necessarily stand up on "
                            "the floor."
                        ),
                        html.Li(
                            "Joint angles are clamped to each profile's "
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


@app.callback(
    Output(LANDING_STATUS_ID, "children"),
    Output(LANDING_STATUS_ID, "className"),
    Output(LANDING_STATE_ID, "children"),
    Output(LANDING_STATE_ID, "className"),
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
    )
