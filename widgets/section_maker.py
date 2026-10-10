# Building blocks of the panels over the view and of the dock, so they all lay
# their controls out the same way. Sizing is left to the CSS (see CONTROLS in
# assets/industrial.css) rather than to Bootstrap column counts.
import dash_bootstrap_components as dbc
from dash import dcc, html

from hexapod.naming import leg_label


def field_label(text):
    return html.Label(text, className="ind-field-label")


def group_header(text):
    """A small header over a group of fields within one card."""
    return html.Div(text, className="ind-group-header")


def make_slider_field(
    slider_id, label, min_value, max_value, step, value, disabled=False, updatemode="mouseup"
):
    """A slider on one line: its label, the track, and its value box.

    The box at the right end is Dash's own direct input, so a value can be
    typed as well as dragged to.
    """
    return html.Div(
        [
            field_label(label),
            dcc.Slider(
                id=slider_id,
                min=min_value,
                max=max_value,
                step=step,
                value=value,
                marks=None,
                disabled=disabled,
                updatemode=updatemode,
                allow_direct_input=True,
            ),
        ],
        className="ind-inline-slider",
        title=f"{min_value:g} to {max_value:g}",
    )


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


def make_joint_grid(rows, column_labels, make_cell, class_name="", corner=""):
    """A table of one input per leg and joint.

    `rows` is a list of (key, label) pairs and `make_cell(key, column_index)`
    builds the input for one cell. The columns are named once, in the header,
    instead of under every input; `corner` goes over the rows' labels.
    """
    header = html.Tr(
        [html.Th(corner)]
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


# The legs a side at a time, front to back: the left ones, then the right.
LEG_SIDES = (
    ("Left", ("left-front", "left-middle", "left-back")),
    ("Right", ("right-front", "right-middle", "right-back")),
)


def short_leg_name(leg_name):
    """ "Right Leg 1" -> "R1", for where there is no room for the name."""
    side, _, number = leg_label(leg_name).split()
    return f"{side[0]}{number}"


# The splitters that resize the workspace's parts -- the dock, and the dock's
# columns -- by dragging or with the arrow keys, done in the page by
# assets/workspace_resize.js, which knows each by its kind (a class).
SPLITTER_CLASS = "ws-splitter"


def make_splitter(kind, orientation, label):
    """A splitter of `kind` ("dock", "lib", "run"), "vertical" for one
    dragged sideways; `label` says what it does, as "resize the dock"."""
    return html.Div(
        className=f"{SPLITTER_CLASS} {SPLITTER_CLASS}-{kind}",
        role="separator",
        tabIndex="0",
        title=f"Drag to {label}; double-click to reset",
        **{"aria-orientation": orientation, "aria-label": label.capitalize()},
    )
