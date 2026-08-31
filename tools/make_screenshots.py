"""Capture the README screenshots.

    python tools/make_screenshots.py

Serves the app on a loopback port, drives headless Chrome over it once per
page, and writes the results to docs/images/. The screenshots are therefore
always of the current UI -- rerun this after a theme or layout change rather
than editing the PNGs by hand.

Pass --no-gif to skip the animation, or --gif-only to redo just that.

Chrome (or Edge) has to be installed; set CHROME to a browser executable to
override the search. Nothing here is imported by the app itself.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import threading

import numpy as np
from PIL import Image
from werkzeug.serving import make_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, "docs", "images")
PORT = 8099
# Captured at 2x and downsampled, which is what makes text in the shots crisp
# on the ~900 px column GitHub renders a README into.
SCALE = 2
OUTPUT_WIDTH = 1600
# Chrome renders the whole window and the page never scrolls, so each height
# below is just "tall enough for that page's control panel".
PAGES = [
    ("home", "/", 1400, 1700),
    ("kinematics", "/kinematics", 1400, 1000),
    ("inverse-kinematics", "/inverse-kinematics", 1400, 1000),
    ("leg-patterns", "/leg-patterns", 1400, 1000),
    ("motion", "/motion-animations", 1400, 1150),
]

# Widget values applied before serving, so each page is captured showing off
# what it does instead of the neutral start-up pose. Keyed by widget id, which
# is also what the page callbacks key off, so these stay valid as long as the
# callbacks do; ids that no longer exist are skipped.
POSED_WIDGETS = {
    # Kinematics: a tripod stance, three legs planted and three lifted.
    "widget-right-front-coxia": 25.0,
    "widget-right-front-femur": 40.0,
    "widget-right-front-tibia": -55.0,
    "widget-right-middle-coxia": 0.0,
    "widget-right-middle-femur": 5.0,
    "widget-right-middle-tibia": -25.0,
    "widget-right-back-coxia": -25.0,
    "widget-right-back-femur": 40.0,
    "widget-right-back-tibia": -55.0,
    "widget-left-front-coxia": -25.0,
    "widget-left-front-femur": 5.0,
    "widget-left-front-tibia": -25.0,
    "widget-left-middle-coxia": 0.0,
    "widget-left-middle-femur": 40.0,
    "widget-left-middle-tibia": -55.0,
    "widget-left-back-coxia": 25.0,
    "widget-left-back-femur": 5.0,
    "widget-left-back-tibia": -25.0,
    # Inverse kinematics: body shifted and tilted off centre, well inside what
    # the solver can reach so the shot shows a solved pose and not an error.
    "widget-start-hip-stance": 12.0,
    "widget-start-leg-stance": 45.0,
    "widget-percent-x": 0.15,
    "widget-percent-y": -0.1,
    "widget-percent-z": 0.2,
    "widget-rot-x": 10.5,
    "widget-rot-y": -9.0,
    "widget-rot-z": 6.0,
    # Leg patterns: all six legs swept together.
    "widget-alpha": 0.0,
    "widget-beta": 33.0,
    "widget-gamma": -45.0,
}

# The animated hero on the README: one gait cycle, played on the kinematics
# page because that page takes its pose straight from the widget values.
GIF_MOTION = "walk_0"
GIF_PROFILE = "mochi"
GIF_FRAME_STEP = 2
GIF_WIDTH = 640
GIF_FRAME_MS = 90


def apply_values(node, values, seen):
    """Set .value on every component in a Dash layout whose id we have."""
    node_id = getattr(node, "id", None)
    if isinstance(node_id, str) and node_id in values:
        node.value = values[node_id]
        seen.add(node_id)

    children = getattr(node, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if hasattr(child, "_prop_names") or hasattr(child, "children"):
            apply_values(child, values, seen)


def crop_trailing_background(image, margin=40):
    """Trim the dead space below a page that is shorter than the window."""
    pixels = np.asarray(image.convert("RGB"), dtype=np.int16)
    background = pixels[-1, 5]
    differs = (np.abs(pixels - background).sum(axis=2) > 12).any(axis=1)
    if not differs.any():
        return image
    last = int(np.flatnonzero(differs)[-1])
    bottom = min(image.height, last + margin)
    return image.crop((0, 0, image.width, bottom))


def longest_run(flags):
    """Start and end of the longest stretch of True in a boolean array."""
    best = run_start = None
    best_length = current = 0
    for index, flag in enumerate(flags):
        if flag:
            if current == 0:
                run_start = index
            current += 1
            if current > best_length:
                best_length, best = current, (run_start, index)
        else:
            current = 0
    return best


def find_plot_box(image, dark_level=70, coverage=0.25):
    """Bounding box of the dark 3D plot panel inside a page screenshot.

    Takes the longest stretch of dark rows and columns rather than their
    outer bounds, so the navbar's dark hazard stripe -- also full width and
    also dark -- is not swept into the box.
    """
    dark = np.asarray(image.convert("L")) < dark_level
    rows = longest_run(dark.mean(axis=1) > coverage)
    if rows is None:
        return None
    top, bottom = rows
    cols = longest_run(dark[top:bottom + 1].mean(axis=0) > coverage)
    if cols is None:
        return None
    return cols[0], top, cols[1] + 1, bottom + 1


def find_browser():
    override = os.environ.get("CHROME")
    if override:
        return override
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    for name in ("google-chrome", "chromium", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    sys.exit("no Chrome/Chromium found; set CHROME to a browser executable")


def capture_raw(browser, profile_dir, url, out_path, width, height):
    subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--hide-scrollbars",
            f"--force-device-scale-factor={SCALE}",
            f"--window-size={width},{height}",
            # Dash renders the page, then a round of callbacks draws the
            # figure. Virtual time lets that finish before the shot is taken.
            "--virtual-time-budget=15000",
            f"--user-data-dir={profile_dir}",
            f"--screenshot={out_path}",
            url,
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if not os.path.exists(out_path):
        sys.exit(f"browser wrote no screenshot for {url}")


def capture(browser, profile_dir, url, out_path, width, height):
    capture_raw(browser, profile_dir, url, out_path, width, height)
    image = crop_trailing_background(Image.open(out_path))
    scaled_height = round(image.height * OUTPUT_WIDTH / image.width)
    image.convert("RGB").resize(
        (OUTPUT_WIDTH, scaled_height), Image.LANCZOS
    ).save(out_path, optimize=True)
    return OUTPUT_WIDTH, scaled_height


def capture_gif(browser, profile_dir, layouts, url, out_path):
    """Walk the hexapod through one gait cycle, one browser shot per frame."""
    from hexapod.path_generator import generate_poses

    poses = generate_poses(GIF_MOTION, GIF_PROFILE)[::GIF_FRAME_STEP]
    frames = []
    box = None
    with tempfile.TemporaryDirectory() as frame_dir:
        for number, pose in enumerate(poses):
            values = {
                f"widget-{leg['name']}-{joint}": round(float(leg[joint]), 2)
                for leg in pose.values()
                for joint in ("coxia", "femur", "tibia")
            }
            for layout in layouts:
                apply_values(layout, values, set())

            raw = os.path.join(frame_dir, f"{number:02d}.png")
            capture_raw(browser, profile_dir, url, raw, 1400, 1000)
            image = Image.open(raw).convert("RGB")
            # The camera never moves, so the panel found in the first frame
            # frames every later one too and the GIF does not jitter.
            box = box or find_plot_box(image)
            if box:
                image = image.crop(box)
            height = round(image.height * GIF_WIDTH / image.width)
            frames.append(image.resize((GIF_WIDTH, height), Image.LANCZOS))
            print(f"    frame {number + 1}/{len(poses)}")

    # One shared palette across frames, otherwise each frame quantises
    # differently and the background shimmers.
    palette = frames[0].quantize(colors=128, method=Image.MEDIANCUT)
    frames = [frame.quantize(palette=palette, dither=Image.NONE)
              for frame in frames]
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=GIF_FRAME_MS,
        loop=0,
        optimize=True,
    )
    return frames[0].size


def main():
    import index  # noqa: E402  (imported late; it builds the whole app)

    seen = set()
    for layout in index.PAGES.values():
        apply_values(layout, POSED_WIDGETS, seen)
    missing = sorted(set(POSED_WIDGETS) - seen)
    if missing:
        print(f"warning: no such widget(s), left at default: {', '.join(missing)}")

    os.makedirs(OUT_DIR, exist_ok=True)
    server = make_server("127.0.0.1", PORT, index.app.server, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    gif_only = "--gif-only" in sys.argv
    browser = find_browser()
    print(f"browser: {browser}")
    try:
        with tempfile.TemporaryDirectory() as profile_dir:
            for name, path, width, height in ([] if gif_only else PAGES):
                out_path = os.path.join(OUT_DIR, f"{name}.png")
                size = capture(
                    browser,
                    profile_dir,
                    f"http://127.0.0.1:{PORT}{path}",
                    out_path,
                    width,
                    height,
                )
                kb = os.path.getsize(out_path) // 1024
                print(f"  docs/images/{name}.png  {size[0]}x{size[1]}  {kb} KB")

            if "--no-gif" in sys.argv:
                return
            print(f"  rendering {GIF_MOTION} ...")
            out_path = os.path.join(OUT_DIR, "walk.gif")
            size = capture_gif(
                browser,
                profile_dir,
                list(index.PAGES.values()),
                f"http://127.0.0.1:{PORT}/kinematics",
                out_path,
            )
            kb = os.path.getsize(out_path) // 1024
            print(f"  docs/images/walk.gif  {size[0]}x{size[1]}  {kb} KB")
    finally:
        server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
