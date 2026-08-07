# This module contains the model of a hexapod
# It's used to manipulate the pose of the hexapod
from copy import deepcopy
from pprint import pprint
from math import atan2, degrees, isclose
import json
import numpy as np
from settings import PRINT_MODEL_ON_UPDATE, ALPHA_MAX_ANGLE, BETA_MAX_ANGLE, GAMMA_MAX_ANGLE
from hexapod.linkage import Linkage
from hexapod.naming import LEG_NAMES, joint_label, leg_label
import hexapod.ground_contact_solver.ground_contact_solver as gc
import hexapod.ground_contact_solver.ground_contact_solver2 as gc2

from hexapod.templates.pose_template import HEXAPOD_POSE
from hexapod.points import (
    Vector,
    frame_to_align_vector_a_to_b,
    frame_rotxyz,
    rotz,
)


# Dimensions f, s, and m
#
#       |-f-|
#       *---*---*--------
#      /    |    \     |
#     /     |     \    s
#    /      |      \   |
#   *------cog------* ---
#    \      |      /|
#     \     |     / |
#      \    |    /  |
#       *---*---*   |
#           |       |
#           |---m---|
#
#    y axis
#    ^
#    |
#    |
#    ----> x axis
#  cog (origin)
#
#
# Relative x-axis, for each attached linkage
#
#         x2          x1
#          \         /
#           *---*---*
#          /    |    \
#         /     |     \
#        /      |      \
#  x3 --*------cog------*-- x0
#        \      |      /
#         \     |     /
#          \    |    /
#           *---*---*
#          /         \
#         x4         x5
#
class Hexagon:
    # Ordered to match the firmware's leg indices; see hexapod/naming.py
    VERTEX_NAMES = LEG_NAMES
    __slots__ = (
        "f",
        "m",
        "s",
        "cog",
        "head",
        "vertices",
        "all_points",
        "coxia_axes",
    )

    def __init__(self, f, m, s):
        self.f = f
        self.m = m
        self.s = s

        self.cog = Vector(0, 0, 0, name="center-of-gravity")
        self.head = Vector(0, s, 0, name="head")
        self.vertices = [
            Vector(f, s, 0, name=Hexagon.VERTEX_NAMES[0]),
            Vector(m, 0, 0, name=Hexagon.VERTEX_NAMES[1]),
            Vector(f, -s, 0, name=Hexagon.VERTEX_NAMES[2]),
            Vector(-f, s, 0, name=Hexagon.VERTEX_NAMES[3]),
            Vector(-m, 0, 0, name=Hexagon.VERTEX_NAMES[4]),
            Vector(-f, -s, 0, name=Hexagon.VERTEX_NAMES[5]),
        ]

        self.all_points = self.vertices + [self.cog, self.head]

        # Azimuth of each leg's coxia (joint 1) rotation axis, in the body frame.
        #
        # A leg bolts onto its hexagon corner and points radially away from the
        # cog, so the axis direction is the direction of the vertex itself --
        # it follows from f, m and s rather than being a constant. It must,
        # because the path generator solves IK around the physical robot's
        # `legMountAngle` (hexapod/robot_profiles.py), and for both robots that
        # angle is exactly atan2(legMountY, legMountX). Pinning these to the
        # 45/0/315/135/180/225 that a square body happens to give would rotate
        # each corner leg about its own mount point, which shears the support
        # polygon apart as a gait plays instead of translating it rigidly.
        self.coxia_axes = tuple(
            degrees(atan2(vertex.y, vertex.x)) % 360 for vertex in self.vertices
        )


