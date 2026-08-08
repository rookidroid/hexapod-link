from math import isclose
from hexapod.points import (
    Vector,
    dot,
    cross,
    vector_from_to,
    get_normal_given_three_points,
    scalar_multiply,
)

# Prioritize legs that are not adjacent to each other
SOME_LEG_TRIOS = [
    (1, 0, 4),
    (1, 0, 5),
    (1, 3, 4),
    (1, 3, 5),
    (1, 3, 2),
    (1, 4, 5),
    (1, 4, 2),
    (0, 3, 5),
    (0, 3, 2),
    (0, 4, 5),
    (0, 4, 2),
    (0, 5, 2),
    (3, 4, 2),
    (3, 5, 2),
]

ADJACENT_LEG_TRIOS = [
    (1, 0, 3),
    (0, 3, 4),
    (3, 4, 5),
    (4, 5, 2),
    (1, 5, 2),
    (1, 0, 2),
]

LEG_TRIOS = SOME_LEG_TRIOS + ADJACENT_LEG_TRIOS


# math.stackexchange.com/questions/544946/
#   determine-if-projection-of-3d-point-onto-plane-is-within-a-triangle
# gamedev.stackexchange.com/questions/23743/
#   whats-the-most-efficient-way-to-find-barycentric-coordinates
# en.wikipedia.org/wiki/Barycentric_coordinate_system
def is_stable(p1, p2, p3, tol=0.001):
    """
    Determines stability of the pose.
    Determine if projection of 3D point p
    onto the plane defined by p1, p2, p3
    is within a triangle defined by p1, p2, p3.
    """
    p = Vector(0, 0, 0)
    u = vector_from_to(p1, p2)
    v = vector_from_to(p1, p3)
    n = cross(u, v)
    w = vector_from_to(p1, p)
    n2 = dot(n, n)
    beta = dot(cross(u, w), n) / n2
    gamma = dot(cross(w, v), n) / n2
    alpha = 1 - gamma - beta
    # then coordinate of the projected point (p_) of point p
    # p_ = alpha * p1 + beta * p2 + gamma * p3
    min_val = -tol
    max_val = 1 + tol
    cond1 = min_val <= alpha <= max_val
    cond2 = min_val <= beta <= max_val
    cond3 = min_val <= gamma <= max_val
    return cond1 and cond2 and cond3


def ground_plane_properties(p0, p1, p2):
    """The plane through three contact points, normal oriented up, and the
    height of the cog above it.

    Callers rely on the normal pointing up out of the ground: it is what makes
    the height below the cog's clearance, what makes is_lower() mean lower, and
    what the frame that stands the robot up is expecting. The trio tables were
    written assuming their listed order delivers that, but the order fixes only
    the winding, and the winding is not fixed: enough hip stance swings a leg
    past its neighbour, reorders the feet around the body, and flips every
    normal at once.

    Up is the body's own +z, and it cannot be read off the cog instead. The cog
    clears the plane through the robot's highest joints just as happily as the
    one through its feet -- from underneath -- and taking that plane for the
    ground hangs the robot off its own knees.
    """
    n = get_normal_given_three_points(p0, p1, p2)

    if n.z < 0:
        n = scalar_multiply(n, -1)

    # p0 is the vector from the cog (the origin) to a point on the plane, so
    # -dot(n, p0) is how far the cog sits above the plane, measured along n.
    # With n pointing up, a plane above the robot gives this a negative value,
    # and is_lower() then correctly reports the points beneath it.
    #
    #  cog *  ^ (n) ----
    #      \  |        |
    #       \ |     height
    #        \|        |
    #         V p0 -----
    return n, -dot(n, p0)


def is_lower(point, height, n, tol=1):
    _height = -dot(n, point)
    return _height > height + tol


def find_legs_on_ground(legs, n, height, tol=1):
    legs_on_ground = []
    for leg in legs:
        for point in reversed(leg.all_points[1:]):
            _height = -dot(n, point)
            if isclose(height, _height, abs_tol=tol):
                legs_on_ground.append(leg)
                break

    return legs_on_ground
