# What the 3D view draws, as plain data.
#
# The hexapod is drawn by a three.js view (assets/hexapod_view.js). This module
# turns a posed VirtualHexapod into the lists that view takes: the body
# outline, each leg's four points, the support polygon, and the body's own
# axes. It goes to the browser as JSON through a dcc.Store, so everything here
# is plain floats.
#
#   body      6 vertices, leg order (hexapod/naming.py)
#   head      the point marking the front
#   cog       centre of the body
#   legs      per leg: body contact, coxia, femur and foot tip points
#   feet      the six foot tips
#   support   the feet standing on the ground, in order around the polygon
#   axes      the body's own axes: [{"from", "to", "axis": "x"|"y"|"z"}]
#   ground    height of the floor
#   size      the robot's overall measure, which the camera is framed by
#   labels    each leg's name as the firmware gives it, shown on hover
#   colors    style_settings.py, so the view needs no colours of its own

from math import atan2

import numpy as np

from hexapod.naming import LEG_LABELS
from style_settings import (
    AXIS_X_COLOR,
    AXIS_Y_COLOR,
    AXIS_Z_COLOR,
    BODY_COLOR,
    BODY_MESH_COLOR,
    COG_COLOR,
    GRID_COLOR,
    GROUND_COLOR,
    HEAD_COLOR,
    JOINT_COLOR,
    LEG_COLOR,
    PAPER_BG_COLOR,
    SUPPORT_POLYGON_MESH_COLOR,
)

VIEWER_COLORS = {
    "background": PAPER_BG_COLOR,
    "ground": GROUND_COLOR,
    "grid": GRID_COLOR,
    "body": BODY_MESH_COLOR,
    "bodyOutline": BODY_COLOR,
    "leg": LEG_COLOR,
    "joint": JOINT_COLOR,
    "jointAccent": BODY_COLOR,
    "foot": SUPPORT_POLYGON_MESH_COLOR,
    "footSelected": HEAD_COLOR,
    "head": HEAD_COLOR,
    "cog": COG_COLOR,
    "support": SUPPORT_POLYGON_MESH_COLOR,
    "axisX": AXIS_X_COLOR,
    "axisY": AXIS_Y_COLOR,
    "axisZ": AXIS_Z_COLOR,
}


def xyz(point):
    """[x, y, z] to a thousandth, with -0.0 turned into 0.0.

    The scene ends up in a dcc.Store, which tells -0 from 0 although JSON does
    not; a -0 there can have a session store rewriting itself until React gives
    up. See hexapod/keyframes.py clean_feet().
    """
    return [round(point.x, 3) + 0.0, round(point.y, 3) + 0.0, round(point.z, 3) + 0.0]


def order_around_centre(points):
    """Points sorted by angle about their centroid.

    Enough to draw a hexapod's support polygon: its at most six feet sit on a
    convex ring.
    """
    if not points:
        return []
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return sorted(points, key=lambda p: atan2(p[1] - cy, p[0] - cx))


def hexapod_to_scene(hexapod, ground, support):
    """The scene for a posed hexapod, in its body frame.

    `support` is the list of [x, y, z] points the support polygon is drawn
    through, flat at `ground`.
    """
    legs = [[xyz(point) for point in leg.all_points] for leg in hexapod.legs]
    cog = xyz(hexapod.body.cog)
    support = [[p[0], p[1], ground + 0.0] for p in order_around_centre(support)]

    # The body's own axes from its centre, half the body's front length long.
    scale = float(hexapod.front / 2)
    axes = []
    for i, name in enumerate("xyz"):
        tip = list(cog)
        tip[i] = round(tip[i] + scale, 3) + 0.0
        axes.append({"from": cog, "to": tip, "axis": name})

    return {
        "body": [xyz(vertex) for vertex in hexapod.body.vertices],
        "head": xyz(hexapod.body.head),
        "cog": cog,
        "legs": legs,
        "feet": [leg[3] for leg in legs],
        "support": support,
        "axes": axes,
        "ground": ground + 0.0,
        "size": round(hexapod.sum_of_dimensions(), 3),
        "labels": list(LEG_LABELS),
        "colors": VIEWER_COLORS,
    }


def transform_scene(scene, rotation, shift):
    """The same scene moved rigidly: every point p goes to rotation @ p + shift.

    How the body-frame scene of a pose is drawn with the body placed in the
    world (hexapod/pose_layers.py). The floor height is only moved, not
    tilted, so set it afterwards when the rotation is not upright.
    """
    rotation = np.asarray(rotation, dtype=float)
    shift = np.asarray(shift, dtype=float)

    def move(point):
        moved = rotation @ np.asarray(point, dtype=float) + shift
        return [round(float(c), 3) + 0.0 for c in moved]

    return {
        **scene,
        "body": [move(p) for p in scene["body"]],
        "head": move(scene["head"]),
        "cog": move(scene["cog"]),
        "legs": [[move(p) for p in leg] for leg in scene["legs"]],
        "feet": [move(p) for p in scene["feet"]],
        "support": [move(p) for p in scene["support"]],
        "axes": [
            {**axis, "from": move(axis["from"]), "to": move(axis["to"])}
            for axis in scene["axes"]
        ],
        "ground": round(scene["ground"] + float(shift[2]), 3) + 0.0,
    }
