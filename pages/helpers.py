from copy import deepcopy
import dash_bootstrap_components as dbc
from dash import html
from hexapod.const import (
    BASE_POSE,
    NAMES_LEG,
)
from hexapod.naming import JOINT_NAMES, joint_label, joint_number, leg_label
from widgets.section_maker import LEG_SIDES, short_leg_label

NEW_POSES = deepcopy(BASE_POSE)


def make_pose(alpha, beta, gamma, poses=NEW_POSES):

    for k in poses.keys():
        poses[k] = {
            "id": k,
            "name": NAMES_LEG[k],
            "coxia": alpha,
            "femur": beta,
            "tibia": gamma,
        }
    return poses


def make_angle_strip(poses, bad_legs=(), legs_off_ground=()):
    """The pose's joint angles in one compact table: a row per joint, a column
    per leg, left legs then right.

    Legs and joints are named the way the robot firmware names them, so a
    value can be read straight onto the robot's calibration page. `bad_legs`
    (ids) are marked: their foot is out of reach or a joint is past its limit,
    so their angles mean nothing.
    """
    by_name = {pose["name"]: pose for pose in poses.values()}
    bad_names = {NAMES_LEG[leg] for leg in bad_legs}
    columns = [name for _, legs in LEG_SIDES for name in legs]

    def cell(leg_name, joint):
        bad = leg_name in bad_names
        text = "—" if bad else f"{by_name[leg_name][joint]:+.2f}"
        return html.Td(
            html.Div(text, className="ind-readout is-bad" if bad else "ind-readout")
        )

    header = html.Tr(
        [html.Th("")]
        + [html.Th(short_leg_label(name), className="text-center") for name in columns]
    )
    # "J1", with the joint's name as a tooltip: the dock is short of width.
    rows = [
        html.Tr(
            [html.Th(html.Span(f"J{joint_number(joint)}", title=joint_label(joint)))]
            + [cell(name, joint) for name in columns]
        )
        for joint in JOINT_NAMES
    ]
    body = [
        dbc.Table(
            [html.Thead(header), html.Tbody(rows)],
            borderless=True,
            size="sm",
            className="ind-joint-grid ind-angle-strip mb-0",
        )
    ]

    if bad_legs:
        labels = ", ".join(leg_label(leg) for leg in bad_legs)
        body.append(
            html.Div(f"⚠ Out of reach or past a joint limit: {labels}", className="ind-alert mt-2")
        )
    # The pose is reachable, but these legs came up short of the ground point
    # they were aimed at and are stretched straight out in the air instead.
    # Worth saying, otherwise the robot just looks wrong for no stated reason.
    if legs_off_ground:
        labels = ", ".join(leg_label(leg) for leg in legs_off_ground)
        body.append(
            html.Div(f"⚠ Not reaching the ground: {labels}", className="ind-alert mt-2")
        )
    return html.Div(body)


def make_alert_message(alert):
    return html.Div(f"⚠ {alert}", className="ind-alert mb-3")
