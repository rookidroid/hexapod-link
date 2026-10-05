import json
from dash import callback, no_update
from dash.dependencies import Output
from settings import RECOMPUTE_HEXAPOD
from hexapod.models import VirtualHexapod
from hexapod.scene import hexapod_to_scene
from hexapod.robot_link import ROBOT_LINK
from hexapod.ik_solver.ik_solver2 import solve_inverse_kinematics
from hexapod.ik_solver.recompute_hexapod import recompute_hexapod
from widgets.ik_ui import IK_WIDGETS_SECTION, IK_CALLBACK_INPUTS
from pages import helpers, shared


# ......................
# Page layout
# ......................

VIEW_ID = "view-inverse"
MESSAGE_SECTION_ID = "message-inverse"
PARAMETERS_SECTION_ID = "parameters-inverse"

# The solved pose is streamed from this page, so the stream switch belongs
# beside the controls that produce it rather than in the global panel.
sidebar = shared.make_standard_page_sidebar(
    MESSAGE_SECTION_ID,
    PARAMETERS_SECTION_ID,
    IK_WIDGETS_SECTION,
    robot_section=shared.make_stream_controls("inverse"),
)

layout = shared.make_standard_page_layout(VIEW_ID, sidebar)


# ......................
# Update page
# ......................

outputs, inputs = shared.make_standard_page_callback_params(
    VIEW_ID, PARAMETERS_SECTION_ID, MESSAGE_SECTION_ID
)


@callback(outputs, inputs)
def update_inverse_page(dimensions_json, ik_parameters_json):

    dimensions = helpers.load_params(dimensions_json, "dims")
    ik_parameters = helpers.load_params(ik_parameters_json, "ik")
    hexapod = VirtualHexapod(dimensions)

    try:
        poses, hexapod, legs_off_ground = solve_inverse_kinematics(
            hexapod, ik_parameters
        )
    except Exception as alert:
        return no_update, helpers.make_alert_message(alert)

    # Only sent once the IK solver has produced a reachable pose.
    ROBOT_LINK.send_pose(poses)

    if RECOMPUTE_HEXAPOD:
        try:
            hexapod = recompute_hexapod(
                dimensions, ik_parameters, poses, legs_off_ground
            )
        except Exception as alert:
            return no_update, helpers.make_alert_message(alert)

    return hexapod_to_scene(hexapod), helpers.make_poses_message(poses, legs_off_ground)


# ......................
# Update parameters
# ......................

output_parameter = Output(PARAMETERS_SECTION_ID, "children")
input_parameters = IK_CALLBACK_INPUTS


@callback(output_parameter, input_parameters)
def update_ik_parameters(
    hip_stance, leg_stance, percent_x, percent_y, percent_z, rot_x, rot_y, rot_z
):

    return json.dumps(
        {
            "hip_stance": hip_stance or 0,
            "leg_stance": leg_stance or 0,
            "percent_x": percent_x or 0,
            "percent_y": percent_y or 0,
            "percent_z": percent_z or 0,
            "rot_x": rot_x or 0,
            "rot_y": rot_y or 0,
            "rot_z": rot_z or 0,
        }
    )
