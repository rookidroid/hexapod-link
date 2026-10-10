from copy import deepcopy
from dash import html
from hexapod.const import (
    BASE_POSE,
    NAMES_LEG,
)
from hexapod.naming import leg_label

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


def make_reach_warning(bad_legs):
    """Says which legs (ids) cannot be posed: their foot is out of reach or a
    joint is past its limit, so their angles mean nothing. Nothing for none."""
    if not bad_legs:
        return None
    labels = ", ".join(leg_label(leg) for leg in bad_legs)
    return html.Div(f"⚠ Out of reach or past a joint limit: {labels}", className="ind-alert")


def make_alert_message(alert, class_name="mb-3"):
    return html.Div(f"⚠ {alert}", className=f"ind-alert {class_name}".strip())
