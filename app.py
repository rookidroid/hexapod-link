import os
from dash import Dash
from texts import APP_TITLE
from style_settings import EXTERNAL_STYLESHEETS

app = Dash(
    __name__,
    external_stylesheets=EXTERNAL_STYLESHEETS,
    suppress_callback_exceptions=True,
    title=APP_TITLE,
)
server = app.server
server.secret_key = os.environ.get("secret_key", "secret")
