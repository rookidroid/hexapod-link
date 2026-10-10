"""Gaits of one's own (hexapod/gait_library.py): a sequence saved by name, to
be put into another later. Each is a keyframe file, so what is saved loads
back as it was, and only for the robot it was made on.
"""

import json

import pytest

from hexapod import gait_library as gl
from hexapod import keyframes as kf
from hexapod.gait_keyframes import gait_keyframes
from settings import GAITS_ENV
from tests.robots import ROBOT_CONFIGS

NOUGAT = ROBOT_CONFIGS["nougat"]
MOCHI = ROBOT_CONFIGS["mochi"]


@pytest.fixture
def gaits_folder(tmp_path, monkeypatch):
    folder = tmp_path / "gaits"
    monkeypatch.setenv(GAITS_ENV, str(folder))
    return folder


def _frames(robot_config, count=3):
    standby = kf.standby_feet(robot_config)
    frames = []
    for index in range(count):
        feet = [[x, y, z + 10.0 * index] for x, y, z in standby]
        frames.append(kf.make_keyframe(feet, 400 + 100 * index, ease=index % 2 == 0))
    return frames


def test_nothing_is_listed_without_a_folder(gaits_folder):
    assert gl.gaits_dir() == gaits_folder
    assert gl.list_gaits(NOUGAT) == []


def test_a_saved_gait_is_listed_and_loads_back(gaits_folder):
    frames = _frames(NOUGAT)
    gait_id = gl.save_gait("  Wave   hello ", frames, NOUGAT)

    assert gl.list_gaits(NOUGAT) == [
        {
            "id": gait_id,
            "name": "Wave hello",
            "count": 3,
            "duration_ms": kf.sequence_duration_ms(frames),
        }
    ]
    loaded = gl.load_gait(gait_id, NOUGAT)
    assert [frame["duration_ms"] for frame in loaded] == [400, 500, 600]
    assert [kf.eases(frame) for frame in loaded] == [True, False, True]
    assert [frame["feet"] for frame in loaded] == [frame["feet"] for frame in frames]


def test_a_gait_file_is_a_keyframe_file(gaits_folder):
    gait_id = gl.save_gait("Twist", gait_keyframes("twist", NOUGAT), NOUGAT)
    text = (gaits_folder / f"{gait_id}.json").read_text(encoding="utf-8")
    assert json.loads(text)["name"] == "Twist"
    assert len(kf.load(text, NOUGAT)) == len(gait_keyframes("twist", NOUGAT))


def test_saving_under_the_same_name_replaces_the_gait(gaits_folder):
    first = gl.save_gait("Dance", _frames(NOUGAT, 2), NOUGAT)
    second = gl.save_gait("dance", _frames(NOUGAT, 4), NOUGAT)
    assert first == second
    assert [gait["count"] for gait in gl.list_gaits(NOUGAT)] == [4]


def test_gaits_are_listed_by_name(gaits_folder):
    for name in ("walk b", "Alpha", "zig"):
        gl.save_gait(name, _frames(NOUGAT), NOUGAT)
    assert [gait["name"] for gait in gl.list_gaits(NOUGAT)] == ["Alpha", "walk b", "zig"]


def test_another_robots_gait_is_not_listed_nor_loaded(gaits_folder):
    gait_id = gl.save_gait("Mine", _frames(NOUGAT), NOUGAT)
    gl.save_gait("Mochi's", _frames(MOCHI), MOCHI)

    assert [gait["name"] for gait in gl.list_gaits(NOUGAT)] == ["Mine"]
    assert [gait["name"] for gait in gl.list_gaits(MOCHI)] == ["Mochi's"]
    with pytest.raises(kf.KeyframeFileError):
        gl.load_gait(gait_id, MOCHI)


def test_a_broken_file_is_left_out(gaits_folder):
    gl.save_gait("Good", _frames(NOUGAT), NOUGAT)
    (gaits_folder / "nougat--broken.json").write_text("{not json", encoding="utf-8")
    (gaits_folder / "nougat--other.json").write_text('{"format": "x"}', encoding="utf-8")
    assert [gait["name"] for gait in gl.list_gaits(NOUGAT)] == ["Good"]


def test_a_keyframe_file_dropped_in_is_listed(gaits_folder):
    gaits_folder.mkdir()
    (gaits_folder / "Nougat_keyframes.json").write_text(
        kf.dump(_frames(NOUGAT), NOUGAT), encoding="utf-8"
    )
    [gait] = gl.list_gaits(NOUGAT)
    assert gait["name"] == "Nougat_keyframes"
    assert len(gl.load_gait(gait["id"], NOUGAT)) == 3


def test_a_gait_is_deleted(gaits_folder):
    gait_id = gl.save_gait("Gone", _frames(NOUGAT), NOUGAT)
    assert gl.delete_gait(gait_id)
    assert gl.list_gaits(NOUGAT) == []
    assert not gl.delete_gait(gait_id)
    with pytest.raises(kf.KeyframeFileError):
        gl.load_gait(gait_id, NOUGAT)


@pytest.mark.parametrize("gait_id", ["../preferences", "..", "a/b", "a\b", ".hidden", "", None])
def test_an_id_cannot_reach_outside_the_folder(gaits_folder, gait_id):
    with pytest.raises(kf.KeyframeFileError):
        gl.load_gait(gait_id, NOUGAT)
    assert not gl.delete_gait(gait_id)


def test_a_gait_needs_a_name_and_keyframes(gaits_folder):
    with pytest.raises(ValueError):
        gl.save_gait("   ", _frames(NOUGAT), NOUGAT)
    with pytest.raises(ValueError):
        gl.save_gait(None, _frames(NOUGAT), NOUGAT)
    with pytest.raises(ValueError):
        gl.save_gait("Empty", [], NOUGAT)
    assert not gaits_folder.exists()


def test_a_long_name_is_cut_short(gaits_folder):
    gl.save_gait("x" * 100, _frames(NOUGAT), NOUGAT)
    assert gl.list_gaits(NOUGAT)[0]["name"] == "x" * gl.MAX_NAME_LENGTH
