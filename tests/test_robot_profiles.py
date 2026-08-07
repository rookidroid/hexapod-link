"""Profiles are the bridge between path_tool's config and the simulator's model.

The joint angles the simulator computes are only meaningful for the geometry
they were derived from, so the two representations of that geometry -- the
path_tool-style config dict and the simulator's dimensions dict -- have to stay
in step. These tests pin the mapping between them and the invariants the mount
layout depends on.
"""

import pytest

from hexapod.models import VirtualHexapod
from hexapod.robot_profiles import (
    DEFAULT_PROFILE,
    PROFILE_OPTIONS,
    ROBOT_PROFILES,
    get_joint_limits,
    get_physical_config,
    get_profile,
    get_sequence_fps,
    get_simulator_dimensions,
)


def test_the_default_profile_exists():
    """Every lookup falls back to it, so a stale name would break all of them."""
    assert DEFAULT_PROFILE in ROBOT_PROFILES


def test_an_unknown_profile_falls_back_to_the_default():
    """The UI can hold a stale profile name; that must not raise mid-callback."""
    default = ROBOT_PROFILES[DEFAULT_PROFILE]
    assert get_profile("no-such-robot") is default
    assert get_profile(None) is default
    assert get_profile("") is default


def test_every_profile_is_complete():
    """A profile missing a key would fail far from here, inside a gait or a send."""
    for name, profile in ROBOT_PROFILES.items():
        for key in ("label", "branch", "ssid", "ip", "delay_ms", "config", "gait"):
            assert key in profile, f"{name} has no {key}"
        for key in ("coxia", "femur", "tibia"):
            assert key in profile["joint_limits"], f"{name} has no {key} limit"


def test_profile_options_cover_every_profile():
    """The dropdown is built from this, so a missing entry hides a whole robot."""
    assert {option["value"] for option in PROFILE_OPTIONS} == set(ROBOT_PROFILES)
    for option in PROFILE_OPTIONS:
        profile = ROBOT_PROFILES[option["value"]]
        # The SSID is in the label because the machine has to join that network
        # before the robot is reachable at all.
        assert profile["ssid"] in option["label"]


def test_simulator_dimensions_read_the_mount_layout_back_out():
    """The dimensions dict must describe the same body as the config it came from.

    `front` and `side` are the corner mount offsets and `middle` is the middle
    leg's, which is how _make_config laid them out; reading them back from the
    wrong index would build a body of the wrong shape while still looking valid.
    """
    for name in ROBOT_PROFILES:
        config = get_physical_config(name)
        dimensions = get_simulator_dimensions(name)

        assert dimensions["front"] == config["legMountX"][0]
        assert dimensions["side"] == config["legMountY"][0]
        assert dimensions["middle"] == config["legMountX"][1]
        assert dimensions["coxia"] == config["legJoint1ToJoint2"]
        assert dimensions["femur"] == config["legJoint2ToJoint3"]
        assert dimensions["tibia"] == config["legJoint3ToTip"]


def test_the_mount_layout_is_mirrored_left_to_right():
    """Corner mounts sit at +/-front and +/-side, and the middles on the x axis.

    The gait generators aim each stroke by the leg's own azimuth, computed from
    these offsets, so an asymmetric layout would quietly skew every path.
    """
    for name in ROBOT_PROFILES:
        config = get_physical_config(name)
        x, y = config["legMountX"], config["legMountY"]

        assert x[0] == x[2] == -x[3] == -x[5], f"{name}: corner x not mirrored"
        assert y[0] == -y[2] == y[3] == -y[5], f"{name}: corner y not mirrored"
        assert y[1] == y[4] == 0, f"{name}: middle legs are off the x axis"
        assert x[1] == -x[4], f"{name}: middle legs not mirrored"


def test_every_profile_builds_a_hexapod():
    """The end of the mapping: these dimensions have to make a model that stands."""
    for name in ROBOT_PROFILES:
        hexapod = VirtualHexapod(get_simulator_dimensions(name))
        assert len(hexapod.legs) == 6
        assert len(hexapod.ground_contacts) >= 3, (
            f"{name}: a standing hexapod needs at least three feet down"
        )


def test_sequence_fps_matches_the_firmware_delay():
    """Gait playback rate is 1000 / DELAY_MS, the robot's own LUT frame rate.

    Streaming at anything else plays a baked gait back at the wrong speed.
    """
    for name, profile in ROBOT_PROFILES.items():
        assert get_sequence_fps(name) == pytest.approx(1000.0 / profile["delay_ms"])

    # The two robots are deliberately geared differently; mochi is the faster.
    assert get_sequence_fps("mochi") > get_sequence_fps("macaroon")


def test_joint_limits_are_symmetric_and_positive():
    """clamp_pose_angles treats a limit as +/-limit, so a negative one inverts it."""
    for name in ROBOT_PROFILES:
        for joint, limit in get_joint_limits(name).items():
            assert limit > 0, f"{name}: {joint} limit {limit} is not positive"


def test_macaroon_is_the_larger_robot():
    """Its longer legs are why it gets the wider stride and turn radii."""
    mochi = get_simulator_dimensions("mochi")
    macaroon = get_simulator_dimensions("macaroon")
    for key in ("coxia", "femur", "tibia", "front", "middle", "side"):
        assert macaroon[key] > mochi[key], f"macaroon should have the larger {key}"

    assert get_profile("macaroon")["gait"]["walk_radius"] > (
        get_profile("mochi")["gait"]["walk_radius"]
    )


def test_the_profiles_do_not_share_mutable_gait_state():
    """macaroon's gait is a deepcopy of mochi's, so editing one must not move both."""
    mochi_gait = get_profile("mochi")["gait"]
    macaroon_gait = get_profile("macaroon")["gait"]
    assert mochi_gait is not macaroon_gait
    assert mochi_gait["fastwalk"] is not macaroon_gait["fastwalk"]
