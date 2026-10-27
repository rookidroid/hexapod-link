// Leg and joint identity, following the ESP32 firmware's convention.
//
// The physical robot (the `hexapod` repo) numbers legs per side, front to back,
// and numbers joints outward from the body:
//
//   leg index    0             1              2             3            4             5
//   firmware     Right Leg 1   Right Leg 2    Right Leg 3   Left Leg 1   Left Leg 2    Left Leg 3
//   simulator    right-front   right-middle   right-back    left-front   left-middle   left-back
//
//   joint index  1             2              3
//   firmware     Joint 1       Joint 2        Joint 3
//   simulator    coxia         femur          tibia
//   angle        alpha         beta           gamma   (linkage.ts)
//
// The index order is already the same in both projects, so nothing here
// reorders anything. Internal identifiers stay descriptive; everything a person
// reads is built from the label tables below, so the app and the robot's
// calibration page name the same servo the same way.

export const LEG_NAMES = [
    "right-front",
    "right-middle",
    "right-back",
    "left-front",
    "left-middle",
    "left-back",
] as const;

export const LEG_LABELS = [
    "Right Leg 1",
    "Right Leg 2",
    "Right Leg 3",
    "Left Leg 1",
    "Left Leg 2",
    "Left Leg 3",
] as const;

/** Anatomical names, ordered from the body outward: index i is "Joint i + 1". */
export const JOINT_NAMES = ["coxia", "femur", "tibia"] as const;

export type LegName = (typeof LEG_NAMES)[number];
export type JointName = (typeof JOINT_NAMES)[number];

export function legIndex(leg: LegName | number): number {
    if (typeof leg === "string") {
        const index = LEG_NAMES.indexOf(leg);
        if (index < 0) {
            throw new Error(`unknown leg: ${leg}`);
        }
        return index;
    }
    return Math.trunc(leg);
}

/** The firmware's name for a leg, given its id or its simulator name. */
export function legLabel(leg: LegName | number): string {
    return LEG_LABELS[legIndex(leg)];
}

/** The firmware's joint number (1-3) for an anatomical name. */
export function jointNumber(joint: JointName): number {
    const index = JOINT_NAMES.indexOf(joint);
    if (index < 0) {
        throw new Error(`unknown joint: ${joint}`);
    }
    return index + 1;
}

/** The firmware's joint number, with its name: "Joint 1 (coxia)". */
export function jointLabel(joint: JointName): string {
    return `Joint ${jointNumber(joint)} (${joint})`;
}

/** "Right Leg 1" -> "R1", for where there is no room for the name. */
export function shortLegName(leg: LegName | number): string {
    const [side, , number] = legLabel(leg).split(" ");
    return `${side[0]}${number}`;
}
