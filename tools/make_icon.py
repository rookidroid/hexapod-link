"""Generate the Hexapod Link app icon.

Draws the icon procedurally at 8x and downsamples, so every output is
resolution-independent and reproducible:

    python tools/make_icon.py

Writes assets/icon.png (512 master), assets/app.ico (the icon PyInstaller
embeds in the Windows exe) and assets/favicon.ico (the browser tab icon).
Both .ico files are real multi-resolution ICOs.

The artwork follows the hexapod project's own logo (images/hexapod-logo.svg
in rookidroid/hexapod): the same chamfered navy badge, the robot seen from
above and turned 45 degrees, in the RX-78-2 white, blue, red and yellow.
Only the hub differs -- where the hexapod has a yellow dot, Hexapod Link has
a yellow signal, the 'Link' half of the name. The geometry below is copied
from that SVG by hand, in its 512-unit coordinates, so keep the two in step.
"""

import math
import os
import sys

from PIL import Image, ImageDraw

SUPERSAMPLE = 8
MASTER = 512
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
             (256, 256)]

# The hexapod logo's palette, shared with its web UI
INK = (27, 42, 74, 255)        # #1b2a4a navy outlines and badge
ARMOR = (255, 255, 255, 255)   # #ffffff white armour
BLUE = (29, 79, 163, 255)      # #1d4fa3 knees and deck
RED = (214, 40, 40, 255)       # #d62828 feet
YELLOW = (242, 183, 5, 255)    # #f2b705 signal

# Everything below is in the SVG's 512-unit space; px() scales it to pixels.
SCALE = MASTER * SUPERSAMPLE / 512
INK_WIDTH = 7

# Badge: navy plate chamfered top-right and bottom-left
BADGE = [(10, 10), (430, 10), (502, 82), (502, 502), (82, 502), (10, 430)]

# The robot is drawn in its own frame, then turned and shrunk onto the badge
ROBOT_CENTER = (256, 256)
ROBOT_ROTATION = 45
ROBOT_SCALE = 0.94

# One leg, mounted at the origin and reaching along +x
COXA_OFFSET = 100
KNEE_OFFSET = 72
FEMUR = [(-10, -22), (56, -18), (74, 0), (56, 18), (-10, 22)]
TIBIA = [(0, -20), (50, -14), (76, 0), (50, 14), (0, 20)]
TIBIA_TIP = [(53.5, -12.5), (72, 0), (53.5, 12.5)]
KNEE_RADIUS = 17
# Front and rear knees bend the tibia away from the middle
TIBIA_BEND = {0: 0, 60: 20, 120: -20, 180: 0, 240: 20, 300: -20}

TORSO_RADIUS = 106
DECK_RADIUS = 70

# The signal stays upright on the badge, so it is laid out in badge units
# around the robot's centre: a dot with two arcs fanning up from it.
SIGNAL_DOT = (0, 15)
SIGNAL_DOT_RADIUS = 12
SIGNAL_ARCS = (27, 44)
SIGNAL_ARC_WIDTH = 10
SIGNAL_SPAN = 90


def px(value):
    return value * SCALE


def rotate(point, degrees):
    """Rotate like SVG's rotate(): clockwise on screen, since y points down."""
    angle = math.radians(degrees)
    x, y = point
    return (x * math.cos(angle) - y * math.sin(angle),
            x * math.sin(angle) + y * math.cos(angle))


def to_badge(point):
    """Map a point from the robot's frame into pixels on the badge."""
    x, y = rotate(point, ROBOT_ROTATION)
    return (px(ROBOT_CENTER[0] + ROBOT_SCALE * x),
            px(ROBOT_CENTER[1] + ROBOT_SCALE * y))


def disc(draw, xy, radius, fill):
    draw.ellipse([xy[0] - radius, xy[1] - radius,
                  xy[0] + radius, xy[1] + radius], fill=fill)