# ..........................................
# The hexapod model
# ..........................................
class VirtualHexapod:
    LEG_COUNT = 6
    __slots__ = (
        "body",
        "legs",
        "dimensions",
        "coxia",
        "femur",
        "tibia",
        "front",
        "side",
        "mid",
        "body_rotation_frame",
        "ground_contacts",
        "x_axis",
        "y_axis",
        "z_axis",
    )

    def __init__(self, dimensions):
        self._store_attributes(dimensions)
        self._init_legs()
        self._init_local_frame()

    def update(self, poses, assume_ground_targets=True):
        """Pose the hexapod and settle it onto the ground."""
        might_raise_poses_range_error(poses)

        self.body_rotation_frame = None
        old_contacts = deepcopy(self.ground_contacts)

        # Update leg poses
        for pose in poses.values():
            i = pose["id"]
            self.legs[i].change_pose(pose["coxia"], pose["femur"], pose["tibia"])

        # Find new orientation of the body (new normal)
        # distance of cog from ground and which legs are on the ground
        if assume_ground_targets:
            # We are positive that our assumed target ground contact points
            # are correct then we don't have to test all possible cases
            legs, n_axis, height = gc.compute_orientation_properties(self.legs)
        else:
            legs, n_axis, height = gc2.compute_orientation_properties(self.legs)

        if n_axis is None:
            raise Exception("❗Pose Unstable. COG not inside support polygon.")

        # Tilt and shift the hexapod based on new normal
        frame = frame_to_align_vector_a_to_b(n_axis, Vector(0, 0, 1))
        self.rotate_and_shift(frame, height)
        self._update_local_frame(frame)

        # Twist around the new normal. find_twist_frame returns the identity
        # when the planted feet did not turn, so this needs no guard.
        self.ground_contacts = [leg.ground_contact() for leg in legs]
        self.rotate_and_shift(find_twist_frame(old_contacts, self.ground_contacts))

        might_print_hexapod(self, poses)

    def detach_body_rotate_and_translate(self, rx, ry, rz, tx, ty, tz):
        # Detach the body of the hexapod from the legs
        # then rotate and translate body as if a separate entity
        frame = frame_rotxyz(rx, ry, rz)
        self.body_rotation_frame = frame

        for point in self.body.all_points:
            point.update_point_wrt(frame)
            point.move_xyz(tx, ty, tz)

        self._update_local_frame(frame)

    def move_xyz(self, tx, ty, tz):
        for point in self.body.all_points:
            point.move_xyz(tx, ty, tz)

        for leg in self.legs:
            for point in leg.all_points:
                point.move_xyz(tx, ty, tz)

    def update_stance(self, hip_stance, leg_stance):
        pose = deepcopy(HEXAPOD_POSE)
        pose[0]["coxia"] = -hip_stance  # right_front
        pose[3]["coxia"] = hip_stance  # left_front
        pose[5]["coxia"] = -hip_stance  # left_back
        pose[2]["coxia"] = hip_stance  # right_back

        for leg in pose.values():
            leg["femur"] = leg_stance
            leg["tibia"] = -leg_stance

        self.update(pose)

    def sum_of_dimensions(self):
        f, m, s = self.front, self.mid, self.side
        a, b, c = self.coxia, self.femur, self.tibia
        return f + m + s + a + b + c

    def _store_attributes(self, dimensions):
        self.body_rotation_frame = None
        self.dimensions = dimensions
        self.coxia = dimensions["coxia"]
        self.femur = dimensions["femur"]
        self.tibia = dimensions["tibia"]
        self.front = dimensions["front"]
        self.mid = dimensions["middle"]
        self.side = dimensions["side"]
        self.body = Hexagon(self.front, self.mid, self.side)

    def _init_legs(self):
        self.legs = []
        for i in range(VirtualHexapod.LEG_COUNT):
            linkage = Linkage(
                self.coxia,
                self.femur,
                self.tibia,
                coxia_axis=self.body.coxia_axes[i],
                new_origin=self.body.vertices[i],
                name=Hexagon.VERTEX_NAMES[i],
                id_number=i,
            )
            self.legs.append(linkage)

        self.ground_contacts = [leg.ground_contact() for leg in self.legs]

    def rotate_and_shift(self, frame, height=0):
        for vertex in self.body.all_points:
            vertex.update_point_wrt(frame, height)

        for leg in self.legs:
            leg.update_leg_wrt(frame, height)

    def _init_local_frame(self):
        self.x_axis = Vector(1, 0, 0, name="hexapod x axis")
        self.y_axis = Vector(0, 1, 0, name="hexapod y axis")
        self.z_axis = Vector(0, 0, 1, name="hexapod z axis")

    def _update_local_frame(self, frame):
        # Update the x, y, z axis centered at cog of hexapod
        self.x_axis.update_point_wrt(frame)
        self.y_axis.update_point_wrt(frame)
        self.z_axis.update_point_wrt(frame)


