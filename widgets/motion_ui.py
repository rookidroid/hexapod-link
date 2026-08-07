import dash_bootstrap_components as dbc
from dash import dcc, html
from style_settings import NUMBER_INPUT_STYLE

# --- Element IDs ---
MOTION_DROPDOWN_ID = "motion-type-dropdown"
MOTION_PLAY_BTN_ID = "motion-play-btn"
MOTION_SPEED_SLIDER_ID = "motion-speed-slider"
MOTION_FRAME_SLIDER_ID = "motion-frame-slider"
MOTION_LOOP_CHECKBOX_ID = "motion-loop-checkbox"
MOTION_FRAME_DISPLAY_ID = "motion-frame-display"
MOTION_ROBOT_MODE_ID = "motion-robot-mode"
MOTION_ROBOT_RUN_BTN_ID = "motion-robot-run-btn"
MOTION_ROBOT_STOP_BTN_ID = "motion-robot-stop-btn"
MOTION_ROBOT_MESSAGE_ID = "motion-robot-message"

# --- Data ---
MOTION_TYPES = [
    {"label": "Standby (Reset)", "value": "standby"},
    {"label": "Walk Forward", "value": "walk_0"},
    {"label": "Walk Backward", "value": "walk_180"},
    {"label": "Walk Right 45°", "value": "walk_r45"},
    {"label": "Walk Right 90°", "value": "walk_r90"},
    {"label": "Walk Right 135°", "value": "walk_r135"},
    {"label": "Walk Left 45°", "value": "walk_l45"},
    {"label": "Walk Left 90°", "value": "walk_l90"},
    {"label": "Walk Left 135°", "value": "walk_l135"},
    {"label": "Fast Forward", "value": "fast_forward"},
    {"label": "Fast Backward", "value": "fast_backward"},
    {"label": "Turn Left", "value": "turn_left"},
    {"label": "Turn Right", "value": "turn_right"},
    {"label": "Climb Forward", "value": "climb_forward"},
    {"label": "Climb Backward", "value": "climb_backward"},
    {"label": "Rotate X (Pitch)", "value": "rotate_x"},
    {"label": "Rotate Y (Roll)", "value": "rotate_y"},
    {"label": "Rotate Z (Wobble)", "value": "rotate_z"},
    {"label": "Twist (Figure-8)", "value": "twist"},
    {"label": "Stand Up", "value": "standup"},
]

# --- UI Components ---
def make_section(header, content, card_style=None):
    return dbc.Card(
        [
            dbc.CardHeader(header, className="fw-bold text-center"),
            dbc.CardBody(content),
        ],
        className="mb-3",
        style=card_style,
    )

dropdown = dbc.Select(
    id=MOTION_DROPDOWN_ID,
    options=MOTION_TYPES,
    value="walk_0",
    className="mb-3 form-control",
)

playback_controls = dbc.Row(
    [
        dbc.Col(
            dbc.Button(
                "▶ Play",
                id=MOTION_PLAY_BTN_ID,
                color="primary",
                className="w-100 fw-bold",
            ),
            width=5,
        ),
        dbc.Col(
            html.Div(
                "Frame 0/0",
                id=MOTION_FRAME_DISPLAY_ID,
                className="text-center w-100 fw-bold d-flex align-items-center justify-content-center h-100",
            ),
            width=4,
        ),
        dbc.Col(
            dcc.Checklist(
                id=MOTION_LOOP_CHECKBOX_ID,
                options=[{"label": " Loop", "value": "loop"}],
                value=["loop"],
                className="d-flex align-items-center justify-content-center h-100 fw-bold",
            ),
            width=3,
        ),
    ],
    className="mb-3 g-2",
)

speed_slider = html.Div(
    [
        html.Label("Playback Speed", className="fw-bold mb-1"),
        dcc.Slider(
            id=MOTION_SPEED_SLIDER_ID,
            min=0.2,
            max=3.0,
            step=0.1,
            value=1.0,
            marks={0.5: "0.5x", 1.0: "1x", 2.0: "2x", 3.0: "3x"},
            tooltip={"placement": "bottom", "always_visible": False},
        ),
    ],
    className="mb-4",
)

frame_scrubber = html.Div(
    [
        html.Label("Scrub Frame", className="fw-bold mb-1"),
        dcc.Slider(
            id=MOTION_FRAME_SLIDER_ID,
            min=0,
            max=27, # Will be updated dynamically
            step=1,
            value=0,
            marks=None,
            tooltip={"placement": "bottom", "always_visible": True},
        ),
    ]
)

robot_mode = dbc.RadioItems(
    id=MOTION_ROBOT_MODE_ID,
    options=[
        {"label": " Robot's own gait (recommended)", "value": "native"},
        {"label": " Stream frames from simulator", "value": "stream"},
    ],
    value="native",
    className="mb-3",
)

robot_buttons = dbc.Row(
    [
        dbc.Col(
            dbc.Button(
                "▶ Run on Robot",
                id=MOTION_ROBOT_RUN_BTN_ID,
                color="success",
                className="w-100 fw-bold",
            ),
            width=7,
        ),
        dbc.Col(
            dbc.Button(
                "■ Standby",
                id=MOTION_ROBOT_STOP_BTN_ID,
                color="secondary",
                className="w-100 fw-bold",
            ),
            width=5,
        ),
    ],
    className="g-2",
)

robot_motion_controls = html.Div(
    [
        robot_mode,
        robot_buttons,
        html.Div(
            id=MOTION_ROBOT_MESSAGE_ID,
            className="small text-muted font-monospace text-center mt-2",
        ),
    ]
)

# --- Put it together ---
MOTION_WIDGETS_SECTION = html.Div(
    [
        make_section("SELECT MOTION", dropdown, card_style={"overflow": "visible", "zIndex": 2}),
        make_section("PLAYBACK", html.Div([playback_controls, speed_slider, frame_scrubber]), card_style={"zIndex": 1}),
        make_section("RUN ON ROBOT", robot_motion_controls, card_style={"zIndex": 1}),
    ]
)
