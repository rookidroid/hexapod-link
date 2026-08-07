import numpy as np

from hexapod.robot_profiles import (
    DEFAULT_PROFILE,
    get_physical_config,
    get_profile,
    get_simulator_dimensions,
)

# Geometry and gait parameters differ between the two robots, so they live in
# hexapod/robot_profiles.py. `get_simulator_dimensions` is re-exported here for
# callers that used to import it from this module.
__all__ = [
    "generate_poses",
    "get_simulator_dimensions",
    "inverse_kinematics",
]

# --- Path Library Functions (from path_tool/path_lib.py) ---

def semicircle_generator(radius, steps, reverse=False):
    assert (steps % 4) == 0
    halfsteps = int(steps / 2)
    step_angle = np.pi / halfsteps
    result = np.zeros((steps, 3))
    halfsteps_array = np.arange(halfsteps)
    result[:halfsteps, 1] = radius - halfsteps_array * radius * 2 / halfsteps
    angle = np.pi - step_angle * halfsteps_array
    result[halfsteps:, 1] = radius * np.cos(angle)
    result[halfsteps:, 2] = radius * np.sin(angle)
    result = np.roll(result, int(steps / 4), axis=0)
    if reverse:
        result = np.flip(result, axis=0)
        result = np.roll(result, 1, axis=0)
    return result

def semicircle2_generator(steps, y_radius, z_radius, x_radius, reverse=False):
    assert (steps % 4) == 0
    halfsteps = int(steps / 2)
    step_angle = np.pi / halfsteps
    result = np.zeros((steps, 3))
    halfsteps_array = np.arange(halfsteps)
    result[:halfsteps, 1] = y_radius - halfsteps_array * y_radius * 2 / halfsteps
    angle = np.pi - step_angle * halfsteps_array
    result[halfsteps:, 0] = x_radius * np.sin(angle)
    result[halfsteps:, 1] = y_radius * np.cos(angle)
    result[halfsteps:, 2] = z_radius * np.sin(angle)
    result = np.roll(result, int(steps / 4), axis=0)
    if reverse:
        result = np.flip(result, axis=0)
        result = np.roll(result, 1, axis=0)
    return result

def get_rotate_x_matrix(angle):
    angle = angle * np.pi / 180
    return np.matrix([
        [1, 0, 0, 0],
        [0, np.cos(angle), -np.sin(angle), 0],
        [0, np.sin(angle), np.cos(angle), 0],
        [0, 0, 0, 1],
    ])

def get_rotate_y_matrix(angle):
    angle = angle * np.pi / 180
    return np.matrix([
        [np.cos(angle), 0, np.sin(angle), 0],
        [0, 1, 0, 0],
        [-np.sin(angle), 0, np.cos(angle), 0],
        [0, 0, 0, 1],
    ])

