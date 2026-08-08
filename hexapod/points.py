# This module contains the Vector class
# and functions for manipulating vectors
# and finding properties and relationships of vectors
# computing reference frames
from math import sqrt, radians, sin, cos, degrees, acos
import numpy as np

from settings import DEBUG_MODE


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

    def update_point_wrt(self, reference_frame, z=0):
        p = np.array([self.x, self.y, self.z, 1])
        p = np.matmul(reference_frame, p)
        self.x = p[0]
        self.y = p[1]
        self.z = p[2] + z

    def move_xyz(self, x, y, z):
        self.x += x
        self.y += y
        self.z += z

    @property
    def vec(self):
        return self.x, self.y, self.z

    def __repr__(self):
        s = f"Vector(x={self.x:>+8.2f}, y={self.y:>+8.2f}, z={self.z:>+8.2f}, name='{self.name}')"
        return s

    def __str__(self):
        return repr(self)

    def __eq__(self, other, percent_tol=0.0075):
        if not isinstance(other, Vector):
            return False

        tol = length(self) * percent_tol
        equal_val = np.allclose(self.vec, other.vec, atol=tol)
        equal_name = self.name == other.name
        return equal_val and equal_name


def is_triangle(a, b, c):
    return (a + b > c) and (a + c > b) and (b + c > a)


# https://www.maplesoft.com/support/help/Maple/view.aspx?path=MathApps%2FProjectionOfVectorOntoPlane
# u is the vector, n is the plane normal
def project_vector_onto_plane(u, n):
    s = dot(u, n) / dot(n, n)
    temporary_vector = scalar_multiply(n, s)
    return subtract_vectors(u, temporary_vector)


def might_print_angle_between_error(a, b):
    if DEBUG_MODE:
        print(
            f"❗❗❗ERROR: angle_between({a}, {b}) is NAN\
        ... One of the might be a zero vector\
        ... the vectors might be pointing at the same direction or\
        ... something else entirely. 🤔"
        )


def acos_degrees(ratio):
    """acos in degrees, tolerant of a ratio that drifts a hair out of [-1, 1].

    Every ratio passed here is a cosine recovered from a dot product or from the
    law of cosines, so 1.0000000000000002 means "these are parallel", not "this
    is impossible". math.acos raises on it, and since nothing caught that, two
    vectors happening to line up exactly would sink an otherwise ordinary pose
    with a bare "math domain error". Clamping reads such a ratio as the 0 or 180
    degrees it was rounding away from.
    """
    return degrees(acos(min(1.0, max(-1.0, ratio))))


def angle_between(a, b):
    # returns the shortest angle between two vectors
    denominator = sqrt(dot(a, a) * dot(b, b))

    # A zero-length vector has no direction to measure against.
    if denominator == 0.0:
        might_print_angle_between_error(a, b)
        return 0.0

    return acos_degrees(dot(a, b) / denominator)


def angle_opposite_of_last_side(a, b, c):
    # The angle between sides a and b of a triangle, opposite side c.
    if a == 0 or b == 0:
        return 0.0

    return acos_degrees((a * a + b * b - c * c) / (2 * a * b))


# Check if angle from vector a to b about normal n is positive
# Rotating from vector a to is moving into a conter clockwise direction
def is_counter_clockwise(a, b, n):
    return dot(a, cross(b, n)) > 0


def _half_turn_frame(a):
    """A half turn about some axis perpendicular to a, which reverses it."""
    # Any perpendicular axis will do; cross a with whichever of x or y it is
    # not parallel to.
    axis = cross(a, Vector(1, 0, 0))
    if length(axis) == 0.0:
        axis = cross(a, Vector(0, 1, 0))
    k = get_unit_vector(axis)

    # Rodrigues at theta = 180 degrees collapses to 2*k*k' - I.
    kv = np.array([k.x, k.y, k.z])
    r = 2 * np.outer(kv, kv) - np.eye(3)
    r = np.hstack((r, [[0], [0], [0]]))
    return np.vstack((r, [0, 0, 0, 1]))


# https://math.stackexchange.com/questions/180418/calculate-rotation-matrix-to-align-vector-a-to-vector-b-in-3d
def frame_to_align_vector_a_to_b(a, b):
    v = cross(a, b)
    s = length(v)
    c = dot(a, b)

    # The cross product vanishes both when a and b already point the same way
    # and when they point exactly opposite, and the formula below divides by s
    # so it cannot tell them apart. Returning the identity for the opposite case
    # meant "align these" quietly left them reversed -- which is how a ground
    # normal pointing into the floor used to survive being stood up.
    if s == 0.0:
        if c >= 0:
            return np.eye(4)
        return _half_turn_frame(a)

    i = np.eye(3)  # Identity matrix 3x3

    # skew symmetric cross product
    vx = skew(v)
    d = (1 - c) / (s * s)
    r = i + vx + np.matmul(vx, vx) * d

    # r00 r01 r02 0
    # r10 r11 r12 0
    # r20 r21 r22 0
    #  0   0   0  1
    r = np.hstack((r, [[0], [0], [0]]))
    r = np.vstack((r, [0, 0, 0, 1]))
    return r


# rotate about y, translate in x
def frame_yrotate_xtranslate(theta, x):
    c, s = _return_sin_and_cos(theta)

    return np.array([[c, 0, s, x], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]])


# rotate about z, translate in x and y
def frame_zrotate_xytranslate(theta, x, y):
    c, s = _return_sin_and_cos(theta)

    return np.array([[c, -s, 0, x], [s, c, 0, y], [0, 0, 1, 0], [0, 0, 0, 1]])


def frame_rotxyz(a, b, c):
    rx = rotx(a)
    ry = roty(b)
    rz = rotz(c)
    rxy = np.matmul(rx, ry)
    rxyz = np.matmul(rxy, rz)
    return rxyz


def rotx(theta):
    c, s = _return_sin_and_cos(theta)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]])


def roty(theta):
    c, s = _return_sin_and_cos(theta)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]])


def rotz(theta):
    c, s = _return_sin_and_cos(theta)
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])


def _return_sin_and_cos(theta):
    d = radians(theta)
    c = cos(d)
    s = sin(d)
    return c, s


# get vector pointing from point a to point b
def vector_from_to(a, b):
    return Vector(b.x - a.x, b.y - a.y, b.z - a.z)


def scale(v, d):
    return Vector(v.x / d, v.y / d, v.z / d)


def dot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z


def cross(a, b):
    x = a.y * b.z - a.z * b.y
    y = a.z * b.x - a.x * b.z
    z = a.x * b.y - a.y * b.x
    return Vector(x, y, z)


def length(v):
    return sqrt(dot(v, v))


def add_vectors(a, b):
    return Vector(a.x + b.x, a.y + b.y, a.z + b.z)


def subtract_vectors(a, b):
    return Vector(a.x - b.x, a.y - b.y, a.z - b.z)


def scalar_multiply(p, s):
    return Vector(s * p.x, s * p.y, s * p.z)


def get_unit_vector(v):
    return scale(v, length(v))


def get_normal_given_three_points(a, b, c):
    """
    Get the unit normal vector to the
    plane defined by the points a, b, c.
    """
    ab = vector_from_to(a, b)
    ac = vector_from_to(a, c)
    v = cross(ab, ac)
    v = scale(v, length(v))
    return v


def skew(p):
    return np.array([[0, -p.z, p.y], [p.z, 0, -p.x], [-p.y, p.x, 0]])
