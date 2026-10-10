"""The controller over the view (DRIVE_HUD in widgets/robot_link_ui.py) runs
the robot's own gaits for as long as a pad is held. Its page script,
assets/drive_pads.js, talks to this route rather than to a Dash callback:
a callback can wait in line behind a slow one, such as a gait preview being
built, and letting go of a pad has to stop the robot at once.

    POST /api/drive  {"motion": "walk_0"}   run a gait, or renew its hold
                     {"motion": "standby"}  let go

Answers {"ok": bool, "message": str}. How long a hold lasts without being
renewed is ROBOT_DRIVE_HOLD_S; see RobotLink.drive().
"""

from flask import jsonify, request

from hexapod.robot_link import ROBOT_LINK

DRIVE_ROUTE = "/api/drive"


def drive():
    body = request.get_json(silent=True) or {}
    if not ROBOT_LINK.connected:
        return jsonify(ok=False, message="Connect a robot to drive it.")

    motion = body.get("motion")
    if not isinstance(motion, str) or not ROBOT_LINK.drive(motion):
        return jsonify(ok=False, message=f"The robot has no '{motion}' gait.")
    return jsonify(ok=True, message="")


def register_drive_route(server):
    server.add_url_rule(DRIVE_ROUTE, "drive", drive, methods=["POST"])
