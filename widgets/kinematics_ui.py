import dash_bootstrap_components as dbc
from dash import html
from dash.dependencies import Input
from hexapod.const import NAMES_LEG, NAMES_JOINT
from settings import ALPHA_MAX_ANGLE, BETA_MAX_ANGLE, GAMMA_MAX_ANGLE
from texts import KINEMATICS_WIDGETS_HEADER
from widgets.section_maker import make_leg_sides

MAX_ANGLES = {
    "coxia": ALPHA_MAX_ANGLE,
    "femur": BETA_MAX_ANGLE,
    "tibia": GAMMA_MAX_ANGLE,
}



# widget id format: "widget-<side>-<placement>-<joint>",
# e.g. "widget-left-front-coxia"
def joint_widget_id(leg_name, joint_name):
    return f"widget-{leg_name}-{joint_name}"


def make_joint_widget(leg_name, joint_index):
    joint_name = NAMES_JOINT[joint_index]
    max_angle = MAX_ANGLES[joint_name]
    return dbc.Input(
        id=joint_widget_id(leg_name, joint_name),
        type="number",
        value=0.0,
        min=-max_angle,
        max=max_angle,
        size="sm",
    )


def make_kinematics_section():
    sides = make_leg_sides(make_joint_widget)

    return dbc.Card(
        dbc.CardBody([html.H6(KINEMATICS_WIDGETS_HEADER, className="mb-3"), sides]),
        className="mb-3 ind-card",
    )


# ................................
# COMPONENTS
# ................................

KINEMATICS_WIDGETS_SECTION = make_kinematics_section()
KINEMATICS_CALLBACK_INPUTS = [
    Input(joint_widget_id(leg_name, joint_name), "value")
    for leg_name in NAMES_LEG
    for joint_name in NAMES_JOINT
]
