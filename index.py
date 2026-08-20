import dash_bootstrap_components as dbc
from dash import dcc, html, callback, Input, Output
from texts import (
    URL_REPO,
    KINEMATICS_PAGE_PATH,
    IK_PAGE_PATH,
    PATTERNS_PAGE_PATH,
    MOTION_PAGE_PATH,
    ROOT_PATH,
)
from settings import DEBUG_MODE
from style_settings import GLOBAL_PAGE_STYLE
from app import app
from pages import page_inverse, page_kinematics, page_patterns, page_landing, page_motion
from pages.shared import (
    GLOBAL_CONTROLS_PANEL,
    GLOBAL_PANEL_TOGGLE_ID,
    GLOBAL_PANEL_TOGGLE_CLASS,
    GLOBAL_PANEL_TOGGLE_LABEL,
)

server = app.server

# .....................
# Navigation partials
# .....................

div_header = dbc.Navbar(
    dbc.Container(
        [
            dbc.NavbarBrand("Hexapod Link", href=ROOT_PATH),
            dbc.Nav(
                [
                    dbc.NavItem(dbc.NavLink("Home", href=ROOT_PATH)),
                    dbc.NavItem(dbc.NavLink("Kinematics", href=KINEMATICS_PAGE_PATH)),
                    dbc.NavItem(dbc.NavLink("Inverse Kinematics", href=IK_PAGE_PATH)),
                    dbc.NavItem(dbc.NavLink("Leg Patterns", href=PATTERNS_PAGE_PATH)),
                    dbc.NavItem(dbc.NavLink("Motion", href=MOTION_PAGE_PATH)),
                    dbc.NavItem(dbc.NavLink("👾 Source", href=URL_REPO, target="_blank")),
                ],
                navbar=True,
            ),
            # Doubles as the app's status readout and as the handle for the
            # global robot panel. ONLINE means the link to the hexapod is up.
            html.Button(
                GLOBAL_PANEL_TOGGLE_LABEL,
                id=GLOBAL_PANEL_TOGGLE_ID,
                className=GLOBAL_PANEL_TOGGLE_CLASS,
                title="Robot link and dimensions",
            ),
        ],
        fluid=True,
    ),
    className="mb-3 scifi-navbar",
    sticky="top",
)

# ....................
# Page layout
# ....................
app.layout = dbc.Container(
    [
        div_header,
        dcc.Location(id="url", refresh=False),
        GLOBAL_CONTROLS_PANEL,
        # Sizing and scrolling live in the PAGE LAYOUT block of scifi.css: it
        # takes a media query to say that this scrolls only once the columns
        # have stacked, and an inline style cannot carry one.
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


# ....................
# URL redirection
# ....................
PAGES = {
    IK_PAGE_PATH: page_inverse.layout,
    KINEMATICS_PAGE_PATH: page_kinematics.layout,
    PATTERNS_PAGE_PATH: page_patterns.layout,
    MOTION_PAGE_PATH: page_motion.layout,
    ROOT_PATH: page_landing.layout,
}


# ....................
# Callback to display page given URL
# ....................
@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    try:
        return PAGES[pathname]
    except KeyError:
        return PAGES[ROOT_PATH]


# ....................
# Run server
# ....................
if __name__ == "__main__":
    app.run(
        debug=DEBUG_MODE, dev_tools_ui=DEBUG_MODE, dev_tools_props_check=DEBUG_MODE
    )
