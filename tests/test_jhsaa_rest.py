"""Talent-aware staffing vs. truly bad teams (owner rule 2026-08, rest count
expanded 2026-08 alongside injuries).

A coach facing a clearly weaker regular-season opponent rests a run of starters
(1 up to REST_MAX, tapering off) from the TOP of the ladder; everyone shifts up
a rung so the card still reads as the ladder. Never in the postseason, never at
a showcase, never past the bench.
"""
import random

import pytest

from app import jhsaa


def _teams():
    schools = jhsaa.load_schools("boys")
    strong = max(schools[:60], key=lambda s: s.enrollment)
    weak = min(schools[:60], key=lambda s: s.enrollment)
    a = jhsaa.TeamSeason(school=strong, roster=jhsaa.build_roster(strong, 2035))
    b = jhsaa.TeamSeason(school=weak, roster=jhsaa.build_roster(weak, 2035))
    return a, b


def _force_gap(a, b):
    """Make the gap unambiguous whatever the dice rolled."""
    for p in a.roster:
        p.current = {k: min(80.0, v + 15) for k, v in p.current.items()}
    for p in b.roster:
        p.current = {k: max(12.0, v - 15) for k, v in p.current.items()}


def test_rest_fires_against_a_bad_record_and_big_gap():
    a, b = _teams()
    _force_gap(a, b)
    b.wins, b.losses = 1, 9                     # .100, real sample
    rng = random.Random(1)
    fired = sum(bool(jhsaa._rest_count(a, b, rng, 3)) for _ in range(200))
    assert 0.5 < fired / 200 < 0.95             # REST_RATE, not always


def test_a_real_record_overrides_the_eye_test():
    """A weak-looking roster that is actually winning does not get rested on."""
    a, b = _teams()
    _force_gap(a, b)
    b.wins, b.losses = 6, 2                     # .750 with a real sample
    rng = random.Random(1)
    assert all(jhsaa._rest_count(a, b, rng, 3) == 0 for _ in range(50))


def test_no_gap_no_rest_and_no_bench_no_rest():
    a, b = _teams()
    b.wins, b.losses = 0, 10
    rng = random.Random(1)
    # near-peer rosters (no forced gap): the strength floor must hold on its own
    if jhsaa._strength(a) - jhsaa._strength(b) < jhsaa.REST_GAP:
        assert jhsaa._rest_count(a, b, rng, 3) == 0
    _force_gap(a, b)
    assert all(jhsaa._rest_count(a, b, rng, 0) == 0 for _ in range(20))


def test_lineup_rests_from_the_top_and_keeps_ladder_order():
    a, b = _teams()
    _force_gap(a, b)
    b.wins, b.losses = 0, 10
    order = [p.pid for p in jhsaa._order(a)]
    need = jhsaa.lineup_need("early")           # 5S/2D: plain ladder order card
    rested = 0
    for seed in range(60):
        rng = random.Random(f"lineup|{seed}")
        nine = jhsaa._lineup(a, "early", rng, b)
        pids = [p.pid for p in nine]
        if order[0] not in pids:
            rested += 1
            # everyone shifts up: the dressed card is a contiguous ladder slice
            # apart from the ordinary bench rotation at the bottom seats. `k` can
            # now run up to REST_MAX (tapering off), not just 1-2.
            k = order.index(pids[0])
            assert 1 <= k <= jhsaa.REST_MAX
            assert pids[:need - 2] == order[k:k + need - 2]
    assert rested > 10, rested


def test_postseason_and_showcases_never_rest():
    a, b = _teams()
    _force_gap(a, b)
    b.wins, b.losses = 0, 12
    top = jhsaa._order(a)[0].pid
    for phase in jhsaa.POSTSEASON + jhsaa.SHOWCASE:
        a.order_of_ability = []                 # re-freeze each phase cleanly
        for seed in range(20):
            rng = random.Random(f"lineup|{seed}")
            nine = jhsaa._lineup(a, phase, rng, b)
            assert top in [p.pid for p in nine], phase


def test_rest_never_wraps_a_short_roster():
    a, b = _teams()
    _force_gap(a, b)
    b.wins, b.losses = 0, 10
    a.roster = a.roster[:jhsaa.lineup_need("regular")]      # zero bench
    for seed in range(30):
        rng = random.Random(f"lineup|{seed}")
        nine = jhsaa._lineup(a, "regular", rng, b)
        assert len({p.pid for p in nine}) == len(nine)
