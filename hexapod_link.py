"""Hexapod Link entry point.

Builds the Dash app and serves it with waitress on a loopback-only port, inside
a pywebview window by default.

    python hexapod_link.py              # native window
    python hexapod_link.py --no-window  # serve only, open the URL in a browser
"""

import argparse
import mimetypes
import os
import socket
import sys
import threading
import time

import dash_bootstrap_components as dbc
import waitress
from dash import Dash, Input, Output, callback, dcc, html

from hexapod.preferences import load_theme
from hexapod.robot_link import ROBOT_LINK
from pages import (
    page_calibration,
    page_landing,
    page_motion,
    page_pose,
)
from pages.shared import (
    GLOBAL_CONTROLS_PANEL,
    GLOBAL_PANEL_TOGGLE_CLASS,
    GLOBAL_PANEL_TOGGLE_ID,
    GLOBAL_PANEL_TOGGLE_LABEL,
    make_theme_toggle,
)
from style_settings import EXTERNAL_STYLESHEETS, GLOBAL_PAGE_STYLE
from texts import (
    APP_TITLE,
    APP_VERSION,
    CALIBRATION_PAGE_PATH,
    IK_PAGE_PATH,
    KINEMATICS_PAGE_PATH,
    MOTION_PAGE_PATH,
    PATTERNS_PAGE_PATH,
    POSE_PAGE_PATH,
    POSER_PAGE_PATH,
    ROOT_PATH,
)


# ....................
# Dash app
# ....................


def resource_root():
    """Directory holding the bundled data files (assets/, ...).

    A PyInstaller one-file build unpacks itself into a temporary directory and
    points sys._MEIPASS at it; __file__ then refers to a path inside the frozen
    archive and cannot be used to locate assets. Outside a bundle this is just
    the repository root.
    """
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


ASSETS_PATH = os.path.join(resource_root(), "assets")

# Windows has no registry entry for .woff2, so the bundled fonts would be
# served as application/octet-stream.
mimetypes.add_type("font/woff2", ".woff2")


class HexapodDash(Dash):
    """Dash, with the saved colour theme written into the served page.

    The theme lives on the <html> element, which Dash's layout cannot reach;
    setting it from a callback would only happen after the first paint, so a
    dark start would flash light. Putting it into the index page itself avoids
    that. See the theme section of pages/shared.py.
    """

    def interpolate_index(self, **kwargs):
        index = super().interpolate_index(**kwargs)
        theme = load_theme()
        return index.replace(
            "<html>", f'<html data-theme="{theme}" data-bs-theme="{theme}">', 1
        )


app = HexapodDash(
    __name__,
    assets_folder=ASSETS_PATH,
    external_stylesheets=EXTERNAL_STYLESHEETS,
    suppress_callback_exceptions=True,
    title=APP_TITLE,
)
server = app.server


# ....................
# Layout
# ....................

NAV_LINKS = dbc.Nav(
    [
        dbc.NavItem(dbc.NavLink("Pose", href=POSE_PAGE_PATH)),
        dbc.NavItem(dbc.NavLink("Motion", href=MOTION_PAGE_PATH)),
    ],
    navbar=True,
)


def make_navbar(theme):
    return dbc.Navbar(
        dbc.Container(
            [
                dbc.NavbarBrand(
                    [
                        APP_TITLE,
                        html.Span(f"v{APP_VERSION}", className="navbar-version"),
                    ],
                    href=ROOT_PATH,
                ),
                NAV_LINKS,
                html.Div(
                    [
                        make_theme_toggle(theme),
                        # Doubles as the app's status readout and as the handle
                        # for the global robot panel. ONLINE means the link to
                        # the hexapod is up.
                        html.Button(
                            GLOBAL_PANEL_TOGGLE_LABEL,
                            id=GLOBAL_PANEL_TOGGLE_ID,
                            className=GLOBAL_PANEL_TOGGLE_CLASS,
                            title="Robot link and dimensions",
                        ),
                    ],
                    className="navbar-actions",
                ),
            ],
            fluid=True,
        ),
        className="mb-3 ind-navbar",
        sticky="top",
        # Always laid out horizontally: there is no collapse toggler, so the
        # default (collapse below `md`) would just stack the links into a tall
        # list. Narrow windows wrap them onto a second row instead -- see NAVBAR
        # in industrial.css.
        expand=True,
    )


def serve_layout():
    """Built per page load, so the navbar's theme button matches the saved
    theme (see HexapodDash above)."""
    return dbc.Container(
        [
            make_navbar(load_theme()),
            dcc.Location(id="url", refresh=False),
            GLOBAL_CONTROLS_PANEL,
            # Sizing and scrolling live in the PAGE LAYOUT block of
            # industrial.css: it takes a media query to say that this scrolls
            # only once the columns have stacked, and an inline style cannot
            # carry one.
            html.Div(id="page-content", className="flex-grow-1"),
        ],
        fluid=True,
        style={
            **GLOBAL_PAGE_STYLE,
            "height": "100vh",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            # Breathing room under the content now that there is no footer bar.
            "paddingBottom": "1rem",
        },
    )


