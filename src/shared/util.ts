// Small numeric helpers shared by the kinematics.
//
// The kinematics were first written in Python, and the files they save (the
// keyframes, the preferences) and the tests carry its numbers. These helpers
// round and wrap the way Python does, so the numbers come out the same.

export type Vec3 = [number, number, number];
export type Mat3 = [Vec3, Vec3, Vec3];
/** Six feet (or six of anything with three numbers), leg order. */
export type Feet = Vec3[];

/**
 * Python's round(x, digits): to the nearest, and a tie -- only possible when
 * the binary value is exactly half way -- to the even neighbour. -0 becomes 0.
 */
export function pyRound(x: number, digits = 0): number {
    if (!Number.isFinite(x)) {
        return x;
    }
    const negative = x < 0;
    const abs = Math.abs(x);
    // toFixed(100) is the exact decimal expansion of the double, for the
    // magnitudes here; a tie is "...5" followed by nothing but zeros.
    if (abs < 1e21) {
        const exact = abs.toFixed(100);
        const point = exact.indexOf(".");
        const rest = exact.slice(point + 1 + digits);
        if (/^50*$/.test(rest)) {
            const kept = exact.slice(0, point + 1 + digits).replace(".", "");
            const last = Number(kept[kept.length - 1] ?? "0");
            let value = BigInt(kept || "0");
            if (last % 2 === 1) {
                value += 1n;
            }
            const result = Number(value) / 10 ** digits;
            return (negative ? -result : result) + 0;
        }
    }
    const result = Number(abs.toFixed(digits));
    return (negative ? -result : result) + 0;
}

/** Python's a % b for floats: the result takes the sign of b. */
export function pyMod(a: number, b: number): number {
    const r = a % b;
    return r !== 0 && r < 0 !== b < 0 ? r + b : r + 0;
}

export function clamp(value: number, low: number, high: number): number {
    return Math.min(Math.max(value, low), high);
}

export const radians = (deg: number) => (deg * Math.PI) / 180;
export const degrees = (rad: number) => (rad * 180) / Math.PI;

export function add(a: readonly number[], b: readonly number[]): Vec3 {
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
}

export function sub(a: readonly number[], b: readonly number[]): Vec3 {
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

export function scale(a: readonly number[], k: number): Vec3 {
    return [a[0] * k, a[1] * k, a[2] * k];
}

export function dot(a: readonly number[], b: readonly number[]): number {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

export function cross(a: readonly number[], b: readonly number[]): Vec3 {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

export function norm(a: readonly number[]): number {
    return Math.sqrt(a.reduce((sum, c) => sum + c * c, 0));
}

/** m @ v for a square matrix. */
export function matVec(m: readonly (readonly number[])[], v: readonly number[]): number[] {
    return m.map((row) => row.reduce((sum, c, i) => sum + c * v[i], 0));
}

/** a @ b. */
export function matMul(
    a: readonly (readonly number[])[],
    b: readonly (readonly number[])[],
): number[][] {
    const n = a.length;
    const m = b[0].length;
    const k = b.length;
    const out: number[][] = [];
    for (let i = 0; i < n; i++) {
        const row: number[] = [];
        for (let j = 0; j < m; j++) {
            let sum = 0;
            for (let x = 0; x < k; x++) {
                sum += a[i][x] * b[x][j];
            }
            row.push(sum);
        }
        out.push(row);
    }
    return out;
}

export function transpose(m: readonly (readonly number[])[]): number[][] {
    return m[0].map((_, j) => m.map((row) => row[j]));
}

/** The top-left 3x3 of a 4x4 frame. */
export function rotationOf(frame: readonly (readonly number[])[]): Mat3 {
    return [0, 1, 2].map((i) => [frame[i][0], frame[i][1], frame[i][2]]) as Mat3;
}

export function identity3(): Mat3 {
    return [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
    ];
}

/** A finite number, from what may not be one. */
export function isFiniteNumber(value: unknown): value is number {
    return typeof value === "number" && Number.isFinite(value);
}

/** Deep copy of plain JSON data. */
export function clone<T>(value: T): T {
    return structuredClone(value);
}

/** Deep equality of plain JSON data, -0 equal to 0. */
export function deepEqual(a: unknown, b: unknown): boolean {
    if (a === b) {
        return true;
    }
    if (typeof a !== typeof b || a === null || b === null || typeof a !== "object") {
        return false;
    }
    if (Array.isArray(a) !== Array.isArray(b)) {
        return false;
    }
    if (Array.isArray(a)) {
        const bb = b as unknown[];
        return a.length === bb.length && a.every((v, i) => deepEqual(v, bb[i]));
    }
    const ka = Object.keys(a as object);
    const kb = Object.keys(b as object);
    return (
        ka.length === kb.length &&
        ka.every((k) =>
            deepEqual((a as Record<string, unknown>)[k], (b as Record<string, unknown>)[k]),
        )
    );
}

/** Python-style "%.2f" of a value. */
export function fixed(value: number, digits: number): string {
    return pyRound(value, digits).toFixed(digits);
}
