"""The naming module is the simulator's only claim about the firmware's numbering.

Nothing here computes anything; the tables *are* the contract. What these tests
guard is that the correspondence stays the one documented at the top of
hexapod/naming.py -- right legs first, joints numbered outward from the body --
because every widget caption, plot trace and alert message is built from it, and
a silent reordering would have the simulator and the robot's calibration page
name the same servo differently.
"""

import pytest

from hexapod.naming import (
    JOINT_ANGLE_NAMES,
    JOINT_NAMES,
    LEG_LABELS,
    LEG_NAMES,
    joint_label,
    joint_number,
    joint_short_label,
    leg_index,
    leg_label,
)


def test_leg_tables_line_up():
    """The two leg tables are indexed by the same leg id, so they must match."""
    assert len(LEG_NAMES) == len(LEG_LABELS) == 6
    assert len(set(LEG_NAMES)) == 6, "leg names must be distinct"
    assert len(set(LEG_LABELS)) == 6, "leg labels must be distinct"


def test_right_legs_come_first():
    """Ids 0-2 are the right legs and 3-5 the left, front to back on each side.

    This is the firmware's `right_legs` / `left_legs` order from config.h. The
    ground contact solver and the servo tick layout both index by it, so the
    tables and the firmware have to agree on which half is which.
    """
    for leg_id in range(3):
        assert LEG_NAMES[leg_id].startswith("right-")
        assert LEG_LABELS[leg_id] == f"Right Leg {leg_id + 1}"
    for leg_id in range(3, 6):
        assert LEG_NAMES[leg_id].startswith("left-")
        assert LEG_LABELS[leg_id] == f"Left Leg {leg_id - 2}"


def test_leg_index_accepts_a_name_or_an_id():
    """Callers hold either form, so both have to resolve to the same leg."""
    for leg_id, name in enumerate(LEG_NAMES):
        assert leg_index(name) == leg_id
        assert leg_index(leg_id) == leg_id
        assert leg_label(name) == leg_label(leg_id) == LEG_LABELS[leg_id]


def test_leg_index_rejects_an_unknown_name():
    """A typo'd leg name must fail loudly rather than resolve to leg 0."""
    with pytest.raises(KeyError):
        leg_index("right-centre")


def test_joints_are_numbered_outward_from_the_body():
    """coxia/femur/tibia are joints 1/2/3, and alpha/beta/gamma are the same three.

    The kinematics talk in angles and the widgets talk in anatomy; both have to
    land on the firmware's joint number or a calibration value gets written to
    the wrong servo.
    """
    assert JOINT_NAMES == ("coxia", "femur", "tibia")
    assert JOINT_ANGLE_NAMES == ("alpha", "beta", "gamma")

    for i, (anatomical, angle) in enumerate(zip(JOINT_NAMES, JOINT_ANGLE_NAMES)):
        assert joint_number(anatomical) == i + 1
        assert joint_number(angle) == i + 1


def test_joint_labels_keep_the_vocabulary_they_were_asked_about():
    """The number is added, the caller's own word is not translated away.

    A page that talks in alpha must not suddenly say coxia, which is why
    joint_label interpolates the name it was given.
    """
    assert joint_label("coxia") == "Joint 1 (coxia)"
    assert joint_label("alpha") == "Joint 1 (alpha)"
    assert joint_label("tibia") == "Joint 3 (tibia)"
    assert joint_short_label("beta") == "J2 beta"


def test_joint_number_rejects_an_unknown_joint():
    with pytest.raises(KeyError):
        joint_number("knee")
