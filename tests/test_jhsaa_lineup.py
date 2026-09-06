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


def test_the_top_of_a_roster_plays_far_more_than_the_bench(season):
    """Rotation is meant to hand the bench seat around, not hand a starting job to
    a true reserve. 3S/4D dresses eleven of a twelve-man roster (owner rule
    2027-08 — the regular season swapped to the doubles-forward card), so 'the
    bottom of the roster' is no longer a fixed bottom-3: ranks #10-#11 are
    guaranteed S2/S3 starters now, not bench. Compare against whoever actually
    sits beyond `lineup_need('regular')` instead, so this holds under either
    format."""
    def played(t, p):
        w, l = t.records.get(p.pid, [0, 0])
        return w + l

    need = jh.lineup_need("regular")
    top, bench = [], []
    for t in season["teams"].values():
        by_ovr = sorted(t.roster, key=lambda p: -p.current_overall())
        if len(by_ovr) <= need:
            continue
        top += [played(t, p) for p in by_ovr[:3]]
        bench += [played(t, p) for p in by_ovr[need:]]
    assert top and bench
    assert sum(top) / len(top) > 3 * (sum(bench) / len(bench))


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
    """‼️ SHAPE-AWARE, because three shapes now play a road to State: 1S/4D, 1A's
    2S/3D and 8A/9A's 4S/5D. The anti-stacking rule is ONE mechanism at every width
    — the singles seats plus D1 consume the top `n_singles + 2` of the frozen order
    and the pairs below them respect the rank-sum boundary — so the assertion is
    written in those terms rather than in nines."""
    for i in (0, 7, 40, 120, 300):
        ts = _real_ts(i)
        f = jh.dual_format("sectional", ts.school.group)
        need = jh.lineup_need("sectional", ts.school.group)
        if len(ts.roster) < need:
            continue
        lu = jh._lineup(ts, "sectional", _random.Random(1))
        oo = ts.order_of_ability
        assert oo, "the Order of Ability freezes on first postseason use"
        rank = {pid: k + 1 for k, pid in enumerate(oo)}
        top = f.n_singles + 2                       # the singles seats + D1
        # the players who dress are the frozen order's top `need`
        assert {p.pid for p in lu} == set(oo[:need])
        # the singles seats + D1 consume the top pool; nobody in it hides below D1
        assert {rank[p.pid] for p in lu[:top]} == set(range(1, top + 1))
        assert all(rank[p.pid] > top for p in lu[top:])
        # the remaining pairs' rank sums respect the anti-stacking boundary
        starts = range(top, len(lu) - 1, 2)
        sums = [rank[lu[k].pid] + rank[lu[k + 1].pid] for k in starts]
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
# League play is free: a program runs one of three explicit coaching strategies for
# the 3S/4D card. The ALLOCATION is fixed (S1 = #1, doubles pool = #2-#9, S2/S3 =
# #10-#11) — strategy only decides how the 8-player pool pairs into D1-D4: maximize
# (best total doubles_rating over all 105 splits), balanced (same search, penalised
# for a lopsided spread across the four pairs), or traditional (adjacent-ladder
# pairing: D1=#2+#3, D2=#4+#5, D3=#6+#7, D4=#8+#9). The strategy is a durable
# program trait; the postseason Order of Ability is untouched by it.

def test_all_three_regular_season_strategies_exist():
    keys = [s.key for s in jh.load_schools("boys")]
    strategies = {jh._coach_strategy(k) for k in keys}
    assert strategies == {"maximize", "balanced", "traditional"}


def test_traditional_strategy_is_adjacent_ladder_pairing_with_fixed_allocation():
    order = jh._order(_real_ts(0))[:11]
    rank = {p.pid: k + 1 for k, p in enumerate(order)}
    lu = jh._arrange_regular(order, "traditional")
    assert len(lu) == 11
    assert rank[lu[0].pid] == 1                                 # S1 = top seed
    assert {rank[lu[1].pid], rank[lu[2].pid]} == {10, 11}       # S2/S3 = #10-#11
    # D1-D4 = adjacent pairs of the #2-#9 pool, in ladder order
    doubles_ranks = [rank[p.pid] for p in lu[3:11]]
    assert doubles_ranks == [2, 3, 4, 5, 6, 7, 8, 9]


def test_maximize_and_balanced_produce_a_legal_permutation_with_the_fixed_allocation():
    order = jh._order(_real_ts(0))[:11]
    ids = {p.pid for p in order}
    rank = {p.pid: k + 1 for k, p in enumerate(order)}
    for strategy in ("maximize", "balanced"):
        lu = jh._arrange_regular(order, strategy)
        assert {p.pid for p in lu} == ids
        assert len(lu) == 11
        assert lu[0].pid == order[0].pid                        # S1 always the top seed
        assert {rank[lu[1].pid], rank[lu[2].pid]} == {10, 11}   # S2/S3 always #10-#11
        doubles_ranks = {rank[p.pid] for p in lu[3:11]}
        assert doubles_ranks == {2, 3, 4, 5, 6, 7, 8, 9}        # pool is always #2-#9


