"""Bring the desktop window back as it was last closed.

The window's position and size, and whether it was maximized, are saved as it
closes (save_window in hexapod/preferences.py) and handed to
webview.create_window on the next launch. A position on a screen that is no
longer there is dropped, so the window never opens out of sight.

pywebview only says where a window is through its moved and resized events,
and reading window.x and the like from the closing handler can hang, as that
handler runs on the GUI thread the read waits on. So the geometry is followed
from those events. What is kept is the window's normal place: maximizing or
minimizing moves and resizes the window too, and since pywebview runs each
handler on a thread of its own, those moves can arrive just before or just
after the maximized event. Changes made just before it are taken back.
"""

import sys
import threading
import time

from hexapod.preferences import WINDOW_KEYS, load_window, save_window

# How long before a maximize or minimize the moves and resizes it made can
# arrive. Far shorter than a person can resize a window and then maximize it.
SETTLE_S = 0.5

# A saved position is used only if this much of the window's top edge, where
# it is dragged from, is on one of the screens.
VISIBLE_W = 120
VISIBLE_H = 30


class WindowState:
    """Follows a pywebview window's normal geometry and saves it as it closes."""

    def __init__(self, saved, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._normal = {key: saved.get(key) for key in WINDOW_KEYS}
        self._maximized = saved.get("maximized") is True
        self._minimized = False
        self._undo = []  # (time, key, the value it replaced)
        self._window = None

    def attach(self, window):
        self._window = window
        window.events.moved += self._on_moved
        window.events.resized += self._on_resized
        window.events.maximized += self._on_maximized
        window.events.minimized += self._on_minimized
        window.events.restored += self._on_restored
        window.events.closing += self.save

    # ---- Events ----

    def _on_moved(self, x, y):
        self._update(x=x, y=y)

    def _on_resized(self, width, height):
        self._update(width=width, height=height)

    def _update(self, **values):
        with self._lock:
            if self._maximized or self._minimized:
                return
            now = self._clock()
            self._undo = [entry for entry in self._undo if now - entry[0] <= SETTLE_S]
            for key, value in values.items():
                self._undo.append((now, key, self._normal[key]))
                self._normal[key] = int(value)

    def _take_back_recent(self):
        now = self._clock()
        for when, key, value in reversed(self._undo):
            if now - when <= SETTLE_S:
                self._normal[key] = value
        self._undo = []

    def _on_maximized(self):
        with self._lock:
            if not (self._maximized or self._minimized):
                self._take_back_recent()
            self._maximized = True
            self._minimized = False

    def _on_minimized(self):
        with self._lock:
            if not (self._maximized or self._minimized):
                self._take_back_recent()
            self._minimized = True

    def _on_restored(self):
        """Back from minimized, or from maximized. GTK says restored when a
        minimized window comes back maximized too, so the first only ends
        the minimize."""
        with self._lock:
            if self._minimized:
                self._minimized = False
            else:
                self._maximized = False

    # ---- Saving ----

    def state(self):
        """What would be saved: the normal geometry and "maximized"."""
        with self._lock:
            state = dict(self._normal, maximized=self._maximized)
        native = self._native_state()
        return native if native else state

    def _native_state(self):
        """On Windows the form knows its normal bounds itself, even while it
        is maximized or minimized; ask it, as the closing handler runs on the
        GUI thread. None elsewhere, or if it cannot be read."""
        if sys.platform != "win32" or self._window is None:
            return None
        try:
            from System.Windows.Forms import FormWindowState  # pylint: disable=import-error

            form = self._window.native
            scale = getattr(form, "_scale", 1.0) or 1.0
            bounds = form.RestoreBounds
            if form.WindowState == FormWindowState.Minimized:
                maximized = self._maximized
            else:
                maximized = form.WindowState == FormWindowState.Maximized
            return {
                "x": int(bounds.X / scale),
                "y": int(bounds.Y / scale),
                "width": int(bounds.Width / scale),
                "height": int(bounds.Height / scale),
                "maximized": maximized,
            }
        except Exception:  # the followed geometry is nearly as good
            return None

    def save(self):
        """Store the window's state. Never stops the window from closing."""
        try:
            save_window(self.state())
        except Exception as error:
            print(f"could not save the window's state: {error}", file=sys.stderr)


def on_a_screen(x, y, width, screens):
    """Whether enough of a window's top edge at (x, y) is on one of `screens`
    (anything with x, y, width and height) to grab it by."""
    for screen in screens:
        left = max(x, screen.x)
        right = min(x + width, screen.x + screen.width)
        top = max(y, screen.y)
        bottom = min(y + VISIBLE_H, screen.y + screen.height)
        if right - left >= min(VISIBLE_W, width) and bottom - top >= VISIBLE_H:
            return True
    return False


def window_options(saved, screens, default_size, origin=(0, 0)):
    """Keyword arguments for webview.create_window from the saved state.

    `screens` are the screens there are now; with none known, a saved
    position is not trusted. `origin` is where the backend counts positions
    from: GTK places a window relative to the first screen.
    """
    width = saved.get("width") or default_size[0]
    height = saved.get("height") or default_size[1]
    options = {"width": width, "height": height, "maximized": saved.get("maximized") is True}
    x, y = saved.get("x"), saved.get("y")
    if x is not None and y is not None and on_a_screen(x, y, width, screens):
        options["x"] = x - origin[0]
        options["y"] = y - origin[1]
    return options


def restored_window(default_size):
    """The saved state, and create_window's keyword arguments for it."""
    saved = load_window()
    try:
        import webview  # pylint: disable=import-outside-toplevel

        screens = list(webview.screens)
    except Exception as error:
        print(f"could not list the screens: {error}", file=sys.stderr)
        screens = []
    origin = (0, 0)
    if sys.platform.startswith("linux") and screens:
        origin = (screens[0].x, screens[0].y)
    return saved, window_options(saved, screens, default_size, origin)
