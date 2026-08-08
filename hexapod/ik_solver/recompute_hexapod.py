from copy import deepcopy
import numpy as np
from hexapod.models import VirtualHexapod, Hexagon
from hexapod.points import (
    angle_between,
    is_counter_clockwise,
    Vector,
    rotz,
    vector_from_to,
    length,
)
from settings import ASSERTION_ENABLED, PRINT_IK


def recompute_hexapod(dimensions, ik_parameters, poses, legs_off_ground=()):

    # make the hexapod with all angles = 0
    # update the hexapod so that we know which given points are in contact with the ground
    old_hexapod = VirtualHexapod(dimensions)
    old_hexapod.update_stance(ik_parameters["hip_stance"], ik_parameters["leg_stance"])
    old_contacts = deepcopy(old_hexapod.ground_contacts)

    # make a new hexapod with all angles = 0
    # and update given the poses/ angles we've computed
    new_hexapod = VirtualHexapod(dimensions)
    new_hexapod.update(poses)
    new_contacts = deepcopy(new_hexapod.ground_contacts)

    # get two points that are on the ground before and after
    # updating to the given poses
    id1, id2 = find_two_same_leg_ids(old_contacts, new_contacts, legs_off_ground)

    # Nothing to line the body up against. The pose itself is still valid, so
    # show it where the forward-kinematics pass put it rather than throwing the
    # whole thing away.
    if id1 is None:
        return new_hexapod

    old_p1 = deepcopy(old_hexapod.legs[id1].ground_contact())
    old_p2 = deepcopy(old_hexapod.legs[id2].ground_contact())
    new_p1 = deepcopy(new_hexapod.legs[id1].ground_contact())
    new_p2 = deepcopy(new_hexapod.legs[id2].ground_contact())

    # we must translate and rotate the hexapod with the pose
    # so that the hexapod is stepping on the old predefined ground contact points
    old_vector = vector_from_to(old_p1, old_p2)
    new_vector = vector_from_to(new_p1, new_p2)

    _, twist_frame = find_twist_to_recompute_hexapod(new_vector, old_vector)
    new_hexapod.rotate_and_shift(twist_frame, 0)

    # The point being lined up has to be the same one the twist was measured
    # from -- the ground contact, which is only the foot tip while the leg is
    # standing on its foot. Under a steep pose the knee is the lowest point, and
    # reading the foot tip there slid the body by the gap between the two.
    twisted_p2 = new_hexapod.legs[id2].ground_contact()
    translate_vector = vector_from_to(twisted_p2, old_p2)
    new_hexapod.move_xyz(translate_vector.x, translate_vector.y, 0)

    might_sanity_check_points(new_p1, new_p2, old_p1, old_p2, new_vector, old_vector)

    return new_hexapod


def make_contact_dict(ground_contact_list):
    # map index in ground_contact_list
    contact_dict = {}
    for contact in ground_contact_list:
        left_or_right, front_mid_back, _ = contact.name.split("-")
        leg_placement = left_or_right + "-" + front_mid_back
        leg_id = Hexagon.VERTEX_NAMES.index(leg_placement)
        contact_dict[leg_id] = leg_placement

    return contact_dict


def find_two_same_leg_ids(old_contacts, new_contacts, legs_off_ground=()):
    """Two legs planted both before and after the pose, or (None, None).

    A leg the solver could not bring down to its target is not planted, but the
    forward-kinematics pass can still count it as a ground contact -- being the
    lowest point of a leg is not the same as being where the leg was asked to
    go. Lining the body up against such a leg pins it to a point it never
    reached and drags the rest of the robot out of place, so those are skipped.
    """
    off_ground = set(legs_off_ground)
    same_ids = []
    old_contact_dict = make_contact_dict(old_contacts)
    new_contact_dict = make_contact_dict(new_contacts)

    if PRINT_IK:
        print("In recomputing hexapod:")
        print("...old contacts:", old_contact_dict)
        print("...new_contacts: ", new_contact_dict)
        print("...legs off ground:", sorted(off_ground))

    for leg_id, leg_placement in old_contact_dict.items():
        if leg_placement in off_ground:
            continue

        if leg_id not in new_contact_dict:
            continue

        same_ids.append(leg_id)
        if len(same_ids) == 2:
            return same_ids[0], same_ids[1]

    return None, None


def find_twist_to_recompute_hexapod(a, b):
    twist = angle_between(a, b)
    z_axis = Vector(0, 0, -1)
    is_ccw = is_counter_clockwise(a, b, z_axis)
    if is_ccw:
        twist = -twist

    twist_frame = rotz(twist)
    return twist, twist_frame


def should_be_on_ground_msg(point):
    return f"Vector should be on the ground:\n{point}, z != 0"


def might_sanity_check_points(new_p1, new_p2, old_p1, old_p2, new_vector, old_vector):
    if not ASSERTION_ENABLED:
        return

    print("Sanity check on hexapod.ik_solver.recompute_hexapod")
    assert np.isclose(new_p1.z, 0, atol=1), should_be_on_ground_msg(new_p1)
    assert np.isclose(new_p2.z, 0, atol=1), should_be_on_ground_msg(new_p2)
    assert np.isclose(old_p1.z, 0, atol=1), should_be_on_ground_msg(old_p1)
    assert np.isclose(old_p2.z, 0, atol=1), should_be_on_ground_msg(old_p2)

    assert new_p1.name == old_p1.name, f"Should be the same name:\n{old_p1}\n{new_p1}"
    assert new_p2.name == old_p2.name, f"Should be the same name:\n{old_p2}\n{new_p2}"
    assert np.isclose(
        length(new_vector), length(old_vector), atol=1.0
    ), f"Should be same length.\nnew_vector:{new_vector}\n old_vector:{old_vector}"
