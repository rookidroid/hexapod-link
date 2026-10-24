// What tools/build_three_bundle.sh puts in assets/vendor/three.bundle.min.js.
// Only what assets/hexapod_view.js uses is exported, which keeps the file
// small. Using another three.js class there means adding it here and running
// the script again.

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
