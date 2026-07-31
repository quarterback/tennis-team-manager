"""Point-ending attribution (owner rules 2027-07 — see
docs/AAR-point-attribution-winner-error-mix.md).

Three invariants:
  1. CONSERVATION — every point of a match is labeled exactly once. A player's
     points won == their winners (incl. aces) + the opponent's errors + the
     opponent's double faults. The owner's gut check: the labels must add up to
     the match's real point total, which for a 6-0 set alone is 24-48 points.
  2. LEVEL-BLIND — a matched dual reads the same at every level: a Challenger
     box score looks like an ATP one; every division is the pros of its own
     world. No absolute-level term may creep back in.
  3. GAP-DRIVEN — when levels MEET, the difference shows: the stronger side's
     winner share rises and the weaker side's losses tilt unforced.
"""
import random

from engine import random_player, simulate_match


def _pool_mix(base_a, base_b, n=25, seed0=1000):
    rng = random.Random(99)
    tot = {"w": 0, "f": 0, "u": 0, "df": 0, "pts": 0}
    per_side = []
    for k in range(n):
        a = random_player(rng, "A", base=base_a)
        b = random_player(rng, "B", base=base_b)
        r = simulate_match(a, b, seed=seed0 + k)
        s = r.stats
        # --- invariant 1: conservation, per match, both directions ---
        for me, opp in ((0, 1), (1, 0)):
            assert s[me].points_won == (s[me].winners + s[opp].forced_errors
                                        + s[opp].unforced_errors + s[opp].double_faults), \
                "a point went unlabeled (or double-labeled)"
        total = s[0].points_won + s[1].points_won
        assert total >= 48, "a completed match can't have fewer points than two 6-0 sets"
        for i in (0, 1):
            tot["w"] += s[i].winners
            tot["f"] += s[i].forced_errors
            tot["u"] += s[i].unforced_errors
            tot["df"] += s[i].double_faults
            tot["pts"] += s[i].points_won
        per_side.append((s[0].winners, s[1].winners))
    return {"winners": tot["w"] / tot["pts"], "forced": tot["f"] / tot["pts"],
            "unforced": (tot["u"] + tot["df"]) / tot["pts"], "per_side": per_side}


def test_every_point_is_attributed_and_matched_mix_is_level_blind():
    elite = _pool_mix(0.85, 0.83)
    weak = _pool_mix(0.33, 0.31)
    # Matched duals: same statistical shape at every level (owner rule — no
    # "D4 discount"). Ace rates differ a little by serve talent, so allow a few
    # points of drift, not the old 32%-vs-9% collapse.
    assert abs(elite["winners"] - weak["winners"]) < 0.05, \
        f"matched mix drifted with level: {elite['winners']:.2f} vs {weak['winners']:.2f}"
    assert abs(elite["unforced"] - weak["unforced"]) < 0.05
    # And the mix itself sits in the real-world band (~30% winners / ~70% errors).
    for m in (elite, weak):
        assert 0.24 <= m["winners"] <= 0.40
        assert m["forced"] + m["unforced"] >= 0.60


def test_the_gap_shows_when_levels_meet():
    matched = _pool_mix(0.55, 0.53)
    mismatch = _pool_mix(0.70, 0.40)
    # The stronger side out-hits the weaker side on winners in a mismatch...
    hi = sum(a for a, b in mismatch["per_side"])
    lo = sum(b for a, b in mismatch["per_side"])
    assert hi > lo * 1.2, f"a big favorite should out-winner the underdog ({hi} vs {lo})"
    # ...and the beaten side's losses tilt unforced vs a matched pairing.
    assert mismatch["unforced"] >= matched["unforced"] - 0.03
