"""The pose page's keyframes: solving joints from feet and back, and timing.

The page places feet in the path tool's body frame and draws them with the
simulator's linkage model, so the first thing checked is that those two agree:
a foot solved by one lands where the other draws it, and a pose set by joint
angles (the body's sliders, a leg's fields) turns into feet that solve back to it. The
rest covers what a sequence turns into on its way to the robot.
"""

import json

import numpy as np
import pytest

from hexapod.keyframes import (
    MAX_DURATION_MS,
    MIN_DURATION_MS,
    KeyframeFileError,
    dump,
    feet_to_pose,
    frame_times,
    ground_height,
    interpolate,
    interpolate_feet,
    keyframe_times_ms,
    load,
    make_keyframe,
    pose_to_feet,
    pose_to_scene,
    sequence_duration_ms,
    standby_feet,
)
from hexapod.ik_solver.ik_solver2 import solve_inverse_kinematics
from hexapod.models import VirtualHexapod
from hexapod.path_generator import generate_poses
from hexapod.robot_config import get_simulator_dimensions
from pages.helpers import make_pose
from hexapod.robot_config import GENERIC_CONFIG, get_sequence_fps
from tests.robots import ROBOT_CONFIGS

ROBOTS = list(ROBOT_CONFIGS.values()) + [GENERIC_CONFIG]
ROBOT_IDS = list(ROBOT_CONFIGS) + ["generic"]


def lifted(feet, leg, dz):
    feet = [list(foot) for foot in feet]
    feet[leg][2] += dz
    return feet


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_standby_feet_round_trip_through_the_simulator(robot):
    feet = standby_feet(robot)
    pose, bad = feet_to_pose(feet, robot)
    assert bad == []
    scene = pose_to_scene(pose, robot)
    np.testing.assert_allclose(scene["feet"], feet, atol=1e-2)


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_moved_feet_round_trip_through_the_simulator(robot):
    feet = np.array(standby_feet(robot))
    feet[0] += [10, 15, 20]
    feet[4] += [-12, 8, 5]
    pose, bad = feet_to_pose(feet, robot)
    assert bad == []
    np.testing.assert_allclose(pose_to_scene(pose, robot)["feet"], feet, atol=1e-2)


def assert_same_pose(actual, expected, atol=1e-2):
    for leg_id in range(6):
        for joint in ("coxia", "femur", "tibia"):
            assert actual[leg_id][joint] == pytest.approx(expected[leg_id][joint], abs=atol)


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_feet_round_trip_through_their_pose(robot):
    feet = np.array(standby_feet(robot))
    feet[2] += [8, -6, 25]
    pose, bad = feet_to_pose(feet, robot)
    assert bad == []
    np.testing.assert_allclose(pose_to_feet(pose, robot), feet, atol=1e-2)


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_body_pose_survives_the_trip_through_feet(robot):
    # What moving the body does: solve a tilted, shifted body, keep it as feet,
    # and solve the joints back from those for the readout and the robot.
    parameters = {
        "hip_stance": 0,
        "leg_stance": 0,
        "percent_x": 0.1,
        "percent_y": -0.1,
        "percent_z": 0.05,
        "rot_x": 6,
        "rot_y": -4.5,
        "rot_z": 3,
    }
    hexapod = VirtualHexapod(get_simulator_dimensions(robot))
    poses, _, _ = solve_inverse_kinematics(hexapod, parameters)
    pose, bad = feet_to_pose(pose_to_feet(poses, robot), robot)
    assert bad == []
    assert_same_pose(pose, poses)


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_leg_pattern_survives_the_trip_through_feet(robot):
    poses = make_pose(5, 20, -10, {leg: {} for leg in range(6)})
    pose, bad = feet_to_pose(pose_to_feet(poses, robot), robot)
    assert bad == []
    assert_same_pose(pose, poses)


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_standby_feet_solve_to_the_standby_motion(robot):
    pose, _ = feet_to_pose(standby_feet(robot), robot)
    expected = generate_poses("standby", robot)[0]
    for leg_id in range(6):
        for joint in ("coxia", "femur", "tibia"):
            assert pose[leg_id][joint] == pytest.approx(expected[leg_id][joint], abs=1e-2)


def test_unreachable_foot_is_reported():
    robot = ROBOT_CONFIGS["nougat"]
    feet = np.array(standby_feet(robot))
    feet[2] *= 10
    _, bad = feet_to_pose(feet, robot)
    assert bad == [2]


def test_foot_past_a_joint_limit_is_reported():
    robot = ROBOT_CONFIGS["mochi"]
    feet = np.array(standby_feet(robot))
    # Swinging the foot round towards its neighbour turns the coxia well past
    # its 45 degree limit while staying within reach.
    x, y, z = feet[1]
    radius = np.hypot(x, y)
    feet[1] = [radius * np.cos(np.radians(70)), radius * np.sin(np.radians(70)), z]
    _, bad = feet_to_pose(feet, robot)
    assert bad == [1]


