"""Tests for the NCAA individual doubles championship (app.individuals)."""
import pytest

from app.web.server import create_app
from app.individuals import (run_doubles_championship, select_doubles_field,
                             DOUBLES_FIELD)
from app.ncaa import load_division


@pytest.fixture(scope="module", autouse=True)
def _boot():
    create_app()          # bootstrap schemas / data


def test_field_is_seeded_by_doubles_rating():
    progs = load_division("D1", "men").programs
    field = select_doubles_field(progs, DOUBLES_FIELD)
    assert len(field) == min(DOUBLES_FIELD, len(progs))
    ratings = [e.rating for e in field]
    assert ratings == sorted(ratings, reverse=True)      # #1 seed strongest
    # each entry is a distinct program's #1 pair
    assert len({e.program.key for e in field}) == len(field)


def test_championship_runs_and_has_a_champion():
    ch = run_doubles_championship("D1", "men", seed=2026, size=64)
    assert ch.champion is not None and ch.runner_up is not None
    assert ch.champion is not ch.runner_up
    assert ch.rounds                                     # several rounds played
    # 64-draw → 6 rounds (64→32→16→8→4→2)
    assert len(ch.rounds) == 6
    # the final is a single match between champion and runner-up
    final = ch.rounds[-1]
    assert len(final) == 1
    assert final[0].winner is ch.champion
    assert final[0].scoreline


def test_championship_is_deterministic():
    a = run_doubles_championship("D1", "men", seed=2026, size=64)
    b = run_doubles_championship("D1", "men", seed=2026, size=64)
    assert a.champion.program.key == b.champion.program.key
    assert [m.scoreline for m in a.rounds[-1]] == [m.scoreline for m in b.rounds[-1]]


def test_seed_changes_the_champion_sometimes():
    champs = {run_doubles_championship("D1", "men", seed=s, size=64).champion.program.key
              for s in range(2020, 2030)}
    assert len(champs) > 1                               # not a fixed outcome


def test_seeds_are_favored_but_field_is_deep():
    # A 64-draw needs six straight wins and college doubles is tightly bunched,
    # so the title is open — but stronger seeds should still win it far more than
    # a coin flip would predict (random mean champion seed would be ~32.5).
    champ_seeds = [run_doubles_championship("D1", "men", seed=s, size=64).seed_of(
        run_doubles_championship("D1", "men", seed=s, size=64).champion)
        for s in range(24)]
    assert sum(champ_seeds) / len(champ_seeds) < 28      # skewed toward strong pairs
    assert len(set(champ_seeds)) > 6                     # not a fixed outcome


def test_smaller_field_clamps():
    ch = run_doubles_championship("D1", "men", seed=1, size=16)
    assert len(ch.entries) == 16
    assert len(ch.rounds) == 4                           # 16→8→4→2
