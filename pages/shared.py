import json
from dash import callback, clientside_callback, dcc, html, no_update
from dash.dependencies import Output, Input, State
from widgets.dimensions_ui import (
    DIMENSION_CALLBACK_INPUTS,
    DIMENSION_WIDGET_IDS,
)
from widgets.robot_link_ui import (
    TOPBAR_CONNECTION,
    ROBOT_INFO_ID,
    ROBOT_CONFIG_STORE_ID,
    ROBOT_IP_INPUT_ID,
    ROBOT_CONNECT_BTN_ID,
    ROBOT_POLL_INTERVAL_ID,
    SECTION_CONTROLS_CLASS,
    SECTION_CONTROLS_OFFLINE_CLASS,
    STREAM_CONTROLS_ID,
    STREAM_MAX_STEP_ID,
    STREAM_SWITCH_ID,
)
from widgets.section_maker import make_splitter
from hexapod.robot_link import ROBOT_LINK
from hexapod.preferences import save_layout, save_theme
from hexapod.robot_config import describe, describe_firmware, get_simulator_dimensions
from texts import APP_TITLE, APP_VERSION


# ......................
# Update hexapod dimensions callback
# ......................

DIMENSIONS_HIDDEN_SECTION_ID = "hexapod-dimensions-values"
DIMENSIONS_HIDDEN_SECTION = html.Div(
    id=DIMENSIONS_HIDDEN_SECTION_ID, style={"display": "none"}
)
DIMS_JSON_CALLBACK_OUTPUT = Output(DIMENSIONS_HIDDEN_SECTION_ID, "children")


@callback(DIMS_JSON_CALLBACK_OUTPUT, DIMENSION_CALLBACK_INPUTS)
def update_dimensions(front, side, middle, coxia, femur, tibia):
    dimensions = {
        "front": front or 0,
        "side": side or 0,
        "middle": middle or 0,
        "coxia": coxia or 0,
        "femur": femur or 0,
        "tibia": tibia or 0,
    }

    # A real robot's legs are mounted at the angles it reports, whatever the
    # body measurements are edited to. The generic model has no robot behind
    # it, so its legs keep pointing out from the cog as the body is resized.
    robot_config = ROBOT_LINK.robot_config
    if robot_config["source"] != "generic":
        dimensions["mount_angles"] = get_simulator_dimensions(robot_config)[
            "mount_angles"
        ]
    return json.dumps(dimensions)


# ......................
# The 3D view
#
# The hexapod is drawn by assets/hexapod_view.js (three.js). A scene
# (hexapod/scene.py) goes in the view's store and a clientside callback hands
# it to the view in the browser; the camera stays wherever the user left it.
# ......................


def view_store_id(view_id):
    return f"{view_id}-scene"


def make_view(view_id, scene=None, overlay=None, hud=None, controls=None, drive=None):
    """The element the view draws into, and the store its scene goes in.

    `overlay` is laid over the view's top-right corner, for a button or two
    that act on the view itself; `hud` over its bottom-left, for a readout;
    `controls` over its top-left, for what acts on what the view shows; and
    `drive` over its bottom-right, for driving the robot itself.
    """
    children = [
        html.Div(id=view_id, className="hexapod-view"),
        dcc.Store(id=view_store_id(view_id), data=scene),
        dcc.Store(id=f"{view_id}-ack"),
    ]
    if overlay:
        children.append(html.Div(overlay, className="hexapod-view-overlay"))
    if hud:
        children.append(html.Div(hud, className="hexapod-view-hud"))
    if controls:
        children.append(html.Div(controls, className="hexapod-view-controls"))
    if drive:
        children.append(html.Div(drive, className="hexapod-view-drive"))
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
            DIMENSIONS_HIDDEN_SECTION,
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
STATUS_PILL_ID = "status-pill"
_PILL_BASE_CLASS = "status-pill"


def _pill_class(state):
    return f"{_PILL_BASE_CLASS} {state}"


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
            html.Div(
                "Offline",
                id=STATUS_PILL_ID,
                className=_pill_class("is-offline"),
                title="Disconnected",
                role="status",
            ),
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


# ......................
# Physical robot link callbacks
# ......................


@callback(
    Output(ROBOT_CONNECT_BTN_ID, "children"),
    Output(ROBOT_CONNECT_BTN_ID, "color"),
    Output(ROBOT_CONFIG_STORE_ID, "data"),
    Input(ROBOT_CONNECT_BTN_ID, "n_clicks"),
    State(ROBOT_IP_INPUT_ID, "value"),
    State(ROBOT_CONFIG_STORE_ID, "data"),
    prevent_initial_call=True,
)
def toggle_robot_connection(_n_clicks, ip, config_store):
    """Connect or disconnect. Connecting reads the robot's config first."""
    if ROBOT_LINK.connected:
        ROBOT_LINK.disconnect()
    else:
        ROBOT_LINK.connect(ip)

    # Only a successful connect loads a config; tell everything drawn from the
    # robot's geometry when it has changed.
    version = ROBOT_LINK.config_version
    store = no_update
    if not config_store or config_store.get("version") != version:
        store = {"version": version, "name": ROBOT_LINK.robot_config["name"]}

    if ROBOT_LINK.connected:
        return "Disconnect", "secondary", store
    return "Connect", "primary", store