def test_scene_marks_lifted_feet_off_the_ground():
    robot = ROBOT_CONFIGS["nougat"]
    feet = lifted(standby_feet(robot), 3, 30)
    pose, _ = feet_to_pose(feet, robot)
    scene = pose_to_scene(pose, robot)
    assert len(scene["support"]) == 5
    assert all(point[2] == ground_height(robot) for point in scene["support"])
    assert len(scene["legs"]) == 6 and all(len(leg) == 4 for leg in scene["legs"])
    # The scene goes to the browser as JSON.
    json.dumps(scene)


def test_interpolation_frame_count_and_end_points():
    robot = ROBOT_CONFIGS["nougat"]
    start = standby_feet(robot)
    end = lifted(start, 0, 40)
    keyframes = [make_keyframe(start, 500), make_keyframe(end, 500)]

    frames = interpolate_feet(keyframes, fps=20)
    assert len(frames) == 1 + 10
    np.testing.assert_allclose(frames[0], keyframes[0]["feet"])
    np.testing.assert_allclose(frames[-1], keyframes[1]["feet"])
    # Eased: the first step is smaller than the middle one.
    lift = [frame[0][2] - start[0][2] for frame in frames]
    assert lift[1] - lift[0] < lift[6] - lift[5]


def test_looping_closes_the_seam_without_repeating_the_first_frame():
    robot = ROBOT_CONFIGS["nougat"]
    start = standby_feet(robot)
    end = lifted(start, 0, 40)
    keyframes = [make_keyframe(start, 250), make_keyframe(end, 500)]

    frames = interpolate_feet(keyframes, fps=20, loop=True, ease=False)
    # 10 frames out, 5 back of which the last would be the first again.
    assert len(frames) == 1 + 10 + 4
    np.testing.assert_allclose(frames[10], keyframes[1]["feet"])
    assert frames[-1][0][2] == pytest.approx(start[0][2] + 40 / 5, abs=1e-2)


def test_single_keyframe_is_one_frame():
    robot = ROBOT_CONFIGS["mochi"]
    keyframes = [make_keyframe(standby_feet(robot))]
    assert len(interpolate_feet(keyframes, fps=50, loop=True)) == 1
    assert interpolate_feet([], fps=50) == []


def test_interpolate_reports_frames_that_pass_out_of_reach():
    robot = ROBOT_CONFIGS["nougat"]
    start = standby_feet(robot)
    poses, bad = interpolate([make_keyframe(start)], robot, fps=50)
    assert len(poses) == 1 and bad == []

    far = [list(foot) for foot in start]
    far[5] = [c * 10 for c in far[5]]
    _, bad = interpolate([make_keyframe(start), make_keyframe(far, 100)], robot, fps=50)
    assert bad and bad[-1] == 5


def test_poses_play_on_the_robot_link():
    from hexapod.robot_link import pose_to_ticks

    robot = ROBOT_CONFIGS["macaroon"]
    start = standby_feet(robot)
    keyframes = [make_keyframe(start), make_keyframe(lifted(start, 1, 20), 300)]
    fps = get_sequence_fps(robot)
    poses, bad = interpolate(keyframes, robot, fps=fps)
    assert bad == []
    assert len(poses) == 1 + round(0.3 * fps)
    assert all(len(pose_to_ticks(pose, robot)) == 18 for pose in poses)


def test_durations_are_clamped_and_summed():
    feet = standby_feet(GENERIC_CONFIG)
    assert make_keyframe(feet, 1)["duration_ms"] == MIN_DURATION_MS
    assert make_keyframe(feet, 10**9)["duration_ms"] == MAX_DURATION_MS
    assert make_keyframe(feet, None)["duration_ms"] == 500

    keyframes = [make_keyframe(feet, 100), make_keyframe(feet, 200), make_keyframe(feet, 300)]
    assert sequence_duration_ms(keyframes) == 500
    assert sequence_duration_ms(keyframes, loop=True) == 600
    assert sequence_duration_ms([]) == 0


def test_file_round_trip():
    robot = ROBOT_CONFIGS["mochi"]
    start = standby_feet(robot)
    keyframes = [make_keyframe(start, 400), make_keyframe(lifted(start, 2, 25), 700)]
    assert load(dump(keyframes, robot), robot) == keyframes


def test_file_for_another_robot_is_refused():
    text = dump([make_keyframe(standby_feet(ROBOT_CONFIGS["mochi"]))], ROBOT_CONFIGS["mochi"])
    with pytest.raises(KeyframeFileError, match="mochi"):
        load(text, ROBOT_CONFIGS["nougat"])


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        json.dumps([1, 2, 3]),
        json.dumps({"format": "something-else"}),
        json.dumps({"format": "hexapod-link-keyframes", "version": 99, "robot": "nougat"}),
        json.dumps({"format": "hexapod-link-keyframes", "version": 1, "robot": "nougat"}),
        json.dumps(
            {
                "format": "hexapod-link-keyframes",
                "version": 1,
                "robot": "nougat",
                "keyframes": [{"feet": [[0, 0, 0]] * 5, "duration_ms": 100}],
            }
        ),
        json.dumps(
            {
                "format": "hexapod-link-keyframes",
                "version": 1,
                "robot": "nougat",
                "keyframes": [{"feet": [[0, 0, 0]] * 6}],
            }
        ),
    ],
)
def test_malformed_files_are_refused(text):
    with pytest.raises(KeyframeFileError):
        load(text, ROBOT_CONFIGS["nougat"])


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_stored_feet_hold_no_negative_zero(robot):
    # dcc.Store tells -0 from 0 but JSON does not, so a -0 in a session store
    # has it rewriting itself forever; see clean_feet().
    def has_negative_zero(values):
        return any(str(c) == "-0.0" for foot in values for c in foot)

    assert has_negative_zero([[-0.0, 1.0, 2.0]])
    assert not has_negative_zero(standby_feet(robot))
    assert not has_negative_zero(make_keyframe([[-0.0, -0.0, -0.0]] * 6)["feet"])
    pose, _ = feet_to_pose(standby_feet(robot), robot)
    assert not has_negative_zero(pose_to_scene(pose, robot)["legs"][4])


