# Leg and joint identity, following the ESP32 firmware's convention.
#
# The physical robot (the `hexapod` repo) numbers legs per side, front to back,
# and numbers joints outward from the body:
#
#   leg index    0             1              2             3            4             5
#   firmware     Right Leg 1   Right Leg 2    Right Leg 3   Left Leg 1   Left Leg 2    Left Leg 3
#   simulator    right-front   right-middle   right-back    left-front   left-middle   left-back
#
#   joint index  1             2              3
#   firmware     Joint 1       Joint 2        Joint 3
#   simulator    coxia         femur          tibia
#                alpha         beta           gamma
#
# The index order is already the same in both projects -- compare `left_legs` /
# `right_legs` in the firmware's config.h and `legNames` in path_tool's
# config.json -- so nothing here reorders anything. What this module does is
# make the firmware's numbering the only numbering the user ever sees, instead
# of leaving the correspondence to be looked up in a comment.
#
# Internal identifiers stay descriptive: `right-front` says which leg it is
# without a diagram, and the pose dicts, widget ids and point names all key off
# them. Everything a person reads -- widget captions, plot traces, pose tables,
# alert messages -- is built from the label tables below, so the simulator and
# the robot's calibration page name the same servo the same way.


LEG_NAMES = (
    "right-front",
    "right-middle",
    "right-back",
    "left-front",
    "left-middle",
    "left-back",
)

LEG_LABELS = (
    "Right Leg 1",
    "Right Leg 2",
    "Right Leg 3",
    "Left Leg 1",
    "Left Leg 2",
    "Left Leg 3",
)

# Anatomical names, ordered from the body outward. Index i is the firmware's
# "Joint i + 1".
JOINT_NAMES = ("coxia", "femur", "tibia")

# The angle each joint is posed by, in the same order. The simulator's kinematics
# talk in alpha/beta/gamma; they are the same three joints under another name.
JOINT_ANGLE_NAMES = ("alpha", "beta", "gamma")

_JOINT_INDEX = {name: i for i, name in enumerate(JOINT_NAMES)}
_JOINT_INDEX.update({name: i for i, name in enumerate(JOINT_ANGLE_NAMES)})

_LEG_INDEX = {name: i for i, name in enumerate(LEG_NAMES)}


def leg_index(leg):
    """Resolve a leg id or name to its index."""
    if isinstance(leg, str):
        return _LEG_INDEX[leg]
    return int(leg)


def leg_label(leg):
    """The firmware's name for a leg, given its id or its simulator name."""
    return LEG_LABELS[leg_index(leg)]


def joint_number(joint):
    """The firmware's joint number (1-3) for an anatomical or angle name."""
    return _JOINT_INDEX[joint] + 1


def joint_label(joint):
    """The firmware's joint number, keeping the name it was asked about.

    `joint_label("coxia")` is "Joint 1 (coxia)" and `joint_label("alpha")` is
    "Joint 1 (alpha)", so a widget can carry the number without giving up the
    vocabulary of the page it sits on.
    """
    return f"Joint {joint_number(joint)} ({joint})"


def joint_short_label(joint):
    """Abbreviated form for places too narrow for the full label."""
    return f"J{joint_number(joint)} {joint}"
