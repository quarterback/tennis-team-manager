"""The Epiregional — the Zonal champions' play-in for the State draw's bye lines
(owner rule 2026-09) — and the merit seeding it feeds.

Everything here runs on REAL rosters (`district_teams` over the girls' list) but
no played season: the round and the seeding are pure functions of a field, a
rating and a seed, so they are exercised directly, at every field size, with an
explicit EIGHT-champion entry list. A scaled season fixture will often crown
fewer than eight and skip this path while every test stays green — that is how
the JV State play-in hid a bug until a full-sized save — so the eight are built
by hand here and the archived-season file (`test_jhsaa_ladder.py`) covers the
wiring.
"""
from types import SimpleNamespace

import pytest

from app import jhsaa as jh
from app import regions
from app import world as wd


@pytest.fixture(scope="module")
def _teams():
    return jh.district_teams(jh.load_schools("girls")[:40], 2027, "")


@pytest.fixture
def teams(_teams):
    """Fresh season-shaped records per test — `play_dual` CREDITS a result to the
    team's record, so a play-in changes the win percentage the seeding then reads
    (that is the design: the State draw is seeded after the play-in, on the
    record that includes it). A test that pre-computes an expected order must do
    so BEFORE playing, and must not inherit another test's results."""
    for i, t in enumerate(_teams):
        t.wins, t.losses = 30 - (i * 5) // 8, (i * 5) // 8 + 2
        t.schedule.clear()
    return _teams


def _power(teams, pis=None):
    """A `power` map in `rating.RatingLine`'s one relevant field (`pi_raw`)."""
    return {t.school.name: SimpleNamespace(pi_raw=(pis[i] if pis else 1.0 - i * 0.02))
            for i, t in enumerate(teams)}


# --- the play-in ---------------------------------------------------------------------

def test_the_play_in_takes_eight_and_returns_exactly_four_winners(teams):
    champs = teams[:8]
    names = jh.epiregional_names("girls", 2068, "7A", "")
    arc, winners, losers = jh.run_epiregional(champs, _power(teams), {}, names, seed=5)
    assert len(arc["field"]) == 8 and set(arc["field"]) == {t.school.name for t in champs}
    assert len(arc["rounds"]) == 1 and len(arc["rounds"][0]) == 4
    assert len(winners) == 4 and len(losers) == 4
    assert {t.school.name for t in winners} | {t.school.name for t in losers} \
        == set(arc["field"])
    assert arc["survivors"] == [t.school.name for t in winners]
    assert arc["round_names"] == [jh.EPIREGIONAL_NAME]


def test_the_play_in_pairs_1v8_on_atr_and_the_higher_seed_hosts(teams):
    champs = teams[:8]
    power = _power(teams)
    # the expected order is taken BEFORE the round: the duals credit records
    satr = jh.seed_atr(champs, power)
    order = sorted(champs, key=jh._seed_atr_key(satr))
    names = [t.school.name for t in order]
    arc, _w, _l = jh.run_epiregional(champs, power, {}, ["A", "B", "C", "D"], seed=5)
    assert arc["field"] == names                       # the seed order among the eight
    pairs = [(gm["home"], gm["away"]) for gm in arc["rounds"][0]]
    assert pairs == [(names[0], names[7]), (names[1], names[6]),
                     (names[2], names[5]), (names[3], names[4])]


def test_each_dual_is_a_named_unit_off_the_ncaa_region_pool(teams):
    names = jh.epiregional_names("girls", 2068, "7A", "")
    assert len(names) == 4 and len(set(names)) == 4
    assert set(names) <= set(regions.LEAGUE_NAMES)
    # stable across calls (an archived unit must reproduce after a restart)...
    assert names == jh.epiregional_names("girls", 2068, "7A", "")
    # ...and rotating by year and by class
    assert names != jh.epiregional_names("girls", 2069, "7A", "")
    assert names != jh.epiregional_names("girls", 2068, "6A", "")
    arc, _w, _l = jh.run_epiregional(teams[:8], _power(teams), {}, names, seed=5)
    assert [gm["unit"] for gm in arc["rounds"][0]] == [f"{n} Epiregional" for n in names]
    # the honours chip keeps the region name whole
    assert wd._unit_honour(f"{names[0]} Epiregional") == f"{names[0]} Epiregional"


