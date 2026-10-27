// The bridge to the main process, put on `window` by src/preload/index.ts.
import type { HexapodApi } from "../../shared/api";

declare global {
    interface Window {
        hexapod: HexapodApi;
    }
}

export const api: HexapodApi = window.hexapod;
