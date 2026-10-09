# Building blocks of the tool panels, so every tool lays out its controls the
# same way. Sizing is left to the CSS (see CONTROLS in assets/industrial.css): each block adapts to whatever width the panel has
# rather than to Bootstrap column counts.
import dash_bootstrap_components as dbc
from dash import dcc, html

from hexapod.naming import JOINT_NAMES, joint_short_label, leg_label


def field_label(text):
    return html.Label(text, className="ind-field-label")


def panel_section(header, children, blurb=None, **div_props):
    """One titled block of a tool panel.

    Flat on the panel rather than a card inside it: sections are told apart by
    the rule under each one (see TOOL PANEL in assets/industrial.css), so
    the panel is one plate instead of a stack of nested ones.
    """
    body = [html.H6(header, className="mb-2" if blurb else "mb-3")]
    if blurb:
        body.append(html.P(blurb, className="text-muted small mb-3"))
    body.extend(children if isinstance(children, list) else [children])
    return html.Section(body, className="ind-section", **div_props)


def group_header(text):
    """A small header over a group of fields within one card."""
    return html.Div(text, className="ind-group-header")


def make_slider_field(
    slider_id,
    label,
    min_value,
    max_value,
    step,
    value,
    marks=None,
    disabled=False,
    updatemode="mouseup",
):
    """A label on its own line, then the slider with its value box.

    The same two rows whatever the label or the width of the panel. The box at
    the right end is Dash's own direct input, so a value can be typed as well
    as dragged to. Marks default to the two ends of the range, so every slider
    shows its limits the same way.
    """
    if marks is None:
        marks = {min_value: _mark(min_value), max_value: _mark(max_value)}

    return html.Div(
        [
            field_label(label),
            dcc.Slider(
                id=slider_id,
                min=min_value,
                max=max_value,
                step=step,
                value=value,
                marks=marks,
                disabled=disabled,
                updatemode=updatemode,
                allow_direct_input=True,
            ),
        ],
        className="ind-slider-field",
    )


def _mark(number):
    return f"{number:g}"


def make_number_field(input_id, label, **input_props):
    """A number input with its label above it, for use in make_field_grid()."""
    return html.Div(
        [
            field_label(label),
            dbc.Input(id=input_id, type="number", size="sm", **input_props),
        ],
        className="ind-number-field",
    )


def make_field_grid(fields, one_row=False):
    """Lays fields out in as many columns as the panel has room for, or all
    on one row with `one_row`, for a few that belong together (x, y, z)."""
    class_name = "ind-field-grid ind-field-row" if one_row else "ind-field-grid"
    return html.Div(fields, className=class_name)


def make_joint_grid(rows, column_labels, make_cell, class_name=""):
    """A table of one input per (row, joint): rows of legs, columns of joints.

    `rows` is a list of (key, label) pairs and `make_cell(key, column_index)`
    builds the input for one cell. The joint names are printed once, in the
    header, instead of under every input.
    """
    header = html.Tr(
        [html.Th("")]
        + [html.Th(label, className="text-center") for label in column_labels]
    )
    body = [
        html.Tr(
            [html.Th(label, className="text-nowrap align-middle")]
            + [html.Td(make_cell(key, j)) for j in range(len(column_labels))]
        )
        for key, label in rows
    ]
    return dbc.Table(
        [html.Thead(header), html.Tbody(body)],
        borderless=True,
        size="sm",
        className=f"ind-joint-grid {class_name}".strip(),
    )


# One block per side, front to back, left beside right as on the robot.
LEG_SIDES = (
    ("Left", ("left-front", "left-middle", "left-back")),
    ("Right", ("right-front", "right-middle", "right-back")),
)


def short_leg_label(leg_name):
    # "Right Leg 1" -> "R1". The block it sits in already says which side;
    # the full name is kept as a tooltip.
    full = leg_label(leg_name)
    side, _, number = full.split()
    return html.Span(f"{side[0]}{number}", title=full)


def make_leg_sides(make_cell):
    """A Left and a Right joint grid, side by side when the panel has room.

    `make_cell(leg_name, joint_index)` builds one cell. Left above right when
    they do not fit together -- never interleaved. See CONTROLS in
    assets/industrial.css.
    """
    blocks = [
        html.Div(
            [
                group_header(side),
                make_joint_grid(
                    [(name, short_leg_label(name)) for name in legs],
                    [joint_short_label(joint) for joint in JOINT_NAMES],
                    make_cell,
                    class_name="mb-0",
                ),
            ],
            className="ind-joint-side",
        )
        for side, legs in LEG_SIDES
    ]
    return html.Div(blocks, className="ind-joint-sides")
