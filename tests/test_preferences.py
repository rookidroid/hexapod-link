import json

import pytest

from hexapod.preferences import (
    DEFAULT_THEME,
    load_theme,
    preferences_path,
    save_preference,
    save_theme,
)
from settings import PREFERENCES_ENV


@pytest.fixture
def preferences_file(tmp_path, monkeypatch):
    path = tmp_path / "preferences.json"
    monkeypatch.setenv(PREFERENCES_ENV, str(path))
    return path


def test_theme_defaults_to_light_without_a_file(preferences_file):
    assert DEFAULT_THEME == "light"
    assert load_theme() == "light"


def test_theme_round_trips(preferences_file):
    assert save_theme("dark")
    assert preferences_path() == preferences_file
    assert json.loads(preferences_file.read_text(encoding="utf-8")) == {"theme": "dark"}
    assert load_theme() == "dark"

    assert save_theme("light")
    assert load_theme() == "light"


def test_saving_keeps_other_preferences(preferences_file):
    assert save_preference("other", 42)
    assert save_theme("dark")
    assert json.loads(preferences_file.read_text(encoding="utf-8")) == {
        "other": 42,
        "theme": "dark",
    }


@pytest.mark.parametrize(
    "contents",
    ["not json", "[1, 2]", '{"theme": "purple"}', '{"theme": null}'],
)
def test_unusable_file_falls_back_to_light(preferences_file, contents):
    preferences_file.write_text(contents, encoding="utf-8")
    assert load_theme() == "light"


def test_unknown_theme_is_rejected(preferences_file):
    with pytest.raises(ValueError):
        save_theme("purple")
    assert not preferences_file.exists()
