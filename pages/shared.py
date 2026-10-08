import json
import dash_bootstrap_components as dbc
from dash import callback, clientside_callback, dcc, html, no_update
from dash.dependencies import Output, Input, State
from dash.exceptions import PreventUpdate
from widgets.dimensions_ui import (
    DIMENSION_CALLBACK_INPUTS,
    DIMENSION_WIDGET_IDS,
    DIMENSIONS_WIDGETS_SECTION,
)
from widgets.robot_link_ui import (
    ROBOT_LINK_WIDGETS_SECTION,
    ROBOT_INFO_ID,
    ROBOT_FIRMWARE_ID,
    ROBOT_CONFIG_STORE_ID,
    ROBOT_IP_INPUT_ID,
    ROBOT_CONNECT_BTN_ID,
    ROBOT_STATUS_ID,
    ROBOT_POLL_INTERVAL_ID,
    SECTION_CONTROLS_CLASS,
    SECTION_CONTROLS_OFFLINE_CLASS,
    make_stream_control_ids,
    make_stream_controls_section,
)
from hexapod.const import BASE_SCENE
from hexapod.robot_link import ROBOT_LINK
from hexapod.preferences import save_theme
from hexapod.robot_config import describe, describe_firmware, get_simulator_dimensions


# ......................
# Update hexapod dimensions callback
# ......................

DIMENSIONS_HIDDEN_SECTION_ID = "hexapod-dimensions-values"
DIMENSIONS_HIDDEN_SECTION = html.Div(
    id=DIMENSIONS_HIDDEN_SECTION_ID, style={"display": "none"}
)
DIMS_JSON_CALLBACK_INPUT = Input(DIMENSIONS_HIDDEN_SECTION_ID, "children")
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
# Every page draws the hexapod with assets/hexapod_view.js (three.js). A page
# puts a scene (hexapod/scene.py) in the view's store and this hands it to the
# view in the browser; the camera stays wherever the user left it.
# ......................


def view_store_id(view_id):
    return f"{view_id}-scene"


def make_view(view_id, scene=None):
    """The element the view draws into, and the store its scene goes in."""
    return html.Div(
        [
            html.Div(id=view_id, className="hexapod-view"),
            dcc.Store(id=view_store_id(view_id), data=scene),
            dcc.Store(id=f"{view_id}-ack"),
        ],
        className="hexapod-view-frame",
    )


def register_view(view_id, zoom=True):
    """Draw whatever lands in the view's store.

    `zoom=False` leaves the mouse wheel to the page, for a view in a page that
    scrolls. The pose editor wires its view up itself, since it switches it
    between editing and previewing (pages/page_poser.py).
    """
    clientside_callback(
        """
        function(scene) {
            if (window.hexapodView && scene) {
                window.hexapodView.render(%s, scene, {zoom: %s});
            }
            return window.dash_clientside.no_update;
        }
        """
        % (json.dumps(view_id), "true" if zoom else "false"),
        Output(f"{view_id}-ack", "data"),
        Input(view_store_id(view_id), "data"),
    )


# ......................
# Make uniform layout
# View on the right, controls on the left
#
# The height rules that make this one screenful -- who scrolls, who fills --
# are in the PAGE LAYOUT block of assets/industrial.css, because they only hold
# above the `lg` breakpoint and inline styles cannot carry a media query.
# ......................


def make_standard_page_layout(view_id, sidebar_sections):
    """Sidebar on the left, the 3D view on the right, already wired up.

    The view starts on the neutral hexapod, and keeps it if the page's first
    pose cannot be drawn, rather than starting as an empty screen.
    """
    register_view(view_id)
    sidebar = dbc.Col(
        dbc.Card(
            dbc.CardBody(sidebar_sections),
            className="ind-card page-panel flex-grow-1",
        ),
        width=12,
        lg=4,
        className="page-sidebar mb-3 mb-lg-0 d-flex flex-column",
    )
    view = dbc.Col(
        html.Div(make_view(view_id, BASE_SCENE), className="graph-container flex-grow-1"),
        width=12,
        lg=8,
        className="page-plot d-flex flex-column",
    )

    return dbc.Row([sidebar, view], className="page-row flex-grow-1 m-0")


def make_scrollable_page(children):
    """Wrap a document-style page so it can scroll inside the fixed app shell.

    The 3D view pages are one screenful by design, so above `lg` the shell does
    not scroll -- see the PAGE LAYOUT block in assets/industrial.css. A page that is
    taller than the viewport therefore has to bring its own scroll region, or
    its bottom is simply cut off with no way to reach it.
    """
    return html.Div(children, className="page-scroll")


# ......................
# Make standard sidebar
# ......................


