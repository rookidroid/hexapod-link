"""The gaits' foot paths (hexapod/path_generator.py), as the simulator draws
them: the leg mounts it poses the legs around, and how the feet on the floor
move while they stay down.
"""

from itertools import combinations

import numpy as np
import pytest

from hexapod.models import VirtualHexapod
from hexapod.path_generator import generate_poses
from hexapod.robot_config import get_simulator_dimensions
from tests.robots import ROBOT_CONFIGS

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

# The robots' `side` is a rounded value -- macaroon's 85.22 stands in for
# 49.2 * tan(60deg) = 85.2169 -- which tilts each mount azimuth by under a
# thousandth of a degree and leaves a sub-micron residue in the numbers below.
# A micron of slack absorbs it while still catching anything real: the bugs
# this module guards against moved planted feet by millimetres per frame.
TOL_MM = 1e-3


def test_coxia_axes_match_the_physical_leg_mounts():
    """The simulator must mount each leg where the robot mounts it.

    generate_poses and the workspace solve IK around the physical config's
    `legMountAngle`, and VirtualHexapod draws those joint angles around
    `body.coxia_axes`. When the two disagree, every leg is drawn rotated about
    its own mount point, away from where the robot puts its foot.
    """
    for name, robot in ROBOT_CONFIGS.items():
        hexapod = VirtualHexapod(get_simulator_dimensions(robot))
        expected = [a % 360 for a in robot["config"]["legMountAngle"]]
        assert np.allclose(hexapod.body.coxia_axes, expected, atol=0.01), (
            f"{name}: coxia_axes {hexapod.body.coxia_axes} != legMountAngle {expected}"
        )


def test_nougat_legs_are_not_radial():
    """Why the robot's mount angles are passed to the simulator at all.

    Mochi and Macaroon mount every leg pointing straight out from the cog, so
    their legMountAngle is the azimuth of the mount point. Nougat's corner legs
    are angled at 45 degrees while sitting at about 59, and a model that assumed
    radial legs would twist each of them 14 degrees off the robot.
    """
    for name, robot in ROBOT_CONFIGS.items():
        radial = VirtualHexapod(get_simulator_dimensions(robot, mount_angles=False))
        expected = [a % 360 for a in robot["config"]["legMountAngle"]]
        worst = max(abs(a - b) for a, b in zip(radial.body.coxia_axes, expected))
        if name == "nougat":
            assert worst == pytest.approx(59.07 - 45, abs=0.05)
        else:
            assert worst < 0.01, f"{name}: legs should be radial"


def test_coxia_axes_of_a_square_body():
    """A body with front == side puts its corner legs on the diagonals."""
    hexapod = VirtualHexapod(
        {"front": 100, "side": 100, "middle": 100, "coxia": 100, "femur": 100, "tibia": 100}
    )
    assert np.allclose(hexapod.body.coxia_axes, (45, 0, 315, 135, 180, 225))


def _foot_frames(motion_name, profile_name):
    """Each frame of a motion as the simulator draws it: the six foot tips in
    the body frame, posed by the simulator's linkage from the gait's joint
    angles."""
    robot = ROBOT_CONFIGS[profile_name]
    hexapod = VirtualHexapod(get_simulator_dimensions(robot))
    frames = []
    for pose in generate_poses(motion_name, robot):
        for leg_id, joints in pose.items():
            hexapod.legs[leg_id].change_pose(joints["coxia"], joints["femur"], joints["tibia"])
        frames.append(np.array([[f.x, f.y, f.z] for f in (leg.foot_tip() for leg in hexapod.legs)]))
    return frames


def _planted(feet):
    """The feet on the floor, by leg, with the floor at z = 0 under the lowest.

    The body is level in every gait checked here, so the floor is the plane of
    the lowest feet, and a foot on it does not move while it stays down.
    """
    floor = feet[:, 2].min()
    return {
        leg: feet[leg] - [0.0, 0.0, floor]
        for leg in range(6)
        if feet[leg, 2] - floor < TOL_MM
    }


def _stance_runs(motion_name, profile_name):
    """A motion's frames, grouped into runs that share a set of planted feet."""
    runs = []
    for feet in _foot_frames(motion_name, profile_name):
        contacts = _planted(feet)
        if runs and set(runs[-1][-1]) == set(contacts):
            runs[-1].append(contacts)
        else:
            runs.append([contacts])
    return runs


def _consecutive_stance_frames(motions=STRAIGHT_GAITS):
    for profile_name in ROBOT_CONFIGS:
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
    satisfy. In the body frame a walk's planted feet slide backwards under the
    body; for a gait that walks in a straight line that slide has to be a pure
    translation, with no turn mixed in, or the body would yaw as it walks.
    """
    for case, before, after in _consecutive_stance_frames():
        deltas = np.array([after[leg] - point for leg, point in before.items()])
        spread = deltas.max(axis=0) - deltas.min(axis=0)
        assert np.all(spread < TOL_MM), (
            f"{case}: planted feet displaced by differing amounts, "
            f"spread={spread}, deltas={deltas}"
        )


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
    for profile_name in ROBOT_CONFIGS:
        landed = _foot_frames("standup", profile_name)[-1]
        standing_by = _foot_frames("standby", profile_name)[0]
        off = np.linalg.norm(landed - standing_by, axis=1)
        assert np.all(off < TOL_MM), (
            f"{profile_name}: feet landed {np.round(off, 3)}mm off their standby spots"
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
        for leg, point in before.items():
            moved = np.linalg.norm(after[leg] - point)
            assert moved < TOL_MM, f"{case}: leg {leg} dragged {moved:.3f}mm while planted"


def _sides(contacts):
    """The pairwise distances of a stance, in a stable order."""
    names = sorted(contacts)
    return np.array(
        [np.linalg.norm(contacts[a] - contacts[b]) for a, b in combinations(names, 2)]
    )


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

    That holds exactly only where the planted feet stand at equal radii from the
    cog, as on Mochi and Macaroon: the chord swells each foot's radius by an
    amount that depends on that radius. Nougat's feet stand at unequal radii, so
    its triangle shears very slightly (~1e-3) -- still twenty times less than
    the mis-aimed strokes did, and the robot's own turn LUT does the same.
    """
    for case, before, after in _consecutive_stance_frames(TURN_GAITS):
        was, now = _sides(before), _sides(after)
        drift = np.abs(now / now.mean() - was / was.mean()).max()
        bound = 2e-3 if case.startswith("nougat/") else 1e-5
        assert drift < bound, f"{case}: support triangle sheared, side ratios moved {drift:.2e}"


def test_turn_support_polygon_only_breathes_slightly():
    """And the scale change the turn is allowed must stay small.

    A bound on the dilation the chord stroke costs, so that "only scales" cannot
    be satisfied by a path that scales absurdly.
    """
    for profile_name in ROBOT_CONFIGS:
        for motion_name in TURN_GAITS:
            for run in _stance_runs(motion_name, profile_name):
                scales = np.array([_sides(frame).mean() for frame in run])
                swing = scales.max() / scales.min() - 1
                assert swing < 0.02, (
                    f"{profile_name}/{motion_name}: support triangle scaled by "
                    f"{swing:.2%} while the same feet were planted"
                )
