"""The calibration page's mapping between its 18 inputs and the robot's offsets.

The firmware keeps offsets as {"left": [3 legs][3 joints], "right": ...}, legs
front to back; the page lays them out in leg-index order, right legs first. A
mix-up here trims the wrong servo, so the correspondence is pinned.
"""

from pages.page_calibration import offsets_to_values, values_to_offsets
from widgets.calibration_ui import OFFSET_INPUT_IDS, offset_input_id


def test_inputs_are_leg_major():
    assert OFFSET_INPUT_IDS[0] == offset_input_id(0, 0)
    assert OFFSET_INPUT_IDS[5] == offset_input_id(1, 2)
    assert OFFSET_INPUT_IDS[17] == offset_input_id(5, 2)


def test_right_leg_1_is_the_first_right_row_and_left_leg_1_the_first_left_row():
    offsets = {
        "right": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
        "left": [[-1, -2, -3], [-4, -5, -6], [-7, -8, -9]],
    }
    values = offsets_to_values(offsets)
    assert values[0:3] == [1, 2, 3]        # Right Leg 1 = leg 0
    assert values[9:12] == [-1, -2, -3]    # Left Leg 1 = leg 3
    assert values_to_offsets(values) == offsets


def test_blank_inputs_are_zero_and_wide_ones_are_clamped():
    values = [None] * 18
    values[4] = 150      # Right Leg 2, joint 2
    values[15] = -250.4  # Left Leg 3, joint 1
    values[16] = 7.6
    offsets = values_to_offsets(values)
    assert offsets["right"][1] == [0, 100, 0]
    assert offsets["left"][2] == [-100, 8, 0]