def make_standard_page_sidebar(
    message_section_id,
    params_hidden_section_id,
    params_widgets_section,
    robot_section=None,
):
    """Sidebar holding only what is specific to one page.

    Robot dimensions and the link to the hardware are deliberately absent: they
    describe the robot rather than the page, so they live in
    GLOBAL_CONTROLS_PANEL, mounted once for the whole app. Controls that act on
    what this page is showing -- streaming its pose, running its motion -- go
    in `robot_section`, below the page's message, so a solved pose or an alert
    sits right under the controls that produced it.
    """
    params_hidden_section = html.Div(
        id=params_hidden_section_id, style={"display": "none"}
    )
    message_section = html.Div(id=message_section_id)

    sections = [params_widgets_section, message_section]
    if robot_section is not None:
        sections.append(robot_section)
    sections.append(params_hidden_section)
    return sections


# ......................
# Global controls panel
#
# Dimensions and the robot link describe one robot, not one page, so they are
# mounted once outside the routed page content. Keeping them here means their
# values survive navigation instead of being rebuilt at defaults on every page
# change, and there is only ever one connect button and one robot.
#
# It is a drawer rather than a column so that no page has to give up layout
# space for it and the landing page can reach it too.
#
# Deliberately not a dbc.Offcanvas: that unmounts its children while closed, so
# every callback wired to these widgets -- including the one that publishes the
# dimensions the pages plot from -- would stop firing whenever the drawer was
# shut. This one is always mounted and only slid out of view by CSS.
# ......................

GLOBAL_PANEL_ID = "global-controls-panel"
GLOBAL_PANEL_TOGGLE_ID = "global-controls-toggle"
GLOBAL_PANEL_CLOSE_ID = "global-controls-close"

# The navbar button is also the app's status readout: ONLINE means the link to
# the hexapod is up, OFFLINE means it is not. The state modifier drives the LED
# and the accent bar in industrial.css.
_TOGGLE_BASE_CLASS = "ind-status-btn"


def _toggle_label(state):
    return f"Robot: {state}"


def _toggle_class(state):
    return f"{_TOGGLE_BASE_CLASS} {state}"


GLOBAL_PANEL_TOGGLE_LABEL = _toggle_label("OFFLINE")
GLOBAL_PANEL_TOGGLE_CLASS = _toggle_class("is-offline")

_PANEL_CLASS = "global-drawer"
_PANEL_CLASS_OPEN = "global-drawer global-drawer-open"

_panel_header = html.Div(
    [
        html.H6("Robot", className="mb-0"),
        dbc.Button(
            "✕",
            id=GLOBAL_PANEL_CLOSE_ID,
            color="link",
            className="p-0 fw-bold text-decoration-none",
        ),
    ],
    className="d-flex justify-content-between align-items-center mb-3",
)

GLOBAL_CONTROLS_PANEL = html.Div(
    [
        _panel_header,
        DIMENSIONS_WIDGETS_SECTION,
        ROBOT_LINK_WIDGETS_SECTION,
        DIMENSIONS_HIDDEN_SECTION,
    ],
    id=GLOBAL_PANEL_ID,
    className=_PANEL_CLASS,
)


@callback(
    Output(GLOBAL_PANEL_ID, "className"),
    Input(GLOBAL_PANEL_TOGGLE_ID, "n_clicks"),
    Input(GLOBAL_PANEL_CLOSE_ID, "n_clicks"),
    State(GLOBAL_PANEL_ID, "className"),
    prevent_initial_call=True,
)
def toggle_global_panel(_toggle_clicks, _close_clicks, class_name):
    if class_name == _PANEL_CLASS_OPEN:
        return _PANEL_CLASS
    return _PANEL_CLASS_OPEN


