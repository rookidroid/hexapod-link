from itertools import combinations

import numpy as np

from hexapod.const import BASE_DIMENSIONS
from hexapod.models import VirtualHexapod
from hexapod.path_generator import generate_poses
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


def _stance_runs(motion_name, profile_name):
    """A motion's frames, grouped into runs that share a set of ground contacts."""
    dimensions = get_simulator_dimensions(profile_name)
    runs = []

    for pose in generate_poses(motion_name, profile_name):
        hexapod = VirtualHexapod(dimensions)
        hexapod.update(pose, twist_body=False)
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

    The model pins the body at the origin, so a gait's world-frame feet slide
    backwards instead of the body advancing forwards. For a gait that walks in a
    straight line that slide has to be a pure translation of the whole support
    polygon.
    """
    for case, before, after in _consecutive_stance_frames():
        deltas = np.array([after[name] - point for name, point in before.items()])
        spread = deltas.max(axis=0) - deltas.min(axis=0)
        assert np.all(spread < TOL_MM), (
            f"{case}: planted feet displaced by differing amounts, "
            f"spread={spread}, deltas={deltas}"
        )
