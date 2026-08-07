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
# The turns are not here, and cannot be: they sweep each foot along a straight
# chord rather than an arc about the cog, so a planted foot's radius from the
# cog swells towards both ends of the sweep and the support polygon really does
# change size. That is path_tool's own chord primitive showing through, and it
# is the robot's actual behaviour. What the turns owe us instead is that the
# polygon only ever *scales* -- see TURN_GAITS below.
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

# Turning in place. These get the weaker invariant described above.
TURN_GAITS = ["turn_left", "turn_right"]

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


def _consecutive_stance_frames(motions=STRAIGHT_GAITS):
    for profile_name in ROBOT_PROFILES:
        for motion_name in motions:
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


def _ground_contacts(motion_name, profile_name, frame):
    """Where a single frame of a motion puts the feet that are on the ground."""
    hexapod = VirtualHexapod(get_simulator_dimensions(profile_name))
    hexapod.update(generate_poses(motion_name, profile_name)[frame])
    return {p.name: np.array([p.x, p.y, p.z]) for p in hexapod.ground_contacts}


def test_standup_ends_in_the_standby_stance():
    """Standing up must finish exactly where standing by starts.

    gen_standup_path walks each leg inward along a lift-and-place arc aimed by
    that leg's azimuth. Hardcoding the corner azimuths at 45deg -- right only
    for a body with front == side -- landed every corner foot 9.4mm (mochi) to
    13.5mm (macaroon) away from its standby spot, about 5deg of coxia. Nothing
    scuffs on the way, since the arc lifts each foot clear before moving it; the
    cost is that the boot sequence ends in a stance the robot never asked for,
    and the corner legs then snap those 12 servo ticks across to standby the
    moment anything else is commanded.
    """
    for profile_name in ROBOT_PROFILES:
        landed = _ground_contacts("standup", profile_name, -1)
        standing_by = _ground_contacts("standby", profile_name, 0)
        assert set(landed) == set(standing_by), (
            f"{profile_name}: standup ends on {sorted(landed)}, "
            f"standby stands on {sorted(standing_by)}"
        )
        for name, point in standing_by.items():
            off = np.linalg.norm(landed[name] - point)
            assert off < TOL_MM, (
                f"{profile_name}: {name} landed {off:.3f}mm off its standby spot"
            )


def test_standup_never_drags_a_planted_foot():
    """And it must get there without scuffing.

    The arc lifts a foot clear of the ground before moving it and the tripods
    take turns, so a foot that is down stays put -- not merely rigid with its
    neighbours, as in the gaits above, but motionless. This is why the misaimed
    corner azimuths were a landing error rather than a drag, and it has to hold
    however the offsets are aimed.
    """
    for case, before, after in _consecutive_stance_frames(["standup"]):
        for name, point in before.items():
            moved = np.linalg.norm(after[name] - point)
            assert moved < TOL_MM, f"{case}: {name} dragged {moved:.3f}mm while planted"


def test_straight_gaits_do_not_yaw_the_body():
    """A gait that walks in a straight line must not turn the body.


def test_turn_support_polygon_stays_similar():
    """A turn's planted feet may change scale, but not shape.

    The chord stroke makes each planted foot's radius from the cog swell a few
    millimetres towards both ends of the sweep, so the support triangle breathes
    -- that much is path_tool's primitive and the robot does it too. What must
    not happen is the triangle shearing, because that means the feet are being
    pushed along strokes that are not tangent to the turn circle. Aiming each
    stroke by its leg's own azimuth is what buys this: with the corner strokes
    mis-aimed by 15deg the side ratios drifted by ~2e-2, and each planted foot
    was dragged some 22mm in and out per stance.
    """
    for case, before, after in _consecutive_stance_frames(TURN_GAITS):
        was, now = _sides(before), _sides(after)
        drift = np.abs(now / now.mean() - was / was.mean()).max()
        assert drift < 1e-5, f"{case}: support triangle sheared, side ratios moved {drift:.2e}"


def test_turn_support_polygon_only_breathes_slightly():
    """And the scale change the turn is allowed must stay small.

    A bound on the dilation the chord stroke costs, so that "only scales" cannot
    be satisfied by a path that scales absurdly.
    """
    for profile_name in ROBOT_PROFILES:
        for motion_name in TURN_GAITS:
            for run in _stance_runs(motion_name, profile_name):
                scales = np.array([_sides(frame).mean() for frame in run])
                swing = scales.max() / scales.min() - 1
                assert swing < 0.02, (
                    f"{profile_name}/{motion_name}: support triangle scaled by "
                    f"{swing:.2%} while the same feet were planted"
                )
