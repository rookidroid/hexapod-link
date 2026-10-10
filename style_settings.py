# Bootstrap theme - using local CSS file from assets folder
EXTERNAL_STYLESHEETS = ["/assets/bootstrap.min.css"]


# ***************************************
# HEXAPOD VIEW
# ***************************************

# The 3D view (assets/hexapod_view.js) is the cockpit's panoramic monitor in
# both themes: a navy screen with the robot in RX-78-2 colours and HUD-cyan
# overlays. hexapod/scene.py hands these to it with every scene.

BODY_MESH_COLOR = "#e8ecf2"       # White armour
BODY_COLOR = "#3b7bff"            # Federation blue body trim and joint rings
JOINT_COLOR = "#55627e"          # Inner-frame grey joint hubs
COG_COLOR = "#e63946"             # Red core block
HEAD_COLOR = "#f7c600"            # V-fin yellow head; also a picked-up foot
LEG_COLOR = "#dfe6ef"             # White armour legs
SUPPORT_POLYGON_MESH_COLOR = "#4cc9f0"  # HUD cyan support polygon and feet
PAPER_BG_COLOR = "#0a1428"        # Monitor navy background
GROUND_COLOR = "#13213f"          # Navy ground floor
GRID_COLOR = "#24406e"            # Grid lines on the floor
# Direction arrows on the body and at the origin.
AXIS_X_COLOR = "#e63946"          # Red
AXIS_Y_COLOR = "#f7c600"          # Yellow
AXIS_Z_COLOR = "#4cc9f0"          # Cyan
