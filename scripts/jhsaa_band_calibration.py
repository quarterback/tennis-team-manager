"""Describe the JHSAA gap-response curve — `engine.fast.PER_POINT_SLOPES`.

The high-school matchup curve is a PER-POINT slope array indexed by integer OVR
gap (owner spec 2026-09; it replaced the banded `BAND_EDGES_OVR` / `BAND_SLOPES`
table, which this script used to re-solve). The effect at gap g is the SUM of the
marginal slopes for every point 1..g (`engine.fast.get_effective_delta`), so the
array is a table of derivatives and what decides a match is its integral — read
through `skill_slope` and ~20 games of logistic compounding. Never eyeball the
array; describe it.

    python3 scripts/jhsaa_band_calibration.py                 # every integer gap 0-40
    python3 scripts/jhsaa_band_calibration.py --gaps 1,3,5,10,15,30 --trials 20000

Per gap: the marginal slope, the cumulative effective delta (OVR points), the
implied hold probability for the favourite serving, and the MEASURED favourite
match-win and three-set rates through the shipped fast model at the association's
own match format (`jhsaa.MATCH_FORMAT`, first serve alternating). Nothing is
fitted and nothing is installed: the array is authored by the owner, and this
script exists to show what it does.
"""

from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import jhsaa                                            # noqa: E402
from engine import fast                                          # noqa: E402
from engine.state import Player                                  # noqa: E402


#: A flat player — every driver at one value — so `_edges`' per-situation
#: composites reduce to the overall gap exactly (the equivalence the HS_PROFILE
#: comment relies on). A shaped player would fold serve/return/mental/stamina
#: deviations into the measurement and stop it being a pure gap curve.
#: ‼️ The unit scale is the 20-80 GRADE SPAN, not 0-100. A 14-point gap must
#: arrive as 14/60 = 0.2333 in driver units. Dividing by 100 understates every gap
#: by a THIRD and quietly measures the curve against the wrong x-axis.
def flat(name: str, ovr: float) -> Player:
    v = (ovr - 20.0) / fast.GRADE_SPAN
    p = Player(name=name)
    for f in p.__dataclass_fields__:
        if isinstance(getattr(p, f), float):
            setattr(p, f, v)
    return p


def measure(gap_ovr: float, trials: int, base: float = 50.0) -> tuple[float, float]:
    """(favourite match-win %, three-set %) at an OVR gap, through the shipped
    fast model at the association's own match format. First serve alternates so
    the result is not a measurement of who served first."""
    fav = flat("fav", base + gap_ovr / 2.0)
    dog = flat("dog", base - gap_ovr / 2.0)
    wins = three = 0
    for i in range(trials):
        res = fast.simulate_fast(fav, dog, seed=0x5EED * 7919 + i,
                                 fmt=jhsaa.MATCH_FORMAT,
                                 first_server=i & 1, profile=fast.HS_PROFILE)
        wins += res.winner == 0
        three += len(res.set_scores) == 3
    return 100.0 * wins / trials, 100.0 * three / trials


def hold_prob(delta_ovr: float) -> float:
    """The favourite's hold probability on serve at a cumulative delta, under the
    HS profile's dials — the number the array actually moves, per game."""
    x = fast.HS_PROFILE["skill_slope"] * delta_ovr / fast.GRADE_SPAN
    return 1.0 / (1.0 + math.exp(-(fast.HS_PROFILE["hold_base_logit"] + x)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gaps", default=",".join(str(g) for g in range(0, 41)),
                    help="comma-separated OVR gaps to describe (fractions allowed)")
    ap.add_argument("--trials", type=int, default=4000,
                    help="matches simulated per gap (se ~0.8pt at 4000)")
    args = ap.parse_args()
    gaps = [float(g) for g in args.gaps.split(",") if g.strip()]

    n = len(fast.PER_POINT_SLOPES)
    print(f"PER_POINT_SLOPES: {n} points, plateau {fast.PLATEAU_SLOPE} a point past {n}")
    print(f"skill_slope {fast.HS_PROFILE['skill_slope']}  tb_slope "
          f"{fast.HS_PROFILE['tb_slope']}  hold_base_logit "
          f"{fast.HS_PROFILE['hold_base_logit']}  format {jhsaa.MATCH_FORMAT}\n")
    print(f"{'gap':>5} {'marginal':>8} {'cum delta':>9} {'hold%':>6} "
          f"{'fav win%':>8} {'3-set%':>7}")
    for g in gaps:
        idx = int(math.ceil(g)) - 1
        marginal = (0.0 if g <= 0 else
                    fast.PER_POINT_SLOPES[min(idx, n - 1)] if idx < n
                    else fast.PLATEAU_SLOPE)
        delta = fast.get_effective_delta(g)
        wr, t3 = measure(g, args.trials)
        gs = f"{g:g}"
        print(f"{gs:>5} {marginal:8.2f} {delta:9.2f} {100 * hold_prob(delta):6.1f} "
              f"{wr:8.1f} {t3:7.1f}")


if __name__ == "__main__":
    main()
