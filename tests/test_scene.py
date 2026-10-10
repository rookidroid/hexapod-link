"""The scene handed to the 3D view (hexapod/scene.py).

The view only draws what it is given, so what is checked here is that the scene
is the hexapod: each leg's points are the linkage's own, the support polygon is
drawn through the feet given, in order, and the whole thing survives the trip
to the browser.
"""

import json
from math import atan2

import numpy as np
import pytest

from hexapod.keyframes import pose_to_scene
from hexapod.models import VirtualHexapod
from hexapod.path_generator import generate_poses
from hexapod.robot_config import get_simulator_dimensions
from hexapod.scene import VIEWER_COLORS, hexapod_to_scene, transform_scene
from tests.robots import ROBOT_CONFIGS


def posed(robot_config, motion="walk_0", frame=3):
    """The simulator's model with its legs set to one frame of a gait."""
    hexapod = VirtualHexapod(get_simulator_dimensions(robot_config))
    for leg_id, joints in generate_poses(motion, robot_config)[frame].items():
        hexapod.legs[leg_id].change_pose(joints["coxia"], joints["femur"], joints["tibia"])
    return hexapod


def all_numbers(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from all_numbers(item)
    elif isinstance(value, list):
        for item in value:
            yield from all_numbers(item)
    elif isinstance(value, float):
        yield value


def assert_same_point(scene_point, point):
    assert scene_point == pytest.approx([point.x, point.y, point.z], abs=1e-3)


@pytest.mark.parametrize("name", list(ROBOT_CONFIGS))
def test_legs_are_the_linkage_points(name):
    hexapod = posed(ROBOT_CONFIGS[name])
    scene = hexapod_to_scene(hexapod, -100.0, [])

    assert len(scene["legs"]) == 6
    for leg, points in zip(hexapod.legs, scene["legs"]):
        assert len(points) == 4
        for scene_point, point in zip(points, leg.all_points):
            assert_same_point(scene_point, point)
    for scene_point, vertex in zip(scene["body"], hexapod.body.vertices):
        assert_same_point(scene_point, vertex)
    assert scene["feet"] == [points[3] for points in scene["legs"]]
    assert scene["colors"] == VIEWER_COLORS


def test_support_polygon_is_drawn_flat_and_in_order():
    hexapod = posed(ROBOT_CONFIGS["nougat"])
    feet = [[100.0, 0.0, -90.0], [-50.0, -87.0, -91.0], [-50.0, 87.0, -89.0], [0.0, 120.0, -90.0]]
    scene = hexapod_to_scene(hexapod, -90.0, feet)

    assert sorted((p[0], p[1]) for p in scene["support"]) == sorted((p[0], p[1]) for p in feet)
    assert all(p[2] == -90.0 for p in scene["support"])

    # Ordered around the centre, so the polygon is drawn without crossing.
    cx = sum(p[0] for p in scene["support"]) / len(scene["support"])
    cy = sum(p[1] for p in scene["support"]) / len(scene["support"])
    angles = [atan2(p[1] - cy, p[0] - cx) for p in scene["support"]]
    assert angles == sorted(angles)


def test_axes_are_the_bodys_own_from_the_cog():
    hexapod = posed(ROBOT_CONFIGS["nougat"])
    scene = hexapod_to_scene(hexapod, 0.0, [])

    assert [a["axis"] for a in scene["axes"]] == ["x", "y", "z"]
    assert all(a["from"] == scene["cog"] for a in scene["axes"])
    scale = hexapod.front / 2
    for i, axis in enumerate(scene["axes"]):
        expected = list(scene["cog"])
        expected[i] += scale
        assert axis["to"] == pytest.approx(expected, abs=1e-3)


@pytest.mark.parametrize("name", list(ROBOT_CONFIGS))
def test_scene_survives_json_without_negative_zero(name):
    robot = ROBOT_CONFIGS[name]
    scene = pose_to_scene(generate_poses("turn_left", robot)[7], robot)
    assert json.loads(json.dumps(scene)) == scene
    assert not any(str(n) == "-0.0" for n in all_numbers(scene))


def test_a_transformed_scene_moves_every_point_rigidly():
    robot = ROBOT_CONFIGS["nougat"]
    scene = pose_to_scene(generate_poses("walk_0", robot)[3], robot)
    turn = np.radians(30)
    rotation = [[np.cos(turn), -np.sin(turn), 0], [np.sin(turn), np.cos(turn), 0], [0, 0, 1]]
    shift = [10.0, -20.0, 50.0]
    moved = transform_scene(scene, rotation, shift)

    def points(s):
        return [s["head"], s["cog"], *s["body"], *s["feet"], *s["support"]] + [
            p for leg in s["legs"] for p in leg
        ] + [p for axis in s["axes"] for p in (axis["from"], axis["to"])]

    for before, after in zip(points(scene), points(moved), strict=True):
        assert after == pytest.approx(np.asarray(rotation) @ before + shift, abs=1e-3)
    assert moved["ground"] == pytest.approx(scene["ground"] + 50.0)
    assert moved["size"] == scene["size"] and moved["labels"] == scene["labels"]
