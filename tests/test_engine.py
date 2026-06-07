import random

import pytest

from engine import random_player, simulate_match, PRESETS
from engine.format import MatchFormat


def _two_players(seed=0, base0=0.6, base1=0.5):
    rng = random.Random(seed)
    return random_player(rng, "Alpha", "US", base=base0), random_player(rng, "Beta", "ES", base=base1)


def test_determinism_full():
    p0, p1 = _two_players()
    r1 = simulate_match(p0, p1, seed=42)
    p0, p1 = _two_players()
    r2 = simulate_match(p0, p1, seed=42)
    assert r1.scoreline == r2.scoreline
    assert r1.set_scores == r2.set_scores
    assert r1.pbp == r2.pbp
    assert r1.stats[0].points_won == r2.stats[0].points_won


def test_determinism_fast():
    p0, p1 = _two_players()
    r1 = simulate_match(p0, p1, seed=7, fidelity="fast")
    p0, p1 = _two_players()
    r2 = simulate_match(p0, p1, seed=7, fidelity="fast")
    assert r1.scoreline == r2.scoreline
    assert r1.set_scores == r2.set_scores


def test_winner_has_more_sets():
    p0, p1 = _two_players()
    r = simulate_match(p0, p1, seed=3)
    assert r.sets[r.winner] > r.sets[1 - r.winner]
    assert r.sets[r.winner] == 2  # best-of-3


def test_set_scores_valid():
    """Every non-final set is won by 2 games or via a 7-6 tiebreak."""
    p0, p1 = _two_players()
    r = simulate_match(p0, p1, seed=99, fmt=PRESETS["advantage"])
    for a, b in r.set_scores:
        hi, lo = max(a, b), min(a, b)
        assert hi >= 6 and hi - lo >= 2


def test_tiebreak_at_6_6():
    # All sets are normal sets with a tiebreak at 6-6 (no match-tiebreak set),
    # so any 7-6 set score must have come from a tiebreak.
    fmt = MatchFormat(best_of=3, set_tiebreak=True, final_set_tiebreak=False)
    p0, p1 = _two_players(base0=0.5, base1=0.5)
    saw_tb = any(
        {a, b} == {7, 6}
        for s in range(200)
        for a, b in simulate_match(p0, p1, seed=s, fmt=fmt).set_scores
    )
    assert saw_tb


def test_pro_set_single_set():
    p0, p1 = _two_players()
    r = simulate_match(p0, p1, seed=11, fmt=PRESETS["pro_set_8"])
    assert len(r.set_scores) == 1
    a, b = r.set_scores[0]
    assert max(a, b) >= 8


def test_no_ad_completes():
    p0, p1 = _two_players()
    fmt = MatchFormat(best_of=3, no_ad=True)
    r = simulate_match(p0, p1, seed=5, fmt=fmt)
    assert r.winner in (0, 1)


def test_stat_invariants():
    p0, p1 = _two_players()
    r = simulate_match(p0, p1, seed=21)
    total_points = sum(s.serve_points_total for s in r.stats)
    assert r.stats[0].points_won + r.stats[1].points_won == total_points
    for s in r.stats:
        assert s.points_won == s.serve_points_won + s.return_points_won
        assert s.first_serves_in <= s.first_serve_points
        assert s.aces <= s.serve_points_total
        assert s.break_points_saved <= s.break_points_faced
        assert 0.0 <= s.first_serve_pct <= 1.0


def test_stronger_player_wins_more():
    wins = [0, 0]
    for s in range(120):
        rng = random.Random(s)
        strong = random_player(rng, "Strong", base=0.72)
        weak = random_player(rng, "Weak", base=0.42)
        r = simulate_match(strong, weak, seed=s)
        wins[r.winner] += 1
    assert wins[0] > wins[1] * 3  # clearly stronger player dominates
