"""The wire format between the simulator and the ESP32.

Everything here mirrors something in the firmware repo -- SERVOMIN/SERVOMAX and
the packed structs in config.h, the RobotCommand enum, the baked lut_standby --
and none of it is checked at runtime: a wrong tick is a servo driven into a hard
stop, and a wrong struct layout is a packet the firmware silently misreads. The
tests below are the only place those constants are held to their originals.

RobotLink itself owns a socket and a thread, so what is exercised here is the
pure conversion layer it is built on, plus the packet encoding.
"""

import struct

import pytest

from hexapod.path_generator import generate_poses
from hexapod.robot_link import (
    LEG_SIGN,
    MAGIC_MOTION,
    MAGIC_POSE,
    MAGIC_SESSION,
    MOTION_COMMANDS,
    SERVO_MAX_TICKS,
    SERVO_MIN_TICKS,
    STANDBY_POSE,
    _FMT_MOTION,
    _FMT_POSE,
    _FMT_SESSION,
    clamp_pose_angles,
    joint_angles_to_servo_angles,
    pose_to_ticks,
    servo_angle_to_ticks,
)
from hexapod.robot_profiles import ROBOT_PROFILES, get_joint_limits
from widgets.motion_ui import MOTION_TYPES

# The firmware's lut_standby, right legs. Both robots bake standby from
# gen_posture(60, 75), whose joint angles do not depend on link lengths.
FIRMWARE_STANDBY_RIGHT = [307, 239, 273]


def test_standby_pose_reproduces_the_firmware_lut():
    """The one end-to-end anchor: our standby must be the robot's standby.

    If this drifts, connecting to the robot jerks it out of the posture it
    booted into, which is the whole reason STANDBY_POSE was decoded from the
    LUT rather than guessed.
    """
    ticks = pose_to_ticks(STANDBY_POSE)
    assert len(ticks) == 18
    for leg_id in range(3):
        assert ticks[leg_id * 3 : leg_id * 3 + 3] == FIRMWARE_STANDBY_RIGHT, (
            f"right leg {leg_id} does not match the firmware's lut_standby"
        )


def test_left_legs_mirror_the_right_ones():
    """Left servos are mounted facing the other way, so LEG_SIGN flips j2 and j3.

    In ticks that mirroring is a reflection about the 90deg centre: coxia is
    untouched, femur and tibia land the same distance the other side of it.
    """
    ticks = pose_to_ticks(STANDBY_POSE)
    centre = servo_angle_to_ticks(90)

    for right_id, left_id in zip(range(3), range(3, 6)):
        right = ticks[right_id * 3 : right_id * 3 + 3]
        left = ticks[left_id * 3 : left_id * 3 + 3]
        assert right[0] == left[0] == centre, "coxia is not mirrored"
        assert right[1] - centre == centre - left[1], "femur is not mirrored"
        assert right[2] - centre == centre - left[2], "tibia is not mirrored"


def test_leg_sign_splits_the_sides():
    """+1 for the right legs (0-2), -1 for the left (3-5)."""
    assert LEG_SIGN == (1, 1, 1, -1, -1, -1)


def test_servo_angles_put_zero_at_the_centre():
    """A zeroed simulator pose is every servo at 90deg, its mechanical centre."""
    for leg_id in range(6):
        assert joint_angles_to_servo_angles(leg_id, 0, 0, 0) == (90.0, 90.0, 90.0)


def test_servo_angle_to_ticks_spans_the_firmware_range():
    """0-180deg maps onto SERVOMIN-SERVOMAX linearly, with 90deg at the midpoint."""
    assert servo_angle_to_ticks(0) == SERVO_MIN_TICKS
    assert servo_angle_to_ticks(180) == SERVO_MAX_TICKS
    assert servo_angle_to_ticks(90) == pytest.approx(
        (SERVO_MIN_TICKS + SERVO_MAX_TICKS) / 2, abs=1
    )


def test_servo_angle_to_ticks_clamps_and_returns_an_int():
    """struct.pack needs an int, and out-of-range angles must not leave the range.

    Clamping here is the last guard before the packet: a tick outside
    SERVOMIN/SERVOMAX is a servo commanded past its stop.
    """
    for angle in (-1000, -0.1, 180.1, 1000):
        ticks = servo_angle_to_ticks(angle)
        assert isinstance(ticks, int)
        assert SERVO_MIN_TICKS <= ticks <= SERVO_MAX_TICKS

    assert servo_angle_to_ticks(-1000) == SERVO_MIN_TICKS
    assert servo_angle_to_ticks(1000) == SERVO_MAX_TICKS


def test_clamp_pose_angles_holds_the_mechanical_limits():
    """The simulator lets beta and gamma reach +/-180; the hardware does not."""
    for name in ROBOT_PROFILES:
        limits = get_joint_limits(name)
        clamped = clamp_pose_angles(180, 180, 180, name)
        assert clamped == (limits["coxia"], limits["femur"], limits["tibia"])

        clamped = clamp_pose_angles(-180, -180, -180, name)
        assert clamped == (-limits["coxia"], -limits["femur"], -limits["tibia"])

        # An already-legal pose passes through untouched.
        assert clamp_pose_angles(1, 2, 3, name) == (1, 2, 3)


