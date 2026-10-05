// The pose editor's 3D view (pages/page_poser.py).
//
// Plotly's 3D plot cannot drag a point, so this page draws the robot with
// three.js instead and lets each foot be picked up and moved. The server stays
// in charge of the kinematics: this only draws the scene it is given and turns
// a drag into a foot target. A target goes back through the "poser-foot-target"
// store; the server solves the leg's joints and, if the foot can get there,
// sends back the new scene, which is drawn here. A foot that cannot get there
// springs back to where the server last put it.
//
// Coordinates are the robot's body frame, as the server sends them: x right,
// y forward, z up, millimetres, origin at the centre of the body.
//
// Dash loads every .js file in assets/ on its own, so this is a plain script.
// three.js comes from assets/vendor/three.bundle.min.js (window.HexapodThree);
// see tools/build_three_bundle.sh. It is only looked up when the view is first
// drawn, so the order the two files load in does not matter.

(function () {
    "use strict";

    var FOOT_TARGET_ID = "poser-foot-target";
    var SELECTED_LEG_ID = "poser-selected-leg";

    // How often a foot target is sent while dragging, in ms. The final position
    // is always sent when the drag ends.
    var SEND_INTERVAL_MS = 80;

    // A press that moves further than this (px) is an orbit, not a click.
    var CLICK_SLOP = 5;

    // Colours of the CAD view, as style_settings.py gives them for the Plotly
    // pages; the server sends the actual values with each scene.
    var DEFAULT_COLORS = {
        background: "#0a1428",
        ground: "#13213f",
        grid: "#24406e",
        body: "#e8ecf2",
        bodyOutline: "#3b7bff",
        leg: "#dfe6ef",
        joint: "#3b7bff",
        foot: "#4cc9f0",
        footSelected: "#f7c600",
        head: "#f7c600",
        cog: "#e63946",
        support: "#4cc9f0",
    };

    var view = null;
    var lastCamera = null;

    function three() {
        return window.HexapodThree;
    }

    // Updates for Dash are sent from a timeout rather than from inside the
    // pointer handlers (or a clientside callback) that produce them, and only
    // the latest per id: a burst of synchronous set_props calls nests React
    // updates until it gives up ("maximum update depth exceeded").
    var pendingProps = {};
    var flushScheduled = false;

    function setProps(id, props) {
        pendingProps[id] = props;
        if (flushScheduled) {
            return;
        }
        flushScheduled = true;
        window.setTimeout(function () {
            var batch = pendingProps;
            pendingProps = {};
            flushScheduled = false;
            if (!(window.dash_clientside && window.dash_clientside.set_props)) {
                return;
            }
            Object.keys(batch).forEach(function (key) {
                window.dash_clientside.set_props(key, batch[key]);
            });
        }, 0);
    }

    function vec(T, p) {
        return new T.Vector3(p[0], p[1], p[2]);
    }

    // ------------------------------------------------------------- building

    function createView(container) {
        var T = three();
        var renderer = new T.WebGLRenderer({ antialias: true });
        renderer.setPixelRatio(window.devicePixelRatio || 1);
        renderer.domElement.style.display = "block";
        renderer.domElement.style.width = "100%";
        renderer.domElement.style.height = "100%";
        renderer.domElement.style.touchAction = "none";
        container.appendChild(renderer.domElement);

        var scene = new T.Scene();
        var camera = new T.PerspectiveCamera(40, 1, 1, 100000);
        camera.up.set(0, 0, 1);

        scene.add(new T.HemisphereLight(0xffffff, 0x223355, 1.6));
        var sun = new T.DirectionalLight(0xffffff, 1.4);
        sun.position.set(1, -2, 3);
        scene.add(sun);

        var orbit = new T.OrbitControls(camera, renderer.domElement);
        orbit.enableDamping = false;

        var gizmo = new T.TransformControls(camera, renderer.domElement);
        gizmo.setSpace("world");
        gizmo.setSize(0.9);
        scene.add(gizmo.getHelper());

        var v = {
            container: container,
            renderer: renderer,
            scene: scene,
            camera: camera,
            orbit: orbit,
            gizmo: gizmo,
            raycaster: new T.Raycaster(),
            root: new T.Group(),
            parts: null,
            colors: DEFAULT_COLORS,
            size: 0,
            data: null,
            editable: true,
            selected: null,
            dragging: false,
            seq: 0,
            lastSent: 0,
            sendTimer: null,
            frameRequested: false,
            pointerDown: null,
        };
        scene.add(v.root);

        orbit.addEventListener("change", function () {
            requestFrame(v);
        });
        gizmo.addEventListener("change", function () {
            requestFrame(v);
        });
        gizmo.addEventListener("dragging-changed", function (event) {
            v.dragging = event.value;
            orbit.enabled = !event.value;
            if (!event.value) {
                sendTarget(v, true);
            }
        });
        gizmo.addEventListener("objectChange", function () {
            sendTarget(v, false);
        });

        var canvas = renderer.domElement;
        canvas.addEventListener("pointerdown", function (event) {
            v.pointerDown = { x: event.clientX, y: event.clientY };
        });
        canvas.addEventListener("pointerup", function (event) {
            var start = v.pointerDown;
            v.pointerDown = null;
            if (!start || v.dragging || gizmo.axis) {
                return;
            }
            var moved = Math.hypot(event.clientX - start.x, event.clientY - start.y);
            if (moved <= CLICK_SLOP) {
                pick(v, event);
            }
        });

        v.resizeObserver = new ResizeObserver(function () {
            resize(v);
        });
        v.resizeObserver.observe(container);
        resize(v);
        return v;
    }

    function disposeView(v) {
        if (!v) {
            return;
        }
        lastCamera = cameraState(v);
        v.resizeObserver.disconnect();
        v.gizmo.detach();
        v.gizmo.dispose();
        v.orbit.dispose();
        v.renderer.dispose();
        if (v.renderer.domElement.parentNode) {
            v.renderer.domElement.parentNode.removeChild(v.renderer.domElement);
        }
    }

    function cameraState(v) {
        return {
            position: v.camera.position.clone(),
            target: v.orbit.target.clone(),
            size: v.size,
        };
    }

    function resize(v) {
        var width = v.container.clientWidth || 1;
        var height = v.container.clientHeight || 1;
        v.renderer.setSize(width, height, false);
        v.camera.aspect = width / height;
        v.camera.updateProjectionMatrix();
        requestFrame(v);
    }

    function requestFrame(v) {
        if (v.frameRequested) {
            return;
        }
        v.frameRequested = true;
        window.requestAnimationFrame(function () {
            v.frameRequested = false;
            if (view === v && v.container.isConnected) {
                v.renderer.render(v.scene, v.camera);
            }
        });
    }

    // Everything that depends on the robot's size is rebuilt when it changes
    // (another robot connected); otherwise the meshes are only moved.
    function buildParts(v, data) {
        var T = three();
        var c = v.colors;
        var size = data.size;

        while (v.root.children.length) {
            var child = v.root.children.pop();
            child.traverse(function (o) {
                if (o.geometry) {
                    o.geometry.dispose();
                }
            });
        }

        function mat(color, extra) {
            return new T.MeshStandardMaterial(
                Object.assign({ color: color, roughness: 0.55, metalness: 0.1 }, extra || {})
            );
        }

        var legRadius = size * 0.009;
        var jointRadius = size * 0.015;
        var footRadius = size * 0.022;

        var cylinder = new T.CylinderGeometry(1, 1, 1, 16);
        cylinder.rotateX(Math.PI / 2); // along z, so lookAt() aims it
        var sphere = new T.SphereGeometry(1, 24, 16);

        var parts = { legs: [], joints: [], feet: [] };

        // The floor: a large tile and a grid on it.
        var groundSize = size * 3;
        var ground = new T.Mesh(
            new T.PlaneGeometry(groundSize, groundSize),
            mat(c.ground, { roughness: 1, transparent: true, opacity: 0.9 })
        );
        var grid = new T.GridHelper(groundSize, 30, c.grid, c.grid);
        grid.rotation.x = Math.PI / 2;
        parts.ground = new T.Group();
        parts.ground.add(ground, grid);
        v.root.add(parts.ground);

        parts.support = new T.Mesh(
            new T.BufferGeometry(),
            new T.MeshBasicMaterial({
                color: c.support,
                transparent: true,
                opacity: 0.25,
                side: T.DoubleSide,
                depthWrite: false,
            })
        );
        v.root.add(parts.support);

        parts.body = new T.Mesh(
            new T.BufferGeometry(),
            mat(c.body, { transparent: true, opacity: 0.85, side: T.DoubleSide })
        );
        v.root.add(parts.body);
        parts.bodyEdges = [];
        for (var e = 0; e < 6; e++) {
            var edge = new T.Mesh(cylinder, mat(c.bodyOutline));
            edge.userData.radius = legRadius * 1.2;
            parts.bodyEdges.push(edge);
            v.root.add(edge);
        }

        parts.head = new T.Mesh(sphere, mat(c.head));
        parts.head.scale.setScalar(jointRadius * 1.2);
        parts.cog = new T.Mesh(sphere, mat(c.cog));
        parts.cog.scale.setScalar(jointRadius * 1.2);
        v.root.add(parts.head, parts.cog);

        for (var i = 0; i < 6; i++) {
            var segments = [];
            for (var s = 0; s < 3; s++) {
                var seg = new T.Mesh(cylinder, mat(c.leg));
                seg.userData.radius = legRadius;
                segments.push(seg);
                v.root.add(seg);
            }
            parts.legs.push(segments);

            var joints = [];
            for (var j = 0; j < 3; j++) {
                var joint = new T.Mesh(sphere, mat(c.joint));
                joint.scale.setScalar(jointRadius);
                joints.push(joint);
                v.root.add(joint);
            }
            parts.joints.push(joints);

            var foot = new T.Mesh(sphere, mat(c.foot, { emissive: c.foot, emissiveIntensity: 0.25 }));
            foot.scale.setScalar(footRadius);
            foot.userData.leg = i;
            parts.feet.push(foot);
            v.root.add(foot);
        }

        v.parts = parts;
        v.size = size;
    }

    function placeSegment(T, mesh, a, b) {
        var from = vec(T, a);
        var to = vec(T, b);
        var length = from.distanceTo(to);
        mesh.visible = length > 1e-6;
        if (!mesh.visible) {
            return;
        }
        mesh.position.copy(from).add(to).multiplyScalar(0.5);
        mesh.scale.set(mesh.userData.radius, mesh.userData.radius, length);
        mesh.lookAt(to);
    }

    function polygonGeometry(T, points, z) {
        // A fan from the first point; the points come convex and in order.
        var positions = [];
        for (var i = 1; i + 1 < points.length; i++) {
            [points[0], points[i], points[i + 1]].forEach(function (p) {
                positions.push(p[0], p[1], z === undefined ? p[2] : z);
            });
        }
        var geometry = new T.BufferGeometry();
        geometry.setAttribute("position", new T.Float32BufferAttribute(positions, 3));
        geometry.computeVertexNormals();
        return geometry;
    }

    // ------------------------------------------------------------- drawing

    function draw(v, data) {
        var T = three();
        var parts = v.parts;

        parts.ground.position.z = data.ground - 0.5;

        parts.support.geometry.dispose();
        parts.support.geometry = polygonGeometry(T, data.support, data.ground + 0.5);

        // Body outline in the order that walks round the hexagon: the vertices
        // come in leg order, right side front to back then left side.
        var ring = [0, 1, 2, 5, 4, 3].map(function (i) {
            return data.body[i];
        });
        parts.body.geometry.dispose();
        parts.body.geometry = polygonGeometry(T, ring);
        for (var e = 0; e < 6; e++) {
            placeSegment(T, parts.bodyEdges[e], ring[e], ring[(e + 1) % 6]);
        }
        parts.head.position.copy(vec(T, data.head));
        parts.cog.position.set(0, 0, 0);

        for (var i = 0; i < 6; i++) {
            var points = data.legs[i];
            for (var s = 0; s < 3; s++) {
                placeSegment(T, parts.legs[i][s], points[s], points[s + 1]);
            }
            for (var j = 0; j < 3; j++) {
                parts.joints[i][j].position.copy(vec(T, points[j]));
            }
            // The foot being dragged stays under the cursor; it is put back
            // where the server says once the drag is over.
            if (!(v.dragging && v.selected === i)) {
                parts.feet[i].position.copy(vec(T, points[3]));
            }
            var selected = v.editable && v.selected === i;
            parts.feet[i].material.color.set(selected ? v.colors.footSelected : v.colors.foot);
            parts.feet[i].material.emissive.set(selected ? v.colors.footSelected : v.colors.foot);
            parts.feet[i].visible = true;
        }
        requestFrame(v);
    }

    function frameCamera(v, data) {
        var size = data.size;
        if (lastCamera && Math.abs(lastCamera.size - size) < 1e-6) {
            v.camera.position.copy(lastCamera.position);
            v.orbit.target.copy(lastCamera.target);
        } else {
            v.camera.position.set(size * 0.9, -size * 1.5, size * 0.9);
            v.orbit.target.set(0, 0, data.ground * 0.5);
        }
        v.orbit.update();
    }

    // ------------------------------------------------------------- editing

    function select(v, leg) {
        if (!v.editable) {
            leg = null;
        }
        if (v.selected === leg) {
            return;
        }
        v.selected = leg;
        if (leg === null) {
            v.gizmo.detach();
        } else {
            v.gizmo.attach(v.parts.feet[leg]);
        }
        setProps(SELECTED_LEG_ID, { data: leg });
        if (v.data) {
            draw(v, v.data);
        }
    }

    function pick(v, event) {
        if (!v.editable || !v.parts) {
            return;
        }
        var T = three();
        var rect = v.renderer.domElement.getBoundingClientRect();
        var pointer = new T.Vector2(
            ((event.clientX - rect.left) / rect.width) * 2 - 1,
            -((event.clientY - rect.top) / rect.height) * 2 + 1
        );
        v.raycaster.setFromCamera(pointer, v.camera);
        var hits = v.raycaster.intersectObjects(v.parts.feet, false);
        select(v, hits.length ? hits[0].object.userData.leg : null);
    }

    function sendTarget(v, now) {
        if (v.selected === null) {
            return;
        }
        if (v.sendTimer) {
            window.clearTimeout(v.sendTimer);
            v.sendTimer = null;
        }
        var elapsed = Date.now() - v.lastSent;
        if (!now && elapsed < SEND_INTERVAL_MS) {
            v.sendTimer = window.setTimeout(function () {
                v.sendTimer = null;
                sendTarget(v, true);
            }, SEND_INTERVAL_MS - elapsed);
            return;
        }
        var p = v.parts.feet[v.selected].position;
        v.lastSent = Date.now();
        v.seq += 1;
        setProps(FOOT_TARGET_ID, {
            data: {
                leg: v.selected,
                foot: [p.x, p.y, p.z],
                seq: v.seq,
                final: !v.dragging,
            },
        });
    }

    // ------------------------------------------------------------- public

    // Draws `data` (keyframes.pose_to_scene plus "colors") into the element
    // `containerId`. `editable` is false while a sequence is being previewed:
    // the feet cannot be picked up then.
    function render(containerId, data, editable) {
        var container = document.getElementById(containerId);
        if (!container || !data || !three()) {
            return false;
        }

        // Dash builds the page anew on every visit, so the element the view
        // was mounted in may be gone; start over in the new one.
        if (view && view.container !== container) {
            disposeView(view);
            view = null;
        }
        var fresh = !view;
        if (fresh) {
            view = createView(container);
        }
        var v = view;

        // Preview frames come without colours; they keep the editor's.
        if (data.colors) {
            v.colors = Object.assign({}, DEFAULT_COLORS, data.colors);
        }
        if (fresh || !v.parts || Math.abs(v.size - data.size) > 1e-6) {
            // Another robot: the feet are about to be rebuilt, so let go of
            // the one being held rather than leave the gizmo on a dead mesh.
            if (v.selected !== null) {
                v.gizmo.detach();
                v.selected = null;
                setProps(SELECTED_LEG_ID, { data: null });
            }
            v.renderer.setClearColor(v.colors.background);
            buildParts(v, data);
            frameCamera(v, data);
        }

        v.editable = editable !== false;
        if (!v.editable && v.selected !== null) {
            select(v, null);
        }
        v.data = data;
        draw(v, data);
        return true;
    }

    function resetCamera() {
        if (view && view.data) {
            lastCamera = null;
            frameCamera(view, view.data);
            requestFrame(view);
        }
    }

    // Where a foot is drawn, in page pixels, or null before the first draw.
    // For scripts that drive the editor, such as tools/make_screenshots.py.
    function footScreenPosition(leg) {
        if (!view || !view.parts) {
            return null;
        }
        var p = view.parts.feet[leg].position.clone().project(view.camera);
        var rect = view.renderer.domElement.getBoundingClientRect();
        return {
            x: rect.left + ((p.x + 1) / 2) * rect.width,
            y: rect.top + ((1 - p.y) / 2) * rect.height,
        };
    }

    window.hexapodPoser = {
        render: render,
        resetCamera: resetCamera,
        footScreenPosition: footScreenPosition,
    };
})();
