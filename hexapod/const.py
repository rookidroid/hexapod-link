from copy import deepcopy
from hexapod.models import VirtualHexapod, Hexagon, Linkage
from hexapod.scene import hexapod_to_scene
from hexapod.templates.pose_template import HEXAPOD_POSE

# These identify a leg or joint in code. What the user is shown is built from
# hexapod/naming.py instead, which numbers both the way the robot firmware does.
NAMES_LEG = Hexagon.VERTEX_NAMES
NAMES_JOINT = Linkage.POINT_NAMES

BASE_DIMENSIONS = {
    "front": 100,
    "side": 100,
    "middle": 100,
    "coxia": 100,
    "femur": 100,
    "tibia": 100,
}


BASE_POSE = deepcopy(HEXAPOD_POSE)

BASE_HEXAPOD = VirtualHexapod(BASE_DIMENSIONS)

HEXAPOD = deepcopy(BASE_HEXAPOD)
HEXAPOD.update(HEXAPOD_POSE)
# The neutral hexapod as the 3D view draws it, for the landing page.
BASE_SCENE = hexapod_to_scene(HEXAPOD)
