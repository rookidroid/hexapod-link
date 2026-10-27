// Settings shared by the window and the page.

export const APP_TITLE = "Hexapod Link";

// How far the body's rotation sliders go either way, in degrees.
export const BODY_MAX_ANGLE = 40;
export const SLIDER_ANGLE_RESOLUTION = 1.5;
export const INPUT_DIMENSIONS_RESOLUTION = 1;

// ***************************
// Physical robot link
// ***************************

// The ESP32 runs as a WiFi access point, so the machine running this app has to
// join the robot's network before it can be reached. Per-robot details
// (geometry, gait parameters, joint limits, frame delay) are not kept here: the
// robot serves them at GET /robot_config and the link fetches them on connect;
// see robot_config.ts.
export const ROBOT_DEFAULT_IP = "192.168.4.1";
export const ROBOT_UDP_PORT = 1234;

// The firmware's web server: robot config, speed and calibration routes.
export const ROBOT_HTTP_PORT = 80;
export const ROBOT_HTTP_TIMEOUT_S = 2.0;

// Firmware version query, sent over UDP on connect (MAGIC_VERSION in the
// firmware's protocol.h). UDP may drop the request or the answer, so it is
// retried; a robot that never answers costs at most the product of the two.
export const ROBOT_VERSION_TIMEOUT_S = 0.3;
export const ROBOT_VERSION_ATTEMPTS = 3;

// Rate at which the current pose is republished to the robot. This has to be at
// least the fastest robot's gait frame rate (mochi runs 1000/12 = 83 fps) or
// streamed gaits play back slower than they do natively. The firmware applies
// poses every REALTIME_PERIOD_MS (20 ms) and the servos refresh at 50 Hz.
export const ROBOT_STREAM_HZ = 100;

// Idle keep-alive rate. Well under the firmware's REALTIME_TIMEOUT_MS (1000 ms)
// but far below the streaming rate, since holding a pose needs no bandwidth.
export const ROBOT_PING_HZ = 10;

// How long a gait run from the controller over the view lasts past the last
// word from the page. While a pad is held the page repeats it several times a
// second; if that stops the robot is sent to standby this long after.
export const ROBOT_DRIVE_HOLD_S = 0.6;

// Per-joint slew limit in servo ticks per firmware control cycle (20 ms).
// 1 tick is about 0.44 degrees, so 8 ticks/cycle is roughly 175 deg/s.
export const ROBOT_DEFAULT_MAX_STEP = 8;

// Slew limit used during gait streaming: gait frames are small deltas meant to
// be played back to back, so the limit is relaxed.
export const ROBOT_SEQUENCE_MAX_STEP = 40;

// ***************************
// What is kept on disk
// ***************************
//
// Under ~/.hexapod-link/, each movable by an environment variable (the tests
// use these). The same files the Python version of the app kept, so settings
// and gaits carry over.
export const PREFERENCES_ENV = "HEXAPOD_LINK_PREFERENCES";
export const ROBOT_CONFIG_CACHE_ENV = "HEXAPOD_LINK_CONFIG_CACHE";
export const GAITS_ENV = "HEXAPOD_LINK_GAITS";
export const DATA_DIR_NAME = ".hexapod-link";
