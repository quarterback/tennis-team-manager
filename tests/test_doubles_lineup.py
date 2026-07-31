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
    from app.ncaa import dual_format, lineup_size
    prog, roster = _roster()
    n, n_d = lineup_size(prog.division), dual_format(prog.division).n_doubles
    # A clearly deep player (below the singles card by ability) — paired at D1.
    by_str = sorted(roster, key=lambda p: p.str_value(), reverse=True)
    specialist = by_str[n + 1]
    others = [p for p in roster if p.pid != specialist.pid][:2 * n_d - 1]
    pin = [specialist.pid] + [p.pid for p in others]

    # best_six lineup = strict STR order, so with only two bench seats left on a
    # 12-cap roster the below-card specialist stays out of singles deterministically.
    team, chosen, chosen_dbl = coach_lineup(prog, roster, None, 0.5, lineup_seed=1,
                                            doubles_pin=pin, best_six=True)
    assert [p.pid for p in chosen_dbl] == pin            # honored, in order
    assert team.doubles_players is not None and len(team.doubles_players) == 2 * n_d
    assert team.doubles == [(2 * i, 2 * i + 1) for i in range(n_d)]
    # the specialist plays DOUBLES but is NOT in the singles card
    assert specialist.pid not in {p.pid for p in chosen}
    assert specialist.pid == chosen_dbl[0].pid


def test_no_pin_falls_back_to_auto_singles_pairing():
    from app.ncaa import dual_format
    prog, roster = _roster()
    from app.season import doubles_perms
    perms = doubles_perms(dual_format(prog.division).n_doubles)
    team, chosen, chosen_dbl = coach_lineup(prog, roster, None, 0.5, lineup_seed=1)
    assert team.doubles_players is None                  # engine pairs from singles
    assert chosen_dbl is chosen
    assert [list(p) for p in team.doubles] in [[list(x) for x in perm] for perm in perms]


def test_invalid_pin_falls_back_to_auto():
    prog, roster = _roster()
    team, _chosen, _cd = coach_lineup(prog, roster, None, 0.5, lineup_seed=1,
                                      doubles_pin=["bogus", "x", "y", "z", "w", "v"])
    assert team.doubles_players is None                  # pin doesn't cover the card → auto


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
    assert len(res.lines) == 9                            # classic default: 3 doubles + 6 singles
