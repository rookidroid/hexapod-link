# Sliders that move and tilt the body over the planted feet: shown in the
# overlay on the view while the body is picked (widgets/pose_ui.py,
# pages/pose.py, hexapod/pose_layers.py).
from settings import UPDATE_MODE, BODY_MAX_ANGLE, SLIDER_ANGLE_RESOLUTION
from widgets.components import group_header, make_slider_field

# A fraction of the body's size along each axis: its middle width, its side
# length and its tibia length (hexapod/pose_layers.py).
MAX_SHIFT = 1.0
# The slider's steps count from its minimum, so a range that is not a whole
# number of steps (40 in steps of 1.5) would put no step on 0, and the body
# could not be set level again. Trimmed to the last whole step.
MAX_ANGLE = SLIDER_ANGLE_RESOLUTION * (BODY_MAX_ANGLE // SLIDER_ANGLE_RESOLUTION)


def make_translate_slider(name, slider_label):
    return make_slider_field(
        name, slider_label, -MAX_SHIFT, MAX_SHIFT, 0.05, 0.0, updatemode=UPDATE_MODE
    )


def make_rotate_slider(name, slider_label):
    return make_slider_field(
        name,
        slider_label,
        -MAX_ANGLE,
        MAX_ANGLE,
        SLIDER_ANGLE_RESOLUTION,
        0.0,
        updatemode=UPDATE_MODE,
    )


# ................................
# COMPONENTS
# ................................

# In the order of pose_layers.BODY_KEYS.
BODY_SLIDER_IDS = [
    "widget-percent-x",
    "widget-percent-y",
    "widget-percent-z",
    "widget-rot-x",
    "widget-rot-y",
    "widget-rot-z",
]
# How far each goes either way, in the same order: what the body is held to
# when it is dragged in the view instead.
BODY_RANGES = [MAX_SHIFT] * 3 + [MAX_ANGLE] * 3

TRANSLATE_WIDGETS = [
    group_header("Translate (× body size)"),
    make_translate_slider(BODY_SLIDER_IDS[0], "X"),
    make_translate_slider(BODY_SLIDER_IDS[1], "Y"),
    make_translate_slider(BODY_SLIDER_IDS[2], "Z"),
]

ROTATE_WIDGETS = [
    group_header("Rotate (°)"),
    make_rotate_slider(BODY_SLIDER_IDS[3], "X"),
    make_rotate_slider(BODY_SLIDER_IDS[4], "Y"),
    make_rotate_slider(BODY_SLIDER_IDS[5], "Z"),
]
