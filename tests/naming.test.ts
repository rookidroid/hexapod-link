// The naming module is the app's only claim about the firmware's numbering.
// The tables *are* the contract: right legs first, joints numbered outward
// from the body, because every caption, view label and alert is built from it.
import { describe, expect, it } from "vitest";
import {
    JOINT_NAMES,
    jointLabel,
    jointNumber,
    LEG_LABELS,
    LEG_NAMES,
    legIndex,
    legLabel,
    shortLegName,
} from "../src/shared/naming";

describe("naming", () => {
    it("lines the two leg tables up", () => {
        expect(LEG_NAMES.length).toBe(6);
        expect(LEG_LABELS.length).toBe(6);
        expect(new Set(LEG_NAMES).size).toBe(6);
        expect(new Set(LEG_LABELS).size).toBe(6);
    });

    it("puts the right legs first, front to back", () => {
        for (let id = 0; id < 3; id++) {
            expect(LEG_NAMES[id].startsWith("right-")).toBe(true);
            expect(LEG_LABELS[id]).toBe(`Right Leg ${id + 1}`);
        }
        for (let id = 3; id < 6; id++) {
            expect(LEG_NAMES[id].startsWith("left-")).toBe(true);
            expect(LEG_LABELS[id]).toBe(`Left Leg ${id - 2}`);
        }
    });

    it("resolves a leg by name or id", () => {
        LEG_NAMES.forEach((name, id) => {
            expect(legIndex(name)).toBe(id);
            expect(legIndex(id)).toBe(id);
            expect(legLabel(name)).toBe(LEG_LABELS[id]);
            expect(legLabel(id)).toBe(LEG_LABELS[id]);
        });
        expect(shortLegName("left-back")).toBe("L3");
    });

    it("refuses an unknown leg or joint", () => {
        expect(() => legIndex("right-centre" as never)).toThrow();
        expect(() => jointNumber("knee" as never)).toThrow();
    });

    it("numbers joints outward from the body", () => {
        expect(JOINT_NAMES).toEqual(["coxia", "femur", "tibia"]);
        JOINT_NAMES.forEach((name, i) => {
            expect(jointNumber(name)).toBe(i + 1);
        });
        expect(jointLabel("coxia")).toBe("Joint 1 (coxia)");
        expect(jointLabel("tibia")).toBe("Joint 3 (tibia)");
    });
});
