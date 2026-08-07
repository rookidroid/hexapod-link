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
    Vector(x=+59.46, y=+93.84, z=+100.61, name="right-front"),
    Vector(x=+119.62, y=+1.99, z=+121.71, name="right-middle"),
    Vector(x=+84.09, y=-91.45, z=+171.77, name="right-back"),
    Vector(x=-84.09, y=+91.45, z=+144.07, name="left-front"),
    Vector(x=-119.62, y=-1.99, z=+194.13, name="left-middle"),
    Vector(x=-59.46, y=-93.84, z=+215.22, name="left-back"),
    Vector(x=+0.00, y=+0.00, z=+157.92, name="center-of-gravity"),
    Vector(x=-12.31, y=+92.64, z=+122.34, name="head"),
]

# ********************************
# Leg Vectors
# ********************************

leg0_points = [
    Vector(x=+119.62, y=+1.99, z=+121.71, name="right-middle-body-contact"),
    Vector(x=+160.24, y=-27.17, z=+122.05, name="right-middle-coxia"),
    Vector(x=+271.19, y=-82.94, z=+160.48, name="right-middle-femur"),
    Vector(x=+292.23, y=-200.42, z=+0.00, name="right-middle-tibia"),
]

leg1_points = [
    Vector(x=+59.46, y=+93.84, z=+100.61, name="right-front-body-contact"),
    Vector(x=+56.55, y=+140.11, z=+81.89, name="right-front-coxia"),
    Vector(x=+89.91, y=+199.31, z=+192.71, name="right-front-femur"),
    Vector(x=+37.36, y=+209.34, z=+0.00, name="right-front-tibia"),
]

leg2_points = [
    Vector(x=-84.09, y=+91.45, z=+144.07, name="left-front-body-contact"),
    Vector(x=-103.87, y=+135.54, z=+131.25, name="left-front-coxia"),
    Vector(x=-69.72, y=+184.44, z=+246.76, name="left-front-femur"),
    Vector(x=-158.62, y=+339.38, z=+156.81, name="left-front-tibia"),
]

leg3_points = [
    Vector(x=-119.62, y=-1.99, z=+194.13, name="left-middle-body-contact"),
    Vector(x=-167.71, y=+6.86, z=+204.60, name="left-middle-coxia"),
    Vector(x=-295.44, y=+7.04, z=+180.45, name="left-middle-femur"),
    Vector(x=-272.11, y=-75.97, z=+0.00, name="left-middle-tibia"),
]

leg4_points = [
    Vector(x=-59.46, y=-93.84, z=+215.22, name="left-back-body-contact"),
    Vector(x=-83.24, y=-131.37, z=+238.15, name="left-back-coxia"),
    Vector(x=-44.86, y=-75.79, z=+349.22, name="left-back-femur"),
    Vector(x=-131.55, y=-205.58, z=+224.17, name="left-back-tibia"),
]

leg5_points = [
    Vector(x=+84.09, y=-91.45, z=+171.77, name="right-back-body-contact"),
    Vector(x=+114.58, y=-130.36, z=+179.23, name="right-back-coxia"),
    Vector(x=+200.39, y=-212.83, z=+231.55, name="right-back-femur"),
    Vector(x=+190.42, y=-334.64, z=+73.24, name="right-back-tibia"),
]

correct_leg_points = [
    leg1_points,
    leg0_points,
    leg5_points,
    leg2_points,
    leg3_points,
    leg4_points,
]
