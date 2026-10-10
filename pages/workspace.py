"""The workspace: the whole app below the top bar, on one screen.

    [stream]                     3D view              [reset pose][reset view]
    [dimensions]
    [angles, and what is picked]                                  [controller]
    ---------------------------------------------------------------------------
    dock: gaits library  |  sequence (poses and gaits, as keyframes)  |  playback, robot

Everything that sets the pose is on the view: click the body or a foot to pick
it, and its controls show under the joint angles, in the view's corner. What
belongs to the robot rather than to the pose -- streaming to it, its
dimensions, the controller that drives it -- sits over the view too.

What the controls do is in pages/pose.py (the pose, the sequence) and
pages/robot.py (the robot link), and the frame they sit in is pages/shell.py;
this module only puts them in place.
"""

from hexapod import pose_layers as pl
from hexapod.robot_link import ROBOT_LINK
from pages import pose, robot  # noqa: F401  (registers the workspace's callbacks)
from pages.shell import make_view, make_workspace
from widgets.dimensions_ui import DIMENSIONS_HUD
from widgets.pose_ui import ANGLES_HUD, POSE_DOCK, POSE_VIEW_ID, VIEW_OVERLAY
from widgets.robot_link_ui import DRIVE_HUD, STREAM_OVERLAY


def standby_scene(robot_config):
    """The robot at standby, as the view draws it."""
    state = pl.standby_state()
    _, angles, _ = pl.solve(state, robot_config)
    return pl.scene(state, angles, robot_config)


WORKSPACE = make_workspace(
    # Starts on the modelled robot at standby, and keeps it if the first pose
    # cannot be drawn, rather than starting as an empty screen.
    make_view(
        POSE_VIEW_ID,
        standby_scene(ROBOT_LINK.robot_config),
        overlay=VIEW_OVERLAY,
        hud=ANGLES_HUD,
        controls=[STREAM_OVERLAY, DIMENSIONS_HUD],
        drive=DRIVE_HUD,
    ),
    POSE_DOCK,
)
