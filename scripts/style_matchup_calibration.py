#!/usr/bin/env python3
"""Style-vs-style matchup matrix through the SHIPPED fast models — the
calibration tool for `engine.fast.STYLE_K` and the check that the style plane
realises the agreed tournament (owner rule 2026-09,
docs/AAR-style-matchup-cross-term.md).

Generates a pool of prospects per play style at one talent, pairs them across
styles at (near-)EQUAL overall, and plays each pairing both ways through
`engine.match.simulate_match(fidelity="fast")` under the college dials and the
HS profile — so the rating gap is removed and only the style term can move a
cell. Zero structure here means the term is inert; a cell far from 50 on a
pairing the tournament calls neutral means the axes are wrong.

  python3 scripts/style_matchup_calibration.py                # matrices, both profiles
  python3 scripts/style_matchup_calibration.py --k 0.3        # try another STYLE_K
  python3 scripts/style_matchup_calibration.py --doubles      # pair-vs-pair too
  python3 scripts/style_matchup_calibration.py --solve        # re-fit the axes from
                                                              #   development._STYLE_BIAS_V2

‼️ The quantity is a RATE over simulated results, so the sample is the number
of MATCHES, not of players (the JHSAA 1A pilot's lesson) — the defaults play
~1,800 matches a cell; 95% CI about ±2.3 points.
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import development as dev                     # noqa: E402
from engine import fast                                # noqa: E402
from engine.match import simulate_match                # noqa: E402
from engine.doubles import DoublesTeam, simulate_doubles  # noqa: E402

STYLES = ("counterpuncher", "all_court", "aggressive_baseliner", "serve_first", "balanced")
#: The agreed tournament: (winner, loser) at equal overall. Everything else ~50.
TOURNAMENT = (("counterpuncher", "aggressive_baseliner"),
              ("counterpuncher", "serve_first"),
              ("serve_first", "aggressive_baseliner"),
              ("aggressive_baseliner", "all_court"),
              ("all_court", "serve_first"),
              ("all_court", "counterpuncher"))
#: Target angles on the style plane (degrees) — a style beats every style
#: within a half-turn behind it, which is exactly TOURNAMENT.
ANGLES = {"counterpuncher": 0, "all_court": 90, "aggressive_baseliner": 240, "serve_first": 300}


def pool(n: int, talent: float = 48.0, maturity: float = 0.85, shape: str = "v2",
         gender: str = "male") -> dict:
    out = {s: [] for s in STYLES}
    i = 0
    while any(len(v) < n for v in out.values()):
        p = dev.generate_prospect(random.Random(1000 + i), f"P{i}", "US", gender=gender,
                                  talent=talent, maturity_range=(maturity, maturity), shape=shape)
        i += 1
        s = p.traits["play_style"]
        if len(out[s]) < n:
            out[s].append(p)
    return out


def matrix(pl: dict, profile: dict | None, seeds: int = 3, tol: float = 1.0,
           fidelity: str = "fast"):
    eng = {s: sorted(((p.current_overall(), p.engine_player()) for p in pl[s]),
                     key=lambda t: t[0]) for s in STYLES}
    cells = {}
    for ia, a in enumerate(STYLES):
        for ib, b in enumerate(STYLES):
            # ‼️ Seeds are keyed per CELL. Shared across cells, one lucky seed
            # set moves every cell the same way and the whole matrix reads
            # +2 — correlated noise that looks like a uniform bias.
            base = (ia * 7 + ib + 1) * 1_000_003
            w = n = 0
            for (oa, pa), (ob, pb) in zip(eng[a], eng[b]):
                if abs(oa - ob) > tol:
                    continue
                for k in range(seeds):
                    r = simulate_match(pa, pb, seed=base + k * 7919 + n, fidelity=fidelity, profile=profile)
                    w += (r.winner == 0); n += 1
                    r = simulate_match(pb, pa, seed=base + k * 7919 + n + 1, fidelity=fidelity, profile=profile)
                    w += (r.winner == 1); n += 1
            cells[(a, b)] = (w / n if n else float("nan"), n)
    return cells


def doubles_matrix(pl: dict, profile: dict | None, seeds: int = 2, tol: float = 0.04,
                   fidelity: str = "fast"):
    """Same-style pairs against same-style pairs (a CP+CP pair vs an AB+AB pair).
    `doubles_rating` is net/serve-weighted, so all-court and serve-first pairs
    rate ABOVE counterpuncher/baseliner pairs of the same singles level — the
    rank pairing plus a wider tolerance is what leaves those cells populated."""
    eng = {s: [p.engine_player() for p in pl[s]] for s in STYLES}
    cells = {}
    for ia, a in enumerate(STYLES):
        for ib, b in enumerate(STYLES):
            base = (ia * 7 + ib + 1) * 1_000_003
            w = n = 0
            ta = [DoublesTeam((eng[a][i], eng[a][i + 1])) for i in range(0, len(eng[a]) - 1, 2)]
            tb = [DoublesTeam((eng[b][i], eng[b][i + 1])) for i in range(0, len(eng[b]) - 1, 2)]
            ta.sort(key=lambda t: t.rating); tb.sort(key=lambda t: t.rating)
            for x, y in zip(ta, tb):
                if abs(x.rating - y.rating) > tol:
                    continue
                for k in range(seeds):
                    r = simulate_doubles(x, y, seed=base + k * 104729 + n, fidelity=fidelity, profile=profile)
                    w += (r.winner == 0); n += 1
                    r = simulate_doubles(y, x, seed=base + k * 104729 + n + 1, fidelity=fidelity, profile=profile)
                    w += (r.winner == 1); n += 1
            cells[(a, b)] = (w / n if n else float("nan"), n)
    return cells


def show(title: str, cells: dict) -> None:
    print(f"\n{title}: row style win % vs column style")
    print("%-22s" % "" + "".join("%12s" % s[:11] for s in STYLES))
    for a in STYLES:
        print("%-22s" % a + "".join("%7.1f(%4d)" % (100 * cells[(a, b)][0], cells[(a, b)][1])
                                    for b in STYLES))
    worst = min(100 * cells[(w, l)][0] for w, l in TOURNAMENT)
    print(f"  weakest agreed edge: {worst:.1f}%   (target ~56)")
    # A style's mean win % against the OTHER styles: at --k 0 this is the
    # engine's own (transitive) pricing of the shift table and must sit near 50
    # for every style — the cross term is meant to be the ONLY style effect.
    strength = {a: 100 * sum(cells[(a, b)][0] for b in STYLES if b != a) / (len(STYLES) - 1)
                for a in STYLES}
    print("  strength vs field: " + "  ".join(f"{a[:11]} {v:.1f}" for a, v in strength.items()))


def angles(pl: dict) -> None:
    """Where generated players of each style actually land on the plane."""
    for s in STYLES:
        xs, ys = zip(*(fast.style_vector(p.engine_player()) for p in pl[s]))
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        ang = math.degrees(math.atan2(my, mx)) % 360 if (mx or my) else float("nan")
        r = math.hypot(mx, my)
        spread = sum(math.hypot(x - mx, y - my) for x, y in zip(xs, ys)) / len(xs)
        print(f"  {s:22s} mean=({mx:6.3f},{my:6.3f}) angle={ang:6.1f} r={r:.3f} "
              f"scatter={spread:.3f}  target {ANGLES.get(s, '-')}")


def _cluster_devs(p) -> list[float]:
    """A generated player's cluster deviations (unit scale), the vector the
    engine's axes are applied to."""
    r = p.engine_player().rich
    means = [sum(r[n] for n in names) / len(names) for names in fast.STYLE_CLUSTERS.values()]
    c = sum(means) / len(means)
    return [m - c for m in means]


