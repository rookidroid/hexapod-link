// The app's model of a hexapod: a hexagonal body with a three-joint leg at
// each vertex, posed by its joint angles (forward kinematics).
//
// The body is never moved: every point is in the body frame, with the cog at
// the origin. Placing the body in the world, and solving the joints for where
// the feet should go, is pose_layers.ts and keyframes.ts.
//
// Dimensions f, s, and m
//
//       |-f-|
//       *---*---*--------
//      /    |    \     |
//     /     |     \    s
//    /      |      \   |
//   *------cog------* ---
//    \      |      /|
//     \     |     / |
//      \    |    /  |
//       *---*---*   |
//           |       |
//           |---m---|
//
// y forward, x right, cog at the origin.
import { Linkage } from "./linkage";
import { LEG_NAMES } from "./naming";
import { type Point, point } from "./points";
import type { Dimensions } from "./robot_config";
import { degrees, pyMod } from "./util";

export class Hexagon {
    readonly cog: Point;
    readonly head: Point;
    readonly vertices: Point[];
    readonly coxiaAxes: number[];

    constructor(
        readonly f: number,
        readonly m: number,
        readonly s: number,
        mountAngles?: number[] | null,
    ) {
        this.cog = point(0, 0, 0, "center-of-gravity");
        this.head = point(0, s, 0, "head");
        // In the firmware's leg order; see naming.ts
        this.vertices = [
            point(f, s, 0, LEG_NAMES[0]),
            point(m, 0, 0, LEG_NAMES[1]),
            point(f, -s, 0, LEG_NAMES[2]),
            point(-f, s, 0, LEG_NAMES[3]),
            point(-m, 0, 0, LEG_NAMES[4]),
            point(-f, -s, 0, LEG_NAMES[5]),
        ];
        // Azimuth of each leg's coxia (joint 1) rotation axis, in the body
        // frame. It has to match the robot's `legMountAngle`, the angle the
        // path generator solves IK around. A robot that reports its mount
        // angles passes them in (Nougat's corner legs are angled at 45 degrees
        // while sitting at about 59); without them a leg points radially away
        // from the cog, along its own vertex.
        this.coxiaAxes = mountAngles
            ? mountAngles.map((angle) => pyMod(angle, 360))
            : this.vertices.map((v) => pyMod(degrees(Math.atan2(v.y, v.x)), 360));
    }
}

export class VirtualHexapod {
    static readonly LEG_COUNT = 6;
    readonly body: Hexagon;
    readonly legs: Linkage[];

    constructor(readonly dimensions: Dimensions) {
        this.body = new Hexagon(
            dimensions.front,
            dimensions.middle,
            dimensions.side,
            dimensions.mount_angles,
        );
        this.legs = LEG_NAMES.map(
            (name, i) =>
                new Linkage(
                    dimensions.coxia,
                    dimensions.femur,
                    dimensions.tibia,
                    this.body.coxiaAxes[i],
                    this.body.vertices[i],
                    name,
                    i,
                ),
        );
    }

    sumOfDimensions(): number {
        const d = this.dimensions;
        return d.front + d.middle + d.side + d.coxia + d.femur + d.tibia;
    }
}