def test_maximize_never_scores_worse_than_traditional():
    """The whole point of the search: 'maximize' picks from every legal split of
    the fixed #2-#9 pool (105 of them), so its four-pair total can never be beaten
    by the one split the adjacent-ladder pairing happens to use."""
    from engine.doubles import doubles_rating
    for i in (0, 5, 12, 27, 41):
        ts = _real_ts(i)
        order = jh._order(ts)[:11]
        if len(order) < 11:
            continue
        eng = {p.pid: p.engine_player() for p in order}
        def total(lu):
            return sum(doubles_rating(eng[lu[k].pid], eng[lu[k + 1].pid])
                       for k in (3, 5, 7, 9))
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


# --- the 1A 2S/3D postseason pilot (owner rule 2026-08) ----------------------
# See docs/AAR-jhsaa-1a-2s3d-postseason-pilot.md. 1A alone plays 2 singles /
# 3 doubles on its ROAD TO STATE; its TOC entry and every other class stay
# 1S/4D, and 1A's own regular season and showcases are untouched.

def _ts_in_group(group="1A", gender="boys", year=2031):
    for sc in jh.load_schools(gender):
        if sc.group == group:
            ts = jh.TeamSeason(school=sc, roster=jh.build_roster(sc, year))
            if len(ts.roster) >= 9:
                return ts
    return None


def test_only_1a_road_to_state_plays_2s3d():
    """The pilot is scoped THREE ways, and each is a separate way to get it wrong:
    by group (1A only), by phase (road-to-State only, never the TOC), and by
    season half (postseason only — the league card and showcases are untouched)."""
    road = jh.dual_format("state", "1A")
    assert (road.n_singles, road.n_doubles) == (2, 3)
    # the TOC fields every class's champion, so it stays one shape for everyone
    assert jh.dual_format("toc", "1A") == jh.FORMATS["state"]
    for g in ("2A", "5A", "6A", None):
        assert jh.dual_format("state", g) == jh.FORMATS["state"], g
    # 7A/8A/9A are the OTHER pilot (owner rule 2070; 7A joined 2026-09) — not this one
    for g in jh.WIDE_GROUPS:
        assert jh.dual_format("state", g) == jh.FORMATS["state_4s5d"], g
    # untouched outside the postseason, 1A included
    assert jh.dual_format("regular", "1A") == jh.FORMATS["regular"]
    # a showcase rehearses the class's OWN state format (owner rule 2026-09)
    assert jh.dual_format("showcase_pod", "1A") == jh.FORMATS["state_1a"]
    assert jh.dual_format("showcase_tiered", "5A") == jh.FORMATS["state"]
    assert jh.dual_format("early", "1A") == jh.FORMATS["early"]
    # ...and the roster the shape demands follows it
    assert jh.lineup_need("state", "1A") == 8
    assert jh.lineup_need("toc", "1A") == 9
    assert jh.lineup_need("state", "2A") == 9


def test_the_1a_postseason_lineup_is_legal_under_the_order_of_ability():
    """The same anti-stacking mechanism as 1S/4D's, one seat wider: ranks #1-#4
    are consumed by S1/S2/D1 (nobody from the top four hides at D2-D3), and the
    remaining pairs respect the rank-sum boundary."""
    ts = _ts_in_group("1A")
    if ts is None:
        pytest.skip("no 1A program in the patched association")
    lu = jh._lineup(ts, "sectional", _random.Random(1))
    oo = ts.order_of_ability
    assert oo, "the Order of Ability still freezes on first postseason use"
    rank = {pid: k + 1 for k, pid in enumerate(oo)}
    assert len(lu) == 8, "2S/3D dresses eight, one fewer than 1S/4D"
    assert {p.pid for p in lu} == set(oo[:8])
    # S1 + S2 + D1 consume ranks #1-#4 — the top-four pool, not a pinned #1
    assert {rank[p.pid] for p in lu[:4]} == {1, 2, 3, 4}
    assert all(rank[p.pid] > 4 for p in lu[4:])
    # the two singles seats are ordered by ladder rank between themselves
    assert rank[lu[0].pid] < rank[lu[1].pid]
    sums = [rank[lu[k].pid] + rank[lu[k + 1].pid] for k in (4, 6)]
    for hi, lo in zip(sums, sums[1:]):
        assert hi <= lo + jh.PAIR_SUM_TOL, sums


