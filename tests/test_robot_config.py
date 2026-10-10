"""Reading the robot's config from the robot, and the HTTP routes around it.

The app keeps no robot definitions: connecting asks the robot for its config
(GET /robot_config), and that is what the simulator then models. These tests
run the real HTTP client against tools/fake_robot.py, which answers the way the
firmware does.
"""

import copy
import json

import pytest

from hexapod import robot_http
from hexapod.robot_config import (
    DEFAULT_CONFIG,
    RobotConfigError,
    cache_path,
    command_id,
    describe,
    describe_firmware,
    fetch_robot_config,
    get_simulator_dimensions,
    load_cached_config,
    load_startup_config,
    parse_robot_config,
    save_cached_config,
)
from hexapod.robot_http import robot_url, split_address
from hexapod.robot_link import RobotLink
from tests.robots import ROBOT_CONFIGS, ROBOT_NAMES, load_payload
from tools.fake_robot import FakeRobot


@pytest.fixture
def cache_file(tmp_path, monkeypatch):
    path = tmp_path / "robot_config.json"
    monkeypatch.setenv("HEXAPOD_LINK_CONFIG_CACHE", str(path))
    return path


@pytest.fixture
def nougat():
    with FakeRobot.from_fixture("nougat", udp_port=0) as robot:
        yield robot


def _link_to(robot):
    """A link that sends its UDP to `robot` rather than the real port 1234."""
    return RobotLink(DEFAULT_CONFIG, udp_port=robot.udp_port)


# ................................................................ parsing


def test_every_robot_payload_parses():
    for name in ROBOT_NAMES:
        robot = parse_robot_config(load_payload(name))
        assert robot["name"] == name
        assert robot["label"] == name.capitalize()
        assert robot["source"] == "robot"
        assert robot["servo_min"] == 102 and robot["servo_max"] == 512


def test_the_payload_carries_the_robots_own_values():
    """Timing, limits, gait radii and mounts all arrive from the robot."""
    mochi = ROBOT_CONFIGS["mochi"]
    assert mochi["ssid"] == "hexapod"
    assert mochi["delay_ms"] == 12
    assert mochi["joint_limits"] == {"coxia": 45, "femur": 75, "tibia": 75}
    assert mochi["gait"]["walk_radius"] == 30
    assert mochi["gait"]["fastwalk"] == {
        "g_steps": 28, "y_radius": 40, "z_radius": 30, "x_radius": 15
    }
    assert ROBOT_CONFIGS["macaroon"]["delay_ms"] == 25
    assert ROBOT_CONFIGS["nougat"]["config"]["legMountAngle"] == [45, 0, -45, -225, -180, -135]


def test_gait_parameters_the_json_omits_match_generate_motion():
    """Rotations, twist and stand-up are fixed in path_tool's generate_motion.py."""
    gait = ROBOT_CONFIGS["nougat"]["gait"]
    assert gait["rotate_x"] == {"g_steps": 28, "swing_angle": 10, "y_radius": 10}
    assert gait["rotate_y"] == {"g_steps": 28, "swing_angle": 10, "x_radius": 10}
    assert gait["rotate_z"] == {"g_steps": 28, "z_lift": 7}
    assert gait["twist"] == {"g_steps": 28}
    assert gait["standup_steps"] == 28
    assert gait["standby_posture"] == (60, 75)


def test_parsed_configs_do_not_share_state():
    a = parse_robot_config(load_payload("mochi"))
    b = parse_robot_config(load_payload("mochi"))
    a["gait"]["rotate_x"]["g_steps"] = 99
    a["config"]["legMountX"][0] = 0
    assert b["gait"]["rotate_x"]["g_steps"] == 28
    assert b["config"]["legMountX"][0] != 0


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda p: p.pop("geometry"), "geometry"),
        (lambda p: p.pop("protocol"), "protocol"),
        (lambda p: p.update(protocol=2), "Update Hexapod Link"),
        (lambda p: p.update(delay_ms=0), "delay_ms"),
        (lambda p: p["geometry"].update(legMountX=[1, 2, 3]), "legMountX"),
        (lambda p: p["geometry"]["legScale"].pop(), "legScale"),
        (lambda p: p["geometry"]["legScale"][0].__setitem__(1, 2), "legScale"),
        (lambda p: p["geometry"].update(legJoint3ToTip=0), "legJoint3ToTip"),
        (lambda p: p["geometry"]["gait"].pop("walk_radius"), "walk_radius"),
        (lambda p: p.update(servo={"min": 500, "max": 100}), "servo"),
    ],
)
def test_a_malformed_payload_is_refused(mutate, message):
    payload = copy.deepcopy(load_payload("nougat"))
    mutate(payload)
    with pytest.raises(RobotConfigError, match=message):
        parse_robot_config(payload)


