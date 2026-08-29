"""
JHSAA scoreline-realism benchmark — the sim's set scores against REAL high
school tennis.

The target is five seasons of actual Oregon high-school results (boys + girls,
2021-25, 41,932 varsity matches / 84,238 completed standard sets:
github.com/quarterback/or-tennis-data), the dataset engine.fast.HS_PROFILE was
calibrated against. Real HS tennis is blowout-shaped — 6-0 is the most common
set and frequency falls monotonically to 7-6 — and the real shape is near-
uniform across gender and flight (boys/girls, D1-D3, S2/S3 all within ~2
points; only No. 1 singles is more lopsided, 33% 6-0), which is why one
profile serves every line.

Run it after ANY change to engine.fast, engine.doubles' fast model, the
HS_PROFILE, or the JHSAA talent tables:

    python3 scripts/jhsaa_scoreline_benchmark.py            # girls, 8 districts
    python3 scripts/jhsaa_scoreline_benchmark.py --gender boys --districts 12

It simulates real district round-robins through the SHIPPED path
(jhsaa._lineup / _squad / simulate_dual with the profile play_dual passes) and
reports:
  * the set-score histogram vs the Oregon target, with total-variation distance
  * three-set rate vs the real 13.8%
  * hold rate (read off the recorded game_flow) vs the real-world HS band
    (30-45%; the Oregon feed has no serving data, so the band is the target)
  * favorite dual-win% by per-line-average strength gap (the upset dial —
    the HS profile DELIBERATELY steepens this curve over the college one;
    see the HS_PROFILE comment in engine/fast.py)

Judge a change on the whole report, not one row — several wrong mechanisms can
reproduce any single marginal.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from collections import Counter, defaultdict
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import jhsaa
from engine.dual import simulate_dual
from engine.fast import HS_PROFILE

# Real Oregon HS target — ONE authority, shared with the in-game view
# (/jhsaa/realism reads the archive against the same numbers).
REAL_SETS = jhsaa.OREGON_SET_TARGET
REAL_THREE_SET = jhsaa.OREGON_THREE_SET
REAL_HOLD_BAND = (30.0, 45.0)  # % service games held, HS level (no OR serving data)

# Gap bins are EMPIRICAL PERCENTILES of the sampled pairings' strength gaps
# (owner rule 2026-08) — p10/p25/p50/p75/p90/p95 edges, so every report bins on
# the distribution the association actually produced rather than typed numbers.
GAP_PCTS = [10, 25, 50, 75, 90, 95]


def team_strength(ts) -> float:
    lu = jhsaa._order(ts)[:jhsaa.lineup_need("regular")]
    return sum(p.engine_player().overall for p in lu) / max(1, len(lu))


def run(gender: str, n_districts: int, trials: int, seed: int) -> None:
    rng = random.Random(seed)
    byd = defaultdict(list)
    for s in jhsaa.load_schools(gender):
        byd[(s.group, s.district)].append(s)
    districts = [v for v in byd.values() if len(v) >= 6]
    rng.shuffle(districts)
    districts = districts[:n_districts]

    teams: dict = {}

    def ts(s):
        if s.key not in teams:
            teams[s.key] = jhsaa.TeamSeason(school=s,
                                            roster=jhsaa.build_roster(s, 0, ""))
        return teams[s.key]

    setdist: Counter = Counter()
    matches = three = 0
    holds = games = 0
    by_gap: dict = defaultdict(lambda: [0, 0])  # bin -> [duals, favorite wins]

    pairs = [(a, b) for d in districts for a, b in combinations(d, 2)]
    gaps = sorted(abs(team_strength(ts(a)) - team_strength(ts(b)))
                  for a, b in pairs)
    edges = [gaps[min(len(gaps) - 1, int(p / 100 * len(gaps)))]
             for p in GAP_PCTS]
    bins = list(zip([0.0] + edges, edges + [gaps[-1] + 1e-9]))

    for a, b in pairs:
        sa, sb = team_strength(ts(a)), team_strength(ts(b))
        gap = abs(sa - sb)
        fav_home = sa >= sb
        for _ in range(trials):
            dual_seed = rng.getrandbits(32)
            lrng = random.Random(f"lineup|{dual_seed}")
            la = jhsaa._lineup(ts(a), "regular", lrng)
            lb = jhsaa._lineup(ts(b), "regular", lrng)
            res = simulate_dual(
                jhsaa._squad(ts(a), "regular", la),
                jhsaa._squad(ts(b), "regular", lb),
                seed=dual_seed, play_all=True, fidelity=jhsaa.FIDELITY,
                dual_fmt=jhsaa.dual_format("regular"),
                singles_fmt=jhsaa.MATCH_FORMAT,
                doubles_fmt=jhsaa.MATCH_FORMAT, profile=HS_PROFILE)
            for k, (lo, hi) in enumerate(bins):
                if lo <= gap < hi:
                    by_gap[k][0] += 1
                    by_gap[k][1] += (res.winner == 0) == fav_home
            for line in res.lines:
                m = line.result
                matches += 1
                three += len(m.set_scores) == 3
                for x, y in m.set_scores:
                    hi_, lo_ = max(x, y), min(x, y)
                    key = f"{hi_}-{lo_}"
                    if key in REAL_SETS:
                        setdist[key] += 1
                for flow in m.game_flow or []:
                    for srv, win in flow.get("games", []):
                        games += 1
                        holds += srv == win

    total = sum(setdist.values())
    print(f"\n=== JHSAA scoreline benchmark — {gender}, {len(districts)} "
          f"districts, {matches} line matches, {total} sets ===")
    print(f"{'set':>5} {'sim%':>6} {'real%':>6}")
    tv = 0.0
    for k, real in REAL_SETS.items():
        sim = 100 * setdist[k] / total if total else 0.0
        tv += abs(sim - real)
        print(f"{k:>5} {sim:6.1f} {real:6.1f}")
    t3 = 100 * three / matches if matches else 0.0
    hold = 100 * holds / games if games else 0.0
    print(f"total-variation distance: {tv / 2:.1f} (sum|diff| {tv:.1f})")
    print(f"three-set rate: {t3:.1f}%  (real {REAL_THREE_SET})")
    print(f"hold rate:      {hold:.1f}%  (HS band {REAL_HOLD_BAND[0]:.0f}-"
          f"{REAL_HOLD_BAND[1]:.0f})")
    print("\nfavorite dual-win% by strength-gap percentile bin "
          "(edges = p10/p25/p50/p75/p90/p95 of the sampled gaps; "
          "steeper than college BY DESIGN):")
    labels = ["<p10", "p10-25", "p25-50", "p50-75", "p75-90", "p90-95", ">p95"]
    for k, (lo, hi) in enumerate(bins):
        n, w = by_gap[k]
        if n:
            print(f"  {labels[k]:>7} ({lo:.3f}-{hi:.3f}): "
                  f"{100 * w / n:5.1f}%  ({n} duals)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gender", default="girls", choices=["girls", "boys"])
    ap.add_argument("--districts", type=int, default=8)
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--seed", type=int, default=20260828)
    a = ap.parse_args()
    run(a.gender, a.districts, a.trials, a.seed)
