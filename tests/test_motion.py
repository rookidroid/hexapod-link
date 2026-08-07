from itertools import combinations
from math import atan2, degrees

import numpy as np

from hexapod.const import BASE_DIMENSIONS
from hexapod.models import VirtualHexapod, find_twist_frame
from hexapod.path_generator import generate_poses
from hexapod.points import Vector
from hexapod.robot_profiles import (
    ROBOT_PROFILES,
    get_physical_config,
    get_simulator_dimensions,
)

# Gaits whose stance stroke is a straight line in one direction, so the feet that
# stay planted must stay put relative to each other.
#
# The turns are deliberately not here. They sweep each foot along a straight
# chord rather than an arc about the cog, so their support polygon deforms by a
# few millimetres per frame no matter what this module does -- that comes from
# the robot's own path_tool, which these paths mirror, and asserting either
# behaviour here would be asserting something about the firmware.
STRAIGHT_GAITS = [
    "walk_0",
    "walk_180",
    "walk_l45",
    "walk_l90",
    "walk_l135",
    "walk_r45",
    "walk_r90",
    "walk_r135",
    "fast_forward",
    "fast_backward",
]

# Both robots' `side` is a rounded value -- macaroon's 85.22 stands in for
# 49.2 * tan(60deg) = 85.2169 -- which tilts each mount azimuth by under a
# thousandth of a degree and leaves a sub-micron residue in the numbers below.
# A micron of slack absorbs it while still catching anything real: the bug this
# module guards against moved planted feet by millimetres per frame.
TOL_MM = 1e-3


def test_coxia_axes_match_the_physical_leg_mounts():
    """The simulator must mount each leg where the robot mounts it.

    generate_poses solves IK around the physical config's `legMountAngle`, and
    VirtualHexapod replays those joint angles around `body.coxia_axes`. When the
    two disagree, every corner leg is rotated about its own mount point, and
    because those mount points differ the planted feet stop moving as one.
    """
    for name in ROBOT_PROFILES:
        hexapod = VirtualHexapod(get_simulator_dimensions(name))
        expected = [a % 360 for a in get_physical_config(name)["legMountAngle"]]
        assert np.allclose(hexapod.body.coxia_axes, expected, atol=0.01), (
            f"{name}: coxia_axes {hexapod.body.coxia_axes} != legMountAngle {expected}"
        )


def test_coxia_axes_of_a_square_body():
    """A body with front == side puts its corner legs on the diagonals."""
    hexapod = VirtualHexapod(BASE_DIMENSIONS)
    assert np.allclose(hexapod.body.coxia_axes, (45, 0, 315, 135, 180, 225))


def _feet(**positions):
    """Named ground contacts at the given (x, y), on the ground."""
    return [Vector(x, y, 0, name=name) for name, (x, y) in positions.items()]


def _twist_angle(old_feet, new_feet):
    """The yaw find_twist_frame would take back out, in degrees."""
    frame = find_twist_frame(old_feet, new_feet)
    return degrees(atan2(frame[1][0], frame[0][0]))


def test_twist_ignores_a_translation():
    """Feet carried in a straight line are the body sliding, not turning."""
    old = _feet(a=(100, 0), b=(-50, 87), c=(-50, -87))
    for shift in ((0, -40), (25, 0), (-13, 7)):
        new = _feet(
            a=(100 + shift[0], 0 + shift[1]),
            b=(-50 + shift[0], 87 + shift[1]),
            c=(-50 + shift[0], -87 + shift[1]),
        )
        assert abs(_twist_angle(old, new)) < 1e-6, f"shift {shift}"


def test_twist_recovers_a_rotation():
    """Feet carried around their own centre are the body turning."""
    old = _feet(a=(100, 0), b=(-50, 87), c=(-50, -87))
    for angle in (-30, -5, 5, 30):
        radians = np.radians(angle)
        rotation = np.array([
            [np.cos(radians), -np.sin(radians)],
            [np.sin(radians), np.cos(radians)],
        ])
        turned = {
            name: tuple(rotation @ np.array([point.x, point.y]))
            for name, point in zip("abc", old)
        }
        # Undoing the turn is what the frame is for, so it comes back negated.
        assert abs(_twist_angle(old, _feet(**turned)) + angle) < 1e-6, f"{angle} deg"


