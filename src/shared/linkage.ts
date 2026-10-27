// -------------
// LINKAGE
// -------------
// Neutral position of the linkages (alpha=0, beta=0, gamma=0)
// note that at neutral position:
//  link b and link c are perpendicular to each other
//  link a and link b form a straight line
//  link a and the leg x axis are aligned
//
// alpha - the angle linkage a makes with x_axis about z axis
// beta - the angle that linkage a makes with linkage b
// gamma - the angle that linkage c make with the line perpendicular to linkage b
//
//  |--- a--------|--b--|
//  |=============|=====| p2 -------
//  p0            p1    |          |
//                      |          c
//                      |          |
//                      | p3  ------
//
// p0 - body contact
// p1 - coxia point
// p2 - femur point
// p3 - foot tip

import {
    frameYrotateXtranslate,
    frameZrotateXytranslate,
    type Point,
    point,
    pointWrt,
} from "./points";
import { matMul } from "./util";

export class Linkage {
    alpha = 0;
    beta = 0;
    gamma = 0;
    allPoints: Point[] = [];

    constructor(
        readonly a: number,
        readonly b: number,
        readonly c: number,
        readonly coxiaAxis = 0,
        readonly newOrigin: Point = point(0, 0, 0),
        readonly name = "",
        readonly id = 0,
        alpha = 0,
        beta = 0,
        gamma = 0,
    ) {
        this.changePose(alpha, beta, gamma);
    }

    footTip(): Point {
        return this.allPoints[3];
    }

    changePose(alpha: number, beta: number, gamma: number): void {
        this.alpha = alpha;
        this.beta = beta;
        this.gamma = gamma;

        // frame_ab is the pose of frame_b wrt frame_a
        const frame01 = frameYrotateXtranslate(-beta, this.a);
        const frame12 = frameYrotateXtranslate(90 - gamma, this.b);
        const frame23 = frameYrotateXtranslate(0, this.c);
        const frame02 = matMul(frame01, frame12);
        const frame03 = matMul(frame02, frame23);
        const newFrame = frameZrotateXytranslate(
            this.coxiaAxis + alpha,
            this.newOrigin.x,
            this.newOrigin.y,
        );

        // points wrt the body contact point, then wrt the centre of gravity
        const p0 = point(0, 0, 0);
        const p1 = pointWrt(p0, frame01);
        const p2 = pointWrt(p0, frame02);
        const p3 = pointWrt(p0, frame03);

        this.allPoints = [
            { ...this.newOrigin, name: `${this.newOrigin.name}-body-contact` },
            pointWrt(p1, newFrame, `${this.name}-coxia`),
            pointWrt(p2, newFrame, `${this.name}-femur`),
            pointWrt(p3, newFrame, `${this.name}-tibia`),
        ];
    }
}
