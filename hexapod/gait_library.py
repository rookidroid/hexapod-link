# Gaits of one's own: a whole sequence saved under a name, to be put into
# another sequence the way one of the robot's gaits is (the dock's Gaits
# library, pages/pose.py).
#
# Each is a keyframe file, as Save… writes it (hexapod/keyframes.py), with its
# name added, in GAITS_DIR (settings.py). So a gait's file loads with Load…
# too, and a keyframe file dropped in the folder shows up as a gait. Foot
# positions only fit the robot they were placed on, so a gait belongs to one
# robot: the others' are not listed, and are refused if asked for.
#
# The library is best effort, like the preferences (hexapod/preferences.py):
# a file that cannot be read is left out of the list rather than breaking it.

import json
import os
import re
from pathlib import Path

from hexapod import keyframes as kf
from settings import GAITS_DIR, GAITS_ENV

MAX_NAME_LENGTH = 40

# What a gait's id may be: a file name in the folder, without a path separator
# or a leading dot, so it cannot point anywhere else. Ids made here are
# narrower (gait_id); this lets a file dropped in by hand be listed too.
_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


def gaits_dir():
    return Path(os.environ.get(GAITS_ENV) or GAITS_DIR)


def clean_name(name):
    """The name a gait is kept under: trimmed, its spaces collapsed, and not
    too long. Raises ValueError for one with nothing in it."""
    name = " ".join(str(name or "").split())[:MAX_NAME_LENGTH].strip()
    if not name:
        raise ValueError("Give the gait a name.")
    return name


def gait_id(name, robot_config):
    """The gait's id, and its file's name without the .json: the robot's name
    and the gait's, as letters, digits and dashes. A gait saved under the name
    of one already there replaces it."""
    slug = re.sub(r"[^a-z0-9]+", "-", clean_name(name).lower()).strip("-") or "gait"
    robot = re.sub(r"[^a-z0-9]+", "-", str(robot_config["name"]).lower()).strip("-")
    return f"{robot}--{slug}"


def _path(gait_id):
    if not isinstance(gait_id, str) or not _ID_PATTERN.fullmatch(gait_id):
        raise kf.KeyframeFileError("No such gait.")
    return gaits_dir() / f"{gait_id}.json"


def _read(path, robot_config):
    """(name, keyframes) from a gait's file; raises KeyframeFileError for one
    that is not a gait of this robot, OSError for one that cannot be read."""
    text = path.read_text(encoding="utf-8")
    keyframes = kf.load(text, robot_config)
    name = json.loads(text).get("name")
    return (name if isinstance(name, str) and name.strip() else path.stem), keyframes


def list_gaits(robot_config):
    """This robot's gaits, by name: [{"id", "name", "count", "duration_ms"}]."""
    folder = gaits_dir()
    try:
        paths = sorted(folder.glob("*.json"))
    except OSError:
        return []
    gaits = []
    for path in paths:
        if not _ID_PATTERN.fullmatch(path.stem):
            continue
        try:
            name, keyframes = _read(path, robot_config)
        except (OSError, ValueError):
            continue
        if not keyframes:
            continue
        gaits.append(
            {
                "id": path.stem,
                "name": name,
                "count": len(keyframes),
                "duration_ms": kf.sequence_duration_ms(keyframes),
            }
        )
    return sorted(gaits, key=lambda gait: (gait["name"].lower(), gait["id"]))


def load_gait(gait_id, robot_config):
    """A gait's keyframes. Raises KeyframeFileError for one that is not there
    or not this robot's."""
    try:
        _, keyframes = _read(_path(gait_id), robot_config)
    except FileNotFoundError as error:
        raise kf.KeyframeFileError("That gait is not there any more.") from error
    except OSError as error:
        raise kf.KeyframeFileError(f"Could not read the gait: {error}") from error
    return keyframes


def save_gait(name, keyframes, robot_config):
    """Keep the keyframes as a gait, replacing one of the same name; its id.

    Raises ValueError with no name or no keyframes, OSError if it cannot be
    written."""
    name = clean_name(name)
    if not keyframes:
        raise ValueError("Build a sequence first: there is nothing to save.")
    document = json.loads(kf.dump(keyframes, robot_config))
    document["name"] = name
    new_id = gait_id(name, robot_config)
    path = _path(new_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return new_id


def delete_gait(gait_id):
    """Remove a gait; whether there was one to remove."""
    try:
        _path(gait_id).unlink()
    except (FileNotFoundError, kf.KeyframeFileError):
        return False
    return True
