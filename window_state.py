"""The window's size and place, kept between launches.

Saved as the window closes (hexapod/preferences.py) and put back as it next
opens (hexapod_link.py): the size and place it had out of maximized, so a
window left maximized still restores to where it was, and whether it was
maximized. Everything is in logical pixels, as pywebview takes and reports it.

A place that no screen shows any more, say a monitor since unplugged, is
dropped, and the window opens centred instead.
"""

import sys
import threading
import time

from hexapod.preferences import load_window, save_window

# How much of the window's top must be on a screen for the saved place to be
# kept: enough of the top bar to grab and drag it.
GRAB_STRIP_H = 40
GRAB_MIN_W = 120
GRAB_MIN_H = 20

# Outside Windows the window's size and place are followed through its moved
# and resized events, which come each on a thread of their own, so the one a
# maximize causes can be taken before the maximize itself. Changes this recent
# when the window maximizes or minimizes are put back.
SETTLE_S = 0.5


def _overlap(a_start, a_length, b_start, b_length):
    return max(0, min(a_start + a_length, b_start + b_length) - max(a_start, b_start))


def screen_holding(x, y, width, screens):
    """The screen showing enough of a window's top at (x, y) to grab it, or
    None."""
    for screen in screens:
        if (
            _overlap(x, width, screen.x, screen.width) >= GRAB_MIN_W
            and _overlap(y, GRAB_STRIP_H, screen.y, screen.height) >= GRAB_MIN_H
        ):
            return screen
    return None


def fit_window(saved, default_size, min_size, screens):
    """Where and how big to open the window: (x, y, width, height), x and y
    None to centre it.

    `saved` is preferences.load_window(); `screens` pywebview's, each with an
    x, y, width and height, or empty if they are not known, which keeps the
    saved place as it is. The size is kept within the screen the window opens
    on, and not under min_size.
    """
    width = saved.get("width") or default_size[0]
    height = saved.get("height") or default_size[1]
    x, y = saved.get("x"), saved.get("y")

    screen = None
    if screens:
        if x is not None:
            screen = screen_holding(x, y, width, screens)
            if screen is None:
                x = y = None
        screen = screen or screens[0]
        width = min(width, screen.width)
        height = min(height, screen.height)

    width = max(width, min_size[0])
    height = max(height, min_size[1])
    return x, y, width, height


class WindowState:
    """Follows one window and saves its size and place as it closes."""

    def __init__(self, x, y, width, height, maximized=False):
        self._window = None
        self._lock = threading.Lock()
        self._normal = {"x": x, "y": y, "width": width, "height": height}
        self._changes = []  # (when, key, value before), for SETTLE_S
        # One opened maximized is taken as such until it says otherwise.
        self._state = "maximized" if maximized else "normal"

    def geometry(self):
        """(x, y, width, height) to open the window with; x and y None to
        centre it."""
        with self._lock:
            normal = self._normal
            return normal["x"], normal["y"], normal["width"], normal["height"]

    def attach(self, window):
        self._window = window
        window.events.maximized += lambda: self._set_state("maximized")
        window.events.minimized += lambda: self._set_state("minimized")
        window.events.restored += lambda: self._set_state("normal")
        window.events.moved += self._on_moved
        window.events.resized += self._on_resized
        # The closing handlers run in turn, on the window's own thread.
        window.events.closing += self.save

    # ---- Following it ----

    def _set_state(self, state):
        with self._lock:
            if state != "normal":
                # Undo what the maximize or minimize itself moved.
                settled = time.monotonic() - SETTLE_S
                for when, key, before in reversed(self._changes):
                    if when >= settled:
                        self._normal[key] = before
            self._changes = []
            self._state = state

    def _note(self, **values):
        with self._lock:
            if self._state != "normal":
                return
            now = time.monotonic()
            self._changes = [c for c in self._changes if c[0] >= now - SETTLE_S]
            for key, value in values.items():
                self._changes.append((now, key, self._normal[key]))
                self._normal[key] = int(value)

    def _on_moved(self, x, y):
        self._note(x=x, y=y)

    def _on_resized(self, width, height):
        self._note(width=width, height=height)

    # ---- Saving it ----

    def save(self):
        """Store the window's size and place. Best effort: never stops the
        window closing."""
        try:
            normal, maximized = self._read()
            save_window(maximized=maximized, **normal)
        except Exception as error:
            print(f"could not save the window's size and place: {error}", file=sys.stderr)

    def _read(self):
        if sys.platform == "win32":
            try:
                return _read_form(self._window.native)
            except Exception as error:  # fall back on what was followed
                print(f"could not read the window's bounds: {error}", file=sys.stderr)
        with self._lock:
            return dict(self._normal), self._state == "maximized"


def _read_form(form):
    """On Windows the form itself says where it would be restored to, exactly,
    maximized or minimized. Its bounds are in physical pixels.

    Read as the window closes, on its own thread, so without an Invoke."""
    from System.Windows.Forms import FormWindowState  # pylint: disable=import-error

    scale = form._scale  # pywebview's, for this window's screen
    bounds = form.Bounds if form.WindowState == FormWindowState.Normal else form.RestoreBounds
    normal = {
        "x": int(round(bounds.X / scale)),
        "y": int(round(bounds.Y / scale)),
        "width": int(round(bounds.Width / scale)),
        "height": int(round(bounds.Height / scale)),
    }
    return normal, form.WindowState == FormWindowState.Maximized


def restore_window(default_size, min_size, screens):
    """The saved window fitted to the screens: (WindowState, maximized)."""
    saved = load_window()
    x, y, width, height = fit_window(saved, default_size, min_size, screens)
    maximized = saved["maximized"]
    return WindowState(x, y, width, height, maximized), maximized
