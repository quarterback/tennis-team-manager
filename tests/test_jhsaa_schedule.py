"""JHSAA schedule shape (owner rule 2027-08).

District play is a DOUBLE round-robin — home and away — and the rest of the card is
non-district, drawn on geography, talent and availability, at your classification or one
apart. Every one of these was got wrong once: a single round-robin, a uniform-random
opponent draw, and a crossover locked inside one classification.

Scoped to a few districts so the file stays fast; `run_season` is ~17s a gender.
"""
import collections
import random

import pytest

from app import jhsaa


@pytest.fixture(scope="module")
def played():
    """Two 7A districts and two 6A, played in `run_season`'s order: rosters, then one
    crossover across all four, then the district round-robins."""
    groups = []
    for group in ("7A", "6A"):
        d = jhsaa.districts("girls", group)
        groups += [jhsaa.district_teams(d[name], 2030) for name in sorted(d)[:2]]
    teams = [t for g in groups for t in g]
    jhsaa._crossover(teams, random.Random("test|xover"))
    for g in groups:
        jhsaa.play_district(g, 2030)
    return teams


def test_non_district_duals_are_played_before_league_play(played):
    """Non-conference is front-loaded, as in real life and in the college sim."""
    for t in played:
        flags = [x["district"] for x in _regular(t)]
        assert flags == sorted(flags), (t.school.name, flags)   # all False, then all True


def _regular(t):
    return [x for x in t.schedule if x["phase"] == "regular"]


def test_district_play_is_a_double_round_robin(played):
    """Every league opponent exactly twice, once home and once away."""
    for t in played:
        legs = collections.defaultdict(list)
        for x in _regular(t):
            if x["district"]:
                legs[x["opp"]].append(x["home"])
        peers = sum(1 for o in played
                    if (o.school.group, o.school.district)
                    == (t.school.group, t.school.district)) - 1
        assert len(legs) == peers, (t.school.name, len(legs), peers)
        for opp, homes in legs.items():
            assert sorted(homes) == [False, True], (t.school.name, opp, homes)


def test_no_opponent_is_played_more_than_twice_in_the_regular_season(played):
    """Non-district play must not quietly recreate a second home-and-home."""
    for t in played:
        counts = collections.Counter(x["opp"] for x in _regular(t))
        assert not [o for o, n in counts.items() if n > 2], (t.school.name, counts)


def test_non_district_stays_within_one_classification(played):
    """A 7A card mixes 7A and 6A; it never lands on 1A."""
    by = {t.school.name: t for t in played}
    seen = 0
    for t in played:
        for x in _regular(t):
            o = by.get(x["opp"])
            if x["district"] or o is None:
                continue
            seen += 1
            gap = abs(jhsaa._GROUP_IX[o.school.group] - jhsaa._GROUP_IX[t.school.group])
            assert gap <= 1, (t.school.name, x["opp"], gap)
    assert seen, "no cross-district duals were scheduled at all"


def test_non_district_opponents_are_never_from_your_own_district(played):
    by = {t.school.name: t for t in played}
    for t in played:
        for x in _regular(t):
            o = by.get(x["opp"])
            if x["district"] or o is None:
                continue
            assert (o.school.group, o.school.district) \
                != (t.school.group, t.school.district), (t.school.name, x["opp"])


def test_non_district_count_is_an_allowance_not_a_season_total(played):
    """Teams from different-sized districts play different totals; the NON-DISTRICT
    count is what's bounded."""
    for t in played:
        n = sum(1 for x in _regular(t) if not x["district"])
        assert n <= jhsaa.NONDISTRICT_MAX, (t.school.name, n)


def test_non_district_draw_prefers_near_opponents_on_geography_and_talent(played):
    """Not a golden value — a directional check that the draw is scored, not uniform.
    Compare each actual non-district opponent against the classification-eligible field:
    the picks must sit well inside it on both geography and talent."""
    by = {t.school.name: t for t in played}
    geo_pick, geo_all, tal_pick, tal_all = [], [], [], []
    for t in played:
        gi = jhsaa._GROUP_IX[t.school.group]
        st = jhsaa._strength(t)
        field = [o for o in played if o is not t
                 and abs(jhsaa._GROUP_IX[o.school.group] - gi) <= 1
                 and (o.school.group, o.school.district)
                 != (t.school.group, t.school.district)]
        if not field:
            continue
        geo_all += [jhsaa._geo_gap(t.school, o.school) for o in field]
        tal_all += [abs(jhsaa._strength(o) - st) for o in field]
        for x in _regular(t):
            o = by.get(x["opp"])
            if x["district"] or o is None:
                continue
            geo_pick.append(jhsaa._geo_gap(t.school, o.school))
            tal_pick.append(abs(jhsaa._strength(o) - st))
    assert geo_pick and tal_pick
    mean = lambda v: sum(v) / len(v)                          # noqa: E731
    assert mean(geo_pick) < mean(geo_all), "draw ignores geography"
    assert mean(tal_pick) < mean(tal_all), "draw ignores talent"
