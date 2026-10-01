"""The wire format between the simulator and the ESP32.

Everything here mirrors something in the firmware repo -- SERVOMIN/SERVOMAX and
the packed structs in protocol.h, the RobotCommand enum, the baked motion LUTs
-- and none of it is checked at runtime: a wrong tick is a servo driven into a
hard stop, and a wrong struct layout is a packet the firmware silently misreads.
The tests below are the only place those constants are held to their originals.

RobotLink itself owns a socket and a thread, so what is exercised here is the
pure conversion layer it is built on, plus the packet encoding. Connecting --
reading the robot's config first -- is covered in test_robot_config.py.
"""

import struct

import numpy as np
import pytest

from hexapod.path_generator import generate_poses
from hexapod.robot_config import (
    FIRMWARE_COMMANDS,
    GENERIC_CONFIG,
    command_id,
    get_joint_limits,
    get_leg_signs,
    get_sequence_fps,
)
from hexapod.robot_link import (
    MAGIC_MOTION,
    MAGIC_POSE,
    MAGIC_SESSION,
    MAGIC_VERSION,
    MOTION_COMMANDS,
    STANDBY_POSE,
    RobotLink,
    _FMT_MOTION,
    _FMT_POSE,
    _FMT_SESSION,
    _FMT_VERSION_REPLY,
    _FMT_VERSION_REQUEST,
    clamp_pose_angles,
    joint_angles_to_servo_angles,
    parse_version_reply,
    pose_to_ticks,
    servo_angle_to_ticks,
)
from tests.robots import ROBOT_CONFIGS, load_firmware_luts
from widgets.motion_ui import MOTION_TYPES

SERVO_MIN_TICKS = 102
SERVO_MAX_TICKS = 512

# The firmware's lut_standby for an unmirrored leg. Every robot bakes standby
# from gen_posture(60, 75), whose joint angles do not depend on link lengths.
FIRMWARE_STANDBY_UNMIRRORED = [307, 239, 273]
FIRMWARE_STANDBY_MIRRORED = [307, 375, 341]


def _leg(ticks, leg_id):
    return ticks[leg_id * 3 : leg_id * 3 + 3]


def test_standby_pose_reproduces_the_firmware_lut():
    """The one end-to-end anchor: our standby must be the robot's standby.

    If this drifts, connecting to the robot jerks it out of the posture it
    booted into, which is the whole reason STANDBY_POSE was decoded from the
    LUT rather than guessed. Checked against each robot's own motion.h.
    """
    for name, robot in ROBOT_CONFIGS.items():
        ticks = pose_to_ticks(STANDBY_POSE, robot)
        assert ticks == load_firmware_luts(name)["standby"][0], name


def test_standby_follows_each_robots_mirroring():
    """Which legs are mirrored comes from the robot's legScale.

    Mochi and Macaroon mirror the left side; Nougat mirrors legs 0, 4 and 5.
    """
    expected_mirrored = {
        "mochi": {3, 4, 5},
        "macaroon": {3, 4, 5},
        "nougat": {0, 4, 5},
    }
    for name, robot in ROBOT_CONFIGS.items():
        ticks = pose_to_ticks(STANDBY_POSE, robot)
        for leg_id in range(6):
            mirrored = leg_id in expected_mirrored[name]
            expected = FIRMWARE_STANDBY_MIRRORED if mirrored else FIRMWARE_STANDBY_UNMIRRORED
            assert _leg(ticks, leg_id) == expected, f"{name} leg {leg_id}"


@pytest.mark.parametrize("name", ["nougat", "macaroon"])
def test_a_streamed_walk_is_the_robots_own_walk(name):
    """Streaming walk_0 from the simulator sends exactly the robot's LUT.

    The whole chain -- path generation, IK around the robot's mount angles, the
    per-leg mirroring and the tick conversion -- against the firmware's baked
    lut_walk_0, tick for tick.
    """
    robot = ROBOT_CONFIGS[name]
    ticks = [pose_to_ticks(pose, robot) for pose in generate_poses("walk_0", robot)]
    assert ticks == load_firmware_luts(name)["walk_0"]


def test_a_streamed_mochi_walk_differs_only_where_it_is_clamped():
    """Mochi's walk asks for more femur than its joint limits allow (see below),
    so the streamed walk matches the LUT except for a few clipped ticks."""
    robot = ROBOT_CONFIGS["mochi"]
    ticks = np.array([pose_to_ticks(p, robot) for p in generate_poses("walk_0", robot)])
    lut = np.array(load_firmware_luts("mochi")["walk_0"])
    diff = np.abs(ticks - lut)
    assert diff.max() <= 4
    # Only femurs (joint index 1 of each leg) are clipped.
    assert set(np.nonzero(diff > 1)[1] % 3) == {1}


