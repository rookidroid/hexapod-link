// The window's size and place, kept between launches.
//
// Saved as the window closes (storage.ts) and put back as it next opens: the
// size and place it had out of maximized, so a window left maximized still
// restores to where it was, and whether it was maximized. A place that no
// screen shows any more, say a monitor since unplugged, is dropped, and the
// window opens centred instead.

import type { SavedWindow } from "./storage";

export interface Area {
    x: number;
    y: number;
    width: number;
    height: number;
}

// How much of the window's top must be on a screen for the saved place to be
// kept: enough of the top bar to grab and drag it.
const GRAB_STRIP_H = 40;
const GRAB_MIN_W = 120;
const GRAB_MIN_H = 20;

function overlap(aStart: number, aLength: number, bStart: number, bLength: number): number {
    return Math.max(0, Math.min(aStart + aLength, bStart + bLength) - Math.max(aStart, bStart));
}

/** The screen showing enough of a window's top at (x, y) to grab it, or null. */
export function screenHolding(x: number, y: number, width: number, screens: Area[]): Area | null {
    return (
        screens.find(
            (s) =>
                overlap(x, width, s.x, s.width) >= GRAB_MIN_W &&
                overlap(y, GRAB_STRIP_H, s.y, s.height) >= GRAB_MIN_H,
        ) ?? null
    );
}

/** Where and how big to open the window: x and y null to centre it. The size
 * is kept within the screen the window opens on, and not under minSize.
 * Without screens the saved place is kept as it is. */
export function fitWindow(
    saved: SavedWindow,
    defaultSize: [number, number],
    minSize: [number, number],
    screens: Area[],
): { x: number | null; y: number | null; width: number; height: number } {
    let width = saved.width || defaultSize[0];
    let height = saved.height || defaultSize[1];
    let { x, y } = saved;
    if (screens.length) {
        let screen: Area | null = null;
        if (x !== null && y !== null) {
            screen = screenHolding(x, y, width, screens);
            if (screen === null) {
                x = y = null;
            }
        }
        screen = screen ?? screens[0];
        width = Math.min(width, screen.width);
        height = Math.min(height, screen.height);
    }
    return { x, y, width: Math.max(width, minSize[0]), height: Math.max(height, minSize[1]) };
}