def test_the_play_in_never_replays_a_road_opponent(teams):
    """Impossible by construction on the real ladder (two Zonal champions came out
    of different Zonals), stated in code all the same: a prestate pairing between
    the natural 1v8 opponents is swapped away."""
    champs = teams[:8]
    power = _power(teams)
    satr = jh.seed_atr(champs, power)
    order = [t.school.name for t in sorted(champs, key=jh._seed_atr_key(satr))]
    prestate = {"rounds": [[{"home": order[0], "away": order[7], "winner": order[0]}]]}
    arc, _w, _l = jh.run_epiregional(champs, power, prestate, ["A", "B", "C", "D"], seed=5)
    for gm in arc["rounds"][0]:
        assert {gm["home"], gm["away"]} != {order[0], order[7]}
    # every champion still plays exactly once
    played = [n for gm in arc["rounds"][0] for n in (gm["home"], gm["away"])]
    assert sorted(played) == sorted(order)


def test_the_play_in_is_deterministic(teams):
    """Same seed, same field, same INPUT STATE → the same round. The round credits
    its results to the teams, so the second run takes a copy of the field as it
    stood before the first."""
    import copy
    power = _power(teams)
    a = jh.run_epiregional(copy.deepcopy(teams[:8]), power, {}, ["A", "B", "C", "D"],
                           seed=77)
    b = jh.run_epiregional(copy.deepcopy(teams[:8]), power, {}, ["A", "B", "C", "D"],
                           seed=77)
    assert a[0] == b[0]


# --- the seeding ATR -----------------------------------------------------------------

def test_atr_is_standardised_within_the_field_it_is_given(teams):
    """The z-scores are taken over the list passed in — a class-gender field —
    never over the gender. The SAME team gets a different number in a different
    field, and the ordering inside one field is stable and reproducible."""
    power = _power(teams)
    small, big = jh.seed_atr(teams[:8], power), jh.seed_atr(teams, power)
    name = teams[0].school.name
    assert small[name] != big[name]
    # within one field the blend is exactly the two named constants over z-scores
    assert jh.SEED_ATR_TOSS_WEIGHT + jh.SEED_ATR_WIN_WEIGHT == pytest.approx(1.0)
    assert jh.seed_atr(teams, power) == jh.seed_atr(teams, power)
    order = sorted(teams, key=jh._seed_atr_key(big))
    assert order == sorted(teams, key=jh._seed_atr_key(jh.seed_atr(teams, power)))
    # a z-score field is centred
    assert sum(big.values()) == pytest.approx(0.0, abs=1e-9)


def test_atr_lets_record_overturn_toss_in_a_close_case(teams):
    """The 8A shape that motivated the blend: TOSS rates a 22-11 team a hair
    above a 24-3 one; ATR takes the 24-3."""
    a, b = teams[0], teams[1]
    a.wins, a.losses = 22, 11
    b.wins, b.losses = 24, 3
    pool = teams[:8]
    pis = [0.700, 0.695] + [0.5 - i * 0.02 for i in range(6)]
    satr = jh.seed_atr(pool, _power(pool, pis))
    assert satr[b.school.name] > satr[a.school.name]


# --- the State draw's seed order -----------------------------------------------------

def _field(teams, n):
    return teams[:8], teams[8:n]


@pytest.mark.parametrize("n", [24, 32, 40])
def test_bye_lines_are_the_play_in_winners_plus_the_best_four_on_atr(teams, n):
    champs, rest = _field(teams, n)
    power = _power(teams)
    _arc, winners, losers = jh.run_epiregional(champs, power, {}, ["A", "B", "C", "D"],
                                               seed=3)
    ordered, byes = jh.state_seed_order(champs, winners, rest, power)
    assert len(ordered) == n and len(byes) == jh.STATE_BYES
    assert [t.school.name for t in ordered[:jh.STATE_BYES]] == byes
    win_names = {t.school.name for t in winners}
    assert win_names <= set(byes)                       # a win guarantees a top-8 line
    satr = jh.seed_atr(champs + rest, power)
    others = sorted((t for t in champs + rest if t.school.name not in win_names),
                    key=jh._seed_atr_key(satr))
    assert set(byes) == win_names | {t.school.name for t in others[:4]}
    # 1-8 among the bye holders on ATR — not winners first; and 9+ on ATR too
    key = jh._seed_atr_key(satr)
    assert ordered[:8] == sorted(ordered[:8], key=key)
    assert ordered[8:] == sorted(ordered[8:], key=key)
    # every Zonal champion is still in the field, however the play-in went
    assert {t.school.name for t in champs} <= {t.school.name for t in ordered}
    assert {t.school.name for t in losers} <= {t.school.name for t in ordered}


