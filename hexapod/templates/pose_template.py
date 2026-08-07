# pose = {
#   LEG_ID: {
#     'name': LEG_NAME,
#     'id': LEG_ID
#     'coxia': ALPHA,
#     'femur': BETA,
#     'tibia': GAMMA}
#   }
#
# LEG_ID is the leg index shared with the robot firmware, and the joints are
# listed body-outward as Joint 1, 2 and 3. See hexapod/naming.py.
from hexapod.naming import JOINT_NAMES, LEG_NAMES

HEXAPOD_POSE = {
    leg_id: dict(
        {joint: 0 for joint in JOINT_NAMES},
        name=name,
        id=leg_id,
    )
    for leg_id, name in enumerate(LEG_NAMES)
}
