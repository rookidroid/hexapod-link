from types import SimpleNamespace

import pytest

from hexapod.preferences import load_window, save_window
from settings import PREFERENCES_ENV
from window_state import SETTLE_S, WindowState, on_a_screen, window_options


@pytest.fixture
def preferences_file(tmp_path, monkeypatch):
    path = tmp_path / "preferences.json"
    monkeypatch.setenv(PREFERENCES_ENV, str(path))
    return path


NOTHING_SAVED = {"x": None, "y": None, "width": None, "height": None, "maximized": False}


def test_no_window_is_saved_at_first(preferences_file):
    assert load_window() == NOTHING_SAVED


def test_the_window_round_trips(preferences_file):
    state = {"x": -1500, "y": 40, "width": 1300.4, "height": 820, "maximized": True}
    assert save_window(state)
    assert load_window() == {**state, "width": 1300}


@pytest.mark.parametrize(
    "contents",
    [
        '{"window": [1]}',
        '{"window": {"x": "left", "y": true, "width": 50, "height": 1e9, "maximized": 1}}',
    ],
)
def test_an_unusable_window_is_ignored(preferences_file, contents):
    preferences_file.write_text(contents, encoding="utf-8")
    assert load_window() == NOTHING_SAVED


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def follow(saved=NOTHING_SAVED):
    clock = Clock()
    return WindowState(saved, clock=clock), clock


def test_moves_and_resizes_are_followed():
    state, clock = follow()
    state._on_moved(10, 20)
    clock.now += 5
    state._on_resized(1200, 800)
    assert state.state() == {"x": 10, "y": 20, "width": 1200, "height": 800, "maximized": False}


def test_maximizing_keeps_the_normal_place():
    state, clock = follow()
    state._on_moved(10, 20)
    state._on_resized(1200, 800)
    clock.now += 5
    # The maximize's own move, then the maximized event, then its resize.
    state._on_moved(0, 0)
    clock.now += 0.01
    state._on_maximized()
    state._on_resized(1920, 1040)
    assert state.state() == {"x": 10, "y": 20, "width": 1200, "height": 800, "maximized": True}

    state._on_restored()
    clock.now += 0.01
    state._on_moved(10, 20)
    assert state.state()["maximized"] is False


def test_changes_well_before_a_maximize_stay():
    state, clock = follow()
    state._on_resized(1200, 800)
    clock.now += SETTLE_S * 4
    state._on_maximized()
    assert state.state()["width"] == 1200


def test_minimizing_keeps_the_normal_place():
    state, clock = follow()
    state._on_moved(10, 20)
    clock.now += 5
    state._on_moved(-32000, -32000)
    state._on_minimized()
    assert state.state()["x"] == 10


def test_coming_back_from_minimized_stays_maximized():
    state, _ = follow({**NOTHING_SAVED, "width": 1200, "maximized": True})
    state._on_minimized()
    state._on_restored()  # GTK, back to maximized
    assert state.state()["maximized"] is True
    state._on_restored()
    assert state.state()["maximized"] is False


def test_opening_maximized_keeps_the_saved_normal_size():
    saved = {"x": 10, "y": 20, "width": 1200, "height": 800, "maximized": True}
    state, _ = follow(saved)
    state._on_resized(1920, 1040)
    assert state.state() == saved


def test_closing_saves_the_state(preferences_file):
    state, _ = follow()
    state._on_moved(10, 20)
    state.save()
    assert load_window() == {**NOTHING_SAVED, "x": 10, "y": 20}


SCREENS = [
    SimpleNamespace(x=0, y=0, width=1920, height=1080),
    SimpleNamespace(x=-1280, y=0, width=1280, height=1024),
]


@pytest.mark.parametrize(
    "x, y, expected",
    [
        (100, 100, True),
        (-1000, 500, True),  # on the second screen
        (1850, 100, False),  # only a sliver on screen
        (100, 1070, False),
        (100, -20, False),  # its top edge above every screen
        (4000, 100, False),  # a screen since unplugged
    ],
)
def test_a_position_must_be_on_a_screen(x, y, expected):
    assert on_a_screen(x, y, 1200, SCREENS) is expected


def test_options_default_without_a_saved_window():
    assert window_options(NOTHING_SAVED, SCREENS, (1440, 900)) == {
        "width": 1440,
        "height": 900,
        "maximized": False,
    }


def test_options_restore_the_saved_window():
    saved = {"x": 100, "y": 50, "width": 1200, "height": 800, "maximized": True}
    assert window_options(saved, SCREENS, (1440, 900), origin=(0, 0)) == saved
    moved = window_options(saved, SCREENS, (1440, 900), origin=(-1280, 0))
    assert (moved["x"], moved["y"]) == (1380, 50)


def test_options_drop_a_position_off_every_screen():
    saved = {"x": 5000, "y": 50, "width": 1200, "height": 800, "maximized": False}
    assert "x" not in window_options(saved, SCREENS, (1440, 900))
    assert "x" not in window_options({**saved, "x": 100}, [], (1440, 900))
