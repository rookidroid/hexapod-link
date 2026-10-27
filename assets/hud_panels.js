// The overlays on the view that fold away -- the pose, the dimensions
// and the controller -- each a native <details> named by its data-panel
// attribute (PANELS in pages/workspace.py). The page is served with each as
// it was left; one folded or opened by hand here goes to the panels store, to
// be kept with the preferences (keep_panel_states in pages/shell.py).
//
// Only a click on its title counts. The pose also opens by itself
// as the body or a foot is picked or dragged (pages/pose.py); that is not
// kept, so it starts folded again the next time.
(function () {
    "use strict";

    var STORE_ID = "panel-states";
    var ATTRIBUTE = "data-panel";

    document.addEventListener("click", function (event) {
        var summary = event.target.closest && event.target.closest("summary");
        var panel = summary && summary.parentElement;
        var key = panel && panel.getAttribute(ATTRIBUTE);
        if (!key) {
            return;
        }
        // The click folds or opens it only once its handlers are through.
        window.setTimeout(function () {
            var data = {n: Date.now()};
            data[key] = panel.open;
            if (window.dash_clientside && window.dash_clientside.set_props) {
                window.dash_clientside.set_props(STORE_ID, {data: data});
            }
        }, 0);
    });
})();
