"""
Realism evaluation harness for the dual-match sim engine.

This is NOT a unit test (those assert invariants/determinism). It runs full
simulated seasons and measures whether the *emergent* outcomes look like real
college tennis, per docs/match-engine-and-ratings.md §6:

  1. Favorite win-rate bucketed by talent (STR/UTR) gap  -> §4 calibration table
  2. The talent distribution in UTR-equivalent units      -> §5 "bulb" shape
  3. A handful of sanity checks (competitiveness, dual scorelines)

Usage:
    python3 scripts/eval_realism.py                 # D1 men + D1 women
    python3 scripts/eval_realism.py D1:men D2:women  # explicit list
    python3 scripts/eval_realism.py D1:men --postseason
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict

import app.seasonmode as sm
from app.ncaa import build_roster, load_division

# UTR-equivalent from the game-native STR band (31-57 spans ~15.5 UTR).
_STR_PER_UTR = 1.677


def utr(str_val: float) -> float:
    return 1.0 + (str_val - 31.0) / _STR_PER_UTR


# Real-life late-2025 UTR anchors (from the design doc) for context.
REAL_UTR = {
    ("D1", "men"):   {"p50": 14.3, "ceiling": "~14.3 avg, elites ~16"},
    ("D1", "women"): {"p50": 11.6, "ceiling": "~11.6 avg"},
    ("D2", "men"):   {"p50": None, "ceiling": "below D1"},
    ("D2", "women"): {"p50": None, "ceiling": "below D1"},
    ("D3", "men"):   {"p50": None, "ceiling": "lowest funded tier"},
    ("D3", "women"): {"p50": None, "ceiling": "lowest funded tier"},
}

GAP_BUCKETS = [(0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 99)]


def pct(vals, q):
    if not vals:
        return float("nan")
    s = sorted(vals)
    i = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[i]


def run_division(division: str, gender: str, postseason: bool, seed: int) -> dict:
    t0 = time.time()
    div = load_division(division, gender)

    # pid -> static ability STR (the "true talent" signal we bucket on) and metadata.
    str_by_pid: dict[str, float] = {}
    is_starter: dict[str, bool] = {}
    intl = total = 0
    team_no1_utr = []
    for p in div.programs:
        roster = sorted(build_roster(p), key=lambda pr: pr.current_overall(), reverse=True)
        for rank, pr in enumerate(roster):
            str_by_pid[pr.pid] = pr.str_value()
            is_starter[pr.pid] = rank < 6
            total += 1
            if not getattr(pr, "domestic", False):
                intl += 1
        if roster:
            team_no1_utr.append(utr(roster[0].str_value()))

    sid = sm.create_season(division, gender, seed=seed)
    phases = ("ita_kickoff", "ita_indoor", "fall_portal", "regular")
    if postseason:
        phases += ("conf_tournaments", "selection", "ncaa")
    guard = 0
    while sm.load_season(sid)["phase"] != "complete" and guard < 120:
        ph = sm.load_season(sid)["phase"]
        if not postseason and ph not in phases:
            break
        sm.advance(sid)
        guard += 1

    # Collect completed singles lines.
    conn = sm._db()
    rows = conn.execute(
        "SELECT lines_json FROM duals WHERE season_id=? AND status='final'", (sid,)
    ).fetchall()
    conn.close()

    bucket_fav = defaultdict(lambda: [0, 0])   # bucket -> [fav_wins, total]
    n_singles = 0
    dual_margin = defaultdict(int)             # winning team points -> count (proxy via lines)
    for r in rows:
        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed") or not str(ln.get("slot", "")).startswith("S"):
                continue
            hp, ap = ln.get("home_pid"), ln.get("away_pid")
            if hp not in str_by_pid or ap not in str_by_pid:
                continue
            sh, sa = str_by_pid[hp], str_by_pid[ap]
            gap = abs(sh - sa) / _STR_PER_UTR
            higher_home = sh >= sa
            fav_won = (ln.get("home_won") == higher_home)
            n_singles += 1
            for lo, hi in GAP_BUCKETS:
                if lo <= gap < hi:
                    bucket_fav[(lo, hi)][0] += int(fav_won)
                    bucket_fav[(lo, hi)][1] += 1
                    break

    all_utr = [utr(s) for s in str_by_pid.values()]
    starter_utr = [utr(str_by_pid[pid]) for pid, st in is_starter.items() if st]

    return {
        "division": division, "gender": gender,
        "elapsed": time.time() - t0,
        "n_players": total, "n_singles": n_singles,
        "intl_share": intl / total if total else 0.0,
        "utr_p10": pct(all_utr, 0.10), "utr_p50": pct(all_utr, 0.50),
        "utr_p90": pct(all_utr, 0.90), "utr_p99": pct(all_utr, 0.99),
        "utr_max": max(all_utr) if all_utr else float("nan"),
        "starter_p50": pct(starter_utr, 0.50),
        "no1_p50": pct(team_no1_utr, 0.50),
        "no1_top12_spread": (
            pct(sorted(team_no1_utr, reverse=True)[:12], 1.0) -
            pct(sorted(team_no1_utr, reverse=True)[:12], 0.0)
        ) if len(team_no1_utr) >= 12 else float("nan"),
        "buckets": {f"{lo}-{hi}": (w, n) for (lo, hi), (w, n) in
                    sorted(bucket_fav.items())},
    }


def fmt_report(res: dict) -> str:
    d, g = res["division"], res["gender"]
    L = []
    L.append(f"\n{'='*64}\n{d} {g}  —  {res['n_singles']} singles matches "
             f"({res['elapsed']:.0f}s)\n{'='*64}")
    real = REAL_UTR.get((d, g), {})
    L.append("Talent distribution (UTR-equivalent):")
    L.append(f"  p10={res['utr_p10']:.1f}  p50={res['utr_p50']:.1f}  "
             f"p90={res['utr_p90']:.1f}  p99={res['utr_p99']:.1f}  "
             f"max={res['utr_max']:.1f}")
    L.append(f"  starters p50={res['starter_p50']:.1f}   "
             f"team #1 p50={res['no1_p50']:.1f}   "
             f"top-12 #1 spread={res['no1_top12_spread']:.2f} UTR")
    if real.get("p50"):
        L.append(f"  (real-life ~p50 UTR {real['p50']}; {real['ceiling']})")
    L.append(f"  international share: {res['intl_share']*100:.0f}%")
    L.append("\nFavorite win-rate by UTR gap (emergent):")
    L.append(f"  {'gap':>9} {'fav%':>6} {'n':>7}")
    fav_w = fav_n = 0
    for key, (w, n) in res["buckets"].items():
        fav_w += w; fav_n += n
        rate = (w / n * 100) if n else float("nan")
        L.append(f"  {key:>9} {rate:>5.0f}% {n:>7}")
    L.append(f"  {'overall':>9} {(fav_w/fav_n*100):>5.0f}% {fav_n:>7}"
             if fav_n else "  (no matches)")
    return "\n".join(L)


def main(argv):
    targets, postseason, seed = [], False, 2026
    for a in argv:
        if a == "--postseason":
            postseason = True
        elif a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
        elif ":" in a:
            div, gen = a.split(":", 1)
            targets.append((div, gen))
    if not targets:
        targets = [("D1", "men"), ("D1", "women")]

    print(f"Realism eval — seed={seed} postseason={postseason}")
    print("Targets:", ", ".join(f"{d}:{g}" for d, g in targets))
    results = []
    for div, gen in targets:
        # fresh DB per run so seasons don't collide
        sm.DB_PATH = f"/tmp/eval_realism_{div}_{gen}.db"
        try:
            import os
            if os.path.exists(sm.DB_PATH):
                os.remove(sm.DB_PATH)
        except OSError:
            pass
        sm._forced_cache.clear()
        res = run_division(div, gen, postseason, seed)
        results.append(res)
        print(fmt_report(res))
    print("\nDone.")


if __name__ == "__main__":
    main(sys.argv[1:])