def register_open_panel_button(button_id):
    """Wire a button on some page to open the global ROBOT drawer.

    A separate callback rather than another Input on the toggle above: that one
    is registered for the whole app, and a callback whose Input is missing from
    the current page does not fire at all -- adding the landing page's button
    there would stop the navbar handle working on every other page.
    """

    @callback(
        Output(GLOBAL_PANEL_ID, "className", allow_duplicate=True),
        Input(button_id, "n_clicks"),
        prevent_initial_call=True,
    )
    def open_global_panel(n_clicks):
        # `prevent_initial_call` does not cover this one. The button arrives as
        # the output of the page-routing callback, and Dash fires callbacks for
        # components another callback has just added -- so without this guard
        # the drawer slid open by itself every time the page was opened.
        if not n_clicks:
            raise PreventUpdate
        return _PANEL_CLASS_OPEN


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
    """The navbar button and the store it drives, rendered for `theme`."""
    return html.Div(
        [
            dcc.Store(id=THEME_STORE_ID, data=theme),
            html.Button(
                _THEME_TOGGLE_ICON[theme],
                id=THEME_TOGGLE_ID,
                className="ind-theme-btn",
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
#
# Registered once here, against the single set of widgets in the global panel.
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
    """One line describing the link, shared by the panel and the page sections."""
    if status["last_error"]:
        return f"⚠ {status['last_error']}", "text-danger"

    if not status["connected"]:
        return "Disconnected", "text-muted"

    mode = "STREAMING" if status["streaming"] else "IDLE (holding)"
    text = (
        f"● {status['robot_label']} @ {status['ip']} — {mode} — "
        f"{status['packets_sent']} pkts"
    )
    return text, "text-success" if status["streaming"] else "text-info"


@callback(
    Output(ROBOT_STATUS_ID, "children"),
    Output(ROBOT_STATUS_ID, "className"),
    Output(ROBOT_FIRMWARE_ID, "children"),
    Output(GLOBAL_PANEL_TOGGLE_ID, "children"),
    Output(GLOBAL_PANEL_TOGGLE_ID, "className"),
    Input(ROBOT_POLL_INTERVAL_ID, "n_intervals"),
)
def update_robot_status(_n_intervals):
    """Refresh the detail line in the panel and the navbar status readout.

    The navbar carries the summary -- whether the robot is reachable -- so link
    state is legible from any page without opening the drawer; the detail line
    inside the drawer carries the address, mode and packet count, with the
    robot's firmware version on its own line.
    """
    status = ROBOT_LINK.status()
    text, colour_class = link_status_text(status)
    base_class = "small font-monospace text-center "

    if status["last_error"]:
        state = ("FAULT", "is-fault")
    elif not status["connected"]:
        state = ("OFFLINE", "is-offline")
    elif status["streaming"]:
        state = ("ONLINE", "is-streaming")
    else:
        state = ("ONLINE", "is-online")

    return (
        text,
        base_class + colour_class,
        firmware_status_text(status),
        _toggle_label(state[0]),
        _toggle_class(state[1]),
    )


# ......................
# Stream-to-robot controls
#
# Built and registered per page, because streaming the pose only means anything
# where a pose is being solved. Each page owns its own widgets; they all drive
# the one link, so the sync callback below re-seeds them from the link's state
# rather than trusting the defaults they were rendered with.
# ......................


def make_stream_controls(page_key):
    ids = make_stream_control_ids(page_key)
    section = make_stream_controls_section(ids)

    @callback(
        Output(ids["switch"], "value"),
        Input(ids["switch"], "value"),
        prevent_initial_call=True,
    )
    def toggle_robot_streaming(streaming):
        ROBOT_LINK.set_streaming(streaming)
        # Reflect back what the link accepted; streaming cannot be enabled while
        # disconnected, so the switch must not appear on in that case.
        return ROBOT_LINK.streaming

    @callback(
        Output(ids["max_step"], "value"),
        Input(ids["max_step"], "value"),
        prevent_initial_call=True,
    )
    def update_robot_max_step(max_step):
        ROBOT_LINK.set_max_step(max_step)
        return max_step

    @callback(
        Output(ids["switch"], "value", allow_duplicate=True),
        Input(ids["relax"], "n_clicks"),
        prevent_initial_call=True,
    )
    def relax_robot(_n_clicks):
        ROBOT_LINK.relax()
        return False

    @callback(
        Output(ids["status"], "children"),
        Output(ids["status"], "className"),
        Output(ids["controls"], "className"),
        Output(ids["switch"], "disabled"),
        Output(ids["relax"], "disabled"),
        Output(ids["max_step"], "disabled"),
        Output(ids["switch"], "value", allow_duplicate=True),
        Output(ids["max_step"], "value", allow_duplicate=True),
        Input(ids["interval"], "n_intervals"),
        State(ids["switch"], "value"),
        State(ids["max_step"], "value"),
        prevent_initial_call=True,
    )
    def sync_stream_controls(_n_intervals, switch_value, max_step_value):
        """Keep this page's widgets honest about the one shared link.

        Offline, none of these controls has anything to act on, so they are
        greyed out and disabled; the status line above them says why.

        The values are only written back when they disagree with the link --
        the page was arrived at showing its rendered default, or the link
        dropped streaming on its own -- so the ordinary case does not retrigger
        the toggle callbacks every second.
        """
        status = ROBOT_LINK.status()
        text, colour_class = link_status_text(status)
        offline = not status["connected"]

        streaming = status["streaming"]
        switch = no_update if bool(switch_value) == streaming else streaming

        max_step = status["max_step"]
        max_step_out = no_update if max_step_value == max_step else max_step

        return (
            text,
            "small font-monospace text-center " + colour_class,
            SECTION_CONTROLS_OFFLINE_CLASS if offline else SECTION_CONTROLS_CLASS,
            offline,
            offline,
            offline,
            switch,
            max_step_out,
        )

    return section


# ......................
# Make outputs and inputs for page update callbacks
# .....................


def make_standard_page_callback_params(view_id, params_section_id, message_section_id):
    """Outputs and inputs of a page's update callback.

    It takes the dimensions and the page's own parameters, and returns the
    scene to draw and the message to show. On an error it returns no_update
    for the scene, so the last pose that worked stays on screen.
    """
    outputs = [
        Output(view_store_id(view_id), "data"),
        Output(message_section_id, "children"),
    ]
    inputs = [DIMS_JSON_CALLBACK_INPUT, Input(params_section_id, "children")]
    return outputs, inputs
