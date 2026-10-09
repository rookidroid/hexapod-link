# Widgets used to set the dimensions of the hexapod: a block of the Robot
# tool panel (pages/workspace.py).
from dash.dependencies import Input
from texts import DIMENSIONS_WIDGETS_HEADER
from settings import INPUT_DIMENSIONS_RESOLUTION
from hexapod.robot_config import get_simulator_dimensions
from hexapod.robot_link import ROBOT_LINK
from widgets.section_maker import (
    group_header,
    make_field_grid,
    make_number_field,
    panel_section,
)


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

# Start on the geometry of the robot last connected (or the generic model).
# `follow_robot_config` in pages/shared.py keeps these on the connected robot
# from then on.
_DEFAULT_DIMENSIONS = get_simulator_dimensions(ROBOT_LINK.robot_config)
widgets = [
    make_number_widget(widget_id, name, _DEFAULT_DIMENSIONS[name])
    for widget_id, name in zip(DIMENSION_WIDGET_IDS, WIDGET_NAMES)
]
sections = [
    group_header("Body"),
    make_field_grid(widgets[:3]),
    group_header("Leg"),
    make_field_grid(widgets[3:]),
]

DIMENSIONS_WIDGETS_SECTION = panel_section(
    DIMENSIONS_WIDGETS_HEADER,
    sections,
    blurb=(
        "Follow the connected robot; edit them to try another body. Poses "
        "keep their meaning on the resized body."
    ),
)
