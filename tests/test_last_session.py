import json

import pytest
from dash import dcc, html

from hexapod import pose_layers as pl
from hexapod.keyframes import make_keyframe, standby_feet
from hexapod.preferences import load_workspace, save_workspace
from hexapod.robot_link import ROBOT_LINK
from pages import last_session
from settings import PREFERENCES_ENV


@pytest.fixture
def preferences_file(tmp_path, monkeypatch):
    path = tmp_path / "preferences.json"
    monkeypatch.setenv(PREFERENCES_ENV, str(path))
    return path


def _pose():
    state = pl.standby_state()
    return {"robot": "nougat", "state": state, "feet": [[1.0, 2.0, 3.0]] * 6, "seq": 4}


def _keyframes():
    feet = standby_feet(ROBOT_LINK.robot_config)
    return {"robot": "nougat", "keyframes": [make_keyframe(feet, 500), make_keyframe(feet, 300)]}


def test_workspace_values_are_saved_one_at_a_time(preferences_file):
    save_workspace({"speed": 120})
    save_workspace({"loop": ["loop"]})
    assert load_workspace() == {"speed": 120, "loop": ["loop"]}


def test_usable_values_come_back(preferences_file):
    values = {
        "pose": _pose(),
        "keyframes": json.loads(json.dumps(_keyframes())),
        "selected": 1,
        "body_mode": "rotate",
        "gait_source": "mine",
        "gait_name": "my walk",
        "duration": 750,
        "ease": "linear",
        "speed": 120,
        "loop": ["loop"],
        "robot_ip": "10.0.0.7",
    }
    save_workspace(values)
    assert last_session.saved_values() == values


def test_unusable_values_are_dropped(preferences_file):
    save_workspace(
        {
            "pose": {"robot": "nougat", "state": "x", "feet": []},
            "keyframes": {"robot": "nougat", "keyframes": [{"feet": "no"}]},
            "selected": -1,
            "body_mode": "spin",
            "gait_source": True,
            "gait_name": "x" * 41,
            "duration": 1e9,
            "ease": ["sometimes"],
            "speed": float("nan"),
            "loop": "loop",
            "robot_ip": 7,
        }
    )
    assert last_session.saved_values() == {}


def test_nothing_selected_comes_back_too(preferences_file):
    save_workspace({"selected": None})
    assert last_session.saved_values() == {"selected": None}


def _layout():
    def component(component_id, prop):
        if prop == "data":
            return dcc.Store(id=component_id, data=None)
        return dcc.Input(id=component_id, value="default")

    return html.Div(
        [component(component_id, prop) for component_id, prop, _ in last_session.FIELDS.values()]
    )


def test_restore_puts_values_back_and_others_to_their_defaults(preferences_file, monkeypatch):
    monkeypatch.setattr(last_session, "_defaults", {})
    layout = _layout()
    save_workspace({"speed": 120, "gait_source": "mine"})
    last_session.restore(layout)
    assert layout["pose-speed"].value == 120
    assert layout["pose-gait-source"].value == "mine"
    assert layout["pose-loop"].value == "default"

    preferences_file.unlink()
    last_session.restore(layout)
    assert layout["pose-speed"].value == "default"


def test_dimensions_come_back_only_on_their_robot(preferences_file):
    values = {"front": 40, "side": 70, "middle": 60, "coxia": 38, "femur": 77, "tibia": 93}
    save_workspace({"dimensions": {"robot": "nougat", "values": values}})
    assert last_session.saved_dimensions("nougat") == values
    assert last_session.saved_dimensions("mochi") is None

    save_workspace({"dimensions": {"robot": "nougat", "values": {**values, "femur": None}}})
    assert last_session.saved_dimensions("nougat") is None


def test_the_link_gets_its_speeds_back(preferences_file, monkeypatch):
    calls = []
    monkeypatch.setattr(ROBOT_LINK, "set_max_step", lambda v: calls.append(("max_step", v)))
    monkeypatch.setattr(ROBOT_LINK, "set_motion_speed", lambda v: calls.append(("speed", v)))
    save_workspace({"max_step": 12, "drive_speed": "fast"})
    last_session.restore_robot_link()
    assert calls == [("max_step", 12)]