def inked_polygon(draw, points, fill):
    """Fill a polygon, then stroke it in ink with round joins like the SVG."""
    width = px(INK_WIDTH * ROBOT_SCALE)
    draw.polygon(points, fill=fill)
    draw.line(points + points[:1], fill=INK, width=round(width),
              joint="curve")
    # Pillow does not join the line's two ends, so round every corner here
    for point in points:
        disc(draw, point, width / 2, INK)


def inked_circle(draw, center, radius, fill):
    width = px(INK_WIDTH * ROBOT_SCALE)
    disc(draw, center, px(radius * ROBOT_SCALE) + width / 2, INK)
    disc(draw, center, px(radius * ROBOT_SCALE) - width / 2, fill)


def hexagon(radius):
    return [(radius * math.cos(math.radians(60 * i)),
             radius * math.sin(math.radians(60 * i))) for i in range(6)]


def draw_badge(draw):
    draw.polygon([(px(x), px(y)) for x, y in BADGE], fill=INK)


def draw_legs(draw):
    for heading, bend in TIBIA_BEND.items():
        def place(points, knee_bend=None, heading=heading):
            """Leg frame to badge; with a knee_bend, from the knee's frame."""
            placed = []
            for point in points:
                if knee_bend is not None:
                    x, y = rotate(point, knee_bend)
                    point = (x + KNEE_OFFSET, y)
                x, y = rotate((point[0] + COXA_OFFSET, point[1]), heading)
                placed.append(to_badge((x, y)))
            return placed

        inked_polygon(draw, place(FEMUR), ARMOR)
        inked_polygon(draw, place(TIBIA, bend), ARMOR)
        draw.polygon(place(TIBIA_TIP, bend), fill=RED)
        inked_circle(draw, place([(0, 0)], 0)[0], KNEE_RADIUS, BLUE)


def draw_torso(draw):
    inked_polygon(draw, [to_badge(p) for p in hexagon(TORSO_RADIUS)], ARMOR)
    inked_polygon(draw, [to_badge(p) for p in hexagon(DECK_RADIUS)], BLUE)


def draw_link_signal(draw):
    """The dot and the two arcs above it: the 'Link' half of the name."""
    cx = px(ROBOT_CENTER[0] + SIGNAL_DOT[0])
    cy = px(ROBOT_CENTER[1] + SIGNAL_DOT[1])
    width = px(SIGNAL_ARC_WIDTH)
    # Pillow measures arcs clockwise from 3 o'clock, so 12 o'clock is -90
    start, end = -90 - SIGNAL_SPAN / 2, -90 + SIGNAL_SPAN / 2
    for radius in SIGNAL_ARCS:
        # The box is the arc's outer edge; centre the stroke on the radius
        outer = px(radius) + width / 2
        draw.arc([cx - outer, cy - outer, cx + outer, cy + outer],
                 start=start, end=end, fill=YELLOW, width=round(width))
        # Round caps, to match the ink's round joins
        for degrees in (start, end):
            angle = math.radians(degrees)
            disc(draw, (cx + px(radius) * math.cos(angle),
                        cy + px(radius) * math.sin(angle)), width / 2, YELLOW)
    disc(draw, (cx, cy), px(SIGNAL_DOT_RADIUS), YELLOW)


def render():
    size = MASTER * SUPERSAMPLE
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw_badge(draw)
    draw_legs(draw)
    draw_torso(draw)
    draw_link_signal(draw)
    return image.resize((MASTER, MASTER), Image.LANCZOS)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets = os.path.join(root, "assets")
    icon = render()

    master_path = os.path.join(assets, "icon.png")
    icon.save(master_path)

    # Pillow downsamples each ICO frame itself, but LANCZOS from the master
    # keeps the small sizes noticeably crisper.
    frames = [icon.resize(size, Image.LANCZOS) for size in ICO_SIZES]
    for name in ("app.ico", "favicon.ico"):
        icon.save(os.path.join(assets, name), format="ICO", sizes=ICO_SIZES,
                  append_images=frames)

    print(f"wrote {master_path}, assets/app.ico, assets/favicon.ico")


if __name__ == "__main__":
    sys.exit(main())
