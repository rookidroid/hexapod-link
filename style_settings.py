# Bootstrap theme - using local CSS file from assets folder
EXTERNAL_STYLESHEETS = ["/assets/bootstrap.min.css"]


# ***************************************
# GLOBAL PAGE STYLE
# ***************************************

GLOBAL_PAGE_STYLE = {
    # Theme tokens from industrial.css, so the light/dark switch reaches them.
    "background": "var(--ind-bg)",
    "color": "var(--ind-text)",
    "padding": "0em",
    "fontFamily": "'Chakra Petch', sans-serif"
}


# ***************************************
# HEXAPOD GRAPH
# ***************************************

# The plot is the cockpit's panoramic monitor in both themes: a navy screen
# with the robot in RX-78-2 colours and HUD-cyan overlays.

BODY_MESH_COLOR = "#e8ecf2"       # White armour
BODY_MESH_OPACITY = 0.8
BODY_COLOR = "#3b7bff"            # Federation blue body outline
BODY_OUTLINE_WIDTH = 10
COG_COLOR = "#e63946"             # Red core block
COG_SIZE = 15
HEAD_COLOR = "#f7c600"            # V-fin yellow head
HEAD_SIZE = 12
LEG_COLOR = "#dfe6ef"             # White armour legs
LEG_OUTLINE_WIDTH = 10
SUPPORT_POLYGON_MESH_COLOR = "#4cc9f0"  # HUD cyan support polygon
SUPPORT_POLYGON_MESH_OPACITY = 0.15
LEGENDS_BG_COLOR = "rgba(10, 20, 40, 0.85)"  # Navy glass legend
AXIS_ZERO_LINE_COLOR = "#4cc9f0"  # HUD cyan axis lines
PAPER_BG_COLOR = "#0a1428"        # Monitor navy background
GROUND_COLOR = "#13213f"          # Navy ground floor
LEGEND_FONT_COLOR = "#e4eeff"     # Light legend text
# Direction arrows on the body and at the origin.
AXIS_X_COLOR = "#e63946"          # Red
AXIS_Y_COLOR = "#f7c600"          # Yellow
AXIS_Z_COLOR = "#4cc9f0"          # Cyan
