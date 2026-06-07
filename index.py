import dash_bootstrap_components as dbc
from dash import dcc, html, callback, Input, Output
from texts import (
    URL_REPO,
    KINEMATICS_PAGE_PATH,
    IK_PAGE_PATH,
    PATTERNS_PAGE_PATH,
    ROOT_PATH,
)
from settings import DEBUG_MODE
from style_settings import GLOBAL_PAGE_STYLE
from app import app
from pages import page_inverse, page_kinematics, page_patterns, page_landing

server = app.server

# .....................
# Navigation partials
# .....................

div_header = dbc.Navbar(
    dbc.Container(
        [
            dbc.NavbarBrand("Hexapod Simulator", href=ROOT_PATH),
            dbc.Nav(
                [
                    dbc.NavItem(dbc.NavLink("Home", href=ROOT_PATH)),
                    dbc.NavItem(dbc.NavLink("Kinematics", href=KINEMATICS_PAGE_PATH)),
                    dbc.NavItem(dbc.NavLink("Inverse Kinematics", href=IK_PAGE_PATH)),
                    dbc.NavItem(dbc.NavLink("Leg Patterns", href=PATTERNS_PAGE_PATH)),
                    dbc.NavItem(dbc.NavLink("👾 Source", href=URL_REPO, target="_blank")),
                ],
                navbar=True,
            ),
        ],
        fluid=True,
    ),
    className="mb-3 scifi-navbar",
    sticky="top",
)

div_footer = html.Footer(
    dbc.Container(
        dbc.Row(
            [
                dbc.Col(
                    dbc.Nav(
                        [
                            dbc.NavItem(dbc.NavLink("Home", href=ROOT_PATH)),
                            dbc.NavItem(dbc.NavLink("Kinematics", href=KINEMATICS_PAGE_PATH)),
                            dbc.NavItem(dbc.NavLink("Inverse Kinematics", href=IK_PAGE_PATH)),
                            dbc.NavItem(dbc.NavLink("Leg Patterns", href=PATTERNS_PAGE_PATH)),
                            dbc.NavItem(dbc.NavLink("👾 Source", href=URL_REPO, target="_blank")),
                        ],
                    ),
                    width=12,
                    md=8,
                ),
                dbc.Col(
                    html.Span("SYS.STATUS: ONLINE ●", className="footer-status"),
                    width=12,
                    md=4,
                    className="text-end d-flex align-items-center justify-content-end",
                ),
            ],
            className="align-items-center",
        ),
        fluid=True,
    ),
    className="scifi-footer",
)

# ....................
# Page layout
# ....................
app.layout = dbc.Container(
    [
        div_header,
        dcc.Location(id="url", refresh=False),
        html.Div(id="page-content"),
        div_footer,
    ],
    fluid=True,
    style=GLOBAL_PAGE_STYLE,
)


# ....................
# URL redirection
# ....................
PAGES = {
    IK_PAGE_PATH: page_inverse.layout,
    KINEMATICS_PAGE_PATH: page_kinematics.layout,
    PATTERNS_PAGE_PATH: page_patterns.layout,
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
