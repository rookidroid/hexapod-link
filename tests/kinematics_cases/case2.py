from hexapod.points import Vector

description = "Kinematics Random Pose #2"

# ********************************
# Dimensions
# ********************************

given_dimensions = {
    "front": 53,
    "side": 112,
    "middle": 124,
    "coxia": 65,
    "femur": 147,
    "tibia": 158,
}

# ********************************
# Poses
# ********************************

given_poses = {
    1: {
        "name": "right-middle",
        "id": 1,
        "coxia": -46.173564612682185,
        "femur": -0.5639873561713742,
        "tibia": -22.853557731606656,
    },
    0: {
        "name": "right-front",
        "id": 0,
        "coxia": -38.57261437211969,
        "femur": -3.2736722565308938,
        "tibia": -24.640160005779748,
    },
    3: {
        "name": "left-front",
        "id": 3,
        "coxia": 2.0526054688295687,
        "femur": 35.09407799312794,
        "tibia": -31.188148885325916,
    },
    4: {
        "name": "left-middle",
        "id": 4,
        "coxia": -16.947073091191385,
        "femur": 46.44561383735447,
        "tibia": -19.412041056143877,
    },
    5: {
        "name": "left-back",
        "id": 5,
        "coxia": -33.39847023693062,
        "femur": 41.05787103974741,
        "tibia": -5.900804146706449,
    },
    2: {
        "name": "right-back",
        "id": 2,
        "coxia": -38.67228081907621,
        "femur": 18.790558327957655,
        "tibia": -30.220554892132796,
    },
}

# ********************************
# Correct Body Vectors
# ********************************

correct_body_points = [
    Vector(x=+15.34, y=+122.33, z=+118.25, name="right-front"),
    Vector(x=+115.62, y=+36.61, z=+131.67, name="right-middle"),
    Vector(x=+83.50, y=-91.03, z=+115.51, name="right-back"),
    Vector(x=-83.50, y=+91.03, z=+96.18, name="left-front"),
    Vector(x=-115.62, y=-36.61, z=+80.03, name="left-middle"),
    Vector(x=-15.34, y=-122.33, z=+93.44, name="left-back"),
    Vector(x=+0.00, y=+0.00, z=+105.85, name="center-of-gravity"),
    Vector(x=-34.08, y=+106.68, z=+107.22, name="head"),
]


# ********************************
# Leg Vectors
# ********************************

leg0_points = [
    Vector(x=+115.62, y=+36.61, z=+131.67, name="right-middle-body-contact"),
    Vector(x=+171.87, y=+5.23, z=+140.47, name="right-middle-coxia"),
    Vector(x=+299.33, y=-65.62, z=+158.95, name="right-middle-femur"),
    Vector(x=+273.23, y=-24.47, z=+8.65, name="right-middle-tibia"),
]


leg1_points = [
    Vector(x=+15.34, y=+122.33, z=+118.25, name="right-front-body-contact"),
    Vector(x=+61.06, y=+166.80, z=+130.75, name="right-front-coxia"),
    Vector(x=+165.94, y=+267.84, z=+150.77, name="right-front-femur"),
    Vector(x=+141.09, y=+227.67, z=+0.00, name="right-front-tibia"),
]

leg2_points = [
    Vector(x=-83.50, y=+91.03, z=+96.18, name="left-front-body-contact"),
    Vector(x=-128.94, y=+137.19, z=+90.66, name="left-front-coxia"),
    Vector(x=-229.47, y=+216.27, z=+163.10, name="left-front-femur"),
    Vector(x=-206.30, y=+235.70, z=+8.02, name="left-front-tibia"),
]

leg3_points = [
    Vector(x=-115.62, y=-36.61, z=+80.03, name="left-middle-body-contact"),
    Vector(x=-179.37, y=-36.92, z=+67.31, name="left-middle-coxia"),
    Vector(x=-299.44, y=-45.37, z=+151.69, name="left-middle-femur"),
    Vector(x=-342.46, y=-35.19, z=+0.00, name="left-middle-tibia"),
]

leg4_points = [
    Vector(x=-15.34, y=-122.33, z=+93.44, name="left-back-body-contact"),
    Vector(x=-56.87, y=-170.87, z=+81.46, name="left-back-coxia"),
    Vector(x=-146.50, y=-260.87, z=+155.46, name="left-back-femur"),
    Vector(x=-179.47, y=-319.16, z=+12.36, name="left-back-tibia"),
]

leg5_points = [
    Vector(x=+83.50, y=-91.03, z=+115.51, name="right-back-body-contact"),
    Vector(x=+88.76, y=-155.70, z=+111.62, name="right-back-coxia"),
    Vector(x=+90.78, y=-297.70, z=+149.58, name="right-back-femur"),
    Vector(x=+118.41, y=-254.97, z=+0.00, name="right-back-tibia"),
]


correct_leg_points = [
    leg1_points,
    leg0_points,
    leg5_points,
    leg2_points,
    leg3_points,
    leg4_points,
]
