"""A challenge ladder is SEEDED ON ABILITY and MOVED BY RESULTS.

`_order` used to sort on cumulative wins first (`-w`), with ability third. That is a
ratchet, not a ladder: a win TOTAL measures opportunity, so dressing earns wins, wins
earn the next start, and a player who lost his opening duals — or who was tenth in week
one and never got a start — could never climb back, because every team-mate who kept
playing sat above him on a number he was not being allowed to add to. Ability was in
the key but unreachable behind it.

Measured over a full boys' season before the fix: a top-four player finished outside
the nine on 55 of 400 rosters, 21 of them under seven matches all year — the report
that started this was a 51-OVR senior who played six matches while a 28-OVR team-mate
played twenty-seven.

The bench ROTATION is not the bug and is not being removed: the owner wants a ninth
seat that moves around. What must hold is that it moves around the *best* nine.
"""
import pytest

from app import jhsaa as jh


class _P:
    """The two things `_order` reads off a player, and a pid."""

    def __init__(self, pid, ovr, strv=None):
        self.pid, self._ovr, self._str = pid, ovr, strv if strv is not None else ovr

    def current_overall(self):
        return self._ovr

    def str_value(self):
        return self._str


class _TS:
    def __init__(self, roster, records=None):
        self.roster, self.records = roster, records or {}


def test_a_player_who_has_not_played_is_ranked_at_his_ability():
    """The one that shipped: nobody starts at the bottom for not having started."""
    roster = [_P("a", 51), _P("b", 39), _P("c", 28)]
    # b and c have been dressing all season; a has not played a match.
    ts = _TS(roster, {"b": [12, 8], "c": [10, 10]})
    assert [p.pid for p in jh._order(ts)] == ["a", "b", "c"]


def test_a_bad_start_does_not_bury_a_good_player_for_the_season():
    """0-2 out of the gate cost a 51 OVR his seat permanently, behind team-mates whose
    only advantage was having been picked first."""
    roster = [_P("star", 51), _P("d1", 37), _P("d2", 35), _P("d3", 34)]
    ts = _TS(roster, {"star": [0, 2], "d1": [4, 1], "d2": [4, 2], "d3": [3, 3]})
    assert jh._order(ts)[0].pid == "star"


def test_wins_still_move_the_ladder():
    """The fix must not flatten it into a pure ability sort — a season of winning has
    to be worth real places, or the results never mean anything."""
    roster = [_P("high", 44), _P("low", 38)]
    even = _TS(roster, {"high": [10, 10], "low": [10, 10]})
    assert [p.pid for p in jh._order(even)] == ["high", "low"]
    swung = _TS(roster, {"high": [2, 18], "low": [18, 2]})
    assert [p.pid for p in jh._order(swung)] == ["low", "high"]


def test_a_win_count_never_outranks_a_win_rate():
    """`-w` ranked 5-15 above 4-0 — and doubles credits BOTH partners, so a rotation
    player banked wins faster than a number one playing the toughest opponent."""
    ts = _TS([_P("grinder", 40), _P("perfect", 40)],
             {"grinder": [5, 15], "perfect": [4, 0]})
    assert jh._order(ts)[0].pid == "perfect"


def test_a_short_sample_moves_the_ladder_less_than_a_long_one():
    """`LADDER_PRIOR` is why a 1-2 opening week cannot outrank a whole season."""
    p = _P("x", 40)
    early = jh.ladder_score(p, [0, 3])
    late = jh.ladder_score(p, [0, 24])
    assert 40 > early > late


def test_the_ladder_is_a_bounded_adjustment_not_a_replacement():
    """A perfect record is worth `LADDER_SWING / 2`; nothing can swing further, so a
    genuine gap in ability still decides the lineup."""
    p = _P("x", 40)
    assert jh.ladder_score(p, None) == 40
    assert jh.ladder_score(p, [200, 0]) < 40 + jh.LADDER_SWING / 2
    assert jh.ladder_score(p, [0, 200]) > 40 - jh.LADDER_SWING / 2


# --- over a real season ---------------------------------------------------------

@pytest.fixture(scope="module")
def season():
    """Two districts per classification — the real sim, a tenth the size."""
    real = jh.load_schools

    def small(gender):
        out = []
        for grp in jh.GROUPS:
            keep = sorted({s.district for s in real(gender) if s.group == grp})[:2]
            out += [s for s in real(gender) if s.group == grp and s.district in keep]
        return out

    jh.load_schools = small
    jh._season_cache.clear()
    try:
        yield jh.run_season("boys", 2027, seed=0, salt="")
    finally:
        jh.load_schools = real
        jh._season_cache.clear()


