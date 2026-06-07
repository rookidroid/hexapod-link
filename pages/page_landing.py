import dash_bootstrap_components as dbc
from dash import html
from texts import (
    URL_IMG_LANDING,
    KINEMATICS_PAGE_PATH,
    IK_PAGE_PATH,
    PATTERNS_PAGE_PATH,
)

img = html.Img(src=URL_IMG_LANDING, className="img-fluid scifi-landing-img")

# Hero section
hero = html.Div(
    [
        html.H1(
            "HEXAPOD LINK",
            className="display-5 scifi-hero-title",
        ),
        html.P(
            "INITIALIZING ROBOTICS ENGINE...",
            className="scifi-hero-subtitle mt-2",
        ),
        html.Div(className="scifi-hero-hr"),
        html.P(
            "Advanced hexapod control interface. "
            "Explore forward kinematics, inverse kinematics, "
            "and leg gait patterns in real-time 3D.",
            style={"color": "#475569", "fontSize": "1rem", "lineHeight": "1.6"},
        ),
    ],
    className="glass-panel-light p-4",
    style={"borderRadius": "12px"},
)

# Feature cards
def _feature(icon, title, desc, href):
    return dbc.Col(
        html.A(
            html.Div(
                [
                    html.Div(icon, className="feature-icon"),
                    html.Div(title, className="feature-title"),
                    html.Div(desc, className="feature-desc"),
                ],
                className="card feature-card p-3",
            ),
            href=href,
            style={"textDecoration": "none"},
        ),
        width=12,
        md=4,
        className="mb-3",
    )


features_row = dbc.Row(
    [
        _feature(
            "⚙️", "Kinematics",
            "Control each joint angle independently",
            KINEMATICS_PAGE_PATH,
        ),
        _feature(
            "🎯", "Inverse Kinematics",
            "Set body pose & compute joint angles",
            IK_PAGE_PATH,
        ),
        _feature(
            "🦿", "Leg Patterns",
            "Uniform leg poses with alpha, beta, gamma",
            PATTERNS_PAGE_PATH,
        ),
    ],
    className="mt-4",
)

layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(img, width=12, md=5, className="mb-4 mb-md-0"),
                dbc.Col(hero, width=12, md=7),
            ],
            className="py-5 align-items-center",
        ),
        features_row,
    ],
    fluid=True,
)
