"""The pose page's pose in layers (hexapod/pose_layers.py).

What matters is that the layers add up instead of undoing each other: the
body moves over feet that stay planted, and a moved foot stays where it was
put while the body moves. Then that a sequence made of layered keyframes
plays as the layers say.
"""

import json

import numpy as np
import pytest

from hexapod import keyframes as kf
from hexapod import pose_layers as pl
from hexapod.robot_config import GENERIC_CONFIG, get_simulator_dimensions, with_dimensions
from tests.robots import ROBOT_CONFIGS

ROBOTS = list(ROBOT_CONFIGS.values()) + [GENERIC_CONFIG]
ROBOT_IDS = list(ROBOT_CONFIGS) + ["generic"]

TILT = {
    "percent_x": 0.15,
    "percent_y": -0.1,
    "percent_z": 0.2,
    "rot_x": 7.5,
    "rot_y": -6.0,
    "rot_z": 6.0,
}


def tilted():
    return pl.make_state(TILT, np.zeros((6, 3)))


def drawn_feet(state, robot):
    _, pose, _ = pl.solve(state, robot)
    return np.array(pl.scene(state, pose, robot)["feet"])


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_standby_state_is_the_standby_posture(robot):
    state = pl.standby_state()
    feet, _, bad = pl.solve(state, robot)
    assert bad == []
    np.testing.assert_allclose(feet, kf.standby_feet(robot), atol=1e-2)
    # Standing on the floor, which the view has at z = 0.
    np.testing.assert_allclose(drawn_feet(state, robot)[:, 2], 0, atol=1e-2)


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_moving_the_body_keeps_the_feet_planted(robot):
    state = tilted()
    _, _, bad = pl.solve(state, robot)
    assert bad == []
    np.testing.assert_allclose(
        drawn_feet(state, robot), drawn_feet(pl.standby_state(), robot), atol=1e-2
    )


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_raising_the_body_lowers_the_feet_in_the_body_frame(robot):
    raised = pl.make_state({"percent_z": 0.1}, np.zeros((6, 3)))
    before = np.array(pl.body_feet(pl.standby_state(), robot))
    after = np.array(pl.body_feet(raised, robot))
    np.testing.assert_allclose(after[:, :2], before[:, :2], atol=1e-2)
    assert (after[:, 2] < before[:, 2]).all()


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_turning_the_body_turns_every_coxia_the_other_way(robot):
    turned = pl.make_state({"rot_z": 12.0}, np.zeros((6, 3)))
    _, pose, bad = pl.solve(turned, robot)
    assert bad == []
    coxias = [pose[leg]["coxia"] for leg in range(6)]
    assert all(coxia < -1.0 for coxia in coxias)


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_a_moved_foot_lands_where_it_was_put_and_stays_as_the_body_moves(robot):
    state = tilted()
    target = drawn_feet(state, robot)[0] + [10.0, 5.0, 30.0]
    moved = pl.with_foot_at(state, 0, target, robot)
    _, _, bad = pl.solve(moved, robot)
    assert bad == []
    np.testing.assert_allclose(drawn_feet(moved, robot)[0], target, atol=1e-2)
    np.testing.assert_allclose(pl.view_feet(moved, robot)[0], target, atol=1e-2)

    # Level the body again: the foot stays where it was put.
    level = pl.make_state({}, moved["offsets"])
    np.testing.assert_allclose(drawn_feet(level, robot)[0], target, atol=1e-2)
    # The other feet were never moved, and stand on the floor throughout.
    np.testing.assert_allclose(drawn_feet(level, robot)[1:, 2], 0, atol=1e-2)


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_a_foot_dragged_past_its_legs_reach_is_held_as_near_as_it_gets(robot):
    state = tilted()
    start = drawn_feet(state, robot)[0]

    # Within reach, it goes where it is dragged.
    target = start + [10.0, 5.0, 30.0]
    assert pl.with_foot_near(state, 0, target, robot) == pl.with_foot_at(state, 0, target, robot)

    # Further than the leg is long, it stops short, on the way there, and
    # the leg can still be posed. The body and the other feet stay.
    away = np.append(start[:2], 0) / np.hypot(*start[:2])
    target = start + 500.0 * away
    _, _, bad = pl.solve(pl.with_foot_at(state, 0, target, robot), robot)
    assert bad == [0]
    held = pl.with_foot_near(state, 0, target, robot)
    _, _, bad = pl.solve(held, robot)
    assert bad == []
    foot = drawn_feet(held, robot)[0]
    np.testing.assert_allclose(pl.view_feet(held, robot)[0], foot, atol=1e-2)
    assert np.linalg.norm(foot - start) > 10.0
    assert np.linalg.norm(foot - target) < np.linalg.norm(start - target)
    assert held["body"] == state["body"]
    np.testing.assert_allclose(drawn_feet(held, robot)[1:], drawn_feet(state, robot)[1:], atol=1e-2)

    # Dragged on along the edge of its reach, it stays where it is held.
    assert pl.with_foot_near(held, 0, target, robot) == held


