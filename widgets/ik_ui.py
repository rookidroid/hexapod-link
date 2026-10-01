# Widgets used to set the inverse kinematics parameters
import dash_bootstrap_components as dbc
from dash import html
from dash.dependencies import Input
from texts import IK_WIDGETS_HEADER
from settings import (
    UPDATE_MODE,
    BODY_MAX_ANGLE,
    HIP_STANCE_MAX_ANGLE,
    LEG_STANCE_MAX_ANGLE,
    SLIDER_ANGLE_RESOLUTION,
)
from widgets.section_maker import group_header, make_slider_field


def make_translate_slider(name, slider_label):
    # Translation is a fraction of the body size along each axis (see ik_solver2).
    return make_slider_field(
        name, slider_label, -1.0, 1.0, 0.05, 0.05, updatemode=UPDATE_MODE
    )


def make_rotate_slider(name, slider_label, max_angle=BODY_MAX_ANGLE):
    return make_slider_field(
        name,
        slider_label,
        -max_angle,
        max_angle,
        SLIDER_ANGLE_RESOLUTION,
        1.5,
        updatemode=UPDATE_MODE,
    )


# ................................
# COMPONENTS
# ................................

IK_WIDGETS_IDS = [
    "widget-start-hip-stance",
    "widget-start-leg-stance",
    "widget-percent-x",
    "widget-percent-y",
    "widget-percent-z",
    "widget-rot-x",
    "widget-rot-y",
    "widget-rot-z",
]
IK_CALLBACK_INPUTS = [Input(input_id, "value") for input_id in IK_WIDGETS_IDS]

stance = [
    group_header("Starting stance"),
    make_rotate_slider(IK_WIDGETS_IDS[0], "Hip stance (°)", HIP_STANCE_MAX_ANGLE),
    make_rotate_slider(IK_WIDGETS_IDS[1], "Leg stance (°)", LEG_STANCE_MAX_ANGLE),
]

translate = [
    group_header("Translate (× body size)"),
    make_translate_slider(IK_WIDGETS_IDS[2], "X"),
    make_translate_slider(IK_WIDGETS_IDS[3], "Y"),
    make_translate_slider(IK_WIDGETS_IDS[4], "Z"),
]

rotate = [
    group_header("Rotate (°)"),
    make_rotate_slider(IK_WIDGETS_IDS[5], "X"),
    make_rotate_slider(IK_WIDGETS_IDS[6], "Y"),
    make_rotate_slider(IK_WIDGETS_IDS[7], "Z"),
]

HEADER = html.H6(IK_WIDGETS_HEADER, className="mb-3")
IK_WIDGETS_SECTION = dbc.Card(
    dbc.CardBody([HEADER, *stance, *translate, *rotate]),
    className="mb-3 ind-card",
)
