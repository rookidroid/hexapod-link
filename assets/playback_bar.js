// How tall the playback bar over the view is (PLAYBACK_HUD in
// widgets/pose_ui.py), as --playback-h on the view's frame: the pose and the
// controller, opened, go up above it by that much (Playback in
// assets/industrial.css). It changes as the bar wraps onto a second line, or
// shows a message under its buttons.
(function () {
    "use strict";

    var observed = null;

    function watch() {
        var bar = document.querySelector(".playback-hud");
        if (!bar || bar === observed || !window.ResizeObserver) {
            return;
        }
        observed = bar;
        new ResizeObserver(function () {
            var frame = bar.closest(".hexapod-view-frame");
            if (frame) {
                frame.style.setProperty("--playback-h", bar.offsetHeight + "px");
            }
        }).observe(bar);
    }

    // The layout is drawn by Dash after the page loads.
    new MutationObserver(watch).observe(document.documentElement, {
        childList: true,
        subtree: true,
    });
    watch();
})();
