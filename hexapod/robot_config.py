# The config of the physical hexapod being driven.
#
# The firmware serves its own at GET /robot_config -- its name and access
# point, servo range, LUT frame delay, playback speed limits, the motion
# commands it knows, and its geometry, which is the robot's
# software/path_tool/robots/<name>.json compiled into the firmware. The link
# fetches that on every connect (hexapod/robot_link.py), so the simulator
# always models the robot that is actually on the other end.
#
# The last config received is cached to disk, so the app still shows that robot
# when started without one. Before any robot has ever connected it falls back
# to DEFAULT_PAYLOAD below: Nougat, the one robot defined in this app.
#
# A payload is parsed into the dict the rest of the app works with:
#
#   name, label, ssid, protocol, source ("robot", "cache" or "default")
#   firmware          {"version", "build", "protocol"}, or None if not reported
#   delay_ms          LUT frame period at 100 % speed
#   servo_min/max     PWM tick range
#   speed             {"min", "max", "default", "current"} in percent
#   commands          firmware motion names; the index is the command id
#   config            path_tool geometry: legMountX/Y/Angle, legScale, lengths
#   gait              path generator parameters (hexapod/path_generator.py)
#   joint_limits      mechanical travel in degrees, per joint

import json
import os
from copy import deepcopy
from pathlib import Path

from settings import ROBOT_CONFIG_CACHE_ENV, ROBOT_CONFIG_CACHE_PATH
from hexapod.robot_http import RobotHttpError, get_robot_config

# Highest GET /robot_config protocol this app understands (PROTOCOL_VERSION in
# the firmware's protocol.h).
SUPPORTED_PROTOCOL = 1

# The firmware's motion names in RobotCommand order, for configs that predate
# the robot listing them.
FIRMWARE_COMMANDS = [
    "standby",
    "walk0",
    "walk180",
    "walkr45",
    "walkr90",
    "walkr135",
    "walkl45",
    "walkl90",
    "walkl135",
    "fastforward",
    "fastbackward",
    "turnleft",
    "turnright",
    "climbforward",
    "climbbackward",
    "rotatex",
    "rotatey",
    "rotatez",
    "twist",
]

DEFAULT_SPEED = {"min": 20, "max": 100, "default": 60}
DEFAULT_JOINT_LIMITS = {"coxia": 45, "femur": 75, "tibia": 75}

# Gait parameters path_tool's generate_motion.py bakes into every robot's LUTs
# without reading them from the robot's JSON. The JSON's own "gait" block (walk
# and turn radii, fast-walk radii) is laid over these.
_FIXED_GAIT = {
    "fastwalk_g_steps": 28,
    "rotate_x": {"g_steps": 28, "swing_angle": 10, "y_radius": 10},
    "rotate_y": {"g_steps": 28, "swing_angle": 10, "x_radius": 10},
    "rotate_z": {"g_steps": 28, "z_lift": 7},
    "twist": {"g_steps": 28},
    "standup_steps": 28,
}


# Nougat's geometry: the firmware repo's software/path_tool/robots/nougat.json.
_NOUGAT_GEOMETRY = {
    "name": "nougat",
    "label": "Nougat",
    "legMountX": [44.82, 61.03, 44.82, -44.82, -61.03, -44.82],
    "legMountY": [74.82, 0, -74.82, 74.82, 0, -74.82],
    "legMountAngle": [45, 0, -45, -225, -180, -135],
    "legScale": [
        [1, -1, -1], [1, 1, 1], [1, 1, 1],
        [1, 1, 1], [1, -1, -1], [1, -1, -1],
    ],
    "legRootToJoint1": 0,
    "legJoint1ToJoint2": 38.0,
    "legJoint2ToJoint3": 54.06,
    "legJoint3ToTip": 93.53,
    "servoMin": 102,
    "servoMax": 512,
    "jointLimits": dict(DEFAULT_JOINT_LIMITS),
    "standbyPosture": [60, 75],
    "laydownPosture": [25, 25],
    "gait": {
        "walk_radius": 40,
        "fastwalk_y_radius": 50,
        "fastwalk_z_radius": 40,
        "fastwalk_x_radius": 15,
        "turn_radius": 35,
    },
}

