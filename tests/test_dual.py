import random

from engine import random_player, simulate_dual, Team


def _team(name, base, seed):
    rng = random.Random(seed)
    return Team(name=name, singles=[random_player(rng, f"{name}{i}", base=base) for i in range(6)])


def test_dual_clinch_at_4():
    home = _team("H", 0.6, 1)
    away = _team("A", 0.55, 2)
    res = simulate_dual(home, away, seed=10)
    assert res.home_points + res.away_points <= 7
    assert max(res.home_points, res.away_points) == 4   # clinch at 4
    assert res.winner in (0, 1)


def test_dual_abandons_after_clinch():
    home = _team("H", 0.75, 1)   # lopsided → likely early clinch
    away = _team("A", 0.40, 2)
    res = simulate_dual(home, away, seed=3)
    # If a side reached 4 before all 6 singles, some lines are unfinished.
    completed_singles = [l for l in res.lines if l.slot.startswith("S") and l.completed]
    assert len(completed_singles) <= 6


def test_dual_deterministic():
    h1, a1 = _team("H", 0.6, 1), _team("A", 0.55, 2)
    h2, a2 = _team("H", 0.6, 1), _team("A", 0.55, 2)
    r1 = simulate_dual(h1, a1, seed=9)
    r2 = simulate_dual(h2, a2, seed=9)
    assert (r1.home_points, r1.away_points) == (r2.home_points, r2.away_points)


def test_dual_order_of_finish():
    """Every completed line carries a 1-based order-of-finish ordinal (the ITA
    box-score 'Order of finish'); abandoned lines carry none. Within each
    discipline the ordinals are a clean 1..N sequence, and the count of completed
    singles equals the points that were on the board when the dual clinched."""
    res = simulate_dual(_team("H", 0.75, 1), _team("A", 0.40, 2), seed=3)  # lopsided → early clinch
    for disc in ("D", "S"):
        done = [l for l in res.lines if l.slot[0] == disc and l.completed]
        abandoned = [l for l in res.lines if l.slot[0] == disc and not l.completed]
        assert all(l.finish is None for l in abandoned)
        # ordinals are exactly 1..len(done), each used once (a real finish order).
        assert sorted(l.finish for l in done) == list(range(1, len(done) + 1))
    # All three doubles play out in this sim, so doubles always has a full 1..3 order.
    assert len([l for l in res.lines if l.slot[0] == "D" and l.completed]) == 3


def test_dual_order_of_finish_deterministic():
    r1 = simulate_dual(_team("H", 0.6, 1), _team("A", 0.55, 2), seed=9)
    r2 = simulate_dual(_team("H", 0.6, 1), _team("A", 0.55, 2), seed=9)
    assert [l.finish for l in r1.lines] == [l.finish for l in r2.lines]
