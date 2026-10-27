// One screen: the top bar, then the workspace -- the 3D view with everything
// laid over it, and the dock along the bottom. The grid is laid out in the
// WORKSPACE block of styles/industrial.css, which also decides who scrolls:
// above `lg` the dock does, and the view takes whatever room is left; below it
// the two stack and the page scrolls as a whole.

import { useEffect } from "react";
import { Dock } from "./components/Dock";
import { Splitter } from "./components/Splitter";
import { TopBar } from "./components/TopBar";
import { View } from "./components/View";
import { followPose, keepWorkspace, useStore } from "./state/store";

// Every readout of the link's state runs off this one poll: often enough that
// the status pill feels live.
const STATUS_POLL_MS = 1000;

export function App() {
    useEffect(() => {
        const stopFollowing = followPose();
        const stopKeeping = keepWorkspace();
        const poll = setInterval(() => void useStore.getState().pollStatus(), STATUS_POLL_MS);
        return () => {
            stopFollowing();
            stopKeeping();
            clearInterval(poll);
        };
    }, []);
    return (
        <div className="app-shell">
            <TopBar />
            <main className="workspace">
                <div className="ws-view">
                    <View />
                </div>
                <div className="ws-dock">
                    <Dock />
                </div>
                <Splitter kind="dock" />
            </main>
        </div>
    );
}
