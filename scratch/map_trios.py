import re

filepath = "hexapod/ground_contact_solver/shared.py"
with open(filepath, "r") as f:
    content = f.read()

# Old to new mapping
MAPPING = {
    0: 1,
    1: 0,
    2: 3,
    3: 4,
    4: 5,
    5: 2
}

def map_trio(match):
    trio_str = match.group(0)
    # Extract numbers
    nums = [int(x) for x in re.findall(r'\d+', trio_str)]
    new_nums = [MAPPING[n] for n in nums]
    return f"({new_nums[0]}, {new_nums[1]}, {new_nums[2]})"

new_content = re.sub(r'\(\d,\s*\d,\s*\d\)', map_trio, content)

with open(filepath, "w") as f:
    f.write(new_content)

print("Mapped LEG_TRIOS!")
