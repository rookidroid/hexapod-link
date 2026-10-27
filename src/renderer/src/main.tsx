import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles/vendor/bootstrap.min.css";
import "./styles/vendor/dash-widgets.css";
import "./styles/industrial.css";

createRoot(document.getElementById("root") as HTMLElement).render(
    <StrictMode>
        <App />
    </StrictMode>,
);
