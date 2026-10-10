# The simulator's model of a hexapod: a hexagonal body with a three-joint leg
# at each vertex, posed by its joint angles (forward kinematics).
#
# The body is never moved: every point is in the body frame, with the cog at
# the origin. Placing the body in the world, and solving the joints for where
# the feet should go, is hexapod/pose_layers.py and hexapod/keyframes.py.
from math import atan2, degrees

from hexapod.linkage import Linkage
from hexapod.naming import LEG_NAMES
from hexapod.points import Vector


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
    __slots__ = ("f", "m", "s", "cog", "head", "vertices", "coxia_axes")

    def __init__(self, f, m, s, mount_angles=None):
        self.f = f
        self.m = m
        self.s = s

        self.cog = Vector(0, 0, 0, name="center-of-gravity")
        self.head = Vector(0, s, 0, name="head")
        # In the firmware's leg order; see hexapod/naming.py
        self.vertices = [
            Vector(f, s, 0, name=LEG_NAMES[0]),
            Vector(m, 0, 0, name=LEG_NAMES[1]),
            Vector(f, -s, 0, name=LEG_NAMES[2]),
            Vector(-f, s, 0, name=LEG_NAMES[3]),
            Vector(-m, 0, 0, name=LEG_NAMES[4]),
            Vector(-f, -s, 0, name=LEG_NAMES[5]),
        ]

        # Azimuth of each leg's coxia (joint 1) rotation axis, in the body frame.
        #
        # It has to match the physical robot's `legMountAngle`, the angle the
        # path generator solves IK around (hexapod/robot_config.py). Get it
        # wrong and each leg rotates about its own mount point, so the feet
        # the simulator draws are not where the robot puts them.
        #
        # A robot that reports its mount angles passes them in: Nougat's corner
        # legs are angled at 45 degrees while sitting at about 59. Without them
        # a leg is taken to point radially away from the cog, i.e. along its own
        # vertex -- right for Mochi and Macaroon, whose legMountAngle is exactly
        # atan2(legMountY, legMountX), and it follows edits to f, m and s.
        if mount_angles is not None:
            self.coxia_axes = tuple(float(angle) % 360 for angle in mount_angles)
        else:
            self.coxia_axes = tuple(
                degrees(atan2(vertex.y, vertex.x)) % 360 for vertex in self.vertices
            )


class VirtualHexapod:
    LEG_COUNT = 6
    __slots__ = ("body", "legs", "dimensions", "coxia", "femur", "tibia", "front", "side", "mid")

    def __init__(self, dimensions):
        self.dimensions = dimensions
        self.coxia = dimensions["coxia"]
        self.femur = dimensions["femur"]
        self.tibia = dimensions["tibia"]
        self.front = dimensions["front"]
        self.mid = dimensions["middle"]
        self.side = dimensions["side"]
        self.body = Hexagon(self.front, self.mid, self.side, dimensions.get("mount_angles"))
        self.legs = [
            Linkage(
                self.coxia,
                self.femur,
                self.tibia,
                coxia_axis=self.body.coxia_axes[i],
                new_origin=self.body.vertices[i],
                name=LEG_NAMES[i],
                id_number=i,
            )
            for i in range(VirtualHexapod.LEG_COUNT)
        ]

    def sum_of_dimensions(self):
        return self.front + self.mid + self.side + self.coxia + self.femur + self.tibia
