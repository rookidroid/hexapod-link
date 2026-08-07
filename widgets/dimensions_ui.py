# Widgets used to set the dimensions of the hexapod
import dash_bootstrap_components as dbc
from dash import html
from dash.dependencies import Input
from texts import DIMENSIONS_WIDGETS_HEADER
from settings import INPUT_DIMENSIONS_RESOLUTION
from hexapod.robot_profiles import DEFAULT_PROFILE, get_simulator_dimensions
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

# Start on the default robot's real geometry rather than a neutral 100 each.
# `select_robot_profile` already resets these whenever the profile changes, on
# the grounds that mismatched dimensions make the on-screen hexapod disagree with
# the hardware; that argument applies just as much to the first render, which
# that callback never sees because it is prevent_initial_call.
_DEFAULT_DIMENSIONS = get_simulator_dimensions(DEFAULT_PROFILE)
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
