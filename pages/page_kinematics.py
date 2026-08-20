import json
from dash import html
from dash.dependencies import Output
from app import app
from settings import WHICH_POSE_CONTROL_UI
from hexapod.models import VirtualHexapod
from hexapod.const import BASE_PLOTTER
from hexapod.robot_link import ROBOT_LINK
from widgets.pose_control.components import KINEMATICS_CALLBACK_INPUTS
from pages import helpers, shared

if WHICH_POSE_CONTROL_UI == 1:
    from widgets.pose_control.generic_daq_slider_ui import KINEMATICS_WIDGETS_SECTION
elif WHICH_POSE_CONTROL_UI == 2:
    from widgets.pose_control.generic_slider_ui import KINEMATICS_WIDGETS_SECTION
else:
    from widgets.pose_control.generic_input_ui import KINEMATICS_WIDGETS_SECTION

# ......................
# Page layout
# ......................

GRAPH_ID = "graph-kinematics"
MESSAGE_SECTION_ID = "message-kinematics"
PARAMETERS_SECTION_ID = "parameters-kinematics"

# Joint angles set here are streamed straight to the servos, so the stream
# switch belongs on this page rather than in the global panel.
widgets_section = html.Div(
    [KINEMATICS_WIDGETS_SECTION, shared.make_stream_controls("kinematics")]
)

sidebar = shared.make_standard_page_sidebar(
    MESSAGE_SECTION_ID, PARAMETERS_SECTION_ID, widgets_section
)

layout = shared.make_standard_page_layout(GRAPH_ID, sidebar)


# ......................
# Update page
# ......................

outputs, inputs, states = shared.make_standard_page_callback_params(
    GRAPH_ID, PARAMETERS_SECTION_ID, MESSAGE_SECTION_ID
)


@app.callback(outputs, inputs, states)
def update_kinematics_page(dimensions_json, poses_json, relayout_data, figure):

    dimensions = helpers.load_params(dimensions_json, "dims")
    poses = helpers.load_params(poses_json, "pose")
    hexapod = VirtualHexapod(dimensions)

    # Joint angles are the input here, so they are valid to send even when the
    # simulator cannot resolve a stable body orientation for them below.
    ROBOT_LINK.send_pose(poses)

    try:
        hexapod.update(poses, assume_ground_targets=False)
    except Exception as alert:
        return figure, helpers.make_alert_message(alert)

    BASE_PLOTTER.update(figure, hexapod)
    helpers.change_camera_view(figure, relayout_data)
    return figure, ""


# ......................
# Update parameters
# ......................


output_parameter = Output(PARAMETERS_SECTION_ID, "children")
input_parameters = KINEMATICS_CALLBACK_INPUTS

# fmt: off


@app.callback(output_parameter, input_parameters)
def update_poses(
    rfc, rff, rft,
    rmc, rmf, rmt,
    rbc, rbf, rbt,
    lfc, lff, lft,
    lmc, lmf, lmt,
    lbc, lbf, lbt,
):

    return json.dumps({
        0: {"coxia": rfc or 0, "femur": rff or 0, "tibia": rft or 0, "name": "right-front", "id": 0},
        1: {"coxia": rmc or 0, "femur": rmf or 0, "tibia": rmt or 0, "name": "right-middle", "id": 1},
        2: {"coxia": rbc or 0, "femur": rbf or 0, "tibia": rbt or 0, "name": "right-back", "id": 2},
        3: {"coxia": lfc or 0, "femur": lff or 0, "tibia": lft or 0, "name": "left-front", "id": 3},
        4: {"coxia": lmc or 0, "femur": lmf or 0, "tibia": lmt or 0, "name": "left-middle", "id": 4},
        5: {"coxia": lbc or 0, "femur": lbf or 0, "tibia": lbt or 0, "name": "left-back", "id": 5},
    })

# fmt: on
