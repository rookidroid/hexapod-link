// The workspace's splitters (make_workspace in pages/shared.py): one on the
// tool panel's right edge sets its width, one on the dock's top edge its
// height. Drag one, or focus it and use the arrow keys (Shift for bigger
// steps); double-click it to put the size back to the stylesheet's.
//
// A size is a CSS variable on <html> (WORKSPACE in assets/industrial.css),
// where hexapod_link.py writes the saved ones before the page is served. One
// let go of goes to the sizes store, to be kept with the preferences
// (keep_layout_sizes in pages/shared.py). A drag is held to the window, so
// the view always keeps some room; the stylesheet keeps that room too when
// the window is made smaller than the sizes were set for.
//
// Only above `lg`: below it everything stacks and the splitters are hidden.
(function () {
    "use strict";

    var STORE_ID = "layout-sizes";
    var WIDE = window.matchMedia("(min-width: 992px)");
    // How much of the window the view always keeps (px; --view-min-w and
    // --view-min-h in the stylesheet), and the smallest a panel may be made.
    var VIEW_MIN_W = 360;
    var VIEW_MIN_H = 180;
    var PANEL_MIN_W = 220;
    var PANEL_MAX_W = 720;
    var DOCK_MIN_H = 140;
    var KEY_STEP = 16;
    var KEY_STEP_BIG = 64;

    var SIZES = {
        panel: {
            variable: "--panel-w",
            key: "panel_w",
            selector: ".ws-panel",
            cursor: "col-resize",
            // How big the panel is, and how big it is made with the pointer
            // at (x, y).
            current: function (box) { return box.width; },
            fromPointer: function (x, y, box) { return x - box.left; },
            range: function (workspace) {
                var rail = workspace.querySelector(".ws-rail");
                var room = workspace.clientWidth - (rail ? rail.offsetWidth : 0) - VIEW_MIN_W;
                return [PANEL_MIN_W, Math.max(PANEL_MIN_W, Math.min(PANEL_MAX_W, room))];
            },
            keys: {ArrowLeft: -1, ArrowRight: 1},
        },
        dock: {
            variable: "--dock-h",
            key: "dock_h",
            selector: ".ws-dock",
            cursor: "row-resize",
            current: function (box) { return box.height; },
            fromPointer: function (x, y, box) { return box.bottom - y; },
            range: function (workspace) {
                var room = workspace.clientHeight - VIEW_MIN_H;
                return [DOCK_MIN_H, Math.max(DOCK_MIN_H, room)];
            },
            keys: {ArrowUp: 1, ArrowDown: -1},
        },
    };

    var root = document.documentElement;
    var dragging = null;
    // A key held down saves once, a moment after it is let go; per splitter.
    var saveTimers = {};

    function sizeOf(splitter) {
        if (splitter.classList.contains("ws-splitter-panel")) {
            return SIZES.panel;
        }
        return splitter.classList.contains("ws-splitter-dock") ? SIZES.dock : null;
    }

    function workspace() {
        return document.querySelector(".workspace");
    }

    function box(size) {
        var element = document.querySelector(size.selector);
        return element ? element.getBoundingClientRect() : null;
    }

    function clamp(size, px) {
        var ws = workspace();
        if (!ws) {
            return Math.round(px);
        }
        var range = size.range(ws);
        return Math.round(Math.min(Math.max(px, range[0]), range[1]));
    }

    function apply(size, px) {
        root.style.setProperty(size.variable, clamp(size, px) + "px");
    }

    // Both sizes as set, each in pixels or null for one left to the
    // stylesheet; so two saves close together cannot undo one another.
    function save() {
        var data = {n: Date.now()};
        Object.keys(SIZES).forEach(function (name) {
            var px = parseFloat(root.style.getPropertyValue(SIZES[name].variable));
            data[SIZES[name].key] = isNaN(px) ? null : Math.round(px);
        });
        if (window.dash_clientside && window.dash_clientside.set_props) {
            window.dash_clientside.set_props(STORE_ID, {data: data});
        }
    }

    function saveSoon(size) {
        clearTimeout(saveTimers[size.key]);
        saveTimers[size.key] = setTimeout(save, 400);
    }

    function onPointerDown(event) {
        var splitter = event.target.closest && event.target.closest(".ws-splitter");
        var size = splitter && sizeOf(splitter);
        if (!size || !WIDE.matches || event.button !== 0) {
            return;
        }
        event.preventDefault();
        try {
            splitter.setPointerCapture(event.pointerId);
        } catch (error) {
            // Not a live pointer (a synthetic event): the document's
            // listeners still follow it.
        }
        dragging = {size: size, splitter: splitter, pointer: event.pointerId, moved: false};
        root.classList.add("is-resizing");
        root.style.setProperty("--resize-cursor", size.cursor);
    }

    function onPointerMove(event) {
        if (!dragging || event.pointerId !== dragging.pointer) {
            return;
        }
        var shown = box(dragging.size);
        if (shown) {
            dragging.moved = true;
            apply(dragging.size, dragging.size.fromPointer(event.clientX, event.clientY, shown));
        }
    }

    function onPointerUp(event) {
        if (!dragging || event.pointerId !== dragging.pointer) {
            return;
        }
        var moved = dragging.moved;
        dragging = null;
        root.classList.remove("is-resizing");
        root.style.removeProperty("--resize-cursor");
        // A click that did not drag -- as each of a double-click's is --
        // changes nothing, so saves nothing.
        if (moved) {
            save();
        }
    }

    function onDoubleClick(event) {
        var splitter = event.target.closest && event.target.closest(".ws-splitter");
        var size = splitter && sizeOf(splitter);
        if (!size) {
            return;
        }
        root.style.removeProperty(size.variable);
        save();
    }

    function onKeyDown(event) {
        var splitter = event.target.closest && event.target.closest(".ws-splitter");
        var size = splitter && sizeOf(splitter);
        var direction = size && size.keys[event.key];
        if (!direction || !WIDE.matches) {
            return;
        }
        event.preventDefault();
        var shown = box(size);
        if (shown) {
            var step = event.shiftKey ? KEY_STEP_BIG : KEY_STEP;
            apply(size, size.current(shown) + direction * step);
            saveSoon(size);
        }
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("pointermove", onPointerMove);
    document.addEventListener("pointerup", onPointerUp);
    document.addEventListener("pointercancel", onPointerUp);
    document.addEventListener("dblclick", onDoubleClick);
    document.addEventListener("keydown", onKeyDown);
})();
