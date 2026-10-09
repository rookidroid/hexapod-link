# One pose in two layers on top of the robot's standby posture, as the pose
# page (pages/page_pose.py) edits it:
#
#   offsets  how far each foot has been moved from where standby plants it,
#            in the world (6x3, mm).
#   body     how the body is moved and tilted over the planted feet: a shift
#            as a fraction of the body's size, and rotations in degrees, as
#            the inverse kinematics sliders have always meant them.
#
# The layers add up rather than replace each other, so each tool's controls
# keep meaning what they say whichever tool was used last: tilting the body
# keeps the feet where they were put, and moving a foot keeps the tilt.
#
# Out of the layers come the feet in the body frame (hexapod/keyframes.py) --
# what the joints are solved from, what is streamed to the robot -- and the
# scene, drawn in the world with the floor at z = 0.
#
# The world here is the body frame of the robot at standby: x right, y
# forward, z up, the floor at kf.ground_height(). The view's frame is the same
# raised to put the floor at z = 0.

import numpy as np

from hexapod import keyframes as kf
from hexapod.models import VirtualHexapod
from hexapod.points import frame_rotxyz
from hexapod.robot_config import get_simulator_dimensions
from hexapod.scene import hexapod_to_scene, order_around_centre, transform_scene

BODY_KEYS = ("percent_x", "percent_y", "percent_z", "rot_x", "rot_y", "rot_z")


def _number(value):
    # Rounded and without -0.0, for the same reason as kf.clean_feet().
    return round(float(value or 0), 4) + 0.0


def make_state(body, offsets):
    return {
        "body": {key: _number(body.get(key)) for key in BODY_KEYS},
        "offsets": kf.clean_feet(offsets),
    }


def standby_state():
    """The robot's standby posture, with nothing moved."""
    return make_state({}, np.zeros((6, 3)))


def is_state(state):
    """Whether `state` is a pose in layers, e.g. one read back from a file."""
    if not isinstance(state, dict):
        return False
    try:
        numbers = [float(state["body"][key]) for key in BODY_KEYS]
        offsets = np.asarray(state["offsets"], dtype=float)
    except (KeyError, TypeError, ValueError):
        return False
    return offsets.shape == (6, 3) and np.isfinite(numbers).all() and np.isfinite(offsets).all()


def _placement(state, robot_config):
    """Where the feet are planted in the world, and the body's frame in it.

    A point p in the body frame is at rotation @ p + origin in the world.
    """
    dimensions = get_simulator_dimensions(robot_config)
    body = state["body"]
    rotation = frame_rotxyz(body["rot_x"], body["rot_y"], body["rot_z"])[:3, :3]
    origin = np.array(
        [
            body["percent_x"] * dimensions["middle"],
            body["percent_y"] * dimensions["side"],
            body["percent_z"] * dimensions["tibia"],
        ]
    )
    planted = np.asarray(kf.standby_feet(robot_config)) + np.asarray(state["offsets"], dtype=float)
    return planted, rotation, origin


def body_feet(state, robot_config):
    """The feet in the body frame: what the joints are solved from."""
    planted, rotation, origin = _placement(state, robot_config)
    # rotation.T @ (p - origin), for each foot as a row.
    return kf.clean_feet((planted - origin) @ rotation)


def solve(state, robot_config):
    """(feet, pose, bad_legs) for a state; see kf.feet_to_pose()."""
    feet = body_feet(state, robot_config)
    pose, bad_legs = kf.feet_to_pose(feet, robot_config)
    return feet, pose, bad_legs


def view_feet(state, robot_config):
    """Where the feet are planted, in the view's coordinates (floor at z = 0)."""
    planted, _, _ = _placement(state, robot_config)
    return kf.clean_feet(planted - [0.0, 0.0, kf.ground_height(robot_config)])


def with_foot_at(state, leg, target, robot_config):
    """The state with one foot moved to `target`, in the view's coordinates."""
    world = np.asarray(target, dtype=float) + [0.0, 0.0, kf.ground_height(robot_config)]
    offsets = np.array(state["offsets"], dtype=float)
    offsets[leg] = world - kf.standby_feet(robot_config)[leg]
    return make_state(state["body"], offsets)


