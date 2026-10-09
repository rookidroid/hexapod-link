"""The workspace: the whole app below the top bar, on one screen.

    rail | tool panel |            3D view
         |            |  [angles]          [reset pose][reset view]
    -------------------------------------------------------------
    dock: what is played (keyframes or a gait), then playing it

The rail picks one tool -- Body, Feet or Robot -- and only that tool's panel
shows; the others are hidden but stay mounted, so their callbacks keep firing.
What the controls do is in pages/page_pose.py (the pose, the sequence) and
pages/shared.py (the robot link); this module only puts them in place.
"""

from dash import Input, Output, callback, html
from dash.exceptions import PreventUpdate

from hexapod.const import BASE_SCENE
from pages import page_pose  # noqa: F401  (registers the workspace's callbacks)
from pages import shared
from texts import URL_BUILD_GUIDE
from widgets.dimensions_ui import DIMENSIONS_WIDGETS_SECTION
from widgets.pose_ui import (
    ANGLES_HUD,
    BODY_PANEL,
    FEET_PANEL,
    POSE_DOCK,
    POSE_MESSAGE,
    POSE_TOOL_ID,
    POSE_TOOL_PANEL_IDS,
    POSE_VIEW_ID,
    TOOL_RAIL,
    TOOL_ROBOT,
    VIEW_OVERLAY,
)
from widgets.robot_link_ui import ROBOT_INFO_SECTION, make_stream_section
from widgets.section_maker import panel_section

# What used to be the home page's warning, next to the controls it is about.
safety_section = panel_section(
    "Before you stream",
    [
        html.Ul(
            [
                html.Li(
                    "Put the hexapod on a stand: a pose that stands up here "
                    "will not necessarily stand up on the floor."
                ),
                html.Li(
                    "Joint angles are clamped to the robot's mechanical limits "
                    "before being sent."
                ),
                html.Li(
                    "If the stream stops, the robot eases back to standby on "
                    "its own after a second."
                ),
            ],
            className="safety-list",
        ),
        html.A(
            "Build one — frames, parts and firmware on rookidroid.com ↗",
            href=URL_BUILD_GUIDE,
            target="_blank",
            className="build-link",
        ),
    ],
)

ROBOT_PANEL = html.Div(
    [
        ROBOT_INFO_SECTION,
        make_stream_section(),
        DIMENSIONS_WIDGETS_SECTION,
        safety_section,
        shared.DIMENSIONS_HIDDEN_SECTION,
    ],
    id=POSE_TOOL_PANEL_IDS[TOOL_ROBOT],
    style={"display": "none"},
)

WORKSPACE = shared.make_workspace(
    TOOL_RAIL,
    [BODY_PANEL, FEET_PANEL, ROBOT_PANEL, POSE_MESSAGE],
    # Starts on the neutral hexapod, and keeps it if the first pose cannot be
    # drawn, rather than starting as an empty screen.
    shared.make_view(POSE_VIEW_ID, BASE_SCENE, overlay=VIEW_OVERLAY, hud=ANGLES_HUD),
    POSE_DOCK,
)


@callback(
    Output(POSE_TOOL_ID, "value"),
    Input(shared.STATUS_PILL_ID, "n_clicks"),
    prevent_initial_call=True,
)
def open_robot_tool(n_clicks):
    """The status pill opens the Robot tool, where the link's detail is."""
    if not n_clicks:
        raise PreventUpdate
    return TOOL_ROBOT
