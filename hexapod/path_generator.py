import numpy as np

# Physical robot configuration from path_tool's config.json
PHYSICAL_CONFIG = {
    "legNames": [
        "front_right", "center_right", "rear_right",
        "front_left", "center_left", "rear_left"
    ],
    "legMountX": [40.9, 81.8, 40.9, -40.9, -81.8, -40.9],
    "legMountY": [70.84, 0, -70.84, 70.84, 0, -70.84],
    "legMountAngle": [60, 0, -60, -240, -180, -120],
    "legScale": [
        [1, 1, 1], [1, 1, 1], [1, 1, 1],
        [1, -1, -1], [1, -1, -1], [1, -1, -1]
    ],
    "legRootToJoint1": 0,
    "legJoint1ToJoint2": 36.0,
    "legJoint2ToJoint3": 43.6,
    "legJoint3ToTip": 85.22
}

def get_simulator_dimensions():
    """Maps the physical robot's dimensions to the simulator's format."""
    return {
        "front": 40.9,
        "side": 70.84,
        "middle": 81.8,
        "coxia": PHYSICAL_CONFIG["legJoint1ToJoint2"],
        "femur": PHYSICAL_CONFIG["legJoint2ToJoint3"],
        "tibia": PHYSICAL_CONFIG["legJoint3ToTip"],
    }

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
    halfsteps = int(g_steps / 2)
    path = np.zeros((g_steps, 6, 3))
    semi_circle = semicircle_generator(g_radius, g_steps)
    mir_path = np.roll(semi_circle, halfsteps, axis=0)
    if direction == "left":
        path[:, 0, :] = path_rotate_z(semi_circle, 45)
        path[:, 1, :] = path_rotate_z(mir_path, 0)
        path[:, 2, :] = path_rotate_z(semi_circle, 315)
        path[:, 5, :] = path_rotate_z(mir_path, 225)
        path[:, 4, :] = path_rotate_z(semi_circle, 180)
        path[:, 3, :] = path_rotate_z(mir_path, 135)
    elif direction == "right":
        path[:, 0, :] = path_rotate_z(semi_circle, 45 + 180)
        path[:, 1, :] = path_rotate_z(mir_path, 0 + 180)
        path[:, 2, :] = path_rotate_z(semi_circle, 315 + 180)
        path[:, 5, :] = path_rotate_z(mir_path, 225 + 180)
        path[:, 4, :] = path_rotate_z(semi_circle, 180 + 180)
        path[:, 3, :] = path_rotate_z(mir_path, 135 + 180)
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
    r_leg2_offset = np.zeros((adjust_leg_size, 3))
    r_leg2_offset[:, 0] = x_offset
    r_leg2_offset[:, 2] = z_offset
    r_leg1_offset = path_rotate_z(r_leg2_offset, 45)
    r_leg3_offset = path_rotate_z(r_leg2_offset, -45)
    l_leg1_offset = path_rotate_z(r_leg2_offset, 135)
    l_leg2_offset = path_rotate_z(r_leg2_offset, 180)
    l_leg3_offset = path_rotate_z(r_leg2_offset, -135)
    for idx in range(0, adjust_leg_size):
        lut_standup[idx + lift_up_size, :, :] = lut_standup[lift_up_size - 1, :, :]
        lut_standup[idx + lift_up_size, 3, :] = lut_standup[idx + lift_up_size, 3, :] + l_leg1_offset[idx, :]
        lut_standup[idx + lift_up_size, 1, :] = lut_standup[idx + lift_up_size, 1, :] + r_leg2_offset[idx, :]
        lut_standup[idx + lift_up_size, 5, :] = lut_standup[idx + lift_up_size, 5, :] + l_leg3_offset[idx, :]
    for idx in range(0, adjust_leg_size):
        lut_standup[idx + lift_up_size + adjust_leg_size, :, :] = lut_standup[lift_up_size + adjust_leg_size - 1, :, :]
        lut_standup[idx + lift_up_size + adjust_leg_size, 0, :] = lut_standup[idx + lift_up_size + adjust_leg_size, 0, :] + r_leg1_offset[idx, :]
        lut_standup[idx + lift_up_size + adjust_leg_size, 4, :] = lut_standup[idx + lift_up_size + adjust_leg_size, 4, :] + l_leg2_offset[idx, :]
        lut_standup[idx + lift_up_size + adjust_leg_size, 2, :] = lut_standup[idx + lift_up_size + adjust_leg_size, 2, :] + r_leg3_offset[idx, :]
    return lut_standup

