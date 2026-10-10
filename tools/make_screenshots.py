"""Capture the README's screenshots and animations.

    python tools/make_screenshots.py              # all of them
    python tools/make_screenshots.py app pose     # only those

Serves the app on a loopback port, connects it to a stand-in robot
(tools/fake_robot.py) so that nothing in it is greyed out, and drives it in a
headless Chrome the way a person would -- picking the body, adding gaits to
the sequence, playing it -- taking a picture at each step. What it writes to
docs/images/:

    app         app.png, app-dark.png   the whole window, in each theme
                controller.png          the controller, cut out of it
    walk        walk.gif                a walk cycle, in the 3D view alone
    pose        pose.gif                posing the body and a foot
    sequence    sequence.gif,           building a sequence and playing it,
                sequence-dark.gif       in each theme

They are therefore always of the current UI: rerun this after a theme or
layout change rather than editing the images by hand.

Chrome (or Edge) has to be installed; set CHROME to a browser executable to
override the search. The stand-in robot listens on the robot's UDP port, so
neither it nor a real robot's app session can be running on this machine at
the same time. Nothing here is imported by the app itself, and the
preferences, robot cache and gaits of this machine are neither read nor
written.
"""

import base64
import io
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlparse
from urllib.request import urlopen

from PIL import Image
from werkzeug.serving import make_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, "docs", "images")
PORT = 8099
URL = f"http://127.0.0.1:{PORT}/"

# Captured at 2x and downsampled, which is what makes text in the shots crisp
# on the ~900 px column GitHub renders a README into.
SCALE = 2
# The app is one screen that never scrolls: the window is the picture. This is
# the size the desktop app opens at.
APP_WINDOW = (1440, 900)
APP_WIDTH = 1600
# The animations are of a smaller window, so that what is in them is still
# readable at the width a README shows them.
POSE_WINDOW = (1120, 860)
SEQUENCE_WINDOW = (1200, 720)
GIF_WIDTH = 840
WALK_WIDTH = 760

# Every themed shot is taken once per theme, with this suffix on the file
# name. The README picks between the two with a <picture> element, so readers
# see the one matching their GitHub colour mode.
THEMES = [("light", ""), ("dark", "-dark")]

# What the whole-window shot shows instead of the neutral start-up pose: one
# foot lifted, under a body shifted and tilted off centre, all well within
# reach, as the second keyframe of a sequence that goes on into a gait.
POSED_BODY = {
    "widget-percent-x": 0.15,
    "widget-percent-y": -0.1,
    "widget-percent-z": 0.2,
    "widget-rot-x": 7.5,
    "widget-rot-y": -6.0,
    "widget-rot-z": 6.0,
}
# The leg whose foot is lifted (Right Leg 1), and how far it is moved from
# where it stands: across, forward and up, in mm.
POSED_LEG = 0
POSED_FOOT = (15, 20, 35)
POSED_GAIT = "twist"

# The animated hero on the README: one cycle of this gait, looped. A robot
# takes a step in a third of a second, which is a blur at the 25 frames a
# second the preview is drawn at (PREVIEW_FPS in widgets/pose_ui.py), so it is
# played at the slowest the app has: a quarter speed.
WALK_GAIT = "walk_0"
WALK_SPEED_PCT = 25
WALK_FRAME_MS = 40
# The foot lifted in the animation of posing: Right Leg 3's, the one nearest
# the camera.
POSE_GIF_LEG = 2
# What the animation of a sequence puts into it, from the robot's gaits.
SEQUENCE_GAITS = ("walk_0", "turn_left", "twist")
# How long a frame of the other animations is shown, in ms, unless it is
# held for longer; a played sequence is shown at half its speed.
STEP_FRAME_MS = 80
# How long the mark that shows where a click lands is up before the click.
CLICK_MS = 450
GIF_COLORS = 256


# ................................
# The browser
#
# One headless browser for the whole run, driven over the DevTools protocol.
# That is a WebSocket, which the standard library has no client for; the
# little of it the protocol needs is written out here rather than made a
# dependency of a tool.
# ................................