def test_a_play_in_loser_can_still_take_a_merit_bye(teams):
    champs, rest = _field(teams, 32)
    # the eight champions ARE the eight best, by a margin one play-in loss (which
    # the round credits to the loser's record) cannot close
    power = _power(teams, [0.9] * 8 + [0.4 - i * 0.005 for i in range(32)])
    _arc, winners, losers = jh.run_epiregional(champs, power, {}, ["A", "B", "C", "D"],
                                               seed=3)
    _ordered, byes = jh.state_seed_order(champs, winners, rest, power)
    assert set(byes) == {t.school.name for t in champs}
    assert {t.school.name for t in losers} <= set(byes)


def test_a_stronger_non_champion_outseeds_a_play_in_loser(teams):
    """The girls' 8A case: the class's best team missed its Zonal. It is not a
    play-in winner, so it cannot hold lines 1-4 by right — but on ATR it takes a
    merit bye and seeds above every champion weaker than it."""
    champs, rest = _field(teams, 32)
    best = rest[0]
    pis = [0.6 - i * 0.01 for i in range(40)]
    pis[8] = 0.95                                        # rest[0] rates highest
    power = _power(teams, pis)
    _arc, winners, losers = jh.run_epiregional(champs, power, {}, ["A", "B", "C", "D"],
                                               seed=3)
    ordered, byes = jh.state_seed_order(champs, winners, rest, power)
    assert best.school.name in byes
    assert ordered.index(best) < max(ordered.index(t) for t in losers)


# --- the draw keeps its shape --------------------------------------------------------

@pytest.mark.parametrize("n,shape,byes", [
    (24, [(24, 8), (16, 8), (8, 4), (4, 2), (2, 1)], 8),
    (32, [(32, 16), (16, 8), (8, 4), (4, 2), (2, 1)], 0),
    (40, [(40, 16), (24, 8), (16, 8), (8, 4), (4, 2), (2, 1)], 8),
])
def test_bye_totals_and_round_sizes_match_the_field_table(teams, n, shape, byes):
    champs, rest = _field(teams, n)
    power = _power(teams)
    _arc, winners, _l = jh.run_epiregional(champs, power, {}, ["A", "B", "C", "D"], seed=3)
    ordered, bye_names = jh.state_seed_order(champs, winners, rest, power)
    br = jh.run_state(ordered, seed=99, champions=jh.STATE_BYES)
    rounds = wd.jhsaa_state_rounds(br)
    assert [(r["alive"], len(r["games"])) for r in rounds] == shape
    names = br.get("round_names") or []
    if names:                                            # a 40: the double bye
        prelim = {t for rd in br["rounds"][:len(names)] for gm in rd
                  for t in (gm["home"], gm["away"])}
        sat_out = set(br["field"]) - prelim
    else:
        first = {t for gm in br["rounds"][0] for t in (gm["home"], gm["away"])}
        sat_out = set(br["field"]) - first
    assert len(sat_out) == byes
    if byes:
        assert sat_out == set(bye_names)                 # the byes ARE the bye lines
    assert br["field"] == [t.school.name for t in ordered]   # seed = field index


def test_the_same_seed_and_field_draw_the_same_bracket_twice(teams):
    champs, rest = _field(teams, 40)
    power = _power(teams)
    _arc, winners, _l = jh.run_epiregional(champs, power, {}, ["A", "B", "C", "D"], seed=3)
    ordered, _b = jh.state_seed_order(champs, winners, rest, power)
    assert jh.run_state(ordered, seed=99, champions=8) \
        == jh.run_state(ordered, seed=99, champions=8)


def test_epiregional_is_a_postseason_phase_right_after_zonals():
    i = jh.POSTSEASON.index("zonal")
    assert jh.POSTSEASON[i + 1] == "epiregional"
    assert "epiregional" not in jh.NEUTRAL_PHASES        # the higher seed hosts
    assert (jh.EPIREGIONAL_NAME, "EPI") in [(n, s) for n, s, _l in wd.jhsaa_title_stages()]
