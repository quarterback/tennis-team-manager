"""Tests for the full two-on-two doubles engine."""
import random

import pytest

from engine import (random_player, simulate_doubles, DoublesTeam, Player,
                    doubles_rating, net_rating, serve_rating)
from engine.format import PRESETS


def _pair(name, base, seed, **skew):
    rng = random.Random(seed)
    a = random_player(rng, f"{name}A", base=base)
    b = random_player(rng, f"{name}B", base=base)
    for p in (a, b):
        for k, v in skew.items():
            setattr(p, k, v)
    return DoublesTeam(players=(a, b))


def test_doubles_runs_and_has_a_winner():
    res = simulate_doubles(_pair("H", 0.6, 1), _pair("A", 0.55, 2), seed=10)
    assert res.winner in (0, 1)
    assert res.fidelity == "full"
    assert len(res.set_scores) >= 2          # best-of-3 default
    assert res.scoreline                      # renders


def test_doubles_deterministic():
    r1 = simulate_doubles(_pair("H", 0.6, 1), _pair("A", 0.55, 2), seed=7)
    r2 = simulate_doubles(_pair("H", 0.6, 1), _pair("A", 0.55, 2), seed=7)
    assert r1.winner == r2.winner
    assert r1.set_scores == r2.set_scores
    assert r1.scoreline == r2.scoreline


def test_doubles_seed_changes_outcome_distribution():
    # Even pairs: across seeds, both sides should win at least sometimes.
    wins = [0, 0]
    for s in range(40):
        res = simulate_doubles(_pair("H", 0.5, 1), _pair("A", 0.5, 2), seed=s)
        wins[res.winner] += 1
    assert wins[0] > 0 and wins[1] > 0


def test_stronger_pair_wins_most():
    wins = [0, 0]
    for s in range(60):
        res = simulate_doubles(_pair("H", 0.72, 1), _pair("A", 0.40, 2), seed=s)
        wins[res.winner] += 1
    assert wins[0] >= 48           # strong pair clears ~80%


def test_fast_fidelity_matches_surface():
    res = simulate_doubles(_pair("H", 0.6, 1), _pair("A", 0.5, 2),
                           seed=3, fidelity="fast")
    assert res.winner in (0, 1)
    assert res.fidelity == "fast"
    assert res.scoreline


def test_fast_is_deterministic():
    a = simulate_doubles(_pair("H", 0.6, 1), _pair("A", 0.5, 2), seed=4, fidelity="fast")
    b = simulate_doubles(_pair("H", 0.6, 1), _pair("A", 0.5, 2), seed=4, fidelity="fast")
    assert a.set_scores == b.set_scores


def test_pro_set_format_is_one_set():
    res = simulate_doubles(_pair("H", 0.6, 1), _pair("A", 0.55, 2),
                           seed=5, fmt=PRESETS["pro_set_8"])
    assert len(res.set_scores) == 1
    hi, lo = max(res.set_scores[0]), min(res.set_scores[0])
    assert hi >= 8 or (hi == 8 and lo <= 6) or hi == 9   # 8-x or 9-7/9-8 tb


def test_net_skill_separates_from_singles():
    # A serve+volley profile should rate ABOVE a baseline-grinder profile in
    # doubles even when their singles `overall` is identical.
    volley = Player(name="V", serve_power=0.85, serve_placement=0.8, movement=0.85,
                    forehand=0.8, mental=0.75, return_game=0.3, backhand=0.3,
                    stamina=0.45, consistency=0.3)
    grinder = Player(name="G", serve_power=0.3, serve_placement=0.3, movement=0.45,
                     forehand=0.4, mental=0.55, return_game=0.85, backhand=0.85,
                     stamina=0.85, consistency=0.85)
    assert abs(volley.overall - grinder.overall) < 0.02      # same singles level
    assert net_rating(volley) > net_rating(grinder)
    assert doubles_rating(volley, volley) > doubles_rating(grinder, grinder)


def test_stats_are_tracked_per_player():
    res = simulate_doubles(_pair("H", 0.6, 1), _pair("A", 0.55, 2), seed=11)
    total_points = sum(s.points_won for s in res.stats)
    # every player on a winning point is credited, so points_won double-counts
    # by team; just assert serving/return ledgers are populated.
    assert any(s.serve_points_total > 0 for s in res.stats)
    assert any(s.aces > 0 or s.double_faults > 0 or s.winners > 0 for s in res.stats)
    assert total_points > 0


def test_accepts_bare_tuples():
    rng = random.Random(1)
    t0 = (random_player(rng, "x"), random_player(rng, "y"))
    t1 = (random_player(rng, "z"), random_player(rng, "w"))
    res = simulate_doubles(t0, t1, seed=2)
    assert res.winner in (0, 1)
