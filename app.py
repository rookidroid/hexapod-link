import mimetypes
import os
import sys
from dash import Dash
from texts import APP_TITLE
from style_settings import EXTERNAL_STYLESHEETS


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

app = Dash(
    __name__,
    assets_folder=ASSETS_PATH,
    external_stylesheets=EXTERNAL_STYLESHEETS,
    suppress_callback_exceptions=True,
    title=APP_TITLE,
)
server = app.server
server.secret_key = os.environ.get("secret_key", "secret")
