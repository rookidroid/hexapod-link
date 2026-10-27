// The robot's gaits by the app's name for each: what the Gaits library offers
// to put into a sequence (gait_keyframes.ts), and what the controller over the
// view has the robot play from its own flash.

export const MOTION_TYPES = [
    { label: "Standby (reset)", value: "standby" },
    { label: "Walk forward", value: "walk_0" },
    { label: "Walk backward", value: "walk_180" },
    { label: "Walk right 45°", value: "walk_r45" },
    { label: "Walk right 90°", value: "walk_r90" },
    { label: "Walk right 135°", value: "walk_r135" },
    { label: "Walk left 45°", value: "walk_l45" },
    { label: "Walk left 90°", value: "walk_l90" },
    { label: "Walk left 135°", value: "walk_l135" },
    { label: "Fast forward", value: "fast_forward" },
    { label: "Fast backward", value: "fast_backward" },
    { label: "Turn left", value: "turn_left" },
    { label: "Turn right", value: "turn_right" },
    { label: "Climb forward", value: "climb_forward" },
    { label: "Climb backward", value: "climb_backward" },
    { label: "Rotate X (pitch)", value: "rotate_x" },
    { label: "Rotate Y (roll)", value: "rotate_y" },
    { label: "Rotate Z (wobble)", value: "rotate_z" },
    { label: "Twist (figure-8)", value: "twist" },
    { label: "Stand up", value: "standup" },
];

export const GAIT_LABELS: Record<string, string> = Object.fromEntries(
    MOTION_TYPES.map((m) => [m.value, m.label]),
);

/** The library's built-in gaits, in groups. */
export const GAIT_MENU: [string, string[]][] = [
    [
        "Walk",
        [
            "walk_0",
            "walk_180",
            "walk_l45",
            "walk_l90",
            "walk_l135",
            "walk_r45",
            "walk_r90",
            "walk_r135",
        ],
    ],
    [
        "Fast, turn and climb",
        [
            "fast_forward",
            "fast_backward",
            "turn_left",
            "turn_right",
            "climb_forward",
            "climb_backward",
        ],
    ],
    ["Body", ["rotate_x", "rotate_y", "rotate_z", "twist"]],
    ["Posture", ["standby", "standup"]],
];

// The controller's move pad: standby in the middle, around it a ring of eight
// walks (clockwise from forward), and outside that fast forward, the turns and
// fast backward.
export const DRIVE_MOVE_PAD = {
    centre: "standby",
    walk: [
        "walk_0",
        "walk_r45",
        "walk_r90",
        "walk_r135",
        "walk_180",
        "walk_l135",
        "walk_l90",
        "walk_l45",
    ],
    outer: ["fast_forward", "turn_right", "fast_backward", "turn_left"],
};

// The body pad: moves on the spot, in rows of two as on the Android app, each
// with the short name it is labelled with.
export const DRIVE_BODY_PAD: [string, string][][] = [
    [
        ["rotate_y", "Roll"],
        ["climb_forward", "Climb"],
    ],
    [
        ["rotate_x", "Pitch"],
        ["twist", "Twist"],
    ],
    [
        ["rotate_z", "Wobble"],
        ["climb_backward", "Climb"],
    ],
];

/** What each pad motion is called in its tooltip, and while it is held. */
export const DRIVE_LABELS: Record<string, string> = {
    standby: "Standby",
    walk_0: "Walk forward",
    walk_180: "Walk backward",
    walk_r45: "Walk right 45°",
    walk_r90: "Walk right 90°",
    walk_r135: "Walk right 135°",
    walk_l45: "Walk left 45°",
    walk_l90: "Walk left 90°",
    walk_l135: "Walk left 135°",
    fast_forward: "Fast forward",
    fast_backward: "Fast backward",
    turn_left: "Turn left",
    turn_right: "Turn right",
    climb_forward: "Climb forward",
    climb_backward: "Climb backward",
    rotate_x: "Rotate X (pitch)",
    rotate_y: "Rotate Y (roll)",
    rotate_z: "Rotate Z (wobble)",
    twist: "Twist (figure-8)",
};