# Stands in for a robot until one has connected: Nougat, as its firmware
# reports itself, so it goes through the same parser.
DEFAULT_PAYLOAD = {
    "protocol": SUPPORTED_PROTOCOL,
    "name": "nougat",
    "ssid": "",
    "delay_ms": 12,
    "servo": {"min": 102, "mid": 307, "max": 512},
    "speed": dict(DEFAULT_SPEED),
    "commands": list(FIRMWARE_COMMANDS),
    "geometry": _NOUGAT_GEOMETRY,
}


class RobotConfigError(Exception):
    """The robot's config could not be fetched or does not make sense."""


# ----------------------------------------------------------------- parsing


def _require(mapping, key, where):
    if not isinstance(mapping, dict) or key not in mapping:
        raise RobotConfigError(f"Robot config is missing '{key}' in {where}")
    return mapping[key]


def _number(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RobotConfigError(f"Robot config: {what} must be a number")
    return value


def _six(values, what):
    if not isinstance(values, list) or len(values) != 6:
        raise RobotConfigError(f"Robot config: {what} must list 6 legs")
    return [_number(v, what) for v in values]


def _parse_geometry(geometry):
    config = deepcopy(geometry)
    config["legMountX"] = _six(_require(geometry, "legMountX", "geometry"), "legMountX")
    config["legMountY"] = _six(_require(geometry, "legMountY", "geometry"), "legMountY")
    config["legMountAngle"] = _six(
        _require(geometry, "legMountAngle", "geometry"), "legMountAngle"
    )

    leg_scale = _require(geometry, "legScale", "geometry")
    if not (
        isinstance(leg_scale, list)
        and len(leg_scale) == 6
        and all(isinstance(row, list) and len(row) == 3 for row in leg_scale)
    ):
        raise RobotConfigError("Robot config: legScale must be 6 rows of 3")
    for row in leg_scale:
        for value in row:
            if value not in (1, -1):
                raise RobotConfigError("Robot config: legScale entries must be 1 or -1")

    for key in ("legJoint1ToJoint2", "legJoint2ToJoint3", "legJoint3ToTip"):
        if _number(_require(geometry, key, "geometry"), key) <= 0:
            raise RobotConfigError(f"Robot config: {key} must be positive")
    config["legRootToJoint1"] = _number(geometry.get("legRootToJoint1", 0), "legRootToJoint1")
    return config


def _parse_gait(geometry):
    gait = _require(geometry, "gait", "geometry")
    parsed = {
        "standby_posture": tuple(_require(geometry, "standbyPosture", "geometry")),
        "laydown_posture": tuple(_require(geometry, "laydownPosture", "geometry")),
        "walk_radius": _number(_require(gait, "walk_radius", "gait"), "walk_radius"),
        "turn_radius": _number(_require(gait, "turn_radius", "gait"), "turn_radius"),
        "fastwalk": {
            "g_steps": _FIXED_GAIT["fastwalk_g_steps"],
            "y_radius": _number(_require(gait, "fastwalk_y_radius", "gait"), "fastwalk_y_radius"),
            "z_radius": _number(_require(gait, "fastwalk_z_radius", "gait"), "fastwalk_z_radius"),
            "x_radius": _number(_require(gait, "fastwalk_x_radius", "gait"), "fastwalk_x_radius"),
        },
        "standup_steps": _FIXED_GAIT["standup_steps"],
    }
    for motion in ("rotate_x", "rotate_y", "rotate_z", "twist"):
        parsed[motion] = dict(_FIXED_GAIT[motion])
    return parsed


def _parse_firmware(firmware, protocol):
    """The payload's {"version", "build"} block, or None for firmware that
    predates reporting it. Shaped like robot_link.parse_version_reply()."""
    if not isinstance(firmware, dict) or not isinstance(firmware.get("version"), str):
        return None
    return {
        "version": firmware["version"],
        "build": str(firmware.get("build") or ""),
        "protocol": protocol,
    }


def parse_robot_config(payload, source="robot"):
    """Turn a GET /robot_config payload into the app's robot config dict."""
    if not isinstance(payload, dict):
        raise RobotConfigError("Robot config is not a JSON object")

    protocol = _require(payload, "protocol", "the payload")
    if isinstance(protocol, bool) or not isinstance(protocol, int):
        raise RobotConfigError("Robot config: protocol must be an integer")
    if protocol > SUPPORTED_PROTOCOL:
        raise RobotConfigError(
            f"The robot speaks protocol {protocol}, but this app only knows up to "
            f"{SUPPORTED_PROTOCOL}. Update Hexapod Link."
        )

    geometry = _require(payload, "geometry", "the payload")
    name = str(payload.get("name") or geometry.get("name") or "robot")
    label = str(geometry.get("label") or name.capitalize())

    delay_ms = _number(_require(payload, "delay_ms", "the payload"), "delay_ms")
    if delay_ms <= 0:
        raise RobotConfigError("Robot config: delay_ms must be positive")

    servo = payload.get("servo") or {}
    servo_min = _number(servo.get("min", geometry.get("servoMin", 102)), "servo min")
    servo_max = _number(servo.get("max", geometry.get("servoMax", 512)), "servo max")
    if servo_max <= servo_min:
        raise RobotConfigError("Robot config: servo max must exceed servo min")

    speed = dict(DEFAULT_SPEED)
    speed.update(
        {k: int(_number(v, f"speed {k}")) for k, v in (payload.get("speed") or {}).items()}
    )
    speed.setdefault("current", speed["default"])

    commands = payload.get("commands") or list(FIRMWARE_COMMANDS)
    if not all(isinstance(c, str) for c in commands):
        raise RobotConfigError("Robot config: commands must be strings")

    joint_limits = dict(DEFAULT_JOINT_LIMITS)
    joint_limits.update(geometry.get("jointLimits") or {})

    return {
        "name": name,
        "label": label,
        "ssid": str(payload.get("ssid") or ""),
        "protocol": protocol,
        "firmware": _parse_firmware(payload.get("firmware"), protocol),
        "source": source,
        "delay_ms": delay_ms,
        "servo_min": servo_min,
        "servo_max": servo_max,
        "speed": speed,
        "commands": list(commands),
        "config": _parse_geometry(geometry),
        "gait": _parse_gait(geometry),
        "joint_limits": joint_limits,
        "payload": deepcopy(payload),
    }


DEFAULT_CONFIG = parse_robot_config(DEFAULT_PAYLOAD, source="default")


# ------------------------------------------------------------ fetch / cache


def fetch_robot_config(address, timeout=None):
    """Ask the robot at `address` for its config."""
    try:
        payload = get_robot_config(address, timeout=timeout)
    except RobotHttpError as error:
        raise RobotConfigError(f"Couldn't read the robot's config: {error}") from error
    return parse_robot_config(payload, source="robot")


def cache_path():
    return Path(os.environ.get(ROBOT_CONFIG_CACHE_ENV) or ROBOT_CONFIG_CACHE_PATH)


def save_cached_config(robot_config):
    """Remember a robot's config for the next offline start. Best effort."""
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(robot_config["payload"], indent=2), encoding="utf-8")
    except OSError as error:
        print(f"Could not cache the robot config to {path}: {error}")
        return False
    return True