def test_a_1a_program_reads_one_frozen_order_at_two_slice_lengths():
    """1A's road dresses eight and its TOC entry nine — off the SAME frozen
    Order of Ability. Freezing a fixed-length slice instead of the full ladder
    would need a second freeze for the TOC, which is exactly the mid-postseason
    re-rank the anti-stacking rule exists to forbid."""
    ts = _ts_in_group("1A")
    if ts is None:
        pytest.skip("no 1A program in the patched association")
    road = jh._lineup(ts, "sectional", _random.Random(1))
    frozen = list(ts.order_of_ability)
    toc = jh._lineup(ts, "toc", _random.Random(1))
    assert ts.order_of_ability == frozen, "the TOC must not re-freeze the order"
    assert len(road) == 8 and len(toc) == 9
    assert {p.pid for p in toc} == set(frozen[:9])


# --- SIBLINGS PARTNER AUTOMATICALLY (owner rule 2026-09) ----------------------
#
# `FAMILY_CHEMISTRY` alone made two siblings partner when the ratings were already
# close and not otherwise, so whether a coach's brothers were together varied dual to
# dual and could only be discovered by opening every dual of every program. Owner:
# "the sibling thing on the same team should be paired automatically because i can't
# track them all the time and it's easier to see it that way." The bonus still decides
# which COURT the pair takes; that they ARE a pair is no longer a rating question.


def _sibs(order, i, j):
    """A sibling map (`TeamSeason.sibling_ids`'s shape) tying two ladder positions."""
    a, b = order[i].pid, order[j].pid
    return {a: {b}, b: {a}}


def _partners(lineup, first):
    """The doubles pairs of a slot-ordered lineup, `first` being D1a's index."""
    return [frozenset((lineup[k].pid, lineup[k + 1].pid))
            for k in range(first, len(lineup), 2)]


def test_siblings_partner_in_every_regular_season_strategy():
    """All three, including `traditional` — the swap is applied after the strategy has
    paired the pool, so each keeps its own one decision and none of them can split a
    pair. #2 and #9 are the two ends of the doubles pool: no strategy pairs them by
    accident, so this cannot pass for the wrong reason."""
    ts = _real_ts(5)
    order = jh._order(ts)[:11]
    assert len(order) == 11
    for strategy in jh._STRATEGIES:
        lu = jh._arrange_regular(order, strategy, _sibs(order, 1, 8))
        assert len(lu) == 11 and len({p.pid for p in lu}) == 11, strategy
        assert frozenset((order[1].pid, order[8].pid)) in _partners(lu, 3), strategy
        # ...and the fixed allocation is untouched: S1 is still the top seed and the
        # S2/S3 seats are still #10-#11.
        assert lu[0].pid == order[0].pid
        assert {lu[1].pid, lu[2].pid} == {order[9].pid, order[10].pid}


def test_siblings_are_never_forced_across_a_boundary_the_format_fixes():
    """A pair straddling S1 and the doubles pool cannot be honoured — the 3S/4D
    allocation is fixed and the anti-stacking rule outranks this. The lineup must come
    back legal and unremarkable, not rearranged to put them together."""
    ts = _real_ts(9)
    order = jh._order(ts)[:11]
    lu = jh._arrange_regular(order, "maximize", _sibs(order, 0, 4))
    assert lu[0].pid == order[0].pid                       # #1 still plays S1
    assert len({p.pid for p in lu}) == 11


def test_siblings_partner_in_the_postseason_lineup_and_it_stays_legal():
    """The 1S/4D card. A pair inside #4-#9 is a CONSTRAINT on the partition search,
    not a bonus inside it — and the anti-stacking rank-sum boundary still binds after,
    because the search only ever chose among LEGAL partitions."""
    for i, (a, b) in ((2, (3, 8)), (11, (4, 7)), (30, (5, 6))):
        ts = _real_ts(i)
        nine = jh._order(ts)[:9]
        if len(nine) < 9:
            continue
        rank = {p.pid: k + 1 for k, p in enumerate(nine)}
        lu = jh._arrange_state(nine, _sibs(nine, a, b))
        assert frozenset((nine[a].pid, nine[b].pid)) in _partners(lu, 3), (i, a, b)
        assert {rank[p.pid] for p in lu[:3]} == {1, 2, 3}       # S1 + D1 = #1-#3
        sums = [rank[lu[k].pid] + rank[lu[k + 1].pid] for k in (3, 5, 7)]
        for hi, lo in zip(sums, sums[1:]):
            assert hi <= lo + jh.PAIR_SUM_TOL, (i, sums)


def test_two_siblings_in_the_top_three_are_d1_and_the_third_plays_s1():
    """There is nothing left to choose: S1 + D1 consume ranks #1-#3, so if two of them
    are siblings the third takes the singles seat whatever the coach's search wanted."""
    ts = _real_ts(14)
    nine = jh._order(ts)[:9]
    if len(nine) >= 9:
        lu = jh._arrange_state(nine, _sibs(nine, 0, 1))
        assert lu[0].pid == nine[2].pid
        assert {lu[1].pid, lu[2].pid} == {nine[0].pid, nine[1].pid}


