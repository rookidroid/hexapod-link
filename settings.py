# ***************************
# Settings
# ***************************

from pathlib import Path

# The range of each leg joint in degrees
ALPHA_MAX_ANGLE = 90
BETA_MAX_ANGLE = 180
GAMMA_MAX_ANGLE = 180
BODY_MAX_ANGLE = 40

# Too slow? set UPDATE_MODE='mouseup'
# Makes widgets only start updating when you release the mouse button
UPDATE_MODE = "drag"

DEBUG_MODE = False
ASSERTION_ENABLED = False

# The inverse kinematics solver already updates the points of the hexapod
# But there is no guarantee that this pose is correct
# So better update a fresh hexapod with the resulting poses
RECOMPUTE_HEXAPOD = True

PRINT_IK_LOCAL_LEG = False
PRINT_IK = False
PRINT_MODEL_ON_UPDATE = False

# Make it more granular to prevent overloading the server
SLIDER_ANGLE_RESOLUTION = 1.5
INPUT_DIMENSIONS_RESOLUTION = 1

# ***************************
# Physical robot link
# ***************************

# The ESP32 runs as a WiFi access point, so the machine running this app has to
# join the robot's network before it can be reached. Per-robot details
# (geometry, gait parameters, joint limits, frame delay) are not kept here: the
# robot serves them at GET /robot_config and the link fetches them on connect;
# see hexapod/robot_config.py.
ROBOT_DEFAULT_IP = "192.168.4.1"
ROBOT_UDP_PORT = 1234

# The firmware's web server: robot config, speed and calibration routes.
ROBOT_HTTP_PORT = 80
ROBOT_HTTP_TIMEOUT_S = 2.0

# Firmware version query, sent over UDP on connect (MAGIC_VERSION in the
# firmware's protocol.h). UDP may drop the request or the answer, so it is
# retried; a robot that never answers costs at most the product of the two.
ROBOT_VERSION_TIMEOUT_S = 0.3
ROBOT_VERSION_ATTEMPTS = 3

# Where the last robot's config is kept, so the app still models that robot when
# started offline. The environment variable overrides it (the tests use this).
ROBOT_CONFIG_CACHE_ENV = "HEXAPOD_LINK_CONFIG_CACHE"
ROBOT_CONFIG_CACHE_PATH = Path.home() / ".hexapod-link" / "robot_config.json"

# Rate at which the current pose is republished to the robot. This has to be at
# least the fastest robot's gait frame rate (mochi runs 1000/12 = 83 fps) or
# streamed gaits play back slower than they do natively. The firmware applies
# poses every REALTIME_PERIOD_MS (20 ms) and the servos refresh at 50 Hz, so
# sending faster than that only ensures the gait advances in correct wall-clock
# time; it does not make the servos move more finely.
ROBOT_STREAM_HZ = 100

# Idle keep-alive rate. Well under the firmware's REALTIME_TIMEOUT_MS (1000 ms)
# but far below the streaming rate, since holding a pose needs no bandwidth.
ROBOT_PING_HZ = 10

# How long a gait run from the controller over the view lasts past the last
# word from the page. While a pad is held the page repeats it several times a
# second (assets/drive_pads.js); if that stops -- the page closed, the network
# dropped -- the robot is sent to standby this long after. The idle pings
# above keep the robot's own failsafe fed, so without this it would walk on.
ROBOT_DRIVE_HOLD_S = 0.6

# Per-joint slew limit in servo ticks per firmware control cycle (20 ms).
# 1 tick is about 0.44 degrees, so 8 ticks/cycle is roughly 175 deg/s.
# Lower this to make the robot follow the simulator more gently.
ROBOT_DEFAULT_MAX_STEP = 8

# Slew limit used during gait streaming. Gait frames are small deltas meant to
# be played back to back, so the limit is relaxed; with the manual-posing value
# the robot would lag behind the gait instead of walking it.
ROBOT_SEQUENCE_MAX_STEP = 40

# ***************************
# User preferences
# ***************************

# UI choices that outlive a session (currently just the colour theme). Kept on
# disk rather than in the browser: the desktop window runs in pywebview's
# private mode and on a fresh port each launch, so browser storage would not
# survive a restart. The environment variable overrides it (the tests use this).
PREFERENCES_ENV = "HEXAPOD_LINK_PREFERENCES"
PREFERENCES_PATH = Path.home() / ".hexapod-link" / "preferences.json"