def test_leg_signs_come_from_leg_scale():
    assert get_leg_signs(ROBOT_CONFIGS["mochi"]) == (1, 1, 1, -1, -1, -1)
    assert get_leg_signs(ROBOT_CONFIGS["macaroon"]) == (1, 1, 1, -1, -1, -1)
    assert get_leg_signs(ROBOT_CONFIGS["nougat"]) == (-1, 1, 1, 1, -1, -1)
    assert get_leg_signs(GENERIC_CONFIG) == (1, 1, 1, -1, -1, -1)


def test_mirrored_legs_reflect_about_the_centre():
    """A mirrored servo lands the same distance the other side of 90 degrees.

    Coxia is untouched, femur and tibia are reflected.
    """
    for sign in (1, -1):
        j1, j2, j3 = joint_angles_to_servo_angles(sign, 10, 20, -30)
        m1, m2, m3 = joint_angles_to_servo_angles(-sign, 10, 20, -30)
        assert j1 == m1
        assert j2 - 90 == 90 - m2
        assert j3 - 90 == 90 - m3


def test_servo_angles_put_zero_at_the_centre():
    """A zeroed simulator pose is every servo at 90deg, its mechanical centre."""
    for sign in (1, -1):
        assert joint_angles_to_servo_angles(sign, 0, 0, 0) == (90.0, 90.0, 90.0)


def test_servo_angle_to_ticks_spans_the_firmware_range():
    """0-180deg maps onto SERVOMIN-SERVOMAX linearly, with 90deg at the midpoint."""
    assert servo_angle_to_ticks(0) == SERVO_MIN_TICKS
    assert servo_angle_to_ticks(180) == SERVO_MAX_TICKS
    assert servo_angle_to_ticks(90) == pytest.approx(
        (SERVO_MIN_TICKS + SERVO_MAX_TICKS) / 2, abs=1
    )


def test_servo_angle_to_ticks_follows_the_robots_range():
    """The range is the robot's, as it reports it."""
    assert servo_angle_to_ticks(0, 150, 600) == 150
    assert servo_angle_to_ticks(180, 150, 600) == 600
    assert servo_angle_to_ticks(90, 150, 600) == 375


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
    for robot in ROBOT_CONFIGS.values():
        limits = get_joint_limits(robot)
        clamped = clamp_pose_angles(180, 180, 180, robot)
        assert clamped == (limits["coxia"], limits["femur"], limits["tibia"])

        clamped = clamp_pose_angles(-180, -180, -180, robot)
        assert clamped == (-limits["coxia"], -limits["femur"], -limits["tibia"])

        # An already-legal pose passes through untouched.
        assert clamp_pose_angles(1, 2, 3, robot) == (1, 2, 3)


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
    for name, robot in ROBOT_CONFIGS.items():
        for motion_name in ("walk_0", "turn_left", "twist", "standup"):
            for pose in generate_poses(motion_name, robot):
                ticks = pose_to_ticks(pose, robot)
                assert len(ticks) == 18
                assert all(
                    SERVO_MIN_TICKS <= t <= SERVO_MAX_TICKS for t in ticks
                ), f"{name}/{motion_name} produced an out-of-range tick"


def test_streaming_a_gait_clips_it_against_the_joint_limits():
    """Recorded behaviour, not an endorsement: some gaits overrun the femur limit.

    mochi's walking and turning paths ask for up to ~3.5 degrees more femur than
    its joint_limits allow, so clamp_pose_angles flattens the extremes of the
    stride on the way to the servos and the streamed gait is slightly shallower
    than the simulated one. macaroon overruns by under half a degree, and
    nougat stays inside its limits.

    Either the limits are more conservative than the hardware or the gait radii
    are too wide for it; this test exists so that whichever way it is resolved,
    it is resolved deliberately rather than noticed on the robot.
    """
    overruns = {}
    for name, robot in ROBOT_CONFIGS.items():
        limits = get_joint_limits(robot)
        worst = -np.inf
        for motion_name in ("walk_0", "walk_l90", "turn_left"):
            for pose in generate_poses(motion_name, robot):
                for entry in pose.values():
                    worst = max(worst, abs(entry["femur"]) - limits["femur"])
        overruns[name] = worst

    assert overruns["mochi"] == pytest.approx(3.53, abs=0.1), (
        f"mochi's femur overrun moved to {overruns['mochi']:.2f} deg"
    )
    assert 0 < overruns["macaroon"] < 1, (
        f"macaroon's femur overrun moved to {overruns['macaroon']:.2f} deg"
    )
    assert overruns["nougat"] < 0, (
        f"nougat now overruns its femur limit by {overruns['nougat']:.2f} deg"
    )


