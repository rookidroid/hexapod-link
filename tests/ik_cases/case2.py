description = "IK Random Pose #2"

# ********************************
# Dimensions
# ********************************

given_dimensions = {
    "front": 76,
    "side": 114,
    "middle": 125,
    "coxia": 63,
    "femur": 142,
    "tibia": 171,
}

# ********************************
# IK Parameters
# ********************************

given_ik_parameters = {
    "hip_stance": 10.5,
    "leg_stance": 25.5,
    "percent_x": 0.3,
    "percent_y": 0.05,
    "percent_z": -0.15,
    "rot_x": -1,
    "rot_y": 12.5,
    "rot_z": -8.5,
}

# ********************************
# Poses
# ********************************

correct_poses = {
    1: {
        "name": "right-middle",
        "id": 1,
        "coxia": 13.43107675540267,
        "femur": 77.7924770301091,
        "tibia": -60.647267530564136,
    },
    0: {
        "name": "right-front",
        "id": 0,
        "coxia": 16.42977972327651,
        "femur": 61.72729607705039,
        "tibia": -51.985972899100375,
    },
    3: {
        "name": "left-front",
        "id": 3,
        "coxia": 32.21115096125315,
        "femur": 14.381990786282792,
        "tibia": -6.3580729468430945,
    },
    4: {
        "name": "left-middle",
        "id": 4,
        "coxia": 14.685705676958776,
        "femur": 3.177447435672022,
        "tibia": 4.800985597502901,
    },
    5: {
        "name": "left-back",
        "id": 5,
        "coxia": -2.4023016746446615,
        "femur": 11.211660624961894,
        "tibia": -5.739531350004228,
    },
    2: {
        "name": "right-back",
        "id": 2,
        "coxia": 13.000938878590318,
        "femur": 55.46991456387096,
        "tibia": -46.72960228202504,
    },
}
