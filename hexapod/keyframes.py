# Keyframed leg motion for the workspace (pages/pose.py).
#
# A pose here is where the six feet are, not what the joints are doing: a 6x3
# list of foot tip positions in the robot's body frame, the same frame the path
# tool and hexapod/path_generator.py work in (x right, y forward, z up, origin at
# the body's centre, millimetres). Dragging a foot sets its position and the
# joints are solved from it, so a keyframe says what the user actually placed.
#
# A keyframe is {"feet": [[x, y, z] * 6], "duration_ms": int}, where the
# duration is the time taken to reach that pose from the keyframe before it. The
# first keyframe's duration is only used when the sequence loops, for the move
# from the last keyframe back round to it. A keyframe made in the workspace
# also keeps the layers the pose was built from, as "state"
# (hexapod/pose_layers.py); this module carries it along without looking in it.
#
# A keyframe also says whether the move into it starts and stops gently, as
# "ease" (left out when it does, the default). A gait's keyframes
# (hexapod/gait_keyframes.py) do not: each is one point on a path the feet
# keep moving along, and easing into it would stop them there.
#
# Nothing here settles the body onto the ground: the body is held still and the
# feet move around it. That is how the robot sees it too -- it has no idea where
# the floor is, it only places its feet -- and in the editor it keeps a dragged
# foot under the cursor.

import json

import numpy as np

from hexapod.models import VirtualHexapod
from hexapod.path_generator import (
    gen_posture,
    inverse_kinematics,
    servo_angles_to_pose,
)
from hexapod.scene import hexapod_to_scene, xyz
from hexapod.robot_config import (
    get_joint_limits,
    get_leg_signs,
    get_simulator_dimensions,
)

FILE_FORMAT = "hexapod-link-keyframes"
FILE_VERSION = 1

DEFAULT_DURATION_MS = 500
# Down to a single frame of the fastest robot's gaits (12 ms).
MIN_DURATION_MS = 10
MAX_DURATION_MS = 60000

# A foot this close to the ground plane (mm) counts as standing on it.
GROUND_TOLERANCE = 2.0

# Some slack on the joint limits, so a pose that sits exactly on a limit is not
# refused for floating point noise.
_LIMIT_SLACK = 1e-6

# How far inside a joint's limit (degrees) a pose that asks for more is held:
# a straight move between two poses on the limit bulges past it a little
# (0.21 degrees at most, on Mochi's sideways walk), and this keeps the whole
# move inside. About a servo tick.
LIMIT_MARGIN_DEG = 0.5

# The nearest (mm) a foot held in reach comes to its coxia's axis: on the
# axis the coxia has no angle to speak of, and past it the leg points the
# other way.
_MIN_RADIUS = 1.0


class KeyframeFileError(ValueError):
    """A keyframe file that cannot be loaded for this robot."""


def clean_feet(feet):
    """Six foot positions as plain floats, to a thousandth of a millimetre.

    Also turns -0.0 into 0.0. These go into dcc.Store, which compares what it
    holds against what it saved to session storage; JSON keeps -0 as 0, and
    the store's equality check tells the two apart, so a -0 there has the
    store rewriting itself until React gives up.
    """
    return [[round(float(c), 3) + 0.0 for c in foot] for foot in feet]


def standby_feet(robot_config):
    """Foot positions of the robot's standby posture, as a 6x3 list."""
    config = robot_config["config"]
    posture = gen_posture(*robot_config["gait"]["standby_posture"], config)
    return clean_feet(posture.tolist())


def ground_height(robot_config):
    """Height of the floor in the body frame: where the feet stand at standby."""
    return min(foot[2] for foot in standby_feet(robot_config))


