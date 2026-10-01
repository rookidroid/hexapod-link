from copy import deepcopy
import json
import dash_bootstrap_components as dbc
from dash import html
from hexapod.const import (
    BASE_PLOTTER,
    BASE_POSE,
    BASE_IK_PARAMS,
    BASE_DIMENSIONS,
    NAMES_JOINT,
    NAMES_LEG,
)
from hexapod.naming import leg_label
from widgets.section_maker import make_leg_sides

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


def change_camera_view(figure, relayout_data):
    if relayout_data and "scene.camera" in relayout_data:
        camera = relayout_data["scene.camera"]
        BASE_PLOTTER.change_camera_view(figure, camera)

    return figure


def load_params(params_json, params_type):
    try:
        params = json.loads(params_json)
    except Exception as e:
        print(f"Error loading json of type {params_type}. {e} | {params_json}")

        if params_type == "dims":
            return BASE_DIMENSIONS
        if params_type == "pose":
            return BASE_POSE
        if params_type == "ik":
            return BASE_IK_PARAMS

        raise Exception(
            f'params_type must be "dims", "pose" or "ik", not {params_type}'
        ) from e

    return params


def make_poses_message(poses, legs_off_ground=()):
    """The solved joint angles, laid out like the kinematics inputs.

    Legs and joints are named the way the robot firmware names them, so a row
    can be read straight onto the robot's calibration page.
    """
    by_name = {pose["name"]: pose for pose in poses.values()}

    def angle_cell(leg_name, joint_index):
        angle = by_name[leg_name][NAMES_JOINT[joint_index]]
        return html.Div(f"{angle:+.2f}", className="ind-readout")

    body = [
        html.H6("Solved joint angles (°)", className="mb-3"),
        make_leg_sides(angle_cell),
    ]

    # The pose is reachable, but these legs came up short of the ground point
    # they were aimed at and are stretched straight out in the air instead.
    # Worth saying, otherwise the robot just looks wrong for no stated reason.
    if legs_off_ground:
        labels = ", ".join(leg_label(leg) for leg in legs_off_ground)
        body.append(
            html.Div(f"⚠ Not reaching the ground: {labels}", className="ind-alert mt-2")
        )

    return dbc.Card(dbc.CardBody(body), className="mb-3 ind-card")


def make_alert_message(alert):
    return html.Div(f"⚠ {alert}", className="ind-alert mb-3")
