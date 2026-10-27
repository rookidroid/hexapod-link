"""Record what the Python code computes, for the TypeScript port's tests.

Run once, with the Python code still in place:

    python tools/dump_golden.py

Writes tests/fixtures/golden/<robot>.json. Inputs are drawn from a seeded
generator and stored next to the outputs, so the TS tests replay them.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hexapod import gait_keyframes as gk  # noqa: E402
from hexapod import keyframes as kf  # noqa: E402
from hexapod import pose_layers as pl  # noqa: E402
from hexapod.path_generator import generate_poses  # noqa: E402
from hexapod.robot_config import (  # noqa: E402
    DEFAULT_CONFIG,
    get_simulator_dimensions,
    parse_robot_config,
    with_dimensions,
)
from hexapod.robot_link import pose_to_ticks  # noqa: E402

MOTIONS = [
    "standby", "walk_0", "walk_180", "walk_r45", "walk_r90", "walk_r135", "walk_l45",
    "walk_l90", "walk_l135", "fast_forward", "fast_backward", "turn_left", "turn_right",
    "climb_forward", "climb_backward", "rotate_x", "rotate_y", "rotate_z", "twist", "standup",
]


def clean(value):
    """JSON-able: numpy to lists, NaN to None, int keys to str."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return None if math.isnan(value) else value
    if isinstance(value, np.integer):
        return int(value)
    return value


def pose_list(pose):
    return [[pose[i]["coxia"], pose[i]["femur"], pose[i]["tibia"]] for i in range(6)]


def random_body(rng, scale=1.0):
    return {
        "percent_x": float(rng.uniform(-0.3, 0.3) * scale),
        "percent_y": float(rng.uniform(-0.3, 0.3) * scale),
        "percent_z": float(rng.uniform(-0.3, 0.3) * scale),
        "rot_x": float(rng.uniform(-15, 15) * scale),
        "rot_y": float(rng.uniform(-15, 15) * scale),
        "rot_z": float(rng.uniform(-15, 15) * scale),
    }