def test_no_program_finishes_the_season_benching_its_best_player(season):
    """The owner's report, as an invariant over the whole association."""
    buried = []
    for t in season["teams"].values():
        best = max(t.roster, key=lambda p: p.current_overall())
        if id(best) not in {id(p) for p in jh._order(t)[:jh.lineup_need("regular")]}:
            buried.append((t.school.name, best.name))
    assert not buried, buried[:5]


def test_the_top_of_a_roster_plays_far_more_than_the_bottom(season):
    """Rotation is meant to hand the ninth seat around, not to hand a starting job to
    the twelfth man. Measured on the old key the two were within a few matches."""
    def played(t, p):
        w, l = t.records.get(p.pid, [0, 0])
        return w + l

    top, bottom = [], []
    for t in season["teams"].values():
        by_ovr = sorted(t.roster, key=lambda p: -p.current_overall())
        if len(by_ovr) < 12:
            continue
        top += [played(t, p) for p in by_ovr[:3]]
        bottom += [played(t, p) for p in by_ovr[-3:]]
    assert top and bottom
    assert sum(top) / len(top) > 3 * (sum(bottom) / len(bottom))


def test_the_bench_still_gets_matches(season):
    """The variation the owner asked for: the reserves are not frozen out either."""
    dressed = 0
    for t in season["teams"].values():
        by_ovr = sorted(t.roster, key=lambda p: -p.current_overall())
        for p in by_ovr[jh.lineup_need("regular"):]:
            w, l = t.records.get(p.pid, [0, 0])
            dressed += (w + l) > 0
    assert dressed > 0


# --- the ORDER OF ABILITY (owner rule 2027-08) — postseason anti-stacking ------------
#
# NFHS-model legality: before a program's first postseason dual its Order of Ability
# is established from the ladder and FROZEN; the nine who dress are its top nine; S1
# and D1 must consume ranks #1-#3; the remaining pairs are ordered on combined ladder
# rank as the anti-stacking BOUNDARY, with the engine's real doubles ability deciding
# only within PAIR_SUM_TOL. See docs/AAR-jhsaa-order-of-ability.md.

import random as _random


def _real_ts(i=0, gender="boys", year=2031):
    # `i` wraps: the module-scoped `season` fixture above patches load_schools to a
    # tenth-size association and tears down at module end, after these tests run.
    pool = jh.load_schools(gender)
    sc = pool[i % len(pool)]
    return jh.TeamSeason(school=sc, roster=jh.build_roster(sc, year))


def test_postseason_lineup_is_legal_under_the_order_of_ability():
    for i in (0, 7, 40, 120, 300):
        ts = _real_ts(i)
        lu = jh._lineup(ts, "sectional", _random.Random(1))
        oo = ts.order_of_ability
        assert oo, "the Order of Ability freezes on first postseason use"
        rank = {pid: k + 1 for k, pid in enumerate(oo)}
        # the nine who dress are the frozen order's top nine
        assert {p.pid for p in lu} == set(oo[:9])
        # S1 + D1 consume ranks #1-#3; nobody top-three appears at D2-D4
        assert {rank[p.pid] for p in lu[:3]} == {1, 2, 3}
        assert all(rank[p.pid] > 3 for p in lu[3:])
        # D2-D4 rank sums respect the anti-stacking boundary
        sums = [rank[lu[k].pid] + rank[lu[k + 1].pid] for k in (3, 5, 7)]
        for hi, lo in zip(sums, sums[1:]):
            assert hi <= lo + jh.PAIR_SUM_TOL, (i, sums)


def test_the_order_of_ability_freezes_for_the_whole_postseason():
    """A mid-bracket hot streak cannot re-rank the roster between rounds: the live
    ladder would move, the frozen postseason lineup must not."""
    ts = _real_ts(3)
    first = [p.pid for p in jh._lineup(ts, "sectional", _random.Random(1))]
    # swing two adjacent dressed players' records as hard as records can swing
    ts.records[ts.order_of_ability[8]] = [30, 0]
    ts.records[ts.order_of_ability[7]] = [0, 30]
    live = [p.pid for p in jh._order(ts)]
    assert live != ts.order_of_ability            # the live ladder DID move...
    again = [p.pid for p in jh._lineup(ts, "zonal", _random.Random(2))]
    assert again == first                          # ...and the lineup did not


def test_the_regular_season_still_runs_on_the_live_ladder():
    """League play is league policy: no freeze, rotation intact — the Order of
    Ability binds championship competition only."""
    ts = _real_ts(5)
    jh._lineup(ts, "regular", _random.Random(4))
    assert not ts.order_of_ability
