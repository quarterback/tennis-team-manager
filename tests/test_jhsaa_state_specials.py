"""State Specials — the final reconciliation round (owner rule, 2026-08).

    missing = STATE_FIELD[group] - qualified
    if missing > 0: 2 × missing latest-eliminated teams play `missing` duals,
    the winners take the missing berths, and State starts full.

Field-size agnostic by design: it knows nothing about 24, 32 or 40. The fault it
ends: the recovery ladder delivered 20 of 9A's 24 earned berths and `run_state`
padded the difference with byes — four teams advancing unplayed, round after round,
on the bracket page.
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
    def __init__(self, name, pct=0.5):
        self.school, self.win_pct = _School(name), pct
        self.schedule = []          # `_pair_penalty` reads it for the rematch rule


class _Res:
    def __init__(self, winner):
        self.winner, self.home_points, self.away_points = winner, 3, 2


@pytest.fixture(autouse=True)
def stub_dual(monkeypatch):
    monkeypatch.setattr(jh, "play_dual",
                        lambda a, b, *, seed, phase: _Res(0))


def stages(*rounds_of_names):
    """Ladder-ordered stage arcs, shallowest first — each stage one round of
    pairings over the named teams."""
    out = []
    for names in rounds_of_names:
        games = [{"home": names[i], "away": names[i + 1], "winner": names[i]}
                 for i in range(0, len(names) - 1, 2)]
        out.append({"rounds": [games]})
    return out


def teams(*names):
    # win_pct DESCENDS through the alphabet, so ATR order inside a tier is the
    # name order and the assertions can say exactly who gets picked.
    return {n: _Team(n, pct=1.0 - i * 0.01) for i, n in enumerate(names)}


def test_it_fills_exactly_the_missing_berths(monkeypatch):
    monkeypatch.setitem(jh.STATE_FIELD, "9A", 32)
    by = teams(*[f"T{i:02}" for i in range(40)])
    taken = {f"T{i:02}" for i in range(28)}          # 28 of 32 — 4 missing
    arc, winners = jh._state_specials(
        "9A", by, stages([f"T{i:02}" for i in range(28, 40)]), taken, {}, seed=7)
    assert len(winners) == 4, "8 teams play for the 4 missing bids"
    assert len(arc["rounds"][0]) == 4
    assert arc["round_names"] == [jh.STATE_SPECIAL_NAME]


def test_a_full_road_plays_no_specials(monkeypatch):
    monkeypatch.setitem(jh.STATE_FIELD, "9A", 24)
    by = teams(*[f"T{i:02}" for i in range(30)])
    arc, winners = jh._state_specials(
        "9A", by, stages(list(by)), {f"T{i:02}" for i in range(24)}, {}, seed=7)
    assert winners == [] and arc["rounds"] == [[]]


def test_selection_walks_back_by_latest_elimination_then_atr(monkeypatch):
    """Conference losers before Semi-Conference losers before anyone earlier —
    ATR orders WITHIN a tier, never across one (the Semi-Conference pool's own
    rule, one round further)."""
    monkeypatch.setitem(jh.STATE_FIELD, "9A", 32)
    by = teams("Early1", "Early2", "Deep1", "Deep2", "Deep3", "Deep4", "Q1", "Q2")
    st = stages(["Early1", "Early2", "Deep1", "Deep2", "Deep3", "Deep4"],  # shallow
                ["Deep1", "Deep2", "Deep3", "Deep4"])                      # deepest
    taken = {f"Q{i}" for i in range(1, 31)}          # 30 of 32 — 2 missing
    arc, winners = jh._state_specials("9A", by, st, taken, {}, seed=7)
    assert set(arc["field"]) == {"Deep1", "Deep2", "Deep3", "Deep4"}, \
        "the four eliminated deepest play; the shallow pair never gets in"
    assert len(winners) == 2


def test_a_dry_pool_admits_directly_and_loudly(monkeypatch, caplog):
    """Fewer than 2×missing bodies: enough enter without playing that the rest can
    still settle the remainder on court — the sc_head idiom — because a short State
    field is the one outcome worse than an unearned entry. Cannot happen at
    association size; a tiny test world hits it."""
    monkeypatch.setitem(jh.STATE_FIELD, "9A", 32)
    by = teams("A", "B", "C", "D")
    taken = {f"Q{i}" for i in range(29)}             # 29 of 32 — 3 missing, 4 bodies
    with caplog.at_level("WARNING"):
        arc, winners = jh._state_specials("9A", by, stages(["A", "B", "C", "D"]),
                                          taken, {}, seed=7)
    assert len(winners) == 3, "the field still ends full"
    # d = 2·missing − pool = 2: two direct, the remaining two play for the third.
    assert len(arc["head"]) == 2
    assert "State Specials short of bodies" in caplog.text


def test_a_specials_loser_finishes_at_state_specials():
    """The finish supersedes the rung that sent them in — one round further than
    the Conference, one short of State."""
    grp = {"state": {}, "state_special": {"field": ["Loser", "Winner"],
                                          "survivors": ["Winner"]},
           "conference": {"field": ["Loser", "Elsewhere"]}}
    assert wd.jhsaa_postseason_result(grp, "Loser")["finish"] == jh.STATE_SPECIAL_FINISH == "Specials"


def test_the_road_ladder_ranks_it_deepest():
    """The ladder ranks FINISHES, so it carries the finish string ("Specials"),
    not the event heading."""
    ladder = wd.jh_road_ladder()
    assert ladder[-1] == jh.STATE_SPECIAL_FINISH
    assert ladder[-2] == jh.CONFERENCE_NAME
