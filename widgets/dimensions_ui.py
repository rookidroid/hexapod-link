# Widgets used to set the dimensions of the hexapod: a panel folded away over
# the 3D view (pages/workspace.py), under the stream controls.
from dash import html
from dash.dependencies import Input

from hexapod.robot_config import describe, get_simulator_dimensions
from hexapod.robot_link import ROBOT_LINK
from settings import INPUT_DIMENSIONS_RESOLUTION
from widgets.components import group_header, make_field_grid, make_number_field
from widgets.robot_link_ui import ROBOT_INFO_ID


def make_number_widget(widget_id, name, value):
    return make_number_field(
        widget_id,
        name.capitalize(),
        value=value,
        min=0,
        step=INPUT_DIMENSIONS_RESOLUTION,
    )


# ................................
# COMPONENTS
# ................................

WIDGET_NAMES = ["front", "side", "middle", "coxia", "femur", "tibia"]
DIMENSION_WIDGET_IDS = [f"widget-dimension-{name}" for name in WIDGET_NAMES]
DIMENSION_CALLBACK_INPUTS = [Input(id, "value") for id in DIMENSION_WIDGET_IDS]
DIMENSIONS_HUD_ID = "dimensions-hud"

# The dimensions as one JSON string, in simulator terms
# (robot_config.get_simulator_dimensions): what everything drawn from them
# listens to. Written by update_dimensions in pages/robot.py.
DIMENSIONS_JSON_ID = "hexapod-dimensions-values"
DIMENSIONS_JSON = html.Div(id=DIMENSIONS_JSON_ID, style={"display": "none"})

# Start on the geometry of the robot last connected (or the generic model).
# `follow_robot_config` in pages/robot.py keeps these on the connected robot
# from then on.
_DEFAULT_DIMENSIONS = get_simulator_dimensions(ROBOT_LINK.robot_config)
widgets = [
    make_number_widget(widget_id, name, _DEFAULT_DIMENSIONS[name])
    for widget_id, name in zip(DIMENSION_WIDGET_IDS, WIDGET_NAMES)
]

# A native <details>, folded until wanted: the view is what it sits over.
DIMENSIONS_HUD = html.Details(
    [
        html.Summary("Dimensions"),
        # Which robot the model is: the one connected, the last one, or the
        # generic model. The measurements below start on its own.
        html.Div(
            describe(ROBOT_LINK.robot_config),
            id=ROBOT_INFO_ID,
            className="dims-robot",
        ),
        group_header("Body (mm)"),
        make_field_grid(widgets[:3], one_row=True),
        group_header("Leg (mm)"),
        make_field_grid(widgets[3:], one_row=True),
        html.Div(
            "Follow the connected robot; edit them to try another body.",
            className="dims-note",
        ),
    ],
    id=DIMENSIONS_HUD_ID,
    className="hud-panel dims-hud",
)
