"""The gait generator, ported from path_tool.

test_motion.py already checks what these paths do once a VirtualHexapod walks
them -- feet not dragging, the body not yawing. What is checked here is the
layer underneath: that every motion the UI offers produces a well-formed pose at
all, that the Cartesian-to-joint conversion is the exact inverse of the posture
builder it is paired with, and that the two robots really do get different paths.
"""

import numpy as np
import pytest

from hexapod.naming import LEG_NAMES
from hexapod.path_generator import (
    gen_posture,
    generate_poses,
    inverse_kinematics,
    path_rotate_z,
    semicircle_generator,
)
from hexapod.robot_profiles import ROBOT_PROFILES, get_physical_config, get_profile
from widgets.motion_ui import MOTION_TYPES

UI_MOTIONS = [option["value"] for option in MOTION_TYPES]

# Every gait is baked at 28 frames; only standby is a single held posture.
GAIT_STEPS = 28


def test_every_motion_the_ui_offers_generates_poses():
    """A motion in the dropdown that generates nothing is a dead menu entry."""
    for profile_name in ROBOT_PROFILES:
        for motion_name in UI_MOTIONS:
            poses = generate_poses(motion_name, profile_name)
            assert len(poses) > 0, f"{profile_name}/{motion_name} generated no frames"


def test_poses_are_well_formed():
    """Every frame poses all six legs, keyed by leg id, with all three joints.

    VirtualHexapod.update indexes straight into this, so a missing leg or a
    renamed key is an error a long way from here.
    """
    for profile_name in ROBOT_PROFILES:
        for motion_name in UI_MOTIONS:
            for i, pose in enumerate(generate_poses(motion_name, profile_name)):
                where = f"{profile_name}/{motion_name} frame {i}"
                assert set(pose) == set(range(6)), f"{where}: legs {sorted(pose)}"
                for leg_id, entry in pose.items():
                    assert entry["id"] == leg_id, f"{where}: leg {leg_id} id mismatch"
                    assert entry["name"] == LEG_NAMES[leg_id], f"{where}: leg name"
                    for joint in ("coxia", "femur", "tibia"):
                        assert np.isfinite(entry[joint]), f"{where}: {joint} not finite"


def test_gaits_are_baked_at_a_fixed_frame_count():
    """The robot's LUTs are this long, so a streamed gait has to match them."""
    for profile_name in ROBOT_PROFILES:
        assert len(generate_poses("standby", profile_name)) == 1
        for motion_name in UI_MOTIONS:
            if motion_name == "standby":
                continue
            assert len(generate_poses(motion_name, profile_name)) == GAIT_STEPS, (
                f"{profile_name}/{motion_name} is not {GAIT_STEPS} frames"
            )


def test_an_unknown_motion_falls_back_to_standby():
    """The UI can hold a stale motion name; that must hold the pose, not raise."""
    for profile_name in ROBOT_PROFILES:
        standby = generate_poses("standby", profile_name)
        assert generate_poses("no-such-motion", profile_name) == standby


def test_generation_is_deterministic():
    """Two runs of a gait must agree, or streaming would jitter between frames."""
    for motion_name in ("walk_0", "turn_left", "standup"):
        assert generate_poses(motion_name, "mochi") == generate_poses(
            motion_name, "mochi"
        )


def test_the_two_robots_get_different_paths():
    """A path baked for one robot's geometry is wrong for the other's.

    This is the reason generate_poses takes a profile at all, so it is worth
    pinning that the argument actually reaches the geometry.
    """
    mochi = generate_poses("walk_0", "mochi")
    macaroon = generate_poses("walk_0", "macaroon")
    assert mochi[0][0]["femur"] != macaroon[0][0]["femur"]


def test_inverse_kinematics_inverts_the_standby_posture():
    """The round trip that the whole generator rests on.

    gen_posture places the feet for a pair of joint angles; inverse_kinematics
    reads joint angles back off foot positions. Every gait is built by perturbing
    standby and running the latter, so an error here is inherited by every motion.

    This is *not* a general inverse. gen_posture measures j3 from the horizontal
    while the IK closes the two-link triangle, so the two only coincide where the
    posture happens to satisfy that closure -- (60, 75) and (70, 80) do, while
    (25, 25), (45, 90) and (50, 60) come back with a different j3. Standby is the
    one the gaits are built from, so it is the one pinned here; see
    test_laydown_is_not_a_fixed_point_of_the_round_trip for the other end.

    The left legs come back mirrored (180 - angle), which is legScale doing its
    job -- their servos face the other way.
    """
    for profile_name in ROBOT_PROFILES:
        config = get_physical_config(profile_name)
        j2, j3 = get_profile(profile_name)["gait"]["standby_posture"]
        angles = inverse_kinematics(gen_posture(j2, j3, config), config)

        for leg_id in range(3):
            assert angles[leg_id] == pytest.approx([90, j2, j3], abs=1e-9), (
                f"{profile_name}: right leg {leg_id} did not round trip"
            )
        for leg_id in range(3, 6):
            assert angles[leg_id] == pytest.approx(
                [90, 180 - j2, 180 - j3], abs=1e-9
            ), f"{profile_name}: left leg {leg_id} did not round trip"


