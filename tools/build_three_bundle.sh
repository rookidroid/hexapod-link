#!/usr/bin/env sh
# Rebuild assets/vendor/three.bundle.min.js, the copy of three.js the 3D view
# (assets/hexapod_view.js) draws with on every page.
#
# It is checked in, like the bundled fonts and bootstrap, so the app needs no
# network and no Node at run time; Node is only needed to run this. The bundle
# is a plain script that sets window.HexapodThree, because Dash loads the files
# in assets/ as plain scripts, not as ES modules.
#
# Only what hexapod_view.js uses is exported, which keeps the file small. Using
# another three.js class there means adding it to the list below and running
# this again.
#
#   $ sh tools/build_three_bundle.sh

set -eu

THREE_VERSION=0.186.1
ESBUILD_VERSION=0.28.2

ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

cd "$WORK"
npm init -y >/dev/null
npm install --silent --no-audit --no-fund "three@$THREE_VERSION" "esbuild@$ESBUILD_VERSION"

cat > entry.js <<'EOF'
export {
    BufferGeometry,
    Color,
    CylinderGeometry,
    DirectionalLight,
    DoubleSide,
    Float32BufferAttribute,
    Group,
    HemisphereLight,
    LineBasicMaterial,
    LineLoop,
    LineSegments,
    Mesh,
    MeshBasicMaterial,
    MeshStandardMaterial,
    PerspectiveCamera,
    Raycaster,
    Scene,
    ShadowMaterial,
    SphereGeometry,
    Vector2,
    Vector3,
    WebGLRenderer,
} from "three";
export { OrbitControls } from "three/addons/controls/OrbitControls.js";
export { TransformControls } from "three/addons/controls/TransformControls.js";
EOF

mkdir -p "$ROOT/assets/vendor"
npx esbuild entry.js \
    --bundle \
    --minify \
    --format=iife \
    --global-name=HexapodThree \
    --legal-comments=inline \
    --banner:js="/* three.js $THREE_VERSION (https://threejs.org), MIT License, see three.LICENSE. Built by tools/build_three_bundle.sh. */" \
    --outfile="$ROOT/assets/vendor/three.bundle.min.js"

cp node_modules/three/LICENSE "$ROOT/assets/vendor/three.LICENSE"