# --- Bridge to Simulator ---

# Path tool: 0:front_right, 1:center_right, 2:rear_right, 3:front_left, 4:center_left, 5:rear_left
# Simulator: 0:right-front, 1:right-middle, 2:right-back, 3:left-front, 4:left-middle, 5:left-back

def generate_poses(motion_name):
    """
    Generates a list of poses for a given motion name, compatible with VirtualHexapod.update().
    Returns: list of dicts, where each dict is a pose for all 6 legs at a specific frame.
    """
    standby = gen_posture(60, 75, PHYSICAL_CONFIG)
    laydown = gen_posture(25, 25, PHYSICAL_CONFIG)

    # Generate Cartesian path
    if motion_name == "standby":
        path = np.array([standby])
    elif motion_name == "walk_0":
        path = gen_walk_path(standby, direction=0)
    elif motion_name == "walk_180":
        path = gen_walk_path(standby, direction=180)
    elif motion_name == "walk_r45":
        path = gen_walk_path(standby, direction=315)
    elif motion_name == "walk_r90":
        path = gen_walk_path(standby, direction=270)
    elif motion_name == "walk_r135":
        path = gen_walk_path(standby, direction=225)
    elif motion_name == "walk_l45":
        path = gen_walk_path(standby, direction=45)
    elif motion_name == "walk_l90":
        path = gen_walk_path(standby, direction=90)
    elif motion_name == "walk_l135":
        path = gen_walk_path(standby, direction=135)
    elif motion_name == "fast_forward":
        path = gen_fastwalk_path(standby, g_steps=28, y_radius=40, z_radius=30)
    elif motion_name == "fast_backward":
        path = gen_fastwalk_path(standby, g_steps=28, y_radius=40, z_radius=30, reverse=True)
    elif motion_name == "turn_left":
        path = gen_turn_path(standby, direction="left")
    elif motion_name == "turn_right":
        path = gen_turn_path(standby, direction="right")
    elif motion_name == "climb_forward":
        path = gen_climb_path(standby, reverse=False)
    elif motion_name == "climb_backward":
        path = gen_climb_path(standby, reverse=True)
    elif motion_name == "rotate_x":
        path = gen_rotatex_path(standby, g_steps=28, swing_angle=10, y_radius=10)
    elif motion_name == "rotate_y":
        path = gen_rotatey_path(standby, g_steps=28, swing_angle=10, x_radius=10)
    elif motion_name == "rotate_z":
        path = gen_rotatez_path(standby, g_steps=28, z_lift=7)
    elif motion_name == "twist":
        path = gen_twist_path(standby, g_steps=28)
    elif motion_name == "standup":
        path = gen_standup_path(standby, laydown, steps=28)
    else:
        path = np.array([standby])

    frames = []
    from hexapod.const import NAMES_LEG
    for step in range(path.shape[0]):
        # Convert Cartesian to joint angles (j1, j2, j3)
        angles = inverse_kinematics(path[step], PHYSICAL_CONFIG)
        
        pose_dict = {}
        for pt_idx in range(6):
            sim_idx = pt_idx
            
            j1 = angles[pt_idx, 0]
            j2 = angles[pt_idx, 1]
            j3 = angles[pt_idx, 2]
            
            # Map path tool's angles to simulator's angles (coxia/femur/tibia)
            # Path tool measures j1 from 90 degree offset
            coxia = j1 - 90
            # For left legs, j1 is mirrored
            if pt_idx >= 3:
                coxia = -(j1 - 90)

            # j2 and j3 mapping
            # simulator neutral: straight line (beta=0), straight down (gamma=0)
            # path tool neutral: ? path tool calculates angles from geometry
            if pt_idx < 3: # Right legs
                femur = -(90 - j2)
                tibia = -(j3 - 90)
            else:          # Left legs
                femur = 90 - j2
                tibia = j3 - 90
                
            pose_dict[sim_idx] = {
                "id": sim_idx,
                "name": NAMES_LEG[sim_idx],
                "coxia": coxia,
                "femur": femur,
                "tibia": tibia,
            }
        frames.append(pose_dict)
        
    return frames
