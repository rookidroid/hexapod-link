# Developing Hexapod Link

Notes for working on the app itself: running it from a checkout, changing how
it looks, building the standalone executable, and how it talks to a robot. To
*use* the app, see the [README](../README.md).

Hexapod Link is a fork of
[mithi/hexapod-robot-simulator](https://github.com/mithi/hexapod-robot-simulator),
extended with a desktop app, real-robot streaming control, and a rebuilt
CI/test suite. It has few dependencies: Numpy for the calculations, Dash for
the UI, and a bundled copy of three.js for the 3D view.

## Requirements

- Python 3.13+ (CI runs 3.13 and 3.14)
- [`requirements.txt`](../requirements.txt) — runtime dependencies (Dash, Numpy, Flask, waitress)
- [`requirements-desktop.txt`](../requirements-desktop.txt) — adds the native window (pywebview) and PyInstaller
- [`requirements-dev.txt`](../requirements-dev.txt) — adds the linters, the test runner and Pillow for the image tools

## Running

```bash
$ pip install -r requirements-desktop.txt
$ python hexapod_link.py
```

That opens the native window: a waitress server bound to loopback, wrapped in
a [pywebview](https://pywebview.flowrl.com/) window. No browser chrome, no
dev-server warnings, and it works offline.

To serve it for a browser instead, which needs only `requirements.txt`:

```bash
$ pip install -r requirements.txt
$ python hexapod_link.py --no-window --port 8050
serving on http://127.0.0.1:8050 (ctrl-c to stop)
```

Flags: `--port` to pin the port, `--debug` for the webview developer tools,
and `--no-window` to start the server only.

## Changing how it looks and behaves

- Default settings are in [`settings.py`](../settings.py) — robot link
  ports/rates, slider resolution, where preferences and gaits are kept, etc.
  Joint limits come from the robot's own config.
- The UI colours are in [`assets/industrial.css`](../assets/industrial.css):
  the light theme's tokens are on `:root`, and the dark theme overrides them
  under `:root[data-theme="dark"]`.
- The 3D view's colours are in [`style_settings.py`](../style_settings.py).
  The view is a dark CAD-style monitor in both themes.
- The robot is drawn by one three.js view,
  [`assets/hexapod_view.js`](../assets/hexapod_view.js), fed scenes built by
  [`hexapod/scene.py`](../hexapod/scene.py). The bundled three.js in
  `assets/vendor/` is rebuilt (with Node) by
  [`tools/build_three_bundle.sh`](../tools/build_three_bundle.sh).

### What is kept between launches

Everything is under `~/.hexapod-link/`, each with an environment variable that
moves it:

| File | What | Variable |
|---|---|---|
| `preferences.json` | theme, dock sizes, which overlays are folded | `HEXAPOD_LINK_PREFERENCES` |
| `robot_config.json` | the last robot's config | `HEXAPOD_LINK_CONFIG_CACHE` |
| `gaits/` | gaits saved under **Mine**, one keyframe file each | `HEXAPOD_LINK_GAITS` |

The theme is applied before the first paint on the next launch, so the app
opens in whichever one it was left in. Light is the default.

## Building a standalone executable

Build from a **minimal environment**. PyInstaller follows optional-import
branches inside dependencies and bundles whatever it finds installed; built
from a rich development environment this comes out around 1 GB instead of
130 MB, mostly polars, pyarrow and Intel MKL that the app never touches.

```bash
$ python -m venv .venv-build
$ .venv-build/Scripts/pip install -r requirements-desktop.txt
$ .venv-build/Scripts/pyinstaller hexapod.spec
```

The result is `dist/HexapodLink/HexapodLink.exe`, about 130 MB in total. Set
`ONEFILE = True` in [`hexapod.spec`](../hexapod.spec) for a single
self-extracting executable instead; it is tidier to hand out but adds several
seconds to every launch.

On Windows the window renders through the Edge WebView2 runtime, which is
present on stock Windows 10/11 installs. A machine that lacks it needs the
[Evergreen Bootstrapper](https://developer.microsoft.com/microsoft-edge/webview2/).

The `build-desktop` GitHub Actions workflow builds and smoke-tests this
bundle for Windows and Linux on every push, and keeps the result as a run
artifact for a day.

## How the app talks to a robot

The ESP32 firmware is in the [`hexapod`](https://github.com/rookidroid/hexapod)
repo (`software/hexapod_esp32`). The app needs a firmware that serves its own
config at `GET /robot_config` (protocol 1); the protocol is documented in that
firmware's README. The ESP32 is the WiFi access point, so the machine running
the app has to join the robot's network.

### The robot's config comes from the robot

The app keeps no list of robots. Connecting first asks the robot for its config
(`GET http://<robot>/robot_config`): its name and access point, leg geometry
(mount positions and angles, link lengths, which servos are mirrored), gait
radii, joint limits, servo range, LUT frame delay, speed range and the motion
commands it knows. The simulator's body and leg dimensions switch to match, so
the on-screen hexapod agrees with the hardware. Any robot in the family --
Nougat, Mochi, Macaroon, or a new one -- works without changing this app; the
geometry lives in the firmware repo's `software/path_tool/robots/<name>.json`.

The last config received is cached (see the table above), so starting the app
without a robot still shows the last one. Before any robot has connected it
shows Nougat, the default model. See
[`hexapod/robot_config.py`](../hexapod/robot_config.py).

### A stand-in robot

To try the robot side without hardware, run the stand-in and connect the app
to `127.0.0.1:8080` (the port is for HTTP; UDP always goes to 1234):

```bash
$ python tools/fake_robot.py nougat
```

It serves the firmware's HTTP routes with the same replies and refusals as the
ESP32, answers version queries, and prints every other packet it is sent.

### Leg and joint numbering

Legs and joints are named the way the robot's firmware names them, so a leg
picked out in the 3D view is the leg the robot's own calibration page calls by
that name. Legs are numbered per side, front to back; joints are numbered
outward from the body.

| Leg index | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| Shown as | Right Leg 1 | Right Leg 2 | Right Leg 3 | Left Leg 1 | Left Leg 2 | Left Leg 3 |
| In code | `right-front` | `right-middle` | `right-back` | `left-front` | `left-middle` | `left-back` |

| Joint | 1 | 2 | 3 |
|---|---|---|---|
| In code | `coxia` / `alpha` | `femur` / `beta` | `tibia` / `gamma` |

Code keeps the descriptive identifiers — they say which leg is meant without a
diagram, and the pose dicts, widget ids and point names key off them. Anything a
person reads is built from the label tables in
[`hexapod/naming.py`](../hexapod/naming.py), which is the only place the two
vocabularies meet. The joint *angles* still follow the simulator's own sign
convention; `hexapod/robot_link.py` converts them to servo angles when streaming.

### Poses, sequences and gaits

There is one pose: the robot's standby posture with two layers on top that add
up, the body's move and tilt over the planted feet, and each foot's move from
where standby has it ([`hexapod/pose_layers.py`](../hexapod/pose_layers.py)).
Foot moves are from standby, so they keep their meaning when the dimensions
are edited, and what is streamed is solved on the edited body too.

A sequence is keyframes of that pose. Between keyframes each layer moves on
its own, so a body tilting from one keyframe to the next tilts over planted
feet, while a moved foot travels in a straight line. **Run on robot** streams
them in real time, smoothed to the robot's own frame rate.

A built-in gait put into a sequence is worked out into the few keyframes that
trace its path to within a millimetre (15 to 24 for a walk, depending on the
robot) at the robot's own timing
([`hexapod/gait_keyframes.py`](../hexapod/gait_keyframes.py)). From then on
they are keyframes like any other, with nothing to mark where they came from.
They come with **Ease in** off, so the robot walks through them rather than
stopping at each, and the swaying gaits (Rotate, Twist) are written as the body
tilting over planted feet. Some robots' own gaits ask a joint for a little more
than its limit (Mochi's walk does); worked out as keyframes they are held just
inside it, as the robot holds them when it plays the gait itself.

The controller is different: it has the ESP32 play its own gaits from flash,
so their smoothness does not depend on WiFi. While a pad is held the page
renews it several times a second through `POST /api/drive`
([`pages/drive.py`](../pages/drive.py)); if that stops, the robot stands on
its own within a second.

Joint angles are clamped to the robot's mechanical limits before being sent
(`jointLimits` in the robot's config), because the simulator allows far more
travel than the hardware has.

## The README's images

Everything in `docs/images/` is generated from the running app by
[`tools/make_screenshots.py`](../tools/make_screenshots.py), which connects it
to the stand-in robot and drives it in a headless Chrome or Edge:

```bash
$ python tools/make_screenshots.py              # all of them
$ python tools/make_screenshots.py app pose     # only those
```

| Name | Writes | Shows |
|---|---|---|
| `app` | `app.png`, `app-dark.png`, `controller.png` | the whole window in each theme, and the controller cut out of it |
| `walk` | `walk.gif` | a walk cycle, in the 3D view alone |
| `pose` | `pose.gif` | posing the body and a foot |
| `sequence` | `sequence.gif`, `sequence-dark.gif` | building a sequence and playing it, in each theme |

The app icon is drawn by [`tools/make_icon.py`](../tools/make_icon.py). Rerun
these after a UI or theme change rather than editing the images by hand.

## Testing

```bash
$ pip install -r requirements-dev.txt
$ pytest
```

The suite in [`tests/`](../tests) covers the kinematics (feet to joints and
back, the body and foot layers of a pose), gait path generation, keyframe
sequences and gaits worked out as keyframes, leg-naming conversions, the
robot-link streaming protocol, reading each robot's config (against
`tools/fake_robot.py`), and the saved preferences and gait library — all
without needing a display, a browser, or a physical robot.

## CI/CD

- [`tests.yml`](../.github/workflows/tests.yml) — runs `pytest` on Ubuntu and
  Windows across Python 3.13/3.14, and byte-compiles + imports every module to
  catch dead code the tests don't reach.
- [`build-desktop.yml`](../.github/workflows/build-desktop.yml) — builds the
  PyInstaller desktop bundle for Windows and Linux, smoke-tests that the built
  binary actually serves a page, and (Windows) verifies the Mark of the Web is
  cleared from bundled DLLs.
- [Dependabot](../.github/dependabot.yml) — weekly update checks for both pip
  dependencies and GitHub Actions versions.

## More information

The original project's
[Wiki](https://github.com/mithi/hexapod-robot-simulator/wiki/Notes) has
additional background on the kinematics math this simulator is built on.
