// The 3D view's colours (view/hexapodView.ts), one set per theme. Dark is
// the cockpit's panoramic monitor: a navy screen with the robot in RX-78-2
// colours and HUD-cyan overlays. Light is the hangar: the same robot on a
// pale panel-grey floor, its trim and markings darkened to read on it.
// scene.ts hands the dark set to the view with every scene; the view swaps in
// the theme's set (components/View.tsx).

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

export type ViewerColors = typeof VIEWER_COLORS;

/** The light theme's view: --view-bg in the stylesheet is its background. */
export const LIGHT_VIEWER_COLORS: ViewerColors = {
    background: "#e6ebf3", // Panel-line grey
    ground: "#d2dae6",
    grid: "#a3b1c8",
    body: "#f4f6fa",
    bodyOutline: "#1d4fa3", // Federation blue
    leg: "#e9edf3",
    joint: "#55627e",
    jointAccent: "#1d4fa3",
    foot: "#1a8fc0", // A deeper cyan, to read on the pale floor
    footSelected: "#f2b705",
    head: "#f2b705",
    cog: "#d62828",
    support: "#1a8fc0",
    axisX: "#d62828",
    axisY: "#e0a800",
    axisZ: "#1a8fc0",
};

export const VIEWER_THEMES = { dark: VIEWER_COLORS, light: LIGHT_VIEWER_COLORS };
