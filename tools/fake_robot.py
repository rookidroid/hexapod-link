"""A stand-in hexapod for trying the app without the hardware.

    python tools/fake_robot.py                 # a Nougat on 127.0.0.1:8080
    python tools/fake_robot.py mochi --port 8081

Serves the firmware's HTTP routes the app uses -- /robot_config and the speed
routes -- with the same replies and refusals as the ESP32, answers
firmware version queries on UDP port 1234, and prints every other UDP packet
sent there. In the app, connect to 127.0.0.1:8080: the port goes to HTTP, UDP
always goes to 1234.

The config it reports is one of the fixtures in tests/fixtures/robot_config,
which are the firmware's own replies. The tests use FakeRobot directly.
Nothing here is imported by the app itself.
"""

import argparse
import json
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "robot_config"

UDP_PORT = 1234

MAGIC_VERSION = 0xA8


def version_reply(request, payload):
    """The firmware's answer to a version query, or None if `request` is not one.

    The version is the one the payload reports, so UDP and HTTP agree.
    """
    if len(request) != 5 or request[0] != MAGIC_VERSION:
        return None
    _, seq = struct.unpack("<BI", request)
    firmware = payload.get("firmware") or {}
    major, minor, patch = (int(n) for n in firmware.get("version", "0.0.0").split("."))
    head = struct.pack("<BIBBBB", MAGIC_VERSION, seq, payload["protocol"], major, minor, patch)
    return head + firmware.get("build", "fake").encode("utf-8")


class FakeRobot:
    """A robot on background threads: HTTP, and UDP when `udp_port` is given.

    `requests` records (method, path, body) for each request and `packets` each
    UDP datagram other than a version query, for the tests. `on_packet` is
    called with each of those datagrams as well. `answer_version` False plays
    firmware that predates the version query.
    """

    def __init__(self, payload, host="127.0.0.1", port=0, udp_port=None,
                 on_packet=None, answer_version=True):
        self.payload = payload
        self.speed = payload.get("speed", {}).get("current", 60)
        self.requests = []
        self.packets = []
        self.on_packet = on_packet
        self.answer_version = answer_version
        self._server = ThreadingHTTPServer((host, port), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

        self._udp = None
        if udp_port is not None:
            self._udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._udp.bind((host, udp_port))
            self._udp_thread = threading.Thread(target=self._serve_udp, daemon=True)

    @classmethod
    def from_fixture(cls, name, **kwargs):
        with open(FIXTURES / f"{name}.json", encoding="utf-8") as f:
            return cls(json.load(f), **kwargs)

    @property
    def address(self):
        host, port = self._server.server_address[:2]
        return f"{host}:{port}"

    @property
    def udp_port(self):
        return self._udp.getsockname()[1] if self._udp else None

    def start(self):
        self._thread.start()
        if self._udp:
            self._udp_thread.start()
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        if self._udp:
            self._udp.close()

    def _serve_udp(self):
        while True:
            try:
                data, sender = self._udp.recvfrom(2048)
            except OSError:
                # Closed by stop(); on Windows also an ICMP error from a reply
                # whose sender has gone, which is not worth stopping for.
                if self._udp.fileno() == -1:
                    return
                continue
            reply = version_reply(data, self.payload)
            if reply is not None:
                if self.answer_version:
                    self._udp.sendto(reply, sender)
                continue
            self.packets.append(data)
            if self.on_packet:
                self.on_packet(data)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    def _handler(self):
        robot = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _reply(self, status, body, content_type="text/plain"):
                data = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _json(self, obj):
                self._reply(200, json.dumps(obj), "application/json")

            def _body(self):
                length = int(self.headers.get("Content-Length") or 0)
                return self.rfile.read(length).decode("utf-8") if length else ""

            def do_GET(self):
                url = urlparse(self.path)
                robot.requests.append(("GET", url.path, None))
                if url.path == "/robot_config":
                    payload = dict(robot.payload)
                    payload["speed"] = dict(payload.get("speed", {}), current=robot.speed)
                    self._json(payload)
                elif url.path == "/get_speed":
                    self._json({"speed": robot.speed})
                else:
                    self._reply(404, "Not found")

            def do_POST(self):
                url = urlparse(self.path)
                body = self._body()
                robot.requests.append(("POST", url.path, body))
                if url.path == "/set_speed":
                    pct = parse_qs(url.query).get("pct")
                    if not pct:
                        self._reply(400, "Missing pct")
                        return
                    robot.speed = max(20, min(100, int(pct[0])))
                    self._json({"speed": robot.speed})
                else:
                    self._reply(404, "Not found")

        return Handler


def _describe_packet(data):
    magic = data[0] if data else None
    if magic == 0xA5 and len(data) in (6, 7):
        _, cmd, seq = struct.unpack("<BBI", data[:6])
        speed = data[6] if len(data) == 7 else None
        return f"MOTION cmd={cmd} seq={seq} speed={speed} ({len(data)} bytes)"
    if magic == 0xA6 and len(data) == 44:
        _, flags, max_step, seq, *ticks = struct.unpack("<BBHI" + "h" * 18, data)
        return f"POSE seq={seq} max_step={max_step} flags={flags} ticks={ticks}"
    if magic == 0xA7 and len(data) == 6:
        _, action, seq = struct.unpack("<BBI", data)
        names = {0: "EXIT", 1: "ENTER", 2: "RELAX", 3: "PING"}
        return f"SESSION {names.get(action, action)} seq={seq}"
    return f"unknown {len(data)} bytes: {data[:16].hex()}"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("robot", nargs="?", default="nougat",
                        help="fixture name: " + ", ".join(p.stem for p in FIXTURES.glob("*.json")))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--quiet-pings", action="store_true", help="hide RT_PING packets")
    args = parser.parse_args()

    def print_packet(data):
        text = _describe_packet(data)
        if not (args.quiet_pings and text.startswith("SESSION PING")):
            print(text, flush=True)

    robot = FakeRobot.from_fixture(
        args.robot, host=args.host, port=args.port, udp_port=UDP_PORT,
        on_packet=print_packet,
    ).start()
    firmware = robot.payload.get("firmware", {}).get("version", "0.0.0")
    print(f"Fake {args.robot} (firmware {firmware}) serving HTTP on {robot.address}, "
          f"UDP on {args.host}:{UDP_PORT}")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        robot.stop()


if __name__ == "__main__":
    main()
