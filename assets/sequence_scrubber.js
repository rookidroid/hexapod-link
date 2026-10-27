// The dock's frame scrubber (POSE_FRAME_SLIDER_ID in widgets/pose_ui.py).
//
// Grabbing it is asking to see the sequence, so it switches the view to it,
// as Play does; letting go makes the frame it was left on the pose, as
// pausing does (POSE_PLAYHEAD_ID, picked up by edit() in pages/pose.py).
// Done here rather than in a callback on the slider's value: the app moves
// the scrubber too -- back to the start whenever the keyframes change -- and
// that must neither take the view off the pose nor replace it.
(function () {
    "use strict";

    var SCRUBBER_ID = "pose-frame-slider";
    var MODE_STORE_ID = "pose-view-mode";
    var PLAYHEAD_STORE_ID = "pose-playhead";
    var MODE_PREVIEW = "preview";

    var grabbed = false;

    function onScrubber(event) {
        return event.target.closest && event.target.closest("#" + SCRUBBER_ID);
    }

    function setProps(id, props) {
        if (window.dash_clientside && window.dash_clientside.set_props) {
            window.dash_clientside.set_props(id, props);
        }
    }

    function frameShown() {
        var thumb = document.querySelector("#" + SCRUBBER_ID + " [role='slider']");
        var frame = thumb ? parseInt(thumb.getAttribute("aria-valuenow"), 10) : NaN;
        return isNaN(frame) ? null : frame;
    }

    function grab(event) {
        if (!onScrubber(event)) {
            return;
        }
        grabbed = true;
        setProps(MODE_STORE_ID, {data: MODE_PREVIEW});
    }

    function letGo() {
        if (!grabbed) {
            return;
        }
        grabbed = false;
        // After the slider has taken its last step.
        setTimeout(function () {
            var frame = frameShown();
            if (frame !== null) {
                setProps(PLAYHEAD_STORE_ID, {data: {frame: frame, n: Date.now()}});
            }
        }, 0);
    }

    document.addEventListener("pointerdown", grab, true);
    document.addEventListener("keydown", grab, true);
    document.addEventListener("pointerup", letGo, true);
    document.addEventListener("pointercancel", letGo, true);
    document.addEventListener("keyup", letGo, true);
})();