def test_pose_to_ticks_accepts_int_or_str_leg_keys():
    """Pose dicts arrive from Dash callbacks, where keys have been through JSON."""
    by_int = pose_to_ticks(STANDBY_POSE)
    by_str = pose_to_ticks({str(k): v for k, v in STANDBY_POSE.items()})
    assert by_int == by_str


def test_pose_to_ticks_treats_a_missing_leg_as_centred():
    """A partial pose must still produce 18 ticks rather than a short packet."""
    ticks = pose_to_ticks({})
    assert len(ticks) == 18
    assert set(ticks) == {servo_angle_to_ticks(90)}

    # A leg present but with a missing angle is centred on that joint alone.
    ticks = pose_to_ticks({0: {"coxia": 0.0, "femur": None}})
    assert len(ticks) == 18


def test_pose_to_ticks_never_leaves_the_servo_range():
    """Whatever a gait asks for, every tick in the packet has to be sendable."""
    for name in ROBOT_PROFILES:
        for motion_name in ("walk_0", "turn_left", "twist", "standup"):
            for pose in generate_poses(motion_name, name):
                ticks = pose_to_ticks(pose, name)
                assert len(ticks) == 18
                assert all(
                    SERVO_MIN_TICKS <= t <= SERVO_MAX_TICKS for t in ticks
                ), f"{name}/{motion_name} produced an out-of-range tick"


def test_streaming_a_gait_clips_it_against_the_joint_limits():
    """Recorded behaviour, not an endorsement: the gaits overrun the femur limit.

    mochi's walking and turning paths ask for up to ~3.5 degrees more femur than
    its joint_limits allow, so clamp_pose_angles flattens the extremes of the
    stride on the way to the servos and the streamed gait is slightly shallower
    than the simulated one. macaroon overruns by under half a degree.

    Either the limits are more conservative than the hardware or the gait radii
    are too wide for it; this test exists so that whichever way it is resolved,
    it is resolved deliberately rather than noticed on the robot.
    """
    overruns = {}
    for profile_name in ROBOT_PROFILES:
        limits = get_joint_limits(profile_name)
        worst = 0.0
        for motion_name in ("walk_0", "walk_l90", "turn_left"):
            for pose in generate_poses(motion_name, profile_name):
                for entry in pose.values():
                    worst = max(worst, abs(entry["femur"]) - limits["femur"])
        overruns[profile_name] = worst

    assert overruns["mochi"] == pytest.approx(3.53, abs=0.1), (
        f"mochi's femur overrun moved to {overruns['mochi']:.2f} deg"
    )
    assert 0 < overruns["macaroon"] < 1, (
        f"macaroon's femur overrun moved to {overruns['macaroon']:.2f} deg"
    )


def test_packet_layouts_match_the_firmware_structs():
    """The firmware's structs are #pragma pack(1) at 6 / 44 / 6 bytes.

    '<' is what keeps these little-endian and unpadded; without it Python pads
    to native alignment and every field after the first lands in the wrong place.
    """
    assert struct.calcsize(_FMT_MOTION) == 6
    assert struct.calcsize(_FMT_POSE) == 44
    assert struct.calcsize(_FMT_SESSION) == 6


def test_a_pose_packet_round_trips():
    """The 18 ticks must survive encoding in the order the firmware reads them."""
    ticks = pose_to_ticks(STANDBY_POSE)
    packet = struct.pack(_FMT_POSE, MAGIC_POSE, 0x01, 8, 42, *ticks)

    magic, flags, max_step, seq, *decoded = struct.unpack(_FMT_POSE, packet)
    assert magic == MAGIC_POSE
    assert flags == 0x01
    assert max_step == 8
    assert seq == 42
    assert decoded == ticks


def test_the_magics_are_distinct():
    """The firmware dispatches on the first byte alone."""
    assert len({MAGIC_MOTION, MAGIC_POSE, MAGIC_SESSION}) == 3


def test_motion_command_ids_are_unique_and_fit_a_byte():
    """They are packed as 'B' and must line up with the firmware's enum."""
    ids = list(MOTION_COMMANDS.values())
    assert len(set(ids)) == len(ids), "two motions share a command id"
    assert all(0 <= i <= 255 for i in ids)
    # The enum is contiguous from standby at 0.
    assert sorted(ids) == list(range(len(ids)))
    assert MOTION_COMMANDS["standby"] == 0


def test_every_robot_command_is_a_motion_the_ui_offers():
    """A command the UI cannot reach is unreachable; the reverse is allowed.

    'standup' is the exception in the other direction: it is the firmware's boot
    sequence rather than a LUT it can be commanded into, so the UI offers it for
    streaming only. pages/shared.py depends on exactly that asymmetry.
    """
    ui_motions = {option["value"] for option in MOTION_TYPES}
    assert set(MOTION_COMMANDS) <= ui_motions, (
        f"robot commands the UI cannot reach: {set(MOTION_COMMANDS) - ui_motions}"
    )
    assert ui_motions - set(MOTION_COMMANDS) == {"standup"}
