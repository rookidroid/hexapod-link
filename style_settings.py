DARKMODE = False

# Bootstrap theme - using local CSS file from assets folder
BOOTSTRAP_THEME = "/assets/bootstrap.min.css"

# Only use Bootstrap CSS without external overrides
EXTERNAL_STYLESHEETS = [BOOTSTRAP_THEME]


# ***************************************
# GLOBAL PAGE STYLE
# ***************************************

DARK_BG_COLOR = "#222f3e"
DARK_FONT_COLOR = "#32ff7e"

GLOBAL_PAGE_STYLE = {
    "background": DARK_BG_COLOR,
    "color": DARK_FONT_COLOR,
    "padding": "0em",
}

if not DARKMODE:
    GLOBAL_PAGE_STYLE = {
        "background": "#cbd5e1",  # Dimmed Slate-300
        "color": "#1e293b",       # Slate for text
        "padding": "0em",
        "fontFamily": "'Rajdhani', sans-serif"
    }


# ***************************************
# NUMBER FIELD INPUT WIDGET
# ***************************************

NUMBER_INPUT_STYLE = {
    "marginRight": "5%",
    "width": "95%",
    "marginBottom": "5%",
    "borderRadius": "10px",
    "border": "solid 1px",
    "fontFamily": "Courier New",
}

if DARKMODE:
    NUMBER_INPUT_STYLE["backgroundColor"] = "#2c3e50"
    NUMBER_INPUT_STYLE["color"] = "#2ecc71"
    NUMBER_INPUT_STYLE["borderColor"] = "#2980b9"
else:
    NUMBER_INPUT_STYLE["fontFamily"] = "'Share Tech Mono', 'Courier New', monospace"
    NUMBER_INPUT_STYLE["borderColor"] = "rgba(14, 165, 233, 0.3)"
    NUMBER_INPUT_STYLE["backgroundColor"] = "rgba(255, 255, 255, 0.7)"
    NUMBER_INPUT_STYLE["color"] = "#1e293b"


# ***************************************
# DAQ SLIDER INPUT WIDGET
# ***************************************

IK_SLIDER_SIZE = 120

SLIDER_THEME = {
    "dark": DARKMODE,
    "detail": "#ffffff",
    "primary": "#ffffff",
    "secondary": "#ffffff",
}

SLIDER_HANDLE_COLOR = "#2ecc71"
SLIDER_COLOR = "#FC427B"

if not DARKMODE:
    SLIDER_HANDLE_COLOR = "#0ea5e9"  # Cyan/Blue handle
    SLIDER_COLOR = "#38bdf8"         # Light blue slider track


# ***************************************
# HEXAPOD GRAPH
# ***************************************

BODY_MESH_COLOR = "#ff6348"
BODY_MESH_OPACITY = 0.3
BODY_COLOR = "#FC427B"
BODY_OUTLINE_WIDTH = 12
COG_COLOR = "#32ff7e"
COG_SIZE = 14
HEAD_SIZE = 14
LEG_COLOR = "#EE5A24"  # "#b71540"
LEG_OUTLINE_WIDTH = 10
SUPPORT_POLYGON_MESH_COLOR = "#3c6382"
SUPPORT_POLYGON_MESH_OPACITY = 0.2
LEGENDS_BG_COLOR = "rgba(44, 62, 80, 0.8)"
AXIS_ZERO_LINE_COLOR = "#079992"
PAPER_BG_COLOR = "#222f3e"
GROUND_COLOR = "#0a3d62"
LEGEND_FONT_COLOR = "#2ecc71"

if not DARKMODE:
    BODY_MESH_COLOR = "#38bdf8"       # Cyan for body mesh
    BODY_MESH_OPACITY = 0.5
    BODY_COLOR = "#0284c7"            # Deep blue body outline
    BODY_OUTLINE_WIDTH = 10
    COG_COLOR = "#f43f5e"             # Rose/Magenta for COG
    COG_SIZE = 15
    HEAD_COLOR = "#0284c7"            # Deep blue for head
    HEAD_SIZE = 12
    LEG_COLOR = "#1e293b"             # Dark slate for legs
    LEG_OUTLINE_WIDTH = 10
    SUPPORT_POLYGON_MESH_COLOR = "#0ea5e9"  # Energetic blue
    SUPPORT_POLYGON_MESH_OPACITY = 0.2
    LEGENDS_BG_COLOR = "rgba(255, 255, 255, 0.5)"
    AXIS_ZERO_LINE_COLOR = "#94a3b8"  # Cool grey for axis
    PAPER_BG_COLOR = "#cbd5e1"        # Dim grey
    GROUND_COLOR = "rgb(180, 190, 200)"
    LEGEND_FONT_COLOR = "#0f172a"
