description = "IK Pose where x, y translation, rot y and z are close to extreme"

# ********************************
# Dimensions
# ********************************

given_dimensions = {
    "front": 73,
    "side": 100,
    "middle": 130,
    "coxia": 75,
    "femur": 129,
    "tibia": 154,
}

# ********************************
# IK Parameters
# ********************************

given_ik_parameters = {
    "hip_stance": 10.5,
    "leg_stance": 30,
    "percent_x": 0.7,
    "percent_y": -0.4,
    "percent_z": 0.2,
    "rot_x": 1.5,
    "rot_y": -16,
    "rot_z": -14.5,
}

# ********************************
# Poses
# ********************************

correct_poses = {
    1: {
        "name": "right-middle",
        "id": 1,
        "coxia": 55.560735264458664,
        "femur": -24.206649398630788,
        "tibia": -8.608209643253772,
    },
    0: {
        "name": "right-front",
        "id": 0,
        "coxia": 48.495495560637686,
        "femur": -2.233541247495843,
        "tibia": -3.350394344605448,
    },
    3: {
        "name": "left-front",
        "id": 3,
        "coxia": 37.325543192420426,
        "femur": 30.51664156495821,
        "tibia": 14.567768525527683,
    },
    4: {
        "name": "left-middle",
        "id": 4,
        "coxia": 13.117976527545807,
        "femur": 48.11622597324919,
        "tibia": -0.4754969993002618,
    },
    5: {
        "name": "left-back",
        "id": 5,
        "coxia": -10.409633194567618,
        "femur": 52.78878537008139,
        "tibia": -23.62757967078278,
    },
    2: {
        "name": "right-back",
        "id": 2,
        "coxia": 17.6433629259098,
        "femur": -15.004470431866508,
        "tibia": -27.565310208989757,
    },
}
