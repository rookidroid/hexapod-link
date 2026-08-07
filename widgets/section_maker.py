# Used to make html divisions using Bootstrap components
import dash_bootstrap_components as dbc


def make_section_type3(div1, div2, div3, name1="", name2="", name3=""):
    return dbc.Row(
        [
            dbc.Col([div1, name1], width=4),
            dbc.Col([div2, name2], width=4),
            dbc.Col([div3, name3], width=4),
        ],
        className="g-2",
    )


def make_section_type4(div1, div2, div3, div4):
    return dbc.Row(
        [
            dbc.Col(div1, width=2),
            dbc.Col(div2, width=3),
            dbc.Col(div3, width=3),
            dbc.Col(div4, width=4),
        ],
        className="g-2",
    )


def make_section_type2(div1, div2):
    return dbc.Row(
        [
            dbc.Col(div1, width=6),
            dbc.Col(div2, width=6),
        ],
        className="g-2",
    )
