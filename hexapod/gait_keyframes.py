# The robot's gaits worked out as keyframes. Once in a sequence on the pose
# page (pages/page_pose.py) they are keyframes like any other -- nothing
# marks where they came from -- to retime, edit, mix with poses of one's own
# or put in twice.
#
# A gait from the path generator (hexapod/path_generator.py) is a pose every
# frame of the robot's own timing -- 20 to 28 to a cycle -- with the feet on
# semicircles. Each pose is first held to the robot's joint limits, as the
# robot holds it when it plays the gait itself: some robots' gaits ask for a
# little more (Mochi's walk takes its femurs a few ticks past). Then each
# frame is turned into layers (hexapod/pose_layers.py):
#
#   * a frame in which the six feet are the standby stance moved as one -- the
#     Rotate gaits and Twist -- is the body moving over planted feet, so it
#     goes into the body layer, and is drawn and edited as a tilt; what a
#     joint limit takes off it (Mochi's Twist, under a millimetre) is left to
#     the feet;
#   * any other is feet moving, so it goes into the offsets, the body raised
#     or lowered to keep the lowest foot on the floor (Climb lowers them all).
#
# Then only the frames needed are kept: as few as leave every foot within
# TOLERANCE_MM of the gait's own path, and every joint within its limits,
# when the sequence is played, which moves in straight lines between them. A
# walk cycle comes to about a dozen. The times between them are the robot's
# own, at full speed, and none of the moves is eased, so a sequence played at
# 100 % walks as the robot does, and looping a cycle has no seam.

import numpy as np

from hexapod import keyframes as kf
from hexapod import pose_layers as pl
from hexapod.path_generator import generate_poses
from hexapod.robot_config import get_joint_limits, get_sequence_fps, get_simulator_dimensions

# How far (mm) a foot may stray from the gait's own path between keyframes.
TOLERANCE_MM = 1.0

# How closely (mm) the six feet must fit the stance moved as one for a frame
# to count as the body moving. The swaying gaits fit to under a millimetre,
# held to the joint limits or not; the others are 14 mm or more away.
RIGID_MM = 2.0

# Gaits that are not cycles: played once, from the first frame to the last.
ONE_SHOT = {"standup"}

# Points checked against the joints' limits between two frames of the gait,
# since a sequence played at another speed or frame rate lands between them.
LIMIT_CHECKS_PER_FRAME = 4


def robot_poses(motion_name, robot_config):
    """The gait's poses, each joint held to the robot's limits."""
    limits = {
        joint: limit - kf.LIMIT_MARGIN_DEG
        for joint, limit in get_joint_limits(robot_config).items()
    }
    poses = generate_poses(motion_name, robot_config)
    for pose in poses:
        for leg in pose.values():
            for joint, limit in limits.items():
                leg[joint] = min(max(leg[joint], -limit), limit)
    return poses


def _rotation_angles(rotation):
    """(rot_x, rot_y, rot_z) in degrees, with frame_rotxyz() of them being
    `rotation`: Rx @ Ry @ Rz."""
    rot_y = np.degrees(np.arcsin(np.clip(rotation[0, 2], -1.0, 1.0)))
    rot_x = np.degrees(np.arctan2(-rotation[1, 2], rotation[2, 2]))
    rot_z = np.degrees(np.arctan2(-rotation[0, 1], rotation[0, 0]))
    return rot_x, rot_y, rot_z


def _rigid_fit(feet, standby):
    """The rotation R and origin o that best put feet on standby, R @ f + o
    (Kabsch), and how far from it the worst foot is left."""
    feet_centre, standby_centre = feet.mean(axis=0), standby.mean(axis=0)
    u, _, vt = np.linalg.svd((feet - feet_centre).T @ (standby - standby_centre))
    reflect = np.sign(np.linalg.det(vt.T @ u.T))
    rotation = vt.T @ np.diag([1.0, 1.0, reflect]) @ u.T
    origin = standby_centre - rotation @ feet_centre
    error = np.abs(feet @ rotation.T + origin - standby).max()
    return rotation, origin, error


