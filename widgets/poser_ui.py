# Sidebar of the pose editor (pages/page_poser.py): posing, the keyframe list,
# previewing the sequence, running it on the robot, and saving it.
import dash_bootstrap_components as dbc
from dash import dcc, html

from hexapod.keyframes import DEFAULT_DURATION_MS, MAX_DURATION_MS, MIN_DURATION_MS
from widgets.robot_link_ui import SECTION_CONTROLS_OFFLINE_CLASS, STATUS_POLL_MS
from widgets.section_maker import field_label, make_slider_field

# --- Element IDs ---
# Written by assets/poser.js through set_props; keep the two in step.
POSER_FOOT_TARGET_ID = "poser-foot-target"
POSER_SELECTED_LEG_ID = "poser-selected-leg"

POSER_VIEWER_ID = "poser-viewer"
POSER_RENDER_ACK_ID = "poser-render-ack"
POSER_FEET_STORE_ID = "poser-feet"
POSER_KEYFRAMES_STORE_ID = "poser-keyframes"
POSER_SELECTED_KF_STORE_ID = "poser-selected-keyframe"
POSER_SCENE_STORE_ID = "poser-scene"
POSER_PREVIEW_STORE_ID = "poser-preview"
POSER_PLAY_STATE_STORE_ID = "poser-play-state"
POSER_INTERVAL_ID = "poser-interval"

POSER_SELECTION_ID = "poser-selection"
POSER_ANGLES_ID = "poser-angles"
POSER_MESSAGE_ID = "poser-message"
POSER_RESET_BTN_ID = "poser-reset-btn"
POSER_RESET_VIEW_BTN_ID = "poser-reset-view-btn"

POSER_DURATION_ID = "poser-duration"
POSER_ADD_BTN_ID = "poser-add-btn"
POSER_UPDATE_BTN_ID = "poser-update-btn"
POSER_DELETE_BTN_ID = "poser-delete-btn"
POSER_UP_BTN_ID = "poser-up-btn"
POSER_DOWN_BTN_ID = "poser-down-btn"
POSER_KF_LIST_ID = "poser-keyframe-list"
POSER_KF_SUMMARY_ID = "poser-keyframe-summary"
# Pattern-matching id of one entry in the keyframe list.
POSER_KF_ITEM_TYPE = "poser-keyframe-item"

POSER_MODE_ID = "poser-mode"
POSER_LOOP_ID = "poser-loop"
POSER_EASE_ID = "poser-ease"
POSER_PLAY_BTN_ID = "poser-play-btn"
POSER_FRAME_SLIDER_ID = "poser-frame-slider"
POSER_FRAME_DISPLAY_ID = "poser-frame-display"
POSER_PREVIEW_MESSAGE_ID = "poser-preview-message"

POSER_ROBOT_CONTROLS_ID = "poser-robot-controls"
POSER_RUN_BTN_ID = "poser-run-btn"
POSER_STOP_BTN_ID = "poser-stop-btn"
POSER_ROBOT_MESSAGE_ID = "poser-robot-message"
POSER_ROBOT_POLL_INTERVAL_ID = "poser-robot-poll-interval"

POSER_SAVE_BTN_ID = "poser-save-btn"
POSER_DOWNLOAD_ID = "poser-download"
POSER_UPLOAD_ID = "poser-upload"

# Frame rate of the preview in the browser. The robot gets its own, faster,
# frames: see run_on_robot() in pages/page_poser.py.
PREVIEW_FPS = 25

MODE_EDIT = "edit"
MODE_PREVIEW = "preview"


def make_section(header, content, blurb=None):
    body = [html.H6(header, className="mb-2" if blurb else "mb-3")]
    if blurb:
        body.append(html.P(blurb, className="text-muted small mb-3"))
    body.append(content)
    return dbc.Card(dbc.CardBody(body), className="mb-3 ind-card")


def _button_row(buttons, class_name="mb-3"):
    return html.Div(buttons, className=f"d-flex flex-wrap gap-2 {class_name}")


# --- Pose ---
pose_section = make_section(
    "Pose",
    html.Div(
        [
            html.Div(
                "Click a foot to pick it up, then drag the arrows to move it.",
                id=POSER_SELECTION_ID,
                className="small font-monospace mb-3",
            ),
            _button_row(
                [
                    dbc.Button(
                        "Reset to standby",
                        id=POSER_RESET_BTN_ID,
                        color="secondary",
                        size="sm",
                        className="fw-bold",
                    ),
                    dbc.Button(
                        "Reset view",
                        id=POSER_RESET_VIEW_BTN_ID,
                        color="secondary",
                        outline=True,
                        size="sm",
                        className="fw-bold",
                    ),
                ],
                class_name="mb-0",
            ),
        ]
    ),
    blurb="The body stays put and the feet move around it, as the robot sees it.",
)


# --- Keyframes ---
def _small_button(label, button_id, color, outline=False, title=None):
    return dbc.Button(
        label,
        id=button_id,
        color=color,
        outline=outline,
        size="sm",
        title=title,
        className="fw-bold",
    )


keyframe_buttons = _button_row(
    [
        _small_button("+ Add", POSER_ADD_BTN_ID, "primary"),
        _small_button("Update", POSER_UPDATE_BTN_ID, "secondary"),
        _small_button("Delete", POSER_DELETE_BTN_ID, "danger"),
        _small_button("▲", POSER_UP_BTN_ID, "secondary", outline=True, title="Move up"),
        _small_button("▼", POSER_DOWN_BTN_ID, "secondary", outline=True, title="Move down"),
    ]
)

