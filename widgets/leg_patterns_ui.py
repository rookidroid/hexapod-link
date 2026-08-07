# Widgets used to set the leg pose of all legs uniformly
import dash_bootstrap_components as dbc
from dash import html
from dash.dependencies import Input
import dash_daq
from hexapod.naming import JOINT_ANGLE_NAMES, joint_label
from texts import PATTERNS_WIDGETS_HEADER
from settings import (
    ALPHA_MAX_ANGLE,
    BETA_MAX_ANGLE,
    GAMMA_MAX_ANGLE,
    UPDATE_MODE,
    SLIDER_ANGLE_RESOLUTION,
)
from style_settings import SLIDER_THEME, SLIDER_HANDLE_COLOR, SLIDER_COLOR


def make_slider(slider_id, name, max_angle):

    handle_style = {
        "showCurrentValue": True,
        "color": SLIDER_HANDLE_COLOR,
        "label": name,
    }

    daq_slider = dash_daq.Slider(  # pylint: disable=not-callable
        id=slider_id,
        min=-max_angle,
        max=max_angle,
        value=1.5,
        step=SLIDER_ANGLE_RESOLUTION,
        size=300,
        updatemode=UPDATE_MODE,
        handleLabel=handle_style,
        color={"default": SLIDER_COLOR},
        theme=SLIDER_THEME,
    )

    return html.Div(daq_slider, className="py-3")


# ................................
# COMPONENTS
# ................................

HEADER = html.H6(PATTERNS_WIDGETS_HEADER, className="mb-3")
# One slider per joint, applied to all six legs at once. The ids keep the
# simulator's angle names; the labels carry the firmware's joint numbers.
WIDGET_NAMES = list(JOINT_ANGLE_NAMES)
PATTERNS_WIDGET_IDS = [f"widget-{name}" for name in WIDGET_NAMES]
PATTERNS_CALLBACK_INPUTS = [Input(i, "value") for i in PATTERNS_WIDGET_IDS]

max_angles = [ALPHA_MAX_ANGLE, BETA_MAX_ANGLE, GAMMA_MAX_ANGLE]
widgets = [
    make_slider(id, joint_label(name), angle)
    for id, name, angle in zip(PATTERNS_WIDGET_IDS, WIDGET_NAMES, max_angles)
]
PATTERNS_WIDGETS_SECTION = dbc.Card(
    dbc.CardBody([HEADER] + widgets),
    className="mb-3 scifi-card",
)
