"""A DISTRICT dual plays its class's State format (owner rule 2026-10).

The district championship is what qualifies and protects a program on the road to
State, and most classes used to spend it playing a different version of tennis from
the championship it fed. Now the league season is where a class plays its own
format: 4S/5D in the wide classes, 6S/5D in 5A, 1S/4D in 4A/3A/2A/Group 3, 2S/3D in
1A, 3S/3D in Group 2, and the unchanged 3S/4D in 6A/11B. Invitationals (every other
regular-season dual) stay 3S/4D and the early window stays 5S/2D.

See docs/AAR-jhsaa-district-plays-the-state-format.md.
"""
import random

import pytest

from app import jhsaa as jh
from app import jhsaa_awards as jaw

#: The owner's table, typed ONCE here so the code cannot drift from it.
DISTRICT = {"9A": (4, 5), "8A": (4, 5), "7A": (4, 5), "6A": (3, 4),
            "5A": (6, 5), "4A": (1, 4), "3A": (1, 4), "2A": (1, 4),
            "1A": (2, 3), "Group 1": (4, 5), "Group 2": (3, 3),
            "Group 3": (1, 4), "10B": (4, 5), "11B": (3, 4)}


def _shape(f):
    return (f.n_singles, f.n_doubles)


def test_every_class_plays_the_owners_district_format():
    assert set(DISTRICT) == set(jh.ROAD_GROUPS)
    for g, want in DISTRICT.items():
        f = jh.dual_format("regular", g, district=True)
        assert _shape(f) == want, g
        assert jh.district_format(g) is f
        assert jh.district_need(g) == want[0] + 2 * want[1], g


def test_the_district_format_IS_the_class_state_format():
    """Not a second table — the road's own shape, so a class that changes its State
    format changes its league season with it."""
    for g in jh.ROAD_GROUPS:
        assert jh.district_format(g) is jh.dual_format("sectional", g), g
        assert jh.district_format(g) is jh.dual_format("state", g), g


def test_invitationals_stay_3s4d_and_the_early_window_stays_5s2d():
    for g in jh.ROAD_GROUPS:
        assert jh.dual_format("regular", g) is jh.FORMATS["regular"], g
        assert jh.lineup_need("regular", g) == 11, g
        assert jh.dual_format(jh.EARLY_FORMAT_PHASE, g) is jh.FORMATS["early"], g
        # `district` only means something for a regular-season dual
        assert jh.dual_format(jh.EARLY_FORMAT_PHASE, g, district=True) \
            is jh.FORMATS["early"], g
        assert jh.dual_format("toc", g, district=True) is jh.FORMATS["state"], g


def test_a_district_dual_is_rated_on_its_formats_weight_table():
    assert jh.flight_weights("regular", "9A", district=True) is jh.FLIGHT_WEIGHTS_4S5D
    assert jh.flight_weights("regular", "5A", district=True) is jh.FLIGHT_WEIGHTS_6S5D
    assert jh.flight_weights("regular", "9A") is jh.FLIGHT_WEIGHTS
    for g in ("6A", "4A", "1A", "Group 2"):
        assert jh.flight_weights("regular", g, district=True) is jh.FLIGHT_WEIGHTS, g
    # every flight any district format contests is priced on its table
    for g in jh.ROAD_GROUPS:
        f = jh.district_format(g)
        w = jh.flight_weights("regular", g, district=True)
        for i in range(1, f.n_singles + 1):
            assert f"S{i}" in w, (g, i)
        for i in range(1, f.n_doubles + 1):
            assert f"D{i}" in w, (g, i)


def test_the_award_weight_follows_the_district_flag():
    """A 9A league S2 is priced on the 4S/5D table (0.50 of the top flight), not
    the 3S/4D one (0.74) the phase alone would name."""
    on = jaw._weight("S2", "regular", jh.POSTSEASON, group="9A", district=True)
    off = jaw._weight("S2", "regular", jh.POSTSEASON, group="9A")
    assert on == pytest.approx(1.00 / 2.00)
    assert off == pytest.approx(jh.FLIGHT_WEIGHTS["S2"])


