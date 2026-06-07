import os
import re

TEST_DIRS = [
    "tests/ik_cases",
    "tests/kinematics_cases",
    "tests/pattern_cases",
]

MAPPING = {
    0: 1,
    1: 0,
    2: 3,
    3: 4,
    4: 5,
    5: 2
}

def fix_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    # 1. Fix correct_poses / given_poses dictionary keys and 'id' values
    for old_id, new_id in MAPPING.items():
        # Match dict key and change temporarily
        content = re.sub(rf"^\s*{old_id}: {{", f"    TEMP_{new_id}: {{", content, flags=re.MULTILINE)
        # Match "id": X
        content = re.sub(rf'\"id\": {old_id}', f'"id": TEMP_{new_id}', content)
        
    for old_id, new_id in MAPPING.items():
        content = content.replace(f"TEMP_{new_id}: {{", f"{new_id}: {{")
        content = content.replace(f'"id": TEMP_{new_id}', f'"id": {new_id}')

    # 2. Fix correct_body_points array order
    body_points_match = re.search(r"correct_body_points = \[(.*?)\]", content, flags=re.DOTALL)
    if body_points_match:
        lines = [line.strip() for line in body_points_match.group(1).split("\n") if line.strip() and not line.strip().startswith("#")]
        if len(lines) >= 8:
            new_lines = [
                lines[1], lines[0], lines[5], lines[2], lines[3], lines[4], lines[6], lines[7]
            ]
            new_block = "correct_body_points = [\n    " + ",\n    ".join([l.rstrip(',') for l in new_lines]) + ",\n]"
            content = content[:body_points_match.start()] + new_block + content[body_points_match.end():]

    # 3. Fix correct_leg_points array order
    leg_points_match = re.search(r"correct_leg_points = \[(.*?)\]", content, flags=re.DOTALL)
    if leg_points_match:
        lines = [line.strip() for line in leg_points_match.group(1).split("\n") if line.strip() and not line.strip().startswith("#")]
        if len(lines) >= 6:
            new_lines = [
                lines[1], lines[0], lines[5], lines[2], lines[3], lines[4]
            ]
            new_block = "correct_leg_points = [\n    " + ",\n    ".join([l.rstrip(',') for l in new_lines]) + ",\n]"
            content = content[:leg_points_match.start()] + new_block + content[leg_points_match.end():]

    with open(filepath, "w") as f:
        f.write(content)

for d in TEST_DIRS:
    for f in os.listdir(d):
        if f.endswith(".py") and f.startswith("case"):
            fix_file(os.path.join(d, f))

print("Fixed tests!")
