"""State Specials — the REQUIRED final round of the Road (owner rule 2026-08).

Conference winners no longer qualify for State directly: each must beat a
CHALLENGER — the best remaining regular-season teams from the ENTIRE
classification — in one State Specials dual. `bids = len(conference_winners)`,
winners qualify, losers finish at Specials, and the arithmetic closes every
field size by construction. `_state_specials` survives behind it as the
emergency reconciliation, only if the played round still leaves State short.
"""
import random

import pytest

from app import jhsaa as jh
from app import world as wd


class _School:
    def __init__(self, name):
        # `_pair_penalty` reads group/district for the same-league soft rule.
        self.name, self.group, self.district = name, "9A", name


class _Team:
    def __init__(self, name, reg=(8, 8), post=(0, 0)):
        """`reg`/`post` are (wins, losses); the schedule carries them at the
        phases the challenger ranking reads them from."""
        self.school = _School(name)
        self.schedule = (
            [{"opp": "x", "phase": "regular", "won": True}] * reg[0]
            + [{"opp": "x", "phase": "regular", "won": False}] * reg[1]
            + [{"opp": "x", "phase": "conference", "won": True}] * post[0]
            + [{"opp": "x", "phase": "conference", "won": False}] * post[1])
        w, l = reg[0] + post[0], reg[1] + post[1]
        self.win_pct = w / (w + l) if w + l else 0.0


class _Res:
    def __init__(self, winner):
        self.winner, self.home_points, self.away_points = winner, 3, 2


@pytest.fixture(autouse=True)
def stub_dual(monkeypatch):
    # home (the Conference winner in the new round) wins every stubbed dual
    monkeypatch.setattr(jh, "play_dual",
                        lambda a, b, *, seed, phase: _Res(0))


def teams(*names, reg=None):
    """win_pct DESCENDS through the argument order unless `reg` says otherwise,
    so rankings inside a tier are the name order and assertions can say exactly
    who gets picked."""
    out = {}
    for i, n in enumerate(names):
        r = reg[i] if reg else (16 - i, i)
        out[n] = _Team(n, reg=r)
    return out


# --- the arithmetic the change is built on -----------------------------------------

