import type { Scene } from "../../../shared/scene";
import type { ViewerColors } from "../../../shared/style";

export type Picked = null | number | "body" | { leg: number; joint: "coxia" | "femur" | "tibia" };

export interface HexapodView {
    /** Draw `scene` into the element with id `containerId`, in `colors` if
     * given rather than the scene's own. */
    render(
        containerId: string,
        scene: Scene,
        options?: { editable?: boolean; zoom?: boolean; colors?: ViewerColors },
    ): boolean;
    resetCamera(containerId: string): void;
    select(containerId: string, what: Picked): void;
    setBodyMode(containerId: string, mode: "translate" | "rotate"): void;
    on(id: "pose-selection", listener: (what: Picked) => void): () => void;
    on(
        id: "pose-foot-target",
        listener: (target: {
            leg: number;
            foot: [number, number, number];
            final: boolean;
            seq: number;
        }) => void,
    ): () => void;
    on(
        id: "pose-body-target",
        listener: (target: {
            origin: number[];
            rot: number[];
            final: boolean;
            seq: number;
        }) => void,
    ): () => void;
    on(
        id: "pose-joint-target",
        listener: (target: {
            leg: number;
            joint: string;
            angle: number;
            final: boolean;
            seq: number;
        }) => void,
    ): () => void;
}

export const hexapodView: HexapodView;