def feet_to_pose(feet, robot_config, margin=0.0):
    """Solve the joints for six foot positions.

    Returns (pose, bad_legs): the simulator pose dict (hexapod/models.py) and
    the indices of the legs that cannot put their foot there, either because
    it is out of reach or because it would take a joint past the robot's
    mechanical limits -- or, with `margin`, nearer than that many degrees to
    them. A bad leg's angles are not meaningful.
    """
    targets = np.asarray(feet, dtype=float).reshape(6, 3)
    with np.errstate(invalid="ignore"):
        angles = inverse_kinematics(targets, robot_config["config"])

    pose = servo_angles_to_pose(np.nan_to_num(angles), get_leg_signs(robot_config))
    # Round off the float noise of the solve, which would otherwise show up as
    # "-0.00" in the angle readout.
    for leg in pose.values():
        for joint in ("coxia", "femur", "tibia"):
            leg[joint] = round(leg[joint], 6) + 0.0
    limits = get_joint_limits(robot_config)

    bad_legs = []
    for leg_id in range(6):
        if np.isnan(angles[leg_id]).any():
            bad_legs.append(leg_id)
            continue
        leg = pose[leg_id]
        if any(abs(leg[joint]) > limits[joint] - margin + _LIMIT_SLACK for joint in limits):
            bad_legs.append(leg_id)

    return pose, bad_legs


def _wrapped(angle):
    """`angle` (radians) as the same direction within half a turn of zero."""
    return (angle + np.pi) % (2 * np.pi) - np.pi


def _held(angle, most):
    """`angle` (radians), turned no further than `most` either way."""
    return min(max(_wrapped(angle), -most), most)


def _plane_foot(femur, tibia, femur_length, tibia_length):
    """Where a leg's femur and tibia (radians, as a pose has them) put its
    foot, in the leg's own plane: (out from the femur's joint, up)."""
    return (
        femur_length * np.cos(femur) + tibia_length * np.sin(femur + tibia),
        femur_length * np.sin(femur) - tibia_length * np.cos(femur + tibia),
    )


def _plane_angles(out, up, femur_length, tibia_length):
    """_plane_foot() run backwards, as inverse_kinematics() does it: (femur,
    tibia), or None for a foot the two cannot reach."""
    reach2 = out * out + up * up
    reach = np.sqrt(reach2)
    if reach < 1e-9:
        return None
    femur_length2, tibia_length2 = femur_length * femur_length, tibia_length * tibia_length
    cos1 = (reach2 + femur_length2 - tibia_length2) / (2 * femur_length * reach)
    cos2 = (reach2 - femur_length2 + tibia_length2) / (2 * tibia_length * reach)
    if abs(cos1) > 1 or abs(cos2) > 1:
        return None
    a1, a2 = np.arccos(cos1), np.arccos(cos2)
    return np.arctan2(up, out) + a1, np.pi / 2 - (a1 + a2)


def _nearest_in_plane(out, up, femur_length, tibia_length, max_femur, max_tibia, min_out):
    """The closest spot to (out, up) in a leg's plane that its femur and
    tibia can put the foot, turning no further than `max_femur` and
    `max_tibia` (radians) and coming no nearer the coxia's axis than
    `min_out`; None if there is none.

    A spot the leg cannot reach has its closest on the edge of what it can:
    with one of the two joints at its limit, or at `min_out`. Each of those
    is an arc or a line, whose closest point is known outright.
    """

    def within(angles):
        return (
            angles is not None
            and abs(angles[0]) <= max_femur + _LIMIT_SLACK
            and abs(angles[1]) <= max_tibia + _LIMIT_SLACK
        )

    if out >= min_out and within(_plane_angles(out, up, femur_length, tibia_length)):
        return out, up

    angles = []
    at_least = _plane_angles(min_out, up, femur_length, tibia_length)
    if within(at_least):
        angles.append(at_least)
    for tibia in (-max_tibia, max_tibia):
        # The tibia held: the foot swings about the femur's joint, at a
        # distance, and ahead of the femur by an angle, that do not change.
        ahead_out, ahead_up = _plane_foot(0.0, tibia, femur_length, tibia_length)
        lead, radius = np.arctan2(ahead_up, ahead_out), np.hypot(ahead_out, ahead_up)
        femurs = [np.arctan2(up, out) - lead, -max_femur, max_femur]
        if radius > abs(min_out):
            swing = np.arccos(min_out / radius)
            femurs += [swing - lead, -swing - lead]
        angles += [(_held(femur, max_femur), tibia) for femur in femurs]
    for femur in (-max_femur, max_femur):
        # The femur held: the foot swings about the knee.
        knee_out, knee_up = femur_length * np.cos(femur), femur_length * np.sin(femur)
        tibias = [np.arctan2(out - knee_out, knee_up - up) - femur]
        if abs(min_out - knee_out) < tibia_length:
            swing = np.arcsin((min_out - knee_out) / tibia_length)
            tibias += [swing - femur, np.pi - swing - femur]
        angles += [(femur, _held(tibia, max_tibia)) for tibia in tibias]

    # Only what solves back to the angles it was made from: a foot folded
    # round behind its own femur solves to a whole turn more.
    spots = [_plane_foot(femur, tibia, femur_length, tibia_length) for femur, tibia in angles]
    spots = [
        spot
        for spot in spots
        if spot[0] >= min_out - _LIMIT_SLACK
        and within(_plane_angles(*spot, femur_length, tibia_length))
    ]
    if not spots:
        return None
    return min(spots, key=lambda spot: np.hypot(spot[0] - out, spot[1] - up))


