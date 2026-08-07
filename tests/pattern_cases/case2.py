from hexapod.points import Vector

description = "Patterns Random Pose #2"
alpha = -28.5
beta = 72
gamma = -54

# ********************************
# Dimensions
# ********************************

given_dimensions = {
    "front": 65,
    "side": 101,
    "middle": 122,
    "coxia": 83,
    "femur": 108,
    "tibia": 177,
}

# ********************************
# Correct Body Vectors
# ********************************

correct_body_points = [
    Vector(x=+33.12, y=+115.45, z=+65.62, name="right-front"),
    Vector(x=+116.82, y=+35.18, z=+65.62, name="right-middle"),
    Vector(x=+91.36, y=-77.97, z=+65.62, name="right-back"),
    Vector(x=-91.36, y=+77.97, z=+65.62, name="left-front"),
    Vector(x=-116.82, y=-35.18, z=+65.62, name="left-middle"),
    Vector(x=-33.12, y=-115.45, z=+65.62, name="left-back"),
    Vector(x=+0.00, y=+0.00, z=+65.62, name="center-of-gravity"),
    Vector(x=-29.12, y=+96.71, z=+65.62, name="head"),
]

# ********************************
# Correct Leg Vectors
# ********************************

leg0_points = [
    Vector(x=+116.82, y=+35.18, z=+65.62, name="right-middle-body-contact"),
    Vector(x=+198.08, y=+18.29, z=+65.62, name="right-middle-coxia"),
    Vector(x=+230.76, y=+11.49, z=+168.34, name="right-middle-femur"),
    Vector(x=+284.31, y=+0.36, z=+0.00, name="right-middle-tibia"),
]

leg1_points = [
    Vector(x=+33.12, y=+115.45, z=+65.62, name="right-front-body-contact"),
    Vector(x=+91.30, y=+174.65, z=+65.62, name="right-front-coxia"),
    Vector(x=+114.69, y=+198.45, z=+168.34, name="right-front-femur"),
    Vector(x=+153.03, y=+237.46, z=+0.00, name="right-front-tibia"),
]

leg2_points = [
    Vector(x=-91.36, y=+77.97, z=+65.62, name="left-front-body-contact"),
    Vector(x=-121.14, y=+155.44, z=+65.62, name="left-front-coxia"),
    Vector(x=-133.11, y=+186.60, z=+168.34, name="left-front-femur"),
    Vector(x=-152.73, y=+237.65, z=+0.00, name="left-front-tibia"),
]

leg3_points = [
    Vector(x=-116.82, y=-35.18, z=+65.62, name="left-middle-body-contact"),
    Vector(x=-198.08, y=-18.29, z=+65.62, name="left-middle-coxia"),
    Vector(x=-230.76, y=-11.49, z=+168.34, name="left-middle-femur"),
    Vector(x=-284.31, y=-0.36, z=+0.00, name="left-middle-tibia"),
]

leg4_points = [
    Vector(x=-33.12, y=-115.45, z=+65.62, name="left-back-body-contact"),
    Vector(x=-91.30, y=-174.65, z=+65.62, name="left-back-coxia"),
    Vector(x=-114.69, y=-198.45, z=+168.34, name="left-back-femur"),
    Vector(x=-153.03, y=-237.46, z=+0.00, name="left-back-tibia"),
]

leg5_points = [
    Vector(x=+91.36, y=-77.97, z=+65.62, name="right-back-body-contact"),
    Vector(x=+121.14, y=-155.44, z=+65.62, name="right-back-coxia"),
    Vector(x=+133.11, y=-186.60, z=+168.34, name="right-back-femur"),
    Vector(x=+152.73, y=-237.65, z=+0.00, name="right-back-tibia"),
]

correct_leg_points = [
    leg1_points,
    leg0_points,
    leg5_points,
    leg2_points,
    leg3_points,
    leg4_points,
]