def test_a_payload_without_optional_fields_gets_defaults():
    payload = copy.deepcopy(load_payload("nougat"))
    for key in ("speed", "commands", "servo"):
        payload.pop(key)
    payload["geometry"].pop("jointLimits")
    robot = parse_robot_config(payload)
    assert robot["speed"] == {"min": 20, "max": 100, "default": 60, "current": 60}
    assert command_id(robot, "twist") == 18
    assert robot["joint_limits"] == {"coxia": 45, "femur": 75, "tibia": 75}


def test_command_ids_follow_the_robots_own_list():
    """A firmware that reorders its commands is followed, not second-guessed."""
    payload = copy.deepcopy(load_payload("nougat"))
    payload["commands"] = ["standby", "twist", "walk0"]
    robot = parse_robot_config(payload)
    assert command_id(robot, "twist") == 1
    assert command_id(robot, "walk_0") == 2
    assert command_id(robot, "turn_left") is None


def test_simulator_dimensions_carry_the_mount_angles():
    dims = get_simulator_dimensions(ROBOT_CONFIGS["nougat"])
    assert dims["front"] == 44.82 and dims["side"] == 74.82 and dims["middle"] == 61.03
    assert (dims["coxia"], dims["femur"], dims["tibia"]) == (38.0, 54.06, 93.53)
    assert dims["mount_angles"] == [45, 0, 315, 135, 180, 225]
    assert "mount_angles" not in get_simulator_dimensions(
        ROBOT_CONFIGS["nougat"], mount_angles=False
    )


def test_the_default_model_is_nougat():
    """Measured, mounted and mirrored as the robot itself reports."""
    nougat = ROBOT_CONFIGS["nougat"]
    assert get_simulator_dimensions(DEFAULT_CONFIG) == get_simulator_dimensions(nougat)
    assert DEFAULT_CONFIG["config"]["legScale"] == nougat["config"]["legScale"]
    assert DEFAULT_CONFIG["joint_limits"] == nougat["joint_limits"]
    assert DEFAULT_CONFIG["name"] == "nougat" and DEFAULT_CONFIG["label"] == "Nougat"
    assert DEFAULT_CONFIG["source"] == "default"


# .................................................................. cache


def test_the_cache_round_trips(cache_file):
    assert load_cached_config() is None
    assert save_cached_config(ROBOT_CONFIGS["nougat"])
    assert cache_path() == cache_file

    cached = load_cached_config()
    assert cached["source"] == "cache"
    assert cached["name"] == "nougat"
    assert cached["config"] == ROBOT_CONFIGS["nougat"]["config"]
    assert load_startup_config()["name"] == "nougat"


def test_without_a_cache_the_app_starts_on_the_default(cache_file):
    assert load_startup_config() is DEFAULT_CONFIG


def test_an_unreadable_cache_is_ignored(cache_file):
    cache_file.write_text("{not json", encoding="utf-8")
    assert load_cached_config() is None
    cache_file.write_text(json.dumps({"protocol": 1}), encoding="utf-8")
    assert load_cached_config() is None


def test_describe_names_the_robot_and_where_its_config_came_from(cache_file):
    assert describe(ROBOT_CONFIGS["nougat"]) == "Nougat · hexapod_nougat"
    save_cached_config(ROBOT_CONFIGS["nougat"])
    assert "last connected" in describe(load_cached_config())
    assert describe(DEFAULT_CONFIG).startswith("Nougat (default)")


# ................................................................... HTTP


def test_addresses_may_carry_an_http_port():
    assert split_address("192.168.4.1") == ("192.168.4.1", 80)
    assert split_address(" 127.0.0.1:8080 ") == ("127.0.0.1", 8080)
    assert robot_url("192.168.4.1", "/robot_config") == "http://192.168.4.1/robot_config"
    assert robot_url("127.0.0.1:8080", "/x") == "http://127.0.0.1:8080/x"


