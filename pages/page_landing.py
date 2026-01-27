import dash_bootstrap_components as dbc
from dash import html
from texts import URL_IMG_LANDING

img = html.Img(src=URL_IMG_LANDING, className="img-fluid")

layout = dbc.Container(
    dbc.Row(
        [
            dbc.Col(img, width=12, md=4),
        ],
        className="py-3",
    ),
    fluid=True,
)
