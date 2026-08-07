[![Tests](https://github.com/rookidroid/hexapod-simulator/actions/workflows/tests.yml/badge.svg)](https://github.com/rookidroid/hexapod-simulator/actions/workflows/tests.yml)
[![Build desktop app](https://github.com/rookidroid/hexapod-simulator/actions/workflows/build-desktop.yml/badge.svg)](https://github.com/rookidroid/hexapod-simulator/actions/workflows/build-desktop.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

# Hexapod Link

A browser-based (and desktop) hexapod robot simulator built from first
principles, with forward/inverse kinematics, gait animation, and real-time
WiFi control of a physical [rookidroid](https://rookidroid.com/) hexapod. 🕷️

This is a fork of [mithi/hexapod-robot-simulator](https://github.com/mithi/hexapod-robot-simulator),
rebranded as **Hexapod Link** and extended with a desktop app, real-robot
streaming control, and a rebuilt CI/test suite.

|  |  |  |  |
|---------|---------|---------|---------|
|![Twisting turning and tilting](https://mithi.github.io/robotics-blog/robot-only-x1.gif)|<img src="https://mithi.github.io/robotics-blog/v2-hexapod-1.gif" width="550"/>|<img src="https://mithi.github.io/robotics-blog/v2-hexapod-2.gif" width="500"/>|![Adjusting camera view](https://mithi.github.io/robotics-blog/robot-only-x3.gif)|

# Features

| STATUS | FEATURE   | DESCRIPTION  |
|---|-----------|--------------|
| 🎉 | Forward Kinematics | Given the angles of each joint, what does the robot look like? |
| 🎉 | Inverse Kinematics | What are the angles of each joint to make the robot look the way I want? Is it even possible? Why or why not? |
| 🎉 | Leg Patterns & Motion | Preview predefined gaits and leg-pattern animations frame by frame. |
| 🎉 | Customizability | Set the dimensions and shape of the robot's body and legs. |
| 🎉 | Real-time Robot Control | Drive a physical ESP32 hexapod over WiFi, from single joints to whole-body gaits. Supports both the `mochi` and `macaroon` robots. |
| 🎉 | Desktop App | Runs as a native window (Windows/Linux) via PyInstaller + pywebview, no browser required. |
| 🎉 | Simplicity | Minimal dependencies. Numpy for calculations, Plotly Dash for the 3D view and UI. |

## Preview

|![image](https://mithi.github.io/robotics-blog/v2-ik-ui.gif)|![image](https://mithi.github.io/robotics-blog/v2-kinematics-ui.gif)|
|----|----|
| ![image](https://mithi.github.io/robotics-blog/UI-1.gif) | ![image](https://mithi.github.io/robotics-blog/UI-2.gif) |

## Requirements

- [x] Python 3.13+ (CI runs 3.13 and 3.14)
- [x] See [`requirements.txt`](./requirements.txt) for runtime dependencies (Dash, Plotly, Numpy, Flask)
- [x] See [`requirements-dev.txt`](./requirements-dev.txt) for linting/test tools
- [x] See [`requirements-desktop.txt`](./requirements-desktop.txt) for the desktop app (adds waitress, pywebview, PyInstaller)

## Run

```bash
$ pip install -r requirements.txt
$ python index.py
Running on http://127.0.0.1:8050/
```

- Modify default settings with [`settings.py`](./settings.py) — joint limits, robot link ports/rates, UI resolution, etc.
- Modify page styles/theme with [`style_settings.py`](./style_settings.py) (light mode is the default; set `DARKMODE = True` to switch).

## Desktop app

The same app can run as a native window instead of in a browser: a waitress
server bound to loopback, wrapped in a [pywebview](https://pywebview.flowrl.com/)
window. No browser chrome, no dev-server warnings, and it works offline.

```bash
$ pip install -r requirements-desktop.txt
$ python desktop.py
```

Useful flags: `--port` to pin the port, `--debug` for the webview developer
tools, and `--no-window` to start the server only.

### Building a standalone executable

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
`ONEFILE = True` in [`hexapod.spec`](./hexapod.spec) for a single
self-extracting executable instead; it is tidier to hand out but adds several
seconds to every launch.

On Windows the window renders through the Edge WebView2 runtime, which is
present on stock Windows 10/11 installs. A machine that lacks it needs the
[Evergreen Bootstrapper](https://developer.microsoft.com/microsoft-edge/webview2/).

The `build-desktop` GitHub Actions workflow builds and smoke-tests this
bundle for Windows and Linux on every push; grab the artifacts from a run if
you just want a prebuilt binary instead of building locally.

## Controlling a real hexapod

The simulator can drive a physical [rookidroid hexapod](https://rookidroid.com/)
over WiFi in real time, from a single joint up to a full gait.

### Setup

1. Flash the ESP32 firmware from the `hexapod` repo (`software/hexapod_esp32`).
   Real-time control needs the pose-streaming protocol, which is documented in
   that firmware's README.
2. Power on the robot and **join its WiFi access point** from the machine
   running this app — the ESP32 is the access point, so there is no other route
   to it. The robot performs its stand-up sequence when a client connects.
3. Start the app, open any page, and use the **ROBOT LINK** panel in the sidebar.

### Leg and joint numbering

Legs and joints are named the way the robot's firmware names them, so a leg
picked out in the 3D plot is the leg the calibration page calls by that name.
Legs are numbered per side, front to back; joints are numbered outward from the
body.

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
[`hexapod/naming.py`](./hexapod/naming.py), which is the only place the two
vocabularies meet. The joint *angles* still follow the simulator's own sign
convention; `hexapod/robot_link.py` converts them to servo angles when streaming.

### Supported robots

Two robots are supported, matching the `mochi` and `macaroon` branches of the
firmware repo. They differ in leg geometry, stride and turn radii, and servo
step delay.

| Profile | WiFi SSID | Coxia / Femur / Tibia | Gait rate |
|---------|-----------|----------------------|-----------|
| Mochi | `hexapod` | 36 / 43.6 / 85.22 mm | 83 fps |
| Macaroon | `hexapod_macaroon` | 62 / 76 / 132 mm | 40 fps |

Selecting a profile also sets the simulator's body and leg dimensions to match,
so the on-screen hexapod agrees with the hardware. Profiles are defined in
[`hexapod/robot_profiles.py`](./hexapod/robot_profiles.py); add a robot there.

### Using it

- **Kinematics page** — move any of the 18 joint inputs and the servo follows.
- **Inverse Kinematics page** — translate and rotate the body; the solved pose is
  streamed once it is reachable.
- **Leg Patterns page** — preview individual leg-pattern trajectories.
- **Motion page** — either trigger the robot's own built-in gait (recommended;
  the ESP32 plays it from flash so smoothness does not depend on WiFi), or
  stream the simulator's frames for paths the firmware does not have.

Turn on **Stream pose to robot** to start sending. **Max joint speed** limits how
fast any servo may slew, and **RELAX** cuts drive so the servos go limp.

### Safety

- **Put the robot on a stand before streaming.** A pose that is stable in the
  simulator is not necessarily stable on the floor.
- Joint angles are clamped to each profile's mechanical limits before being sent
  (see `joint_limits` in `robot_profiles.py`), because the simulator allows far
  more travel than the hardware has. Widen these only after checking clearances.
- If the stream stops, the robot eases back to standby on its own after 1 s.

## Testing

```bash
$ pip install -r requirements-dev.txt
$ pytest
```

The suite (~1200 lines across [`tests/`](./tests)) covers forward/inverse
kinematics, leg patterns, path/motion generation, leg-naming conversions, the
robot-link streaming protocol, and robot profile geometry — all without
needing a display, a browser, or a physical robot.

## CI/CD

- [`tests.yml`](./.github/workflows/tests.yml) — runs `pytest` on Ubuntu and
  Windows across Python 3.13/3.14, and byte-compiles + imports every module to
  catch dead code the tests don't reach.
- [`build-desktop.yml`](./.github/workflows/build-desktop.yml) — builds the
  PyInstaller desktop bundle for Windows and Linux, smoke-tests that the built
  binary actually serves a page, and (Windows) verifies the Mark of the Web is
  cleared from bundled DLLs.
- [Dependabot](./.github/dependabot.yml) — weekly update checks for both pip
  dependencies and GitHub Actions versions.

## Screenshots

| ![Kinematics](https://mithi.github.io/robotics-blog/v2-kinematics-screenshot.png)|
|---|
| ![IK](https://mithi.github.io/robotics-blog/v2-ik-screenshot.png)|

## More Information
The original project's [Wiki](https://github.com/mithi/hexapod-robot-simulator/wiki/Notes)
has additional background on the kinematics math this simulator is built on.

## 🤗 Contributors

Original project ([mithi/hexapod-robot-simulator](https://github.com/mithi/hexapod-robot-simulator)):
- [@mithi](https://github.com/mithi/)
- [@philippeitis](https://github.com/philippeitis/)
- [@mikong](https://github.com/mikong/)
- [@guilyx](https://github.com/guilyx)
- [@markkulube](https://github.com/markkulube)

This fork ([rookidroid/hexapod-simulator](https://github.com/rookidroid/hexapod-simulator)):
- [@rookidroid](https://github.com/rookidroid/)

## License

MIT — see [`LICENSE`](./LICENSE). Copyright (c) 2020 Mithi Sevilla, (c) 2026 rookidroid.com.

![](https://img.shields.io/github/last-commit/rookidroid/hexapod-simulator)
![](https://img.shields.io/github/commit-activity/y/rookidroid/hexapod-simulator)
![](https://img.shields.io/github/languages/code-size/rookidroid/hexapod-simulator?color=yellow)
![](https://img.shields.io/github/repo-size/rookidroid/hexapod-simulator?color=violet)
![](https://img.shields.io/github/languages/top/rookidroid/hexapod-simulator)
