// The workspace's splitters: one on the dock's top edge sets its height, and
// one between the dock's columns the width of the Gaits library, the sequence
// taking what is left. Drag one, or focus it and use the arrow keys (Shift for
// bigger steps); double-click it to put the size back to the stylesheet's.
//
// A size is a CSS variable on <html> (WORKSPACE in styles/industrial.css),
// where the preload script puts the saved ones before the page is drawn. One
// let go of is kept with the preferences. A drag is held to the window, so
// the view always keeps some room. Only above `lg`: below it everything
// stacks and the splitters are hidden.

import { useRef } from "react";
import { api } from "../api";

// How much of the window's height the view always keeps (px; --view-min-h in
// the stylesheet), and the shortest the dock may be made.
const VIEW_MIN_H = 180;
const DOCK_MIN_H = 140;
// The library's least width, its most as a share of the dock, and what the
// sequence always keeps.
const LIB_MIN_W = 180;
const LIB_MAX_SHARE = 0.35;
const SEQUENCE_MIN_W = 320;
const KEY_STEP = 16;
const KEY_STEP_BIG = 64;

interface Size {
    variable: string;
    key: "dock_h" | "lib_w";
    selector: string;
    cursor: string;
    label: string;
    orientation: "horizontal" | "vertical";
    current(box: DOMRect): number;
    fromPointer(x: number, y: number, box: DOMRect): number;
    range(): [number, number];
    keys: Record<string, number>;
}

const SIZES: Record<"dock" | "lib", Size> = {
    dock: {
        variable: "--dock-h",
        key: "dock_h",
        selector: ".ws-dock",
        cursor: "row-resize",
        label: "resize the dock",
        orientation: "horizontal",
        current: (box) => box.height,
        fromPointer: (_x, y, box) => box.bottom - y,
        range: () => {
            const room = (document.querySelector(".workspace")?.clientHeight ?? 0) - VIEW_MIN_H;
            return [DOCK_MIN_H, Math.max(DOCK_MIN_H, room)];
        },
        keys: { ArrowUp: 1, ArrowDown: -1 },
    },
    lib: {
        variable: "--lib-w",
        key: "lib_w",
        selector: ".dock-col-library",
        cursor: "col-resize",
        label: "resize the Gaits library",
        orientation: "vertical",
        current: (box) => box.width,
        fromPointer: (x, _y, box) => x - box.left,
        range: () => {
            const width = document.querySelector(".dock")?.clientWidth ?? 0;
            const room = width - SEQUENCE_MIN_W;
            return [LIB_MIN_W, Math.max(LIB_MIN_W, Math.min(width * LIB_MAX_SHARE, room))];
        },
        keys: { ArrowLeft: -1, ArrowRight: 1 },
    },
};

const wide = () => window.matchMedia("(min-width: 992px)").matches;
const root = () => document.documentElement;

function apply(size: Size, px: number): void {
    const [low, high] = size.range();
    root().style.setProperty(size.variable, `${Math.round(Math.min(Math.max(px, low), high))}px`);
}

/** Keep every size as set, each in pixels or null for one left to the
 * stylesheet. */
function save(): void {
    const sizes: Record<string, number | null> = {};
    for (const size of Object.values(SIZES)) {
        const px = Number.parseFloat(root().style.getPropertyValue(size.variable));
        sizes[size.key] = Number.isNaN(px) ? null : Math.round(px);
    }
    api.saveLayout(sizes);
}

const box = (size: Size) => document.querySelector(size.selector)?.getBoundingClientRect() ?? null;

export function Splitter({ kind }: { kind: "dock" | "lib" }) {
    const size = SIZES[kind];
    const dragging = useRef<{ pointer: number; moved: boolean } | null>(null);
    const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const label = size.label[0].toUpperCase() + size.label.slice(1);
    return (
        <div
            className={`ws-splitter ws-splitter-${kind}`}
            role="separator"
            tabIndex={0}
            title={`Drag to ${size.label}; double-click to reset`}
            aria-orientation={size.orientation}
            aria-label={label}
            onPointerDown={(e) => {
                if (!wide() || e.button !== 0) return;
                e.preventDefault();
                e.currentTarget.setPointerCapture(e.pointerId);
                dragging.current = { pointer: e.pointerId, moved: false };
                root().classList.add("is-resizing");
                root().style.setProperty("--resize-cursor", size.cursor);
            }}
            onPointerMove={(e) => {
                const d = dragging.current;
                const shown = box(size);
                if (!d || e.pointerId !== d.pointer || !shown) return;
                d.moved = true;
                apply(size, size.fromPointer(e.clientX, e.clientY, shown));
            }}
            onPointerUp={(e) => {
                const d = dragging.current;
                if (!d || e.pointerId !== d.pointer) return;
                dragging.current = null;
                root().classList.remove("is-resizing");
                root().style.removeProperty("--resize-cursor");
                // A click that did not drag -- as each of a double-click's
                // is -- changes nothing, so saves nothing.
                if (d.moved) save();
            }}
            onDoubleClick={() => {
                root().style.removeProperty(size.variable);
                save();
            }}
            onKeyDown={(e) => {
                const direction = size.keys[e.key];
                const shown = box(size);
                if (!direction || !wide() || !shown) return;
                e.preventDefault();
                apply(
                    size,
                    size.current(shown) + direction * (e.shiftKey ? KEY_STEP_BIG : KEY_STEP),
                );
                // A key held down saves once, a moment after it is let go.
                if (saveTimer.current) clearTimeout(saveTimer.current);
                saveTimer.current = setTimeout(save, 400);
            }}
        />
    );
}
