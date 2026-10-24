"""The frameless window's own controls, called from the page.

The native frame is gone (hexapod_link.py), so the top bar stands in for it:
it drags the window, double-clicking it maximizes, and its buttons minimize,
maximize and close. Strips along the window's edges resize it, since Windows
gives a frameless window no edges of its own. The page side is
assets/window_frame.js; it reaches these through pywebview's js_api, as
window.pywebview.api.<method>.
"""

import sys

# pywebview's FixPoint flags, by value, so this module imports without
# pywebview: which corner of the window stays put as it is resized. They are
# made into FixPoint itself when the window is resized, as the Windows
# backend will not take a plain number.
FIX_NORTH = 1
FIX_WEST = 2
FIX_EAST = 4
FIX_SOUTH = 8


class WindowControls:
    """The js_api object handed to pywebview.

    pywebview exposes every public attribute to the page, nested objects
    included, so the window is kept in underscored ones.
    """

    def __init__(self, min_size=(0, 0)):
        self._window = None
        self._maximized = False
        self._min_width, self._min_height = min_size
        self._resize_from = None

    def attach(self, window):
        self._window = window
        window.events.maximized += self._on_maximized
        window.events.restored += self._on_restored

    def _on_maximized(self):
        self._maximized = True
        self._tell_page()

    def _on_restored(self):
        self._maximized = False
        self._tell_page()

    def _tell_page(self):
        """Let the page swap the maximize button's icon."""
        state = "true" if self._maximized else "false"
        try:
            self._window.run_js(f"window.hexapodWindowMaximized && hexapodWindowMaximized({state})")
        except Exception:  # the page may be reloading
            pass

    # ---- The buttons ----

    def minimize(self):
        self._window.minimize()

    def toggle_maximize(self):
        if self._maximized:
            self._window.restore()
        else:
            keep_taskbar_visible(self._window)
            self._window.maximize()

    def is_maximized(self):
        return self._maximized

    def close(self):
        self._window.destroy()

    # ---- Resizing from an edge ----

    def begin_resize(self):
        """Note the window's size as a drag on one of its edges starts."""
        self._resize_from = (self._window.width, self._window.height)

    def resize_by(self, edge, dx, dy):
        """Resize the window by how far the pointer has gone since
        begin_resize(), from `edge`: some of "n", "s", "e" and "w".

        The opposite edge stays where it is."""
        if self._resize_from is None or self._maximized:
            return
        width, height = self._resize_from
        fix = 0
        if "e" in edge:
            width += dx
            fix |= FIX_WEST
        elif "w" in edge:
            width -= dx
            fix |= FIX_EAST
        else:
            fix |= FIX_WEST
        if "s" in edge:
            height += dy
            fix |= FIX_NORTH
        elif "n" in edge:
            height -= dy
            fix |= FIX_SOUTH
        else:
            fix |= FIX_NORTH
        width = max(int(width), self._min_width)
        height = max(int(height), self._min_height)
        from webview.window import FixPoint  # pylint: disable=import-outside-toplevel

        self._window.resize(width, height, fix_point=FixPoint(fix))


def keep_taskbar_visible(window):
    """On Windows a maximized frameless form covers the whole screen, taskbar
    and all; limiting it to the screen's working area keeps the taskbar in
    view. Elsewhere the window manager already does that."""
    if sys.platform != "win32":
        return
    try:
        # pythonnet, which pywebview's Windows backend runs on.
        from System.Drawing import Rectangle  # pylint: disable=import-error
        from System.Windows.Forms import Screen  # pylint: disable=import-error

        form = window.native
        screen = Screen.FromRectangle(form.Bounds)
        area, bounds = screen.WorkingArea, screen.Bounds
        # Relative to the screen the window is on, not to the desktop.
        form.MaximizedBounds = Rectangle(
            area.X - bounds.X, area.Y - bounds.Y, area.Width, area.Height
        )
    except Exception as error:  # a full-screen maximize is still usable
        print(f"could not fit the maximized window to the screen: {error}", file=sys.stderr)