def load_cached_config():
    """The last robot's config, or None if there is none (or it is unreadable)."""
    path = cache_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return parse_robot_config(payload, source="cache")
    except FileNotFoundError:
        return None
    except (OSError, ValueError, RobotConfigError) as error:
        print(f"Ignoring the cached robot config at {path}: {error}")
        return None


def load_startup_config():
    """The config to model before any robot connects: cached, else Nougat's."""
    return load_cached_config() or DEFAULT_CONFIG


# ----------------------------------------------------------------- helpers


def get_simulator_dimensions(robot_config, mount_angles=True):
    """Map a robot's geometry to the simulator's dimension format.

    `mount_angles` carries each leg's coxia axis azimuth. The simulator would
    otherwise point every leg straight out from the cog, which is right for
    Mochi and Macaroon but not for Nougat, whose corner legs are angled at 45
    degrees while sitting at about 59.
    """
    config = robot_config["config"]
    dimensions = {
        "front": config["legMountX"][0],
        "side": config["legMountY"][0],
        "middle": config["legMountX"][1],
        "coxia": config["legJoint1ToJoint2"],
        "femur": config["legJoint2ToJoint3"],
        "tibia": config["legJoint3ToTip"],
    }
    if mount_angles:
        dimensions["mount_angles"] = [a % 360 for a in config["legMountAngle"]]
    return dimensions


