import react from "@vitejs/plugin-react";
import { defineConfig } from "electron-vite";

// Three bundles: the main process (Node: the window, the robot link, files on
// disk), the preload script (the bridge between the two), and the renderer
// (the page: React, the 3D view and all the kinematics).
export default defineConfig({
    main: {
        build: { outDir: "out/main" },
    },
    preload: {
        build: {
            outDir: "out/preload",
            rollupOptions: { output: { format: "cjs", entryFileNames: "[name].cjs" } },
        },
    },
    renderer: {
        root: "src/renderer",
        build: { outDir: "out/renderer" },
        plugins: [react()],
    },
});
