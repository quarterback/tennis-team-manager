"""The Special Challengers — the bridge round in FRONT of the State Specials
(owner rule 2026-08; `docs/AAR-jhsaa-special-challengers.md`).

Eligible early exits — eliminated before the Specials with a real statewide
profile (class rank inside the cut, a .700+ TOSS, or a district title, and no
losing regular-season record unless the TOSS clears it) — contest the WEAKEST
formula-selected challenger seats, one dual per seat, and the winner holds the
seat into the Specials. Zero extra berths: only who sits on the challenger
side moves.
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


def stages_played(*names):
    """One arc whose rounds mention every name — 'they entered the postseason
    and were eliminated' is read off appearance in a pre-Specials stage."""
    games = [{"home": names[i], "away": names[i + 1],
              "winner": names[i]} for i in range(0, len(names) - 1, 2)]
    if len(names) % 2:
        games.append({"home": names[-1], "away": None, "winner": names[-1]})
    return [{"rounds": [games]}]


def bridge(by, challengers, played, champs=(), taken=(), power=None,
           group="9A", monkey=None, home_wins=True):
    power = power or {}
    return jh._special_challengers_round(
        group, by, challengers, stages_played(*played), list(champs),
        set(taken), power, seed=11)


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
    arc, out = bridge(by, challengers, ("Early",), power=power)
    assert len(out) == 3 == len(challengers)
    assert [t.school.name for t in out] == ["Ch1", "Ch2", "Early"]
    gm = arc["rounds"][0][0]
    assert (gm["home"], gm["away"]) == ("Ch3", "Early"), \
        "the seat-holder hosts, the weakest seat is contested first"
    assert gm["winner"] == "Early"
    assert arc["round_names"] == [jh.SPECIAL_CHALLENGER_NAME]
    assert gm["unit"] == "Challenge 1"


def test_a_holder_who_wins_keeps_the_seat(home_wins):
    by = {n: _Team(n) for n in ("Ch1", "Ch2", "Early")}
    arc, out = bridge(by, [by["Ch1"], by["Ch2"]], ("Early",),
                      power={"Early": _PI(0.75)})
    assert [t.school.name for t in out] == ["Ch1", "Ch2"]
    assert arc["rounds"][0][0]["winner"] == "Ch2"


def test_eligibility_is_gated(home_wins):
    """No losing regular-season record unless TOSS >= .700; no gate passed at
    all -> no dual. A big class makes the rank cut real: rank 25+ with a
    middling TOSS and no district title stays home."""
    by = {f"T{i:03}": _Team(f"T{i:03}", reg=(12, 4)) for i in range(30)}
    power = {n: _PI(0.9 - i / 1000) for i, n in enumerate(sorted(by))}
    # rank 26 (T025), sub-.700 impossible here so drop its TOSS below the floor
    power["T025"] = _PI(0.10)
    by["T025"] = _Team("T025", reg=(12, 4))
    challengers = [by["T000"]]
    # ranks off `power`: T025 now ranks LAST (rank 30) and holds no other gate
    arc, out = bridge(by, challengers, ("T025",), power=power)
    assert arc["rounds"] == [[]], "rank>24, TOSS<.700, no title: not eligible"
    # a losing record blocks even a top-24 rank …
    by["Losing"] = _Team("Losing", reg=(5, 11))
    power["Losing"] = _PI(0.65)
    arc, out = bridge(by, challengers, ("Losing",), power=power)
    assert arc["rounds"] == [[]]
    # … unless the TOSS clears the floor
    power["Losing"] = _PI(0.72)
    arc, out = bridge(by, challengers, ("Losing",), power=power)
    assert len(arc["rounds"][0]) == 1
    # a district title is a gate of its own
    by["Champ"] = _Team("Champ", reg=(9, 7))
    power["Champ"] = _PI(0.30)
    arc, out = bridge(by, challengers, ("Champ",), champs=("Champ",),
                      power=power)
    assert len(arc["rounds"][0]) == 1


def test_only_postseason_entrants_are_eligible(home_wins):
    """The formula pool already reaches a team that never entered the
    postseason — the bridge exists for the one-early-loss case only."""
    by = {n: _Team(n) for n in ("Ch1", "Stayed")}
    arc, out = bridge(by, [by["Ch1"]], (), power={"Stayed": _PI(0.9)})
    assert arc["rounds"] == [[]]


def test_slots_are_capped_per_class(monkeypatch, home_wins):
    """Two seats everywhere (owner rule 2026-08 — 3A/4A's brief 4 retired with
    their 40 -> 32 field retune); `CHALLENGE_SLOTS` stays the override point,
    so the per-class path is pinned through a patched entry."""
    by = {n: _Team(n) for n in
          ("Ch1", "Ch2", "Ch3", "Ch4", "Ch5", "E1", "E2", "E3", "E4", "E5")}
    power = {f"E{i}": _PI(0.9 - i / 100) for i in range(1, 6)}
    chs = [by[f"Ch{i}"] for i in range(1, 6)]
    arc, _ = bridge(by, chs, ("E1", "E2", "E3", "E4", "E5"), power=power)
    assert len(arc["rounds"][0]) == jh.CHALLENGE_SLOTS_DEFAULT == 2
    assert jh.CHALLENGE_SLOTS == {}, "uniform: no class carries a wider valve"
    monkeypatch.setitem(jh.CHALLENGE_SLOTS, "3A", 4)
    arc, _ = bridge(by, chs, ("E1", "E2", "E3", "E4", "E5"), power=power,
                    group="3A")
    assert len(arc["rounds"][0]) == 4
    # best eligible (E1) takes the weakest seat (Ch5)
    gm = arc["rounds"][0][0]
    assert (gm["home"], gm["away"]) == ("Ch5", "E1")


def test_a_quiet_year_returns_the_present_and_empty_arc(home_wins):
    by = {"Ch1": _Team("Ch1")}
    arc, out = bridge(by, [by["Ch1"]], ())
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
