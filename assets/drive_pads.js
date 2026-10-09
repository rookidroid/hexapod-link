// The controller over the view (DRIVE_HUD in widgets/robot_link_ui.py), after
// the Android app's control screen: a body pad of moves on the spot, and a
// move pad of walks round standby. Each pad is drawn here as SVG from the
// layout the page carries, one shape per motion, so where a press lands is
// exactly what it shows.
//
// A pad drives the robot while it is held: the motion is sent on the press,
// on sliding onto another, and again every RENEW_MS to renew the hold; letting
// go sends standby. If the renewals stop without that -- the page closed, the
// network gone -- the robot stands on its own once the hold runs out
// (ROBOT_DRIVE_HOLD_S in settings.py). The route is in pages/drive.py.
(function () {
    "use strict";

    var SVG_NS = "http://www.w3.org/2000/svg";
    var ROUTE = "/api/drive";
    // Well inside ROBOT_DRIVE_HOLD_S (600 ms), so a late renewal or two does
    // not stop the robot mid-stride.
    var RENEW_MS = 200;
    // Element ids from widgets/robot_link_ui.py.
    var READOUT_ID = "drive-readout";
    var IDLE_TEXT = "Hold a pad to move";

    var held = null; // {pointerId, pad, zone, motion}
    var renewTimer = null;

    // ---------------------------------------------------------- drawing

    function svg(name, attrs, parent) {
        var node = document.createElementNS(SVG_NS, name);
        Object.keys(attrs || {}).forEach(function (key) {
            node.setAttribute(key, attrs[key]);
        });
        if (parent) {
            parent.appendChild(node);
        }
        return node;
    }

    // A point at radius r and bearing deg: 0 is up (forward), clockwise.
    function polar(r, deg) {
        var rad = (deg * Math.PI) / 180;
        return [r * Math.sin(rad), -r * Math.cos(rad)];
    }

    // The ring sector between radii r0 < r1 and bearings a0 < a1.
    function sector(r0, r1, a0, a1) {
        var large = a1 - a0 > 180 ? 1 : 0;
        var p0 = polar(r1, a0), p1 = polar(r1, a1);
        var p2 = polar(r0, a1), p3 = polar(r0, a0);
        return [
            "M", p0, "A", r1, r1, 0, large, 1, p1,
            "L", p2, "A", r0, r0, 0, large, 0, p3, "Z",
        ].join(" ");
    }

    function zone(parent, motion, labels) {
        var group = svg("g", {"class": "drive-zone", "data-motion": motion}, parent);
        svg("title", {}, group).textContent = labels[motion] || motion;
        return group;
    }

    function glyph(parent, x, y, text, size, extraClass) {
        var node = svg("text", {
            x: x,
            y: y,
            "font-size": size,
            "class": "drive-glyph" + (extraClass ? " " + extraClass : ""),
            "text-anchor": "middle",
            "dominant-baseline": "central",
        }, parent);
        node.textContent = text;
        return node;
    }

    // Standby in the middle, eight walks round it, and fast forward, the turns
    // and fast backward round those -- the Android app's circle.
    var CENTRE_R = 27, WALK_R = 64, OUTER_R = 98;

    function drawMovePad(pad, layout, labels) {
        var root = svg("svg", {viewBox: "-100 -100 200 200", "class": "drive-svg"}, pad);

        layout.outer.forEach(function (motion, i) {
            var bearing = i * 90;
            var group = zone(root, motion, labels);
            svg("path", {d: sector(WALK_R, OUTER_R, bearing - 45, bearing + 45), "class": "drive-face drive-face-outer"}, group);
            // Drawn at the top and turned into place; the left turn is the
            // right one mirrored, so it curves the other way round.
            var transform = "rotate(" + bearing + ")" + (bearing === 270 ? " scale(-1,1)" : "");
            var icon = svg("g", {transform: transform, "class": "drive-icon"}, group);
            if (bearing % 180 === 0) {
                // Fast forward and back: a double arrowhead.
                svg("path", {d: "M0,-92 L9,-82 L-9,-82 Z M0,-83 L9,-73 L-9,-73 Z"}, icon);
            } else {
                // The turns: an arrow sweeping round the side it turns to.
                var from = polar(82, -32), to = polar(82, 26);
                svg("path", {d: ["M", from, "A", 82, 82, 0, 0, 1, to].join(" "), "class": "drive-stroke"}, icon);
                svg("path", {d: ["M", polar(82, 37), "L", polar(73, 25), "L", polar(91, 25), "Z"].join(" ")}, icon);
            }
        });

        layout.walk.forEach(function (motion, i) {
            var bearing = i * 45;
            var group = zone(root, motion, labels);
            svg("path", {d: sector(CENTRE_R, WALK_R, bearing - 22.5, bearing + 22.5), "class": "drive-face drive-face-walk"}, group);
            svg("path", {
                d: "M0,-55 L7,-43 L-7,-43 Z",
                transform: "rotate(" + bearing + ")",
                "class": "drive-icon",
            }, group);
        });

        var centre = zone(root, layout.centre, labels);
        svg("circle", {r: CENTRE_R - 2, "class": "drive-face drive-face-centre"}, centre);
        // Standby: a pause sign, as on the Android app.
        svg("path", {d: "M-8,-10 h5 v20 h-5 Z M3,-10 h5 v20 h-5 Z", "class": "drive-icon"}, centre);
    }

    // What each body move is drawn with, over its short name.
    var BODY_GLYPHS = {
        rotate_y: "↔",
        rotate_x: "↕",
        rotate_z: "⟳",
        climb_forward: "▲",
        twist: "∞",
        climb_backward: "▼",
    };
    var CELL = 60;

    function drawBodyPad(pad, rows, labels) {
        var root = svg("svg", {
            viewBox: "0 0 " + 2 * CELL + " " + rows.length * CELL,
            "class": "drive-svg",
        }, pad);
        rows.forEach(function (row, r) {
            row.forEach(function (cell, c) {
                var motion = cell[0], name = cell[1];
                var x = c * CELL, y = r * CELL;
                var group = zone(root, motion, labels);
                svg("rect", {x: x + 1, y: y + 1, width: CELL - 2, height: CELL - 2, "class": "drive-face"}, group);
                glyph(group, x + CELL / 2, y + CELL / 2 - 6, BODY_GLYPHS[motion] || "•", 22);
                glyph(group, x + CELL / 2, y + CELL - 11, name.toUpperCase(), 9, "drive-name");
            });
        });
    }

    function build(controls) {
        var layout;
        try {
            layout = JSON.parse(controls.getAttribute("data-layout"));
        } catch (error) {
            return;
        }
        controls.querySelectorAll(".drive-pad").forEach(function (pad) {
            if (pad.querySelector("svg")) {
                return;
            }
            if (pad.getAttribute("data-pad") === "move") {
                drawMovePad(pad, layout.move, layout.labels);
            } else {
                drawBodyPad(pad, layout.body, layout.labels);
            }
        });
        controls.__driveLabels = layout.labels;
    }

    // Dash renders the page after this script runs, so the pads are drawn
    // when they appear.
    function buildAll() {
        document.querySelectorAll("[data-layout]").forEach(function (controls) {
            if (controls.querySelector(".drive-pad:empty")) {
                build(controls);
            }
        });
    }

    new MutationObserver(buildAll).observe(document.documentElement, {
        childList: true,
        subtree: true,
    });

    // ---------------------------------------------------------- driving

    function setReadout(text) {
        var readout = document.getElementById(READOUT_ID);
        if (readout) {
            readout.textContent = text;
        }
    }

    function post(body, keepalive) {
        return fetch(ROUTE, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(body),
            keepalive: !!keepalive,
        })
            .then(function (response) {
                return response.json();
            })
            .then(function (reply) {
                if (reply.message) {
                    setReadout(reply.message);
                }
                return reply;
            })
            .catch(function () {
                setReadout("The app is not answering.");
            });
    }

    function labelOf(pad, motion) {
        var controls = pad.closest("[data-layout]");
        var labels = (controls && controls.__driveLabels) || {};
        return labels[motion] || motion;
    }

    function zoneAt(x, y) {
        var hit = document.elementFromPoint(x, y);
        return hit && hit.closest ? hit.closest(".drive-zone") : null;
    }

    function select(zoneNode) {
        if (!held || held.zone === zoneNode) {
            return;
        }
        if (held.zone) {
            held.zone.classList.remove("is-active");
        }
        held.zone = zoneNode;
        held.motion = zoneNode.getAttribute("data-motion");
        zoneNode.classList.add("is-active");
        setReadout(labelOf(held.pad, held.motion));
        post({motion: held.motion});
    }

    function release() {
        if (!held) {
            return;
        }
        if (held.zone) {
            held.zone.classList.remove("is-active");
        }
        held = null;
        clearInterval(renewTimer);
        renewTimer = null;
        setReadout(IDLE_TEXT);
        // Sent even if the page is going away, so the robot stands now rather
        // than when its hold runs out.
        post({motion: "standby"}, true);
    }

    document.addEventListener("pointerdown", function (event) {
        var zoneNode = event.target.closest && event.target.closest(".drive-zone");
        if (!zoneNode || event.button !== 0) {
            return;
        }
        var pad = zoneNode.closest(".drive-pad");
        if (pad.closest(".is-offline")) {
            return;
        }
        event.preventDefault();
        release();
        held = {pointerId: event.pointerId, pad: pad, zone: null, motion: null};
        // Keeps the moves and the release coming here, wherever the pointer
        // goes while the pad is held.
        try {
            pad.setPointerCapture(event.pointerId);
        } catch (error) {
            // A pointer the browser no longer knows; the release still comes.
        }
        select(zoneNode);
        renewTimer = setInterval(function () {
            if (held && held.motion) {
                post({motion: held.motion});
            }
        }, RENEW_MS);
    });

    // Sliding onto another zone of the same pad changes gait; off the pad, the
    // last one keeps going, as on the Android app, until let go.
    document.addEventListener("pointermove", function (event) {
        if (!held || event.pointerId !== held.pointerId) {
            return;
        }
        var zoneNode = zoneAt(event.clientX, event.clientY);
        if (zoneNode && zoneNode.closest(".drive-pad") === held.pad) {
            select(zoneNode);
        }
    });

    ["pointerup", "pointercancel", "lostpointercapture"].forEach(function (type) {
        document.addEventListener(type, function (event) {
            if (held && event.pointerId === held.pointerId) {
                release();
            }
        }, true);
    });

    window.addEventListener("blur", release);
    document.addEventListener("visibilitychange", function () {
        if (document.hidden) {
            release();
        }
    });
})();
