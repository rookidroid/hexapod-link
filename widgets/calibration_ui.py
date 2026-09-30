# Widgets for trimming the robot's servo offsets.
#
# A front end to the firmware's own calibration routes (see hexapod/robot_http.py):
# the robot holds its calibration posture while in calibration mode, the
# offsets are applied live, and saving writes them to the robot's flash. The
# grid is laid out the way the firmware names servos (hexapod/naming.py), so it
# reads the same as the robot's built-in calibration page.
import dash_bootstrap_components as dbc
from dash import dcc, html

from hexapod.naming import JOINT_NAMES, LEG_LABELS, joint_label

# Offsets are servo ticks (~0.44 deg each); the firmware rejects anything wider.
CALIBRATION_MAX_OFFSET = 100

CALIBRATION_ENTER_BTN_ID = "calibration-enter-btn"
CALIBRATION_EXIT_BTN_ID = "calibration-exit-btn"
CALIBRATION_RELOAD_BTN_ID = "calibration-reload-btn"
CALIBRATION_APPLY_BTN_ID = "calibration-apply-btn"
CALIBRATION_SAVE_BTN_ID = "calibration-save-btn"
CALIBRATION_MESSAGE_ID = "calibration-message"
CALIBRATION_STATUS_ID = "calibration-status"
CALIBRATION_CONTROLS_ID = "calibration-controls"
CALIBRATION_MODE_STORE_ID = "calibration-mode-store"
CALIBRATION_POLL_INTERVAL_ID = "calibration-poll-interval"

STATUS_POLL_MS = 1000


def offset_input_id(leg_id, joint_index):
    return f"calibration-offset-{leg_id}-{joint_index}"


# Leg-major, joint-minor: the order of the firmware's tables and of pose ticks.
OFFSET_INPUT_IDS = [
    offset_input_id(leg_id, joint_index)
    for leg_id in range(len(LEG_LABELS))
    for joint_index in range(len(JOINT_NAMES))
]


def _offset_input(leg_id, joint_index):
    # No min/max here: an out-of-range entry would reach the callback as blank
    # and be sent as 0. Apply clamps it to the range instead and shows that.
    return dbc.Input(
        id=offset_input_id(leg_id, joint_index),
        type="number",
        value=0,
        step=1,
        disabled=True,
        size="sm",
    )


_header = html.Tr(
    [html.Th("")]
    + [html.Th(joint_label(joint), className="text-center small") for joint in JOINT_NAMES]
)

_rows = [
    html.Tr(
        [html.Th(label, className="small text-nowrap align-middle")]
        + [html.Td(_offset_input(leg_id, j)) for j in range(len(JOINT_NAMES))]
    )
    for leg_id, label in enumerate(LEG_LABELS)
]

offset_table = dbc.Table(
    [html.Thead(_header), html.Tbody(_rows)],
    borderless=True,
    size="sm",
    className="mb-3 calibration-table",
)


def _button(label, button_id, color, outline=False):
    return dbc.Button(
        label,
        id=button_id,
        color=color,
        outline=outline,
        disabled=True,
        className="w-100 fw-bold",
    )


mode_buttons = dbc.Row(
    [
        dbc.Col(_button("Enter calibration", CALIBRATION_ENTER_BTN_ID, "warning"), width=6),
        dbc.Col(_button("Exit", CALIBRATION_EXIT_BTN_ID, "secondary"), width=6),
    ],
    className="mb-3 g-2",
)

offset_buttons = dbc.Row(
    [
        dbc.Col(_button("Reload", CALIBRATION_RELOAD_BTN_ID, "secondary", outline=True), width=4),
        dbc.Col(_button("Apply", CALIBRATION_APPLY_BTN_ID, "primary"), width=4),
        dbc.Col(_button("Save to robot", CALIBRATION_SAVE_BTN_ID, "success"), width=4),
    ],
    className="g-2",
)

CALIBRATION_WIDGETS_SECTION = dbc.Card(
    dbc.CardBody(
        [
            html.H6("SERVO CALIBRATION", className="mb-2"),
            html.P(
                [
                    "Trims each servo so the legs match the robot's calibration "
                    "posture. Enter calibration mode and the robot holds that "
                    "posture; adjust an offset (servo ticks, about 0.44° each, "
                    f"±{CALIBRATION_MAX_OFFSET}) and Apply to see it move. ",
                    html.Strong("Save to robot"),
                    " stores the offsets in the robot's flash so they survive a "
                    "reboot, then Exit.",
                ],
                className="text-muted small mb-3",
            ),
            html.Div(
                [mode_buttons, offset_table, offset_buttons],
                id=CALIBRATION_CONTROLS_ID,
            ),
            html.Div(
                "",
                id=CALIBRATION_MESSAGE_ID,
                className="small font-monospace text-center mt-3",
            ),
            html.Div(
                "Disconnected",
                id=CALIBRATION_STATUS_ID,
                className="small text-muted font-monospace text-center mt-2",
            ),
            dcc.Store(id=CALIBRATION_MODE_STORE_ID, data=False),
            dcc.Interval(
                id=CALIBRATION_POLL_INTERVAL_ID, interval=STATUS_POLL_MS, n_intervals=0
            ),
        ]
    ),
    className="mb-3 ind-card",
)