@callback(
    [Output(widget_id, "value") for widget_id in DIMENSION_WIDGET_IDS]
    + [Output(ROBOT_INFO_ID, "children")],
    Input(ROBOT_CONFIG_STORE_ID, "data"),
)
def follow_robot_config(_config_store):
    """Match the simulator's dimensions to the robot's reported geometry.

    Runs on load as well as on connect: the layout is built once at import, so
    a browser refresh would otherwise show the dimensions of whichever robot
    was known when the app started rather than the one connected since.
    """
    robot_config = ROBOT_LINK.robot_config
    dimensions = get_simulator_dimensions(robot_config)
    return [
        dimensions["front"],
        dimensions["side"],
        dimensions["middle"],
        dimensions["coxia"],
        dimensions["femur"],
        dimensions["tibia"],
        describe(robot_config),
    ]


def firmware_status_text(status):
    """The connected robot's firmware, or nothing while offline."""
    return describe_firmware(status["firmware"]) if status["connected"] else ""


def link_status_text(status):
    """One line describing the link, for the status pill's tooltip."""
    if status["last_error"]:
        return f"⚠ {status['last_error']}"

    if not status["connected"]:
        return "Disconnected"

    mode = "STREAMING" if status["streaming"] else "IDLE (holding)"
    return (
        f"{status['robot_label']} @ {status['ip']} — {mode} — "
        f"{status['packets_sent']} pkts"
    )


@callback(
    Output(STATUS_PILL_ID, "children"),
    Output(STATUS_PILL_ID, "className"),
    Output(STATUS_PILL_ID, "title"),
    Input(ROBOT_POLL_INTERVAL_ID, "n_intervals"),
)
def update_robot_status(_n_intervals):
    """Refresh the status pill in the top bar.

    It reads the summary -- which robot, and whether it is reachable and being
    streamed to -- and its tooltip the detail: the address, mode and packet
    count, and the robot's firmware version.
    """
    status = ROBOT_LINK.status()
    text = link_status_text(status)
    firmware = firmware_status_text(status)

    if status["last_error"]:
        label, state = "Fault", "is-fault"
    elif not status["connected"]:
        label, state = "Offline", "is-offline"
    elif status["streaming"]:
        label, state = f"{status['robot_label']} · Streaming", "is-streaming"
    else:
        label, state = f"{status['robot_label']} · Online", "is-online"

    tooltip = f"{text}\n{firmware}" if firmware else text
    return label, _pill_class(state), tooltip


# ......................
# Stream-to-robot controls
#
# They all drive the one link, so the sync callback re-seeds them from the
# link's state rather than trusting the defaults they were rendered with.
# ......................


@callback(
    Output(STREAM_SWITCH_ID, "value"),
    Input(STREAM_SWITCH_ID, "value"),
    prevent_initial_call=True,
)
def toggle_robot_streaming(streaming):
    ROBOT_LINK.set_streaming(streaming)
    # Reflect back what the link accepted; streaming cannot be enabled while
    # disconnected, so the switch must not appear on in that case.
    return ROBOT_LINK.streaming


@callback(
    Output(STREAM_MAX_STEP_ID, "value"),
    Input(STREAM_MAX_STEP_ID, "value"),
    prevent_initial_call=True,
)
def update_robot_max_step(max_step):
    ROBOT_LINK.set_max_step(max_step)
    return max_step


@callback(
    Output(STREAM_CONTROLS_ID, "className"),
    Output(STREAM_SWITCH_ID, "disabled"),
    Output(STREAM_MAX_STEP_ID, "disabled"),
    Output(STREAM_SWITCH_ID, "value", allow_duplicate=True),
    Output(STREAM_MAX_STEP_ID, "value", allow_duplicate=True),
    Input(ROBOT_POLL_INTERVAL_ID, "n_intervals"),
    State(STREAM_SWITCH_ID, "value"),
    State(STREAM_MAX_STEP_ID, "value"),
    prevent_initial_call="initial_duplicate",
)
def sync_stream_controls(_n_intervals, switch_value, max_step_value):
    """Keep the stream controls honest about the link.

    Offline, none of them has anything to act on, so they are greyed out and
    disabled; the status line above them says why.

    The values are only written back when they disagree with the link -- the
    page was loaded showing its rendered default, or the link dropped
    streaming on its own -- so the ordinary case does not retrigger the
    toggle callbacks every second.
    """
    status = ROBOT_LINK.status()
    offline = not status["connected"]

    streaming = status["streaming"]
    switch = no_update if bool(switch_value) == streaming else streaming

    max_step = status["max_step"]
    max_step_out = no_update if max_step_value == max_step else max_step

    return (
        SECTION_CONTROLS_OFFLINE_CLASS if offline else SECTION_CONTROLS_CLASS,
        offline,
        offline,
        switch,
        max_step_out,
    )
