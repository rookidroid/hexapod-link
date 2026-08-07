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
        "femur": 26.276957259313747,
        "tibia": -38.39772518650969,
    },
    0: {
        "name": "right-front",
        "id": 0,
        "coxia": -28.479335288932702,
        "femur": 28.605906804699067,
        "tibia": -44.7068590874612,
    },
    3: {
        "name": "left-front",
        "id": 3,
        "coxia": -2.7587597543737274,
        "femur": 61.74999721615881,
        "tibia": -42.31866282701506,
    },
    4: {
        "name": "left-middle",
        "id": 4,
        "coxia": -14.447799823858873,
        "femur": 64.61701942138204,
        "tibia": -27.21279908137491,
    },
    5: {
        "name": "left-back",
        "id": 5,
        "coxia": -31.482208518362086,
        "femur": 58.21542430216202,
        "tibia": -18.886694671926904,
    },
    2: {
        "name": "right-back",
        "id": 2,
        "coxia": -32.03744705478175,
        "femur": 41.81637504921453,
        "tibia": -30.600003454967492,
    },
}
