from copy import deepcopy
import json
from dash import dcc
from hexapod.const import (
    BASE_PLOTTER,
    BASE_POSE,
    BASE_IK_PARAMS,
    BASE_DIMENSIONS,
    NAMES_JOINT,
    NAMES_LEG,
)
from hexapod.naming import joint_label, leg_label

NEW_POSES = deepcopy(BASE_POSE)

# Legs and joints are named the way the robot firmware names them, so a row of
# this table can be read straight onto the robot's calibration page.
_LEG_COLUMN_WIDTH = 13
_JOINT_COLUMN_WIDTH = 15
_POSES_MSG_RULE = "\n+{}+{}+".format(
    "-" * (_LEG_COLUMN_WIDTH + 2),
    "+".join(["-" * (_JOINT_COLUMN_WIDTH + 2)] * len(NAMES_JOINT)),
)
_POSES_MSG_COLUMNS = "\n| {} | {} |".format(
    f"{'leg':{_LEG_COLUMN_WIDTH}}",
    " | ".join(f"{joint_label(name):{_JOINT_COLUMN_WIDTH}}" for name in NAMES_JOINT),
)
POSES_MSG_HEADER = _POSES_MSG_RULE + _POSES_MSG_COLUMNS + _POSES_MSG_RULE
POSES_MSG_LAST_ROW = _POSES_MSG_RULE


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


def make_monospace(text):
    return dcc.Markdown(f" ```{text}")


def make_poses_message(poses, legs_off_ground=()):
    message = POSES_MSG_HEADER

    for pose in poses.values():
        label = leg_label(pose["id"])
        angles = " | ".join(
            f"{pose[name]:<+{_JOINT_COLUMN_WIDTH}.2f}" for name in NAMES_JOINT
        )
        message += f"\n| {label:{_LEG_COLUMN_WIDTH}} | {angles} |"

    message += POSES_MSG_LAST_ROW

    # The pose is reachable, but these legs came up short of the ground point
    # they were aimed at and are stretched straight out in the air instead.
    # Worth saying, otherwise the robot just looks wrong for no stated reason.
    if legs_off_ground:
        labels = ", ".join(leg_label(leg) for leg in legs_off_ground)
        message += f"\n\n⚠️ Not reaching the ground: {labels}"

    return make_monospace(message)


def make_alert_message(alert):
    return make_monospace(f"❗❗❗ALERT❗❗❗\n⚠️ {alert} 🔴")
