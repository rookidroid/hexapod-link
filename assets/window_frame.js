// The frameless window's title bar and edges (make_window_buttons and
// make_window_edges in pages/shell.py). The window itself is moved, resized,
// maximized and closed by Python (window_controls.py), reached through
// pywebview as window.pywebview.api. Dragging the bar is taken over here
// (see below).
//
// Nothing here runs outside the frameless window: in a browser, or in a window
// with its own frame, <html> has no data-window="frameless" and the buttons and
// edges are not shown.
(() => {
    function frameless() {
        return document.documentElement.getAttribute("data-window") === "frameless";
    }

    function api() {
        return window.pywebview && window.pywebview.api;
    }

    // Called from Python as the window is maximized or restored, however
    // that came about (the button, a double-click, the keyboard).
    window.hexapodWindowMaximized = (maximized) => {
        document.documentElement.classList.toggle("is-maximized", !!maximized);
        var button = document.querySelector(".window-btn-maximize");
        if (button) {
            var title = maximized ? "Restore" : "Maximize";
            button.title = title;
            button.setAttribute("aria-label", title);
        }
    };

    window.addEventListener("pywebviewready", () => {
        var controls = api();
        if (frameless() && controls && controls.is_maximized) {
            controls.is_maximized().then(window.hexapodWindowMaximized);
        }
    });

    // ---- The buttons ----

    document.addEventListener("click", (event) => {
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
    document.addEventListener("dblclick", (event) => {
        var controls = api();
        if (controls && frameless() && event.target.classList.contains("pywebview-drag-region")) {
            controls.toggle_maximize();
        }
    });

    // ---- Dragging the bar ----
    //
    // pywebview's own drag only moves the window: Windows never sees a title
    // bar being dragged, so it neither snaps the window to the screen's edges
    // nor restores a maximized one. So the drag is taken over here.
    //
    // On Windows it is handed to Windows (begin_native_drag), which does all
    // a title bar's drag does. Elsewhere only a maximized window's is taken
    // over, which Python restores under the pointer (restore_for_drag) before
    // the rest of the drag moves it along, one move in flight at a time;
    // otherwise pywebview's own drag is left to it.
    //
    // Either way, only once the pointer has moved a few pixels with the
    // button down: a click or a double-click on the bar moves nothing.

    var DRAG_REGION = "pywebview-drag-region";
    var DRAG_THRESHOLD = 4;
    var nativeDrag = false;
    var bar = null;

    window.addEventListener("pywebviewready", () => {
        var controls = api();
        if (frameless() && controls && controls.native_drag) {
            controls.native_drag().then((native) => {
                nativeDrag = !!native;
            });
        }
    });

    function maximized() {
        return document.documentElement.classList.contains("is-maximized");
    }

    function sendMove() {
        if (!bar || bar.busy || !bar.grab || !bar.pending) {
            return;
        }
        var to = bar.pending;
        bar.pending = null;
        bar.busy = true;
        var current = bar;
        var done = () => {
            current.busy = false;
            sendMove();
        };
        api()
            .move_to(to.x - bar.grab[0], to.y - bar.grab[1])
            .then(done, done);
    }

    // Captured, and stopped, before pywebview's own drag hears of it.
    document.addEventListener(
        "mousedown",
        (event) => {
            var controls = api();
            if (
                !controls ||
                !frameless() ||
                event.button !== 0 ||
                !event.target.classList ||
                !event.target.classList.contains(DRAG_REGION)
            ) {
                return;
            }
            if (!nativeDrag && !(maximized() && controls.restore_for_drag)) {
                return;
            }
            event.stopPropagation();
            bar = {
                start: { x: event.screenX, y: event.screenY },
                client: { x: event.clientX, y: event.clientY },
                width: window.innerWidth,
                started: false,
                grab: null,
                busy: false,
                pending: null,
            };
        },
        true,
    );

    function startDrag(event) {
        bar.started = true;
        if (nativeDrag) {
            // Windows has it from here, to the button's release.
            api().begin_native_drag();
            bar = null;
            return;
        }
        bar.busy = true;
        var current = bar;
        var settle = (grab) => {
            current.grab = grab || null;
            current.busy = false;
            if (!current.grab && bar === current) {
                bar = null;
            }
            sendMove();
        };
        api()
            .restore_for_drag(event.screenX, event.screenY, bar.client.x, bar.client.y, bar.width)
            .then(settle, () => {
                settle(null);
            });
    }

    window.addEventListener("mousemove", (event) => {
        if (!bar) {
            return;
        }
        if ((event.buttons & 1) === 0) {
            bar = null;
            return;
        }
        if (!bar.started) {
            var dx = event.screenX - bar.start.x,
                dy = event.screenY - bar.start.y;
            if (Math.abs(dx) >= DRAG_THRESHOLD || Math.abs(dy) >= DRAG_THRESHOLD) {
                startDrag(event);
            }
            return;
        }
        bar.pending = { x: event.screenX, y: event.screenY };
        sendMove();
    });

    window.addEventListener("mouseup", () => {
        bar = null;
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
        var done = () => {
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

    document.addEventListener("pointerdown", (event) => {
        var edge = event.target.closest && event.target.closest(".window-edge");
        var controls = api();
        if (drag || !edge || !controls || !frameless() || event.button !== 0) {
            return;
        }
        event.preventDefault();
        edge.setPointerCapture(event.pointerId);
        drag = {
            edge: edge.getAttribute("data-edge"),
            started: { x: event.screenX, y: event.screenY },
            dx: 0,
            dy: 0,
            busy: true,
            pending: false,
            released: false,
        };
        var current = drag;
        var ready = () => {
            current.busy = false;
            sendResize();
        };
        controls.begin_resize().then(ready, ready);
    });

    document.addEventListener("pointermove", (event) => {
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
