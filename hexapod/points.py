# Points, and the homogeneous (4x4) frames that move them.
from math import radians, sin, cos

import numpy as np


class Vector:
    __slots__ = ("x", "y", "z", "name")

    def __init__(self, x, y, z, name=None):
        self.x = x
        self.y = y
        self.z = z
        self.name = name

    def get_point_wrt(self, reference_frame, name=None):
        """
        Given frame_ab which is the pose of frame_b wrt frame_a
        and that this point is defined wrt to frame_b
        Return point defined wrt to frame a
        """
        p = np.array([self.x, self.y, self.z, 1])
        p = np.matmul(reference_frame, p)
        return Vector(p[0], p[1], p[2], name)

    def __repr__(self):
        return f"Vector(x={self.x:>+8.2f}, y={self.y:>+8.2f}, z={self.z:>+8.2f}, name='{self.name}')"


# rotate about y, translate in x
def frame_yrotate_xtranslate(theta, x):
    c, s = _cos_and_sin(theta)
    return np.array([[c, 0, s, x], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]])


# rotate about z, translate in x and y
def frame_zrotate_xytranslate(theta, x, y):
    c, s = _cos_and_sin(theta)
    return np.array([[c, -s, 0, x], [s, c, 0, y], [0, 0, 1, 0], [0, 0, 0, 1]])


def frame_rotxyz(a, b, c):
    """Rotations about x, y and z, in degrees, applied as Rx @ Ry @ Rz."""
    return rotx(a) @ roty(b) @ rotz(c)


def rotx(theta):
    c, s = _cos_and_sin(theta)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]])


def roty(theta):
    c, s = _cos_and_sin(theta)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]])


def rotz(theta):
    c, s = _cos_and_sin(theta)
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])


def _cos_and_sin(theta):
    d = radians(theta)
    return cos(d), sin(d)
