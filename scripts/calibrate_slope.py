"""
Slope calibration sweep. Runs a D1-men regular season at several
engine.fast skill_slope values and prints the emergent favorite-win-rate
curve bucketed by UTR gap, so we can pick the slope that hits a target
curve. tb_slope is held at 0.75 * skill_slope (the original 1.65/2.2 ratio)
unless overridden.

Usage: python3 -m scripts.calibrate_slope 2.2 1.9 1.6 1.4
"""
from __future__ import annotations

import json, os, sys, time
from collections import defaultdict

import engine.fast as ef
import app.seasonmode as sm
from app.ncaa import build_roster, load_division

_STR_PER_UTR = 1.677
GAP_BUCKETS = [(0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 99)]
TARGET = {"0-0.5": "~53", "0.5-1.0": "~56", "1.0-1.5": "57-60",
          "1.5-2.0": "68-72", "2.0-3.0": "77-79", "3.0-99": "86-89"}


def run(div, gen, skill_slope, tb_slope, seed=2026):
    ef.TUNE["skill_slope"] = skill_slope
    ef.TUNE["tb_slope"] = tb_slope
    division = load_division(div, gen)
    str_by_pid = {}
    for p in division.programs:
        for pr in build_roster(p):
            str_by_pid[pr.pid] = pr.str_value()

    sm.DB_PATH = f"/tmp/cal_{div}_{gen}_{skill_slope}.db"
    if os.path.exists(sm.DB_PATH):
        os.remove(sm.DB_PATH)
    sm._forced_cache.clear()
    sid = sm.create_season(div, gen, seed=seed)
    guard = 0
    while True:
        ph = sm.load_season(sid)["phase"]
        if ph in ("conf_tournaments", "selection", "ncaa", "complete") or guard > 60:
            break
        sm.advance(sid); guard += 1

    conn = sm._db()
    rows = conn.execute("SELECT lines_json FROM duals WHERE season_id=? AND status='final'",
                        (sid,)).fetchall()
    conn.close()
    bucket = defaultdict(lambda: [0, 0])
    for r in rows:
        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed") or not str(ln.get("slot", "")).startswith("S"):
                continue
            hp, ap = ln.get("home_pid"), ln.get("away_pid")
            if hp not in str_by_pid or ap not in str_by_pid:
                continue
            sh, sa = str_by_pid[hp], str_by_pid[ap]
            gap = abs(sh - sa) / _STR_PER_UTR
            fav_won = (ln.get("home_won") == (sh >= sa))
            for lo, hi in GAP_BUCKETS:
                if lo <= gap < hi:
                    bucket[(lo, hi)][0] += int(fav_won)
                    bucket[(lo, hi)][1] += 1
                    break
    return bucket


def main(argv):
    slopes = [float(a) for a in argv if a.replace(".", "").isdigit()] or [2.2]
    tok = next((a for a in argv if ":" in a), "D1:men")
    div, gen = tok.split(":", 1)
    print(f"Calibration sweep — {div} {gen}")
    print(f"{'bucket':>9} {'target':>8} | " +
          " ".join(f"s={s:<5}" for s in slopes))
    results = {}
    for s in slopes:
        t0 = time.time()
        results[s] = run(div, gen, s, round(0.75 * s, 3))
        print(f"  (slope {s}: {time.time()-t0:.0f}s)", file=sys.stderr)
    for lo, hi in GAP_BUCKETS:
        key = f"{lo}-{hi}"
        cells = []
        for s in slopes:
            w, n = results[s][(lo, hi)]
            cells.append(f"{(w/n*100 if n else 0):>4.0f}% ")
        print(f"{key:>9} {TARGET.get(key,''):>8} | " + " ".join(cells))
    # overall
    cells = []
    for s in slopes:
        w = sum(v[0] for v in results[s].values())
        n = sum(v[1] for v in results[s].values())
        cells.append(f"{(w/n*100 if n else 0):>4.0f}% ")
    print(f"{'overall':>9} {'':>8} | " + " ".join(cells))


if __name__ == "__main__":
    main(sys.argv[1:])