def test_siblings_partner_in_the_1a_pilot_lineup():
    """2S/3D. A pair inside the top four is either D1 or both at singles — never split
    across the two, which would be the one arrangement that has them on court in
    different roles for no reason."""
    ts = _real_ts(21)
    eight = jh._order(ts)[:8]
    if len(eight) < 8:
        return
    lu = jh._arrange_1a_postseason(eight, _sibs(eight, 4, 7))
    assert frozenset((eight[4].pid, eight[7].pid)) in _partners(lu, 2)
    lu = jh._arrange_1a_postseason(eight, _sibs(eight, 0, 2))
    top = frozenset((eight[0].pid, eight[2].pid))
    assert top == frozenset((lu[0].pid, lu[1].pid)) or top in _partners(lu, 2)


def test_three_siblings_on_one_roster_pair_the_higher_two():
    """Three cannot all partner, so the ladder decides and the third plays on — the
    lineup must still be a legal one with nine distinct people in it."""
    ts = _real_ts(17)
    nine = jh._order(ts)[:9]
    if len(nine) < 9:
        return
    a, b, c = (nine[3].pid, nine[5].pid, nine[7].pid)
    sibs = {a: {b, c}, b: {a, c}, c: {a, b}}
    lu = jh._arrange_state(nine, sibs)
    assert len({p.pid for p in lu}) == 9
    assert frozenset((a, b)) in _partners(lu, 3), [sorted(p) for p in _partners(lu, 3)]


def test_siblings_partner_in_the_early_window_too():
    """‼️ The early 5S/2D window had NO arranger at all — its allocation is fixed by
    the shape, so `_lineup` handed back the plain ladder and the doubles pool paired
    adjacently. Siblings at #6 and #8 therefore drew different partners in every early
    dual while partnering everywhere else in varsity play, which is the "sometimes"
    the rule exists to remove."""
    ts = _real_ts(8)
    need = jh.lineup_need(jh.EARLY_FORMAT_PHASE)
    order = jh._order(ts)[:need]
    if len(order) < need:
        return
    n_s = jh.dual_format(jh.EARLY_FORMAT_PHASE).n_singles
    lu = jh._arrange_early(order, _sibs(order, n_s, n_s + 2))   # the two pools' ends
    assert frozenset((order[n_s].pid, order[n_s + 2].pid)) in _partners(lu, n_s)
    assert [p.pid for p in lu[:n_s]] == [p.pid for p in order[:n_s]]   # singles fixed
    assert len({p.pid for p in lu}) == need
    # No siblings, and no pair to force: the lineup is the ladder, byte for byte.
    assert jh._arrange_early(order, {}) == order


def test_the_early_window_lineup_goes_through_the_arranger():
    """The wiring, not just the helper — `_lineup` returned `nine` unarranged for this
    phase and a fix that only adds the function changes nothing."""
    ts = _real_ts(8)
    # ‼️ Shape-aware: 8A/9A play the early window at 4S/5D (owner rule 2070), so the
    # window's width and singles count are read at the PROGRAM's group. Taken bare,
    # the pool indices below are the wrong ones and the sibling check quietly never
    # fires — the test then measures nothing while looking like it passed.
    g = ts.school.group
    need = jh.lineup_need(jh.EARLY_FORMAT_PHASE, g)
    order = jh._order(ts)[:need]
    if len(order) < need:
        return
    n_s = jh.dual_format(jh.EARLY_FORMAT_PHASE, g).n_singles
    ts.sibling_ids = _sibs(order, n_s, n_s + 2)
    seen = set()
    for seed in range(25):
        lu = jh._lineup(ts, jh.EARLY_FORMAT_PHASE, _random.Random(seed), None, g)
        pool = {p.pid for p in lu[n_s:need]}
        if {order[n_s].pid, order[n_s + 2].pid} <= pool:
            seen.add(frozenset((order[n_s].pid, order[n_s + 2].pid))
                     in _partners(lu, n_s))
    assert seen == {True}, "an early dual dressed the siblings apart"


# --- the 8A/9A 4S/5D postseason pilot (owner rule 2070) ----------------------
# The association's two deepest classifications play NINE points on their road to
# State (and in their early non-district window). Scoped the same three ways as
# 1A's: by group, by phase (never the TOC), and by season half (the league card and
# the showcases are untouched) — plus one the 1A pilot never had to think about,
# since it is the first pilot to reach a phase where a dual can cross groups.