def held_in_reach(state, robot):
    """Whether the state is one a body held within reach is left in."""
    feet = pl.body_feet(state, robot)
    return kf.feet_to_pose(feet, robot, pl.BODY_LIMIT_MARGIN_DEG)[1] == []


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_a_body_moved_within_reach_goes_where_it_is_put(robot):
    start = pl.standby_state()
    assert pl.with_body_near(start, TILT, robot) == tilted()


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
@pytest.mark.parametrize("key", pl.BODY_KEYS)
@pytest.mark.parametrize("way", [-1, 1])
def test_a_body_pushed_past_its_legs_reach_stops_where_they_can_follow(robot, key, way):
    start = tilted()
    # As far as the sliders go, which no robot's legs do.
    asked = {**TILT, key: way * (1.0 if key.startswith("percent") else 39.0)}
    assert pl.solve(pl.make_state(asked, start["offsets"]), robot)[2] != []

    held = pl.with_body_near(start, asked, robot)
    assert held_in_reach(held, robot)
    assert held["offsets"] == start["offsets"]
    # Only that way, part of the way, in whole steps back from what was
    # asked, and as few of them as the legs reach with.
    assert {k: v for k, v in held["body"].items() if k != key} == {
        k: v for k, v in start["body"].items() if k != key
    }
    step = dict(zip(pl.BODY_KEYS, pl.BODY_STEPS))[key]
    back = (asked[key] - held["body"][key]) * way / step
    assert back == pytest.approx(round(back), abs=1e-6) and back >= 1
    assert (held["body"][key] - start["body"][key]) * way > 0
    further = pl.make_state({**held["body"], key: held["body"][key] + way * step}, held["offsets"])
    assert not held_in_reach(further, robot)

    # Pushed again, it stays.
    assert pl.with_body_near(held, asked, robot) == held


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_a_body_pushed_two_ways_goes_the_way_it_can(robot):
    # Sideways a little, which the legs reach, and up further than they do.
    start = tilted()
    asked = {**TILT, "percent_x": 0.1, "percent_z": 1.0}
    held = pl.with_body_near(start, asked, robot)
    assert held_in_reach(held, robot)
    assert held["body"]["percent_x"] == pytest.approx(0.1)
    assert TILT["percent_z"] < held["body"]["percent_z"] < 1.0


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_a_body_whose_legs_are_out_of_reach_already_goes_where_it_is_put(robot):
    # A foot put where its leg cannot reach: there is nothing to hold to.
    offsets = np.zeros((6, 3))
    offsets[2] = [0.0, 0.0, 1000.0]
    start = pl.make_state({}, offsets)
    assert pl.solve(start, robot)[2] == [2]
    assert pl.with_body_near(start, TILT, robot) == pl.make_state(TILT, offsets)


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_a_body_can_be_moved_from_a_foot_held_at_its_limit(robot):
    # The foot's own margin is wider than the body's, so the body is still
    # held from there, and can be moved back.
    start = pl.standby_state()
    foot = drawn_feet(start, robot)[0]
    away = np.append(foot[:2], 0) / np.hypot(*foot[:2])
    stretched = pl.with_foot_near(start, 0, foot + 500.0 * away, robot)
    assert held_in_reach(stretched, robot)
    # Away from the foot the leg cannot follow; towards it, it can.
    side = get_simulator_dimensions(robot)["middle"]
    back = {"percent_x": -30.0 * away[0] / side}
    assert pl.with_body_near(stretched, back, robot)["body"]["percent_x"] != pytest.approx(
        back["percent_x"]
    )
    towards = {"percent_x": 0.05 * np.sign(away[0])}
    assert pl.with_body_near(stretched, towards, robot)["body"]["percent_x"] == pytest.approx(
        towards["percent_x"]
    )


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_setting_a_legs_joints_moves_only_that_foot(robot):
    state = tilted()
    _, before, _ = pl.solve(state, robot)
    moved = pl.with_leg_angles(state, 4, {"coxia": 10.0, "femur": 45.0}, robot)
    _, after, bad = pl.solve(moved, robot)
    assert bad == []
    assert after[4]["coxia"] == pytest.approx(10.0, abs=1e-2)
    assert after[4]["femur"] == pytest.approx(45.0, abs=1e-2)
    assert after[4]["tibia"] == pytest.approx(before[4]["tibia"], abs=1e-2)
    assert moved["body"] == state["body"]
    # The other legs are untouched, and still stand on the floor.
    for leg in (0, 1, 2, 3, 5):
        for joint in ("coxia", "femur", "tibia"):
            assert after[leg][joint] == pytest.approx(before[leg][joint], abs=1e-2)
    np.testing.assert_allclose(np.delete(drawn_feet(moved, robot), 4, axis=0)[:, 2], 0, atol=1e-2)
    # Raising the femur lifts the foot off the floor.
    assert drawn_feet(moved, robot)[4][2] > 1.0


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_the_body_put_where_its_frame_is_is_the_same_body(robot):
    state = tilted()
    frame = pl.body_frame(state, robot)
    body = pl.body_at(frame["origin"], frame["rot"], robot)
    assert pl.make_state(body, state["offsets"])["body"] == pytest.approx(state["body"], abs=1e-3)

    # The view's handle on the body is at its centre, as drawn.
    _, pose, _ = pl.solve(state, robot)
    drawn = pl.scene(state, pose, robot)
    assert drawn["frame"] == frame
    np.testing.assert_allclose(drawn["frame"]["origin"], drawn["cog"], atol=1e-2)


