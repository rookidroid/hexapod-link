# Widgets used to set the dimensions of the hexapod
import dash_bootstrap_components as dbc
from dash import html
from dash.dependencies import Input
from texts import DIMENSIONS_WIDGETS_HEADER
from settings import INPUT_DIMENSIONS_RESOLUTION
from hexapod.robot_config import get_simulator_dimensions
from hexapod.robot_link import ROBOT_LINK
from widgets.section_maker import make_section_type3


def make_number_widget(_name, _value):
    return dbc.Input(
        id=_name,
        type="number",
        value=_value,
        min=0,
        step=INPUT_DIMENSIONS_RESOLUTION,
        className="mb-2",
    )


def _code(name):
    return html.Small(
        name.upper(),
        className="d-block text-center scifi-label",
    )


# ................................
# COMPONENTS
# ................................

HEADER = html.H6(DIMENSIONS_WIDGETS_HEADER, className="mb-3")
WIDGET_NAMES = ["front", "side", "middle", "coxia", "femur", "tibia"]
DIMENSION_WIDGET_IDS = [f"widget-dimension-{name}" for name in WIDGET_NAMES]
DIMENSION_CALLBACK_INPUTS = [Input(id, "value") for id in DIMENSION_WIDGET_IDS]

# Start on the geometry of the robot last connected (or the generic model).
# `follow_robot_config` in pages/shared.py keeps these on the connected robot
# from then on.
_DEFAULT_DIMENSIONS = get_simulator_dimensions(ROBOT_LINK.robot_config)
widgets = [
    make_number_widget(widget_id, _DEFAULT_DIMENSIONS[name])
    for widget_id, name in zip(DIMENSION_WIDGET_IDS, WIDGET_NAMES)
]
sections = dbc.Container(
    [
        make_section_type3(
            widgets[0],
            widgets[1],
            widgets[2],
            _code(WIDGET_NAMES[0]),
            _code(WIDGET_NAMES[1]),
            _code(WIDGET_NAMES[2]),
        ),
        make_section_type3(
            widgets[3],
            widgets[4],
            widgets[5],
            _code(WIDGET_NAMES[3]),
            _code(WIDGET_NAMES[4]),
            _code(WIDGET_NAMES[5]),
        ),
    ],
    fluid=True,
    className="p-0",
)

DIMENSIONS_WIDGETS_SECTION = dbc.Card(
    dbc.CardBody([HEADER, sections]),
    className="mb-3 scifi-card",
)