def test_only_8a_9a_play_4s5d_and_only_on_the_road_and_in_the_early_window():
    for g in jh.WIDE_GROUPS:
        for phase in ("sectional", "zonal", "conference", "state_special", "state",
                      jh.EARLY_FORMAT_PHASE):
            f = jh.dual_format(phase, g)
            assert (f.n_singles, f.n_doubles) == (4, 5), (g, phase)
            assert jh.lineup_need(phase, g) == 14, (g, phase)
        # the TOC fields every class's champion, so an 8A/9A champion reverts to 1S/4D
        assert jh.dual_format("toc", g) == jh.FORMATS["state"]
        assert jh.lineup_need("toc", g) == 9
        # the league season and the showcases are untouched
        assert jh.dual_format("regular", g) == jh.FORMATS["regular"]
        for sh in jh.SHOWCASE:
            assert jh.dual_format(sh, g) == jh.FORMATS["state"]
    # and nobody else moved
    for g in ("1A", "2A", "5A", "6A", None):
        assert jh.dual_format(jh.EARLY_FORMAT_PHASE, g) == jh.FORMATS["early"], g


def test_every_shape_but_group_2s_is_odd_and_cannot_tie():
    """Every varsity dual shape has an odd court count — a property to keep, not a
    coincidence — with ONE exception the association wrote a rule for: Group 2's
    3S/3D postseason (JHSAA rule 2026-09), whose 3-3 is settled by the deciders
    (`_deciding_tiebreaks`). Nothing else may go even without one."""
    for name, f in jh.FORMATS.items():
        if name == "state_3s3d":
            assert (f.n_singles + f.n_doubles) == 6
            continue
        assert (f.n_singles + f.n_doubles) % 2 == 1, name


# --- Group 2's 3S/3D postseason and the deciders (JHSAA rule 2026-09) ----------

def test_only_group_2s_road_to_state_plays_3s3d():
    """Scoped the 1A pilot's three ways: by group (Group 2 only), by phase (the
    road, never the TOC), by season half (league season, early window and
    showcases untouched)."""
    road = jh.dual_format("state", "Group 2")
    assert (road.n_singles, road.n_doubles) == (3, 3)
    for phase in ("sectional", "zonal", "conference", "state_special", "state"):
        assert jh.dual_format(phase, "Group 2") is jh.FORMATS["state_3s3d"], phase
        assert jh.lineup_need(phase, "Group 2") == 9
    assert jh.dual_format("toc", "Group 2") == jh.FORMATS["state"]
    assert jh.dual_format("regular", "Group 2") == jh.FORMATS["regular"]
    assert jh.dual_format(jh.EARLY_FORMAT_PHASE, "Group 2") == jh.FORMATS["early"]
    # the showcases rehearse the class's own state format (owner rule 2026-09), so
    # a Group 2 showcase is 3S/3D and can be drawn — regular season, JV ladder
    for sh in jh.SHOWCASE:
        assert jh.dual_format(sh, "Group 2") is jh.FORMATS["state_3s3d"]
        assert jh.lineup_need(sh, "Group 2") == 9
    for g in ("Group 1", "Group 3", "2A", "6A", None):
        assert jh.dual_format("state", g) is not jh.FORMATS["state_3s3d"], g
    # the flight table already prices S1-S3 / D1-D3
    w = jh.flight_weights("state", "Group 2")
    assert all(s in w for s in ("S1", "S2", "S3", "D1", "D2", "D3"))


def test_the_3s3d_postseason_lineup_is_legal_under_the_order_of_ability():
    """`_arrange_wide` at three singles: ranks #1-#5 are consumed by S1-S3 and D1,
    the two pairs below respect the rank-sum boundary, nine dress."""
    ts = _ts_in_group("Group 2")
    if ts is None or len(ts.roster) < 9:
        pytest.skip("no Group 2 program in the patched association")
    lu = jh._lineup(ts, "sectional", _random.Random(1))
    oo = ts.order_of_ability
    rank = {pid: k + 1 for k, pid in enumerate(oo)}
    assert len(lu) == 9
    assert {p.pid for p in lu} == set(oo[:9])
    assert {rank[p.pid] for p in lu[:5]} == {1, 2, 3, 4, 5}
    assert [rank[p.pid] for p in lu[:3]] == sorted(rank[p.pid] for p in lu[:3])
    s1 = rank[lu[5].pid] + rank[lu[6].pid]
    s2 = rank[lu[7].pid] + rank[lu[8].pid]
    assert s1 <= s2 + jh.PAIR_SUM_TOL


def _level_group2_dual(seed_start=1, tries=4000):
    """Two Group 2 programs and a seed on which their `state`-phase dual finishes
    3-3 — found by searching seeds, since the deciders only fire on a level dual."""
    schools = [s for s in jh.load_schools("girls") if s.group == "Group 2"][:2]
    if len(schools) < 2:
        return None
    teams = jh.district_teams(schools, 0, "g2tb")
    a, b = teams
    for seed in range(seed_start, seed_start + tries):
        for t in (a, b):
            t.schedule.clear(); t.records.clear(); t.matches.clear()
            t.pair_counts.clear()
            t.wins = t.losses = t.ties = 0
        res = jh.play_dual(a, b, seed=seed, phase="state")
        if res.home_points == res.away_points:
            return a, b, res, seed
    return None