class WebSocket:
    """A WebSocket client for text messages, as DevTools sends and takes."""

    TEXT, CLOSE, PING, PONG = 0x1, 0x8, 0x9, 0xA

    def __init__(self, url):
        parts = urlparse(url)
        self.socket = socket.create_connection((parts.hostname, parts.port))
        key = base64.b64encode(os.urandom(16)).decode()
        self.socket.sendall(
            (
                f"GET {parts.path} HTTP/1.1\r\n"
                f"Host: {parts.netloc}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            ).encode()
        )
        self.buffer = bytearray()
        while b"\r\n\r\n" not in self.buffer:
            self._fill()
        head, _, rest = bytes(self.buffer).partition(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise ConnectionError(f"the browser refused the connection: {head[:80]!r}")
        self.buffer = bytearray(rest)

    def _fill(self):
        chunk = self.socket.recv(1 << 20)
        if not chunk:
            raise ConnectionError("the browser closed the connection")
        self.buffer += chunk

    def _read(self, count):
        while len(self.buffer) < count:
            self._fill()
        data = bytes(self.buffer[:count])
        del self.buffer[:count]
        return data

    def _send(self, opcode, payload):
        # What a client sends is masked; what it receives is not.
        length = len(payload)
        if length < 126:
            head = bytes([0x80 | opcode, 0x80 | length])
        elif length < 1 << 16:
            head = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack(">H", length)
        else:
            head = bytes([0x80 | opcode, 0x80 | 127]) + struct.pack(">Q", length)
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.socket.sendall(head + mask + masked)

    def send(self, text):
        self._send(self.TEXT, text.encode())

    def receive(self):
        """The next message, put back together if it came in pieces."""
        message = b""
        while True:
            first, second = self._read(2)
            opcode, length = first & 0x0F, second & 0x7F
            if length == 126:
                (length,) = struct.unpack(">H", self._read(2))
            elif length == 127:
                (length,) = struct.unpack(">Q", self._read(8))
            payload = self._read(length)
            if opcode == self.PING:
                self._send(self.PONG, payload)
            elif opcode == self.CLOSE:
                raise ConnectionError("the browser closed the connection")
            elif opcode != self.PONG:
                message += payload
                if first & 0x80:
                    return message.decode()

    def close(self):
        self.socket.close()


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


# Two frames on, so that what was just changed has been drawn; or after a
# moment, should the page not be drawing at all.
DRAWN = """
new Promise(function (resolve) {
    var done = function () { resolve(true); };
    window.requestAnimationFrame(function () { window.requestAnimationFrame(done); });
    window.setTimeout(done, 400);
})
"""


# A ring over the middle of an element, in the yellow the app picks things
# out in.
MARK = """
(function () {
    var element = %s;
    // Brought into view first: the gaits are a list that scrolls.
    element.scrollIntoView({block: "nearest"});
    var box = element.getBoundingClientRect();
    var ring = document.createElement("div");
    ring.id = "shot-mark";
    ring.style.cssText = "position: fixed; width: 30px; height: 30px; z-index: 99999;"
        + "border-radius: 50%%; border: 3px solid #f7c600; box-sizing: border-box;"
        + "background: rgba(247, 198, 0, 0.3); pointer-events: none;"
        + "left: " + (box.left + box.width / 2 - 15) + "px;"
        + "top: " + (box.top + box.height / 2 - 15) + "px;";
    document.body.appendChild(ring);
})()
"""


class Css(str):
    """A CSS selector, where a component's id would go."""


class Browser:
    """A headless browser with one page, and what the shots do in it."""

    def __init__(self, executable):
        self.profile = tempfile.mkdtemp(prefix="hexapod-link-browser-")
        self.process = subprocess.Popen(
            [
                executable,
                "--headless=new",
                "--disable-gpu",
                # The 3D view is WebGL; without a GPU, Chrome only draws it in
                # software when told it may.
                "--enable-unsafe-swiftshader",
                "--no-first-run",
                "--no-default-browser-check",
                "--hide-scrollbars",
                # Any port that is free; the browser says which in its profile.
                "--remote-debugging-port=0",
                f"--user-data-dir={self.profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with urlopen(f"http://127.0.0.1:{self._devtools_port()}/json") as reply:
            pages = [target for target in json.load(reply) if target["type"] == "page"]
        self.socket = WebSocket(pages[0]["webSocketDebuggerUrl"])
        self.calls = 0
        self.call("Page.enable")

    def _devtools_port(self, timeout=30.0):
        path = os.path.join(self.profile, "DevToolsActivePort")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with open(path, encoding="utf-8") as f:
                    return int(f.readline())
            except (OSError, ValueError):
                time.sleep(0.1)
        sys.exit("the browser did not start")

    def close(self):
        self.socket.close()
        self.process.terminate()
        self.process.wait(timeout=10)
        shutil.rmtree(self.profile, ignore_errors=True)

    def call(self, method, **params):
        self.calls += 1
        self.socket.send(json.dumps({"id": self.calls, "method": method, "params": params}))
        while True:
            message = json.loads(self.socket.receive())
            if message.get("id") == self.calls:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']['message']}")
                return message["result"]

    def run(self, script):
        """Run `script` in the page, for its value."""
        result = self.call(
            "Runtime.evaluate", expression=script, returnByValue=True, awaitPromise=True
        )
        if "exceptionDetails" in result:
            detail = result["exceptionDetails"]
            text = detail.get("exception", {}).get("description") or detail["text"]
            raise RuntimeError(f"{text}\nin: {script.strip()[:200]}")
        return result["result"].get("value")

    def resize(self, width, height):
        self.call(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=height,
            deviceScaleFactor=SCALE,
            mobile=False,
        )

    def open(self, url):
        """Load `url` as a new session would: the pose and the sequence are
        kept in session storage (widgets/pose_ui.py)."""
        self.run("try { window.sessionStorage.clear(); } catch (error) {}")
        self.call("Page.navigate", url=url)
        self.wait_for("document.readyState === 'complete'")
        self.wait_for("window.hexapodView && document.querySelector('#view-pose canvas')")
        self.settle()

    def wait_for(self, condition, timeout=30.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.run(f"!!({condition})"):
                return
            time.sleep(0.05)
        sys.exit(f"the page never got to: {condition}")

    def settle(self, quiet=0.3, timeout=30.0):
        """Wait for the app to be done with what was just asked of it.

        Dash titles the page "Updating..." for as long as a callback is
        waited on, so the page has settled once the title has been its own for
        `quiet` seconds, and what came of it has been drawn.
        """
        deadline = time.monotonic() + timeout
        since = None
        while time.monotonic() < deadline:
            now = time.monotonic()
            if self.run("document.title === 'Updating...'"):
                since = None
            elif since is None:
                since = now
            elif now - since >= quiet:
                break
            time.sleep(0.03)
        self.run(DRAWN)

    # ---- what a person would do ----

    def set(self, component_id, settle=True, **props):
        """Set a component's props, as its widget does when it is used: the
        callbacks that listen to them run."""
        self.run(
            f"window.dash_clientside.set_props({json.dumps(component_id)}, {json.dumps(props)})"
        )
        if settle:
            self.settle()

    @staticmethod
    def element(component_id):
        """The page's element for a component: `component_id` as Dash has it,
        a string or, for one of a list, a dict. A part of a component that
        has no id of its own is found by a CSS selector instead."""
        if isinstance(component_id, Css):
            return f"document.querySelector({json.dumps(str(component_id))})"
        if isinstance(component_id, dict):
            component_id = json.dumps(component_id, sort_keys=True, separators=(",", ":"))
        return f"document.getElementById({json.dumps(component_id)})"

    def click(self, component_id):
        self.run(f"{self.element(component_id)}.click()")
        self.settle()

    def mark(self, component_id=None):
        """Ring a component, to show where the next click lands: a shot has
        no mouse pointer in it. With none given, take the ring away."""
        self.run(
            "(function () { var old = document.getElementById('shot-mark');"
            " if (old) { old.remove(); } })()"
        )
        if component_id is not None:
            self.run(MARK % self.element(component_id))
        self.run(DRAWN)

    def value(self, component_id):
        """What a number field reads."""
        return float(self.run(f"{self.element(component_id)}.value"))

    def style(self, css):
        """Add a rule or two to the page, to leave something out of a shot."""
        self.run(
            "document.head.appendChild(document.createElement('style')).textContent = "
            + json.dumps(css)
        )
        self.run(DRAWN)

    def wheel(self, x, y, delta, times=1):
        """Turn the mouse wheel over a point: in the view, that zooms."""
        for _ in range(times):
            self.call(
                "Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=0, deltaY=delta
            )
        self.run(DRAWN)

    def drag(self, start, end, button="left", steps=8):
        """Drag a mouse button from one point to another. In the view, away
        from the robot, the left one orbits and the right one pans."""
        (x0, y0), (x1, y1) = start, end
        held = {"left": 1, "right": 2}[button]
        mouse = {"button": button, "clickCount": 1}
        self.call(
            "Input.dispatchMouseEvent", type="mousePressed", x=x0, y=y0, buttons=held, **mouse
        )
        for step in range(1, steps + 1):
            x = x0 + (x1 - x0) * step / steps
            y = y0 + (y1 - y0) * step / steps
            self.call(
                "Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y, buttons=held, **mouse
            )
        self.call("Input.dispatchMouseEvent", type="mouseReleased", x=x1, y=y1, buttons=0, **mouse)
        self.run(DRAWN)

    # ---- pictures ----

    def box(self, selector):
        """Where an element is in the window: (left, top, width, height)."""
        return self.run(
            "(function () {"
            f"var r = document.querySelector({json.dumps(selector)}).getBoundingClientRect();"
            "return [r.left, r.top, r.width, r.height]; })()"
        )

    def shot(self, box=None):
        """A picture of the window, or of the `box` of it, at SCALE."""
        params = {"format": "png"}
        if box:
            x, y, width, height = box
            params["clip"] = {"x": x, "y": y, "width": width, "height": height, "scale": 1}
        data = self.call("Page.captureScreenshot", **params)["data"]
        return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")


def scaled(image, width):
    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.LANCZOS)


class Recorder:
    """The frames of an animation: pictures of one box of the window."""

    def __init__(self, browser, box, width):
        self.browser = browser
        self.box = box
        self.width = width
        self.frames = []
        self.durations = []

    def frame(self, ms=STEP_FRAME_MS):
        self.frames.append(scaled(self.browser.shot(self.box), self.width))
        self.durations.append(ms)

    def press(self, component_id, then_ms):
        """Click a component, shown first with a ring on it, and hold what
        comes of it for `then_ms`."""
        self.browser.mark(component_id)
        self.frame(CLICK_MS)
        self.browser.mark(None)
        self.browser.click(component_id)
        self.frame(then_ms)

    def save(self, path):
        # One palette for every frame, taken from all of them together:
        # quantised each on its own, the background would shimmer, and a
        # colour that only turns up later (a button lit, a foot picked) would
        # have none to be drawn in. An octree rather than a median cut, which
        # shares the palette out by area: nearly all of it went to the shades
        # of the floor, and the small bright things -- the feet, the handles,
        # the body's trim -- came out grey.
        sheet = Image.new("RGB", (self.width, sum(frame.height for frame in self.frames)))
        top = 0
        for frame in self.frames:
            sheet.paste(frame, (0, top))
            top += frame.height
        palette = sheet.quantize(colors=GIF_COLORS, method=Image.FASTOCTREE)
        frames = [frame.quantize(palette=palette, dither=Image.NONE) for frame in self.frames]
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            duration=self.durations,
            loop=0,
            optimize=True,
        )
        return frames[0].size


# ................................
# The app, as the shots start from it
# ................................


def open_app(browser, robot, window, theme="light", panels=()):
    """A fresh page of the app in a window of the size given, connected to
    the stand-in robot, with the overlays named in `panels` open."""
    from hexapod.preferences import PANELS, save_panels, save_theme
    from hexapod.robot_link import ROBOT_LINK
    from settings import ROBOT_DEFAULT_IP
    from widgets.robot_link_ui import ROBOT_CONNECT_BTN_ID, ROBOT_IP_INPUT_ID, STATUS_PILL_ID

    # A page is served with Connect on its button whatever the link is doing,
    # so each one starts from a link that is down.
    ROBOT_LINK.disconnect()
    save_theme(theme)
    save_panels({key: key in panels for key in PANELS})
    browser.resize(*window)
    browser.open(URL)

    browser.set(ROBOT_IP_INPUT_ID, value=robot.address)
    browser.click(ROBOT_CONNECT_BTN_ID)
    browser.wait_for(
        f"document.getElementById('{STATUS_PILL_ID}').textContent.indexOf('Online') >= 0"
    )
    # The stand-in is on this machine; the shots show the address a robot has.
    browser.set(ROBOT_IP_INPUT_ID, value=ROBOT_DEFAULT_IP)


def pick(browser, what):
    """Pick the body ("body") or a leg's foot (its id) up in the view, or let
    go (None), as clicking it there does."""
    from widgets.pose_ui import POSE_VIEW_ID

    browser.run(f"window.hexapodView.select({json.dumps(POSE_VIEW_ID)}, {json.dumps(what)})")
    browser.settle()


def gait_button(kind, gait):
    return {"type": kind, "index": gait}


def eased(step, steps):
    """How far along a move is at `step` of `steps`, starting and stopping
    gently."""
    t = step / steps
    return t * t * (3 - 2 * t)


def slide(browser, recorder, component_id, start, stop, steps, resolution):
    """Take a slider or a number field from `start` to `stop`, a frame a
    step, in values its own steps allow."""
    for step in range(1, steps + 1):
        value = start + (stop - start) * eased(step, steps)
        browser.set(component_id, value=round(round(value / resolution) * resolution, 4))
        recorder.frame()


# ................................
# The shots
# ................................


def shoot_app(browser, robot):
    """The whole window in each theme, and the controller cut out of it."""
    from widgets.pose_ui import (
        POSE_ADD_BTN_ID,
        POSE_FOOT_FIELD_IDS,
        POSE_GAIT_ITEM_TYPE,
        POSE_KF_ITEM_TYPE,
        SELECT_BODY,
    )
    from widgets.robot_link_ui import DRIVE_HUD_ID
    from pages.shell import THEME_TOGGLE_ID

    open_app(browser, robot, APP_WINDOW, panels=("pose", "controller"))

    # Standby, then the pose, then a gait: a sequence with the pose selected
    # in it, and the body picked up.
    browser.click(POSE_ADD_BTN_ID)
    pick(browser, SELECT_BODY)
    for slider_id, value in POSED_BODY.items():
        browser.set(slider_id, value=value)
    pick(browser, POSED_LEG)
    for field_id, move in zip(POSE_FOOT_FIELD_IDS, POSED_FOOT):
        browser.set(field_id, value=browser.value(field_id) + move)
    browser.click(POSE_ADD_BTN_ID)
    browser.click(gait_button(POSE_GAIT_ITEM_TYPE, POSED_GAIT))
    browser.click({"type": POSE_KF_ITEM_TYPE, "index": 1})
    pick(browser, SELECT_BODY)

    for theme, suffix in THEMES:
        if theme != "light":
            browser.click(THEME_TOGGLE_ID)
        image = scaled(browser.shot(), APP_WIDTH)
        save(image, f"app{suffix}.png")

    # Laid over the view, which looks the same in both themes.
    left, top, width, height = browser.box(f"#{DRIVE_HUD_ID}")
    margin = 10
    box = (left - margin, top - margin, width + 2 * margin, height + 2 * margin)
    save(browser.shot(box), "controller.png")


def shoot_walk(browser, robot):
    """One cycle of a walk, looped, with nothing in the picture but the view."""
    from widgets.pose_ui import (
        MODE_PREVIEW,
        POSE_GAIT_REPLACE_TYPE,
        POSE_LOOP_ID,
        POSE_SPEED_ID,
        POSE_VIEW_MODE_ID,
    )

    open_app(browser, robot, APP_WINDOW)
    browser.style(
        ".hexapod-view-overlay, .hexapod-view-hud, .hexapod-view-controls,"
        ".hexapod-view-drive, .hexapod-view-tool { display: none !important; }"
    )
    # The gait as the whole sequence, with the move from its last keyframe
    # back to its first: a cycle that repeats.
    browser.click(gait_button(POSE_GAIT_REPLACE_TYPE, WALK_GAIT))
    browser.set(POSE_SPEED_ID, value=WALK_SPEED_PCT)
    browser.set(POSE_LOOP_ID, value=["loop"])
    browser.set(POSE_VIEW_MODE_ID, data=MODE_PREVIEW)

    left, top, width, height = browser.box(".hexapod-view-frame")
    browser.wheel(left + width / 2, top + height / 2, delta=-100, times=5)
    # A band across the view, the robot in the middle of it.
    band = (left + width * 0.17, top + height * 0.1, width * 0.66, height * 0.76)
    recorder = Recorder(browser, band, WALK_WIDTH)
    play(browser, recorder, WALK_FRAME_MS)
    # Looped, the sequence ends where it starts: one of the two is enough.
    if recorder.frames[0].tobytes() == recorder.frames[-1].tobytes():
        recorder.frames.pop()
        recorder.durations.pop()
    save_gif(recorder, "walk.gif")


def play(browser, recorder, frame_ms, every=1):
    """Record the sequence, a frame of the preview at a time. The frames are
    stepped from here rather than by the page's own clock, so that each one
    is in the animation once. Returns the last frame's number."""
    from widgets.pose_ui import POSE_FRAME_SLIDER_ID

    last = int(
        browser.run(
            f"document.querySelector('#{POSE_FRAME_SLIDER_ID} [role=slider]')"
            ".getAttribute('aria-valuemax')"
        )
    )
    for frame in range(0, last + 1, every):
        browser.set(POSE_FRAME_SLIDER_ID, settle=False, value=frame)
        browser.run(DRAWN)
        recorder.frame(frame_ms)
    return last


def shoot_pose(browser, robot):
    """Posing the robot in the view: the body moved and turned, a foot lifted."""
    from widgets.body_ui import BODY_SLIDER_IDS
    from widgets.pose_ui import (
        POSE_BODY_MODE_ID,
        POSE_FOOT_UP_ID,
        POSE_FOOT_Y_ID,
        POSE_PICK_BODY_ID,
        POSE_PICK_LEG_IDS,
    )

    open_app(browser, robot, POSE_WINDOW, panels=("pose",))
    left, top, width, height = browser.box(".hexapod-view-frame")
    # The pose's controls take the view's left side; the robot is moved clear
    # of them, as one would with the right mouse button.
    centre = (left + width / 2, top + height * 0.3)
    browser.drag(centre, (centre[0] + width * 0.16, centre[1] + height * 0.04), button="right")
    recorder = Recorder(browser, (left, top, width, height), GIF_WIDTH)

    slider = dict(zip(("x", "y", "z", "rot_x", "rot_y", "rot_z"), BODY_SLIDER_IDS))
    recorder.frame(900)
    # The body: moved by its arrows, then turned by its rings.
    recorder.press(POSE_PICK_BODY_ID, 800)
    slide(browser, recorder, slider["z"], 0, 0.3, 8, 0.05)
    slide(browser, recorder, slider["x"], 0, -0.25, 8, 0.05)
    recorder.frame(500)
    recorder.press(Css(f"#{POSE_BODY_MODE_ID} .form-check:nth-child(2) label"), 800)
    slide(browser, recorder, slider["rot_x"], 0, 12, 8, 1.5)
    slide(browser, recorder, slider["rot_z"], 0, -15, 8, 1.5)
    recorder.frame(700)
    # A foot: the one nearest the camera, lifted and put forward.
    recorder.press(POSE_PICK_LEG_IDS[POSE_GIF_LEG], 800)
    up = browser.value(POSE_FOOT_UP_ID)
    forward = browser.value(POSE_FOOT_Y_ID)
    slide(browser, recorder, POSE_FOOT_UP_ID, up, up + 50, 8, 1)
    slide(browser, recorder, POSE_FOOT_Y_ID, forward, forward + 40, 8, 1)
    recorder.frame(700)
    pick(browser, None)
    recorder.frame(2000)
    save_gif(recorder, "pose.gif")


def shoot_sequence(browser, robot, theme, suffix):
    """A sequence put together from the robot's gaits, then played."""
    from widgets.pose_ui import (
        POSE_FRAME_SLIDER_ID,
        POSE_GAIT_ITEM_TYPE,
        POSE_INTERVAL_ID,
        POSE_PLAY_BTN_ID,
    )

    open_app(browser, robot, SEQUENCE_WINDOW, theme=theme)
    left, top, width, height = browser.box(".hexapod-view-frame")
    browser.wheel(left + width / 2, top + height / 2, delta=-100, times=2)
    recorder = Recorder(browser, None, GIF_WIDTH)

    recorder.frame(1000)
    for gait in SEQUENCE_GAITS:
        recorder.press(gait_button(POSE_GAIT_ITEM_TYPE, gait), 700)

    browser.mark(POSE_PLAY_BTN_ID)
    recorder.frame(CLICK_MS)
    browser.mark(None)
    browser.click(POSE_PLAY_BTN_ID)
    browser.set(POSE_INTERVAL_ID, disabled=True)
    last = play(browser, recorder, STEP_FRAME_MS)
    # Paused where it ran out, which makes that frame the pose.
    browser.set(POSE_FRAME_SLIDER_ID, value=last)
    browser.click(POSE_PLAY_BTN_ID)
    recorder.frame(2000)
    save_gif(recorder, f"sequence{suffix}.gif")


def save(image, file_name):
    path = os.path.join(OUT_DIR, file_name)
    image.save(path, optimize=True)
    report(path, image.size)


def save_gif(recorder, file_name):
    path = os.path.join(OUT_DIR, file_name)
    size = recorder.save(path)
    report(path, size, f"{len(recorder.frames)} frames")


def report(path, size, note=""):
    kb = os.path.getsize(path) // 1024
    print(f"  docs/images/{os.path.basename(path):<20} {size[0]}x{size[1]}  {kb} KB  {note}")


def shoot_sequences(browser, robot):
    for theme, suffix in THEMES:
        shoot_sequence(browser, robot, theme, suffix)


SHOTS = {
    "app": shoot_app,
    "walk": shoot_walk,
    "pose": shoot_pose,
    "sequence": shoot_sequences,
}


def main():
    wanted = sys.argv[1:] or list(SHOTS)
    unknown = [name for name in wanted if name not in SHOTS]
    if unknown:
        sys.exit(f"no such shot: {', '.join(unknown)} (there are: {', '.join(SHOTS)})")

    # The app keeps its preferences, the last robot's config and one's own
    # gaits on disk, and serves what it finds there. Point all three at a
    # throwaway directory before anything of the app is imported: this
    # machine's are neither shown in the shots nor overwritten by them.
    from settings import GAITS_ENV, PREFERENCES_ENV, ROBOT_CONFIG_CACHE_ENV, ROBOT_UDP_PORT

    scratch = tempfile.mkdtemp(prefix="hexapod-link-shots-")
    os.environ[PREFERENCES_ENV] = os.path.join(scratch, "preferences.json")
    os.environ[ROBOT_CONFIG_CACHE_ENV] = os.path.join(scratch, "robot_config.json")
    os.environ[GAITS_ENV] = os.path.join(scratch, "gaits")

    import hexapod_link  # noqa: E402  (imported late; it builds the whole app)
    from fake_robot import FakeRobot
    from hexapod.robot_link import ROBOT_LINK

    os.makedirs(OUT_DIR, exist_ok=True)
    server = make_server("127.0.0.1", PORT, hexapod_link.app.server, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    robot = FakeRobot.from_fixture("nougat", udp_port=ROBOT_UDP_PORT).start()

    executable = find_browser()
    print(f"browser: {executable}")
    browser = Browser(executable)
    try:
        for name in wanted:
            print(f"{name} ...")
            SHOTS[name](browser, robot)
    finally:
        browser.close()
        ROBOT_LINK.disconnect()
        robot.stop()
        server.shutdown()
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
