// Points, and the homogeneous (4x4) frames that move them.
import { matMul, matVec, radians } from "./util";

export type Frame = number[][];

export interface Point {
    x: number;
    y: number;
    z: number;
    name?: string;
}

export function point(x: number, y: number, z: number, name?: string): Point {
    return { x, y, z, name };
}

/** Given frame_ab, the pose of frame b in frame a, and a point in frame b:
 * the point in frame a. */
export function pointWrt(p: Point, frame: Frame, name?: string): Point {
    const [x, y, z] = matVec(frame, [p.x, p.y, p.z, 1]);
    return { x, y, z, name };
}

function cosAndSin(theta: number): [number, number] {
    const d = radians(theta);
    return [Math.cos(d), Math.sin(d)];
}

/** Rotate about y, translate in x. */
export function frameYrotateXtranslate(theta: number, x: number): Frame {
    const [c, s] = cosAndSin(theta);
    return [
        [c, 0, s, x],
        [0, 1, 0, 0],
        [-s, 0, c, 0],
        [0, 0, 0, 1],
    ];
}

/** Rotate about z, translate in x and y. */
export function frameZrotateXytranslate(theta: number, x: number, y: number): Frame {
    const [c, s] = cosAndSin(theta);
    return [
        [c, -s, 0, x],
        [s, c, 0, y],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ];
}

export function rotx(theta: number): Frame {
    const [c, s] = cosAndSin(theta);
    return [
        [1, 0, 0, 0],
        [0, c, -s, 0],
        [0, s, c, 0],
        [0, 0, 0, 1],
    ];
}

export function roty(theta: number): Frame {
    const [c, s] = cosAndSin(theta);
    return [
        [c, 0, s, 0],
        [0, 1, 0, 0],
        [-s, 0, c, 0],
        [0, 0, 0, 1],
    ];
}

export function rotz(theta: number): Frame {
    const [c, s] = cosAndSin(theta);
    return [
        [c, -s, 0, 0],
        [s, c, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ];
}

/** Rotations about x, y and z, in degrees, applied as Rx @ Ry @ Rz. */
export function frameRotxyz(a: number, b: number, c: number): Frame {
    return matMul(matMul(rotx(a), roty(b)), rotz(c));
}