def test_keyframe_feet_become_moves_from_standby():
    robot = ROBOT_CONFIGS["nougat"]
    feet = np.array(kf.standby_feet(robot))
    feet[2] += [5.0, -5.0, 20.0]
    state = pl.from_feet(feet, robot)
    np.testing.assert_allclose(pl.body_feet(state, robot), feet, atol=1e-2)
    assert np.count_nonzero(np.abs(np.array(state["offsets"])) > 1e-6) == 3


def test_a_state_survives_json_and_is_recognised():
    state = tilted()
    assert pl.is_state(json.loads(json.dumps(state)))
    assert not pl.is_state({"body": {}, "offsets": []})
    assert not pl.is_state(None)


def test_layered_sequence_tilts_the_body_over_planted_feet():
    robot = ROBOT_CONFIGS["nougat"]
    standby = pl.standby_state()
    keyframes = [
        kf.make_keyframe(pl.body_feet(state, robot), 400, state) for state in (standby, tilted())
    ]
    feet, states, poses, bad = pl.sequence(keyframes, robot, fps=20)
    assert bad == [] and len(feet) == len(states) == len(poses) == 1 + 8
    np.testing.assert_allclose(feet[-1], keyframes[-1]["feet"], atol=1e-2)
    # Every frame on the way stands on the same footprints.
    for state, pose in zip(states, poses):
        drawn = np.array(pl.scene(state, pose, robot)["feet"])
        np.testing.assert_allclose(drawn, drawn_feet(standby, robot), atol=1e-2)


def test_sequence_without_layers_moves_the_feet_in_straight_lines():
    robot = ROBOT_CONFIGS["nougat"]
    start = kf.standby_feet(robot)
    end = np.array(start)
    end[0][2] += 30
    keyframes = [kf.make_keyframe(start), kf.make_keyframe(end.tolist(), 500)]
    feet, states, _, bad = pl.sequence(keyframes, robot, fps=20, ease=False)
    assert states is None and bad == []
    np.testing.assert_allclose(feet, kf.interpolate_feet(keyframes, 20, ease=False))


def test_saved_keyframes_keep_their_layers():
    robot = ROBOT_CONFIGS["macaroon"]
    state = tilted()
    keyframes = [kf.make_keyframe(pl.body_feet(state, robot), 300, state)]
    loaded = kf.load(kf.dump(keyframes, robot), robot)
    assert loaded[0]["state"] == state


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_unchanged_dimensions_leave_the_robot_as_it_is(robot):
    dimensions = get_simulator_dimensions(robot, mount_angles=False)
    assert with_dimensions(robot, dimensions) is robot
    assert with_dimensions(robot, None) is robot
    # Nothing usable in the Robot panel: the robot keeps its own measurements.
    assert with_dimensions(robot, {name: 0 for name in dimensions}) is robot


@pytest.mark.parametrize("robot", ROBOTS, ids=ROBOT_IDS)
def test_a_resized_robot_is_measured_as_asked_and_still_poses(robot):
    dimensions = get_simulator_dimensions(robot, mount_angles=False)
    asked = {**dimensions, "front": dimensions["front"] * 1.2, "femur": dimensions["femur"] * 1.1}
    resized = with_dimensions(robot, asked)
    for name, value in get_simulator_dimensions(resized, mount_angles=False).items():
        assert value == pytest.approx(asked[name])
    # Mirroring, limits and the robot's identity are its own.
    assert resized["config"]["legScale"] == robot["config"]["legScale"]
    assert resized["joint_limits"] == robot["joint_limits"] and resized["name"] == robot["name"]
    if robot["source"] != "generic":
        assert resized["config"]["legMountAngle"] == robot["config"]["legMountAngle"]

    # The pose page works on it as on the robot itself.
    state = tilted()
    _, _, bad = pl.solve(state, resized)
    assert bad == []
    np.testing.assert_allclose(drawn_feet(state, resized)[:, 2], 0, atol=1e-2)
    np.testing.assert_allclose(
        pl.body_feet(pl.standby_state(), resized), kf.standby_feet(resized), atol=1e-2
    )
