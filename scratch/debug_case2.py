import sys
import os
sys.path.append(os.path.abspath("."))

from tests.pattern_cases.case2 import given_dimensions, alpha, beta, gamma
from pages.helpers import make_pose
from copy import deepcopy
from hexapod.models import VirtualHexapod, find_twist_frame

poses = make_pose(alpha, beta, gamma)
hexapod = VirtualHexapod(given_dimensions)

old_contacts = deepcopy(hexapod.ground_contacts)
hexapod.update(poses, True)
new_contacts = hexapod.ground_contacts
print("shared contacts:", sorted(
    {p.name for p in old_contacts} & {p.name for p in new_contacts}))
print("twist frame:\n", find_twist_frame(old_contacts, new_contacts))

print("right-front found:", hexapod.body.all_points[0])
