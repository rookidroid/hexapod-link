import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { useStore } from "./state/store";
import { hexapodView } from "./view/hexapodView";
import "./styles/vendor/bootstrap.min.css";
import "./styles/vendor/dash-widgets.css";
import "./styles/industrial.css";

// For the tools that drive the app (tools/make_screenshots.ts): the state and
// the view, to set them up as a person would have.
Object.assign(window, { hexapodApp: { store: useStore, view: hexapodView } });

createRoot(document.getElementById("root") as HTMLElement).render(
    <StrictMode>
        <App />
    </StrictMode>,
);
