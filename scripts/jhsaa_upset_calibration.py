"""
JHSAA upset-calibration Monte Carlo — upset rate and score distribution by
EFFECTIVE-strength gap, for the state (1S/4D) and regular (5S/2D) formats.

"Effective strength" is read off the actual engine inputs the fast model plays
on — the #1 singles player's `Player.overall` and each doubles pair's
`engine.doubles.doubles_rating` — never OVR/STR/TOSS, which are display and
seeding layers. Team pairs are REAL rosters (`jhsaa.build_roster` across every
classification, untouched), binned by the per-line-averaged gap, so the table
measures the match model at the gaps the association actually produces.

Also prints the per-LINE curves (a singles match and a doubles match under the
high-school format, win prob vs gap) — the dual table is just these composed —
and, with --seasons, an end-to-end check: full seasons' postseason duals binned
the same way, plus how well season records track underlying strength (the
records/TOSS side of the same variance dial: the flatter the match model, the
less a 27-4 record means).

Usage:
    python3 scripts/jhsaa_upset_calibration.py                # matchup grid
    python3 scripts/jhsaa_upset_calibration.py --seasons 2    # + full seasons
    python3 scripts/jhsaa_upset_calibration.py --accel 0      # legacy (no hinge)

`--accel/--knee` override engine.fast.TUNE's gap-response keys so before/after
tables come from one script run twice.
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
from collections import Counter, defaultdict

# Importable whether run as a script or with -m (see eval_realism.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine.fast as ef
from engine.doubles import doubles_rating
from engine.dual import simulate_dual
from app import jhsaa

GAP_BINS = [(0.00, 0.025), (0.025, 0.05), (0.05, 0.075), (0.075, 0.10),
            (0.10, 0.15), (0.15, 0.20), (0.20, 0.35)]
PAIRS_PER_BIN = 14
SEEDS_PER_PAIR = 50


def eff(ts, phase: str) -> float:
    """Per-line-averaged effective strength for `phase`'s dual shape: the
    exact numbers the fast model's hold curves read, off the lineup that
    format actually dresses. Phase-matched on purpose — the two formats put
    different players on singles vs doubles (a doubles-archetype lift covers
    4/5 of the state format but only 2/7 of the regular one), so binning
    regular duals by state strength would group them by the wrong inputs."""
    f = jhsaa.dual_format(phase)
    lu = jhsaa._order(ts)[:jhsaa.lineup_need(phase)]
    sq = jhsaa._squad(ts, phase, lu)
    ss = [sq.singles[i].overall for i in range(f.n_singles)]
    ds = [doubles_rating(sq.doubles_players[2 * i], sq.doubles_players[2 * i + 1])
          for i in range(f.n_doubles)]
    return (sum(ss) + sum(ds)) / (f.n_singles + f.n_doubles)


def eff_state(ts) -> float:
    return eff(ts, "state")


def build_teams(gender: str, year: int, salt: str, phase: str = "state"):
    teams = [jhsaa.TeamSeason(school=s, roster=jhsaa.build_roster(s, year, salt))
             for s in jhsaa.load_schools(gender)]
    return sorted(teams, key=lambda t: -eff(t, phase))


def sample_pairs(teams, rng, phase: str):
    """Real team pairs per gap bin (favorite first), by `phase`-format strength."""
    eff_by = {id(t): eff(t, phase) for t in teams}
    by_bin = defaultdict(list)
    idx = list(range(len(teams)))
    for _ in range(60000):
        i, j = rng.sample(idx, 2)
        a, b = teams[i], teams[j]
        if eff_by[id(a)] < eff_by[id(b)]:
            a, b = b, a
        gap = eff_by[id(a)] - eff_by[id(b)]
        for k, (lo, hi) in enumerate(GAP_BINS):
            if lo <= gap < hi and len(by_bin[k]) < PAIRS_PER_BIN:
                by_bin[k].append((a, b, gap))
        if all(len(by_bin[k]) >= PAIRS_PER_BIN for k in range(len(GAP_BINS))):
            break
    return by_bin


def play(a, b, phase, seed):
    lrng = random.Random(f"lineup|{seed}")
    la, lb = jhsaa._lineup(a, phase, lrng), jhsaa._lineup(b, phase, lrng)
    return simulate_dual(jhsaa._squad(a, phase, la), jhsaa._squad(b, phase, lb),
                         seed=seed, play_all=True, fidelity=jhsaa.FIDELITY,
                         dual_fmt=jhsaa.dual_format(phase),
                         singles_fmt=jhsaa.MATCH_FORMAT,
                         doubles_fmt=jhsaa.MATCH_FORMAT)


def grid(gender: str, year: int, salt: str, phase: str) -> None:
    teams = build_teams(gender, year, salt, phase)
    by_bin = sample_pairs(teams, random.Random(20270813), phase)
    total = jhsaa.dual_format(phase).total_points
    print(f"\n=== {phase} format ({jhsaa.dual_format(phase).n_singles}S/"
          f"{jhsaa.dual_format(phase).n_doubles}D, {total} pts) — {gender} {year} ===")
    print(f"{'eff gap':>12} {'duals':>6} {'upset%':>7}  underdog-win scores"
          f"{'':14} favorite-win scores")
    for k, (lo, hi) in enumerate(GAP_BINS):
        pairs = by_bin.get(k, ())
        if not pairs:
            continue
        n = ups = 0
        u_scores, f_scores = Counter(), Counter()
        for p_i, (a, b, gap) in enumerate(pairs):
            for s in range(SEEDS_PER_PAIR):
                res = play(a, b, phase, seed=1_000_003 * p_i + 7919 * s + k)
                n += 1
                sc = (max(res.home_points, res.away_points),
                      min(res.home_points, res.away_points))
                if res.winner == 1:      # b (the underdog) is away
                    ups += 1
                    u_scores[sc] += 1
                else:
                    f_scores[sc] += 1
        fmt_sc = lambda c: " ".join(f"{a}-{b}:{v}" for (a, b), v in sorted(c.items(), reverse=True))  # noqa: E731
        print(f"{lo:>5.3f}-{hi:<5.3f} {n:>6} {100 * ups / n:>6.1f}%  "
              f"{fmt_sc(u_scores):<34} {fmt_sc(f_scores)}")


def line_curves(gender: str, year: int, salt: str) -> None:
    """Win prob of one singles / one doubles MATCH vs gap, high-school format —
    the primitive the dual tables compose."""
    from engine.match import simulate_match
    from engine.doubles import simulate_doubles, DoublesTeam
    teams = build_teams(gender, year, salt)
    players = [p for t in teams[::7] for p in jhsaa._order(t)[:9]]
    eng = [(p.engine_player()) for p in players]
    rng = random.Random(99)
    print("\n=== per-line curves (high-school best-of-3) ===")
    print(f"{'gap':>12} {'singles fav%':>12} {'doubles fav%':>12}")
    for lo, hi in GAP_BINS:
        sn = sw = dn = dw = 0
        for _ in range(4000):
            a, b = rng.sample(eng, 2)
            g = a.overall - b.overall
            if abs(g) < lo or abs(g) >= hi:
                continue
            if g < 0:
                a, b = b, a
            r = simulate_match(a, b, seed=rng.randrange(1 << 30),
                               fmt=jhsaa.MATCH_FORMAT, fidelity="fast")
            sn += 1
            sw += 1 if r.winner == 0 else 0
        for _ in range(4000):
            p = rng.sample(eng, 4)
            t0, t1 = DoublesTeam(players=(p[0], p[1])), DoublesTeam(players=(p[2], p[3]))
            g = t0.rating - t1.rating
            if abs(g) < lo or abs(g) >= hi:
                continue
            if g < 0:
                t0, t1 = t1, t0
            r = simulate_doubles(t0, t1, seed=rng.randrange(1 << 30),
                                 fmt=jhsaa.MATCH_FORMAT, fidelity="fast")
            dn += 1
            dw += 1 if r.winner == 0 else 0
        print(f"{lo:>5.3f}-{hi:<5.3f} "
              f"{100 * sw / sn if sn else float('nan'):>11.1f}% "
              f"{100 * dw / dn if dn else float('nan'):>11.1f}%   (n={sn}/{dn})")


def seasons(gender: str, year: int, n: int) -> None:
    """End-to-end: full seasons — postseason upsets by underlying gap, and how
    records track underlying strength (rank correlation)."""
    import math
    print(f"\n=== full seasons ({gender}, {n} salts) ===")
    agg = defaultdict(lambda: [0, 0, Counter()])
    corrs = []
    for w in range(n):
        salt = f"cal{w}"
        jhsaa._season_cache.clear()
        season = jhsaa.run_season(gender, year, seed=0, salt=salt)
        teams = season["teams"]
        eff = {nme: eff_state(ts) for nme, ts in teams.items()}
        # record rank vs eff rank correlation (Spearman via rank Pearson)
        names = list(teams)
        rrank = {nme: i for i, nme in enumerate(sorted(names, key=lambda x: -teams[x].win_pct))}
        erank = {nme: i for i, nme in enumerate(sorted(names, key=lambda x: -eff[x]))}
        xs, ys = [rrank[nme] for nme in names], [erank[nme] for nme in names]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        corrs.append(sum((a - mx) * (b - my) for a, b in zip(xs, ys))
                     / math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)))
        for nme, ts in teams.items():
            for d in ts.schedule:
                if d["phase"] not in jhsaa.POSTSEASON or not d["home"]:
                    continue
                g = eff[nme] - eff.get(d["opp"], 0.0)
                gap = abs(g)
                upset = (g < 0 and d["won"]) or (g > 0 and not d["won"])
                for k, (lo, hi) in enumerate(GAP_BINS):
                    if lo <= gap < hi:
                        agg[k][0] += 1
                        agg[k][1] += int(upset)
                        if upset:
                            agg[k][2][(max(d["pf"], d["pa"]), min(d["pf"], d["pa"]))] += 1
    print(f"record-rank vs strength-rank correlation: "
          f"{statistics.mean(corrs):.3f} (per season: {[round(c, 3) for c in corrs]})")
    print("postseason duals by underlying gap:")
    for k, (lo, hi) in enumerate(GAP_BINS):
        n_, u, sc = agg.get(k, (0, 0, Counter()))
        if not n_:
            continue
        print(f"  {lo:.3f}-{hi:.3f}: {n_:4d} duals, upsets {u:3d} "
              f"({100 * u / n_:.0f}%)  {dict(sc)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gender", default="boys")
    ap.add_argument("--year", type=int, default=2027)
    ap.add_argument("--salt", default="")
    ap.add_argument("--knee", type=float, default=None,
                    help="override engine.fast.TUNE['gap_knee']")
    ap.add_argument("--accel", type=float, default=None,
                    help="override engine.fast.TUNE['gap_accel'] (0 = legacy linear)")
    ap.add_argument("--seasons", type=int, default=0,
                    help="also run N full seasons end-to-end (slow: ~45s each)")
    ap.add_argument("--lines", action="store_true", help="also print per-line curves")
    args = ap.parse_args()
    if args.knee is not None:
        ef.TUNE["gap_knee"] = args.knee
    if args.accel is not None:
        ef.TUNE["gap_accel"] = args.accel
    print(f"gap response: knee={ef.TUNE.get('gap_knee')} accel={ef.TUNE.get('gap_accel')}")
    grid(args.gender, args.year, args.salt, "state")
    grid(args.gender, args.year, args.salt, "regular")
    if args.lines:
        line_curves(args.gender, args.year, args.salt)
    if args.seasons:
        seasons(args.gender, args.year, args.seasons)


if __name__ == "__main__":
    main()
