from hexapod.points import Vector

description = "Kinematics Random Pose #1"

# ********************************
# Dimensions
# ********************************

given_dimensions = {
    "front": 75,
    "side": 100,
    "middle": 125,
    "coxia": 50,
    "femur": 130,
    "tibia": 200,
}

# ********************************
# Poses
# ********************************

given_poses = {
    1: {"coxia": -40, "femur": 19, "tibia": 6, "name": "right-middle", "id": 1},
    0: {"coxia": 33, "femur": 85, "tibia": -60, "name": "right-front", "id": 0},
    3: {"coxia": -20, "femur": 90, "tibia": -13, "name": "left-front", "id": 3},
    4: {"coxia": -12, "femur": -25, "tibia": 3, "name": "left-middle", "id": 4},
    5: {"coxia": 0, "femur": 94, "tibia": -70, "name": "left-back", "id": 5},
    2: {"coxia": -5, "femur": 17, "tibia": 2, "name": "right-back", "id": 2},
}


# ********************************
# Correct Body Vectors
# ********************************

correct_body_points = [
    Vector(x=-4.04, y=+111.02, z=+100.61, name="right-front"),
    Vector(x=+97.52, y=+69.30, z=+121.71, name="right-middle"),
    Vector(x=+121.07, y=-27.85, z=+171.77, name="right-back"),
    Vector(x=-121.07, y=+27.85, z=+144.07, name="left-front"),
    Vector(x=-97.52, y=-69.30, z=+194.13, name="left-middle"),
    Vector(x=+4.04, y=-111.02, z=+215.22, name="left-back"),
    Vector(x=+0.00, y=+0.00, z=+157.92, name="center-of-gravity"),
    Vector(x=-62.55, y=+69.43, z=+122.34, name="head"),
]

# ********************************
# Leg Vectors
# ********************************

leg0_points = [
    Vector(x=+97.52, y=+69.30, z=+121.71, name="right-middle-body-contact"),
    Vector(x=+147.51, y=+68.22, z=+122.05, name="right-middle-coxia"),
    Vector(x=+270.56, y=+84.99, z=+160.48, name="right-middle-femur"),
    Vector(x=+354.36, y=+0.00, z=+0.00, name="right-middle-tibia"),
]

leg1_points = [
    Vector(x=-4.04, y=+111.02, z=+100.61, name="right-front-body-contact"),
    Vector(x=-32.61, y=+147.53, z=+81.89, name="right-front-coxia"),
    Vector(x=-38.58, y=+215.22, z=+192.71, name="right-front-femur"),
    Vector(x=-87.59, y=+193.77, z=+0.00, name="right-front-tibia"),
]

leg2_points = [
    Vector(x=-121.07, y=+27.85, z=+144.07, name="left-front-body-contact"),
    Vector(x=-162.32, y=+53.03, z=+131.25, name="left-front-coxia"),
    Vector(x=-161.81, y=+112.67, z=+246.76, name="left-front-femur"),
    Vector(x=-322.77, y=+190.17, z=+156.81, name="left-front-tibia"),
]

leg3_points = [
    Vector(x=-97.52, y=-69.30, z=+194.13, name="left-middle-body-contact"),
    Vector(x=-142.18, y=-89.20, z=+204.60, name="left-middle-coxia"),
    Vector(x=-247.63, y=-161.29, z=+180.45, name="left-middle-femur"),
    Vector(x=-181.43, y=-216.56, z=+0.00, name="left-middle-tibia"),
]

leg4_points = [
    Vector(x=+4.04, y=-111.02, z=+215.22, name="left-back-body-contact"),
    Vector(x=+5.66, y=-155.42, z=+238.15, name="left-back-coxia"),
    Vector(x=+5.87, y=-87.87, z=+349.22, name="left-back-femur"),
    Vector(x=+7.79, y=-243.94, z=+224.17, name="left-back-tibia"),
]

leg5_points = [
    Vector(x=+121.07, y=-27.85, z=+171.77, name="right-back-body-contact"),
    Vector(x=+168.23, y=-42.70, z=+179.23, name="right-back-coxia"),
    Vector(x=+285.63, y=-62.18, z=+231.55, name="right-back-femur"),
    Vector(x=+346.31, y=-168.27, z=+73.24, name="right-back-tibia"),
]

correct_leg_points = [
    leg1_points,
    leg0_points,
    leg5_points,
    leg2_points,
    leg3_points,
    leg4_points,
]
