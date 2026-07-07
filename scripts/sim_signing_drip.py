"""Faithful signing-drip simulator — the calibration harness behind
docs/AAR-recruiting-division-radar.md.

Replays the in-season recruiting drip (real `_pick_school` / `_decision_week`,
weekly quota, final mop-up) over the full national class WITHOUT simulating
matches or touching a DB, and reports week-by-week signings per division plus
the owner's invariants (sub-45-STR recruits land D2-D4; elites all sign).

NOTE: `market()` mirrors `world._recruit_market` (minus the DB-backed pro-spend
deduction and the local-territory tables). If you change what the live market
dict carries, update this mirror or the sim will silently diverge — exactly the
bug class this script exists to catch.

Usage:  python3 scripts/sim_signing_drip.py [window] e.g. 18
"""
import sys
from collections import Counter

sys.path.insert(0, ".")

from app import recruit_economy as re
from app import coaches
import app.world as W
from app.ncaa import (load_division, build_roster, _talent_from_strength,
                      roster_cap, SCHOLARSHIP_SLOTS)


def market(gender="men", salt="simsign"):
    progs = {}
    for divn in ("D1", "D2", "D3", "D4"):
        for p in load_division(divn, gender).programs:
            progs[p.school] = p
    traits = {s: (p.prestige, p.academics, p.region, p.division, p.facilities)
              for s, p in progs.items()}
    budget = {s: re.program_budget(p, salt, 0) for s, p in progs.items()}
    level_cal = {s: max(0.0, min(1.0, (_talent_from_strength(p.prestige, p.division, gender) - 20.0) / 60.0))
                 for s, p in progs.items()}
    cap = {}
    for s, p in progs.items():
        roster = build_roster(p)
        grads = sum(1 for pl in roster if W._base_class(pl.class_year) == "Sr")
        if p.division == "D1":              # D1 recruits its scholarship core ONLY
            returning = len(roster) - grads
            ret_core = sum(1 for pl in roster if not pl.walk_on
                           and W._base_class(pl.class_year) != "Sr")
            cap[s] = max(0, min(SCHOLARSHIP_SLOTS - ret_core,
                                roster_cap("D1") - returning))
        else:
            cap[s] = grads
    coachmap = {s: coaches.program_coach(s) for s in progs}
    by_pres = sorted(progs, key=lambda s: traits[s][0])
    pres_arr = [traits[s][0] for s in by_pres]
    academic_top = sorted(progs, key=lambda s: -traits[s][1])[:40]
    by_region: dict = {}
    for s in progs:
        by_region.setdefault(traits[s][2], []).append(s)
    return {"progs": progs, "traits": traits, "cap": cap, "budget": budget,
            "level_cal": level_cal, "coaches": coachmap, "by_pres": by_pres,
            "pres_arr": pres_arr, "academic_top": academic_top, "by_region": by_region}


def run(gender="men", window=18, report_weeks=(4, 8, 10, 14)):
    m = market(gender)
    klass = W.national_class(2026, 0, gender)
    strval = {p.pid: p.str_value() for p in klass}
    n = len(klass)
    denom = max(1, n - 1)
    quota = max(1, sum(m["cap"].values()) // window)
    avail = dict(m["cap"])
    signed: dict = {}
    hist = {}
    for week in range(window):
        progress = min(1.0, week / max(1, window - 1))
        cnt = 0
        for i, p in enumerate(klass):
            if cnt >= quota:
                break
            if p.pid in signed:
                continue
            if W._decision_week(p, "simsign", i / denom, window) > week:
                continue
            best = W._pick_school(p, m, avail, jitter_salt="sign", progress=progress)
            if best is None:
                continue
            avail[best] -= 1
            signed[p.pid] = best
            cnt += 1
        hist[week] = Counter(m["traits"][s][3] for s in signed.values())
    for p in klass:                          # rollover mop-up (progress 1.0)
        if p.pid in signed:
            continue
        best = W._pick_school(p, m, avail, jitter_salt="sign", progress=1.0)
        if best:
            avail[best] -= 1
            signed[p.pid] = best
    final = Counter(m["traits"][s][3] for s in signed.values())

    def row(c):
        return " ".join(f"{d}={c.get(d, 0)}" for d in ("D1", "D2", "D3", "D4"))

    for wk in report_weeks:
        if wk in hist:
            print(f"  week {wk:2d}: total={sum(hist[wk].values()):4d}  {row(hist[wk])}")
    print(f"  FINAL  : total={sum(final.values()):4d}  {row(final)}")
    elites = [p for p in klass if W.recruit_caliber(p) >= 0.70]
    esign = sum(1 for p in elites if p.pid in signed)
    print(f"  elites signed: {esign}/{len(elites)}   class signed: {len(signed)}/{n}")
    sub = [p for p in klass if strval[p.pid] <= 45.0 and p.pid in signed]
    low = sum(1 for p in sub if m["traits"][signed[p.pid]][3] in ("D2", "D3", "D4"))
    subdiv = Counter(m["traits"][signed[p.pid]][3] for p in sub)
    print(f"  STR<=45 -> D2-D4: {low}/{len(sub)} ({100 * low / max(1, len(sub)):.1f}%)  {row(subdiv)}")


if __name__ == "__main__":
    win = int(sys.argv[1]) if len(sys.argv) > 1 else 18
    print(f"=== signing-drip sim  window={win}  band={re._LEVEL_STANDARD_BAND}"
          f"  residual={re._LEVEL_RESIDUAL} ===")
    for g in ("men", "women"):
        print(g)
        run(g, window=win)
