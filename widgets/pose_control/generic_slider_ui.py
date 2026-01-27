import dash_bootstrap_components as dbc
from dash import html
from hexapod.const import NAMES_LEG
from widgets.section_maker import make_section_type4
from widgets.pose_control.joint_widget_maker import (
    make_all_joint_widgets,
    make_slider,
)
from widgets.pose_control.components import HEADER


def make_leg_sections(jwidgets):
    widget_sections = []
    header_section = make_section_type4(
        "", html.H6("coxia"), html.H6("femur"), html.H6("tibia")
    )
    widget_sections.append(header_section)

    for leg in NAMES_LEG:
        header = dbc.Badge(leg, color="primary")
        coxia = jwidgets[leg]["coxia"]
        femur = jwidgets[leg]["femur"]
        tibia = jwidgets[leg]["tibia"]
        section = make_section_type4(header, coxia, femur, tibia)
        widget_sections.append(section)

    return dbc.Container(widget_sections, fluid=True, className="p-0")


# ................................
# COMPONENTS
# ................................

widgets = make_all_joint_widgets(joint_input_function=make_slider)
sections = make_leg_sections(widgets)
KINEMATICS_WIDGETS_SECTION = dbc.Card(
    dbc.CardBody([HEADER, sections]),
    className="mb-3",
)