def test_laydown_is_not_a_fixed_point_of_the_round_trip():
    """Documents the limit of the inverse above, so it is not mistaken for one.

    Laydown (25, 25) is a far more extended leg than standby, and the IK reads it
    back as j3 = 90. That is harmless where it is used -- laydown is only the
    *start* of gen_standup_path, and test_motion.py pins that the sequence still
    ends exactly on standby -- but it means this pair is not interchangeable with
    the standby pair, and a future gait built off laydown cannot assume it is.
    """
    for profile_name in ROBOT_PROFILES:
        config = get_physical_config(profile_name)
        j2, j3 = get_profile(profile_name)["gait"]["laydown_posture"]
        angles = inverse_kinematics(gen_posture(j2, j3, config), config)

        assert angles[0][1] == pytest.approx(j2, abs=1e-9), "femur should round trip"
        assert angles[0][2] != pytest.approx(j3, abs=1e-6), (
            "laydown now round trips; the inverse above can be generalised"
        )


def test_a_posture_stands_level():
    """Both postures put every foot at the same height, which is what makes them
    a stance rather than a pose mid-stride."""
    for profile_name in ROBOT_PROFILES:
        config = get_physical_config(profile_name)
        gait = get_profile(profile_name)["gait"]
        for posture_name in ("standby_posture", "laydown_posture"):
            posture = gen_posture(*gait[posture_name], config)
            assert posture.shape == (6, 3)
            spread = posture[:, 2].max() - posture[:, 2].min()
            assert spread == pytest.approx(0, abs=1e-9), (
                f"{profile_name}/{posture_name} is not level"
            )


def test_laydown_sits_lower_than_standby():
    """Standing up is the move between them, so the order has to be this way."""
    for profile_name in ROBOT_PROFILES:
        config = get_physical_config(profile_name)
        gait = get_profile(profile_name)["gait"]
        standby = gen_posture(*gait["standby_posture"], config)
        laydown = gen_posture(*gait["laydown_posture"], config)
        assert laydown[0, 2] > standby[0, 2], (
            f"{profile_name}: laydown is not above standby in foot-frame z"
        )


def test_semicircle_lifts_the_foot_without_sideways_drift():
    """The swing half arcs up; the stance half is a straight line on the ground.

    The stroke is built in the leg's own frame and rotated into place later, so
    at this stage it has to stay in the y-z plane.
    """
    radius, steps = 30, GAIT_STEPS
    path = semicircle_generator(radius, steps)

    assert path.shape == (steps, 3)
    assert np.allclose(path[:, 0], 0), "the stroke drifted in x"
    assert path[:, 2].min() == pytest.approx(0), "the foot went below the ground"
    assert path[:, 2].max() == pytest.approx(radius), "the lift is not the radius"
    assert path[:, 1].min() == pytest.approx(-radius)
    assert path[:, 1].max() == pytest.approx(radius)

    # Exactly half the frames are on the ground -- this is what makes the gait a
    # tripod, with one set planted while the other swings.
    assert np.count_nonzero(path[:, 2] == 0) == steps // 2


def test_semicircle_reverse_is_the_forward_stroke_backwards():
    """Walking backwards must retrace the same foot path, not a different one."""
    forward = semicircle_generator(30, GAIT_STEPS)
    reverse = semicircle_generator(30, GAIT_STEPS, reverse=True)
    assert np.allclose(sorted(forward[:, 1]), sorted(reverse[:, 1]))
    assert np.allclose(sorted(forward[:, 2]), sorted(reverse[:, 2]))


def test_semicircle_requires_a_step_count_it_can_quarter():
    """It rolls by steps/4 to phase the tripods, so the count must divide by four."""
    for steps in (27, 26, 30):
        with pytest.raises(AssertionError):
            semicircle_generator(30, steps)


def test_path_rotate_z_turns_the_stroke_in_the_ground_plane():
    """Directional walking is the forward stroke rotated, so this must be a
    rotation: lengths preserved, height untouched."""
    path = semicircle_generator(30, GAIT_STEPS)
    turned = np.array(path_rotate_z(path, 90))

    assert np.allclose(
        np.linalg.norm(path[:, :2], axis=1), np.linalg.norm(turned[:, :2], axis=1)
    ), "rotation changed the stroke's radius"
    assert np.allclose(path[:, 2], turned[:, 2]), "rotation changed the foot height"

    # A quarter turn takes +y to +x.
    assert np.allclose(np.array(path_rotate_z(path, 360)), path, atol=1e-9)


def test_opposite_walks_swap_the_legs_rather_than_negate_one():
    """walk_0 and walk_180 are the same stroke aimed the other way.

    The mirror is across the body, not within a leg: walking backwards, the
    front-right leg's share of the stroke is the one the rear-right leg takes
    walking forwards. So leg 0's coxia sweep going forwards is leg 2's negated
    sweep going backwards -- and *not* its own negated sweep, which is what a
    per-leg mirror would predict.
    """
    forward = generate_poses("walk_0", "mochi")
    backward = generate_poses("walk_180", "mochi")

    def coxia_sweep(poses, leg_id, sign=1):
        return sorted(round(sign * pose[leg_id]["coxia"], 6) for pose in poses)

    assert coxia_sweep(forward, 0) == coxia_sweep(backward, 2, -1), (
        "front-right walking forwards should mirror rear-right walking backwards"
    )
    assert coxia_sweep(forward, 0) != coxia_sweep(backward, 0, -1), (
        "a leg is not its own mirror under a reversed walk"
    )


def test_opposite_walks_sweep_the_same_range():
    """Whichever way it walks, a leg covers the same coxia travel.

    Cheap guard that `direction` reaches the generator as a rotation rather than
    changing the size of the stroke.
    """
    forward = [pose[0]["coxia"] for pose in generate_poses("walk_0", "mochi")]
    backward = [pose[0]["coxia"] for pose in generate_poses("walk_180", "mochi")]

    assert min(forward) == pytest.approx(min(backward))
    assert max(forward) == pytest.approx(max(backward))
