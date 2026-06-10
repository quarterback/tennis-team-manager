import random

from engine import random_player
from engine.gtt import GTTTeam, simulate_gtt_dual, LINES_TO_CLINCH

SLOTS = ["MS1", "MS2", "MS3", "WS1", "WS2", "WS3", "XD1", "XD2", "XD3"]


def _gtt_team(name, base, seed):
    rng = random.Random(seed)
    men = [random_player(rng, f"{name}M{i}", base=base) for i in range(3)]
    women = [random_player(rng, f"{name}W{i}", base=base) for i in range(3)]
    return GTTTeam(name=name, men=men, women=women)


def test_gtt_clinch_at_5():
    home = _gtt_team("H", 0.60, 1)
    away = _gtt_team("A", 0.55, 2)
    res = simulate_gtt_dual(home, away, seed=10)
    assert res.home_points + res.away_points <= 9
    assert max(res.home_points, res.away_points) == LINES_TO_CLINCH   # clinch at 5
    assert res.winner in (0, 1)
    # winner is the side that reached the clinch
    assert (res.winner == 0) == (res.home_points > res.away_points)


def test_gtt_nine_lines_three_disciplines():
    res = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=4)
    assert [l.slot for l in res.lines] == SLOTS


def test_gtt_completed_lines_equal_points():
    # Lopsided -> likely early clinch; completed lines == points actually played.
    res = simulate_gtt_dual(_gtt_team("H", 0.80, 1), _gtt_team("A", 0.40, 2), seed=3)
    completed = sum(1 for l in res.lines if l.completed)
    assert completed == res.home_points + res.away_points
    # every unfinished line carries no result
    assert all(l.result is None for l in res.lines if not l.completed)
    assert all(l.result is not None for l in res.lines if l.completed)


def test_gtt_deterministic():
    r1 = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=9)
    r2 = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=9)
    assert (r1.home_points, r1.away_points) == (r2.home_points, r2.away_points)
    assert [l.slot for l in r1.lines] == [l.slot for l in r2.lines]
    assert [l.home_won for l in r1.lines] == [l.home_won for l in r2.lines]


def test_gtt_fast_fidelity_runs_and_clinches():
    res = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2),
                            seed=7, fidelity="fast")
    assert max(res.home_points, res.away_points) == LINES_TO_CLINCH
    assert res.winner in (0, 1)


def test_lines_are_fast4_sets():
    """Every GTT line is a single Fast4 set: first to 4 games, tiebreak at 3-3,
    so no completed line exceeds 4 games and the only one-game margin is 4-3."""
    res = simulate_gtt_dual(_gtt_team("H", 0.62, 1), _gtt_team("A", 0.55, 2), seed=4)
    for ln in res.lines:
        if not ln.completed:
            continue
        sets = ln.result.set_scores
        assert len(sets) == 1, "a GTT line is a single set"
        hi, lo = max(sets[0]), min(sets[0])
        assert hi == 4, f"Fast4 set won at 4 games, got {sets[0]}"
        assert lo <= 3 and (hi - lo >= 2 or (hi, lo) == (4, 3))


def test_form_keeps_determinism():
    a = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=9)
    b = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=9)
    assert [l.home_won for l in a.lines] == [l.home_won for l in b.lines]
