[![Tests](https://github.com/rookidroid/hexapod-link/actions/workflows/tests.yml/badge.svg)](https://github.com/rookidroid/hexapod-link/actions/workflows/tests.yml)
[![Build desktop app](https://github.com/rookidroid/hexapod-link/actions/workflows/build-desktop.yml/badge.svg)](https://github.com/rookidroid/hexapod-link/actions/workflows/build-desktop.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

# Hexapod Link

<img src="assets/icon.png" align="right" width="120" alt="">

A browser-based (and desktop) hexapod robot simulator built from first
principles, with forward/inverse kinematics, gait animation, and real-time
WiFi control of a physical [rookidroid](https://rookidroid.com/) hexapod. 🕷️

This is a fork of [mithi/hexapod-robot-simulator](https://github.com/mithi/hexapod-robot-simulator),
rebranded as **Hexapod Link** and extended with a desktop app, real-robot
streaming control, and a rebuilt CI/test suite.

<p align="center">
  <img src="docs/images/walk.gif" width="620" alt="One tripod gait cycle playing in the 3D view">
</p>

# Features

| STATUS | FEATURE   | DESCRIPTION  |
|---|-----------|--------------|
| 🎉 | Forward Kinematics | Given the angles of each joint, what does the robot look like? |
| 🎉 | Inverse Kinematics | What are the angles of each joint to make the robot look the way I want? Is it even possible? Why or why not? |
| 🎉 | Leg Patterns & Motion | Preview predefined gaits and leg-pattern animations frame by frame. |
| 🎉 | Pose Editor | Drag the feet in 3D, string the poses into a timed keyframe sequence, preview it and run it on the robot. |
| 🎉 | Customizability | Set the dimensions and shape of the robot's body and legs. |
| 🎉 | Real-time Robot Control | Drive a physical ESP32 hexapod over WiFi, from single joints to whole-body gaits. Works with any robot in the family (Nougat, Mochi, Macaroon, ...): each one serves its own config. |
| 🎉 | Desktop App | Runs as a native window (Windows/Linux) via PyInstaller + pywebview, no browser required. |
| 🎉 | Light & Dark Themes | Switch from the navigation bar; the choice is remembered between launches. |
| 🎉 | Simplicity | Minimal dependencies. Numpy for calculations, Plotly Dash for the 3D view and UI, and a bundled copy of three.js for the pose editor. |

## Preview

The screenshots follow your GitHub colour mode: light here shows the light
theme, dark shows the dark one.

<picture><source media="(prefers-color-scheme: dark)" srcset="docs/images/home-dark.png"><img src="docs/images/home.png" alt="The landing page"></picture>

<table>
  <tr>
    <td width="50%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/images/kinematics-dark.png"><img src="docs/images/kinematics.png" alt="The kinematics page"></picture></td>
    <td width="50%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/images/inverse-kinematics-dark.png"><img src="docs/images/inverse-kinematics.png" alt="The inverse kinematics page"></picture></td>
  </tr>
  <tr>
    <td><b>Kinematics</b> — set all 18 joint angles by hand and watch the body follow.</td>
    <td><b>Inverse Kinematics</b> — translate and rotate the body; the solver finds the joints.</td>
  </tr>
  <tr>
    <td><picture><source media="(prefers-color-scheme: dark)" srcset="docs/images/leg-patterns-dark.png"><img src="docs/images/leg-patterns.png" alt="The leg patterns page"></picture></td>
    <td><picture><source media="(prefers-color-scheme: dark)" srcset="docs/images/motion-dark.png"><img src="docs/images/motion.png" alt="The motion page"></picture></td>
  </tr>
  <tr>
    <td><b>Leg Patterns</b> — sweep all six legs together through one set of angles.</td>
    <td><b>Motion</b> — play the generated gaits frame by frame and scrub them.</td>
  </tr>
  <tr>
    <td><picture><source media="(prefers-color-scheme: dark)" srcset="docs/images/pose-editor-dark.png"><img src="docs/images/pose-editor.png" alt="The pose editor page"></picture></td>
    <td></td>
  </tr>
  <tr>
    <td><b>Pose Editor</b> — drag the feet in 3D and build a keyframe sequence to run on the robot.</td>
    <td></td>
  </tr>
</table>

Everything above is generated from the running app by
[`tools/make_screenshots.py`](./tools/make_screenshots.py), which captures every
page in both themes (`<page>.png` and `<page>-dark.png` in `docs/images/`), and
the app icon by [`tools/make_icon.py`](./tools/make_icon.py). Rerun those after
a UI or theme change rather than editing the images by hand.

## Requirements

- [x] Python 3.13+ (CI runs 3.13 and 3.14)
- [x] See [`requirements.txt`](./requirements.txt) for runtime dependencies (Dash, Plotly, Numpy, Flask)
- [x] See [`requirements-dev.txt`](./requirements-dev.txt) for linting/test tools
- [x] See [`requirements-desktop.txt`](./requirements-desktop.txt) for the desktop app (adds waitress, pywebview, PyInstaller)

## Run

```bash
$ pip install -r requirements.txt
$ python hexapod_link.py --no-window --port 8050
serving on http://127.0.0.1:8050 (ctrl-c to stop)
```

Then open the printed URL in a browser.

- Modify default settings with [`settings.py`](./settings.py) — joint limits, robot link ports/rates, UI resolution, etc.
- Modify the UI colours in [`assets/industrial.css`](./assets/industrial.css): the light theme's tokens are on `:root`, and the dark theme overrides them under `:root[data-theme="dark"]`.
- Modify the 3D plot's colours and sizes with [`style_settings.py`](./style_settings.py). The plot is a dark CAD-style view in both themes.
- The pose editor draws with three.js instead of Plotly, since Plotly's 3D plot cannot drag a point. Its view is [`assets/poser.js`](./assets/poser.js); the bundled three.js in `assets/vendor/` is rebuilt (with Node) by [`tools/build_three_bundle.sh`](./tools/build_three_bundle.sh).

### Light and dark themes

The ☾ / ☀ button in the navigation bar, next to the robot status button,
switches between the light and dark themes. The choice is saved to
`~/.hexapod-link/preferences.json` (set `HEXAPOD_LINK_PREFERENCES` to move it)
and applied before the first paint on the next launch, so the app opens in
whichever theme you left it in. Light is the default.

## Desktop app

The same app can run as a native window instead of in a browser: a waitress
server bound to loopback, wrapped in a [pywebview](https://pywebview.flowrl.com/)
window. No browser chrome, no dev-server warnings, and it works offline.

```bash
$ pip install -r requirements-desktop.txt
$ python hexapod_link.py
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
   The app needs a firmware that serves its own config at `GET /robot_config`
   (protocol 1); the protocol is documented in that firmware's README.
2. Power on the robot and **join its WiFi access point** from the machine
   running this app — the ESP32 is the access point, so there is no other route
   to it. The robot performs its stand-up sequence when a client connects.
3. Start the app and open the **ROBOT** panel from the status button in the
   navigation bar. It holds the robot's dimensions and the link to it -- its
   address (`192.168.4.1`) and the connect button -- and is reachable from every
   page. Streaming and gait controls live on the pages that use them.

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

### The robot's config comes from the robot

The app keeps no list of robots. Connecting first asks the robot for its config
(`GET http://<robot>/robot_config`): its name and access point, leg geometry
(mount positions and angles, link lengths, which servos are mirrored), gait
radii, joint limits, servo range, LUT frame delay, speed range and the motion
commands it knows. The simulator's body and leg dimensions switch to match, so
the on-screen hexapod agrees with the hardware. Any robot in the family --
Nougat, Mochi, Macaroon, or a new one -- works without changing this app; the
geometry lives in the firmware repo's `software/path_tool/robots/<name>.json`.

The last config received is saved to `~/.hexapod-link/robot_config.json` (set
`HEXAPOD_LINK_CONFIG_CACHE` to move it), so starting the app without a robot
still shows the last one. Before any robot has connected it shows a generic
model. See [`hexapod/robot_config.py`](./hexapod/robot_config.py).

To try the app without hardware, run the stand-in robot and connect to
`127.0.0.1:8080` (the port is for HTTP; UDP always goes to 1234):

```bash
$ python tools/fake_robot.py nougat
```

### Using it

- **Kinematics page** — move any of the 18 joint inputs and the servo follows.
- **Inverse Kinematics page** — translate and rotate the body; the solved pose is
  streamed once it is reachable.
- **Leg Patterns page** — preview individual leg-pattern trajectories.
- **Motion page** — the **RUN ON ROBOT** section plays the motion selected for
  preview on the hardware: either trigger the robot's own built-in gait
  (recommended; the ESP32 plays it from flash so smoothness does not depend on
  WiFi), or stream the simulator's frames for paths the firmware does not have.
  **Gait speed** (20-100 % of the robot's tuned rate) applies to both, and is
  sent to the robot as soon as it changes.
- **Pose editor page** — click a foot in the 3D view to pick it up, then drag
  the arrows to move it; the joints are solved as it moves, and a foot that
  cannot reach a spot (or would take a joint past its limit) springs back.
  **+ Add** records the pose as a keyframe with the time it takes to get there
  from the one before. **Preview sequence** plays the keyframes in the
  browser, and **RUN ON ROBOT** streams them to the hardware in real time,
  smoothed to the robot's own frame rate (optionally looping, with gentle
  starts and stops). Sequences save to and load from JSON files, which only
  load on the robot they were made for. Feet move in straight lines between
  keyframes, so add one in between to lift a foot over rather than dragging
  it along the floor.
- **Calibration page** — trims each servo's offset through the robot's own
  calibration routes: **Enter calibration** puts the robot in its calibration
  posture, **Apply** moves the servos to the edited offsets, **Save to robot**
  writes them to the robot's flash, then **Exit**.

Connect from the **ROBOT** panel first — until then the **STREAM TO ROBOT** and
**RUN ON ROBOT** controls are greyed out, since neither has anything to act on.
Once connected, the **STREAM TO ROBOT** section on the Kinematics and Inverse
Kinematics pages starts the sending: turn on **Stream pose to robot**, **Max
joint speed** limits how fast any servo may slew, and **RELAX** cuts drive so
the servos go limp. There is only one link behind them, so the switch follows
the robot's actual state when moving between those two pages.

### Safety

- **Put the robot on a stand before streaming.** A pose that is stable in the
  simulator is not necessarily stable on the floor.
- Joint angles are clamped to the robot's mechanical limits before being sent
  (`jointLimits` in the robot's config), because the simulator allows far more
  travel than the hardware has. Widen these only after checking clearances.
- If the stream stops, the robot eases back to standby on its own after 1 s.
- A pose editor sequence starts from its first keyframe wherever the robot is,
  so the first move is as fast as the servos' slew limit allows. Make the first
  keyframe close to standby, or press **Standby** before **Run**.

## Testing

```bash
$ pip install -r requirements-dev.txt
$ pytest
```

The suite (~1950 lines across [`tests/`](./tests)) covers forward/inverse
kinematics, leg patterns, path/motion generation, the pose editor's keyframes,
leg-naming conversions, the robot-link streaming protocol, reading each robot's config (against
`tools/fake_robot.py`), and the saved UI preferences — all without needing a
display, a browser, or a physical robot.

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

This fork ([rookidroid/hexapod-link](https://github.com/rookidroid/hexapod-link)):
- [@rookidroid](https://github.com/rookidroid/)

## License

MIT — see [`LICENSE`](./LICENSE). Copyright (c) 2020 Mithi Sevilla, (c) 2026 rookidroid.com.

![](https://img.shields.io/github/last-commit/rookidroid/hexapod-link)
![](https://img.shields.io/github/commit-activity/y/rookidroid/hexapod-link)
![](https://img.shields.io/github/languages/code-size/rookidroid/hexapod-link?color=yellow)
![](https://img.shields.io/github/repo-size/rookidroid/hexapod-link?color=violet)
![](https://img.shields.io/github/languages/top/rookidroid/hexapod-link)
