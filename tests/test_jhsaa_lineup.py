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
    """A scaled association — the real sim, roughly a tenth the size.

    ‼️ SIZED AGAINST `PROTECTED`, NOT AT A FIXED DISTRICT COUNT (see the same note in
    `test_jhsaa_ladder.py`). Taking the first TWO districts assumed every pair of
    leagues comes to more than the 16 protected seats; leagues run 7-12, so a
    reclassification that puts two small ones at the head of a class's alphabet leaves
    Sectionals ZERO entrants and the ladder is handed an empty field."""
    real = jh.load_schools
    floor = jh.PROTECTED + 8

    def small(gender):
        out = []
        for grp in jh.GROUPS:
            names = sorted({s.district for s in real(gender) if s.group == grp})
            pool, keep = [], set()
            for name in names:
                keep.add(name)
                pool = [s for s in real(gender)
                        if s.group == grp and s.district in keep]
                if len(pool) > floor:
                    break
            out += pool
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


# --- regular-season strategy (owner rule 2027-08) ----------------------------------
#
# League play is free: a program runs one of three explicit coaching strategies —
# maximize (best total doubles_rating over every legal split of #2-#9 into two
# doubles pairs + four singles), balanced (same search, penalised for a lopsided
# D1/D2 split), or traditional (the straight ladder). The strategy is a durable
# program trait; the postseason Order of Ability is untouched by it.

def test_all_three_regular_season_strategies_exist():
    keys = [s.key for s in jh.load_schools("boys")]
    strategies = {jh._coach_strategy(k) for k in keys}
    assert strategies == {"maximize", "balanced", "traditional"}


def test_traditional_strategy_is_the_straight_ladder():
    order = jh._order(_real_ts(0))[:9]
    rank = {p.pid: k + 1 for k, p in enumerate(order)}
    lu = jh._arrange_regular(order, "traditional")
    assert [rank[p.pid] for p in lu] == list(range(1, 10))


def test_maximize_and_balanced_produce_a_legal_permutation_with_top_seed_on_s1():
    order = jh._order(_real_ts(0))[:9]
    ids = {p.pid for p in order}
    for strategy in ("maximize", "balanced"):
        lu = jh._arrange_regular(order, strategy)
        assert {p.pid for p in lu} == ids
        assert lu[0].pid == order[0].pid                       # S1 always the top seed
        assert len(lu) == 9


def test_maximize_never_scores_worse_than_the_straight_ladder():
    """The whole point of the search: 'maximize' picks from every legal split of
    #2-#9, so its D1+D2 total can never be beaten by the one split the straight
    ladder happens to use (D1 = ranks 6+7, D2 = ranks 8+9)."""
    from engine.doubles import doubles_rating
    for i in (0, 5, 12, 27, 41):
        ts = _real_ts(i)
        order = jh._order(ts)[:9]
        if len(order) < 9:
            continue
        eng = {p.pid: p.engine_player() for p in order}
        def total(lu):
            return (doubles_rating(eng[lu[5].pid], eng[lu[6].pid])
                    + doubles_rating(eng[lu[7].pid], eng[lu[8].pid]))
        ladder = jh._arrange_regular(order, "traditional")
        best = jh._arrange_regular(order, "maximize")
        assert total(best) >= total(ladder) - 1e-9


def test_the_pair_boundary_is_adjacent_only_and_tolerance_may_chain():
    """Owner ruling (2027-08): a review proposed enforcing the rank-sum boundary
    across every earlier/later pair, which would outlaw a 15/13/11 chemistry order
    (each step exactly PAIR_SUM_TOL apart, ends 4 apart). The owner kept the chain —
    "chemistry matters to me more than policing pairings at that fidelity" — so the
    boundary binds NEIGHBOURS only. If this test starts failing, someone globalised
    the check; that is a reverted owner decision, not a bug fix."""
    a, b, c = ("hi",), ("mid",), ("lo",)
    sums = {a: 15, b: 13, c: 11}
    rating = {a: 0.9, b: 0.8, c: 0.7}          # chemistry wants 15, 13, 11
    assert jh._order_pairs([c, b, a], sums, rating) == [a, b, c]
    # ...but a NEIGHBOUR gap beyond the tolerance still swaps, chemistry or not
    sums2 = {a: 15, b: 9, c: 11}
    assert jh._order_pairs([c, b, a], sums2, rating)[0] == b