def test_twist_separates_a_rotation_from_a_translation():
    """A turn on top of a slide must yield the turn alone."""
    old = _feet(a=(100, 0), b=(-50, 87), c=(-50, -87))
    radians = np.radians(12)
    rotation = np.array([
        [np.cos(radians), -np.sin(radians)],
        [np.sin(radians), np.cos(radians)],
    ])
    both = {
        name: tuple(rotation @ np.array([point.x, point.y]) + np.array([30, -75]))
        for name, point in zip("abc", old)
    }
    assert abs(_twist_angle(old, _feet(**both)) + 12) < 1e-6


def test_twist_infers_nothing_from_a_single_foot():
    """One shared foot cannot tell a turn from a slide, so neither is assumed."""
    old = _feet(a=(100, 0), b=(-50, 87), c=(-50, -87))
    new = _feet(a=(0, 100), d=(1, 2), e=(3, 4))
    assert abs(_twist_angle(old, new)) < 1e-6


def _stance_runs(motion_name, profile_name):
    """A motion's frames, grouped into runs that share a set of ground contacts."""
    dimensions = get_simulator_dimensions(profile_name)
    runs = []

    for pose in generate_poses(motion_name, profile_name):
        hexapod = VirtualHexapod(dimensions)
        hexapod.update(pose)
        contacts = {p.name: np.array([p.x, p.y]) for p in hexapod.ground_contacts}

        if runs and set(runs[-1][-1]) == set(contacts):
            runs[-1].append(contacts)
        else:
            runs.append([contacts])

    return runs


def _consecutive_stance_frames():
    for profile_name in ROBOT_PROFILES:
        for motion_name in STRAIGHT_GAITS:
            for run in _stance_runs(motion_name, profile_name):
                for before, after in zip(run, run[1:]):
                    yield f"{profile_name}/{motion_name}", before, after


def test_support_polygon_keeps_its_shape():
    """Feet in contact must hold their distances from each other.

    This is the support polygon being a rigid body: the triangle a gait stands
    on may travel, but it may not stretch or shear while the same three feet are
    down.
    """
    for case, before, after in _consecutive_stance_frames():
        for a, b in combinations(before, 2):
            was = np.linalg.norm(before[a] - before[b])
            now = np.linalg.norm(after[a] - after[b])
            assert abs(now - was) < TOL_MM, (
                f"{case}: {a} to {b} went from {was:.4f} to {now:.4f}mm"
            )


def test_planted_feet_move_as_one():
    """Planted feet must displace by the same vector, frame to frame.

    Stronger than the shape test above, which a rotating polygon would also
    satisfy. The model pins the body at the cog, so a gait's world-frame feet
    slide backwards instead of the body advancing forwards; for a gait that walks
    in a straight line that slide has to be a pure translation, with no turn
    mixed in.

    This is what catches a twist that reads a translation as a rotation:
    find_twist_frame measuring off a single planted foot yawed these gaits by up
    to 10.9 degrees, snapping back each time the stance tripod swapped, and that
    put 6 to 17mm between the feet's displacements here.
    """
    for case, before, after in _consecutive_stance_frames():
        deltas = np.array([after[name] - point for name, point in before.items()])
        spread = deltas.max(axis=0) - deltas.min(axis=0)
        assert np.all(spread < TOL_MM), (
            f"{case}: planted feet displaced by differing amounts, "
            f"spread={spread}, deltas={deltas}"
        )


def test_straight_gaits_do_not_yaw_the_body():
    """A gait that walks in a straight line must not turn the body.

    The support-polygon tests above are centroid-relative and would pass on a
    body that yawed with its feet. This pins the yaw itself, read off the head,
    which sits on the +y axis in the body frame.
    """
    for profile_name in ROBOT_PROFILES:
        dimensions = get_simulator_dimensions(profile_name)
        for motion_name in STRAIGHT_GAITS:
            for i, pose in enumerate(generate_poses(motion_name, profile_name)):
                hexapod = VirtualHexapod(dimensions)
                hexapod.update(pose)
                head = hexapod.body.head
                yaw = (degrees(atan2(head.y, head.x)) - 90 + 180) % 360 - 180
                assert abs(yaw) < 0.01, (
                    f"{profile_name}/{motion_name} frame {i}: body yawed {yaw:.3f} deg"
                )