def test_a_keyframe_can_be_moved_into_without_easing():
    """Each keyframe says whether the move into it eases: one that does not
    (as a gait's) is reached at a steady speed, one that does gently."""
    robot = ROBOT_CONFIGS["nougat"]
    start = np.asarray(standby_feet(robot))
    end = start + [0.0, 20.0, 0.0]
    steady = [make_keyframe(start.tolist()), make_keyframe(end.tolist(), 500, ease=False)]
    gentle = [make_keyframe(start.tolist()), make_keyframe(end.tolist(), 500)]

    def y_steps(keyframes):
        ys = np.array(interpolate_feet(keyframes, fps=20, ease=True))[:, 0, 1]
        return np.diff(ys)

    np.testing.assert_allclose(y_steps(steady), 2.0)
    assert y_steps(gentle)[0] < y_steps(gentle)[5]


def test_speed_scales_the_whole_sequence():
    feet = standby_feet(ROBOT_CONFIGS["nougat"])
    keyframes = [make_keyframe(feet, 100), make_keyframe(feet, 400), make_keyframe(feet, 600)]
    assert sequence_duration_ms(keyframes, speed=2.0) == 500
    assert sequence_duration_ms(keyframes, loop=True, speed=0.5) == 2200
    assert len(interpolate_feet(keyframes, fps=20, speed=2.0)) == 1 + 4 + 6
    assert len(interpolate_feet(keyframes, fps=20)) == 1 + 8 + 12


def test_a_keyframes_easing_is_saved_and_loaded():
    robot = ROBOT_CONFIGS["nougat"]
    feet = standby_feet(robot)
    keyframes = [make_keyframe(feet, 300), make_keyframe(feet, 24, ease=False)]
    loaded = load(dump(keyframes, robot), robot)
    assert "ease" not in loaded[0]
    assert loaded[1]["ease"] is False

    document = json.loads(dump(keyframes, robot))
    document["keyframes"][1]["ease"] = "no"
    with pytest.raises(KeyframeFileError):
        load(json.dumps(document), robot)


def test_moves_shorter_than_a_frame_keep_their_time():
    """A gait's keyframes are a frame or two of the robot's apart, far less
    than one of the preview's: the preview then skips between them rather
    than giving each a frame of its own and playing slower."""
    feet = standby_feet(ROBOT_CONFIGS["nougat"])
    keyframes = [make_keyframe(feet, 12, ease=False) for _ in range(30)]
    frames = interpolate_feet(keyframes, fps=25, loop=True)
    assert len(frames) == round(30 * 0.012 * 25)
    assert len(interpolate_feet(keyframes, fps=25, loop=True, speed=0.5)) == round(30 * 0.024 * 25)


@pytest.mark.parametrize("loop", [False, True])
def test_every_frame_knows_where_it_falls_in_the_keyframes_time(loop):
    """So a frame playback comes to rest on can be put back into the sequence
    where it was: on the move from one keyframe to the next, so far in, in
    the keyframes' own time whatever the playback speed."""
    feet = standby_feet(ROBOT_CONFIGS["nougat"])
    keyframes = [make_keyframe(feet, 100), make_keyframe(feet, 400), make_keyframe(feet, 200)]
    for speed in (1.0, 2.0):
        times = frame_times(keyframes, fps=20, loop=loop, speed=speed)
        assert len(times) == len(interpolate_feet(keyframes, fps=20, loop=loop, speed=speed))
        assert times[0] == (0, 0, 0.0)
        # Half way through the 400 ms move into the second keyframe.
        assert (0, 1, pytest.approx(200.0)) in [(s, e, ms) for s, e, ms in times]
        if not loop:
            assert times[-1] == (1, 2, pytest.approx(200.0))
    if loop:
        # The move back round to the first keyframe has frames of its own.
        assert frame_times(keyframes, fps=20, loop=True)[-1] == (2, 0, pytest.approx(50.0))


def test_keyframe_times_add_up_the_moves():
    feet = standby_feet(ROBOT_CONFIGS["nougat"])
    keyframes = [make_keyframe(feet, 100), make_keyframe(feet, 400), make_keyframe(feet, 200)]
    assert keyframe_times_ms(keyframes) == [0, 400, 600]
