from hexapod.points import Vector

description = "Patterns Random Pose #1"
alpha = 42
beta = 66
gamma = -34.5

# ********************************
# Dimensions
# ********************************

given_dimensions = {
    "front": 76,
    "side": 92,
    "middle": 123,
    "coxia": 58,
    "femur": 177,
    "tibia": 151,
}

# ********************************
# Correct Body Vectors
# ********************************

correct_body_points = [
    Vector(x=+76.00, y=+92.00, z=+0.00, name="right-front"),
    Vector(x=+123.00, y=+0.00, z=+0.00, name="right-middle"),
    Vector(x=+76.00, y=-92.00, z=+0.00, name="right-back"),
    Vector(x=-76.00, y=+92.00, z=+0.00, name="left-front"),
    Vector(x=-123.00, y=+0.00, z=+0.00, name="left-middle"),
    Vector(x=-76.00, y=-92.00, z=+0.00, name="left-back"),
    Vector(x=+0.00, y=+0.00, z=+0.00, name="center-of-gravity"),
    Vector(x=+0.00, y=+92.00, z=+0.00, name="head"),
]


# ********************************
# Correct Leg Vectors
# ********************************

leg0_points = [
    Vector(x=+123.00, y=+0.00, z=+0.00, name="right-middle-body-contact"),
    Vector(x=+166.10, y=+38.81, z=+0.00, name="right-middle-coxia"),
    Vector(x=+219.60, y=+86.98, z=+161.70, name="right-middle-femur"),
    Vector(x=+278.24, y=+139.77, z=+32.95, name="right-middle-tibia"),
]

leg1_points = [
    Vector(x=+76.00, y=+92.00, z=+0.00, name="right-front-body-contact"),
    Vector(x=+73.53, y=+149.95, z=+0.00, name="right-front-coxia"),
    Vector(x=+70.47, y=+221.87, z=+161.70, name="right-front-femur"),
    Vector(x=+67.11, y=+300.70, z=+32.95, name="right-front-tibia"),
]

leg2_points = [
    Vector(x=-76.00, y=+92.00, z=+0.00, name="left-front-body-contact"),
    Vector(x=-133.37, y=+100.51, z=+0.00, name="left-front-coxia"),
    Vector(x=-204.58, y=+111.08, z=+161.70, name="left-front-femur"),
    Vector(x=-282.63, y=+122.66, z=+32.95, name="left-front-tibia"),
]

leg3_points = [
    Vector(x=-123.00, y=+0.00, z=+0.00, name="left-middle-body-contact"),
    Vector(x=-166.10, y=-38.81, z=+0.00, name="left-middle-coxia"),
    Vector(x=-219.60, y=-86.98, z=+161.70, name="left-middle-femur"),
    Vector(x=-278.24, y=-139.77, z=+32.95, name="left-middle-tibia"),
]

leg4_points = [
    Vector(x=-76.00, y=-92.00, z=+0.00, name="left-back-body-contact"),
    Vector(x=-73.53, y=-149.95, z=+0.00, name="left-back-coxia"),
    Vector(x=-70.47, y=-221.87, z=+161.70, name="left-back-femur"),
    Vector(x=-67.11, y=-300.70, z=+32.95, name="left-back-tibia"),
]

leg5_points = [
    Vector(x=+76.00, y=-92.00, z=+0.00, name="right-back-body-contact"),
    Vector(x=+133.37, y=-100.51, z=+0.00, name="right-back-coxia"),
    Vector(x=+204.58, y=-111.08, z=+161.70, name="right-back-femur"),
    Vector(x=+282.63, y=-122.66, z=+32.95, name="right-back-tibia"),
]


correct_leg_points = [
    leg1_points,
    leg0_points,
    leg5_points,
    leg2_points,
    leg3_points,
    leg4_points,
]
