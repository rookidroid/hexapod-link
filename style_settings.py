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
        "background": "#e2e8f0",  # Light metallic grey
        "color": "#1a202c",       # Dark slate text
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
if not DARKMODE:
    NUMBER_INPUT_STYLE["fontFamily"] = "'Share Tech Mono', 'Courier New', monospace"
    NUMBER_INPUT_STYLE["borderColor"] = "rgba(0, 91, 181, 0.4)" # Gundam Blue
    NUMBER_INPUT_STYLE["backgroundColor"] = "rgba(255, 255, 255, 0.9)"
    NUMBER_INPUT_STYLE["color"] = "#1a202c"


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
    SLIDER_HANDLE_COLOR = "#e60012"  # Gundam Red handle
    SLIDER_COLOR = "#005bb5"         # Gundam Blue slider track


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
    BODY_MESH_COLOR = "#475569"       # Dark industrial metal
    BODY_MESH_OPACITY = 0.8
    BODY_COLOR = "#f97316"            # Industrial orange body outline
    BODY_OUTLINE_WIDTH = 10
    COG_COLOR = "#22c55e"             # Green COG indicator
    COG_SIZE = 15
    HEAD_COLOR = "#ef4444"            # Red head
    HEAD_SIZE = 12
    LEG_COLOR = "#cbd5e1"             # Light metallic legs for contrast
    LEG_OUTLINE_WIDTH = 10
    SUPPORT_POLYGON_MESH_COLOR = "#f97316"  # Orange support polygon
    SUPPORT_POLYGON_MESH_OPACITY = 0.15
    LEGENDS_BG_COLOR = "rgba(17, 24, 39, 0.85)" # Dark glass legend
    AXIS_ZERO_LINE_COLOR = "#4ade80"  # CRT green axis lines
    PAPER_BG_COLOR = "#111827"        # Very dark gray background (CAD style)
    GROUND_COLOR = "#1f2937"          # Dark gray ground floor
    LEGEND_FONT_COLOR = "#f8fafc"     # Light legend text
