"""Robot configs for the tests, as the robots themselves report them.

The app keeps no robot definitions; it reads each robot's config from the robot
(GET /robot_config). These fixtures are that reply for each robot in the
family, built from the firmware repo's software/path_tool/robots/<name>.json and
the firmware's robot_config.h. tests/fixtures/firmware_luts holds a few of each
robot's baked motion LUTs from its motion.h, the ground truth the tick
conversion is checked against.
"""

import json
from pathlib import Path

from hexapod.robot_config import parse_robot_config

FIXTURES = Path(__file__).parent / "fixtures"


def load_payload(name):
    with open(FIXTURES / "robot_config" / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def load_firmware_luts(name):
    with open(FIXTURES / "firmware_luts" / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)["luts"]


ROBOT_NAMES = ("nougat", "mochi", "macaroon")

ROBOT_CONFIGS = {name: parse_robot_config(load_payload(name)) for name in ROBOT_NAMES}
