"""Capture the README screenshots.

    python tools/make_screenshots.py

Serves the app on a loopback port, drives headless Chrome over it once per
theme, and writes the results to docs/images/: app.png in the light theme and
app-dark.png in the dark one. The screenshots are therefore
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
# The app is one screen that never scrolls at this size: the window is the
# picture.
SHOTS = [
    ("app", "/", 1440, 900),
]

# Every shot is taken once per theme, with this suffix on the file name.
# The README picks between the two with a <picture> element, so readers see
# the one matching their GitHub colour mode.
THEMES = [("light", ""), ("dark", "-dark")]

# The app is captured showing off what it does instead of the neutral start-up
# pose: one foot lifted, under a body shifted and tilted off centre, all well
# within reach. The sliders are drawn from the pose in its store, so the pose
# goes there (posed_pose_stores()) rather than into the slider values.
POSED_LAYERS = {
    "body": {
        "percent_x": 0.15,
        "percent_y": -0.1,
        "percent_z": 0.2,
        "rot_x": 7.5,
        "rot_y": -6.0,
        "rot_z": 6.0,
    },
    "lifted_foot": (0, [15.0, 20.0, 35.0]),
}

# The animated hero on the README: one gait cycle, played in the workspace,
# each frame put in its store as feet moved from standby. The gait is
# generated for the robot the app is modelling, so it fits the body drawn in
# the plot.
GIF_MOTION = "walk_0"
GIF_FRAME_STEP = 2
GIF_WIDTH = 640
GIF_FRAME_MS = 90
# A GIF frame with less contrast than this share of the typical frame's shows
# an empty view, and is taken again, up to this many times.
EMPTY_FRAME_RATIO = 0.8
EMPTY_FRAME_RETRIES = 4


def posed_pose_stores():
    """Starting data for the pose stores, so the shot shows a sequence.

    The pose is POSED_LAYERS, and it is the second of three keyframes --
    standby, that pose, standby -- with the editor loaded from it. Built for
    whichever robot the app is modelling, since foot positions only fit the
    robot they were placed on.
    """
    import numpy as np

    from hexapod import keyframes as kf
    from hexapod import pose_layers as pl
    from hexapod.robot_link import ROBOT_LINK

    robot_config = ROBOT_LINK.robot_config
    standby = pl.standby_state()
    offsets = np.zeros((6, 3))
    leg, lift = POSED_LAYERS["lifted_foot"]
    offsets[leg] = lift
    posed = pl.make_state(POSED_LAYERS["body"], offsets)

    def keyframe(state, duration_ms=kf.DEFAULT_DURATION_MS):
        return kf.make_keyframe(pl.body_feet(state, robot_config), duration_ms, state)

    frames = [keyframe(standby), keyframe(posed, 600), keyframe(standby, 600)]
    return {
        "pose-state": {
            "robot": robot_config["name"],
            "state": posed,
            "feet": frames[1]["feet"],
            "seq": 0,
        },
        "pose-keyframes": {"robot": robot_config["name"], "keyframes": frames},
        "pose-selected-keyframe": 1,
    }


def apply_values(node, values, seen, prop="value"):
    """Set `prop` on every component in a Dash layout whose id we have."""
    node_id = getattr(node, "id", None)
    if isinstance(node_id, str) and node_id in values:
        setattr(node, prop, values[node_id])
        seen.add(node_id)

    children = getattr(node, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if hasattr(child, "_prop_names") or hasattr(child, "children"):
            apply_values(child, values, seen, prop)


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
    outer bounds, so a dark band elsewhere on the page -- the dock's
    readouts, say -- is not swept into the box.
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
            # The 3D views are WebGL; without a GPU, Chrome only draws them in
            # software when told it may.
            "--enable-unsafe-swiftshader",
            "--no-first-run",
            "--no-default-browser-check",
            "--hide-scrollbars",
            f"--force-device-scale-factor={SCALE}",
            f"--window-size={width},{height}",
            # Dash renders the page, then a round of callbacks draws the 3D
            # view. Virtual time lets that finish before the shot is taken.
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


def capture_gif(browser, profile_dir, layout, url, out_path):
    """Walk the hexapod through one gait cycle, one browser shot per frame."""
    from hexapod import keyframes as kf
    from hexapod import pose_layers as pl
    from hexapod.path_generator import generate_poses
    from hexapod.robot_link import ROBOT_LINK

    robot_config = ROBOT_LINK.robot_config
    poses = generate_poses(GIF_MOTION, robot_config)[::GIF_FRAME_STEP]
    box = None

    def shoot(number, pose, frame_dir):
        nonlocal box
        feet = kf.pose_to_feet(pose, robot_config)
        store = {
            "robot": robot_config["name"],
            "state": pl.from_feet(feet, robot_config),
            "feet": feet,
            "seq": number,
        }
        apply_values(layout, {"pose-state": store}, set(), prop="data")

        raw = os.path.join(frame_dir, f"{number:02d}.png")
        capture_raw(browser, profile_dir, url, raw, 1440, 900)
        image = Image.open(raw).convert("RGB")
        # The camera never moves, so the panel found in the first frame
        # frames every later one too and the GIF does not jitter.
        box = box or find_plot_box(image)
        if box:
            image = image.crop(box)
        height = round(image.height * GIF_WIDTH / image.width)
        return image.resize((GIF_WIDTH, height), Image.LANCZOS)

    def detail(image):
        return float(np.asarray(image.convert("L"), dtype=float).std())

    with tempfile.TemporaryDirectory() as frame_dir:
        frames = []
        for number, pose in enumerate(poses):
            frames.append(shoot(number, pose, frame_dir))
            print(f"    frame {number + 1}/{len(poses)}")

        # Now and then the view comes up before the robot is in it, and the
        # shot is of an empty monitor: much flatter than the frames around
        # it. Those are taken again.
        typical = float(np.median([detail(frame) for frame in frames]))
        for number, pose in enumerate(poses):
            for _ in range(EMPTY_FRAME_RETRIES):
                if detail(frames[number]) >= EMPTY_FRAME_RATIO * typical:
                    break
                print(f"    frame {number + 1} came out empty; taking it again")
                frames[number] = shoot(number, pose, frame_dir)

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
    # The app serves whatever theme is saved in the preferences file, so point
    # that at a throwaway file and switch it per capture. The real one, from
    # sessions on this machine, is neither read nor overwritten.
    prefs_dir = tempfile.mkdtemp(prefix="hexapod-link-shots-")
    from settings import PREFERENCES_ENV

    os.environ[PREFERENCES_ENV] = os.path.join(prefs_dir, "preferences.json")
    from hexapod.preferences import save_theme

    import hexapod_link  # noqa: E402  (imported late; it builds the whole app)
    from pages.workspace import WORKSPACE
    from widgets.pose_ui import (
        ANGLES_HUD_ID,
        POSE_RESET_BTN_ID,
        POSE_RESET_VIEW_BTN_ID,
    )

    seen = set()
    stores = posed_pose_stores()
    apply_values(WORKSPACE, stores, seen, prop="data")
    missing = sorted(set(stores) - seen)
    if missing:
        print(f"warning: no such store(s), left empty: {', '.join(missing)}")

    os.makedirs(OUT_DIR, exist_ok=True)
    server = make_server("127.0.0.1", PORT, hexapod_link.app.server, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    gif_only = "--gif-only" in sys.argv
    browser = find_browser()
    print(f"browser: {browser}")
    try:
        with tempfile.TemporaryDirectory() as profile_dir:
            for theme, suffix in ([] if gif_only else THEMES):
                save_theme(theme)
                for name, path, width, height in SHOTS:
                    file_name = f"{name}{suffix}.png"
                    out_path = os.path.join(OUT_DIR, file_name)
                    size = capture(
                        browser,
                        profile_dir,
                        f"http://127.0.0.1:{PORT}{path}",
                        out_path,
                        width,
                        height,
                    )
                    kb = os.path.getsize(out_path) // 1024
                    print(f"  docs/images/{file_name}  {size[0]}x{size[1]}  {kb} KB")

            if "--no-gif" in sys.argv:
                return
            # The GIF is cropped to the 3D view, which looks the same in both
            # themes; find_plot_box() needs the light page around it to find
            # the view's edges. What is laid over the view is hidden, so the
            # robot is all there is in the frame.
            save_theme("light")
            print(f"  rendering {GIF_MOTION} ...")
            out_path = os.path.join(OUT_DIR, "walk.gif")
            hidden = {"display": "none"}
            apply_values(
                WORKSPACE,
                {
                    ANGLES_HUD_ID: hidden,
                    POSE_RESET_BTN_ID: hidden,
                    POSE_RESET_VIEW_BTN_ID: hidden,
                },
                set(),
                prop="style",
            )
            size = capture_gif(
                browser,
                profile_dir,
                WORKSPACE,
                f"http://127.0.0.1:{PORT}/",
                out_path,
            )
            kb = os.path.getsize(out_path) // 1024
            print(f"  docs/images/walk.gif  {size[0]}x{size[1]}  {kb} KB")
    finally:
        server.shutdown()
        shutil.rmtree(prefs_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
