// The frameless window's title bar and edges (make_window_buttons and
// make_window_edges in pages/shell.py). The window itself is moved, resized,
// maximized and closed by Python (window_controls.py), reached through
// pywebview as window.pywebview.api. Dragging the bar is pywebview's own.
//
// Nothing here runs outside the frameless window: in a browser, or in a window
// with its own frame, <html> has no data-window="frameless" and the buttons and
// edges are not shown.
(function () {
    "use strict";

    function frameless() {
        return document.documentElement.getAttribute("data-window") === "frameless";
    }

    function api() {
        return window.pywebview && window.pywebview.api;
    }

    // Called from Python as the window is maximized or restored, however
    // that came about (the button, a double-click, the keyboard).
    window.hexapodWindowMaximized = function (maximized) {
        document.documentElement.classList.toggle("is-maximized", !!maximized);
        var button = document.querySelector(".window-btn-maximize");
        if (button) {
            var title = maximized ? "Restore" : "Maximize";
            button.title = title;
            button.setAttribute("aria-label", title);
        }
    };

    window.addEventListener("pywebviewready", function () {
        var controls = api();
        if (frameless() && controls && controls.is_maximized) {
            controls.is_maximized().then(window.hexapodWindowMaximized);
        }
    });

    // ---- The buttons ----

    document.addEventListener("click", function (event) {
        var button = event.target.closest && event.target.closest("[data-window-action]");
        var controls = api();
        if (!button || !controls || !frameless()) {
            return;
        }
        var action = button.getAttribute("data-window-action");
        if (action === "minimize") {
            controls.minimize();
        } else if (action === "maximize") {
            controls.toggle_maximize();
        } else if (action === "close") {
            controls.close();
        }
    });

    // Double-clicking the bar itself, not something on it, maximizes or
    // restores, as a native title bar does.
    document.addEventListener("dblclick", function (event) {
        var controls = api();
        if (controls && frameless() && event.target.classList.contains("pywebview-drag-region")) {
            controls.toggle_maximize();
        }
    });

    // ---- Resizing from an edge ----
    //
    // One resize in flight at a time: moves that come in while Python is busy
    // with the last one are folded into the next.

    var drag = null;

    function sendResize() {
        if (!drag || drag.busy) {
            return;
        }
        if (!drag.pending) {
            if (drag.released) {
                drag = null;
            }
            return;
        }
        drag.busy = true;
        drag.pending = false;
        var done = function () {
            drag.busy = false;
            sendResize();
        };
        api().resize_by(drag.edge, drag.dx, drag.dy).then(done, done);
    }

    function follow(event) {
        drag.dx = event.screenX - drag.started.x;
        drag.dy = event.screenY - drag.started.y;
        drag.pending = true;
        sendResize();
    }

    document.addEventListener("pointerdown", function (event) {
        var edge = event.target.closest && event.target.closest(".window-edge");
        var controls = api();
        if (drag || !edge || !controls || !frameless() || event.button !== 0) {
            return;
        }
        event.preventDefault();
        edge.setPointerCapture(event.pointerId);
        drag = {
            edge: edge.getAttribute("data-edge"),
            started: {x: event.screenX, y: event.screenY},
            dx: 0,
            dy: 0,
            busy: true,
            pending: false,
            released: false,
        };
        var current = drag;
        var ready = function () {
            current.busy = false;
            sendResize();
        };
        controls.begin_resize().then(ready, ready);
    });

    document.addEventListener("pointermove", function (event) {
        if (drag && !drag.released) {
            follow(event);
        }
    });

    // The last move goes out once the one before it is through.
    function release(event) {
        if (drag && !drag.released) {
            drag.released = true;
            follow(event);
        }
    }

    document.addEventListener("pointerup", release);
    document.addEventListener("pointercancel", release);
})();
