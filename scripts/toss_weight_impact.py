#!/usr/bin/env python3
"""What the per-division TOSS flight weights did to the NCAA field and the S-curve.

Plays one season per division x gender to the SELECTION phase (nothing locked yet),
then runs the real selection path TWICE over the same results:

  OLD  the CLASSIC 6+3 table + the 0.30 fallback every court past #6 used to hit
  NEW  rating.DIVISION_WEIGHTS[div]

Everything downstream is the shipped code -- compute_ratings, committee_seed_score,
select_field, regions.scurve_regions -- so the deltas are the ones the app would show.
Re-implementing selection here would have measured the re-implementation.

Kept because the AAR's own lesson needs it: validate a rating change on the SEEDS,
not the cutline. This run moved 92% of D1 programs and reseeded 61% of the field
while changing tournament MEMBERSHIP by one team, so checking who made the field
would have reported a rounding error. See
docs/AAR-toss-per-division-flight-weights.md for the numbers this produced.

Run: python3 scripts/toss_weight_impact.py [db-path]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["GEN_WORKERS"] = "1"
os.environ["PTC_NO_BOOT_WARM"] = "1"
if len(sys.argv) > 1:
    os.environ["TENNIS_DB_PATH"] = sys.argv[1]

import app.rating as rt
import app.seasonmode as sm
from app.bracket import select_field
from app.regions import scurve_regions

CLASSIC = dict(rt.FLIGHT_WEIGHTS)
_real_flight_score = rt._flight_score
_real_weights_for = sm.weights_for


def _old_flight_score(lines, side, weights=None):
    """`_flight_score` as it was before the per-division tables: unknown court -> 0.30."""
    earned = total = 0.0
    w_table = CLASSIC if weights is None else weights
    for ln in lines:
        w = w_table.get(ln["slot"], 0.3)
        total += w
        won = ln["home_won"] if side == "home" else not ln["home_won"]
        if won:
            earned += w
    return earned / total if total else None


class old_rating:
    def __enter__(self):
        rt._flight_score = _old_flight_score
        sm.weights_for = lambda div: None          # -> CLASSIC table
        sm._pi_cache.clear()

    def __exit__(self, *a):
        rt._flight_score = _real_flight_score
        sm.weights_for = _real_weights_for
        sm._pi_cache.clear()


def selection(sid: int, div: str):
    """(field schools in seed order, {school: committee score}, ratings) -- the real path."""
    conn = sm._db()
    ratings = sm.compute_ratings(sm._completed(conn, sid, sm.SEED_ROUNDS),
                                 weights=sm.weights_for(div))
    dv = sm.load_division(div, sm.load_season(sid)["gender"])
    progs = {p.school: p for p in dv.programs}
    champions = [progs[v] for v in sm.conf_champions(sid) if v in progs and v in ratings]
    score = sm.committee_seed_score(sid, {c.school for c in champions})
    seeded, _ab = select_field(dv.programs, ratings, champions,
                               size=sm.field_for_division(div), score=score)
    conn.close()
    return [p.school for p in seeded], score, ratings


def rank_map(ratings):
    return {s: i + 1 for i, s in enumerate(
        sorted(ratings, key=lambda x: ratings[x].pi_raw, reverse=True))}


def run(div, gender, seed=9100):
    sid = sm.get_or_create(div, gender, seed=seed)
    guard = 0
    while sm.load_season(sid)["phase"] not in ("selection", "ncaa", "complete") and guard < 140:
        sm.advance(sid)
        guard += 1
    ph = sm.load_season(sid)["phase"]
    if ph != "selection":
        return {"div": div, "gender": gender, "error": f"stalled in {ph}"}

    new_field, new_score, new_r = selection(sid, div)
    with old_rating():
        old_field, old_score, old_r = selection(sid, div)

    nr, orank = rank_map(new_r), rank_map(old_r)
    common = [s for s in nr if s in orank]
    deltas = sorted(abs(nr[s] - orank[s]) for s in common)
    moved = [s for s in common if nr[s] != orank[s]]

    ntop, otop = (sorted(nr, key=nr.get)[:25], sorted(orank, key=orank.get)[:25])

    ins = [s for s in new_field if s not in set(old_field)]
    outs = [s for s in old_field if s not in set(new_field)]

    n_seed = {s: i + 1 for i, s in enumerate(new_field)}
    o_seed = {s: i + 1 for i, s in enumerate(old_field)}
    both = [s for s in new_field if s in o_seed]
    seed_moved = [s for s in both if n_seed[s] != o_seed[s]]
    # "moved a seed line" -- four positions, the width of one line in a 4-region draw.
    big = [s for s in both if abs(n_seed[s] - o_seed[s]) >= 4]

    nreg = {t: r for r, m in enumerate(scurve_regions(new_field)) for t in m}
    oreg = {t: r for r, m in enumerate(scurve_regions(old_field)) for t in m}
    reg_moved = [s for s in both if s in nreg and s in oreg and nreg[s] != oreg[s]]

    return {
        "div": div, "gender": gender, "rated": len(nr), "field": len(new_field),
        "pi_moved": len(moved), "pi_mean": sum(deltas) / len(deltas) if deltas else 0,
        "pi_med": deltas[len(deltas) // 2] if deltas else 0,
        "pi_max": deltas[-1] if deltas else 0,
        "top25_churn": len(set(ntop) ^ set(otop)) // 2,
        "seed_moved": len(seed_moved), "seed_big": len(big),
        "reg_moved": len(reg_moved),
        "ins": [(s, o_seed.get(s), n_seed[s], orank.get(s), nr[s]) for s in ins],
        "outs": [(s, o_seed[s], None, orank.get(s), nr.get(s)) for s in outs],
        "biggest": sorted(((abs(nr[s] - orank[s]), s, orank[s], nr[s]) for s in common),
                          reverse=True)[:6],
    }


def main():
    rows = []
    for div in ("D1", "D2", "D3", "D4"):
        for gender in ("men", "women"):
            try:
                r = run(div, gender)
            except Exception as e:
                import traceback
                traceback.print_exc(limit=4)
                r = {"div": div, "gender": gender, "error": f"{type(e).__name__}: {e}"}
            rows.append(r)
            print(json.dumps(r), flush=True)
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