def with_dimensions(robot_config, dimensions):
    """The robot's config with its body and legs measured as `dimensions`.

    `dimensions` is in get_simulator_dimensions()'s terms, as the Dimensions
    panel edits them. The mounts move with front, side and middle, each leg
    keeping its own side and mirroring; the legs take the new lengths. The
    legs keep the angles they are mounted at, whatever the body measures.
    Joint limits, gait and the rest are the robot's own.

    A measurement that is missing or not positive keeps the robot's.
    """
    if not isinstance(dimensions, dict):
        return robot_config
    current = get_simulator_dimensions(robot_config, mount_angles=False)

    def measure(name):
        value = dimensions.get(name)
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
        return float(value) if valid else current[name]

    new = {name: measure(name) for name in current}
    if new == current:
        return robot_config

    def rescaled(values, old, new_value):
        return [value * new_value / old if old else value for value in values]

    config = deepcopy(robot_config["config"])
    corners, middles = (0, 2, 3, 5), (1, 4)
    xs, ys = config["legMountX"], config["legMountY"]
    for leg in corners:
        xs[leg], ys[leg] = (
            rescaled([xs[leg]], current["front"], new["front"])[0],
            rescaled([ys[leg]], current["side"], new["side"])[0],
        )
    for leg in middles:
        xs[leg] = rescaled([xs[leg]], current["middle"], new["middle"])[0]
    config["legJoint1ToJoint2"] = new["coxia"]
    config["legJoint2ToJoint3"] = new["femur"]
    config["legJoint3ToTip"] = new["tibia"]

    return {**robot_config, "config": config}


def get_leg_signs(robot_config):
    """+1 or -1 per leg: how the femur and tibia servos are mirrored.

    From path_tool's legScale. Mochi and Macaroon mirror the left side; Nougat
    mirrors legs 0, 4 and 5.
    """
    return tuple(int(row[1]) for row in robot_config["config"]["legScale"])


def get_sequence_fps(robot_config, speed_pct=100):
    """Frame rate matching the robot's own LUT playback at a given speed.

    The firmware stretches each LUT frame to DELAY_MS * 100 / speed_pct.
    """
    return 1000.0 / robot_config["delay_ms"] * speed_pct / 100.0


def get_joint_limits(robot_config):
    """Mechanical travel limits in degrees."""
    return robot_config["joint_limits"]


def clamp_speed(robot_config, pct):
    speed = robot_config["speed"]
    return int(min(max(int(pct), speed["min"]), speed["max"]))


def command_id(robot_config, motion_name):
    """The robot's command id for a simulator motion name, else None.

    The simulator names motions with underscores ("walk_0"), the firmware
    without ("walk0"); the id is the name's position in the robot's own list.
    """
    firmware_name = motion_name.replace("_", "")
    try:
        return robot_config["commands"].index(firmware_name)
    except ValueError:
        return None


def describe(robot_config):
    """One line naming the robot the simulator is modelling."""
    if robot_config["source"] == "default":
        return f"{robot_config['label']} (default) — connect a robot to load its config"
    ssid = f" · {robot_config['ssid']}" if robot_config["ssid"] else ""
    if robot_config["source"] == "cache":
        return f"{robot_config['label']}{ssid} (last connected)"
    return f"{robot_config['label']}{ssid}"


def describe_firmware(firmware):
    """One line naming the connected robot's firmware (RobotLink.firmware)."""
    if not firmware:
        return "Firmware version not reported"
    build = f" ({firmware['build']})" if firmware["build"] else ""
    return f"Firmware {firmware['version']}{build} · protocol {firmware['protocol']}"