def test_a_level_group_2_postseason_dual_is_decided_on_three_tiebreakers():
    """A 3-3 in Group 2's road is settled by THREE CONCURRENT 10-point tiebreakers
    at S1, D1 and D2, best two of three, by the players who played those flights;
    the winner is credited a W (never a tie), the deciders ride their own
    `tiebreak` key, and nothing about them reaches `lines` or a player record."""
    found = _level_group2_dual()
    if found is None:
        pytest.skip("no level Group 2 dual found in the seed window")
    a, b, res, seed = found
    row_a, row_b = a.schedule[-1], b.schedule[-1]
    tb = row_a["tiebreak"]
    assert row_a["pf"] == row_a["pa"] == 3
    assert [t["slot"] for t in tb] == list(jh.DECIDER_FLIGHTS) == ["S1", "D1", "D2"]
    home_tb = sum(1 for t in tb if t["home_won"])
    assert (res.winner == 0) == (home_tb >= 2)
    assert row_a["won"] != row_b["won"] and not row_a["tied"] and not row_b["tied"]
    assert row_a["won"] == (res.winner == 0)
    assert a.wins + b.wins == 1 and a.ties == b.ties == 0
    # the deciders are played by the flight's own players, and print real points
    lines = {ln["slot"]: ln for ln in row_a["lines"]}
    for t in tb:
        assert t["home"] == lines[t["slot"]]["home"]
        assert t["away"] == lines[t["slot"]]["away"]
        hi, lo = (int(x) for x in t["score"].split("-"))
        assert max(hi, lo) == jh.DECIDER_TARGET and min(hi, lo) <= jh.DECIDER_TARGET - 2
    # a decider is not a match: six lines, and exactly nine player credits (three
    # singles players + three pairs) — a decider adds none
    assert len(row_a["lines"]) == 6
    assert sum(sum(v) for v in a.records.values()) == 9
    # ...and the same seed reproduces the same deciders
    a.schedule.clear(); b.schedule.clear()
    res2 = jh.play_dual(a, b, seed=seed, phase="state")
    assert res2.winner == res.winner and a.schedule[-1]["tiebreak"] == tb


def test_the_deciders_are_best_two_of_three_and_named_by_flight():
    """The fold itself, on engine players: the side that takes two of the three
    advances, whatever the third does."""
    from engine.dual import Team
    from engine import Player

    def flat(name, v):
        return Player(name=name, serve_power=v, serve_placement=v, movement=v,
                      forehand=v, mental=v, return_game=v, backhand=v,
                      stamina=v, consistency=v)
    hp = [flat(f"h{i}", 0.75) for i in range(9)]
    ap = [flat(f"a{i}", 0.25) for i in range(9)]
    home = Team(name="H", singles=hp[:3], doubles=[(0, 1), (2, 3), (4, 5)],
                doubles_players=hp[3:])
    away = Team(name="A", singles=ap[:3], doubles=[(0, 1), (2, 3), (4, 5)],
                doubles_players=ap[3:])

    class _Pl:
        def __init__(self, name):
            self.name = name
    la = [_Pl(f"h{i}") for i in range(9)]
    lb = [_Pl(f"a{i}") for i in range(9)]
    shape = jh.FORMATS["state_3s3d"]
    wins = 0
    for seed in range(40):
        tb, w = jh._deciding_tiebreaks(home, away, la, lb, "state", shape, seed)
        assert [t["slot"] for t in tb] == ["S1", "D1", "D2"]
        assert tb[0]["home"] == ["h0"] and tb[1]["home"] == ["h3", "h4"] \
            and tb[2]["home"] == ["h5", "h6"]
        assert w == (0 if sum(t["home_won"] for t in tb) >= 2 else 1)
        wins += w == 0
    assert wins >= 30, "a clear favourite wins the deciders most of the time"


def test_a_dual_across_classifications_plays_ONE_shape_AND_IT_IS_THE_WIDER():
    """‼️ The early non-district window pairs a program with one in its own
    classification OR one apart, so an 8A-vs-7A early dual has two sides wanting
    different cards. A dual has one card, and it is the WIDER one (owner rule
    2070): every program here carries the bench for nine courts, so the 7A side
    plays 4S/5D rather than dragging the dual down to 5S/2D. Read off the home side
    alone instead, the away side would dress for a card it is not playing and
    `_squad`/`_slot_players` would WRAP — the same player on two courts, raising
    nothing."""
    ep = jh.EARLY_FORMAT_PHASE
    wide = jh.FORMATS["state_4s5d"]
    for a, b in (("8A", "9A"), ("9A", "9A"), ("8A", "7A"), ("7A", "8A")):
        assert jh.dual_format(ep, jh.shape_group(ep, a, b)) == wide, (a, b)
    # two narrow sides still play the narrow card
    # 7A is in the pilot now (owner rule 2026-09), so a 7A-vs-6A early dual is the
    # crossing case and plays wide; two genuinely narrow sides still play narrow
    assert jh.dual_format(ep, jh.shape_group(ep, "7A", "6A")) == wide
    for a, b in (("6A", "5A"), ("1A", "2A")):
        assert jh.dual_format(ep, jh.shape_group(ep, a, b)) == jh.FORMATS["early"], (a, b)
    # a postseason bracket never crosses groups, so the sides always agree there
    assert jh.dual_format("state", jh.shape_group("state", "8A", "8A")) == wide
    # ...and the roster the wider card needs is comfortably inside every band
    for cls, (lo, _hi) in jh.ROSTER_SIZE_BAND_BY_CLASS.items():
        if cls in ("8A", "9A", "7A", "6A"):
            assert lo >= jh.lineup_need(ep, "8A"), cls


