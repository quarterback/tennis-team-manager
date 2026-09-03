"""The program page prints one line per honour per season (owner, 2026-09):
the award label once, then every selection from that program — never a line
per selection. `world.jh_honor_lines` is the pure fold behind it."""
from app.world import jh_honor_lines


def test_same_label_folds_onto_one_line_in_first_seen_order():
    honors = [
        "Snake River District Player of the Year — Isaac Evans",
        "All-Region (Blue Mountain Country) — Isaac Evans",
        "All-Region (Blue Mountain Country) — Cameron Johnson / Logan Rivera",
        "All-State Second Team (2A) — Isaac Evans",
        "All-State Third Team (2A) — Cameron Johnson / Logan Rivera",
        "All-District (Snake River District) — Isaac Evans",
        "All-District (Snake River District) — Cameron Johnson / Logan Rivera",
        "All-District (Snake River District) — Tyler Flores / Liam Cortez",
    ]
    lines = jh_honor_lines(honors)
    assert [l["label"] for l in lines] == [
        "Snake River District Player of the Year",
        "All-Region (Blue Mountain Country)",
        "All-State Second Team (2A)",
        "All-State Third Team (2A)",
        "All-District (Snake River District)",
    ]
    assert lines[1]["names"] == ["Isaac Evans", "Cameron Johnson / Logan Rivera"]
    assert lines[4]["names"] == ["Isaac Evans", "Cameron Johnson / Logan Rivera",
                                 "Tyler Flores / Liam Cortez"]
    # a pure fold: nobody is dropped or duplicated
    assert sum(len(l["names"]) for l in lines) == len(honors)


def test_a_string_without_the_separator_is_its_own_line():
    lines = jh_honor_lines(["Something unlabelled", "All-District (X) — A"])
    assert lines[0] == {"label": "", "names": ["Something unlabelled"]}
    assert lines[1] == {"label": "All-District (X)", "names": ["A"]}
    assert jh_honor_lines([]) == []