def test_packet_layouts_match_the_firmware_structs():
    """The firmware's structs are #pragma pack(1) at 7 / 44 / 6 bytes.

    The motion packet is UdpControlSpeedPacket, the form that carries the gait
    speed. '<' is what keeps these little-endian and unpadded; without it Python
    pads to native alignment and every field after the first lands in the wrong
    place.
    """
    assert struct.calcsize(_FMT_MOTION) == 7
    assert struct.calcsize(_FMT_POSE) == 44
    assert struct.calcsize(_FMT_SESSION) == 6
    # UdpVersionRequest, and the fixed head of UdpVersionReply
    assert struct.calcsize(_FMT_VERSION_REQUEST) == 5
    assert struct.calcsize(_FMT_VERSION_REPLY) == 9


def test_a_version_reply_decodes():
    """The build tag runs to the end of the datagram, unterminated."""
    reply = struct.pack(_FMT_VERSION_REPLY, MAGIC_VERSION, 7, 1, 3, 2, 0) + b"v3.2.0"
    assert parse_version_reply(reply, 7) == {
        "version": "3.2.0",
        "build": "v3.2.0",
        "protocol": 1,
    }


def test_a_reply_to_another_query_is_ignored():
    reply = struct.pack(_FMT_VERSION_REPLY, MAGIC_VERSION, 6, 1, 3, 2, 0) + b"dev"
    assert parse_version_reply(reply, 7) is None
    assert parse_version_reply(reply[:8], 6) is None
    assert parse_version_reply(b"Got 5 bytes of data", 6) is None


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


class _CapturingLink(RobotLink):
    """A link whose packets are captured rather than sent."""

    def __init__(self, robot_config):
        super().__init__(robot_config)
        self.sent = []

    def _send(self, packet):
        self.sent.append(packet)
        return True


def test_a_motion_command_carries_the_speed():
    link = _CapturingLink(ROBOT_CONFIGS["nougat"])
    link.set_motion_speed(80)
    assert link.send_motion_command("walk_l90")

    magic, command, _seq, speed = struct.unpack(_FMT_MOTION, link.sent[-1])
    assert magic == MAGIC_MOTION
    assert command == MOTION_COMMANDS["walk_l90"]
    assert speed == 80


def test_the_speed_is_clamped_to_the_robots_range():
    link = _CapturingLink(ROBOT_CONFIGS["nougat"])
    assert link.set_motion_speed(5) == 20
    assert link.set_motion_speed(250) == 100


def test_streamed_gaits_play_at_the_robots_speed():
    """The firmware stretches each frame to DELAY_MS * 100 / speed."""
    for robot in ROBOT_CONFIGS.values():
        assert get_sequence_fps(robot, 50) == pytest.approx(
            1000.0 / robot["delay_ms"] / 2
        )

    link = _CapturingLink(ROBOT_CONFIGS["macaroon"])
    link.set_motion_speed(40)
    link.play_sequence(generate_poses("walk_0", ROBOT_CONFIGS["macaroon"]))
    assert link._sequence_fps == pytest.approx(1000.0 / 25 * 0.4)

    # Changing the speed mid-gait retimes the gait.
    link.set_motion_speed(100)
    assert link._sequence_fps == pytest.approx(1000.0 / 25)


def test_an_unknown_motion_is_not_sent():
    link = _CapturingLink(ROBOT_CONFIGS["nougat"])
    assert not link.send_motion_command("standup")
    assert not link.has_motion_command("standup")
    assert link.sent == []


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


def test_the_robots_command_list_resolves_every_motion():
    """The link takes command ids from the robot's own list; for the current
    firmware that must agree with the enum above."""
    for robot in list(ROBOT_CONFIGS.values()) + [GENERIC_CONFIG]:
        assert robot["commands"] == FIRMWARE_COMMANDS
        for motion_name, expected in MOTION_COMMANDS.items():
            assert command_id(robot, motion_name) == expected, motion_name


def test_every_robot_command_is_a_motion_the_ui_offers():
    """A command the UI cannot reach is unreachable; the reverse is allowed.

    'standup' is the exception in the other direction: it is the firmware's boot
    sequence rather than a LUT it can be commanded into, so the UI offers it for
    streaming only. pages/page_motion.py depends on exactly that asymmetry.
    """
    ui_motions = {option["value"] for option in MOTION_TYPES}
    assert set(MOTION_COMMANDS) <= ui_motions, (
        f"robot commands the UI cannot reach: {set(MOTION_COMMANDS) - ui_motions}"
    )
    assert ui_motions - set(MOTION_COMMANDS) == {"standup"}
