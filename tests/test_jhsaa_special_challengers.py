"""The Special Challengers — the bridge round in FRONT of the State Specials,
and it ALWAYS convenes (owner rule 2026-08, "there should always be challenger
specials"; `docs/AAR-jhsaa-special-challengers.md`).

Every season, in every class: the `CHALLENGE_SLOTS` WEAKEST selected
challengers (2, or 4 in the 40-field classes) defend their Specials seats
against the `CHALLENGE_SLOTS` BEST teams outside the pool — the next names
down the SAME `_challenger_key` ranking the challenger cut was drawn on.

‼️ NO ELIGIBILITY GATES. A TOSS floor, a class-rank cut, a district-title
SCREEN and a sub-.500 exclusion were each tried and each removed: the
challenger cut already takes the best non-qualified teams by record, so the
pool behind it is the weak tail of the class by construction, and gating on it
emptied the contender pool in whole classifications at random. Ranking alone
is the screen — with ONE priority on top of it, district champions, who are
reconsidered ahead of the rest of the field but gate nobody out.

Zero extra berths: only who sits on the challenger side moves.
"""
import pytest

from app import jhsaa as jh
from app import world as wd


class _School:
    def __init__(self, name):
        self.name, self.group, self.district = name, "9A", name


class _Team:
    def __init__(self, name, reg=(10, 6)):
        self.school = _School(name)
        self.schedule = (
            [{"opp": "x", "phase": "regular", "won": True}] * reg[0]
            + [{"opp": "x", "phase": "regular", "won": False}] * reg[1])
        w, l = reg
        self.win_pct = w / (w + l) if w + l else 0.0
        self.points_for = self.points_against = 0.0


class _Res:
    def __init__(self, winner):
        self.winner, self.home_points, self.away_points = winner, 3, 2


def teams(*pairs):
    return {n: _Team(n, reg=r) for n, r in pairs}


def bridge(by, challengers, champs=(), taken=(), power=None, group="7A"):
    """`group` defaults to a 32-field class, i.e. the default two seats."""
    return jh._special_challengers_round(
        group, by, challengers, list(champs), set(taken), power or {}, seed=11)


@pytest.fixture
def away_wins(monkeypatch):
    monkeypatch.setattr(jh, "play_dual", lambda a, b, *, seed, phase: _Res(1))


@pytest.fixture
def home_wins(monkeypatch):
    monkeypatch.setattr(jh, "play_dual", lambda a, b, *, seed, phase: _Res(0))


def test_the_weakest_seats_face_the_best_teams_outside_the_pool(home_wins):
    """The owner's spec, exactly: the 2 worst teams that would take direct
    entry to the Specials play the 2 best teams outside the pool — best
    contender vs weakest holder, seat-holder hosts."""
    by = teams(("Ch1", (16, 0)), ("Ch2", (15, 1)), ("Ch3", (14, 2)),
               ("A", (13, 3)), ("B", (12, 4)), ("C", (5, 11)))
    chs = [by["Ch1"], by["Ch2"], by["Ch3"]]
    arc, _ = bridge(by, chs)
    assert [(gm["home"], gm["away"]) for gm in arc["rounds"][0]] \
        == [("Ch3", "A"), ("Ch2", "B")]
    assert "C" not in {gm["away"] for gm in arc["rounds"][0]}, \
        "the seats go to the BEST outside the pool, not to a body count"


def test_district_champions_get_first_claim(home_wins):
    """‼️ A district champion that lost early is RECONSIDERED ahead of the
    rest of the field (owner rule 2026-08) — and that is ALL it buys here, on
    top of the PROTECTED Regionals entry it already had. A PRIORITY, not a
    gate: once the champions are used up the seats carry straight on down the
    ranking, and a champion still has to win the dual."""
    by = teams(("Ch1", (16, 0)), ("Ch2", (15, 1)), ("A", (14, 2)),
               ("Champ", (9, 7)))
    # 9-7 outranks a 14-2 team for the FIRST seat, and only the first
    arc, _ = bridge(by, [by["Ch1"], by["Ch2"]], champs=("Champ",))
    assert [gm["away"] for gm in arc["rounds"][0]] == ["Champ", "A"]
    # name no champion and the seats go in plain ranking order
    arc, _ = bridge(by, [by["Ch1"], by["Ch2"]])
    assert [gm["away"] for gm in arc["rounds"][0]] == ["A", "Champ"]


def test_there_are_no_eligibility_gates(home_wins):
    """‼️ The gates are gone and must not come back (owner rule 2026-08).
    A team with a losing record, no district title and no TOSS at all still
    plays if it is the best available — "just leave it to anyone who
    qualifies"."""
    assert not hasattr(jh, "CHALLENGE_TOSS_FLOOR")
    assert not hasattr(jh, "CHALLENGE_RANK_CUT")
    by = teams(("Ch1", (16, 0)), ("Weak", (3, 13)))
    arc, _ = bridge(by, [by["Ch1"]])
    assert [gm["away"] for gm in arc["rounds"][0]] == ["Weak"]