def dump(name, robot):
    rng = np.random.default_rng(abs(hash(name)) % 2**32 if False else len(name) * 7919)
    out = {"name": name}
    out["dimensions"] = get_simulator_dimensions(robot)
    out["standby_feet"] = kf.standby_feet(robot)
    out["ground_height"] = kf.ground_height(robot)

    # Gaits.
    out["generate_poses"] = {m: [pose_list(p) for p in generate_poses(m, robot)] for m in MOTIONS}
    out["robot_poses"] = {m: [pose_list(p) for p in gk.robot_poses(m, robot)] for m in MOTIONS}
    out["gait_keyframes"] = {m: gk.gait_keyframes(m, robot) for m in MOTIONS}

    standby = np.asarray(kf.standby_feet(robot))

    # feet_to_pose, with and without a margin, some out of reach.
    cases = []
    for i in range(40):
        spread = 30 if i < 30 else 150
        feet = (standby + rng.normal(0, spread, (6, 3))).round(3).tolist()
        margin = [0.0, 0.5, 2.0][i % 3]
        pose, bad = kf.feet_to_pose(feet, robot, margin)
        cases.append({"feet": feet, "margin": margin, "pose": pose_list(pose), "bad": bad})
    out["feet_to_pose"] = cases

    # nearest_reachable_foot.
    cases = []
    for i in range(60):
        leg = i % 6
        foot = (standby[leg] + rng.normal(0, 25 if i < 30 else 120, 3)).tolist()
        cases.append(
            {"leg": leg, "foot": foot, "out": kf.nearest_reachable_foot(foot, leg, robot)}
        )
    out["nearest_reachable_foot"] = cases

    # Poses: pose_to_feet, joint_axes, pose_to_scene, ticks.
    cases = []
    for i in range(10):
        angles = rng.uniform(-30, 30, (6, 3)).round(2)
        pose = {
            leg: {"coxia": angles[leg][0], "femur": angles[leg][1], "tibia": angles[leg][2]}
            for leg in range(6)
        }
        pose = {leg: {k: float(v) for k, v in j.items()} for leg, j in pose.items()}
        cases.append(
            {
                "pose": pose_list(pose),
                "feet": kf.pose_to_feet(pose, robot),
                "axes": kf.joint_axes(pose, robot),
                "scene": kf.pose_to_scene(pose, robot),
                "ticks": pose_to_ticks(pose, robot),
            }
        )
    out["poses"] = cases

    # Pose layers.
    cases = []
    for i in range(20):
        body = random_body(rng, 1.0 if i < 15 else 3.0)
        offsets = rng.normal(0, 10, (6, 3)).round(2)
        offsets[rng.integers(0, 6)] = 0
        state = pl.make_state(body, offsets)
        feet, pose, bad = pl.solve(state, robot)
        leg = int(rng.integers(0, 6))
        target = (np.asarray(pl.view_feet(state, robot)[leg]) + rng.normal(0, 40, 3)).tolist()
        angles = {"femur": float(rng.uniform(-60, 60))}
        new_body = random_body(rng, 2.5)
        frame = pl.body_frame(state, robot)
        cases.append(
            {
                "state": state,
                "body_feet": feet,
                "pose": pose_list(pose),
                "bad": bad,
                "view_feet": pl.view_feet(state, robot),
                "scene": pl.scene(state, pose, robot),
                "frame": frame,
                "body_at": pl.body_at(frame["origin"], frame["rot"], robot),
                "leg": leg,
                "target": target,
                "with_foot_at": pl.with_foot_at(state, leg, target, robot),
                "with_foot_near": pl.with_foot_near(state, leg, target, robot),
                "angles": angles,
                "with_leg_angles": pl.with_leg_angles(state, leg, angles, robot),
                "new_body": new_body,
                "with_body_near": pl.with_body_near(state, new_body, robot),
                "from_feet": pl.from_feet(feet, robot),
            }
        )
    out["layers"] = cases

    # Sequences.
    states = [pl.make_state(random_body(rng, 0.5), rng.normal(0, 6, (6, 3))) for _ in range(4)]
    keyframes = [
        kf.make_keyframe(pl.body_feet(s, robot), int(rng.integers(100, 900)), s, ease=i % 2 == 0)
        for i, s in enumerate(states)
    ]
    legacy = [{k: v for k, v in frame.items() if k != "state"} for frame in keyframes]
    cases = []
    for frames, label in ((keyframes, "layers"), (legacy, "legacy"), (keyframes[:1], "one")):
        for loop in (False, True):
            for ease, speed, fps in ((True, 1.0, 25), (False, 1.6, 83.333), (True, 0.4, 25)):
                feet, sstates, poses, bad = pl.sequence(frames, robot, fps, loop, ease, speed)
                cases.append(
                    {
                        "keyframes": label,
                        "loop": loop,
                        "ease": ease,
                        "speed": speed,
                        "fps": fps,
                        "feet": feet,
                        "states": sstates,
                        "poses": [pose_list(p) for p in poses],
                        "bad": bad,
                        "times": kf.frame_times(frames, fps, loop, speed),
                        "duration": kf.sequence_duration_ms(frames, loop, speed),
                    }
                )
    out["sequence_keyframes"] = keyframes
    out["sequences"] = cases
    out["dump"] = json.loads(kf.dump(keyframes, robot))

    # Resized bodies.
    dims = {"front": 50, "side": 80.5, "middle": 70, "coxia": 40, "femur": 60, "tibia": 100}
    resized = with_dimensions(robot, dims)
    out["with_dimensions"] = {
        "dimensions": dims,
        "config": resized["config"],
        "standby_feet": kf.standby_feet(resized),
        "scene": pl.scene(pl.standby_state(), pl.solve(pl.standby_state(), resized)[1], resized),
    }
    return out


def main():
    target = ROOT / "tests" / "fixtures" / "golden"
    target.mkdir(parents=True, exist_ok=True)
    robots = {}
    for name in ("nougat", "mochi", "macaroon"):
        payload = json.loads((ROOT / "tests/fixtures/robot_config" / f"{name}.json").read_text())
        robots[name] = parse_robot_config(payload)
    for name, robot in robots.items():
        data = clean(dump(name, robot))
        parsed = {k: v for k, v in robot.items() if k != "payload"}
        data["parsed_config"] = clean(parsed)
        path = target / f"{name}.json"
        path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        print(path, path.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
