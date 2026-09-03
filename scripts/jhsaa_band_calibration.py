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

‼️ TWO MODES, AND MEASURING IS THE DEFAULT. The fit was written for a four-edge
table whose every edge carried a target; the shipped curve is now authored by hand
over eleven edges, so the useful command is the one that DESCRIBES it — every band
edge the table actually has, with slope, effective gap, favourite and underdog win
rates, and the per-band lift that shows where the curve spends its resolution.

    python3 scripts/jhsaa_band_calibration.py                  # describe the curve
    python3 scripts/jhsaa_band_calibration.py --against 1,1,1.5,2.2,3   # vs another
    python3 scripts/jhsaa_band_calibration.py --fit            # re-solve the slopes

The sweep is DERIVED from `BAND_EDGES_OVR`; a typed gap list silently stops
covering the curve the moment the table changes shape, and prints a clean-looking
report with bands missing from it. `--fit` solves only the edges that carry a
target and says so — it used to index TARGETS by every edge, which raised
`KeyError: 9.0` on the 12-band table AFTER the multi-minute identity measurement.
Neither mode leaves a candidate table installed.
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


def report_gaps() -> list[int]:
    """‼️ DERIVED FROM THE TABLE, never a typed list. The edges have gone from four
    to eleven; a hardcoded sweep silently stops covering the curve it is meant to
    describe, and reports a clean-looking table with bands missing from it."""
    edges = [int(e) for e in fast.BAND_EDGES_OVR]
    top = edges[-1]
    return [0] + edges + [top + 3, top + 6, top + 11]


def measure(slopes, gaps, trials):
    fast.BAND_SLOPES = tuple(slopes)
    fast._BANDS = fast._build_bands()
    return ({g: win_rate(g, trials) for g in gaps},
            {g: fast.band_gap(g / fast.GRADE_SPAN) for g in gaps})


def slope_at(gap: float) -> float:
    for edge, slope in zip(fast.BAND_EDGES_OVR, fast.BAND_SLOPES):
        if gap <= edge:
            return slope
    return fast.BAND_SLOPES[-1]


def do_report(args) -> int:
    """What the shipped curve actually does, at every band edge it actually has."""
    live = tuple(fast.BAND_SLOPES)
    other = tuple(float(x) for x in args.against.split(",")) if args.against else None
    if other and len(other) != len(live):
        print(f"--against needs {len(live)} slopes for {len(fast.BAND_EDGES_OVR)} "
              f"edges, got {len(other)}")
        return 1
    gaps = report_gaps()
    print(f"edges  {tuple(fast.BAND_EDGES_OVR)}")
    print(f"slopes {live}")
    if other:
        print(f"against {other}")
    print(f"\n{args.verify_trials} matches a point\n")
    nw, ne = measure(live, gaps, args.verify_trials)
    ow = measure(other, gaps, args.verify_trials)[0] if other else None
    measure(live, gaps, 1)      # restore the live table before printing

    head = f"{'OVR':>4}{'slope':>7}{'eff gap':>9}{'fav win':>9}{'underdog':>10}"
    print(head + (f"{'other fav':>11}{'other dog':>11}" if other else "")
          + f"{'target':>9}")
    for g in gaps:
        row = (f"{g:>4}{slope_at(g):>7.2f}{ne[g]:>9.4f}"
               f"{nw[g] * 100:>8.1f}%{100 - nw[g] * 100:>9.2f}%")
        if other:
            row += f"{ow[g] * 100:>10.1f}%{100 - ow[g] * 100:>10.2f}%"
        t = TARGETS.get(float(g))
        print(row + (f"{t * 100:>8.1f}%" if t else "         "))

    print("\nper-band lift in favourite win% — where the curve spends its resolution")
    for lo, hi in zip(gaps, gaps[1:]):
        extra = f"   (other {(ow[hi] - ow[lo]) * 100:>5.1f})" if other else ""
        print(f"  {lo:>2}-{hi:<3} {(nw[hi] - nw[lo]) * 100:>6.1f} pts{extra}")
    return 0


def do_fit(args) -> int:
    """Solve the post-peer slopes for the owner's targets.

    ‼️ ONLY THE EDGES THAT HAVE A TARGET. The table's edges are an authored shape
    and have gone from four to eleven; this loop used to index TARGETS by every
    edge, so the 12-band table raised `KeyError: 9.0` — AFTER the multi-minute
    identity measurement, which is the worst place to fail. Bands whose upper edge
    carries no target keep their authored slope and are folded into the running
    accumulator, so a fit over a fine table still solves the four edges the owner
    actually stated.
    """
    before = tuple(fast.BAND_SLOPES)
    edges = tuple(fast.BAND_EDGES_OVR)
    have = [e for e in edges if e in TARGETS]
    if not have:
        print(f"no band edge carries a target — edges {edges}, "
              f"targets {sorted(TARGETS)}. Nothing to fit; use the default report.")
        return 1
    missing = sorted(set(TARGETS) - set(edges))
    if missing:
        print(f"note: targets at {missing} sit inside a band, not on an edge — "
              f"they cannot be solved and are skipped.\n")

    print(f"current BAND_SLOPES {before}  edges {edges}\n")
    print("measuring the identity curve (transform off) …")
    curve = measure_identity(args.trials)

    bounds = (0.0,) + edges
    slopes = [1.0]                      # peer band stays identity, by instruction
    acc = bounds[1] / fast.GRADE_SPAN   # effective gap at the peer edge
    for i, (lo, hi) in enumerate(zip(bounds[1:], bounds[2:]), start=1):
        if hi in TARGETS:
            want = invert(curve, TARGETS[hi])
            slope = max((want - acc) / ((hi - lo) / fast.GRADE_SPAN), slopes[-1])
        else:
            slope = max(before[i], slopes[-1])   # authored, and kept monotone
        slopes.append(slope)
        acc += (hi - lo) / fast.GRADE_SPAN * slope
    # The tail band has no edge above it; keep the step the authored curve used so
    # a mismatch past the last edge stays ordered against one at it.
    slopes.append(slopes[-1] * (before[-1] / before[-2]) if before[-2] else slopes[-1])
    fitted = tuple(round(s, 3) for s in slopes)

    print(f"\nfitted BAND_SLOPES {fitted}\n")
    print(f"verifying through the match engine ({args.verify_trials} a gap)\n")
    gaps = report_gaps()
    cur = measure(before, gaps, args.verify_trials)[0]
    new = measure(fitted, gaps, args.verify_trials)[0]
    measure(before, gaps, 1)            # never leave a fitted table installed
    print(f"{'OVR':>4} {'current':>9} {'fitted':>9} {'target':>8}")
    for g in gaps:
        t = TARGETS.get(float(g))
        print(f"{g:>4} {cur[g] * 100:8.1f}% {new[g] * 100:8.1f}%"
              + (f"{t * 100:7.1f}%" if t else "        "))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Measure (default) or re-fit the JHSAA competitive bands.")
    ap.add_argument("--fit", action="store_true",
                    help="solve the post-peer slopes for the owner's targets "
                         "instead of reporting the shipped curve")
    ap.add_argument("--against", default="",
                    help="comma-separated slopes to report the live table against")
    ap.add_argument("--trials", type=int, default=20000,
                    help="matches per point when measuring the identity curve")
    ap.add_argument("--verify-trials", type=int, default=60000,
                    help="matches per point in the reported table")
    args = ap.parse_args()
    return do_fit(args) if args.fit else do_report(args)


if __name__ == "__main__":
    raise SystemExit(main())
