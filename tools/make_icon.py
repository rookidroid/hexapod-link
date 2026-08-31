"""Generate the Hexapod Link app icon.

Draws the icon procedurally at 8x and downsamples, so every output is
resolution-independent and reproducible:

    python tools/make_icon.py

Writes assets/icon.png (512 master), assets/app.ico (the icon PyInstaller
embeds in the Windows exe) and assets/favicon.ico (the browser tab icon).
Both .ico files are real multi-resolution ICOs.

The palette is the app's own light-industrial theme, kept in sync with
style_settings.py and assets/scifi.css by hand.
"""

import math
import os
import sys

from PIL import Image, ImageDraw

SUPERSAMPLE = 8
MASTER = 512
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
             (256, 256)]

W = MASTER * SUPERSAMPLE
CENTER = W / 2

PLATE = (17, 24, 39, 255)        # #111827 near-black CAD background
PLATE_EDGE = (75, 85, 99, 255)   # #4b5563 heavy grey border
BODY_FILL = (51, 65, 85, 255)    # #334155 industrial metal
BODY_LINE = (249, 115, 22, 255)  # #f97316 orange body outline
LEG = (203, 213, 225, 255)       # #cbd5e1 light metallic legs
JOINT = (249, 115, 22, 255)      # orange joints
COG = (34, 197, 94, 255)         # #22c55e green centre of gravity

# Every dimension below is a fraction of the icon's width, so the geometry
# survives any change to MASTER or SUPERSAMPLE.
PLATE_MARGIN = 0.023
PLATE_RADIUS = 0.185
PLATE_EDGE_WIDTH = 0.012
BODY_RADIUS = 0.208
BODY_LINE_WIDTH = 0.034
LEG_WIDTH = 0.034
COXA_RADIUS = 0.190
KNEE_RADIUS = 0.295
FOOT_RADIUS = 0.398
JOINT_RADIUS = 0.019
# The legs are swept a few degrees off radial so the robot reads as mid-gait
# rather than as a static asterisk.
KNEE_SKEW = 9
FOOT_SKEW = -2


def polar(radius, degrees):
    angle = math.radians(degrees)
    return CENTER + radius * math.cos(angle), CENTER - radius * math.sin(angle)


def disc(draw, xy, radius, fill):
    draw.ellipse([xy[0] - radius, xy[1] - radius,
                  xy[0] + radius, xy[1] + radius], fill=fill)


def draw_plate(draw):
    margin = PLATE_MARGIN * W
    draw.rounded_rectangle(
        [margin, margin, W - margin, W - margin],
        radius=PLATE_RADIUS * W,
        fill=PLATE,
        outline=PLATE_EDGE,
        width=int(PLATE_EDGE_WIDTH * W),
    )


def draw_legs(draw):
    for i in range(6):
        angle = 60 * i
        coxa = polar(COXA_RADIUS * W, angle)
        knee = polar(KNEE_RADIUS * W, angle + KNEE_SKEW)
        foot = polar(FOOT_RADIUS * W, angle + FOOT_SKEW)
        draw.line([coxa, knee, foot], fill=LEG,
                  width=int(LEG_WIDTH * W), joint="curve")
        disc(draw, knee, JOINT_RADIUS * W, JOINT)
        disc(draw, foot, JOINT_RADIUS * 0.85 * W, JOINT)


def draw_body(draw):
    hexagon = [polar(BODY_RADIUS * W, 60 * i) for i in range(6)]
    draw.polygon(hexagon, fill=BODY_FILL)
    draw.line(hexagon + hexagon[:1], fill=BODY_LINE,
              width=int(BODY_LINE_WIDTH * W), joint="curve")


def draw_link_signal(draw):
    """The two arcs and the dot below them: the 'Link' half of the name."""
    for radius in (0.105, 0.152):
        box = [CENTER - radius * W, CENTER - radius * W,
               CENTER + radius * W, CENTER + radius * W]
        # Pillow measures arcs clockwise from 3 o'clock; negate to centre the
        # span on 12 o'clock.
        draw.arc(box, start=-140, end=-40, fill=COG, width=int(0.030 * W))
    disc(draw, (CENTER, CENTER + 0.038 * W), 0.040 * W, COG)


def render():
    image = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw_plate(draw)
    draw_legs(draw)
    draw_body(draw)
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
