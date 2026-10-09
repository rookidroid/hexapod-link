# Sliders that move and tilt the body over the planted feet: the Body tool of
# the pose page (pages/page_pose.py, hexapod/pose_layers.py).
from settings import UPDATE_MODE, BODY_MAX_ANGLE, SLIDER_ANGLE_RESOLUTION
from widgets.section_maker import group_header, make_slider_field


def make_translate_slider(name, slider_label):
    # A fraction of the body's size along each axis: its middle width, its
    # side length and its tibia length (hexapod/pose_layers.py).
    return make_slider_field(
        name, slider_label, -1.0, 1.0, 0.05, 0.0, updatemode=UPDATE_MODE
    )


def make_rotate_slider(name, slider_label, max_angle=BODY_MAX_ANGLE):
    # The slider's steps count from its minimum, so a range that is not a
    # whole number of steps (40 in steps of 1.5) would put no step on 0, and
    # the body could not be set level again. Trimmed to the last whole step.
    max_angle = SLIDER_ANGLE_RESOLUTION * (max_angle // SLIDER_ANGLE_RESOLUTION)
    return make_slider_field(
        name,
        slider_label,
        -max_angle,
        max_angle,
        SLIDER_ANGLE_RESOLUTION,
        0.0,
        updatemode=UPDATE_MODE,
    )


# ................................
# COMPONENTS
# ................................

# In the order of pose_layers.BODY_KEYS.
IK_WIDGETS_IDS = [
    "widget-percent-x",
    "widget-percent-y",
    "widget-percent-z",
    "widget-rot-x",
    "widget-rot-y",
    "widget-rot-z",
]

translate = [
    group_header("Translate (× body size)"),
    make_translate_slider(IK_WIDGETS_IDS[0], "X"),
    make_translate_slider(IK_WIDGETS_IDS[1], "Y"),
    make_translate_slider(IK_WIDGETS_IDS[2], "Z"),
]

rotate = [
    group_header("Rotate (°)"),
    make_rotate_slider(IK_WIDGETS_IDS[3], "X"),
    make_rotate_slider(IK_WIDGETS_IDS[4], "Y"),
    make_rotate_slider(IK_WIDGETS_IDS[5], "Z"),
]

IK_WIDGETS = [*translate, *rotate]
