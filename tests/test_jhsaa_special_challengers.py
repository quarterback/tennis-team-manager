"""The Special Challengers — the bridge round in FRONT of the State Specials,
and it ALWAYS convenes (owner rule 2026-08, "there should always be challenger
specials"; `docs/AAR-jhsaa-special-challengers.md`).

Every season, in every class, the WEAKEST selected challenger seats are
defended on court — 2 duals, 4 in the 40-field classes. Contenders come in
PRIORITY order: the eligibility formula first (class rank inside the cut, a
.700+ TOSS, or a district title; no losing regular-season record unless the
TOSS clears it), then the rest of the WINNING-RECORD teams — both tiers in
the Specials' own challenger ranking (reg-season record, ATR tiebreak), and
a losing record without the TOSS excuse is excluded outright (owner: "i
don't want a bunch of losing teams playing more losing teams"). Zero extra
berths: only who sits on the challenger side moves.
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
        self.points_for = self.points_against = 0.0   # `_power_key`'s fallback


class _PI:
    def __init__(self, v):
        self.pi_raw = v


class _Res:
    def __init__(self, winner):
        self.winner, self.home_points, self.away_points = winner, 3, 2


def bridge(by, challengers, champs=(), taken=(), power=None, group="9A"):
    power = power or {}
    return jh._special_challengers_round(
        group, by, challengers, list(champs), set(taken), power, seed=11)


@pytest.fixture
def away_wins(monkeypatch):
    monkeypatch.setattr(jh, "play_dual", lambda a, b, *, seed, phase: _Res(1))


@pytest.fixture
def home_wins(monkeypatch):
    monkeypatch.setattr(jh, "play_dual", lambda a, b, *, seed, phase: _Res(0))


def test_winner_takes_the_weakest_seat_and_the_field_size_never_moves(away_wins):
    """Best eligible vs weakest selected challenger; the contender wins and
    HOLDS THAT SEAT — the challenger list is the same length before and after
    (zero extra berths, the rule that separates this from a loser's bracket)."""
    by = {n: _Team(n) for n in ("Ch1", "Ch2", "Ch3", "Early")}
    power = {"Early": _PI(0.75)}
    challengers = [by["Ch1"], by["Ch2"], by["Ch3"]]      # best first
    arc, out = bridge(by, challengers, power=power)
    assert len(out) == 3 == len(challengers)
    assert [t.school.name for t in out] == ["Ch1", "Ch2", "Early"]
    gm = arc["rounds"][0][0]
    assert (gm["home"], gm["away"]) == ("Ch3", "Early"), \
        "the seat-holder hosts, the weakest seat is contested first"
    assert gm["winner"] == "Early"
    assert arc["round_names"] == [jh.SPECIAL_CHALLENGER_NAME]
    assert gm["unit"] == "Challenge 1"
    # `field` is the SEED order (`_jh_seeds` labels by index): the defending
    # holder ahead of the contender, never pairing-side order.
    assert arc["field"] == ["Ch3", "Early"]


def test_a_holder_who_wins_keeps_the_seat(home_wins):
    by = {n: _Team(n) for n in ("Ch1", "Ch2", "Early")}
    arc, out = bridge(by, [by["Ch1"], by["Ch2"]], power={"Early": _PI(0.75)})
    assert [t.school.name for t in out] == ["Ch1", "Ch2"]
    assert arc["rounds"][0][0]["winner"] == "Ch2"


def test_the_formula_is_a_priority_not_a_filter(home_wins):
    """The formula decides WHO GOES FIRST, never whether the round plays
    (owner rule 2026-08 — the quiet-year design was reversed): a formula
    team outranks a higher-TOSS team that passes no gate, a losing record
    sorts last unless the TOSS floor clears it into the formula tier, and a
    district title is a gate of its own."""
    # 30 losing-record, sub-floor-TOSS fillers: many hold top-24 ranks (the
    # rank gate passes) but the losing record drops them to the LAST tier.
    by = {f"T{i:03}": _Team(f"T{i:03}", reg=(5, 11)) for i in range(30)}
    power = {n: _PI(0.5 - i / 1000) for i, n in enumerate(sorted(by))}
    challengers = [by["T000"], by["T001"]]
    # "Formula" passes the formula; "NoGate" has a winning record but the
    # worst TOSS in the class (rank past the cut, no title) -> middle tier.
    by["Formula"] = _Team("Formula", reg=(12, 4))
    power["Formula"] = _PI(0.71)
    by["NoGate"] = _Team("NoGate", reg=(12, 4))
    power["NoGate"] = _PI(0.10)
    arc, out = bridge(by, challengers, power=power)
    aways = [gm["away"] for gm in arc["rounds"][0]]
    assert aways == ["Formula", "NoGate"], \
        "formula tier first, then the winning-record tier — the losing-record " \
        "fillers are excluded outright whatever their rank"
    # the TOSS floor lifts a losing record into the formula tier, and a
    # district title is a gate of its own (winning record, sub-floor TOSS,
    # rank past the cut) — checked at the 4-seat class so neither is crowded
    # out of the round by the other formula teams.
    by["Salvaged"] = _Team("Salvaged", reg=(5, 11))
    power["Salvaged"] = _PI(0.72)
    by["Champ"] = _Team("Champ", reg=(9, 7))
    power["Champ"] = _PI(0.30)
    chs4 = [by["T000"], by["T001"], by["T002"], by["T003"], by["T004"]]
    arc, _ = bridge(by, chs4, champs=("Champ",), power=power, group="9A")
    aways = [gm["away"] for gm in arc["rounds"][0]]
    assert aways == ["Formula", "Champ", "Salvaged", "NoGate"], \
        "tier 0 in RECORD order (12-4, 9-7, then the TOSS-excused 5-11 — " \
        "the owner wants good seasons, not TOSS loading), then tier 1"


def test_the_round_always_convenes(home_wins):
    """No formula team at all — the best of the rest still plays: the round
    convenes every season (owner: "there should always be challenger
    specials"), and a team that never entered the postseason can be drafted
    (the postseason-entrants-only screen was retired with the reversal)."""
    by = {n: _Team(n) for n in ("Ch1", "Stayed")}
    arc, out = bridge(by, [by["Ch1"]], power={"Stayed": _PI(0.9)})
    assert len(arc["rounds"][0]) == 1
    assert arc["rounds"][0][0]["away"] == "Stayed"


def test_slots_are_capped_per_class(home_wins):
    """Two seats by default, four in the 40-field classes (owner rule 2026-08)
    — the wider valve is a property of the big-field shape and has moved with
    it once already (3A/4A carried it at 40, dropped it at 32; 8A/9A inherited
    it going back up)."""
    by = {n: _Team(n) for n in
          ("Ch1", "Ch2", "Ch3", "Ch4", "Ch5", "E1", "E2", "E3", "E4", "E5")}
    power = {f"E{i}": _PI(0.9 - i / 100) for i in range(1, 6)}
    chs = [by[f"Ch{i}"] for i in range(1, 6)]
    # a 32-field class carries the default (the harness's own default group,
    # 9A, is a 40-field class now and carries the wider valve)
    arc, _ = bridge(by, chs, power=power, group="7A")
    assert len(arc["rounds"][0]) == jh.CHALLENGE_SLOTS_DEFAULT == 2
    # the wider valve rides the 40-field classes, exactly them
    assert {g for g, n in jh.CHALLENGE_SLOTS.items() if n == 4} \
        == {g for g in jh.GROUPS if jh.state_field_size(g) == 40}
    arc, _ = bridge(by, chs, power=power, group="9A")
    assert len(arc["rounds"][0]) == 4
    # best eligible (E1) takes the weakest seat (Ch5)
    gm = arc["rounds"][0][0]
    assert (gm["home"], gm["away"]) == ("Ch5", "E1")


def test_a_quiet_year_returns_the_present_and_empty_arc(home_wins):
    """Empty now means an empty POOL (every team already qualified or on the
    Specials slate — a tiny test world), never a formula with no takers."""
    by = {"Ch1": _Team("Ch1")}
    arc, out = bridge(by, [by["Ch1"]])
    assert arc == {"field": [], "rounds": [[]], "survivors": [],
                   "round_names": [jh.SPECIAL_CHALLENGER_NAME], "head": []}


def test_a_bridge_loser_finishes_at_Challengers():
    """Either loser — the unseated challenger or the early exit whose extra
    crack fell short — finishes at "Challengers", superseding the rung that
    sent them in; a bridge winner is in the Specials field and reads on."""
    grp = {"state": {},
           "state_special": {"field": ["Early", "CW"], "survivors": ["CW"]},
           "special_challenger": {"field": ["Ch3", "Early"],
                                  "survivors": ["Early"]},
           "ward": {"field": ["Early", "Ch3", "Elsewhere"]}}
    assert wd.jhsaa_postseason_result(grp, "Ch3")["finish"] \
        == jh.SPECIAL_CHALLENGER_FINISH == "Challengers"
    # the winner reached the Specials, so the Specials branch reads first
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
