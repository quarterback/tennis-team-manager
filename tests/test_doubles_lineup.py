"""Independent doubles lineup — a coach can pin the three doubles pairs separately
from the singles six, including a doubles specialist who isn't a singles starter
(real college tennis: a "1 doubles / 5 singles" player)."""
import os
import tempfile

import pytest

os.environ.setdefault("TENNIS_DB_PATH", tempfile.mktemp(suffix="-doubles.db"))

from app import overrides as ov
from app.ncaa import load_division, build_roster, reset_caches
from app.season import coach_lineup
from engine.dual import Team, simulate_dual


@pytest.fixture(autouse=True)
def _clean():
    ov.clear_all(); reset_caches()
    yield
    ov.clear_all(); reset_caches()


def _roster():
    prog = load_division("D1", "men").programs[0]
    return prog, build_roster(prog)


# --- overrides round-trip -------------------------------------------------

def test_doubles_override_roundtrip():
    ov.set_doubles("Test U", ["a", "b", "c", "d", "e", "f"])
    assert ov.get_doubles()["Test U"] == ["a", "b", "c", "d", "e", "f"]
    ov.clear_doubles("Test U")
    assert "Test U" not in ov.get_doubles()


# --- the lineup builder ---------------------------------------------------

def test_pinned_doubles_uses_a_non_singles_specialist():
    prog, roster = _roster()
    # A clearly deep player (8th by ability) — not a singles starter — paired at D1.
    specialist = sorted(roster, key=lambda p: p.str_value(), reverse=True)[7]
    others = [p for p in roster if p.pid != specialist.pid][:5]
    pin = [specialist.pid, others[0].pid, others[1].pid,
           others[2].pid, others[3].pid, others[4].pid]

    team, chosen, chosen_dbl = coach_lineup(prog, roster, None, 0.5, lineup_seed=1,
                                            doubles_pin=pin)
    assert [p.pid for p in chosen_dbl] == pin            # honored, in order
    assert team.doubles_players is not None and len(team.doubles_players) == 6
    assert team.doubles == [(0, 1), (2, 3), (4, 5)]
    # the specialist plays DOUBLES but is NOT in the singles six
    assert specialist.pid not in {p.pid for p in chosen}
    assert specialist.pid == chosen_dbl[0].pid


def test_no_pin_falls_back_to_auto_singles_pairing():
    prog, roster = _roster()
    from app.season import DOUBLES_PERMS
    team, chosen, chosen_dbl = coach_lineup(prog, roster, None, 0.5, lineup_seed=1)
    assert team.doubles_players is None                  # engine pairs from singles
    assert chosen_dbl is chosen
    assert [list(p) for p in team.doubles] in [[list(x) for x in perm] for perm in DOUBLES_PERMS]


def test_invalid_pin_falls_back_to_auto():
    prog, roster = _roster()
    team, _chosen, _cd = coach_lineup(prog, roster, None, 0.5, lineup_seed=1,
                                      doubles_pin=["bogus", "x", "y", "z", "w", "v"])
    assert team.doubles_players is None                  # not all six on roster → auto


# --- the engine honors a separate doubles roster --------------------------

def test_engine_pairs_from_doubles_players_when_set():
    prog, roster = _roster()
    six = sorted(roster, key=lambda p: p.str_value(), reverse=True)[:6]
    specialist = sorted(roster, key=lambda p: p.str_value(), reverse=True)[9]
    singles = [p.engine_player() for p in six]
    # doubles roster swaps the specialist into the #1 doubles seat
    dbl = [specialist.engine_player()] + [p.engine_player() for p in six[1:6]]
    home = Team(name="H", singles=singles, doubles=[(0, 1), (2, 3), (4, 5)],
                doubles_players=dbl)
    away = Team(name="A", singles=[p.engine_player() for p in six])
    res = simulate_dual(home, away, seed=3, fidelity="fast")
    assert res.winner in (0, 1)                          # completes, no IndexError
    assert len(res.lines) == 9                            # 3 doubles + 6 singles
