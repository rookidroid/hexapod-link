# What the 3D view draws, as plain data.
#
# Every page draws the hexapod with the same three.js view
# (assets/hexapod_view.js). This module turns a posed VirtualHexapod into the
# lists that view takes: the body outline, each leg's four points, the support
# polygon, and the body's own axes. It goes to the browser as JSON through a
# dcc.Store, so everything here is plain floats.
#
#   body      6 vertices, leg order (hexapod/naming.py)
#   head      the point marking the front
#   cog       centre of the body
#   legs      per leg: body contact, coxia, femur and foot tip points
#   feet      the six foot tips
#   support   the feet standing on the ground, in order around the polygon
#   axes      [{"from", "to", "axis": "x"|"y"|"z", "world": bool}]
#   ground    height of the floor
#   size      the robot's overall measure, which the camera is framed by
#   labels    each leg's name as the firmware gives it, shown on hover
#   colors    style_settings.py, so the view needs no colours of its own

from math import atan2

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
    "joint": BODY_COLOR,
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


def hexapod_to_scene(hexapod, ground=0.0, support=None, world_axes=True):
    """The scene for a posed hexapod, in whatever frame it was left in.

    `support` is the list of [x, y, z] points the support polygon is drawn
    through; by default the hexapod's own ground contacts, which is what a
    hexapod settled by VirtualHexapod.update() stands on. The polygon is drawn
    flat at `ground`.
    """
    legs = [[xyz(point) for point in leg.all_points] for leg in hexapod.legs]
    cog = xyz(hexapod.body.cog)

    if support is None:
        support = [xyz(point) for point in hexapod.ground_contacts]
    support = [[p[0], p[1], ground + 0.0] for p in order_around_centre(support)]

    # The body's own axes from its centre, and the world's at the origin, both
    # half the body's front length long.
    scale = hexapod.front / 2
    axes = []
    for name, axis in (("x", hexapod.x_axis), ("y", hexapod.y_axis), ("z", hexapod.z_axis)):
        tip = [cog[0] + scale * axis.x, cog[1] + scale * axis.y, cog[2] + scale * axis.z]
        tip = [round(c, 3) + 0.0 for c in tip]
        axes.append({"from": cog, "to": tip, "axis": name, "world": False})
    if world_axes:
        for i, name in enumerate("xyz"):
            tip = [0.0, 0.0, 0.0]
            tip[i] = float(scale)
            axes.append({"from": [0.0, 0.0, 0.0], "to": tip, "axis": name, "world": True})

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
