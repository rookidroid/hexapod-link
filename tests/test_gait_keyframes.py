"""The robot's gaits worked out as keyframes (hexapod/gait_keyframes.py).

A gait put into a sequence is keyframes like any other, and has to play as
the gait: every foot within the tolerance of its own path, at the robot's own
timing, with no seam when the cycle runs round, and every joint within its
limits whatever the speed. Then that it is written in the layers the editor
shows -- the swaying gaits as the body tilting over planted feet.
"""

import numpy as np
import pytest

from hexapod import keyframes as kf
from hexapod import pose_layers as pl
from hexapod.gait_keyframes import ONE_SHOT, TOLERANCE_MM, gait_keyframes, robot_poses
from hexapod.path_generator import generate_poses
from hexapod.robot_config import DEFAULT_CONFIG, get_sequence_fps
from tests.robots import ROBOT_CONFIGS
from widgets.pose_ui import GAIT_MENU, MOTION_TYPES

ROBOTS = list(ROBOT_CONFIGS.values()) + [DEFAULT_CONFIG]
ROBOT_IDS = list(ROBOT_CONFIGS) + ["default"]
GAITS = [option["value"] for option in MOTION_TYPES]
SWAYS = ("rotate_x", "rotate_y", "rotate_z", "twist")


def _gait_feet(motion, robot):
    """The gait's feet as the robot plays it, its joints held to their limits."""
    return np.array([kf.pose_to_feet(pose, robot) for pose in robot_poses(motion, robot)])


@pytest.mark.parametrize("motion", GAITS)
@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_a_gait_plays_its_own_path_at_its_own_timing(robot, motion):
    """Played at the robot's frame rate, a cycle of the keyframes is the gait
    frame for frame, within the tolerance -- ease on, since a gait's
    keyframes are never eased."""
    truth = _gait_feet(motion, robot)
    keyframes = gait_keyframes(motion, robot)
    fps = get_sequence_fps(robot, 100)
    cyclic = motion not in ONE_SHOT
    feet, _, _, _ = pl.sequence(keyframes, robot, fps, loop=cyclic, ease=True)
    feet = np.array(feet)

    assert feet.shape == truth.shape
    assert np.abs(feet - truth).max() <= TOLERANCE_MM + 1e-6
    if cyclic and len(truth) > 1:
        period_ms = 1000.0 / fps
        assert kf.sequence_duration_ms(keyframes, loop=True) == pytest.approx(
            len(truth) * period_ms, abs=len(keyframes)
        )


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_a_walk_cycle_needs_only_some_of_its_frames(robot):
    count = len(gait_keyframes("walk_0", robot))
    assert 4 < count < len(generate_poses("walk_0", robot))


@pytest.mark.parametrize("motion", SWAYS)
@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_a_sway_is_the_body_moving_over_planted_feet(robot, motion):
    """So it is drawn and edited as a tilt, with every foot on the floor,
    rather than as feet swinging through it. What a joint limit takes off the
    sway (Mochi's Twist) is left to the feet, under a millimetre."""
    keyframes = gait_keyframes(motion, robot)
    assert any(
        abs(frame["state"]["body"][key]) > 1
        for frame in keyframes
        for key in ("rot_x", "rot_y", "rot_z")
    )
    for frame in keyframes:
        np.testing.assert_allclose(frame["state"]["offsets"], 0, atol=1.0)
        np.testing.assert_allclose(np.array(pl.view_feet(frame["state"], robot))[:, 2], 0, atol=1.0)
        # And the layers put the feet where the keyframe says.
        np.testing.assert_allclose(pl.body_feet(frame["state"], robot), frame["feet"], atol=0.01)


@pytest.mark.parametrize("motion", ["walk_0", "climb_forward", "fast_forward"])
def test_moving_feet_keep_the_lowest_on_the_floor(motion):
    robot = ROBOT_CONFIGS["nougat"]
    for frame in gait_keyframes(motion, robot):
        heights = np.array(pl.view_feet(frame["state"], robot))[:, 2]
        assert heights.min() == pytest.approx(0, abs=0.05)


def test_gait_keyframes_are_plain_keyframes_that_do_not_ease():
    """Nothing marks where they came from; only their easing, which is any
    keyframe's to set, is off, so the feet keep moving through them."""
    robot = ROBOT_CONFIGS["nougat"]
    keyframes = gait_keyframes("turn_left", robot)
    assert all(set(frame) == {"feet", "duration_ms", "state", "ease"} for frame in keyframes)
    assert not any(kf.eases(frame) for frame in keyframes)

    # A one-off gait is eased into from wherever the sequence was.
    standup = gait_keyframes("standup", robot)
    assert kf.eases(standup[0])
    assert not any(kf.eases(frame) for frame in standup[1:])


def test_two_cycles_in_a_row_run_on_without_a_seam():
    """The first keyframe's time is the move into it from the end of the
    cycle, so a second cycle follows the first as the gait itself does."""
    robot = ROBOT_CONFIGS["nougat"]
    cycle = gait_keyframes("walk_0", robot)
    fps = get_sequence_fps(robot, 100)
    feet, _, _, _ = pl.sequence(cycle + cycle, robot, fps, loop=True)
    truth = _gait_feet("walk_0", robot)
    assert np.abs(np.array(feet) - np.vstack([truth, truth])).max() <= TOLERANCE_MM + 1e-6


@pytest.mark.parametrize("motion", GAITS)
@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_a_gait_stays_within_the_joint_limits_at_any_speed(robot, motion):
    """Some robots' gaits ask a joint for a little more than its limit
    (Mochi's walk does); worked out as keyframes they are held inside it, all
    the way between them too, so the sequence has nothing to refuse whether
    it is previewed or run, slow or fast."""
    keyframes = gait_keyframes(motion, robot)
    loop = motion not in ONE_SHOT
    robot_fps = get_sequence_fps(robot, 100)
    for fps, speed in [(25, 1.0), (robot_fps, 1.0), (robot_fps, 0.33), (robot_fps, 0.75), (robot_fps, 2.0)]:
        _, _, _, bad = pl.sequence(keyframes, robot, fps, loop=loop, speed=speed)
        assert bad == [], (fps, speed)


def test_a_move_of_ones_own_past_a_limit_is_still_caught():
    robot = ROBOT_CONFIGS["mochi"]
    walk = gait_keyframes("walk_0", robot)
    stretched = (np.asarray(kf.standby_feet(robot)) + [0.0, 0.0, -200.0]).tolist()
    _, _, _, bad = pl.sequence(walk + [kf.make_keyframe(stretched, 200)], robot, 50)
    assert bad


def test_the_gait_menu_offers_every_gait_once():
    offered = [motion for _, motions in GAIT_MENU for motion in motions]
    assert sorted(offered) == sorted(GAITS)


@pytest.mark.parametrize("motion", ["rotate_x", "rotate_y", "rotate_z", "twist", "climb_forward", "walk_0"])
@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_a_gait_is_drawn_standing_on_the_floor(robot, motion):
    """Every frame the preview draws of a gait has no foot through the floor
    and at least three on it -- the swaying gaits included, which drawn with
    the body held level used to swing their feet through it."""
    keyframes = gait_keyframes(motion, robot)
    _, states, poses, _ = pl.sequence(keyframes, robot, 25, loop=True)
    for state, pose in zip(states, poses):
        feet = np.array(pl.scene(state, pose, robot)["feet"])
        assert feet[:, 2].min() >= -kf.GROUND_TOLERANCE
        assert (feet[:, 2] <= kf.GROUND_TOLERANCE).sum() >= 3
