import json
from types import SimpleNamespace

import pytest

import window_state
from hexapod.preferences import load_window, save_window
from settings import PREFERENCES_ENV
from window_state import WindowState, fit_window, restore_window

DEFAULT = (1440, 900)
MIN = (1024, 700)
PRIMARY = SimpleNamespace(x=0, y=0, width=1920, height=1080)
LEFT = SimpleNamespace(x=-2560, y=0, width=2560, height=1440)


@pytest.fixture
def preferences_file(tmp_path, monkeypatch):
    path = tmp_path / "preferences.json"
    monkeypatch.setenv(PREFERENCES_ENV, str(path))
    return path


def saved(**values):
    window = {"x": None, "y": None, "width": None, "height": None, "maximized": False}
    window.update(values)
    return window


# ---- The preference ----


def test_no_saved_window(preferences_file):
    assert load_window() == saved()


def test_window_round_trips(preferences_file):
    save_window(-2000, 40, 1600, 1000, True)
    assert load_window() == saved(x=-2000, y=40, width=1600, height=1000, maximized=True)


@pytest.mark.parametrize(
    "contents",
    [
        {"window": "big"},
        {"window": {"x": "1", "y": 2, "width": True, "height": 5}},
        {"window": {"x": 10, "width": 50, "height": 10**6, "maximized": "yes"}},
    ],
)
def test_unusable_window_is_ignored(preferences_file, contents):
    preferences_file.write_text(json.dumps(contents), encoding="utf-8")
    assert load_window() == saved()


# ---- Fitting it to the screens ----


def test_defaults_open_centred():
    assert fit_window(saved(), DEFAULT, MIN, [PRIMARY]) == (None, None, 1440, 900)


def test_saved_place_on_a_screen_is_kept():
    window = saved(x=-2000, y=100, width=1600, height=1000)
    assert fit_window(window, DEFAULT, MIN, [PRIMARY, LEFT]) == (-2000, 100, 1600, 1000)


def test_place_on_a_screen_since_gone_is_dropped():
    window = saved(x=-2000, y=100, width=1600, height=1000)
    assert fit_window(window, DEFAULT, MIN, [PRIMARY]) == (None, None, 1600, 1000)


def test_window_whose_top_is_off_screen_is_recentred():
    window = saved(x=100, y=-200, width=1600, height=1000)
    assert fit_window(window, DEFAULT, MIN, [PRIMARY])[:2] == (None, None)


def test_size_is_kept_within_the_screen_and_over_the_minimum():
    big = saved(x=0, y=0, width=3000, height=2000)
    assert fit_window(big, DEFAULT, MIN, [PRIMARY]) == (0, 0, 1920, 1080)
    small = saved(width=200, height=200)
    assert fit_window(small, DEFAULT, MIN, [PRIMARY])[2:] == MIN


def test_unknown_screens_keep_the_saved_place():
    window = saved(x=-2000, y=100, width=1600, height=1000)
    assert fit_window(window, DEFAULT, MIN, []) == (-2000, 100, 1600, 1000)


# ---- Following the window ----


class FakeEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def set(self, *args):
        for handler in self.handlers:
            handler(*args)


def fake_window():
    names = ("maximized", "minimized", "restored", "moved", "resized", "closing")
    return SimpleNamespace(events=SimpleNamespace(**{n: FakeEvent() for n in names}))


@pytest.fixture
def followed(preferences_file, monkeypatch):
    monkeypatch.setattr(window_state.sys, "platform", "linux")
    state = WindowState(None, None, 1440, 900)
    window = fake_window()
    state.attach(window)
    return window


def test_moves_and_resizes_are_saved_on_close(followed):
    followed.events.moved.set(30, 40)
    followed.events.resized.set(1500, 950)
    followed.events.closing.set()
    assert load_window() == saved(x=30, y=40, width=1500, height=950)


def test_a_maximized_window_keeps_its_restored_size(followed, monkeypatch):
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(window_state.time, "monotonic", lambda: clock.now)
    followed.events.moved.set(30, 40)
    followed.events.resized.set(1500, 950)
    clock.now += 5
    # What the maximize moves, before the maximize itself is heard of...
    followed.events.moved.set(0, 0)
    followed.events.resized.set(1920, 1050)
    followed.events.maximized.set()
    # ...and while it is maximized.
    followed.events.resized.set(1920, 1040)
    followed.events.closing.set()
    assert load_window() == saved(x=30, y=40, width=1500, height=950, maximized=True)


def test_restored_window_is_followed_again(followed):
    followed.events.maximized.set()
    followed.events.restored.set()
    followed.events.moved.set(5, 6)
    followed.events.closing.set()
    assert load_window() == saved(x=5, y=6, width=1440, height=900)


def test_restore_window_reads_the_saved_one(preferences_file):
    save_window(-2000, 100, 1600, 1000, True)
    state, maximized = restore_window(DEFAULT, MIN, [PRIMARY, LEFT])
    assert maximized
    assert state.geometry() == (-2000, 100, 1600, 1000)