keyframes_section = make_section(
    "Keyframes",
    html.Div(
        [
            html.Div(
                [
                    field_label("Time to reach this pose (ms)"),
                    dbc.Input(
                        id=POSER_DURATION_ID,
                        type="number",
                        min=MIN_DURATION_MS,
                        max=MAX_DURATION_MS,
                        step=10,
                        value=DEFAULT_DURATION_MS,
                        size="sm",
                    ),
                ],
                className="mb-3",
            ),
            keyframe_buttons,
            html.Div(id=POSER_KF_LIST_ID, className="mb-2"),
            html.Div(id=POSER_KF_SUMMARY_ID, className="small text-muted font-monospace"),
            _button_row(
                [
                    dbc.Button(
                        "Save…",
                        id=POSER_SAVE_BTN_ID,
                        color="secondary",
                        outline=True,
                        size="sm",
                        className="fw-bold",
                    ),
                    dcc.Upload(
                        dbc.Button(
                            "Load…",
                            color="secondary",
                            outline=True,
                            size="sm",
                            className="fw-bold",
                        ),
                        id=POSER_UPLOAD_ID,
                        accept=".json,application/json",
                    ),
                ],
                class_name="mt-3 mb-0",
            ),
            dcc.Download(id=POSER_DOWNLOAD_ID),
        ]
    ),
    blurb=(
        "Add the current pose to the sequence. Click an entry to load it back "
        "into the editor; Update overwrites it with the pose being edited."
    ),
)

# --- Preview ---
preview_section = make_section(
    "Preview",
    html.Div(
        [
            dbc.RadioItems(
                id=POSER_MODE_ID,
                options=[
                    {"label": "Edit pose", "value": MODE_EDIT},
                    {"label": "Preview sequence", "value": MODE_PREVIEW},
                ],
                value=MODE_EDIT,
                inline=True,
                className="mb-2",
            ),
            html.Div(
                [
                    dcc.Checklist(
                        id=POSER_LOOP_ID,
                        options=[{"label": " Loop", "value": "loop"}],
                        value=[],
                        className="fw-bold",
                    ),
                    dcc.Checklist(
                        id=POSER_EASE_ID,
                        options=[{"label": " Ease in/out", "value": "ease"}],
                        value=["ease"],
                        className="fw-bold",
                    ),
                ],
                className="d-flex gap-3 mb-2",
            ),
            dbc.Button(
                "▶ Play",
                id=POSER_PLAY_BTN_ID,
                color="primary",
                className="w-100 fw-bold mb-2",
            ),
            html.Div(
                "Frame 0/0",
                id=POSER_FRAME_DISPLAY_ID,
                className="fw-bold font-monospace mb-2",
            ),
            make_slider_field(POSER_FRAME_SLIDER_ID, "Frame", 0, 1, 1, 0, disabled=True),
            html.Div(id=POSER_PREVIEW_MESSAGE_ID),
        ]
    ),
)

# --- Run on robot ---
robot_section = dbc.Card(
    dbc.CardBody(
        [
            html.H6("Run on robot", className="mb-2"),
            html.P(
                "Streams the sequence to the hardware in real time, at the "
                "durations set above. Put the hexapod on a stand first.",
                className="text-muted small mb-3",
            ),
            html.Div(
                _button_row(
                    [
                        dbc.Button(
                            "▶ Run on robot",
                            id=POSER_RUN_BTN_ID,
                            color="success",
                            disabled=True,
                            className="fw-bold ind-wrap-main",
                        ),
                        dbc.Button(
                            "■ Standby",
                            id=POSER_STOP_BTN_ID,
                            color="secondary",
                            disabled=True,
                            className="fw-bold ind-wrap-side",
                        ),
                    ],
                    class_name="mb-0",
                ),
                id=POSER_ROBOT_CONTROLS_ID,
                className=SECTION_CONTROLS_OFFLINE_CLASS,
            ),
            html.Div(
                "Connect a robot to run this on the hardware.",
                id=POSER_ROBOT_MESSAGE_ID,
                className="small text-muted font-monospace text-center mt-2",
            ),
            dcc.Interval(
                id=POSER_ROBOT_POLL_INTERVAL_ID,
                interval=STATUS_POLL_MS,
                n_intervals=0,
            ),
        ]
    ),
    className="mb-3 ind-card",
)

# Session storage, so the sequence being built survives going to another page
# and back. Each store records which robot it was made on; see page_poser.py.
hidden_components = html.Div(
    [
        dcc.Store(id=POSER_FOOT_TARGET_ID),
        dcc.Store(id=POSER_SELECTED_LEG_ID),
        dcc.Store(id=POSER_FEET_STORE_ID, storage_type="session"),
        dcc.Store(id=POSER_KEYFRAMES_STORE_ID, storage_type="session"),
        dcc.Store(id=POSER_SELECTED_KF_STORE_ID, storage_type="session"),
        dcc.Store(id=POSER_SCENE_STORE_ID),
        dcc.Store(id=POSER_PREVIEW_STORE_ID),
        dcc.Store(id=POSER_PLAY_STATE_STORE_ID, data=False),
        dcc.Store(id=POSER_RENDER_ACK_ID),
        dcc.Interval(
            id=POSER_INTERVAL_ID,
            interval=1000 // PREVIEW_FPS,
            n_intervals=0,
            disabled=True,
        ),
    ]
)

POSER_WIDGETS_SECTION = html.Div(
    [
        pose_section,
        html.Div(id=POSER_MESSAGE_ID),
        html.Div(id=POSER_ANGLES_ID),
        keyframes_section,
        preview_section,
        robot_section,
        hidden_components,
    ]
)
