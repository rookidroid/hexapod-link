// The 3D view's colours (view/hexapodView.ts). The view is the cockpit's
// panoramic monitor in both themes: a navy screen with the robot in RX-78-2
// colours and HUD-cyan overlays. scene.ts hands these to it with every scene.

export const BODY_MESH_COLOR = "#e8ecf2"; // White armour
export const BODY_COLOR = "#3b7bff"; // Federation blue body trim and joint rings
export const JOINT_COLOR = "#55627e"; // Inner-frame grey joint hubs
export const COG_COLOR = "#e63946"; // Red core block
export const HEAD_COLOR = "#f7c600"; // V-fin yellow head; also a picked-up foot
export const LEG_COLOR = "#dfe6ef"; // White armour legs
export const SUPPORT_POLYGON_MESH_COLOR = "#4cc9f0"; // HUD cyan support polygon and feet
export const PAPER_BG_COLOR = "#0a1428"; // Monitor navy background
export const GROUND_COLOR = "#13213f"; // Navy ground floor
export const GRID_COLOR = "#24406e"; // Grid lines on the floor
// Direction arrows on the body and at the origin.
export const AXIS_X_COLOR = "#e63946"; // Red
export const AXIS_Y_COLOR = "#f7c600"; // Yellow
export const AXIS_Z_COLOR = "#4cc9f0"; // Cyan

export const VIEWER_COLORS = {
    background: PAPER_BG_COLOR,
    ground: GROUND_COLOR,
    grid: GRID_COLOR,
    body: BODY_MESH_COLOR,
    bodyOutline: BODY_COLOR,
    leg: LEG_COLOR,
    joint: JOINT_COLOR,
    jointAccent: BODY_COLOR,
    foot: SUPPORT_POLYGON_MESH_COLOR,
    footSelected: HEAD_COLOR,
    head: HEAD_COLOR,
    cog: COG_COLOR,
    support: SUPPORT_POLYGON_MESH_COLOR,
    axisX: AXIS_X_COLOR,
    axisY: AXIS_Y_COLOR,
    axisZ: AXIS_Z_COLOR,
};
