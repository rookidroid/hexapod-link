"""The workspace: the whole app below the top bar, on one screen.

    [stream]                  [move | rotate]         [reset pose][reset view]
    [dimensions]                 3D view
    [pose: angles, what is picked]                                [controller]
    ---------------------------------------------------------------------------
    dock: gaits library  |  sequence (poses and gaits, as keyframes)  |  playback, robot

Everything that sets the pose is on the view: click the body or a foot to pick
it, and its controls show under the joint angles, in the view's corner. While
the body is picked, what dragging it does -- move it or turn it -- is chosen
over the view's top edge, by the handles it is dragged with. What
belongs to the robot rather than to the pose -- streaming to it, its
dimensions, the controller that drives it -- sits over the view too.

The pose, the dimensions and the controller fold away, and start
folded, so the view starts clear; each is served as it was last left by hand.

What the controls do is in pages/pose.py (the pose, the sequence) and
pages/robot.py (the robot link), and the frame they sit in is pages/shell.py;
this module only puts them in place.
"""

from hexapod import pose_layers as pl
from hexapod.preferences import load_panels
from hexapod.robot_link import ROBOT_LINK
from pages import pose, robot  # noqa: F401  (registers the workspace's callbacks)
from pages.shell import PANEL_ATTRIBUTE, make_view, make_workspace
from widgets.dimensions_ui import DIMENSIONS_HUD
from widgets.pose_ui import POSE_HUD, POSE_DOCK, POSE_VIEW_ID, VIEW_OVERLAY, VIEW_TOOL
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
        hud=POSE_HUD,
        controls=[STREAM_OVERLAY, DIMENSIONS_HUD],
        drive=DRIVE_HUD,
        tool=VIEW_TOOL,
    ),
    POSE_DOCK,
)

# The overlays that fold away, by the preference each is kept under (PANELS in
# hexapod/preferences.py).
PANELS = {"pose": POSE_HUD, "controller": DRIVE_HUD, "dimensions": DIMENSIONS_HUD}
for _key, _panel in PANELS.items():
    setattr(_panel, PANEL_ATTRIBUTE, _key)


def workspace():
    """The workspace, each overlay folded or open as it was left. Built per
    page load, as the top bar is (hexapod_link.py): set from a callback, one
    left open would start folded and jump."""
    for key, is_open in load_panels().items():
        PANELS[key].open = is_open
    return WORKSPACE