def _two(group, gender="boys", year=2031):
    out = []
    for sc in jh.load_schools(gender):
        if sc.group == group:
            ts = jh.TeamSeason(school=sc, roster=jh.build_roster(sc, year))
            if len(ts.roster) >= jh.district_need(group) + 2:
                out.append(ts)
        if len(out) == 2:
            return out
    pytest.skip(f"no two {group} programs")


@pytest.mark.parametrize("group", ["9A", "5A", "4A", "1A", "6A"])
def test_a_district_dual_dresses_and_scores_the_class_format(group):
    a, b = _two(group)
    jh.play_dual(a, b, seed=7, phase="regular", district=True)
    row = a.schedule[-1]
    ns, nd = DISTRICT[group]
    slots = [ln["slot"] for ln in row["lines"]]
    assert slots.count("S1") == 1
    assert sorted(s for s in slots if s[0] == "S") == [f"S{i}" for i in range(1, ns + 1)]
    assert sorted(s for s in slots if s[0] == "D") == [f"D{i}" for i in range(1, nd + 1)]
    assert row["district"] and row["phase"] == "regular"
    assert a.dwins + a.dlosses + a.dties == 1
    # nobody plays two flights of one dual: the dressing group is the format's size
    names = [n for ln in row["lines"] for n in ln["home"]]
    assert len(names) == len(set(names)) == jh.district_need(group)
    # the résumé entry carries the district flag as its seventh field
    entry = next(iter(a.matches.values()))[-1]
    assert len(entry) == 7 and entry[6] is True


def test_a_non_district_dual_between_the_same_programs_is_3s4d():
    a, b = _two("9A")
    jh.play_dual(a, b, seed=7, phase="regular")
    row = a.schedule[-1]
    assert len(row["lines"]) == 7 and not row["district"]
    assert a.dwins + a.dlosses == 0
    entry = next(iter(a.matches.values()))[-1]
    assert entry[6] is False


def test_a_district_rating_row_carries_the_4s5d_table():
    a, b = _two("8A")
    jh.play_dual(a, b, seed=3, phase="regular", district=True)
    jh.play_dual(a, b, seed=4, phase="regular")
    rows = jh.rating_duals([a, b])
    assert [r["weights"] is jh.FLIGHT_WEIGHTS_4S5D for r in rows] == [True, False]


def test_a_level_group_2_district_dual_is_a_tie_and_half_a_win():
    """Group 2's district format is 3S/3D, so a league dual CAN finish level —
    regular season, so the JV ladder (points, sets, games) and then a TIE, never
    the postseason deciders. District place reads it as half a win."""
    # A program against a copy of itself: evenly matched by construction, so a
    # level dual turns up within a few hundred seeds (two real programs are
    # usually far enough apart that it never does).
    a0, _ = _two("Group 2", "girls")
    for seed in range(1, 3000):
        a = jh.TeamSeason(school=a0.school, roster=a0.roster)
        b = jh.TeamSeason(school=a0.school, roster=a0.roster)
        jh.play_dual(a, b, seed=seed, phase="regular", district=True)
        if a.schedule[-1]["tied"]:
            break
    else:
        pytest.skip("no drawn Group 2 district dual in the seed window")
    row = a.schedule[-1]
    assert row["pf"] == row["pa"] == 3 and row["tiebreak"] == []
    assert a.dties == b.dties == 1 and a.ties == 1
    assert a.district_record == "0-0-1"
    assert a.district_pct == pytest.approx(0.5)


def test_the_v1_cut_is_the_district_lineup():
    """The roster-facing readers — the preseason V1 cut and the rising-freshman
    portal's projected seat — key off the class's district lineup."""
    from app import jhsaa_portal as jp
    for group in ("9A", "5A", "1A"):
        a, _ = _two(group)
        assert jp.v1_size(a) == jh.district_need(group)


def test_captains_are_drawn_from_the_smaller_dressing_group():
    """A 1S/4D class dresses nine for district duals, so its captains come from the
    top nine — a captain is always in every regular-season lineup by construction."""
    a, _ = _two("4A")
    order = [p.pid for p in jh._order(a)]
    for pid in jh.pick_captains(a, salt="t", year=2031):
        assert order.index(pid) < 9