def with_leg_angles(state, leg, angles, robot_config):
    """The state with one leg's joints set, as {"coxia": ...} for those that
    change: its foot goes wherever those angles put it, the body staying."""
    _, pose, _ = solve(state, robot_config)
    pose = {leg_id: dict(joints) for leg_id, joints in pose.items()}
    pose[leg].update(angles)
    foot = np.asarray(kf.pose_to_feet(pose, robot_config))[leg]
    _, rotation, origin = _placement(state, robot_config)
    offsets = np.array(state["offsets"], dtype=float)
    offsets[leg] = rotation @ foot + origin - kf.standby_feet(robot_config)[leg]
    return make_state(state["body"], offsets)


def from_feet(feet, robot_config):
    """A state for feet given only in the body frame (a keyframe saved before
    keyframes kept their layers): the body unmoved, the feet as moves from
    standby."""
    return make_state({}, np.asarray(feet, dtype=float) - kf.standby_feet(robot_config))


def scene(state, pose, robot_config):
    """The pose drawn in the world, the floor at z = 0.

    The support polygon goes through the feet standing on the floor. Nothing
    settles the body: as on the robot, it is where the layers put it, whether
    or not it would balance there.
    """
    _, rotation, origin = _placement(state, robot_config)
    lift = [0.0, 0.0, -kf.ground_height(robot_config)]
    drawn = transform_scene(kf.pose_to_scene(pose, robot_config), rotation, origin + lift)
    standing = [foot for foot in drawn["feet"] if foot[2] <= kf.GROUND_TOLERANCE]
    drawn["support"] = [[x, y, 0.0] for x, y, _ in order_around_centre(standing)]
    drawn["ground"] = 0.0
    return drawn


def settled_scene(pose, robot_config):
    """A pose drawn standing on the floor: the body tilted and lifted onto the
    feet that touch the ground, as VirtualHexapod.update() settles it.

    For the gaits. Several of them -- Rotate X/Y/Z, Twist, Climb -- tilt or
    raise the body over planted feet, which in the body frame shows up as the
    feet swinging; drawn with the body held level, as scene() draws an edited
    pose, those feet go through the floor. A frame the model cannot stand on
    (no three feet around the centre of gravity) is drawn that way instead.
    """
    hexapod = VirtualHexapod(get_simulator_dimensions(robot_config))
    try:
        # Not assuming which point of each leg is on the ground: a gait can
        # bend a leg so that its knee is lower than its foot.
        hexapod.update(pose, assume_ground_targets=False)
    except Exception:  # update() raises a bare Exception when it cannot settle
        return scene(from_feet(kf.pose_to_feet(pose, robot_config), robot_config), pose, robot_config)
    return hexapod_to_scene(hexapod, world_axes=False)


def _as_vector(state):
    return np.concatenate(
        [
            [state["body"][key] for key in BODY_KEYS],
            np.asarray(state["offsets"], dtype=float).ravel(),
        ]
    )


def _from_vector(vector):
    body = dict(zip(BODY_KEYS, vector[: len(BODY_KEYS)]))
    offsets = vector[len(BODY_KEYS) :].reshape(6, 3)
    return make_state(body, offsets)


def sequence(keyframes, robot_config, fps, loop=False, ease=True):
    """The frames of a sequence: (feet, states, poses, bad_frames).

    When every keyframe kept its layers, the layers are what is interpolated,
    so a body tilting between two keyframes tilts over planted feet. Otherwise
    each foot moves in a straight line in the body frame (kf.interpolate_feet),
    and `states` is None.
    """
    if keyframes and all(is_state(frame.get("state")) for frame in keyframes):
        vectors = [_as_vector(frame["state"]) for frame in keyframes]
        states = [
            _from_vector(vector)
            for vector in kf.interpolate_arrays(vectors, keyframes, fps, loop, ease)
        ]
        feet = [body_feet(state, robot_config) for state in states]
    else:
        states = None
        feet = kf.interpolate_feet(keyframes, fps, loop, ease)

    poses, bad_frames = [], []
    for index, frame_feet in enumerate(feet):
        pose, bad_legs = kf.feet_to_pose(frame_feet, robot_config)
        poses.append(pose)
        if bad_legs:
            bad_frames.append(index)
    return feet, states, poses, bad_frames
