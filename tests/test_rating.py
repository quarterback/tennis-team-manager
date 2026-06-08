"""Power Index rating — the ITA road-win bonus borrow."""
from app.rating import compute_ratings


def _dual(home, away, home_won):
    return {"home": home, "away": away, "home_won": home_won, "lines": []}


def test_road_wins_rate_above_identical_home_record():
    """Two teams with the SAME record vs the SAME-strength opponents: the one that
    earned its wins on the road (as the away side) rates a hair higher (ITA +10%)."""
    # Both go 1-1 vs the same opponents (beat weak X1, lose to strong X2), so strength
    # of schedule is symmetric — only the venue of the win differs. (A 1-1 record keeps
    # win% off the 1.0 clamp, where the bonus would otherwise wash out.)
    duals = [
        _dual("X1", "RoadTeam", False),   # RoadTeam beats X1 on the road
        _dual("X2", "RoadTeam", True),    # RoadTeam loses to X2 on the road
        _dual("HomeTeam", "X1", True),    # HomeTeam beats X1 at home
        _dual("HomeTeam", "X2", False),   # HomeTeam loses to X2 at home
    ]
    r = compute_ratings(duals)
    assert r["RoadTeam"].road_wins == 1 and r["HomeTeam"].road_wins == 0
    assert (r["RoadTeam"].wins, r["RoadTeam"].losses) == (r["HomeTeam"].wins, r["HomeTeam"].losses) == (1, 1)
    assert r["RoadTeam"].apr > r["HomeTeam"].apr
    assert r["RoadTeam"].pi_raw > r["HomeTeam"].pi_raw