def get_rotate_z_matrix(angle):
    angle = angle * np.pi / 180
    return np.matrix([
        [np.cos(angle), -np.sin(angle), 0, 0],
        [np.sin(angle), np.cos(angle), 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ])

def path_rotate_z(path, angle):
    ptx = np.append(path, np.ones((np.shape(path)[0], 1)), axis=1)
    return ((get_rotate_z_matrix(angle) * np.matrix(ptx).T).T)[:, :-1]

def inverse_kinematics(dest, config):
    mount_x = np.array(config["legMountX"])
    mount_y = np.array(config["legMountY"])
    root_j1 = config["legRootToJoint1"]
    j1_j2 = config["legJoint1ToJoint2"]
    j2_j3 = config["legJoint2ToJoint3"]
    j3_tip = config["legJoint3ToTip"]
    mount_angle = np.array(config["legMountAngle"]) / 180 * np.pi
    mount_position = np.zeros((6, 3))
    mount_position[:, 0] = mount_x
    mount_position[:, 1] = mount_y
    leg_scale = np.array(config["legScale"])

    temp_dest = dest - mount_position
    local_dest = np.zeros_like(dest)
    local_dest[:, 0] = temp_dest[:, 0] * np.cos(mount_angle) + temp_dest[:, 1] * np.sin(mount_angle)
    local_dest[:, 1] = temp_dest[:, 0] * np.sin(mount_angle) - temp_dest[:, 1] * np.cos(mount_angle)
    local_dest[:, 2] = temp_dest[:, 2]

    angles = np.zeros((6, 3))
    x = local_dest[:, 0] - root_j1
    y = local_dest[:, 1]
    angles[:, 0] = -(np.arctan2(y, x) * 180 / np.pi) + 90
    x = np.sqrt(x * x + y * y) - j1_j2
    y = local_dest[:, 2]
    ar = np.arctan2(y, x)
    lr2 = x * x + y * y
    lr = np.sqrt(lr2)
    a1 = np.arccos((lr2 + j2_j3 * j2_j3 - j3_tip * j3_tip) / (2 * j2_j3 * lr))
    a2 = np.arccos((lr2 - j2_j3 * j2_j3 + j3_tip * j3_tip) / (2 * j3_tip * lr))
    angles[:, 1] = 90 - ((ar + a1) * 180 / np.pi) * leg_scale[:, 1]
    angles[:, 2] = (90 - ((a1 + a2) * 180 / np.pi)) * leg_scale[:, 1] + 90
    return angles

# --- Path Generation Functions (from path_tool/path_tool.py) ---

def gen_posture(j2_angle, j3_angle, config):
    mount_x = np.array(config["legMountX"])
    mount_y = np.array(config["legMountY"])
    root_j1 = config["legRootToJoint1"]
    j1_j2 = config["legJoint1ToJoint2"]
    j2_j3 = config["legJoint2ToJoint3"]
    j3_tip = config["legJoint3ToTip"]
    mount_angle = np.array(config["legMountAngle"]) / 180 * np.pi

    j2_rad = j2_angle / 180 * np.pi
    j3_rad = j3_angle / 180 * np.pi
    posture = np.zeros((6, 3))

    posture[:, 0] = mount_x + (root_j1 + j1_j2 + (j2_j3 * np.sin(j2_rad)) + j3_tip * np.cos(j3_rad)) * np.cos(mount_angle)
    posture[:, 1] = mount_y + (root_j1 + j1_j2 + (j2_j3 * np.sin(j2_rad)) + j3_tip * np.cos(j3_rad)) * np.sin(mount_angle)
    posture[:, 2] = j2_j3 * np.cos(j2_rad) - j3_tip * np.sin(j3_rad)
    return posture

def gen_walk_path(standby_coordinate, g_steps=28, g_radius=30, direction=0):
    halfsteps = int(g_steps / 2)
    semi_circle = semicircle_generator(g_radius, g_steps)
    semi_circle = np.array(path_rotate_z(semi_circle, direction))
    mir_path = np.roll(semi_circle, halfsteps, axis=0)
    path = np.zeros((g_steps, 6, 3))
    path[:, [0, 2, 4], :] = np.tile(semi_circle[:, np.newaxis, :], (1, 3, 1))
    path[:, [1, 3, 5], :] = np.tile(mir_path[:, np.newaxis, :], (1, 3, 1))
    return path + np.tile(standby_coordinate, (g_steps, 1, 1))

def gen_fastwalk_path(standby_coordinate, g_steps=20, y_radius=50, z_radius=40, x_radius=15, reverse=False):
    halfsteps = int(g_steps / 2)
    path = np.zeros((g_steps, 6, 3))
    semi_circle_r = semicircle2_generator(g_steps, y_radius, z_radius, x_radius, reverse=reverse)
    semi_circle_l = semicircle2_generator(g_steps, y_radius, z_radius, -x_radius, reverse=reverse)
    path[:, [0, 2], :] = np.tile(semi_circle_r[:, np.newaxis, :], (1, 2, 1))
    path[:, 1, :] = np.roll(semi_circle_r, halfsteps, axis=0)
    path[:, 4, :] = semi_circle_l
    path[:, [3, 5], :] = np.tile(np.roll(semi_circle_l[:, np.newaxis, :], halfsteps, axis=0), (1, 2, 1))
    return path + np.tile(standby_coordinate, (g_steps, 1, 1))

def gen_turn_path(standby_coordinate, g_steps=28, g_radius=35, direction="left"):
    # semicircle_generator strokes along +y, so rotating a leg's stroke by that
    # leg's azimuth from the cog aims it tangent to the turn circle. The azimuth
    # is read off the standby stance rather than hardcoded: path_tool used to
    # spell these 45 / 0 / 315 / 225 / 180 / 135, which is right only for a body
    # whose corner legs sit on the diagonals (front == side). Both real robots
    # have side == front * tan(60deg), putting the corners at 60deg, and the
    # 15deg error sheared the support triangle and dragged each planted foot
    # ~22mm in and out per stance. Same stale-45deg assumption that
    # Hexagon.coxia_axes carried; see hexapod/models.py.
    #
    # A residual remains by design: the stroke is a straight chord, so a planted
    # foot's radius from the cog swells a few mm towards both ends of the
    # sweep. That dilates the support triangle without distorting its shape --
    # it stays similar to a part in 1e6 -- so the turn stays unbiased and only
    # the scuffing is real. Making it exact needs an arc primitive path_tool
    # does not have; tests/test_motion.py pins the similarity that is left.
    halfsteps = int(g_steps / 2)
    path = np.zeros((g_steps, 6, 3))
    semi_circle = semicircle_generator(g_radius, g_steps)
    mir_path = np.roll(semi_circle, halfsteps, axis=0)
    azimuths = np.degrees(
        np.arctan2(standby_coordinate[:, 1], standby_coordinate[:, 0])
    )
    # An unrecognised direction leaves the path at zero, i.e. standing by.
    if direction in ("left", "right"):
        turn_offset = 0 if direction == "left" else 180
        for leg_id in range(6):
            stroke = semi_circle if leg_id in (0, 2, 4) else mir_path
            path[:, leg_id, :] = path_rotate_z(stroke, azimuths[leg_id] + turn_offset)
    return path + np.tile(standby_coordinate, (g_steps, 1, 1))

def gen_climb_path(standby_coordinate, g_steps=28, y_radius=20, z_radius=80, x_radius=30, z_shift=-30, reverse=False):
    halfsteps = int(g_steps / 2)
    rpath = semicircle2_generator(g_steps, y_radius, z_radius, x_radius, reverse=reverse)
    rpath[:, 2] = rpath[:, 2] + z_shift
    lpath = semicircle2_generator(g_steps, y_radius, z_radius, -x_radius, reverse=reverse)
    lpath[:, 2] = lpath[:, 2] + z_shift
    mir_rpath = np.roll(rpath, halfsteps, axis=0)
    mir_lpath = np.roll(lpath, halfsteps, axis=0)
    path = np.zeros((g_steps, 6, 3))
    path[:, 0, :] = rpath
    path[:, 1, :] = mir_rpath
    path[:, 2, :] = rpath
    path[:, 3, :] = mir_lpath
    path[:, 4, :] = lpath
    path[:, 5, :] = mir_lpath
    return path + np.tile(standby_coordinate, (g_steps, 1, 1))

def gen_rotatex_path(standby_coordinate, g_steps=28, swing_angle=15, y_radius=15):
    quarter = int(g_steps / 4)
    path = np.zeros((g_steps, 6, 3))
    step_angle = swing_angle / quarter
    step_offset = y_radius / quarter
    scx = np.append(standby_coordinate, np.ones((6, 1)), axis=1)
    for i in range(quarter):
        m = get_rotate_x_matrix(swing_angle - i * step_angle)
        m[1, 3] = -i * step_offset
        path[i, :, :] = ((np.matmul(m, scx.T)).T)[:, :-1]
    for i in range(quarter):
        m = get_rotate_x_matrix(-i * step_angle)
        m[1, 3] = -y_radius + i * step_offset
        path[i + quarter, :, :] = ((np.matmul(m, scx.T)).T)[:, :-1]
    for i in range(quarter):
        m = get_rotate_x_matrix(i * step_angle - swing_angle)
        m[1, 3] = i * step_offset
        path[i + quarter * 2, :, :] = ((np.matmul(m, scx.T)).T)[:, :-1]
    for i in range(quarter):
        m = get_rotate_x_matrix(i * step_angle)
        m[1, 3] = y_radius - i * step_offset
        path[i + quarter * 3, :, :] = ((np.matmul(m, scx.T)).T)[:, :-1]
    return path

def gen_rotatey_path(standby_coordinate, g_steps=28, swing_angle=15, x_radius=15):
    quarter = int(g_steps / 4)
    path = np.zeros((g_steps, 6, 3))
    step_angle = swing_angle / quarter
    step_offset = x_radius / quarter
    scx = np.append(standby_coordinate, np.ones((6, 1)), axis=1)
    for i in range(quarter):
        m = get_rotate_y_matrix(swing_angle - i * step_angle)
        m[1, 3] = -i * step_offset
        path[i, :, :] = ((np.matmul(m, scx.T)).T)[:, :-1]
    for i in range(quarter):
        m = get_rotate_y_matrix(-i * step_angle)
        m[1, 3] = -x_radius + i * step_offset
        path[i + quarter, :, :] = ((np.matmul(m, scx.T)).T)[:, :-1]
    for i in range(quarter):
        m = get_rotate_y_matrix(i * step_angle - swing_angle)
        m[1, 3] = i * step_offset
        path[i + quarter * 2, :, :] = ((np.matmul(m, scx.T)).T)[:, :-1]
    for i in range(quarter):
        m = get_rotate_y_matrix(i * step_angle)
        m[1, 3] = x_radius - i * step_offset
        path[i + quarter * 3, :, :] = ((np.matmul(m, scx.T)).T)[:, :-1]
    return path

def gen_rotatez_path(standby_coordinate, g_steps=28, z_lift=4.5, xy_radius=1):
    path = np.zeros((g_steps, 6, 3))
    step_angle = 2 * np.pi / g_steps
    scx = np.append(standby_coordinate, np.ones((6, 1)), axis=1)
    for i in range(g_steps):
        x = xy_radius * np.cos(i * step_angle)
        y = xy_radius * np.sin(i * step_angle)
        m = get_rotate_y_matrix(np.arctan2(x, z_lift) * 180 / np.pi) * get_rotate_x_matrix(np.arctan2(y, z_lift) * 180 / np.pi)
        path[i, :, :] = ((np.matmul(m, scx.T)).T)[:, :-1]
    return path

def gen_twist_path(standby_coordinate, g_steps=28, raise_angle=3, twist_x_angle=20, twise_y_angle=12):
    quarter = int(g_steps / 4)
    step_x_angle = twist_x_angle / quarter
    step_y_angle = twise_y_angle / quarter
    scx = np.append(standby_coordinate, np.ones((6, 1)), axis=1)
    m = get_rotate_x_matrix(raise_angle)
    path = np.zeros((g_steps, 6, 3))
    for i in range(quarter):
        temp = m * get_rotate_z_matrix(i * step_x_angle) * get_rotate_x_matrix(i * step_y_angle)
        path[i, :, :] = ((np.matmul(temp, scx.T)).T)[:, :-1]
    for i in range(quarter):
        temp = m * get_rotate_z_matrix((quarter - i) * step_x_angle) * get_rotate_x_matrix((quarter - i) * step_y_angle)
        path[i + quarter * 1, :, :] = ((np.matmul(temp, scx.T)).T)[:, :-1]
    for i in range(quarter):
        temp = m * get_rotate_z_matrix(-i * step_x_angle) * get_rotate_x_matrix(i * step_y_angle)
        path[i + quarter * 2, :, :] = ((np.matmul(temp, scx.T)).T)[:, :-1]
    for i in range(quarter):
        temp = m * get_rotate_z_matrix((-quarter + i) * step_x_angle) * get_rotate_x_matrix((quarter - i) * step_y_angle)
        path[i + quarter * 3, :, :] = ((np.matmul(temp, scx.T)).T)[:, :-1]
    return path

def gen_standup_path(standby_coordinate, laydown_coordinate, steps=28):
    standing_up_lut_size = steps
    lift_up_size = 10
    adjust_leg_size = int((standing_up_lut_size - lift_up_size) / 2)
    lift_up_linspace = np.linspace(laydown_coordinate[0, 2], standby_coordinate[0, 2], lift_up_size)
    lut_standup = np.zeros((standing_up_lut_size, 6, 3))
    for idx, var in enumerate(lift_up_linspace):
        laydown_coordinate[:, 2] = var
        lut_standup[idx, :, :] = laydown_coordinate
    radius = (lut_standup[lift_up_size - 1, 1, 0] - standby_coordinate[1, 0]) / 2
    step_angle = np.pi / adjust_leg_size
    angle = np.arange(1, adjust_leg_size + 1) * step_angle
    z_offset = radius * np.sin(angle)
    x_offset = radius * np.cos(angle) - radius
    center_offset = np.zeros((adjust_leg_size, 3))
    center_offset[:, 0] = x_offset
    center_offset[:, 2] = z_offset
    # `center_offset` is the reposition arc for the centre-right leg, which lies
    # along +x; every other leg needs the same arc turned into its own radial
    # direction. The azimuth is read off the standby stance rather than
    # hardcoded: path_tool used to spell these 45 / -45 / 135 / 180 / -135,
    # which is right only for a body whose corner legs sit on the diagonals
    # (front == side). Both real robots have side == front * tan(60deg), putting
    # the corners at 60deg. Same stale-45deg assumption gen_turn_path carried.
    #
    # The magnitude is shared rather than derived per leg, which is exact here:
    # gen_posture extends every leg from its own mount by the same distance, so
    # laydown and standby differ by the same radial travel on all six.
    azimuths = np.degrees(
        np.arctan2(standby_coordinate[:, 1], standby_coordinate[:, 0])
    )
    leg_offset = np.array(
        [np.asarray(path_rotate_z(center_offset, azimuth)) for azimuth in azimuths]
    )
    # The two tripods reposition in turn, each holding still while the other
    # moves, so a tripod's run starts from the pose the previous one left.
    start = lift_up_size
    for tripod in ((3, 1, 5), (0, 4, 2)):
        base = lut_standup[start - 1, :, :].copy()
        for idx in range(0, adjust_leg_size):
            lut_standup[start + idx, :, :] = base
            for leg_id in tripod:
                lut_standup[start + idx, leg_id, :] += leg_offset[leg_id, idx, :]
        start += adjust_leg_size
    return lut_standup


# --- Bridge to Simulator ---

# Leg indices are shared with the path tool and the firmware, so the paths above
# are indexed directly; hexapod/naming.py holds that correspondence.

def generate_poses(motion_name, profile_name=DEFAULT_PROFILE):
    """
    Generates a list of poses for a given motion name, compatible with VirtualHexapod.update().

    `profile_name` selects which physical robot the path is generated for; the
    two robots differ in leg geometry and in stride and turn radii, so a path
    baked for one is wrong for the other.

    Returns: list of dicts, where each dict is a pose for all 6 legs at a specific frame.
    """
    config = get_physical_config(profile_name)
    gait = get_profile(profile_name)["gait"]

    standby = gen_posture(*gait["standby_posture"], config)
    laydown = gen_posture(*gait["laydown_posture"], config)

    walk_radius = gait["walk_radius"]
    turn_radius = gait["turn_radius"]
    fastwalk = gait["fastwalk"]

    # Generate Cartesian path
    if motion_name == "standby":
        path = np.array([standby])
    elif motion_name == "walk_0":
        path = gen_walk_path(standby, g_radius=walk_radius, direction=0)
    elif motion_name == "walk_180":
        path = gen_walk_path(standby, g_radius=walk_radius, direction=180)
    elif motion_name == "walk_r45":
        path = gen_walk_path(standby, g_radius=walk_radius, direction=315)
    elif motion_name == "walk_r90":
        path = gen_walk_path(standby, g_radius=walk_radius, direction=270)
    elif motion_name == "walk_r135":
        path = gen_walk_path(standby, g_radius=walk_radius, direction=225)
    elif motion_name == "walk_l45":
        path = gen_walk_path(standby, g_radius=walk_radius, direction=45)
    elif motion_name == "walk_l90":
        path = gen_walk_path(standby, g_radius=walk_radius, direction=90)
    elif motion_name == "walk_l135":
        path = gen_walk_path(standby, g_radius=walk_radius, direction=135)
    elif motion_name == "fast_forward":
        path = gen_fastwalk_path(standby, **fastwalk)
    elif motion_name == "fast_backward":
        path = gen_fastwalk_path(standby, **fastwalk, reverse=True)
    elif motion_name == "turn_left":
        path = gen_turn_path(standby, g_radius=turn_radius, direction="left")
    elif motion_name == "turn_right":
        path = gen_turn_path(standby, g_radius=turn_radius, direction="right")
    elif motion_name == "climb_forward":
        path = gen_climb_path(standby, reverse=False)
    elif motion_name == "climb_backward":
        path = gen_climb_path(standby, reverse=True)
    elif motion_name == "rotate_x":
        path = gen_rotatex_path(standby, **gait["rotate_x"])
    elif motion_name == "rotate_y":
        path = gen_rotatey_path(standby, **gait["rotate_y"])
    elif motion_name == "rotate_z":
        path = gen_rotatez_path(standby, **gait["rotate_z"])
    elif motion_name == "twist":
        path = gen_twist_path(standby, **gait["twist"])
    elif motion_name == "standup":
        path = gen_standup_path(standby, laydown, steps=gait["standup_steps"])
    else:
        path = np.array([standby])

    frames = []
    from hexapod.const import NAMES_LEG
    for step in range(path.shape[0]):
        # Convert Cartesian to joint angles (j1, j2, j3)
        angles = inverse_kinematics(path[step], config)
        
        pose_dict = {}
        for leg_id in range(6):
            j1 = angles[leg_id, 0]
            j2 = angles[leg_id, 1]
            j3 = angles[leg_id, 2]

            # Map the path tool's servo angles to the simulator's joint angles.
            # This is the inverse of the relation in hexapod/robot_link.py, and
            # is verified there against the firmware's own standby LUT:
            #
            #   j1 = 90 + alpha              (both sides; the mirroring is
            #                                 already folded into the path
            #                                 tool's local frame)
            #   j2 = 90 - sign * beta
            #   j3 = 90 + sign * gamma       sign = +1 right legs, -1 left legs
            sign = 1 if leg_id < 3 else -1
            coxia = j1 - 90
            femur = sign * (90 - j2)
            tibia = sign * (j3 - 90)

            pose_dict[leg_id] = {
                "id": leg_id,
                "name": NAMES_LEG[leg_id],
                "coxia": coxia,
                "femur": femur,
                "tibia": tibia,
            }
        frames.append(pose_dict)
        
    return frames
