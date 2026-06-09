"""Tests for the NCAA individual singles & doubles championships (app.individuals)."""
import pytest

from app.web.server import create_app
from app.individuals import (run_doubles_championship, run_singles_championship,
                             select_doubles_field, select_singles_field,
                             DOUBLES_FIELD, SINGLES_FIELD)
from app.ncaa import load_division
from engine import seed_count


@pytest.fixture(scope="module", autouse=True)
def _boot():
    create_app()          # bootstrap schemas / data


def test_singles_championship_runs():
    ch = run_singles_championship("D1", "men", seed=2026, size=128)
    assert len(ch.entries) == 128
    assert len(ch.rounds) == 7                     # 128→64→…→2
    assert ch.champion is not None and ch.runner_up is not None
    assert ch.rounds[-1][0].winner is ch.champion


def test_only_a_quarter_of_the_draw_is_seeded():
    # 128→32 seeds, 64→16, per the tennis convention.
    s = run_singles_championship("D1", "men", seed=1, size=128)
    assert s.n_seeds == seed_count(128) == 32
    d = run_doubles_championship("D1", "men", seed=1, size=64)
    assert d.n_seeds == seed_count(64) == 16
    # seeded entrants carry a number; unseeded ones don't.
    assert s.seed_of(s.entries[0]) == 1
    assert s.seed_of(s.entries[31]) == 32
    assert s.seed_of(s.entries[32]) is None
    assert s.seed_of(s.entries[100]) is None


def test_seeds_are_protected_in_the_first_round():
    # With proper seeding, no two seeds can meet in the opening round.
    ch = run_singles_championship("D1", "men", seed=7, size=128)
    both_seeded = sum(1 for m in ch.rounds[0]
                      if m.hi_seed is not None and m.lo_seed is not None)
    assert both_seeded == 0


def test_both_events_run_for_men_and_women():
    for gender in ("men", "women"):
        s = run_singles_championship("D1", gender, seed=2026, size=128)
        d = run_doubles_championship("D1", gender, seed=2026, size=64)
        assert s.champion is not None and len(s.entries) == 128
        assert d.champion is not None and len(d.entries) == 64


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
    # so the title is open (an unseeded pair can win) — but stronger pairs should
    # still win it far more than a coin flip (random mean rank would be ~32.5).
    ranks = []
    for s in range(24):
        ch = run_doubles_championship("D1", "men", seed=s, size=64)
        ranks.append(ch.entries.index(ch.champion) + 1)   # rating rank, always defined
    assert sum(ranks) / len(ranks) < 28                   # skewed toward strong pairs
    assert len(set(ranks)) > 6                            # not a fixed outcome


def test_smaller_field_clamps():
    ch = run_doubles_championship("D1", "men", seed=1, size=16)
    assert len(ch.entries) == 16
    assert len(ch.rounds) == 4                           # 16→8→4→2
