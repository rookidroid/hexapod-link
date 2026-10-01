# UI preferences that persist between launches, kept as one small JSON object
# on disk (see PREFERENCES_PATH in settings.py). Reads and writes are best
# effort: a missing or broken file just means the defaults.

import json
import os
from pathlib import Path

from settings import PREFERENCES_ENV, PREFERENCES_PATH

THEMES = ("light", "dark")
DEFAULT_THEME = "light"


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


def save_preference(key, value):
    """Store one preference, keeping the others. Best effort."""
    path = preferences_path()
    preferences = load_preferences()
    preferences[key] = value
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(preferences, indent=2), encoding="utf-8")
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
