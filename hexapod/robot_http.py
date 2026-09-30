# HTTP client for the routes the ESP32 firmware serves on port 80.
#
# The UDP link is one-way and carries motion; everything that needs an answer
# goes over HTTP instead: the robot's own config (GET /robot_config), the gait
# playback speed and the servo calibration offsets. These are the same routes
# the firmware's built-in web page uses, so nothing here is private to this app.
#
# The robot address may carry an HTTP port ("127.0.0.1:8080"). The firmware
# always listens on 80, but a stand-in robot on a development machine usually
# cannot bind it, and the UDP side ignores the port either way.

import json
import urllib.error
import urllib.parse
import urllib.request

from settings import ROBOT_HTTP_PORT, ROBOT_HTTP_TIMEOUT_S


class RobotHttpError(Exception):
    """A route could not be reached, or answered with an error."""


def split_address(address):
    """Split "host[:port]" into (host, http_port)."""
    address = (address or "").strip()
    host, sep, port = address.rpartition(":")
    if sep and port.isdigit() and host:
        return host, int(port)
    return address, ROBOT_HTTP_PORT


def robot_url(address, path):
    host, port = split_address(address)
    netloc = host if port == 80 else f"{host}:{port}"
    return f"http://{netloc}{path}"


def _request(address, path, method="GET", body=None, timeout=None):
    url = robot_url(address, path)
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif method == "POST":
        # The ESP32 WebServer waits for a body on a POST without a length.
        data = b""

    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(
            request, timeout=timeout or ROBOT_HTTP_TIMEOUT_S
        ) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        # The firmware explains its refusals in the body, e.g. "Enter
        # calibration mode first", which is what the user needs to see.
        detail = error.read().decode("utf-8", errors="replace").strip()
        raise RobotHttpError(detail or f"HTTP {error.code} from {url}") from error
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise RobotHttpError(f"Couldn't reach {url}: {reason}") from error


def get_json(address, path, timeout=None):
    text = _request(address, path, timeout=timeout)
    try:
        return json.loads(text)
    except ValueError as error:
        raise RobotHttpError(
            f"{robot_url(address, path)} did not return JSON"
        ) from error


# ---------------------------------------------------------------- config


def get_robot_config(address, timeout=None):
    """The raw payload of GET /robot_config."""
    return get_json(address, "/robot_config", timeout=timeout)


# ----------------------------------------------------------------- speed


def set_speed(address, pct):
    """Set the LUT playback speed; returns the speed the robot settled on."""
    query = urllib.parse.urlencode({"pct": int(pct)})
    text = _request(address, f"/set_speed?{query}", method="POST")
    try:
        return int(json.loads(text)["speed"])
    except (ValueError, KeyError, TypeError) as error:
        raise RobotHttpError(f"Unexpected /set_speed reply: {text}") from error


# ----------------------------------------------------------- calibration
#
# Offsets are servo ticks, shaped {"left": [[j1, j2, j3] x 3], "right": [...]},
# legs front to back within each side -- the firmware's own layout.


def enter_calibration(address):
    """Put the robot in its calibration posture; returns the current offsets."""
    return get_json(address, "/enter_calibration")


def exit_calibration(address):
    return _request(address, "/exit_calibration")


def get_offsets(address):
    return get_json(address, "/get_offsets")


def set_offsets(address, offsets):
    """Apply offsets live. The robot refuses unless it is in calibration mode."""
    return _request(address, "/set_offsets", method="POST", body=offsets)


def save_offsets(address):
    """Persist the applied offsets to the robot's flash."""
    return _request(address, "/save_offsets", method="POST")
