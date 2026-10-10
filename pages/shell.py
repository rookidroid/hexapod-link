"""The app shell: the top bar, the light and dark themes, the 3D view's
frame, and the workspace grid below the top bar with its splitters.

What goes in them is put together in pages/workspace.py.
"""

import json

from dash import callback, clientside_callback, dcc, html
from dash.dependencies import Input, Output, State

from hexapod.preferences import save_layout, save_theme
from texts import APP_TITLE, APP_VERSION
from widgets.components import make_splitter
from widgets.dimensions_ui import DIMENSIONS_JSON
from widgets.robot_link_ui import STATUS_PILL, TOPBAR_CONNECTION


# ......................
# The 3D view
#
# The hexapod is drawn by assets/hexapod_view.js (three.js). A scene
# (hexapod/scene.py) goes in the view's store and a clientside callback hands
# it to the view in the browser; the camera stays wherever the user left it.
# ......................


def view_store_id(view_id):
    return f"{view_id}-scene"


def view_ack_id(view_id):
    """A store nothing reads: the output of the clientside callbacks that
    only act on the view."""
    return f"{view_id}-ack"


def make_view(view_id, scene=None, overlay=None, hud=None, controls=None, drive=None, tool=None):
    """The element the view draws into, and the store its scene goes in.

    `overlay` is laid over the view's top-right corner, for a button or two
    that act on the view itself; `hud` over its bottom-left, for a readout;
    `controls` over its top-left, for what acts on what the view shows;
    `drive` over its bottom-right, for driving the robot itself; and `tool`
    over the middle of its top edge, for how what is picked is dragged.
    """
    children = [
        html.Div(id=view_id, className="hexapod-view"),
        dcc.Store(id=view_store_id(view_id), data=scene),
        dcc.Store(id=view_ack_id(view_id)),
    ]
    if overlay:
        children.append(html.Div(overlay, className="hexapod-view-overlay"))
    if hud:
        children.append(html.Div(hud, className="hexapod-view-hud"))
    if controls:
        children.append(html.Div(controls, className="hexapod-view-controls"))
    if drive:
        children.append(html.Div(drive, className="hexapod-view-drive"))
    if tool:
        children.append(html.Div(tool, className="hexapod-view-tool"))
    return html.Div(children, className="hexapod-view-frame")


# ......................
# The app shell
#
# One screen: the top bar, then the workspace -- the view, and the dock along
# the bottom. The grid is laid out in the WORKSPACE block of
# assets/industrial.css, which also decides who scrolls: above `lg` the dock
# does, and the view takes whatever room is left; below it the two stack and
# the page scrolls as a whole.
#
# Above `lg` the dock's height can be dragged, by a splitter on its top edge
# (or, focused, with the arrow keys), and double-clicking it puts it back; so
# can the widths of the dock's side columns (POSE_DOCK in widgets/pose_ui.py).
# That is done in the page (assets/workspace_resize.js); the sizes let go of
# come back through the sizes store, to be kept with the preferences and
# served with the page the next time (hexapod_link.py).
# ......................

LAYOUT_SIZES_STORE_ID = "layout-sizes"


def make_workspace(view, dock):
    return html.Main(
        [
            html.Div(view, className="ws-view"),
            html.Div(dock, className="ws-dock"),
            make_splitter("dock", "horizontal", "resize the dock"),
            dcc.Store(id=LAYOUT_SIZES_STORE_ID),
            DIMENSIONS_JSON,
        ],
        className="workspace",
    )


@callback(Input(LAYOUT_SIZES_STORE_ID, "data"), prevent_initial_call=True)
def keep_layout_sizes(sizes):
    """Keep the sizes as a splitter was let go, by preference key
    (hexapod/preferences.py) in pixels, None for one left to the stylesheet."""
    if isinstance(sizes, dict):
        save_layout(sizes)


# The status pill is the app's link readout: whether the robot is reachable,
# which one it is, and whether it is being streamed to. The state modifier
# colours its LED (STATUS PILL in industrial.css); its tooltip has the detail.
def make_topbar(theme):
    return html.Header(
        [
            html.Div(
                [
                    html.Span(APP_TITLE, className="topbar-title"),
                    html.Span(f"v{APP_VERSION}", className="topbar-version"),
                ],
                className="topbar-brand",
            ),
            TOPBAR_CONNECTION,
            STATUS_PILL,
            make_theme_toggle(theme),
        ],
        className="topbar",
    )


# ......................
# Light / dark theme
#
# The theme is a data-theme attribute on <html> (plus data-bs-theme for
# Bootstrap's own components); industrial.css swaps its colour tokens on it.
# hexapod_link.py writes the saved theme into the page before it is served, so
# a dark start never flashes light; these callbacks handle switching after that.
# ......................

THEME_TOGGLE_ID = "theme-toggle"
THEME_STORE_ID = "theme-store"

# What the button offers is the other theme, so it shows that one's icon.
_THEME_TOGGLE_ICON = {"light": "☾", "dark": "☀"}
_THEME_TOGGLE_TITLE = {"light": "Switch to dark theme", "dark": "Switch to light theme"}


def make_theme_toggle(theme):
    """The top bar's button and the store it drives, rendered for `theme`."""
    return html.Div(
        [
            dcc.Store(id=THEME_STORE_ID, data=theme),
            html.Button(
                _THEME_TOGGLE_ICON[theme],
                id=THEME_TOGGLE_ID,
                className="icon-btn",
                title=_THEME_TOGGLE_TITLE[theme],
            ),
        ],
        className="d-flex",
    )


@callback(
    Output(THEME_STORE_ID, "data"),
    Input(THEME_TOGGLE_ID, "n_clicks"),
    State(THEME_STORE_ID, "data"),
    prevent_initial_call=True,
)
def toggle_theme(_n_clicks, theme):
    theme = "light" if theme == "dark" else "dark"
    save_theme(theme)
    return theme


clientside_callback(
    """
    function (theme) {
        var root = document.documentElement;
        root.setAttribute("data-theme", theme);
        root.setAttribute("data-bs-theme", theme);
        return [ICONS[theme], TITLES[theme]];
    }
    """.replace("ICONS", json.dumps(_THEME_TOGGLE_ICON)).replace(
        "TITLES", json.dumps(_THEME_TOGGLE_TITLE)
    ),
    Output(THEME_TOGGLE_ID, "children"),
    Output(THEME_TOGGLE_ID, "title"),
    Input(THEME_STORE_ID, "data"),
    prevent_initial_call=True,
)
