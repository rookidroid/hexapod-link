"""The frameless window's own controls, called from the page.

The native frame is gone (hexapod_link.py), so the top bar stands in for it:
it drags the window -- on Windows by Windows itself, so the window snaps to
the screen's edges and a maximized one is restored -- double-clicking it
maximizes, and its buttons minimize, maximize and close. Strips along the
window's edges resize it, since Windows gives a frameless window no edges of
its own. The page side is assets/window_frame.js; it reaches these through
pywebview's js_api, as window.pywebview.api.<method>.
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

# Win32, for handing a drag of the bar to Windows (begin_native_drag).
WM_NCLBUTTONDOWN = 0x00A1
HTCAPTION = 2
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
SM_SWAPBUTTON = 23


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

    def attach(self, window, maximize=False):
        """Follow `window`; `maximize` maximizes it once it is shown, as it
        was left last time, the way the maximize button does."""
        self._window = window
        window.events.maximized += self._on_maximized
        window.events.restored += self._on_restored

        def on_shown():
            # Snapping first: it is what fits a maximized window to the screen.
            if sys.platform == "win32":
                make_snappable(window)
            if maximize:
                self.toggle_maximize()

        window.events.shown += on_shown

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

    # ---- Dragging the window by its bar ----

    def native_drag(self):
        """Whether begin_native_drag() hands a drag of the bar to the system:
        on Windows. Elsewhere the page drags the window itself."""
        return sys.platform == "win32"

    def begin_native_drag(self):
        """Hand a drag of the bar, already under way, to Windows, as if it were
        the window's own title bar: Windows then moves the window, restores it
        if it is maximized, and snaps it to the screen's edges and corners and
        offers the snap layouts at the top, as it does any window's.

        It is the usual move loop, started by telling the window its caption
        was pressed. Not if the button is up by the time this runs: the loop
        would wait for a release that has already happened, with the window
        stuck to the pointer."""
        if not self.native_drag():
            return False
        keep_taskbar_visible(self._window)
        form = self._window.native

        def start():
            import ctypes  # pylint: disable=import-outside-toplevel

            user32 = ctypes.windll.user32
            # The primary button, whichever side it is on.
            button = VK_RBUTTON if user32.GetSystemMetrics(SM_SWAPBUTTON) else VK_LBUTTON
            if not user32.GetAsyncKeyState(button) & 0x8000:
                return
            user32.ReleaseCapture()
            user32.SendMessageW(
                ctypes.c_void_p(form.Handle.ToInt64()), WM_NCLBUTTONDOWN, HTCAPTION, 0
            )

        # On the window's own thread, which holds the mouse; not waited for,
        # as the move loop runs until the button is let go.
        from System import Action  # pylint: disable=import-error,import-outside-toplevel

        form.BeginInvoke(Action(start))
        return True

    # Elsewhere: dragging a maximized window by its bar first restores it.

    def restore_for_drag(self, screen_x, screen_y, client_x, client_y, page_width):
        """Restore the maximized window as its bar starts being dragged, as a
        native title bar does, and put it under the pointer: as far along the
        restored bar as the pointer was along the maximized one, and as far
        down it. Returns where the pointer now is in the window, [x, y], for
        the rest of the drag (move_to), or None if it was not maximized.

        Positions are the page's: logical pixels, as pywebview's move takes.
        """
        if not self._maximized:
            return None
        fraction = min(max(client_x / page_width, 0.0), 1.0) if page_width else 0.5
        self._window.restore()
        width = self._window.width
        grab_x = int(round(fraction * width))
        grab_y = int(client_y)
        self._window.move(int(screen_x) - grab_x, int(screen_y) - grab_y)
        return [grab_x, grab_y]

    def move_to(self, x, y):
        """Put the window's top-left corner at (x, y), in logical pixels."""
        self._window.move(int(x), int(y))

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


# ---- Snapping, on Windows ----
#
# pywebview makes a frameless window a bare popup, without the styles that
# say it can be resized and maximized, and Windows snaps only windows that
# say so. So they are put back, as Chromium does for its own frameless
# windows, and the frame they would bring is kept off: the window's client
# area is made the whole window (WM_NCCALCSIZE), or, maximized, the screen's
# work area, which Windows would otherwise overhang by its frame.

WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
GWL_STYLE = -16
WM_NCCALCSIZE = 0x0083
SWP_FLAGS = 0x0020 | 0x0001 | 0x0002 | 0x0004 | 0x0010  # FRAMECHANGED, keep the rest
MONITOR_DEFAULTTONEAREST = 2
SNAP_SUBCLASS_ID = 0x6865_7861  # any number of our own

# The window procedure Windows calls, kept alive as long as the window is.
_subclass_procs = []


def make_snappable(window):
    """Let Windows snap the frameless window, on its own thread. Best effort:
    a window that cannot be made so still works, it only does not snap."""
    try:
        from System import Action  # pylint: disable=import-error,import-outside-toplevel

        form = window.native
        form.Invoke(Action(lambda: _make_snappable(form.Handle.ToInt64())))
    except Exception as error:
        print(f"could not let the window snap: {error}", file=sys.stderr)


def _make_snappable(handle):
    import ctypes  # pylint: disable=import-outside-toplevel
    from ctypes import wintypes  # pylint: disable=import-outside-toplevel

    user32 = ctypes.windll.user32
    comctl32 = ctypes.windll.comctl32
    lresult = ctypes.c_ssize_t

    class MonitorInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    subclass_proc = ctypes.WINFUNCTYPE(
        lresult,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
        ctypes.c_size_t,
        ctypes.c_size_t,
    )
    comctl32.DefSubclassProc.restype = lresult
    comctl32.DefSubclassProc.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    comctl32.SetWindowSubclass.argtypes = [
        wintypes.HWND,
        subclass_proc,
        ctypes.c_size_t,
        ctypes.c_size_t,
    ]
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    user32.IsZoomed.argtypes = [wintypes.HWND]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]

    def proc(hwnd, message, wparam, lparam, _id, _data):
        if message == WM_NCCALCSIZE and wparam:
            # The first rectangle is the window's; what is left in it is the
            # client area. Left as it is: no frame. Maximized: the work area.
            if user32.IsZoomed(hwnd):
                info = MonitorInfo()
                info.cbSize = ctypes.sizeof(MonitorInfo)
                monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
                if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                    ctypes.cast(lparam, ctypes.POINTER(wintypes.RECT))[0] = info.rcWork
            return 0
        return comctl32.DefSubclassProc(hwnd, message, wparam, lparam)

    callback = subclass_proc(proc)
    hwnd = wintypes.HWND(handle)
    if not comctl32.SetWindowSubclass(hwnd, callback, SNAP_SUBCLASS_ID, 0):
        raise OSError("SetWindowSubclass failed")
    _subclass_procs.append(callback)

    style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    style |= WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
    user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_FLAGS)
