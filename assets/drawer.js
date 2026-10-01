// Close the global ROBOT drawer when the user clicks anywhere outside it, or
// presses Escape.
//
// Dash loads every .js file in assets/ on its own. The drawer's className is a
// Dash prop that toggle_global_panel() in pages/shared.py reads back as State,
// so it is changed through set_props rather than on the DOM directly: editing
// the class behind Dash's back would leave that State saying "open" and the
// next click on the navbar handle would do nothing.

(function () {
    var PANEL_ID = "global-controls-panel";
    var CLOSED_CLASS = "global-drawer";
    var OPEN_CLASS = "global-drawer-open";

    // Buttons that already open or toggle the drawer through their own
    // callbacks. A click on one of them is left to that callback; closing here
    // as well would race it and the drawer would flicker or stay shut.
    var OPENER_SELECTOR = "#global-controls-toggle, #landing-open-robot-panel";

    function closePanel() {
        var panel = document.getElementById(PANEL_ID);
        if (!panel || !panel.classList.contains(OPEN_CLASS)) {
            return;
        }
        if (window.dash_clientside && window.dash_clientside.set_props) {
            window.dash_clientside.set_props(PANEL_ID, { className: CLOSED_CLASS });
        }
    }

    document.addEventListener(
        "pointerdown",
        function (event) {
            var panel = document.getElementById(PANEL_ID);
            if (!panel || panel.contains(event.target)) {
                return;
            }
            if (event.target.closest && event.target.closest(OPENER_SELECTOR)) {
                return;
            }
            closePanel();
        },
        true
    );

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closePanel();
        }
    });
})();