def solve(n: int = 200, ridge: float = 1e-3) -> None:
    """Re-fit STYLE_AXIS_X/Y (pure Python least squares) on the REALISED mean
    cluster deviations of generated v2 players per style — not on the raw
    shift table: the per-attribute talent noise, the weight normalisation and
    the 18% net-specialist roll all move where a label's players actually land,
    and a fit on the table alone drifted serve_first 25 degrees and shrank the
    baseliner's radius by a third. Paste the output into engine.fast."""
    cl = list(fast.STYLE_CLUSTERS)
    pl = pool(n)
    d = {}
    for s in ANGLES:
        vs = [_cluster_devs(p) for p in pl[s]]
        d[s] = [sum(v[i] for v in vs) / len(vs) for i in range(5)]
    R = 0.15                                   # target radius, unit scale

    def lin(m, v):
        n = len(m); m = [row[:] + [v[i]] for i, row in enumerate(m)]
        for i in range(n):
            piv = max(range(i, n), key=lambda r: abs(m[r][i])); m[i], m[piv] = m[piv], m[i]
            for r in range(n):
                if r != i:
                    f = m[r][i] / m[i][i]; m[r] = [a - f * b for a, b in zip(m[r], m[i])]
        return [m[i][n] / m[i][i] for i in range(n)]

    rows = [d[s] for s in ANGLES]
    tx = [R * math.cos(math.radians(ANGLES[s])) for s in ANGLES]
    ty = [R * math.sin(math.radians(ANGLES[s])) for s in ANGLES]
    lam = ridge                                # ridge: bounds the weights (a flipped
                                               # edge wants huge ones, which only
                                               # amplify per-player noise)
    ata = [[sum(r[i] * r[j] for r in rows) + (lam if i == j else 0) for j in range(5)] for i in range(5)]
    a = lin(ata, [sum(r[i] * t for r, t in zip(rows, tx)) for i in range(5)])
    b = lin(ata, [sum(r[i] * t for r, t in zip(rows, ty)) for i in range(5)])
    print("STYLE_AXIS_X =", {c: round(w, 3) for c, w in zip(cl, a)})
    print("STYLE_AXIS_Y =", {c: round(w, 3) for c, w in zip(cl, b)})
    for s in ANGLES:
        x = sum(p * q for p, q in zip(a, d[s])); y = sum(p * q for p, q in zip(b, d[s]))
        print(f"  {s:22s} angle={math.degrees(math.atan2(y, x)) % 360:6.1f} r={math.hypot(x, y):.3f} (target {ANGLES[s]})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="players per style")
    ap.add_argument("--k", type=float, default=None, help="override engine.fast.STYLE_K")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--doubles", action="store_true")
    ap.add_argument("--solve", action="store_true")
    ap.add_argument("--ridge", type=float, default=1e-3)
    ap.add_argument("--profile", choices=("hs", "college", "both"), default="both")
    ap.add_argument("--shape", choices=("v1", "v2"), default="v2",
                    help="which play-style shift table the pool is generated with")
    ap.add_argument("--fidelity", choices=("fast", "full"), default="fast",
                    help="full = the point engine (the college season's default); "
                         "its dial is engine.rally.TUNE['style_k'] / doubles.TUNE['style_k']")
    args = ap.parse_args()
    if args.solve:
        solve(ridge=args.ridge); return
    if args.k is not None:
        if args.fidelity == "full":
            from engine import rally, doubles as dbl
            rally.TUNE["style_k"] = args.k; dbl.TUNE["style_k"] = args.k
        else:
            fast.TUNE["style_k"] = args.k
    from engine import rally as _rally
    print(f"fidelity={args.fidelity}  fast STYLE_K={fast.TUNE['style_k']} (hs {fast.HS_PROFILE['style_k']})"
          f"  point-engine style_k={_rally.TUNE['style_k']}  style_fade={fast.TUNE['style_fade']}")
    pl = pool(args.n, shape=args.shape)
    print(f"\nwhere generated {args.shape} players land on the plane:")
    angles(pl)
    profiles = {"hs": fast.HS_PROFILE, "college": None}
    names = ("hs", "college") if args.profile == "both" else (args.profile,)
    if args.fidelity == "full":
        names = ("college",)          # the profile is a fast-model overlay
    for name in names:
        show(f"singles / {name} / {args.fidelity}",
             matrix(pl, profiles[name], seeds=args.seeds, fidelity=args.fidelity))
        if args.doubles:
            show(f"doubles / {name} / {args.fidelity}",
                 doubles_matrix(pl, profiles[name], fidelity=args.fidelity))


if __name__ == "__main__":
    main()