# ..........................................
# Helper functions
# ..........................................

def might_raise_poses_range_error(poses):
    angle_limits = {
        "coxia": ALPHA_MAX_ANGLE,
        "femur": BETA_MAX_ANGLE,
        "tibia": GAMMA_MAX_ANGLE,
    }

    def _within_range(angle, max_angle):
        return -max_angle <= angle <= max_angle

    def _raise_range_error(leg_name, joint_name, angle, max_angle):
        identifier = f"{leg_label(leg_name)} {joint_label(joint_name)} angle is {angle}"
        msg = f"{identifier}. Must be within [-{max_angle}, {max_angle}]"
        raise Exception(msg)

    for pose in poses.values():
        for joint_name in angle_limits:

            angle = pose[joint_name]
            max_angle = angle_limits[joint_name]

            if _within_range(angle, max_angle):
                continue

            _raise_range_error(pose["name"], joint_name, angle, max_angle)


def find_twist_frame(old_ground_contacts, new_ground_contacts):
    """The frame that undoes the body's rotation about the ground normal.

    Feet on the ground before and after a pose change did not slide, so whatever
    apparent motion they show is really the body having moved underneath them.
    This recovers the turning part of that motion so the caller can take it back
    out, leaving the planted feet where they were.

    Only the turning part. A foot that ends up somewhere new has either been
    carried around the body's centre or carried straight past it, and those two
    have to be told apart: a walking gait drives its planted feet in a straight
    line, and reading that line as a turn is what used to make the body yaw and
    then snap back every time the stance tripod swapped. So the rotation is
    measured about the centroid of the planted feet, which moves with any
    translation and therefore cancels it.

    A single shared foot cannot distinguish the two -- one point is carried the
    same way whether the body turned about it or slid past it -- so nothing is
    inferred from one, and the frame comes back as the identity.
    """
    old_contacts = {point.name: point for point in old_ground_contacts}
    new_contacts = {point.name: point for point in new_ground_contacts}
    shared = [name for name in old_contacts if name in new_contacts]

    if len(shared) < 2:
        return np.eye(4)

    old_xy = np.array([[old_contacts[n].x, old_contacts[n].y] for n in shared])
    new_xy = np.array([[new_contacts[n].x, new_contacts[n].y] for n in shared])

    # Referred to their own centroids, so only the turn is left to measure.
    old_xy = old_xy - old_xy.mean(axis=0)
    new_xy = new_xy - new_xy.mean(axis=0)

    # The angle that best carries the old spread onto the new one, over every
    # shared foot at once (the 2d case of Kabsch's rigid-fit).
    along = float(np.sum(old_xy * new_xy))
    across = float(
        np.sum(old_xy[:, 0] * new_xy[:, 1] - old_xy[:, 1] * new_xy[:, 0])
    )

    # Feet all sitting on their centroid: no spread to take a bearing from.
    if isclose(along, 0, abs_tol=1e-9) and isclose(across, 0, abs_tol=1e-9):
        return np.eye(4)

    return rotz(-degrees(atan2(across, along)))


def might_print_hexapod(hexapod, poses):
    if not PRINT_MODEL_ON_UPDATE:
        return

    print("█████████████████████████████")
    print("█ start: Hexapod Model      █")
    print("█████████████████████████████")

    print("............")
    print("...Dimensions")
    print("............")
    print(json.dumps(hexapod.dimensions, indent=4))

    print("............")
    print("...Vertices")
    print("............")
    pprint(hexapod.body.all_points)

    print("............")
    print("...Legs")
    print("............")
    for i, leg in enumerate(hexapod.legs):
        print(f"\nleg{i}_points = ")
        pprint(leg.all_points)

    print("............")
    print("...Poses")
    print("............")
    print(json.dumps(poses, indent=4))

    print("█████████████████████████████")
    print("█ end: Hexapod Model        █")
    print("█████████████████████████████")
