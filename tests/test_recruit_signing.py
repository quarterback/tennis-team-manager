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


# ---- the division radar (level floor, pure) ---------------------------------

def test_program_level_floor_holds_then_keeps_residual():
    lc = 0.65                                # a low-D1 program's level
    floor0 = re.program_level_floor(lc, 0.0)
    assert floor0 == lc - re._LEVEL_STANDARD_BAND
    assert re.program_level_floor(lc, re._STANDARD_HOLD) == floor0
    # Signing day: ramps DOWN to the residual — never to zero — so a power
    # sops up only the best leftovers instead of stuffing sub-level recruits
    # into its open seats.
    assert abs(re.program_level_floor(lc, 1.0) - floor0 * re._LEVEL_RESIDUAL) < 1e-9
    assert re.program_level_floor(lc, 1.0) > 0.0
    # Monotonic non-increasing in progress; None (no level) gates nothing.
    vals = [re.program_level_floor(lc, x / 20) for x in range(21)]
    assert all(a >= b - 1e-9 for a, b in zip(vals, vals[1:]))
    assert re.program_level_floor(None, 0.0) == 0.0


# ---- integration: a full signing cycle signs the elites --------------------

def _market(gender="men", salt="recruit_test"):
    from app.ncaa import _talent_from_strength, roster_cap, SCHOLARSHIP_SLOTS
    progs = {}
    for divn in ("D1", "D2", "D3", "D4"):
        for p in load_division(divn, gender).programs:
            progs[p.school] = p
    traits = {s: (p.prestige, p.academics, p.region, p.division, p.facilities)
              for s, p in progs.items()}
    budget = {s: re.program_budget(p, salt, 0) for s, p in progs.items()}
    level_cal = {s: max(0.0, min(1.0, (_talent_from_strength(p.strength, p.division, gender) - 20.0) / 60.0))
                 for s, p in progs.items()}
    cap = {}
    for s, p in progs.items():
        roster = build_roster(p)
        grads = sum(1 for pl in roster if _base_class(pl.class_year) == "Sr")
        if p.division == "D1":              # D1 recruits its scholarship core ONLY
            returning = len(roster) - grads
            ret_core = sum(1 for pl in roster if not pl.walk_on
                           and _base_class(pl.class_year) != "Sr")
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
            "level_cal": level_cal,
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

    # Division radar (owner rule — see docs/AAR-recruiting-division-radar.md):
    # sub-45-STR recruits are never on a D1's board mid-cycle and ~90%+ land in
    # D2-D4 even after the late sop-up; D3 gets real volume (it used to sign
    # NOTHING until the year-end mop-up).
    div_of = {s: market["traits"][s][3] for s in market["traits"]}
    sub45 = [p for p in klass if p.str_value() <= 45.0 and p.pid in signed]
    low = sum(1 for p in sub45 if div_of[signed[p.pid]] in ("D2", "D3", "D4"))
    assert low / max(1, len(sub45)) >= 0.90, (
        f"sub-45-STR recruits belong in D2-D4 (got {low}/{len(sub45)})")
    d3 = sum(1 for sch in signed.values() if div_of[sch] == "D3")
    assert d3 >= 100, f"D3 signs a real share of the class (got {d3})"


def _mini_territory_market():
    """A small controlled market: a Puerto Rico D2 program (a SCHOOL_LOCAL_TERRITORY
    school), a mainland power, and a mid mainland D2 — enough to show the home pull
    in isolation without the noise of the full national board."""
    traits = {
        "Puerto Rico-Bayamón": (0.35, 0.45, "", "D2", 0.4),
        "Big State":           (0.85, 0.55, "SE", "D1", 0.8),
        "Mid U":               (0.45, 0.50, "SE", "D2", 0.5),
    }
    budget = {"Puerto Rico-Bayamón": 5.0, "Big State": 20.0, "Mid U": 5.0}
    by_pres = sorted(traits, key=lambda s: traits[s][0])
    return {
        "traits": traits, "budget": budget, "coaches": {s: None for s in traits},
        "by_pres": by_pres, "pres_arr": [traits[s][0] for s in by_pres],
        "academic_top": [], "by_region": {"": ["Puerto Rico-Bayamón"],
                                          "SE": ["Big State", "Mid U"]},
        "local_terr": {"Puerto Rico-Bayamón": ("PR", 0.85)},
        "local_by_abbr": {"PR": ["Puerto Rico-Bayamón"]},
    }


def _pr_recruit(talent, i):
    from app.development import generate_prospect
    import random
    p = generate_prospect(random.Random(500 + i), "Ana Rivera", "US",
                          gender="women", talent=talent, pid=f"prtest{i}")
    p.hometown = "San Juan, PR"
    p.region = "PR"
    p.domestic = True
    p.homecooking = 0.5
    return p


def _pr_local_rate(market, talent, n=40):
    home = 0
    for i in range(n):
        avail = {s: 5 for s in market["traits"]}
        if _pick_school(_pr_recruit(talent, i), market, dict(avail),
                        jitter_salt="sign") == "Puerto Rico-Bayamón":
            home += 1
    return home / n


def test_local_territory_pull_binds_locals_but_not_elites():
    """The home pull materially raises how often a mid/low Puerto Rico recruit signs
    the PR program, versus the same market with no pull — while a genuine elite still
    escapes to the mainland power (the low-budget D2 can't fund a blue-chip, so the
    budget floor gates it regardless of the pull)."""
    market = _mini_territory_market()
    no_pull = dict(market, local_terr={}, local_by_abbr={})    # same board, pull off

    mid_with = _pr_local_rate(market, 44.0)
    mid_without = _pr_local_rate(no_pull, 44.0)
    assert mid_with > mid_without + 0.20, (
        f"home pull should lift local signing (with={mid_with}, without={mid_without})")
    assert mid_with >= 0.5, f"a mid PR recruit signs home a solid share (got {mid_with})"

    # An elite still escapes to the power even with the pull on.
    elite_home = _pr_local_rate(market, 78.0)
    assert elite_home < 0.35, f"elite PR recruits escape to the mainland (got {elite_home})"
