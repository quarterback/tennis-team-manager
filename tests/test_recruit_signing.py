"""Recruiting economy: funded programs are budget-aware and hold premium seats for
elite talent, so blue-chips/5★ actually sign instead of being crowded out by 3★s
rushing in early. Regression for the "elite players aren't signing" bug."""
from collections import Counter

from app import recruit_economy as re
from app.ncaa import load_division, build_roster
from app import coaches
from app.world import (national_class, _pick_school, _decision_week,
                       _base_class, recruit_caliber)


# ---- the program-side standard (pure) --------------------------------------

def test_program_caliber_floor_holds_then_relaxes():
    # A power (budget 20) courts elite talent early...
    assert re.program_caliber_floor(20.0, 0.0) == re._PROGRAM_CEILING[0][1]
    assert re.program_caliber_floor(20.0, re._STANDARD_HOLD) == re._PROGRAM_CEILING[0][1]
    # ...and fully relaxes by signing day.
    assert re.program_caliber_floor(20.0, 1.0) == 0.0
    # Monotonic non-increasing in progress.
    vals = [re.program_caliber_floor(20.0, x / 20) for x in range(21)]
    assert all(a >= b - 1e-9 for a, b in zip(vals, vals[1:]))


def test_unfunded_programs_take_anyone():
    for prog in range(0, 9):                 # D2/low budgets and below
        assert re.program_caliber_floor(float(prog), 0.0) == 0.0


# ---- integration: a full signing cycle signs the elites --------------------

def _market(gender="men", salt="recruit_test"):
    progs = {}
    for divn in ("D1", "D2", "D3", "D4"):
        for p in load_division(divn, gender).programs:
            progs[p.school] = p
    traits = {s: (p.prestige, p.academics, p.region, p.division, p.facilities)
              for s, p in progs.items()}
    budget = {s: re.program_budget(p, salt, 0) for s, p in progs.items()}
    cap = {s: sum(1 for pl in build_roster(p) if _base_class(pl.class_year) == "Sr")
           for s, p in progs.items()}
    coachmap = {s: coaches.program_coach(s) for s in progs}
    by_pres = sorted(progs, key=lambda s: traits[s][0])
    pres_arr = [traits[s][0] for s in by_pres]
    academic_top = sorted(progs, key=lambda s: -traits[s][1])[:40]
    by_region: dict = {}
    for s in progs:
        by_region.setdefault(traits[s][2], []).append(s)
    return {"progs": progs, "traits": traits, "cap": cap, "budget": budget,
            "coaches": coachmap, "by_pres": by_pres, "pres_arr": pres_arr,
            "academic_top": academic_top, "by_region": by_region}


def _run_cycle(market, klass, window=26):
    n = len(klass)
    avail = dict(market["cap"])
    signed: dict = {}
    for week in range(window):
        progress = week / max(1, window - 1)
        for i, p in enumerate(klass):
            if p.pid in signed:
                continue
            if _decision_week(p, "recruit_test", i / max(1, n - 1), window) > week:
                continue
            best = _pick_school(p, market, avail, jitter_salt="sign", progress=progress)
            if best is None:
                continue
            avail[best] -= 1
            signed[p.pid] = best
    for p in klass:                           # signing-day mop-up (progress 1.0)
        if p.pid in signed:
            continue
        best = _pick_school(p, market, avail, jitter_salt="sign")
        if best:
            avail[best] -= 1
            signed[p.pid] = best
    return signed


def test_elite_recruits_sign():
    """Fog of war: the market signs whom it PERCEIVES as elite, and no genuinely
    good player VANISHES — an under-scouted true elite slides DOWN a level rather
    than going unsigned. (True caliber no longer guarantees an elite TIER; the AI
    acts on perceived caliber. See docs/AAR-fog-of-war-recruiting.md.)"""
    from app.recruiting import consensus_caliber
    market = _market()
    klass = national_class(2026, 0, "men")
    signed = _run_cycle(market, klass)

    def rate(lo, hi, cal_fn):
        grp = [p for p in klass if lo <= cal_fn(p) < hi]
        if not grp:
            return 1.0
        return sum(1 for p in grp if p.pid in signed) / len(grp)

    # The one invariant that matters under fog of war: no genuinely good player
    # VANISHES. True caliber no longer guarantees an elite TIER (the AI acts on
    # perceived caliber, so an over-scouted bust takes a premium seat and an
    # under-scouted gem slides down), but everyone good still lands somewhere.
    assert rate(0.70, 9.0, recruit_caliber) >= 0.90, "true elites sign somewhere"
    assert rate(0.0, 9.0, recruit_caliber) >= 0.95, "essentially everyone signs"