def test_the_4s5d_postseason_lineup_is_legal_under_the_order_of_ability():
    """The same anti-stacking mechanism, three seats wider: ranks #1-#6 are consumed
    by S1-S4 and D1 (nobody from the top six hides at D2-D5), and the pairs below
    respect the rank-sum boundary. The best player is NOT pinned to S1."""
    ts = _ts_in_group("8A") or _ts_in_group("9A")
    if ts is None or len(ts.roster) < 14:
        pytest.skip("no 8A/9A program deep enough in the patched association")
    lu = jh._lineup(ts, "sectional", _random.Random(1))
    oo = ts.order_of_ability
    rank = {pid: k + 1 for k, pid in enumerate(oo)}
    assert len(lu) == 14, "4S/5D dresses fourteen"
    assert {p.pid for p in lu} == set(oo[:14])
    assert {rank[p.pid] for p in lu[:6]} == {1, 2, 3, 4, 5, 6}
    assert all(rank[p.pid] > 6 for p in lu[6:])
    # the four singles seats are ordered by ladder rank between themselves
    assert [rank[p.pid] for p in lu[:4]] == sorted(rank[p.pid] for p in lu[:4])
    sums = [rank[lu[k].pid] + rank[lu[k + 1].pid] for k in (6, 8, 10, 12)]
    for hi, lo in zip(sums, sums[1:]):
        assert hi <= lo + jh.PAIR_SUM_TOL, sums


def test_the_4s5d_dual_is_rated_on_the_associations_own_weight_table():
    """‼️ The same flight NAME is worth different amounts in different shapes (S1 is
    2.00 on the nine-court card and 1.00 everywhere else), so the table is resolved
    per DUAL and a 4S/5D dual carries its own — `rating._flight_score` normalises by
    the weight contested, which is what lets both live in one TOSS graph. D5 must be
    weighted at all: an unrecognised flight RAISES, by design."""
    from app import rating as rt
    w = jh.flight_weights("state", "8A")
    assert w is jh.FLIGHT_WEIGHTS_4S5D
    assert max(w.values()) == 2.00 and w["D5"] == 0.10
    assert w["S4"] > w["D5"] and w["D4"] > w["D5"]
    # a class's LEAGUE season is 3S/4D whatever its playoff shape, and rates on the
    # ordinary table — the resolution is on the SHAPE, not the classification
    assert jh.flight_weights("regular", "8A") is jh.FLIGHT_WEIGHTS
    lines = [{"slot": s, "home_won": True, "home_games": 12, "away_games": 4}
             for s in ("S1", "S2", "S3", "S4", "D1", "D2", "D3", "D4", "D5")]
    assert rt._flight_score(lines, "home", w) == 1.0


def test_the_jv_playoff_cut_moves_but_the_jv_SEASON_cut_does_not():
    """8A/9A dress fourteen in the varsity playoffs, so their JV championship field
    freezes below that (#15 down) — while the JV LEAGUE season's own cut stays #12
    down for every classification, 8A/9A included. The overlap is deliberate: a
    player may dress for both playoff fields."""
    assert jh.lineup_need("regular", "8A") == 11        # the JV season's cut
    for g in jh.WIDE_GROUPS:
        assert jh.jv_postseason_cut(g) == 14
    for g in ("1A", "5A", "6A", None):
        assert jh.jv_postseason_cut(g) == 11, g

# --- PARTNER CONTINUITY (owner rule 2026-09) ----------------------------------
#
# "when partners work together they should be more likely to stay together" —
# within ONE season only (the evidence lives on `TeamSeason.pair_counts`, which
# lives one season), and never at the team's expense: an ESTABLISHED pair (6+
# doubles lines together at a non-losing share) rides the sibling rule's swap in
# the direct arrangers, siblings outranking it; the searching postseason
# arrangers take it as a capped chemistry bonus instead, under the same
# anti-stacking boundary as everything else.


def _pc(order, i, j, n=8, w=5):
    """A `TeamSeason.pair_counts` map establishing ladder positions i and j."""
    return {tuple(sorted((order[i].pid, order[j].pid))): [n, w]}


