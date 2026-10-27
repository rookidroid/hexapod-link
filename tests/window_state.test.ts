// Where the window opens: where it was left, if that is still on a screen.
// (Following it as it moves and maximizes is Electron's: the main process
// reads its normal bounds as it closes.)
import { describe, expect, it } from "vitest";
import type { SavedWindow } from "../src/main/storage";
import { fitWindow } from "../src/main/window_state";

const DEFAULT: [number, number] = [1440, 900];
const MIN: [number, number] = [1024, 700];
const PRIMARY = { x: 0, y: 0, width: 1920, height: 1080 };
const LEFT = { x: -2560, y: 0, width: 2560, height: 1440 };

const saved = (values: Partial<SavedWindow> = {}): SavedWindow => ({
    x: null,
    y: null,
    width: null,
    height: null,
    maximized: false,
    ...values,
});

describe("fitting the window to the screens", () => {
    it("opens centred at the default size", () => {
        expect(fitWindow(saved(), DEFAULT, MIN, [PRIMARY])).toEqual({
            x: null,
            y: null,
            width: 1440,
            height: 900,
        });
    });

    it("keeps a place on a screen, and drops one on a screen since gone", () => {
        const window = saved({ x: -2000, y: 100, width: 1600, height: 1000 });
        expect(fitWindow(window, DEFAULT, MIN, [PRIMARY, LEFT])).toEqual({
            x: -2000,
            y: 100,
            width: 1600,
            height: 1000,
        });
        expect(fitWindow(window, DEFAULT, MIN, [PRIMARY])).toEqual({
            x: null,
            y: null,
            width: 1600,
            height: 1000,
        });
        // Without the screens known, the place is kept as it is.
        expect(fitWindow(window, DEFAULT, MIN, [])).toEqual({
            x: -2000,
            y: 100,
            width: 1600,
            height: 1000,
        });
    });

    it("recentres a window whose top is off screen", () => {
        const fitted = fitWindow(
            saved({ x: 100, y: -200, width: 1600, height: 1000 }),
            DEFAULT,
            MIN,
            [PRIMARY],
        );
        expect([fitted.x, fitted.y]).toEqual([null, null]);
    });

    it("keeps the size within the screen and over the minimum", () => {
        expect(
            fitWindow(saved({ x: 0, y: 0, width: 3000, height: 2000 }), DEFAULT, MIN, [PRIMARY]),
        ).toEqual({
            x: 0,
            y: 0,
            width: 1920,
            height: 1080,
        });
        const small = fitWindow(saved({ width: 200, height: 200 }), DEFAULT, MIN, [PRIMARY]);
        expect([small.width, small.height]).toEqual(MIN);
    });
});