def nearest_reachable_foot(foot, leg, robot_config):
    """The closest spot to `foot`, in the body frame, that leg `leg` can put
    its foot: `foot` itself when the leg can reach it with every joint
    LIMIT_MARGIN_DEG inside its limit, else where the leg ends up following
    it as far as its joints go. How a dragged foot slides along the edge of
    its leg's reach instead of stopping at it.

    The coxia turns towards the foot as far as it may, which puts the leg in
    a plane; the femur and tibia then take the foot as near as they can in
    it. None when the leg can reach nowhere near, which no robot's does.
    """
    config = robot_config["config"]
    most = {
        joint: np.radians(max(limit - LIMIT_MARGIN_DEG, 0.0))
        for joint, limit in get_joint_limits(robot_config).items()
    }
    coxia_length = config["legJoint1ToJoint2"]
    femur_length = config["legJoint2ToJoint3"]
    tibia_length = config["legJoint3ToTip"]

    # Into the leg's own frame and back, as inverse_kinematics() has it: the
    # same turn-and-mirror both ways.
    mount = np.array([config["legMountX"][leg], config["legMountY"][leg]])
    angle = np.radians(config["legMountAngle"][leg])
    mirror = np.array([[np.cos(angle), np.sin(angle)], [np.sin(angle), -np.cos(angle)]])

    x, y, z = (float(c) for c in foot)
    along, across = mirror @ (np.array([x, y]) - mount)
    along -= config["legRootToJoint1"]

    asked = -np.arctan2(across, along)
    coxia = min(max(asked, -most["coxia"]), most["coxia"])
    out = along * np.cos(coxia) - across * np.sin(coxia) - coxia_length
    # Not past straight or folded flat, whatever the tibia's limit: beyond
    # either the same feet come round again.
    spot = _nearest_in_plane(
        out,
        z,
        femur_length,
        tibia_length,
        most["femur"],
        min(most["tibia"], np.pi / 2),
        _MIN_RADIUS - coxia_length,
    )
    if spot is None:
        return None
    if coxia == asked and spot == (out, z):
        return [x, y, z]

    radius = spot[0] + coxia_length
    local = [radius * np.cos(coxia) + config["legRootToJoint1"], -radius * np.sin(coxia)]
    reached = mirror @ local + mount
    return [float(reached[0]), float(reached[1]), float(spot[1])]


def _posed_model(pose, robot_config):
    """The simulator's linkage model with its legs set to `pose`, body unmoved."""
    hexapod = VirtualHexapod(get_simulator_dimensions(robot_config))
    for leg_id in range(6):
        leg = pose.get(leg_id, pose.get(str(leg_id)))
        hexapod.legs[leg_id].change_pose(leg["coxia"], leg["femur"], leg["tibia"])
    return hexapod


def pose_to_feet(pose, robot_config):
    """Where a pose puts the six feet, in the body frame: feet_to_pose run backwards.

    How a pose made from joint angles -- typed into the joint fields, or one
    of a gait's -- becomes feet that can be dragged and kept as a keyframe.
    """
    hexapod = _posed_model(pose, robot_config)
    return clean_feet([xyz(leg.foot_tip()) for leg in hexapod.legs])


