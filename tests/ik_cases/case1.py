description = "IK Random Pose #1"

# ********************************
# Dimensions
# ********************************

given_dimensions = {
    "front": 70,
    "side": 115,
    "middle": 120,
    "coxia": 60,
    "femur": 130,
    "tibia": 150,
}

# ********************************
# IK Parameters
# ********************************

given_ik_parameters = {
    "hip_stance": 7,
    "leg_stance": 32,
    "percent_x": 0.35,
    "percent_y": 0.25,
    "percent_z": -0.2,
    "rot_x": 2.5,
    "rot_y": -9,
    "rot_z": 14,
}

# ********************************
# Poses
# ********************************

correct_poses = {
    1: {
        "name": "right-middle",
        "id": 1,
        "coxia": -36.89755490432384,
        "femur": 26.276957259313683,
        "tibia": -38.39772518650969,
    },
    0: {
        "name": "right-front",
        "id": 0,
        "coxia": -31.715493484789533,
        "femur": 27.717090725335396,
        "tibia": -41.67638594657396,
    },
    3: {
        "name": "left-front",
        "id": 3,
        "coxia": -3.1127758531426934,
        "femur": 64.38109364320302,
        "tibia": -41.751719577946915,
    },
    4: {
        "name": "left-middle",
        "id": 4,
        "coxia": -14.447799823858816,
        "femur": 64.61701942138204,
        "tibia": -27.21279908137491,
    },
    5: {
        "name": "left-back",
        "id": 5,
        "coxia": -27.925865837440085,
        "femur": 57.5357711909659,
        "tibia": -15.824751016445546,
    },
    2: {
        "name": "right-back",
        "id": 2,
        "coxia": -34.07683786865073,
        "femur": 40.018917104647784,
        "tibia": -36.78650126914302,
    },
}
