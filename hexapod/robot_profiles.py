# Definitions for each physical hexapod the simulator can drive.
#
# The two robots live on separate branches of the firmware repo (`mochi` and
# `macaroon`). They share the same firmware, the same servo tick range and the
# same path_tool code; what differs is the leg geometry, the gait parameters
# used to bake the motion LUTs, and the servo step delay.
#
# Values below are taken from each branch's
#   software/path_tool/config.json       (geometry)
#   software/path_tool/lut_generator.ipynb  (gait parameters)
#   software/hexapod_esp32/config.h      (DELAY_MS, WiFi SSID)
# and must be kept in step with them, since the joint angles the simulator
# computes are only meaningful for the geometry they were derived from.

from copy import deepcopy

DEFAULT_PROFILE = "macaroon"

# Shared by both robots: leg mount azimuths, per-side mirroring, and the fact
# that joint 1 sits at the mount point.
_COMMON_CONFIG = {
    "legNames": [
        "front_right", "center_right", "rear_right",
        "front_left", "center_left", "rear_left",
    ],
    "legMountAngle": [60, 0, -60, -240, -180, -120],
    "legScale": [
        [1, 1, 1], [1, 1, 1], [1, 1, 1],
        [1, -1, -1], [1, -1, -1], [1, -1, -1],
    ],
    "legRootToJoint1": 0,
}

# Gait parameters as used by mochi's lut_generator notebook, which relies on
# path_tool's defaults throughout.
_MOCHI_GAIT = {
    "standby_posture": (60, 75),
    "laydown_posture": (25, 25),
    "walk_radius": 30,
    "turn_radius": 35,
    "fastwalk": {"g_steps": 28, "y_radius": 40, "z_radius": 30, "x_radius": 15},
    "rotate_x": {"g_steps": 28, "swing_angle": 10, "y_radius": 10},
    "rotate_y": {"g_steps": 28, "swing_angle": 10, "x_radius": 10},
    "rotate_z": {"g_steps": 28, "z_lift": 7},
    "twist": {"g_steps": 28},
    "standup_steps": 28,
}

# Macaroon is the larger robot and overrides the stride and turn radii.
_MACAROON_GAIT = deepcopy(_MOCHI_GAIT)
_MACAROON_GAIT.update(
    {
        "walk_radius": 50,
        "turn_radius": 50,
        "fastwalk": {"g_steps": 28, "y_radius": 70, "z_radius": 50, "x_radius": 20},
    }
)


def _make_config(front, mid, side, coxia, femur, tibia):
    """Build a path_tool geometry config.

    `front`/`mid`/`side` are the corner and middle leg mount offsets, matching
    the simulator's hexagon dimensions.
    """
    config = deepcopy(_COMMON_CONFIG)
    config.update(
        {
            "legMountX": [front, mid, front, -front, -mid, -front],
            "legMountY": [side, 0, -side, side, 0, -side],
            "legJoint1ToJoint2": coxia,
            "legJoint2ToJoint3": femur,
            "legJoint3ToTip": tibia,
        }
    )
    return config


ROBOT_PROFILES = {
    "mochi": {
        "label": "Mochi",
        "branch": "mochi",
        "ssid": "hexapod",
        "ip": "192.168.4.1",
        # config.h: DELAY_MS 12
        "delay_ms": 12,
        "config": _make_config(40.9, 81.8, 70.84, 36.0, 43.6, 85.22),
        "gait": _MOCHI_GAIT,
        "joint_limits": {"coxia": 45, "femur": 75, "tibia": 75},
    },
    "macaroon": {
        "label": "Macaroon",
        "branch": "macaroon",
        "ssid": "hexapod_macaroon",
        "ip": "192.168.4.1",
        # config.h: DELAY_MS 25
        "delay_ms": 25,
        "config": _make_config(49.2, 98.4, 85.22, 62.0, 76.0, 132.0),
        "gait": _MACAROON_GAIT,
        "joint_limits": {"coxia": 45, "femur": 75, "tibia": 75},
    },
}

PROFILE_OPTIONS = [
    {"label": f"{profile['label']} ({profile['ssid']})", "value": name}
    for name, profile in ROBOT_PROFILES.items()
]


def get_profile(name):
    """Return a profile by name, falling back to the default."""
    return ROBOT_PROFILES.get(name) or ROBOT_PROFILES[DEFAULT_PROFILE]


def get_physical_config(name):
    """Return the path_tool-style geometry config for a profile."""
    return get_profile(name)["config"]


def get_simulator_dimensions(name):
    """Map a profile's geometry to the simulator's dimension format."""
    config = get_physical_config(name)
    return {
        "front": config["legMountX"][0],
        "side": config["legMountY"][0],
        "middle": config["legMountX"][1],
        "coxia": config["legJoint1ToJoint2"],
        "femur": config["legJoint2ToJoint3"],
        "tibia": config["legJoint3ToTip"],
    }


def get_sequence_fps(name):
    """Frame rate matching the robot's own LUT playback (1000 / DELAY_MS)."""
    return 1000.0 / get_profile(name)["delay_ms"]


def get_joint_limits(name):
    """Mechanical travel limits in degrees for a profile."""
    return get_profile(name)["joint_limits"]