def pose_to_scene(pose, robot_config):
    """The scene the 3D view draws for a pose (hexapod/scene.py).

    The legs are posed by the simulator's own linkage model rather than by the
    path tool's IK, so what is drawn is a check on what was solved. The floor
    is drawn where the feet stand at standby, and the support polygon through
    the feet that are on it.
    """
    hexapod = _posed_model(pose, robot_config)
    ground = ground_height(robot_config)
    feet = [xyz(leg.foot_tip()) for leg in hexapod.legs]
    standing = [foot for foot in feet if foot[2] <= ground + GROUND_TOLERANCE]
    return hexapod_to_scene(hexapod, ground, standing)


def clamp_duration(duration_ms):
    try:
        duration = int(round(float(duration_ms)))
    except (TypeError, ValueError):
        duration = DEFAULT_DURATION_MS
    return min(max(duration, MIN_DURATION_MS), MAX_DURATION_MS)


def make_keyframe(feet, duration_ms=DEFAULT_DURATION_MS, state=None, ease=True):
    keyframe = {
        "feet": clean_feet(feet),
        "duration_ms": clamp_duration(duration_ms),
    }
    if isinstance(state, dict):
        keyframe["state"] = state
    if ease is False:
        keyframe["ease"] = False
    return keyframe


def eases(keyframe):
    """Whether the move into `keyframe` starts and stops gently."""
    return keyframe.get("ease", True) is not False


def remade(keyframe, feet, state):
    """`keyframe` with a new pose, keeping its time and easing."""
    return make_keyframe(feet, keyframe["duration_ms"], state, ease=eases(keyframe))


def _ease(t):
    """Smoothstep: start and stop each move gently instead of with a jolt."""
    return t * t * (3.0 - 2.0 * t)


def interpolate_feet(keyframes, fps, loop=False, ease=True, speed=1.0):
    """Foot positions frame by frame, at `fps`, through the keyframes.

    Each foot moves in a straight line from one keyframe to the next. The first
    frame is the first keyframe. When looping, the move from the last keyframe
    back to the first is included, without repeating the first keyframe at the
    end, so playing the frames round and round has no hitch at the seam.

    Each move starts and stops gently into a keyframe that eases (eases());
    `ease` False makes every move steady. `speed` scales every duration: 2
    plays the sequence twice as fast.
    """
    points = [np.asarray(kf["feet"], dtype=float).reshape(6, 3) for kf in keyframes]
    frames = interpolate_arrays(points, keyframes, fps, loop, ease, speed)
    return [frame.tolist() for frame in frames]


def _samples(keyframes, fps, loop, speed):
    """Where each frame of a sequence falls, as (start, end, t): on the move
    from keyframe `start` to keyframe `end`, a fraction `t` of the way.

    Frames are spread evenly in time, at about `fps`, over the moves' total
    time, so a sequence keeps its timing whatever the frame rate -- frames
    fall between keyframes, and a move shorter than a frame (a gait's, in the
    preview) may get none. Without looping the last frame is the last
    keyframe; looping, the move back to the first keyframe is included but
    not the first keyframe again, so the frames play round without a seam.
    """
    count = len(keyframes)
    pairs = [(i - 1, i) for i in range(1, count)]
    if loop and count > 1:
        pairs.append((count - 1, 0))
    seconds = [clamp_duration(keyframes[end]["duration_ms"]) / 1000.0 / speed for _, end in pairs]
    total = sum(seconds)

    samples = [(0, 0, 0.0)]
    if not pairs:
        return samples
    frames = max(1, round(total * fps))
    move, move_start = 0, 0.0
    for frame in range(1, frames if loop else frames + 1):
        time = frame * total / frames
        while move < len(pairs) - 1 and time > move_start + seconds[move] + 1e-12:
            move_start += seconds[move]
            move += 1
        start, end = pairs[move]
        samples.append((start, end, min(1.0, (time - move_start) / seconds[move])))
    return samples


