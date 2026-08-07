# ***************************
# Settings
# ***************************

# The range of each leg joint in degrees
ALPHA_MAX_ANGLE = 90
BETA_MAX_ANGLE = 180
GAMMA_MAX_ANGLE = 180
BODY_MAX_ANGLE = 40

# LEG STANCE
# would define the starting leg position used to compute
# the target ground contact for inverse kinematics poses
# femur/ beta = -leg_stance
# tibia/ gamma = leg_stance
LEG_STANCE_MAX_ANGLE = 90

# HIP STANCE
# would defined the starting hip position used to compute
# the target ground contact for inverse kinematics poses
# coxia/alpha angle of
#  right_front = -hip_stance
#   left_front = +hip_stance
#    left_back = -hip_stance
#   right_back = +hip_stance
#  left_middle = 0
# right_middle = 0
HIP_STANCE_MAX_ANGLE = 45

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

# 1 - Use the daq slider UI
# 2 - Use the generic slider UI
# Anything else defaults to the generic input UI, which I prefer
WHICH_POSE_CONTROL_UI = 0

# Make it more granular to prevent overloading the server
SLIDER_ANGLE_RESOLUTION = 1.5
INPUT_DIMENSIONS_RESOLUTION = 1

# ***************************
# Physical robot link
# ***************************

# The ESP32 runs as a WiFi access point, so the machine running this app has to
# join the selected robot's network before it can be reached. Per-robot details
# (SSID, IP, geometry, gait parameters, joint limits) live in
# hexapod/robot_profiles.py.
ROBOT_UDP_PORT = 1234

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

# Per-joint slew limit in servo ticks per firmware control cycle (20 ms).
# 1 tick is about 0.44 degrees, so 8 ticks/cycle is roughly 175 deg/s.
# Lower this to make the robot follow the simulator more gently.
ROBOT_DEFAULT_MAX_STEP = 8

# Slew limit used during gait streaming. Gait frames are small deltas meant to
# be played back to back, so the limit is relaxed; with the manual-posing value
# the robot would lag behind the gait instead of walking it.
ROBOT_SEQUENCE_MAX_STEP = 40