app.layout = serve_layout

PAGES = {
    POSE_PAGE_PATH: page_pose.layout,
    # The pages the pose page replaced; it opens on the matching tool.
    KINEMATICS_PAGE_PATH: page_pose.layout,
    IK_PAGE_PATH: page_pose.layout,
    PATTERNS_PAGE_PATH: page_pose.layout,
    POSER_PAGE_PATH: page_pose.layout,
    MOTION_PAGE_PATH: page_motion.layout,
    CALIBRATION_PAGE_PATH: page_calibration.layout,
    ROOT_PATH: page_landing.layout,
}


@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    return PAGES.get(pathname, PAGES[ROOT_PATH])


# ....................
# Server and window
# ....................

HOST = "127.0.0.1"

# How long to wait for waitress to start accepting connections before giving
# up. Generous: the first import of plotly/dash is slow on a cold filesystem.
STARTUP_TIMEOUT = 30.0

WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900
WINDOW_MIN_SIZE = (1024, 700)

# Windows draws the window icon through System.Drawing.Icon, which reads real
# ICO files only; the GTK, Qt and Cocoa backends all take the PNG. Both files
# are generated by tools/make_icon.py.
WINDOW_ICON_FILE = "app.ico" if sys.platform == "win32" else "icon.png"


def window_icon():
    """Absolute path to the window icon, or None if it is not there.

    Without this the window borrows whatever icon the running executable has:
    the Python interpreter's when started with `python hexapod_link.py`, and on
    Linux nothing at all, since only the Windows build embeds one in the
    binary. Returning None is what pywebview expects when there is no icon.
    """
    path = os.path.join(ASSETS_PATH, WINDOW_ICON_FILE)
    return path if os.path.isfile(path) else None


def find_free_port():
    """Ask the OS for an unused loopback port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


def wait_until_serving(port, timeout=STARTUP_TIMEOUT):
    """Block until the server accepts a connection, or the timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def start_server(port=None):
    """Start the WSGI server on a daemon thread and return its URL.

    Binding to 127.0.0.1 rather than 0.0.0.0 keeps the app off the network and
    avoids the Windows Firewall prompt on first launch. It does not affect the
    robot link, which is a separate outbound UDP socket.
    """
    port = port or find_free_port()

    # threads=8 is well above what a single window needs, but Dash fires
    # several callbacks concurrently on a page load and a starved pool shows up
    # as a visibly slow UI. Nothing external ever sees this server, so ident=None
    # drops the Server header.
    thread = threading.Thread(
        target=waitress.serve,
        args=(server,),
        kwargs={"host": HOST, "port": port, "threads": 8, "ident": None},
        name="hexapod-wsgi",
        daemon=True,
    )
    thread.start()

    if not wait_until_serving(port):
        # The thread is a daemon, so there is nothing to clean up; if waitress
        # failed to bind, the traceback has already gone to stderr.
        raise RuntimeError(
            f"server did not come up on {HOST}:{port} within {STARTUP_TIMEOUT:.0f}s"
        )

    return f"http://{HOST}:{port}"


def shutdown_robot_link():
    """Return the robot to LUT control before the process goes away.

    The streaming thread is a daemon and would simply die with the process,
    leaving the robot holding the last streamed pose until the firmware's
    1000 ms real-time timeout fires. disconnect() sends RT_EXIT explicitly and
    is a no-op when nothing is connected.
    """
    try:
        ROBOT_LINK.disconnect()
    except Exception as error:  # never block the window from closing
        print(f"robot link shutdown failed: {error}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Run Hexapod Link.")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="serve on this port instead of an OS-assigned one",
    )
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="start the server only and print its URL, without opening a window",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="open the webview's developer tools",
    )
    args = parser.parse_args()

    url = start_server(args.port)

    if args.no_window:
        print(f"serving on {url} (ctrl-c to stop)")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            shutdown_robot_link()
        return

    # Imported here so the app can be served (or imported by tests and tools)
    # without pywebview installed.
    import webview

    window = webview.create_window(
        APP_TITLE,
        url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=WINDOW_MIN_SIZE,
        text_select=True,
    )
    # 'closing' fires while the window and the server thread are both still
    # alive, so the RT_EXIT packet actually makes it out. Returning None lets
    # the close proceed.
    window.events.closing += shutdown_robot_link

    webview.start(debug=args.debug, icon=window_icon())


if __name__ == "__main__":
    main()
