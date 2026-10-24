# UI preferences that persist between launches, kept as one small JSON object
# on disk (see PREFERENCES_PATH in settings.py). Reads and writes are best
# effort: a missing or broken file just means the defaults.

import json
import os
import threading
from pathlib import Path

from settings import PREFERENCES_ENV, PREFERENCES_PATH

THEMES = ("light", "dark")
DEFAULT_THEME = "dark"


def preferences_path():
    return Path(os.environ.get(PREFERENCES_ENV) or PREFERENCES_PATH)


def load_preferences():
    """The saved preferences as a dict, empty if there are none."""
    path = preferences_path()
    try:
        preferences = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        print(f"Ignoring the preferences at {path}: {error}")
        return {}
    return preferences if isinstance(preferences, dict) else {}


# Dash runs callbacks on several threads at once; two saving different
# preferences together must not each write back the file without the other's.
_SAVE_LOCK = threading.RLock()


def save_preference(key, value):
    """Store one preference, keeping the others. Best effort."""
    with _SAVE_LOCK:
        return _save_preference(key, value)


def _save_preference(key, value):
    path = preferences_path()
    preferences = load_preferences()
    preferences[key] = value
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written aside and swapped in, so a page loading meanwhile never
        # reads half a file.
        partial = path.with_name(path.name + ".tmp")
        partial.write_text(json.dumps(preferences, indent=2), encoding="utf-8")
        os.replace(partial, path)
    except OSError as error:
        print(f"Could not save the preferences to {path}: {error}")
        return False
    return True


def load_theme():
    theme = load_preferences().get("theme")
    return theme if theme in THEMES else DEFAULT_THEME


def save_theme(theme):
    if theme not in THEMES:
        raise ValueError(f"unknown theme: {theme!r}")
    return save_preference("theme", theme)


# The workspace's sizes, set by dragging its splitters (assets/workspace_resize.js):
# the height of the dock and the width of the Gaits library beside the
# sequence, in CSS pixels. None for one never dragged,
# or set back with a double-click, which leaves it to the stylesheet.
LAYOUT_SIZES = ("dock_h", "lib_w")
# Far wider than any sensible value either way: only junk is refused here;
# the page keeps them within the window.
LAYOUT_MIN_PX = 100
LAYOUT_MAX_PX = 4000


def _layout_size(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not LAYOUT_MIN_PX <= value <= LAYOUT_MAX_PX:
        return None
    return int(round(value))


def load_layout():
    """Each of LAYOUT_SIZES, in pixels or None."""
    saved = load_preferences().get("layout")
    saved = saved if isinstance(saved, dict) else {}
    return {key: _layout_size(saved.get(key)) for key in LAYOUT_SIZES}


def save_layout(sizes):
    """Store the sizes given, keeping a saved one not among them; one that is
    not a size in range clears it."""
    with _SAVE_LOCK:
        layout = load_layout()
        for key in LAYOUT_SIZES:
            if key in sizes:
                layout[key] = _layout_size(sizes[key])
        return save_preference("layout", layout)


# The overlays on the view that fold away (pages/workspace.py): whether each
# was left open, by hand (assets/hud_panels.js). They all start folded, so the
# view starts clear.
PANELS = ("pose", "controller", "dimensions")


def load_panels():
    """Whether each of PANELS is open."""
    saved = load_preferences().get("panels")
    saved = saved if isinstance(saved, dict) else {}
    return {key: saved.get(key) is True for key in PANELS}


def save_panels(states):
    """Store the states given, keeping a saved one not among them."""
    with _SAVE_LOCK:
        panels = load_panels()
        for key in PANELS:
            if key in states:
                panels[key] = states[key] is True
        return save_preference("panels", panels)


# What the workspace was left showing (pages/last_session.py): the sequence
# and the pose being edited, and the dock's and the view's controls, by name.
# Each value is checked as it is put back, not here.


def load_workspace():
    saved = load_preferences().get("workspace")
    return saved if isinstance(saved, dict) else {}


def save_workspace(values):
    """Store the values given, keeping a saved one not among them."""
    with _SAVE_LOCK:
        workspace = load_workspace()
        workspace.update(values)
        return save_preference("workspace", workspace)


# The window's size and place on the desktop (window_state.py), in logical
# pixels: the size it had out of maximized, and whether it was left maximized.
# None for one never saved, which leaves it to the defaults in hexapod_link.py.
WINDOW_MIN_PX = 100
WINDOW_MAX_PX = 20000
# Screens to the left of or above the primary one have negative coordinates.
WINDOW_MAX_OFFSET_PX = 50000


def _whole_number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not low <= value <= high:
        return None
    return int(round(value))


def load_window():
    """The saved window: x, y, width and height, each in pixels or None, and
    maximized. A place without both its x and its y is no place."""
    saved = load_preferences().get("window")
    saved = saved if isinstance(saved, dict) else {}
    window = {
        key: _whole_number(saved.get(key), -WINDOW_MAX_OFFSET_PX, WINDOW_MAX_OFFSET_PX)
        for key in ("x", "y")
    }
    if window["x"] is None or window["y"] is None:
        window["x"] = window["y"] = None
    for key in ("width", "height"):
        window[key] = _whole_number(saved.get(key), WINDOW_MIN_PX, WINDOW_MAX_PX)
    window["maximized"] = saved.get("maximized") is True
    return window


def save_window(x, y, width, height, maximized):
    """Store the window's size, place and whether it is maximized."""
    return save_preference(
        "window",
        {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "maximized": maximized is True,
        },
    )
