"""The scene every page hands the 3D view (hexapod/scene.py).

The view only draws what it is given, so what is checked here is that the scene
is the hexapod: each leg's points are the linkage's own, the support polygon is
the feet it stands on, and the whole thing survives the trip to the browser.
"""

import json
from math import atan2

import pytest

from hexapod.const import BASE_DIMENSIONS, BASE_SCENE, HEXAPOD
from hexapod.models import VirtualHexapod
from hexapod.path_generator import generate_poses
from hexapod.robot_config import get_simulator_dimensions
from hexapod.scene import VIEWER_COLORS, hexapod_to_scene
from tests.robots import ROBOT_CONFIGS


def settled(robot_config, motion="walk_0", frame=3):
    hexapod = VirtualHexapod(get_simulator_dimensions(robot_config))
    hexapod.update(generate_poses(motion, robot_config)[frame])
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
    hexapod = settled(ROBOT_CONFIGS[name])
    scene = hexapod_to_scene(hexapod)

    assert len(scene["legs"]) == 6
    for leg, points in zip(hexapod.legs, scene["legs"]):
        assert len(points) == 4
        for scene_point, point in zip(points, leg.all_points):
            assert_same_point(scene_point, point)
    for scene_point, vertex in zip(scene["body"], hexapod.body.vertices):
        assert_same_point(scene_point, vertex)
    assert scene["feet"] == [points[3] for points in scene["legs"]]


@pytest.mark.parametrize("name", list(ROBOT_CONFIGS))
def test_support_polygon_is_the_ground_contacts_in_order(name):
    hexapod = settled(ROBOT_CONFIGS[name])
    scene = hexapod_to_scene(hexapod)

    contacts = sorted((round(p.x, 3), round(p.y, 3)) for p in hexapod.ground_contacts)
    assert sorted((p[0], p[1]) for p in scene["support"]) == pytest.approx(contacts, abs=1e-3)
    assert all(p[2] == 0.0 for p in scene["support"])

    # Ordered around the centre, so the polygon is drawn without crossing.
    cx = sum(p[0] for p in scene["support"]) / len(scene["support"])
    cy = sum(p[1] for p in scene["support"]) / len(scene["support"])
    angles = [atan2(p[1] - cy, p[0] - cx) for p in scene["support"]]
    assert angles == sorted(angles)


def test_axes_start_at_the_cog_and_the_origin():
    hexapod = settled(ROBOT_CONFIGS["nougat"], motion="rotate_x", frame=5)
    scene = hexapod_to_scene(hexapod)

    body_axes = [a for a in scene["axes"] if not a["world"]]
    world_axes = [a for a in scene["axes"] if a["world"]]
    assert [a["axis"] for a in body_axes] == ["x", "y", "z"]
    assert all(a["from"] == scene["cog"] for a in body_axes)
    assert all(a["from"] == [0.0, 0.0, 0.0] for a in world_axes)

    scale = hexapod.front / 2
    tip = body_axes[2]["to"]
    up = hexapod.z_axis
    expected = [c + scale * u for c, u in zip(scene["cog"], (up.x, up.y, up.z))]
    assert tip == pytest.approx(expected, abs=1e-3)

    no_world = hexapod_to_scene(hexapod, world_axes=False)
    assert all(not a["world"] for a in no_world["axes"])


def test_base_scene_is_the_neutral_hexapod():
    assert BASE_SCENE == hexapod_to_scene(HEXAPOD)
    assert BASE_SCENE["size"] == pytest.approx(sum(BASE_DIMENSIONS.values()))
    assert len(BASE_SCENE["support"]) == 6
    assert BASE_SCENE["colors"] == VIEWER_COLORS


@pytest.mark.parametrize("name", list(ROBOT_CONFIGS))
def test_scene_survives_json_without_negative_zero(name):
    scene = hexapod_to_scene(settled(ROBOT_CONFIGS[name], motion="turn_left", frame=7))
    assert json.loads(json.dumps(scene)) == scene
    assert not any(str(n) == "-0.0" for n in all_numbers(scene))
