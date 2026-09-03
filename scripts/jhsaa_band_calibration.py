"""Re-solve the JHSAA competitive BANDS against the owner's favourite-win targets.

The high-school matchup curve is `engine.fast.BAND_EDGES_OVR` / `BAND_SLOPES` — a
piecewise-linear transform on the OVR gap, identity inside the peer band and
steeper above it (owner spec 2026-08). The owner's targets are FAVOURITE MATCH
WIN PROBABILITY at the band edges: 62% at 6 OVR, 75% at 14, 87% at 21, 95% at 28.

‼️ THE TRANSFORM IS CUMULATIVE, so the slopes cannot be tuned one at a time by
hand: the effective gap at 21 already contains the 7-14 band's contribution, so
raising that band moves every edge above it. They are solved in order, each
conditioned on the ones below — which for a piecewise-linear cumulative transform
IS the joint solution, since the value at edge k depends only on slopes 1..k.

‼️ AND IT IS SOLVED IN EFFECTIVE-GAP SPACE, NOT BY BISECTING THE SIMULATOR ON
EACH SLOPE. Win rate is a monotone function of the EFFECTIVE gap alone, so the
curve is measured ONCE with every slope at 1.0 (where effective == raw), and
inverted. Bisecting a noisy simulator per slope would cost ~50x the matches and
carry the noise into the answer.

What is fixed, by instruction: the 0-6 peer band stays identity; `skill_slope`
0.9 and `tb_slope` 0.68 are untouched; `gap_knee`/`gap_accel` are neither read
nor written (they are UNUSED while `gap_bands` is on). Optimised against match
win probability through `engine.fast.simulate_fast` at `jhsaa.MATCH_FORMAT` —
never against a set-score distribution. The close-set / high three-set profile is
an accepted consequence of the band spec, not an error to correct.

    python3 scripts/jhsaa_band_calibration.py --trials 40000
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import jhsaa                                            # noqa: E402
from engine import fast                                          # noqa: E402
from engine.state import Player                                  # noqa: E402

TARGETS = {6.0: 0.62, 14.0: 0.75, 21.0: 0.87, 28.0: 0.95}
REPORT_GAPS = (0, 3, 6, 10, 14, 18, 21, 25, 28, 34, 40)

#: A flat player — every driver at one value — so `_edges`' per-situation
#: composites reduce to the overall gap exactly (the equivalence the HS_PROFILE
#: comment relies on). A shaped player would fold serve/return/mental/stamina
#: deviations into the measurement and stop it being a pure gap curve.
#: ‼️ The unit scale is the 20-80 GRADE SPAN, not 0-100. `band_gap` reads "an
#: OVR-point difference divided by the 20-80 scale's span", so a 14-point gap must
#: arrive as 14/60 = 0.2333 in driver units. Dividing by 100 understates every gap
#: by a THIRD and quietly calibrates the curve against the wrong x-axis.
def flat(name: str, ovr: float) -> Player:
    v = (ovr - 20.0) / fast.GRADE_SPAN
    p = Player(name=name)
    for f in p.__dataclass_fields__:
        if isinstance(getattr(p, f), float):
            setattr(p, f, v)
    return p


def win_rate(gap_ovr: float, trials: int, base: float = 55.0) -> float:
    """Favourite match-win rate at an OVR gap, through the shipped fast model at
    the association's own match format. First serve alternates so the result is
    not a measurement of who served first."""
    fav = flat("fav", base + gap_ovr / 2.0)
    dog = flat("dog", base - gap_ovr / 2.0)
    wins = 0
    for i in range(trials):
        res = fast.simulate_fast(fav, dog, seed=0x5EED * 7919 + i,
                                 fmt=jhsaa.MATCH_FORMAT,
                                 first_server=i & 1, profile=fast.HS_PROFILE)
        wins += res.winner == 0
    return wins / trials


def set_slopes(slopes: tuple[float, ...]) -> None:
    """Install a candidate curve. `_BANDS` is precomputed at import, so it has to
    be rebuilt or the hot path keeps scanning the old table."""
    fast.BAND_SLOPES = tuple(slopes)
    fast._BANDS = fast._build_bands()


def measure_identity(trials: int, step: float = 0.5, top: float = 60.0):
    """Win rate against EFFECTIVE gap, sampled with the transform switched off."""
    set_slopes((1.0,) * len(fast.BAND_SLOPES))
    grid = []
    g = 0.0
    while g <= top:
        grid.append((g / fast.GRADE_SPAN, win_rate(g, trials)))
        g += step
    # monotone envelope — sampling noise must not make the inverse ambiguous
    out, best = [], 0.0
    for gap, wr in grid:
        best = max(best, wr)
        out.append((gap, best))
    return out


def invert(curve, target: float) -> float:
    """The effective gap at which the favourite wins `target` of the time."""
    for (g0, w0), (g1, w1) in zip(curve, curve[1:]):
        if w0 <= target <= w1:
            if w1 == w0:
                return g1
            return g0 + (g1 - g0) * (target - w0) / (w1 - w0)
    return curve[-1][0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=20000)
    ap.add_argument("--verify-trials", type=int, default=40000)
    args = ap.parse_args()

    before = tuple(fast.BAND_SLOPES)
    print(f"current BAND_SLOPES {before}  edges {fast.BAND_EDGES_OVR}\n")
    print("measuring the identity curve (transform off) …")
    curve = measure_identity(args.trials)

    edges = (0.0,) + tuple(fast.BAND_EDGES_OVR)
    slopes = [1.0]                      # peer band stays identity, by instruction
    acc = edges[1] / fast.GRADE_SPAN    # effective gap at the peer edge
    for lo, hi in zip(edges[1:], edges[2:]):
        want = invert(curve, TARGETS[hi])
        slope = (want - acc) / ((hi - lo) / fast.GRADE_SPAN)
        slope = max(slope, slopes[-1])  # monotone nondecreasing
        slopes.append(slope)
        acc += (hi - lo) / fast.GRADE_SPAN * slope
    # The tail band has no target above it; keep the step the authored curve used
    # so a 40-OVR mismatch stays ordered against a 28-point one.
    slopes.append(slopes[-1] * (before[-1] / before[-2]))
    fitted = tuple(round(s, 3) for s in slopes)

    print(f"\nfitted BAND_SLOPES {fitted}\n")
    print("verifying through the match engine "
          f"({args.verify_trials} matches per gap)\n")
    print(f"{'OVR':>4} {'current':>9} {'fitted':>9} {'target':>8}")
    rows = []
    for g in REPORT_GAPS:
        set_slopes(before)
        cur = win_rate(g, args.verify_trials)
        set_slopes(fitted)
        new = win_rate(g, args.verify_trials)
        tgt = TARGETS.get(float(g))
        rows.append((g, cur, new, tgt))
        t = f"{tgt*100:7.1f}%" if tgt else "        "
        print(f"{g:>4} {cur*100:8.1f}% {new*100:8.1f}% {t}")
    set_slopes(before)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
