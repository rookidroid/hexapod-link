import dash_bootstrap_components as dbc
from dash import html
from dash.dependencies import Input
from hexapod.const import NAMES_LEG, NAMES_JOINT
from hexapod.naming import joint_short_label, leg_label
from settings import ALPHA_MAX_ANGLE, BETA_MAX_ANGLE, GAMMA_MAX_ANGLE
from texts import KINEMATICS_WIDGETS_HEADER
from widgets.section_maker import make_section_type2, make_section_type3

MAX_ANGLES = {
    "coxia": ALPHA_MAX_ANGLE,
    "femur": BETA_MAX_ANGLE,
    "tibia": GAMMA_MAX_ANGLE,
}


# widget id format: "widget-<side>-<placement>-<joint>",
# e.g. "widget-left-front-coxia"
def joint_widget_id(leg_name, joint_name):
    return f"widget-{leg_name}-{joint_name}"


def make_joint_widget(leg_name, joint_name):
    max_angle = MAX_ANGLES[joint_name]
    return dbc.Input(
        id=joint_widget_id(leg_name, joint_name),
        type="number",
        value=0.0,
        min=-max_angle,
        max=max_angle,
        className="mb-2",
    )


def joint_label(joint_name):
    # Short form: these three sit in a one-third-width column each, and the
    # full "Joint 1 (coxia)" wraps to two lines there.
    return html.Small(
        joint_short_label(joint_name).upper(),
        className="d-block text-center ind-label",
    )


def make_leg_section(leg_name):
    header = html.Div(leg_label(leg_name).upper(), className="ind-leg-header mb-2")
    section = make_section_type3(
        *[make_joint_widget(leg_name, joint) for joint in NAMES_JOINT],
        *[joint_label(joint) for joint in NAMES_JOINT],
    )
    return html.Div([header, section], className="mb-2")


def make_kinematics_section():
    # Left column then right column, three rows front to back -- the same layout
    # as the robot's calibration page, so the two can be read side by side.
    lf, rf, lm, rm, lb, rb = [
        make_leg_section(name)
        for name in (
            "left-front",
            "right-front",
            "left-middle",
            "right-middle",
            "left-back",
            "right-back",
        )
    ]

    widget_sections = dbc.Container(
        [
            make_section_type2(lf, rf),
            make_section_type2(lm, rm),
            make_section_type2(lb, rb),
        ],
        fluid=True,
        className="p-0",
    )

    return dbc.Card(
        dbc.CardBody(
            [html.H6(KINEMATICS_WIDGETS_HEADER, className="mb-3"), widget_sections]
        ),
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
