// The 3D view of the hexapod, in the middle of the workspace.
//
// It draws a scene the server builds (hexapod/scene.py) and nothing else: the
// kinematics all happen in Python. The scene goes in a dcc.Store and a
// clientside callback hands it to hexapodView.render() -- see
// pages/page_pose.py.
//
// While it shows the pose (pages/page_pose.py) the view is also editable: a
// foot, or the body, can be clicked to pick it up -- which the page hears of
// through the "pose-selection" store, and shows its controls -- and then
// dragged by its handles: a foot by arrows, the body by arrows that move it
// or rings that turn it. A drag becomes a target in the "pose-foot-target" or
// "pose-body-target" store; the server solves the joints and sends back the
// new scene. A foot that cannot get there springs back to where the server
// last put it, and the body is held to the range of its sliders.
//
// Coordinates are millimetres, z up: the robot's body frame at standby,
// raised to stand on the floor at z = 0.
//
// Dash loads every .js file in assets/ on its own, so this is a plain script.
// three.js comes from assets/vendor/three.bundle.min.js (window.HexapodThree);
// see tools/build_three_bundle.sh. It is only looked up when a view is first
// drawn, so the order the two files load in does not matter.

(function () {
    "use strict";

    // The pose page's stores, written while editing.
    var FOOT_TARGET_ID = "pose-foot-target";
    var BODY_TARGET_ID = "pose-body-target";
    var SELECTION_ID = "pose-selection";

    // What is picked is a leg's id, for its foot, or this, or null.
    var BODY = "body";

    // How often a target is sent while dragging, in ms. The final position
    // is always sent when the drag ends.
    var SEND_INTERVAL_MS = 80;

    // A press that moves further than this (px) is an orbit, not a click.
    var CLICK_SLOP = 5;

    // A degree, in radians.
    var DEGREE = Math.PI / 180;

    // Fallbacks only; every scene carries style_settings.py's colours.
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
        axisX: "#e63946",
        axisY: "#f7c600",
        axisZ: "#4cc9f0",
    };

    // One view per container id. A page is built anew on every visit, so the
    // element a view was mounted in can disappear; the camera it was left at
    // is kept here by id, so coming back to a page finds the same view.
    var views = {};
    var cameras = {};
    // Which handles the body is dragged by, "translate" or "rotate", by view
    // id too: it can be set before the view is first drawn.
    var bodyModes = {};

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

    function createView(id, container) {
        var T = three();
        var renderer = new T.WebGLRenderer({ antialias: true });
        renderer.setPixelRatio(window.devicePixelRatio || 1);
        renderer.domElement.style.display = "block";
        renderer.domElement.style.width = "100%";
        renderer.domElement.style.height = "100%";
        renderer.domElement.style.touchAction = "none";
        container.appendChild(renderer.domElement);

        // Names the leg under the pointer, as the firmware numbers it.
        var label = document.createElement("div");
        label.className = "hexapod-view-label";
        label.style.display = "none";
        container.appendChild(label);

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

        // What the gizmo holds the body by: nothing to see, placed on the
        // body's frame. Its Euler angles are turned in the order the pose's
        // rotations are (hexapod/pose_layers.py), so they are those angles.
        var bodyHandle = new T.Group();
        bodyHandle.rotation.order = "XYZ";
        scene.add(bodyHandle);

        var v = {
            id: id,
            container: container,
            renderer: renderer,
            scene: scene,
            camera: camera,
            orbit: orbit,
            gizmo: gizmo,
            bodyHandle: bodyHandle,
            raycaster: new T.Raycaster(),
            root: new T.Group(),
            parts: null,
            colors: DEFAULT_COLORS,
            size: 0,
            data: null,
            editable: false,
            selected: null,
            dragging: false,
            seq: 0,
            lastSent: 0,
            sendTimer: null,
            frameRequested: false,
            pointerDown: null,
            label: label,
            hoverFrame: false,
        };
        scene.add(v.root);

        orbit.addEventListener("change", function () {
            cameras[id] = cameraState(v);
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
        canvas.addEventListener("pointermove", function (event) {
            if (v.hoverFrame) {
                return;
            }
            v.hoverFrame = true;
            window.requestAnimationFrame(function () {
                v.hoverFrame = false;
                hover(v, event);
            });
        });
        canvas.addEventListener("pointerleave", function () {
            label.style.display = "none";
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
        v.resizeObserver.disconnect();
        if (v.sendTimer) {
            window.clearTimeout(v.sendTimer);
        }
        v.gizmo.detach();
        v.gizmo.dispose();
        v.orbit.dispose();
        v.root.traverse(function (o) {
            if (o.geometry) {
                o.geometry.dispose();
            }
        });
        v.renderer.dispose();
        // Browsers allow only a handful of live WebGL contexts; give this one
        // back now rather than whenever the canvas is collected.
        v.renderer.forceContextLoss();
        if (v.renderer.domElement.parentNode) {
            v.renderer.domElement.parentNode.removeChild(v.renderer.domElement);
        }
        if (v.label.parentNode) {
            v.label.parentNode.removeChild(v.label);
        }
    }

    // Views whose page has been navigated away from.
    function disposeDetached() {
        Object.keys(views).forEach(function (id) {
            var v = views[id];
            if (!v.container.isConnected || document.getElementById(id) !== v.container) {
                disposeView(v);
                delete views[id];
            }
        });
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
        // Resizing the canvas clears it. Drawn again straight away rather than
        // on the next frame, so it is never caught blank in between: the view
        // is resized whenever the panels around it change height.
        if (views[v.id] === v) {
            v.renderer.render(v.scene, v.camera);
        } else {
            requestFrame(v);
        }
    }

    function requestFrame(v) {
        if (v.frameRequested) {
            return;
        }
        v.frameRequested = true;
        window.requestAnimationFrame(function () {
            v.frameRequested = false;
            if (views[v.id] === v && v.container.isConnected) {
                v.renderer.render(v.scene, v.camera);
            }
        });
    }

    // Everything sized to the robot is rebuilt when its size changes (other
    // dimensions, another robot); otherwise the meshes are only moved.
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

        var parts = { legs: [], joints: [], feet: [], axes: [] };

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
        // What a click picks the body by.
        parts.bodyParts = [parts.body, parts.head, parts.cog].concat(parts.bodyEdges);

        // Up to six axis arrows: the body's own three and the world's three.
        // Drawn on top of everything, as a HUD overlay.
        var axisColors = { x: c.axisX, y: c.axisY, z: c.axisZ };
        for (var a = 0; a < 6; a++) {
            var axis = new T.Mesh(
                cylinder,
                new T.MeshBasicMaterial({ color: c.axisX, transparent: true, depthTest: false })
            );
            axis.renderOrder = 10;
            axis.visible = false;
            parts.axes.push(axis);
            v.root.add(axis);
        }
        parts.axisColors = axisColors;
        parts.axisRadius = legRadius * 0.45;

        for (var i = 0; i < 6; i++) {
            var segments = [];
            for (var s = 0; s < 3; s++) {
                var seg = new T.Mesh(cylinder, mat(c.leg));
                seg.userData.radius = legRadius;
                seg.userData.leg = i;
                segments.push(seg);
                v.root.add(seg);
            }
            parts.legs.push(segments);

            var joints = [];
            for (var j = 0; j < 3; j++) {
                var joint = new T.Mesh(sphere, mat(c.joint));
                joint.scale.setScalar(jointRadius);
                joint.userData.leg = i;
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

        parts.legParts = [];
        for (var k = 0; k < 6; k++) {
            parts.legParts = parts.legParts.concat(parts.legs[k], parts.joints[k], [parts.feet[k]]);
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
        parts.support.geometry = polygonGeometry(T, data.support || [], data.ground + 0.5);

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
        parts.cog.position.copy(vec(T, data.cog || [0, 0, 0]));
        var bodyPicked = v.editable && v.selected === BODY;
        parts.bodyEdges.forEach(function (edge) {
            edge.material.color.set(bodyPicked ? v.colors.footSelected : v.colors.bodyOutline);
        });
        // The body being dragged stays under the cursor, as a foot does.
        if (data.frame && !(v.dragging && v.selected === BODY)) {
            v.bodyHandle.position.copy(vec(T, data.frame.origin));
            v.bodyHandle.rotation.set(
                data.frame.rot[0] * DEGREE,
                data.frame.rot[1] * DEGREE,
                data.frame.rot[2] * DEGREE
            );
        }

        var axes = data.axes || [];
        for (var a = 0; a < parts.axes.length; a++) {
            var mesh = parts.axes[a];
            var axis = axes[a];
            if (!axis) {
                mesh.visible = false;
                continue;
            }
            mesh.material.color.set(parts.axisColors[axis.axis]);
            mesh.material.opacity = axis.world ? 0.55 : 1;
            mesh.userData.radius = parts.axisRadius * (axis.world ? 0.7 : 1);
            placeSegment(T, mesh, axis.from, axis.to);
        }

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
        }
        requestFrame(v);
    }

    function frameCamera(v, data, saved) {
        var size = data.size;
        // A camera from an earlier visit is only reused for a robot of about
        // the same size; framed for another, it could be inside it.
        if (saved && Math.abs(saved.size - size) <= 0.25 * size) {
            v.camera.position.copy(saved.position);
            v.orbit.target.copy(saved.target);
        } else {
            var cog = data.cog || [0, 0, 0];
            var targetZ = (cog[2] + data.ground) / 2;
            v.orbit.target.set(0, 0, targetZ);
            v.camera.position.set(size * 0.9, -size * 1.5, targetZ + size * 0.9);
        }
        v.orbit.update();
    }

    // ------------------------------------------------------------- editing

    // The body is moved along the world's axes, as its sliders move it, and
    // turned about its own.
    function holdBody(v) {
        var mode = bodyModes[v.id] === "rotate" ? "rotate" : "translate";
        v.gizmo.setMode(mode);
        v.gizmo.setSpace(mode === "rotate" ? "local" : "world");
        v.gizmo.attach(v.bodyHandle);
    }

    // Picks `what` up: a leg's id for its foot, BODY, or null to let go.
    function select(v, what) {
        if (!v.editable || (what === BODY && !(v.data && v.data.frame))) {
            what = null;
        }
        if (v.selected === what) {
            return;
        }
        v.selected = what;
        if (what === null) {
            v.gizmo.detach();
        } else if (what === BODY) {
            holdBody(v);
        } else {
            v.gizmo.setMode("translate");
            v.gizmo.setSpace("world");
            v.gizmo.attach(v.parts.feet[what]);
        }
        setProps(SELECTION_ID, { data: what });
        if (v.data) {
            draw(v, v.data);
        }
    }

    // The first of `objects` under the pointer, or null.
    function hit(v, event, objects) {
        var T = three();
        var rect = v.renderer.domElement.getBoundingClientRect();
        var pointer = new T.Vector2(
            ((event.clientX - rect.left) / rect.width) * 2 - 1,
            -((event.clientY - rect.top) / rect.height) * 2 + 1
        );
        v.raycaster.setFromCamera(pointer, v.camera);
        var hits = v.raycaster.intersectObjects(objects, false);
        return hits.length ? hits[0].object : null;
    }

    // What a click on `object` picks: its foot's leg, or the body.
    function pickable(v, object) {
        if (v.parts.feet.indexOf(object) >= 0) {
            return object.userData.leg;
        }
        return v.parts.bodyParts.indexOf(object) >= 0 ? BODY : null;
    }

    function pick(v, event) {
        if (!v.editable || !v.parts) {
            return;
        }
        var over = hit(v, event, v.parts.feet.concat(v.parts.bodyParts));
        select(v, over ? pickable(v, over) : null);
    }

    function hover(v, event) {
        var labels = v.data && v.data.labels;
        var over = null;
        if (v.parts && labels && !v.dragging) {
            over = hit(v, event, v.parts.legParts.concat(v.parts.bodyParts));
        }
        if (!over) {
            v.label.style.display = "none";
            v.renderer.domElement.style.cursor = "";
            return;
        }
        var onBody = v.parts.bodyParts.indexOf(over) >= 0;
        var rect = v.container.getBoundingClientRect();
        v.label.textContent = onBody ? "Body" : labels[over.userData.leg];
        v.label.style.left = event.clientX - rect.left + 14 + "px";
        v.label.style.top = event.clientY - rect.top + 10 + "px";
        v.label.style.display = "block";
        var canPick = v.editable && pickable(v, over) !== null;
        v.renderer.domElement.style.cursor = canPick ? "pointer" : "";
    }

    // Where what is held has been dragged to: a foot's position, or the
    // body's and its rotations in degrees.
    function target(v) {
        var data = { seq: v.seq, final: !v.dragging };
        if (v.selected === BODY) {
            var p = v.bodyHandle.position;
            var r = v.bodyHandle.rotation;
            data.origin = [p.x, p.y, p.z];
            data.rot = [r.x / DEGREE, r.y / DEGREE, r.z / DEGREE];
            return { id: BODY_TARGET_ID, data: data };
        }
        var foot = v.parts.feet[v.selected].position;
        data.leg = v.selected;
        data.foot = [foot.x, foot.y, foot.z];
        return { id: FOOT_TARGET_ID, data: data };
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
        v.lastSent = Date.now();
        v.seq += 1;
        var sent = target(v);
        setProps(sent.id, { data: sent.data });
    }

    // ------------------------------------------------------------- public

    // Draws `data` (hexapod/scene.py) into the element with id `containerId`.
    //
    // options.editable  the body and the feet can be picked up and dragged
    //                   (false while a sequence is previewed)
    // options.zoom      false leaves the mouse wheel to the page, for a view
    //                   that sits in a scrolling page
    function render(containerId, data, options) {
        options = options || {};
        var container = document.getElementById(containerId);
        if (!container || !data || !three()) {
            return false;
        }

        disposeDetached();
        var v = views[containerId];
        var fresh = !v;
        if (fresh) {
            v = views[containerId] = createView(containerId, container);
        }

        if (data.colors) {
            v.colors = Object.assign({}, DEFAULT_COLORS, data.colors);
        }
        if (fresh || !v.parts || Math.abs(v.size - data.size) > 1e-6) {
            // The feet are about to be rebuilt, so let go of what is being
            // held rather than leave the gizmo on a dead mesh.
            if (v.selected !== null) {
                v.gizmo.detach();
                v.selected = null;
                setProps(SELECTION_ID, { data: null });
            }
            v.renderer.setClearColor(v.colors.background);
            buildParts(v, data);
            // The camera stays where the user put it while the robot is
            // resized; only a view that is new to this page is framed.
            if (fresh) {
                frameCamera(v, data, cameras[containerId]);
            }
        }

        v.orbit.enableZoom = options.zoom !== false;
        v.editable = options.editable === true;
        if (!v.editable && v.selected !== null) {
            select(v, null);
        }
        v.data = data;
        draw(v, data);
        return true;
    }

    function resetCamera(containerId) {
        var v = views[containerId];
        if (v && v.data) {
            delete cameras[containerId];
            frameCamera(v, v.data, null);
            cameras[containerId] = cameraState(v);
            requestFrame(v);
        }
    }

    // Picks up a foot, by its leg's id, or the body ("body"), or lets go
    // (null), as clicking in the view would: for the pose page's buttons.
    function selectIn(containerId, what) {
        var v = views[containerId];
        if (v && v.parts) {
            select(v, what === undefined ? null : what);
        }
    }

    // Which handles the body is dragged by: "translate" for arrows that move
    // it, "rotate" for rings that turn it.
    function setBodyMode(containerId, mode) {
        bodyModes[containerId] = mode;
        var v = views[containerId];
        if (v && v.selected === BODY) {
            holdBody(v);
            requestFrame(v);
        }
    }

    // Where a foot is drawn, in page pixels, or null before the first draw.
    // For scripts that drive the pose page in a browser.
    function footScreenPosition(containerId, leg) {
        var v = views[containerId];
        if (!v || !v.parts) {
            return null;
        }
        var p = v.parts.feet[leg].position.clone().project(v.camera);
        var rect = v.renderer.domElement.getBoundingClientRect();
        return {
            x: rect.left + ((p.x + 1) / 2) * rect.width,
            y: rect.top + ((1 - p.y) / 2) * rect.height,
        };
    }

    window.hexapodView = {
        render: render,
        resetCamera: resetCamera,
        select: selectIn,
        setBodyMode: setBodyMode,
        footScreenPosition: footScreenPosition,
    };
})();