def interpolate_arrays(points, keyframes, fps, loop=False, ease=True, speed=1.0):
    """interpolate_feet() for any values: one array per keyframe, timed by
    the keyframes' durations. Returns the arrays, one per frame."""
    if not keyframes:
        return []

    points = [np.asarray(point, dtype=float) for point in points]
    frames = []
    for start, end, t in _samples(keyframes, fps, loop, speed):
        if ease and eases(keyframes[end]):
            t = _ease(t)
        frames.append(points[start] + (points[end] - points[start]) * t)
    return frames


def frame_times(keyframes, fps, loop=False, speed=1.0):
    """For each frame interpolate_arrays() gives, where it falls in the
    keyframes' own time, whatever the speed: (start, end, ms), `ms` into the
    move from keyframe `start` to keyframe `end`. The first frame is (0, 0, 0)."""
    if not keyframes:
        return []
    return [
        (start, end, t * clamp_duration(keyframes[end]["duration_ms"]) if t else 0.0)
        for start, end, t in _samples(keyframes, fps, loop, speed)
    ]


def keyframe_times_ms(keyframes):
    """When each keyframe is reached, from the first, in ms."""
    times, total = [], 0
    for index, frame in enumerate(keyframes):
        if index:
            total += clamp_duration(frame["duration_ms"])
        times.append(total)
    return times


def solve_frames(feet_frames, robot_config):
    """Simulator poses for each frame of feet: (poses, bad_frames).

    The poses are ready for RobotLink.play_sequence(); `bad_frames` are the
    indices of the frames where some leg cannot reach. A straight line between
    two reachable foot positions can pass out of reach, so this is checked
    frame by frame rather than assumed from the keyframes being valid.
    """
    poses, bad_frames = [], []
    for index, feet in enumerate(feet_frames):
        pose, bad_legs = feet_to_pose(feet, robot_config)
        poses.append(pose)
        if bad_legs:
            bad_frames.append(index)
    return poses, bad_frames


def sequence_duration_ms(keyframes, loop=False, speed=1.0):
    """How long one pass through the keyframes takes, at `speed`."""
    if not keyframes:
        return 0
    durations = [clamp_duration(kf["duration_ms"]) for kf in keyframes]
    total = sum(durations) if loop and len(keyframes) > 1 else sum(durations[1:])
    return total / speed


def dump(keyframes, robot_config):
    """The keyframes as a JSON document to save."""
    return json.dumps(
        {
            "format": FILE_FORMAT,
            "version": FILE_VERSION,
            "robot": robot_config["name"],
            "keyframes": [remade(kf, kf["feet"], kf.get("state")) for kf in keyframes],
        },
        indent=2,
    )


def load(text, robot_config):
    """Keyframes from a saved JSON document.

    Foot positions only make sense on the robot they were placed for -- another
    robot's legs are mounted elsewhere and are a different length -- so a file
    saved for another robot is refused rather than played.
    """
    try:
        document = json.loads(text)
    except (TypeError, ValueError) as error:
        raise KeyframeFileError(f"Not a keyframe file: {error}") from error

    if not isinstance(document, dict) or document.get("format") != FILE_FORMAT:
        raise KeyframeFileError("Not a keyframe file.")
    if document.get("version") != FILE_VERSION:
        raise KeyframeFileError(
            f"Unsupported keyframe file version: {document.get('version')}."
        )

    robot = document.get("robot")
    if robot != robot_config["name"]:
        raise KeyframeFileError(
            f"These keyframes were made for '{robot}', "
            f"not for '{robot_config['name']}'."
        )

    raw = document.get("keyframes")
    if not isinstance(raw, list):
        raise KeyframeFileError("The file has no keyframe list.")

    keyframes = []
    for index, entry in enumerate(raw):
        try:
            feet = np.asarray(entry["feet"], dtype=float)
            if feet.shape != (6, 3) or not np.isfinite(feet).all():
                raise ValueError("feet must be six [x, y, z] positions")
            ease = entry.get("ease", True)
            if not isinstance(ease, bool):
                raise ValueError("ease must be true or false")
            keyframes.append(
                make_keyframe(feet.tolist(), entry["duration_ms"], entry.get("state"), ease)
            )
        except (KeyError, TypeError, ValueError) as error:
            raise KeyframeFileError(f"Keyframe {index + 1} is malformed: {error}") from error

    return keyframes
