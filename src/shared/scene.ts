// What the 3D view draws, as plain data.
//
// The hexapod is drawn by a three.js view (renderer/src/view/hexapodView.ts).
// This module turns a posed VirtualHexapod into the lists that view takes:
//
//   body      6 vertices, leg order (naming.ts)
//   head      the point marking the front
//   cog       centre of the body
//   legs      per leg: body contact, coxia, femur and foot tip points
//   feet      the six foot tips
//   support   the feet standing on the ground, in order around the polygon
//   axes      the body's own axes: [{from, to, axis: "x"|"y"|"z"}]
//   ground    height of the floor
//   size      the robot's overall measure, which the camera is framed by
//   labels    each leg's name as the firmware gives it, shown on hover
//   colors    style.ts, so the view needs no colours of its own
//
// pose_layers.ts adds the body's frame and each joint's ring, for the view's
// handles.

import type { VirtualHexapod } from "./models";
import { LEG_LABELS } from "./naming";
import type { Point } from "./points";
import { VIEWER_COLORS } from "./style";
import { matVec, pyRound, type Vec3 } from "./util";

export interface SceneAxis {
    from: Vec3;
    to: Vec3;
    axis: "x" | "y" | "z";
}

export interface SceneJoint {
    axis: Vec3 | null;
    angle: number;
    most: number;
}

export interface Scene {
    body: Vec3[];
    head: Vec3;
    cog: Vec3;
    legs: Vec3[][];
    feet: Vec3[];
    support: Vec3[];
    axes: SceneAxis[];
    ground: number;
    size: number;
    labels: string[];
    colors: typeof VIEWER_COLORS;
    frame?: { origin: Vec3; rot: Vec3 };
    joints?: SceneJoint[][];
    seq?: number;
}

/** [x, y, z] to a thousandth. */
export function xyz(p: Point): Vec3 {
    return [pyRound(p.x, 3), pyRound(p.y, 3), pyRound(p.z, 3)];
}

/** Points sorted by angle about their centroid: enough to draw a hexapod's
 * support polygon, whose at most six feet sit on a convex ring. */
export function orderAroundCentre<T extends readonly number[]>(points: readonly T[]): T[] {
    if (!points.length) {
        return [];
    }
    const cx = points.reduce((s, p) => s + p[0], 0) / points.length;
    const cy = points.reduce((s, p) => s + p[1], 0) / points.length;
    const keyed = points.map((p) => ({ p, key: Math.atan2(p[1] - cy, p[0] - cx) }));
    keyed.sort((a, b) => a.key - b.key);
    return keyed.map((k) => k.p);
}

/** The scene for a posed hexapod, in its body frame. `support` is the points
 * the support polygon is drawn through, flat at `ground`. */
export function hexapodToScene(
    hexapod: VirtualHexapod,
    ground: number,
    support: readonly Vec3[],
): Scene {
    const legs = hexapod.legs.map((leg) => leg.allPoints.map(xyz));
    const cog = xyz(hexapod.body.cog);
    // The body's own axes from its centre, half the body's front length long.
    const length = hexapod.dimensions.front / 2;
    const axes = (["x", "y", "z"] as const).map((axis, i) => {
        const tip = [...cog] as Vec3;
        tip[i] = pyRound(tip[i] + length, 3);
        return { from: cog, to: tip, axis };
    });
    return {
        body: hexapod.body.vertices.map(xyz),
        head: xyz(hexapod.body.head),
        cog,
        legs,
        feet: legs.map((leg) => leg[3]),
        support: orderAroundCentre(support).map((p) => [p[0], p[1], ground + 0] as Vec3),
        axes,
        ground: ground + 0,
        size: pyRound(hexapod.sumOfDimensions(), 3),
        labels: [...LEG_LABELS],
        colors: VIEWER_COLORS,
    };
}

/** The same scene moved rigidly: every point p goes to rotation @ p + shift.
 * The floor height is only moved, not tilted. */
export function transformScene(
    scene: Scene,
    rotation: readonly (readonly number[])[],
    shift: readonly number[],
): Scene {
    const move = (p: readonly number[]): Vec3 => {
        const r = matVec(rotation, p);
        return [pyRound(r[0] + shift[0], 3), pyRound(r[1] + shift[1], 3), pyRound(r[2] + shift[2], 3)];
    };
    return {
        ...scene,
        body: scene.body.map(move),
        head: move(scene.head),
        cog: move(scene.cog),
        legs: scene.legs.map((leg) => leg.map(move)),
        feet: scene.feet.map(move),
        support: scene.support.map(move),
        axes: scene.axes.map((axis) => ({ ...axis, from: move(axis.from), to: move(axis.to) })),
        ground: pyRound(scene.ground + shift[2], 3),
    };
}
