# Developing Hexapod Link

Notes for working on the app itself: running it from a checkout, changing how
it looks, building the standalone app, and how it talks to a robot. To *use*
the app, see the [README](../README.md).

Hexapod Link is a fork of
[mithi/hexapod-robot-simulator](https://github.com/mithi/hexapod-robot-simulator),
extended with a desktop app, real-robot streaming control, and a rebuilt
test suite. It is an [Electron](https://www.electronjs.org/) app written in
TypeScript: React for the page, three.js for the 3D view.

## Requirements

- [Node.js](https://nodejs.org/) 22 or newer (CI runs 22)
- `npm install` -- everything else, Electron included, comes from
  [`package.json`](../package.json)

## Running

```bash
$ npm install
$ npm run dev     # the app, reloading the page as the code changes
$ npm start       # the app, built as it ships
```

The window is frameless: the app's top bar, laid see-through over the 3D view,
is its title bar, with its own minimize, maximize and close buttons
([`TopBar.tsx`](../src/renderer/src/components/TopBar.tsx)). The system drags
the window by it (`-webkit-app-region` in the stylesheet), so it snaps to the
screen's edges like any other. On macOS the system's own traffic lights stay.
The window reopens at the size and place it was closed at, and maximized if
it was left so ([`window_state.ts`](../src/main/window_state.ts)); a place on
a screen since unplugged is dropped, and the window opens centred.
`HEXAPOD_LINK_FRAMED=1` keeps the system's window frame.

## How it is put together

Electron runs the app in two processes, and everything that can be is in the
page:

| Where | What |
|---|---|
| [`src/shared/`](../src/shared) | The kinematics, the gaits, keyframes, the robot's config and its UDP protocol: plain TypeScript, no I/O, used by both processes and the tests |
| [`src/renderer/`](../src/renderer) | The page: React components, the state ([`store.ts`](../src/renderer/src/state/store.ts)), and the 3D view ([`hexapodView.js`](../src/renderer/src/view/hexapodView.js)) |
| [`src/main/`](../src/main) | The window, the robot link (UDP and HTTP, [`robot_link.ts`](../src/main/robot_link.ts)) and what is kept on disk ([`storage.ts`](../src/main/storage.ts)) |
| [`src/preload/`](../src/preload) | The bridge between the two, as `window.hexapod`; its calls are listed in [`api.ts`](../src/shared/api.ts) |

Every edit -- a foot dragged, a slider moved, a keyframe added -- is one
action in [`store.ts`](../src/renderer/src/state/store.ts), solved there and
then: there is no server to wait on. The page asks the main process only for
what a page cannot do itself: sending to the robot, reading and writing files,
and the window's buttons.

## Changing how it looks and behaves

- Default settings are in [`settings.ts`](../src/shared/settings.ts) -- robot
  link ports and rates, slider resolution, where preferences and gaits are kept.
  Joint limits come from the robot's own config.
- The UI colours are in
  [`industrial.css`](../src/renderer/src/styles/industrial.css): the light
  theme's tokens are on `:root`, and the dark theme overrides them under
  `:root[data-theme="dark"]`. The sliders' and checkboxes' base look is its
  WIDGETS block.
  It builds on Bootstrap's CSS (the `bootstrap` npm package), which the
  components' buttons, fields and checks take their class names from.
- The 3D view's colours are in [`style.ts`](../src/shared/style.ts). The view
  is a dark CAD-style monitor in both themes.
- The robot is drawn by one three.js view,
  [`hexapodView.js`](../src/renderer/src/view/hexapodView.js), fed scenes built
  by [`scene.ts`](../src/shared/scene.ts) and
  [`pose_layers.ts`](../src/shared/pose_layers.ts). three.js comes from npm;
  Dependabot opens a PR when it has a new release.

### What is kept between launches

Everything is under `~/.hexapod-link/`, each with an environment variable that
moves it. These are the same files, in the same shapes, as the Python version
of the app kept, so settings and gaits carry over.

| File | What | Variable |
|---|---|---|
| `preferences.json` | theme, dock sizes, which overlays are folded, the window's place, and the workspace as it was closed (sequence, pose, dock and playback controls, dimensions, robot address) | `HEXAPOD_LINK_PREFERENCES` |
| `robot_config.json` | the last robot's config | `HEXAPOD_LINK_CONFIG_CACHE` |
| `gaits/` | gaits saved under **Mine**, one keyframe file each | `HEXAPOD_LINK_GAITS` |

The theme and the dock's sizes are put on the page by the preload script
before it is first drawn, so the app opens in whichever theme it was left in
without a flash. Dark is the default.

## Building the standalone app

```bash
$ npm run dist
```

[electron-builder](https://www.electron.build/) writes, into `dist/`, an
installer for the platform it runs on -- `HexapodLink-v<version>-windows-x64-setup.exe`
(NSIS, per-user, no admin rights needed) on Windows, an `.AppImage` and a
`.deb` on Linux -- and on the way the app as a plain folder,
`dist/<platform>-unpacked/`, with `HexapodLink` (`HexapodLink.exe` on
Windows) in it; see [`electron-builder.yml`](../electron-builder.yml). The
page, the main process and every npm package it uses are bundled into `out/`
by electron-vite first, so no `node_modules` ship. To get just the folder,
quicker, run `npx electron-vite build && npx electron-builder --dir`.

The `build-desktop` GitHub Actions workflow builds Windows and Linux on every
push, smoke-tests the unpacked app, and keeps what a person would download
as a run artifact for a day: the installers, plus a portable archive of the
folder, `HexapodLink-v<version>-<platform>-portable` (a `.zip` for Windows, a
`.tar.gz` for Linux), unpacking to one `HexapodLink/` folder. On a `v*` tag it
publishes all of them, with a `SHA256SUMS.txt`, as a release. The tag has to
match the version in `package.json`, which is also what the top bar shows.

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
commands it knows. The app's body and leg dimensions switch to match, so the
on-screen hexapod agrees with the hardware. Any robot in the family --
Nougat, Mochi, Macaroon, or a new one -- works without changing this app; the
geometry lives in the firmware repo's `software/path_tool/robots/<name>.json`.

The last config received is cached (see the table above), so starting the app
without a robot still shows the last one. Before any robot has connected it
shows Nougat, the default model. See
[`robot_config.ts`](../src/shared/robot_config.ts).

### A stand-in robot

To try the robot side without hardware, run the stand-in and connect the app
to `127.0.0.1:8080` (the port is for HTTP; UDP always goes to 1234):

```bash
$ npm run fake-robot              # a Nougat
$ npm run fake-robot -- mochi
```

It serves the firmware's HTTP routes with the same replies and refusals as the
ESP32, answers version queries, and prints every other packet it is sent
([`fake_robot.ts`](../tools/fake_robot.ts)).

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

Code keeps the descriptive identifiers -- they say which leg is meant without a
diagram, and the poses and element ids key off them. Anything a person reads
is built from the label tables in [`naming.ts`](../src/shared/naming.ts),
which is the only place the two vocabularies meet. The joint *angles* follow
the simulator's own sign convention;
[`protocol.ts`](../src/shared/protocol.ts) converts them to servo angles when
streaming.

### Poses, sequences and gaits

There is one pose: the robot's standby posture with two layers on top that add
up, the body's move and tilt over the planted feet, and each foot's move from
where standby has it ([`pose_layers.ts`](../src/shared/pose_layers.ts)).
Foot moves are from standby, so they keep their meaning when the dimensions
are edited, and what is streamed is solved on the edited body too.

A sequence is keyframes of that pose. Between keyframes each layer moves on
its own, so a body tilting from one keyframe to the next tilts over planted
feet, while a moved foot travels in a straight line. **Run on robot** streams
them in real time, smoothed to the robot's own frame rate.

A built-in gait put into a sequence is worked out into the few keyframes that
trace its path to within a millimetre (15 to 24 for a walk, depending on the
robot) at the robot's own timing
([`gait_keyframes.ts`](../src/shared/gait_keyframes.ts)). From then on they
are keyframes like any other, with nothing to mark where they came from.
They come with **Ease in** off, so the robot walks through them rather than
stopping at each, and the swaying gaits (Rotate, Twist) are written as the body
tilting over planted feet. Some robots' own gaits ask a joint for a little more
than its limit (Mochi's walk does); worked out as keyframes they are held just
inside it, as the robot holds them when it plays the gait itself.

The controller is different: it has the ESP32 play its own gaits from flash,
so their smoothness does not depend on WiFi. While a pad is held the page
renews it several times a second; if that stops, the robot stands on its own
within a second ([`robot_link.ts`](../src/main/robot_link.ts) `drive()`).

Joint angles are clamped to the robot's mechanical limits before being sent
(`jointLimits` in the robot's config), because the simulator allows far more
travel than the hardware has.

## The README's images

Everything in `docs/images/` is generated from the running app by
[`make_screenshots.ts`](../tools/make_screenshots.ts), which connects it to
the stand-in robot and drives it as a person would:

```bash
$ npm run screenshots              # all of them
$ npm run screenshots -- app pose  # only those
```

| Name | Writes | Shows |
|---|---|---|
| `app` | `app.png`, `controller.png` | the whole window, and the controller cut out of it |
| `walk` | `walk.gif` | a walk cycle, in the 3D view alone |
| `pose` | `pose.gif` | posing the body and a foot |
| `sequence` | `sequence.gif` | building a sequence and playing it |

All of them are in the dark theme.

The app icon is `resources/icon.png` (and `app.ico` for Windows). Rerun the
screenshots after a UI or theme change rather than editing the images by hand.
Without a display, run it under `xvfb-run`.

## Testing

```bash
$ npm test                 # unit tests (vitest)
$ npm run typecheck
$ npm run build && npm run smoke
```

The suite in [`tests/`](../tests) covers the kinematics (feet to joints and
back, the body and foot layers of a pose), gait path generation, keyframe
sequences and gaits worked out as keyframes, leg-naming conversions, the
robot-link protocol against the firmware's own LUTs, reading each robot's
config and streaming to it over real UDP and HTTP (against the stand-in
robot), the saved preferences and gait library, and restoring the workspace --
all without a display or a physical robot.

[`golden.test.ts`](../tests/golden.test.ts) also holds the TypeScript
kinematics to what the Python version of the app computed, case by case, for
each robot: the recorded inputs and results are in `tests/fixtures/golden/`.

The smoke test ([`smoke_test.ts`](../tools/smoke_test.ts)) launches the built
app and drives it against the stand-in robot: connect, pose, add a gait, play,
run on the robot, drive, close, reopen. With `HEXAPOD_LINK_EXECUTABLE` set to
a packaged app, it drives that instead.

## Linting and formatting

[Biome](https://biomejs.dev/) lints and formats the code, configured in
[`biome.json`](../biome.json). CI fails on either, so run it before pushing:

```bash
$ npm run format   # fix what can be fixed
$ npm run lint     # check
```

## CI/CD

- [`tests.yml`](../.github/workflows/tests.yml) -- typechecks and runs the
  unit tests on Ubuntu and Windows, and drives the built app on Ubuntu.
- [`lint.yml`](../.github/workflows/lint.yml) -- runs `biome ci`; findings show
  up as annotations on the PR diff.
- [`build-desktop.yml`](../.github/workflows/build-desktop.yml) -- builds the
  standalone app and its installers for Windows and Linux, smoke-tests the
  built binary, and publishes a release for a `v*` tag.
- [Dependabot](../.github/dependabot.yml) -- weekly update checks for npm
  packages and GitHub Actions versions.

## More information

The original project's
[Wiki](https://github.com/mithi/hexapod-robot-simulator/wiki/Notes) has
additional background on the kinematics math this simulator is built on.
