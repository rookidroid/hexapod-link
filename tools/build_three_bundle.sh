#!/usr/bin/env sh
# Rebuild assets/vendor/three.bundle.min.js, the copy of three.js the 3D view
# (assets/hexapod_view.js) draws with on every page.
#
# It is checked in, like the bundled fonts and bootstrap, so the app needs no
# network and no Node at run time; Node is only needed to run this. The bundle
# is a plain script that sets window.HexapodThree, because Dash loads the files
# in assets/ as plain scripts, not as ES modules.
#
# The three.js and esbuild versions are pinned in tools/three-bundle/package.json
# (and its lockfile), where Dependabot finds and bumps them. What is exported
# is listed in tools/three-bundle/entry.js. After changing either, run this and
# commit the new bundle; CI checks that the checked-in bundle matches.
#
#   $ sh tools/build_three_bundle.sh

set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT/tools/three-bundle"

npm ci --silent --no-audit --no-fund

THREE_VERSION=$(node -p 'require("./node_modules/three/package.json").version')

mkdir -p "$ROOT/assets/vendor"
npx --no-install esbuild entry.js \
    --bundle \
    --minify \
    --format=iife \
    --global-name=HexapodThree \
    --legal-comments=inline \
    --banner:js="/* three.js $THREE_VERSION (https://threejs.org), MIT License, see three.LICENSE. Built by tools/build_three_bundle.sh. */" \
    --outfile="$ROOT/assets/vendor/three.bundle.min.js"

cp node_modules/three/LICENSE "$ROOT/assets/vendor/three.LICENSE"