def test_an_established_pair_stays_together_in_every_regular_season_strategy():
    """#2 and #9 are the two ends of the doubles pool: no strategy pairs them by
    accident, so this cannot pass for the wrong reason."""
    ts = _real_ts(5)
    order = jh._order(ts)[:11]
    assert len(order) == 11
    for strategy in jh._STRATEGIES:
        lu = jh._arrange_regular(order, strategy, {}, _pc(order, 1, 8))
        assert len(lu) == 11 and len({p.pid for p in lu}) == 11, strategy
        assert frozenset((order[1].pid, order[8].pid)) in _partners(lu, 3), strategy
        # the fixed allocation is untouched
        assert lu[0].pid == order[0].pid
        assert {lu[1].pid, lu[2].pid} == {order[9].pid, order[10].pid}


def test_a_pair_losing_together_is_not_protected():
    """The coach breaks up a losing pair — which is the realism, and what keeps
    the mandate from costing the team. 2-6 together is not an established pair."""
    ts = _real_ts(5)
    order = jh._order(ts)[:11]
    lu = jh._arrange_regular(order, "traditional", {}, _pc(order, 1, 8, n=8, w=2))
    assert frozenset((order[1].pid, order[8].pid)) not in _partners(lu, 3)


def test_a_short_history_is_not_an_established_pair():
    ts = _real_ts(5)
    order = jh._order(ts)[:11]
    lu = jh._arrange_regular(order, "traditional", {},
                             _pc(order, 1, 8, n=jh.PARTNER_ESTABLISHED_MIN - 1, w=5))
    assert frozenset((order[1].pid, order[8].pid)) not in _partners(lu, 3)


def test_siblings_outrank_partner_continuity():
    """Both claims on one player: the sibling pair holds, the established partner
    yields — and the lineup stays a legal permutation."""
    ts = _real_ts(5)
    order = jh._order(ts)[:11]
    lu = jh._arrange_regular(order, "traditional", _sibs(order, 1, 8),
                             _pc(order, 1, 6, n=20, w=15))
    assert frozenset((order[1].pid, order[8].pid)) in _partners(lu, 3)
    assert len({p.pid for p in lu}) == 11


def test_partner_chemistry_is_capped_and_evidence_weighted():
    """Zero history is zero bonus; the bonus grows with lines together and never
    reaches `PARTNER_CHEMISTRY` — the FAMILY_CHEMISTRY scale, a tiebreak only."""
    pc = {("a", "b"): [jh.PARTNER_PRIOR, jh.PARTNER_PRIOR]}
    assert jh.partner_chemistry({}, "a", "b") == 0.0
    assert jh.partner_chemistry(pc, "x", "y") == 0.0
    half = jh.partner_chemistry(pc, "a", "b")
    assert abs(half - jh.PARTNER_CHEMISTRY / 2) < 1e-12
    lots = jh.partner_chemistry({("a", "b"): [200, 120]}, "b", "a")  # symmetric
    assert half < lots < jh.PARTNER_CHEMISTRY


def test_the_postseason_arrangement_stays_legal_under_the_chemistry_bonus():
    """The searching arrangers take continuity as a bonus, never a mandate — the
    anti-stacking boundary still binds and S1+D1 still consume ranks #1-#3."""
    ts = _real_ts(11)
    nine = jh._order(ts)[:9]
    if len(nine) < 9:
        pytest.skip("thin roster in the patched association")
    rank = {p.pid: k + 1 for k, p in enumerate(nine)}
    lu = jh._arrange_state(nine, {}, _pc(nine, 4, 7, n=30, w=20))
    assert len({p.pid for p in lu}) == 9
    assert {rank[p.pid] for p in lu[:3]} == {1, 2, 3}
    sums = [rank[lu[k].pid] + rank[lu[k + 1].pid] for k in (3, 5, 7)]
    for hi, lo in zip(sums, sums[1:]):
        assert hi <= lo + jh.PAIR_SUM_TOL, sums
    # and with no history at all, the arrangement is byte-identical to before
    assert ([p.pid for p in jh._arrange_state(nine, {})]
            == [p.pid for p in jh._arrange_state(nine, {}, {})])


def test_a_doubles_line_records_the_pair_and_a_singles_line_does_not():
    ts = jh.TeamSeason(school=None, roster=[])
    lu = [_P(f"p{k}", 40) for k in range(11)]
    f = jh.FORMATS["regular"]
    jh._credit(ts, lu, "regular", "D1", True, fmt=f)
    jh._credit(ts, lu, "regular", "D1", False, fmt=f)
    jh._credit(ts, lu, "regular", "S1", True, fmt=f)
    key = tuple(sorted((lu[3].pid, lu[4].pid)))
    assert ts.pair_counts == {key: [2, 1]}
