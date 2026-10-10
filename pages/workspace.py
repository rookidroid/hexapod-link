"""The workspace: the whole app below the top bar, on one screen.

    rail | tool panel |  [stream]      3D view       [reset pose][reset view]
         |            |  [dimensions]
         |            |  [angles]                                    [controller]
    ---------------------------------------------------------------------------
    dock: sequence (poses and gaits, as keyframes)  |  playback, then the robot

The rail picks one tool -- Body or Feet -- and only that tool's panel shows;
the other is hidden but stays mounted, so its callbacks keep firing. What
belongs to the robot rather than to a tool -- streaming to it, its
dimensions, the controller that drives it -- sits over the view.

What the controls do is in pages/page_pose.py (the pose, the sequence) and
pages/shared.py (the robot link); this module only puts them in place.
"""

from hexapod.const import BASE_SCENE
from pages import page_pose  # noqa: F401  (registers the workspace's callbacks)
from pages import shared
from widgets.dimensions_ui import DIMENSIONS_HUD
from widgets.pose_ui import (
    ANGLES_HUD,
    BODY_PANEL,
    FEET_PANEL,
    POSE_DOCK,
    POSE_MESSAGE,
    POSE_VIEW_ID,
    TOOL_RAIL,
    VIEW_OVERLAY,
)
from widgets.robot_link_ui import DRIVE_HUD, STREAM_OVERLAY

WORKSPACE = shared.make_workspace(
    TOOL_RAIL,
    [BODY_PANEL, FEET_PANEL, POSE_MESSAGE, shared.DIMENSIONS_HIDDEN_SECTION],
    # Starts on the neutral hexapod, and keeps it if the first pose cannot be
    # drawn, rather than starting as an empty screen.
    shared.make_view(
        POSE_VIEW_ID,
        BASE_SCENE,
        overlay=VIEW_OVERLAY,
        hud=ANGLES_HUD,
        controls=[STREAM_OVERLAY, DIMENSIONS_HUD],
        drive=DRIVE_HUD,
    ),
    POSE_DOCK,
)
