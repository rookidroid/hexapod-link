import sys
import os
sys.path.append(os.path.abspath("."))

from tests.pattern_cases.case2 import given_dimensions, alpha, beta, gamma
from pages.helpers import make_pose
from hexapod.models import VirtualHexapod, find_if_might_twist, find_twist_frame

poses = make_pose(alpha, beta, gamma)
hexapod = VirtualHexapod(given_dimensions)

might_twist = find_if_might_twist(hexapod, poses)
print("might_twist:", might_twist)

old_contacts = hexapod.ground_contacts
hexapod.update(poses, True)
new_contacts = hexapod.ground_contacts
print("twist_frame applied in update?:", hexapod.body_rotation_frame is not None)

print("right-front found:", hexapod.body.all_points[0])
