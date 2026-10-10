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
        joint: "#55627e",
        jointAccent: "#3b7bff",
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

        // The sun casts the robot's shadow on the floor; where it stands and
        // how much it covers go by the robot's size (buildParts). A weak light
        // from the other side keeps the faces turned away from it readable.
        renderer.shadowMap.enabled = true;
        scene.add(new T.HemisphereLight(0xffffff, 0x223355, 1.5));
        var sun = new T.DirectionalLight(0xffffff, 2.2);
        sun.castShadow = true;
        sun.shadow.mapSize.set(2048, 2048);
        sun.shadow.radius = 3;
        scene.add(sun);
        var fill = new T.DirectionalLight(0x9db8ff, 0.6);
        fill.position.set(-2, 3, 1);
        scene.add(fill);

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
            sun: sun,
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
        v.sun.dispose();
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

        // A part of the robot itself, which is what throws a shadow.
        function solid(geometry, material) {
            var mesh = new T.Mesh(geometry, material);
            mesh.castShadow = true;
            v.root.add(mesh);
            return mesh;
        }

        var linkRadius = size * 0.013;
        var hubRadius = size * 0.021;
        var footRadius = size * 0.017;
        var thickness = size * 0.034;

        // Unit shapes along z, so lookAt() aims them, scaled where they are
        // placed. A link narrows towards its far end: the femur a little, and
        // the tibia from there down to the foot.
        function along(geometry) {
            return geometry.rotateX(Math.PI / 2);
        }
        var cylinder = along(new T.CylinderGeometry(1, 1, 1, 32));
        var femur = along(new T.CylinderGeometry(0.8, 1, 1, 24));
        var tibia = along(new T.CylinderGeometry(0.35, 0.8, 1, 24));
        var cone = along(new T.CylinderGeometry(0, 1, 1, 16));
        var sphere = new T.SphereGeometry(1, 24, 16);

        var parts = { legs: [], joints: [], feet: [], axes: [] };
        parts.thickness = thickness;

        // The floor: a disc that fades into the background towards its rim,
        // the grid on it fading with it, and over both what the robot's
        // shadow falls on.
        var groundRadius = size * 2.5;
        var cell = size / 10;
        var groundColor = new T.Color(c.ground);
        var backgroundColor = new T.Color(c.background);
        var gridColor = new T.Color(c.grid);
        function floorColor(r) {
            var t = smoothstep(r, groundRadius * 0.3, groundRadius);
            return groundColor.clone().lerp(backgroundColor, t);
        }
        function lineColor(r, major) {
            var strength = 1 - smoothstep(r, groundRadius * 0.25, groundRadius * 0.9);
            return floorColor(r).lerp(gridColor, strength * (major ? 1 : 0.45));
        }
        var disc = discGeometry(T, groundRadius, 12, 96, floorColor);
        var floor = new T.Mesh(
            disc,
            new T.MeshBasicMaterial({
                vertexColors: true,
                polygonOffset: true,
                polygonOffsetFactor: 1,
                polygonOffsetUnits: 1,
            })
        );
        var grid = new T.LineSegments(
            gridGeometry(T, groundRadius, cell, 5, lineColor),
            new T.LineBasicMaterial({ vertexColors: true })
        );
        var shadow = new T.Mesh(
            disc,
            new T.ShadowMaterial({ opacity: 0.4, depthWrite: false })
        );
        shadow.receiveShadow = true;
        shadow.renderOrder = 1;
        parts.ground = new T.Group();
        parts.ground.add(floor, grid, shadow);
        v.root.add(parts.ground);

        var reach = size * 1.2;
        v.sun.position.set(size, -2 * size, 3 * size);
        var lit = v.sun.shadow.camera;
        lit.left = lit.bottom = -reach;
        lit.right = lit.top = reach;
        lit.near = size;
        lit.far = size * 7;
        lit.updateProjectionMatrix();
        v.sun.shadow.normalBias = size * 0.002;

        // The polygon the robot stands on, filled faintly and outlined.
        parts.support = new T.Mesh(
            new T.BufferGeometry(),
            new T.MeshBasicMaterial({
                color: c.support,
                transparent: true,
                opacity: 0.16,
                side: T.DoubleSide,
                depthWrite: false,
            })
        );
        parts.support.renderOrder = 2;
        parts.supportOutline = new T.LineLoop(
            new T.BufferGeometry(),
            new T.LineBasicMaterial({ color: c.support, transparent: true, opacity: 0.7 })
        );
        parts.supportOutline.renderOrder = 3;
        v.root.add(parts.support, parts.supportOutline);

        // The body: a plate, with a band round its side that shows it picked
        // up, a chevron on top pointing to the front, and a disc at its centre.
        parts.body = solid(new T.BufferGeometry(), mat(c.body));
        parts.bodyTrim = solid(new T.BufferGeometry(), mat(c.bodyOutline));
        parts.head = new T.Mesh(
            new T.BufferGeometry(),
            mat(c.head, { emissive: c.head, emissiveIntensity: 0.35, side: T.DoubleSide })
        );
        parts.cog = new T.Mesh(cylinder, mat(c.cog, { emissive: c.cog, emissiveIntensity: 0.25 }));
        parts.cog.scale.set(hubRadius * 0.7, hubRadius * 0.7, thickness * 1.12);
        v.root.add(parts.head, parts.cog);
        // What a click picks the body by.
        parts.bodyParts = [parts.body, parts.bodyTrim, parts.head, parts.cog];

        // Up to six axis arrows: the body's own three and the world's three.
        // Drawn on top of everything, as a HUD overlay.
        var axisColors = { x: c.axisX, y: c.axisY, z: c.axisZ };
        for (var a = 0; a < 6; a++) {
            var axisMaterial = new T.MeshBasicMaterial({
                color: c.axisX,
                transparent: true,
                depthTest: false,
            });
            var axis = { shaft: new T.Mesh(cylinder, axisMaterial), head: new T.Mesh(cone, axisMaterial) };
            axis.shaft.renderOrder = axis.head.renderOrder = 10;
            axis.shaft.visible = axis.head.visible = false;
            parts.axes.push(axis);
            v.root.add(axis.shaft, axis.head);
        }
        parts.axisColors = axisColors;
        parts.axisRadius = size * 0.004;

        // A joint is a disc on the axis it turns about, with a band round its
        // middle in the body's trim colour.
        var armour = mat(c.leg);
        var hub = mat(c.joint);
        var accent = mat(c.jointAccent);
        for (var i = 0; i < 6; i++) {
            var segments = [cylinder, femur, tibia].map(function (shape) {
                var seg = solid(shape, armour);
                seg.userData.radius = linkRadius;
                seg.userData.leg = i;
                return seg;
            });
            parts.legs.push(segments);

            var joints = [];
            for (var j = 0; j < 3; j++) {
                var joint = solid(cylinder, hub);
                if (j === 0) {
                    joint.scale.set(hubRadius, hubRadius, thickness * 1.2);
                } else {
                    joint.scale.set(hubRadius * 0.9, hubRadius * 0.9, linkRadius * 2.4);
                }
                var band = new T.Mesh(cylinder, accent);
                band.scale.set(1.08, 1.08, 0.22);
                joint.add(band);
                joint.userData.leg = i;
                joints.push(joint);
            }
            parts.joints.push(joints);

            var foot = solid(sphere, mat(c.foot, { emissive: c.foot, emissiveIntensity: 0.35 }));
            foot.scale.setScalar(footRadius);
            foot.userData.leg = i;
            parts.feet.push(foot);
        }

        parts.legParts = [];
        for (var k = 0; k < 6; k++) {
            parts.legParts = parts.legParts.concat(parts.legs[k], parts.joints[k], [parts.feet[k]]);
        }

        v.parts = parts;
        v.size = size;
    }

    function smoothstep(x, from, to) {
        var t = Math.min(1, Math.max(0, (x - from) / (to - from)));
        return t * t * (3 - 2 * t);
    }

    // A disc on z = 0 in `rings` rings of `segments` pieces, each vertex
    // coloured by colorAt(its distance from the centre).
    function discGeometry(T, radius, rings, segments, colorAt) {
        var positions = [];
        var normals = [];
        var colors = [];
        var index = [];
        for (var ring = 0; ring <= rings; ring++) {
            var r = (radius * ring) / rings;
            var color = colorAt(r);
            for (var s = 0; s < segments; s++) {
                var angle = (2 * Math.PI * s) / segments;
                positions.push(r * Math.cos(angle), r * Math.sin(angle), 0);
                normals.push(0, 0, 1);
                colors.push(color.r, color.g, color.b);
            }
        }
        for (var inner = 0; inner < rings; inner++) {
            for (var i = 0; i < segments; i++) {
                var a = inner * segments + i;
                var b = inner * segments + ((i + 1) % segments);
                index.push(a, a + segments, b + segments, a, b + segments, b);
            }
        }
        var geometry = new T.BufferGeometry();
        geometry.setAttribute("position", new T.Float32BufferAttribute(positions, 3));
        geometry.setAttribute("normal", new T.Float32BufferAttribute(normals, 3));
        geometry.setAttribute("color", new T.Float32BufferAttribute(colors, 3));
        geometry.setIndex(index);
        return geometry;
    }

    // The lines of a grid of `cell` squares on z = 0, out to `radius`, every
    // `majorEvery`th one major. Each is cut into pieces a cell long, so that
    // colorAt(distance from the centre, major) can fade it along its length.
    function gridGeometry(T, radius, cell, majorEvery, colorAt) {
        var positions = [];
        var colors = [];
        var count = Math.floor(radius / cell);

        function point(across, along, major, swap) {
            var color = colorAt(Math.hypot(across, along), major);
            positions.push(swap ? along : across, swap ? across : along, 0);
            colors.push(color.r, color.g, color.b);
        }

        for (var line = -count; line <= count; line++) {
            var across = line * cell;
            var major = line % majorEvery === 0;
            for (var piece = -count; piece < count; piece++) {
                var from = piece * cell;
                var to = from + cell;
                if (Math.hypot(across, from) > radius || Math.hypot(across, to) > radius) {
                    continue;
                }
                for (var swap = 0; swap < 2; swap++) {
                    point(across, from, major, swap);
                    point(across, to, major, swap);
                }
            }
        }
        var geometry = new T.BufferGeometry();
        geometry.setAttribute("position", new T.Float32BufferAttribute(positions, 3));
        geometry.setAttribute("color", new T.Float32BufferAttribute(colors, 3));
        return geometry;
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

    // Puts a disc at `point`, to turn about `axis` (a unit vector).
    function placeDisc(T, mesh, point, axis) {
        mesh.position.copy(point);
        mesh.quaternion.setFromUnitVectors(new T.Vector3(0, 0, 1), axis);
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

    // Flat-faced geometry from triangles, each three Vector3s.
    function facetGeometry(T, triangles) {
        var positions = [];
        triangles.forEach(function (triangle) {
            triangle.forEach(function (p) {
                positions.push(p.x, p.y, p.z);
            });
        });
        var geometry = new T.BufferGeometry();
        geometry.setAttribute("position", new T.Float32BufferAttribute(positions, 3));
        geometry.computeVertexNormals();
        return geometry;
    }

    // The body as a plate `thickness` thick about its outline `ring`
    // (Vector3s, anticlockwise seen from `up`), its top and bottom edges cut
    // back by `chamfer`. Two geometries: the faces, and the band left round
    // the side between the two cuts.
    function plateGeometry(T, ring, up, thickness, chamfer) {
        var n = ring.length;
        var centre = new T.Vector3();
        var radius = 0;
        ring.forEach(function (p) {
            centre.add(p);
        });
        centre.divideScalar(n);
        ring.forEach(function (p) {
            radius += p.distanceTo(centre) / n;
        });
        var inset = radius > 0 ? Math.max(0, 1 - chamfer / radius) : 1;

        // `ring` drawn in by `scale` and moved `height` along `up`.
        function level(scale, height) {
            return ring.map(function (p) {
                return p.clone().sub(centre).multiplyScalar(scale).add(centre).addScaledVector(up, height);
            });
        }
        var half = thickness / 2;
        var bottom = level(inset, -half);
        var low = level(1, chamfer - half);
        var high = level(1, half - chamfer);
        var top = level(inset, half);

        function band(lower, upper) {
            var triangles = [];
            for (var i = 0; i < n; i++) {
                var j = (i + 1) % n;
                triangles.push([lower[i], lower[j], upper[j]], [lower[i], upper[j], upper[i]]);
            }
            return triangles;
        }
        // The top and bottom are fans from the centre, which sees the whole
        // outline even of a body narrower at its middle than at its ends.
        var faces = band(bottom, low).concat(band(high, top));
        var above = centre.clone().addScaledVector(up, half);
        var below = centre.clone().addScaledVector(up, -half);
        for (var i = 0; i < n; i++) {
            var j = (i + 1) % n;
            faces.push([above, top[i], top[j]], [below, bottom[j], bottom[i]]);
        }
        return { faces: facetGeometry(T, faces), trim: facetGeometry(T, band(low, high)) };
    }

    // The body's own up, from its outline; straight up for a body that has
    // been given no area.
    function bodyUp(T, body) {
        var across = vec(T, body[3]).sub(vec(T, body[0]));
        var back = vec(T, body[2]).sub(vec(T, body[0]));
        var up = across.cross(back);
        return up.lengthSq() > 1e-6 ? up.normalize() : up.set(0, 0, 1);
    }

    // What a leg's knee and ankle turn about: across the plane the leg bends
    // in, which the body's up lies in too. Taken with whichever link is
    // furthest from in line with that.
    function legAxis(T, points, up) {
        var axis = new T.Vector3(1, 0, 0);
        var best = 1e-6;
        for (var s = 0; s < 3; s++) {
            var link = vec(T, points[s + 1]).sub(vec(T, points[s]));
            var across = new T.Vector3().crossVectors(up, link);
            if (across.lengthSq() > best) {
                best = across.lengthSq();
                axis = across;
            }
        }
        return axis.normalize();
    }

    // ------------------------------------------------------------- drawing

    function draw(v, data) {
        var T = three();
        var parts = v.parts;

        parts.ground.position.z = data.ground - 0.5;

        var support = data.support || [];
        parts.support.geometry.dispose();
        parts.support.geometry = polygonGeometry(T, support, data.ground + 0.5);
        parts.supportOutline.geometry.dispose();
        parts.supportOutline.geometry = new T.BufferGeometry().setFromPoints(
            support.map(function (p) {
                return new T.Vector3(p[0], p[1], data.ground + 0.6);
            })
        );

        // The body's outline in the order that walks round the hexagon
        // anticlockwise: the vertices come in leg order, right side front to
        // back then left side.
        var up = bodyUp(T, data.body);
        var ring = [3, 4, 5, 2, 1, 0].map(function (i) {
            return vec(T, data.body[i]);
        });
        var plate = plateGeometry(T, ring, up, parts.thickness, parts.thickness * 0.22);
        parts.body.geometry.dispose();
        parts.body.geometry = plate.faces;
        parts.bodyTrim.geometry.dispose();
        parts.bodyTrim.geometry = plate.trim;
        var bodyPicked = v.editable && v.selected === BODY;
        parts.bodyTrim.material.color.set(bodyPicked ? v.colors.footSelected : v.colors.bodyOutline);

        // On the plate's top face, a chevron from the centre towards the head.
        var cog = vec(T, data.cog || [0, 0, 0]);
        var forward = vec(T, data.head).sub(cog);
        var side = new T.Vector3().crossVectors(forward, up);
        var halfFront = vec(T, data.body[0]).distanceTo(vec(T, data.body[3])) / 2;
        side.setLength(Math.min(0.24 * forward.length(), 0.5 * halfFront));
        var face = cog.clone().addScaledVector(up, parts.thickness * 0.53);
        function onFace(along, across) {
            return face.clone().addScaledVector(forward, along).addScaledVector(side, across);
        }
        var tip = onFace(0.82, 0);
        var notch = onFace(0.62, 0);
        parts.head.geometry.dispose();
        parts.head.geometry = facetGeometry(T, [
            [tip, onFace(0.5, -1), notch],
            [tip, notch, onFace(0.5, 1)],
        ]);
        placeDisc(T, parts.cog, cog, up);

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
            var arrow = parts.axes[a];
            var axis = axes[a];
            if (!axis) {
                arrow.shaft.visible = arrow.head.visible = false;
                continue;
            }
            arrow.shaft.material.color.set(parts.axisColors[axis.axis]);
            arrow.shaft.material.opacity = axis.world ? 0.55 : 1;
            var radius = parts.axisRadius * (axis.world ? 0.7 : 1);
            // The arrowhead takes the last of the length.
            var to = vec(T, axis.to);
            var neck = vec(T, axis.from).lerp(to, 0.78).toArray();
            arrow.shaft.userData.radius = radius;
            arrow.head.userData.radius = radius * 2.6;
            placeSegment(T, arrow.shaft, axis.from, neck);
            placeSegment(T, arrow.head, neck, axis.to);
        }

        for (var i = 0; i < 6; i++) {
            var points = data.legs[i];
            for (var s = 0; s < 3; s++) {
                placeSegment(T, parts.legs[i][s], points[s], points[s + 1]);
            }
            // The hip turns about the body's up, the knee and ankle across
            // the leg.
            var across = legAxis(T, points, up);
            for (var j = 0; j < 3; j++) {
                placeDisc(T, parts.joints[i][j], vec(T, points[j]), j === 0 ? up : across);
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
