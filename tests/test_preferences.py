import json

import pytest

from hexapod.preferences import (
    DEFAULT_THEME,
    load_layout,
    load_theme,
    preferences_path,
    save_layout,
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


NO_LAYOUT = {"panel_w": None, "dock_h": None, "lib_w": None, "run_w": None}


def test_layout_defaults_to_the_stylesheets(preferences_file):
    assert load_layout() == NO_LAYOUT


def test_layout_sizes_are_saved_one_at_a_time(preferences_file):
    assert save_theme("dark")
    assert save_layout({"panel_w": 412.4, "n": 123})
    assert save_layout({"dock_h": 260, "run_w": 380})
    assert load_layout() == {**NO_LAYOUT, "panel_w": 412, "dock_h": 260, "run_w": 380}
    assert load_theme() == "dark"

    # Set back with a double-click.
    assert save_layout({"panel_w": None, "lib_w": 250})
    assert load_layout() == {**NO_LAYOUT, "dock_h": 260, "lib_w": 250, "run_w": 380}


@pytest.mark.parametrize("value", [None, "300", True, -5, 50, 10_000, float("nan")])
def test_a_size_out_of_range_is_not_kept(preferences_file, value):
    save_layout({"dock_h": 300})
    save_layout({"dock_h": value})
    assert load_layout()["dock_h"] is None


@pytest.mark.parametrize(
    "contents", ['{"layout": [1]}', '{"layout": {"panel_w": "wide", "dock_h": {}}}']
)
def test_an_unusable_layout_is_ignored(preferences_file, contents):
    preferences_file.write_text(contents, encoding="utf-8")
    assert load_layout() == NO_LAYOUT