def test_fetch_reads_the_robots_config(nougat):
    robot = fetch_robot_config(nougat.address)
    assert robot["name"] == "nougat"
    assert robot["config"] == ROBOT_CONFIGS["nougat"]["config"]


def test_fetch_from_nowhere_explains_itself():
    with FakeRobot.from_fixture("nougat") as robot:
        address = robot.address
    with pytest.raises(RobotConfigError, match="Couldn't read the robot's config"):
        fetch_robot_config(address, timeout=0.5)


def test_speed_routes(nougat):
    assert robot_http.set_speed(nougat.address, 75) == 75
    assert nougat.speed == 75
    assert robot_http.set_speed(nougat.address, 5) == 20


# ............................................................... connect


def test_connecting_loads_the_robots_config(nougat, cache_file):
    link = _link_to(nougat)
    try:
        assert link.connect(nougat.address)
        assert link.connected
        assert link.robot_config["name"] == "nougat"
        assert link.config_version == 1
        assert link.status()["robot_label"] == "Nougat"
        # Remembered for the next offline start.
        assert load_cached_config()["name"] == "nougat"
    finally:
        link.disconnect()


def test_connecting_picks_up_the_robots_speed(nougat, cache_file):
    nougat.speed = 45
    link = _link_to(nougat)
    try:
        link.connect(nougat.address)
        assert link.speed_pct == 45
        link.set_motion_speed(90)
        assert nougat.speed == 90
    finally:
        link.disconnect()


def test_a_robot_that_does_not_answer_is_not_connected(cache_file):
    with FakeRobot.from_fixture("nougat") as robot:
        address = robot.address
    link = RobotLink(DEFAULT_CONFIG)
    assert not link.connect(address)
    assert not link.connected
    assert "Couldn't read the robot's config" in link.status()["last_error"]
    assert link.robot_config is DEFAULT_CONFIG
    assert link.config_version == 0
    assert not cache_file.exists()


# .............................................................. firmware


def test_the_payload_reports_the_firmware():
    robot = parse_robot_config(load_payload("nougat"))
    assert robot["firmware"] == {"version": "3.2.0", "build": "dev", "protocol": 1}


def test_firmware_that_predates_reporting_it_parses():
    payload = load_payload("nougat")
    del payload["firmware"]
    assert parse_robot_config(payload)["firmware"] is None
    assert DEFAULT_CONFIG["firmware"] is None


def test_describe_firmware():
    firmware = {"version": "3.2.0", "build": "v3.2.0-4-gabc", "protocol": 1}
    assert describe_firmware(firmware) == "Firmware 3.2.0 (v3.2.0-4-gabc) · protocol 1"
    assert describe_firmware(dict(firmware, build="")) == "Firmware 3.2.0 · protocol 1"
    assert describe_firmware(None) == "Firmware version not reported"


def test_connecting_queries_the_firmware_over_udp(nougat, cache_file):
    # With no version in the payload, the fake's UDP answer is the only source:
    # its stand-in version shows the query went out and the reply was decoded.
    del nougat.payload["firmware"]
    link = _link_to(nougat)
    try:
        assert link.connect(nougat.address)
        assert link.robot_config["firmware"] is None
        assert link.firmware == {"version": "0.0.0", "build": "fake", "protocol": 1}
        assert link.status()["firmware"] == link.firmware
    finally:
        link.disconnect()
    assert link.firmware is None


def test_without_a_udp_answer_the_firmware_comes_from_the_config(cache_file):
    with FakeRobot.from_fixture("nougat", udp_port=0, answer_version=False) as robot:
        link = _link_to(robot)
        try:
            assert link.connect(robot.address)
            assert link.firmware == {"version": "3.2.0", "build": "dev", "protocol": 1}
        finally:
            link.disconnect()


def test_older_firmware_connects_without_a_version(cache_file):
    payload = load_payload("nougat")
    del payload["firmware"]
    with FakeRobot(payload, udp_port=0, answer_version=False) as robot:
        link = _link_to(robot)
        try:
            assert link.connect(robot.address)
            assert link.connected
            assert link.firmware is None
        finally:
            link.disconnect()