def test_the_round_always_convenes(home_wins):
    """The failure this replaced: with a sub-.500 screen the round fired in
    some classifications and not others, because the challenger cut leaves
    the weak tail of the class behind it. Any team outside the pool is a
    contender now, so the only empty arc is an empty POOL."""
    by = teams(("Ch1", (16, 0)), ("Only", (1, 15)))
    arc, _ = bridge(by, [by["Ch1"]])
    assert len(arc["rounds"][0]) == 1


def test_winner_takes_the_seat_and_the_field_size_never_moves(away_wins):
    """The contender wins and HOLDS THAT SEAT — the challenger list is the
    same length before and after (zero extra berths, the rule that separates
    this from a loser's bracket)."""
    by = teams(("Ch1", (16, 0)), ("Ch2", (15, 1)), ("Ch3", (14, 2)),
               ("A", (13, 3)))
    chs = [by["Ch1"], by["Ch2"], by["Ch3"]]
    arc, out = bridge(by, chs)
    assert len(out) == 3 == len(chs)
    assert [t.school.name for t in out] == ["Ch1", "Ch2", "A"]
    gm = arc["rounds"][0][0]
    assert (gm["home"], gm["away"], gm["winner"]) == ("Ch3", "A", "A")
    assert arc["round_names"] == [jh.SPECIAL_CHALLENGER_NAME]
    assert gm["unit"] == "Challenge 1"
    # `field` is the SEED order (`_jh_seeds` labels by index): the defending
    # holder ahead of the contender, never pairing-side order.
    assert arc["field"][0] == "Ch3"


def test_a_holder_who_wins_keeps_the_seat(home_wins):
    by = teams(("Ch1", (16, 0)), ("Ch2", (15, 1)), ("A", (13, 3)))
    arc, out = bridge(by, [by["Ch1"], by["Ch2"]])
    assert [t.school.name for t in out] == ["Ch1", "Ch2"]
    assert arc["rounds"][0][0]["winner"] == "Ch2"


def test_slots_are_two_and_four_in_the_forty_field_classes(home_wins):
    """The wider valve is a property of the big-field shape and has moved
    with it twice (3A/4A carried it at 40, dropped it at 32; 8A/9A inherited
    it going back up)."""
    by = teams(*[(f"Ch{i}", (20 - i, i)) for i in range(1, 6)],
               *[(f"E{i}", (14 - i, i)) for i in range(1, 6)])
    chs = [by[f"Ch{i}"] for i in range(1, 6)]
    arc, _ = bridge(by, chs, group="7A")
    assert len(arc["rounds"][0]) == jh.CHALLENGE_SLOTS_DEFAULT == 2
    assert {g for g, n in jh.CHALLENGE_SLOTS.items() if n == 4} \
        == {g for g in jh.GROUPS if jh.state_field_size(g) == 40}
    arc, _ = bridge(by, chs, group="9A")
    assert len(arc["rounds"][0]) == 4
    assert (arc["rounds"][0][0]["home"], arc["rounds"][0][0]["away"]) \
        == ("Ch5", "E1")


def test_an_empty_pool_returns_the_present_and_empty_arc(home_wins):
    """The ONLY no-fire condition left: every team in the class is already
    qualified or already on the Specials slate (a tiny test world)."""
    by = teams(("Ch1", (16, 0)))
    arc, out = bridge(by, [by["Ch1"]])
    assert arc == {"field": [], "rounds": [[]], "survivors": [],
                   "round_names": [jh.SPECIAL_CHALLENGER_NAME], "head": []}


def test_a_bridge_loser_finishes_at_Challengers():
    """Either loser — the unseated holder or the contender whose crack fell
    short — finishes at "Challengers", superseding the rung that sent them
    in; a bridge winner is in the Specials field and reads on."""
    grp = {"state": {},
           "state_special": {"field": ["Early", "CW"], "survivors": ["CW"]},
           "special_challenger": {"field": ["Ch3", "Early"],
                                  "survivors": ["Early"]},
           "ward": {"field": ["Early", "Ch3", "Elsewhere"]}}
    assert wd.jhsaa_postseason_result(grp, "Ch3")["finish"] \
        == jh.SPECIAL_CHALLENGER_FINISH == "Challengers"
    assert wd.jhsaa_postseason_result(grp, "Early")["finish"] \
        == jh.STATE_SPECIAL_FINISH


def test_phase_is_postseason_and_shapes_resolve():
    """A phase is the archive's identity for an event: `special_challenger` is
    in POSTSEASON (order: after the Conference, before the Specials), plays the
    1S/4D state shape — and the 1A pilot's 2S/3D, since the bridge is part of
    1A's road."""
    ps = jh.POSTSEASON
    assert ps.index("conference") < ps.index("special_challenger") \
        < ps.index("state_special")
    f = jh.dual_format("special_challenger")
    assert (f.n_singles, f.n_doubles) == (1, 4)
    f1a = jh.dual_format("special_challenger", "1A")
    assert (f1a.n_singles, f1a.n_doubles) == (2, 3)