def test_bids_derive_from_conference_winners_at_every_shape():
    """‼️ THE MATH CLOSES EVERY FIELD SIZE BY CONSTRUCTION: a Conference
    winner's old automatic seat became a Specials dual one-for-one, so
    champions + Semi-State + Divisional + Specials winners == STATE_FIELD —
    the owner's 8 + 12 + 6 + 6 = 32, and the same identity at 40 and on the
    fixed 24 (8 Zonal + 8 Super Regional + 4 Divisional + 4 Specials)."""
    for g in jh.GROUPS:
        field = jh.state_field_size(g)
        if field == 24:
            assert 8 + 8 + 4 + 4 == field, g
            continue
        shape = jh.recovery_shape(g)
        assert (8 + shape["semi_state"] // 2 + shape["divisional"] // 2
                + shape["conference"] // 2) == field, (g, shape)


def test_conference_winners_play_one_dual_per_bid(monkeypatch):
    """32-shape: 6 Conference winners -> 6 duals against 6 challengers -> 6
    qualifiers, and 8 champions + 18 automatics + 6 winners == 32."""
    monkeypatch.setitem(jh.STATE_FIELD, "9A", 32)
    by = teams(*[f"T{i:02}" for i in range(40)])
    qualified = {f"T{i:02}" for i in range(26)}          # 8 zonal + 18 automatic
    cw = [by[f"T{i:02}"] for i in range(26, 32)]         # the 6 Conference winners
    arc, winners = jh._state_specials_round(
        "9A", by, cw, qualified, {}, seed=7)
    assert len(arc["rounds"][0]) == len(cw) == 6
    assert len(winners) == 6
    assert len(arc["field"]) == 12
    assert len(qualified) + len(winners) == 32 == jh.state_field_size("9A")
    assert arc["round_names"] == [jh.STATE_SPECIAL_NAME]
    for gm in arc["rounds"][0]:                          # CW hosts a challenger
        assert gm["home"] in {t.school.name for t in cw}
        assert gm["away"] not in qualified | {t.school.name for t in cw}


def test_no_conference_winners_plays_no_specials(monkeypatch):
    monkeypatch.setitem(jh.STATE_FIELD, "9A", 24)
    by = teams(*[f"T{i:02}" for i in range(30)])
    arc, winners = jh._state_specials_round(
        "9A", by, [], {f"T{i:02}" for i in range(24)}, {}, seed=7)
    assert winners == [] and arc["rounds"] == [[]]


# --- the challengers ----------------------------------------------------------------

def test_challengers_come_from_the_whole_classification(monkeypatch):
    """A challenger is ANY non-qualified, non-winner team in the classification —
    a great regular season that never reached the postseason path outranks a
    deep postseason run with a worse one, because the ranking reads the
    REGULAR SEASON ONLY."""
    monkeypatch.setitem(jh.STATE_FIELD, "9A", 32)
    by = {
        "Winner": _Team("Winner", reg=(6, 10)),          # losing-record CW
        "NoPost": _Team("NoPost", reg=(15, 1)),          # never made the road
        "DeepRun": _Team("DeepRun", reg=(9, 7), post=(4, 1)),
        "Qualified": _Team("Qualified", reg=(16, 0)),
    }
    arc, winners = jh._state_specials_round(
        "9A", by, [by["Winner"]], {"Qualified"}, {}, seed=7)
    assert arc["rounds"][0][0]["away"] == "NoPost", \
        "the best regular-season non-qualified team challenges — postseason " \
        "depth buys nothing and a qualified team is never drafted"


def test_challenger_ranking_ignores_postseason_results():
    """reg pct, then reg wins, then ATR — and the postseason contributes to NONE
    of the first two (a 12-4 regular season outranks 11-5 whatever the bracket
    then added)."""
    a = _Team("A", reg=(12, 4), post=(0, 3))
    b = _Team("B", reg=(11, 5), post=(3, 0))
    assert jh._reg_season_record(a) == (12, 4)
    assert jh._reg_season_record(b) == (11, 5)
    assert sorted([b, a], key=jh._challenger_key({}))[0] is a


def test_pairing_is_best_challenger_vs_weakest_winner(monkeypatch):
    """Seeded, best-vs-worst (owner rule 2026-08): the top-ranked challenger
    draws the weakest Conference winner by ATR."""
    monkeypatch.setitem(jh.STATE_FIELD, "9A", 32)
    by = teams("StrongCW", "WeakCW", "BestCh", "NextCh",
               reg=[(14, 2), (5, 11), (13, 3), (10, 6)])
    arc, _ = jh._state_specials_round(
        "9A", by, [by["StrongCW"], by["WeakCW"]], set(), {}, seed=7)
    games = arc["rounds"][0]
    assert (games[0]["home"], games[0]["away"]) == ("WeakCW", "BestCh")
    assert (games[1]["home"], games[1]["away"]) == ("StrongCW", "NextCh")


def test_a_dry_challenger_pool_admits_winners_unopposed(monkeypatch, caplog):
    """Fewer challengers than bids (a tiny test world — statewide the pool is
    every non-qualified team): the unpaired Conference winners qualify
    unopposed, loudly, because a short State field is the one outcome worse
    than an uncontested berth."""
    monkeypatch.setitem(jh.STATE_FIELD, "9A", 32)
    by = teams("CW1", "CW2", "CW3", "OnlyCh")
    with caplog.at_level("WARNING"):
        arc, winners = jh._state_specials_round(
            "9A", by, [by["CW1"], by["CW2"], by["CW3"]], set(), {}, seed=7)
    assert len(winners) == 3, "every bid is still filled"
    assert len(arc["rounds"][0]) == 1 and len(arc["head"]) == 2
    assert "short of challengers" in caplog.text


# --- the emergency reconciliation stays behind it -----------------------------------

def stages(*rounds_of_names):
    out = []
    for names in rounds_of_names:
        games = [{"home": names[i], "away": names[i + 1], "winner": names[i]}
                 for i in range(0, len(names) - 1, 2)]
        out.append({"rounds": [games]})
    return out


def test_emergency_reconciliation_still_fills_a_short_field(monkeypatch):
    """`_state_specials` is unchanged behind the played round: 2 x missing
    latest-eliminated teams play for exactly the missing berths."""
    monkeypatch.setitem(jh.STATE_FIELD, "9A", 32)
    by = teams(*[f"T{i:02}" for i in range(40)])
    taken = {f"T{i:02}" for i in range(28)}              # 28 of 32 — 4 missing
    arc, winners = jh._state_specials(
        "9A", by, stages([f"T{i:02}" for i in range(28, 40)]), taken, {}, seed=7)
    assert len(winners) == 4
    assert len(arc["rounds"][0]) == 4


def test_emergency_reconciliation_is_a_no_op_on_a_full_field(monkeypatch):
    monkeypatch.setitem(jh.STATE_FIELD, "9A", 24)
    by = teams(*[f"T{i:02}" for i in range(30)])
    arc, winners = jh._state_specials(
        "9A", by, stages(list(by)), {f"T{i:02}" for i in range(24)}, {}, seed=7)
    assert winners == [] and arc["rounds"] == [[]]


# --- finishes -----------------------------------------------------------------------

def test_a_specials_loser_finishes_at_specials():
    """A Conference winner OR a challenger that loses the Specials finishes at
    Specials — one round further than the Conference, one short of State — and
    a Specials winner is a normal State qualifier (read off the state field)."""
    grp = {"state": {}, "state_special": {"field": ["Loser", "Winner"],
                                          "survivors": ["Winner"]},
           "conference": {"field": ["Loser", "Elsewhere"]}}
    assert wd.jhsaa_postseason_result(grp, "Loser")["finish"] \
        == jh.STATE_SPECIAL_FINISH == "Specials"


def test_the_road_ladder_ranks_it_deepest():
    ladder = wd.jh_road_ladder()
    assert ladder[-1] == jh.STATE_SPECIAL_FINISH
    assert ladder[-2] == jh.CONFERENCE_NAME
