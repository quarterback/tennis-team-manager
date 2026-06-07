import pytest

from app.str_rating import match_rating, player_str, converge_ids, Match, STR_MIN, STR_MAX

# STR is on the 31–57 band; opponent values below are in that band.


def test_str_stays_in_band():
    r = match_rating(44, 6, 3)
    assert STR_MIN <= r <= STR_MAX


def test_match_rating_anchors_on_opponent():
    assert match_rating(44, 5, 5) == pytest.approx(44, abs=0.01)   # a split = opponent's level
    assert match_rating(44, 7, 3) > 44                              # win → above
    assert match_rating(44, 3, 7) < 44                              # loss → below


def test_beating_better_players_rates_higher():
    assert match_rating(51, 6, 4) > match_rating(38, 6, 4)         # same share, stronger opp → higher


def test_recency_can_pull_str_down():
    """'What have you done lately' — recent bad results lower the rating."""
    good = [Match(50, 6, 3) for _ in range(10)]
    s_good, _ = player_str(good)
    slumping = good + [Match(40, 3, 6) for _ in range(6)]
    s_after, _ = player_str(slumping)
    assert s_after < s_good - 0.8


def test_reliability_grows_and_reliable_by_five():
    _, r1 = player_str([Match(44, 6, 4)])
    _, r5 = player_str([Match(44, 6, 4) for _ in range(5)])
    assert r5 > r1
    assert r5 >= 0.7                                                # ~reliable by 5 matches


def test_thin_record_blends_toward_prior():
    s, r = player_str([Match(54, 6, 5)], prior=38.0)
    s_noprior, _ = player_str([Match(54, 6, 5)])
    assert 38.0 < s < s_noprior
    assert r < 0.3


def test_only_last_30_matches_count():
    old = [Match(56, 6, 1) for _ in range(10)]                     # strong but stale
    recent = [Match(38, 3, 6) for _ in range(30)]
    s_all, _ = player_str(old + recent)
    s_recent, _ = player_str(recent)
    assert s_all == pytest.approx(s_recent, abs=0.3)


def test_converge_excludes_blowout_gap_matches():
    # A's real matches are vs peer B (gap 0). Lopsided wins vs weak W (gap ≈16 STR
    # > the ±3.35 cutoff) must be EXCLUDED so they don't drag A down to W.
    matches = {
        "A": [("B", 6, 4)] * 5 + [("W", 6, 0)] * 5,
        "B": [("A", 4, 6)] * 5,
        "W": [("A", 0, 6)] * 5,
    }
    res = converge_ids(matches, priors={"A": 51.0, "B": 51.0, "W": 35.0})
    assert res["A"][0] > 48.0                                       # stayed near peer level
    assert res["A"][1] > 0


def test_converge_rewards_beating_a_stronger_field():
    matches = {
        "climber": [("strong", 6, 4)] * 6,
        "strong":  [("climber", 4, 6)] * 6,
        "front":   [("weak", 6, 4)] * 6,
        "weak":    [("front", 4, 6)] * 6,
    }
    res = converge_ids(matches, priors={"climber": 50, "strong": 53, "front": 50, "weak": 47})
    assert res["climber"][0] > res["front"][0]                      # beating up > beating down