def frame_state(feet, robot_config):
    """The layers of a gait frame given by its feet in the body frame: the
    body moved over standby if the stance moved as one, else feet moved."""
    feet = np.asarray(feet, dtype=float)
    standby = np.asarray(kf.standby_feet(robot_config), dtype=float)
    rotation, origin, error = _rigid_fit(feet, standby)
    if error > RIGID_MM:
        rotation = np.eye(3)
        origin = np.array([0.0, 0.0, standby[:, 2].min() - feet[:, 2].min()])

    dimensions = get_simulator_dimensions(robot_config)
    rot_x, rot_y, rot_z = _rotation_angles(rotation)
    body = {
        "percent_x": origin[0] / dimensions["middle"],
        "percent_y": origin[1] / dimensions["side"],
        "percent_z": origin[2] / dimensions["tibia"],
        "rot_x": rot_x,
        "rot_y": rot_y,
        "rot_z": rot_z,
    }
    # The offsets are taken from the body as it is kept, rounded, so the two
    # layers still put the feet exactly where the gait has them.
    _, rotation, origin = pl._placement(pl.make_state(body, np.zeros((6, 3))), robot_config)
    return pl.make_state(body, feet @ rotation.T + origin - standby)


def _fits(vectors, feet, robot_config, start, end, tolerance):
    """Whether the move from frame `start` to frame `end`, with only those
    two kept, passes every frame in between within `tolerance` of where the
    gait has it, and stays within the joints' limits all the way."""
    a, b = vectors[start], vectors[end % len(vectors)]
    steps = (end - start) * LIMIT_CHECKS_PER_FRAME
    for step in range(1, steps):
        t = step / steps
        played = pl.body_feet(pl._from_vector(a + (b - a) * t), robot_config)
        if step % LIMIT_CHECKS_PER_FRAME == 0:
            index = start + step // LIMIT_CHECKS_PER_FRAME
            if np.abs(np.asarray(played) - feet[index]).max() > tolerance:
                return False
        if kf.feet_to_pose(played, robot_config)[1]:
            return False
    return True


def gait_keyframes(motion_name, robot_config, tolerance=TOLERANCE_MM):
    """The keyframes of one cycle of a gait, for `robot_config`.

    None is eased into, but the first of a one-off gait (standing up), from
    wherever the sequence was. The first one's time is the move into it from
    the end of the cycle, so a cycle put in twice, or looped, runs on without
    a seam.
    """
    poses = robot_poses(motion_name, robot_config)
    feet = [np.asarray(kf.pose_to_feet(pose, robot_config), dtype=float) for pose in poses]
    states = [frame_state(frame_feet, robot_config) for frame_feet in feet]
    count = len(states)

    if count == 1:
        state = states[0]
        return [kf.make_keyframe(pl.body_feet(state, robot_config), kf.DEFAULT_DURATION_MS, state)]

    cyclic = motion_name not in ONE_SHOT
    # A cycle closes on its first frame again, as frame `count`.
    last = count if cyclic else count - 1
    vectors = [pl._as_vector(state) for state in states]
    kept = [0]
    while kept[-1] < last:
        end = kept[-1] + 1
        while end < last and _fits(vectors, feet, robot_config, kept[-1], end + 1, tolerance):
            end += 1
        kept.append(end)

    period_ms = 1000.0 / get_sequence_fps(robot_config, 100)
    if cyclic:
        kept.pop()
        first_ms = (count - kept[-1]) * period_ms
    else:
        first_ms = kf.DEFAULT_DURATION_MS

    keyframes = []
    for position, index in enumerate(kept):
        state = states[index]
        duration_ms = first_ms if position == 0 else (index - kept[position - 1]) * period_ms
        keyframes.append(
            kf.make_keyframe(
                pl.body_feet(state, robot_config),
                duration_ms,
                state,
                # Into a one-off from wherever the sequence was, gently.
                ease=position == 0 and not cyclic,
            )
        )
    return keyframes
