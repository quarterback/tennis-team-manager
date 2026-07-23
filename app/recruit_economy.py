"""
Recruiting budget economy — how talent clusters at the programs that can pay.

Each program gets a recruiting **budget** (scholarship equivalency) scaled by its
prestige tier, with a per-world random jitter so every sim differs. Recruits cost
budget by star tier — blue-chips are expensive, role players are free — so a
program can only stockpile elite talent if it has the budget AND the prestige to
attract it. Powers fund deep and fill with blue-chips/5★; low-majors fund thin
and fill with 3★ and walk-ons. This replaces the old flat conf-strength roster
fill, so roster quality is *earned* by where a program sits.

Talent grades per star tier are calibrated to the UTR ladder (blue-chip ≈ UTR 14,
3★ ≈ UTR 9.5, …) so team strength still lands where it should.
"""
from __future__ import annotations

import random

# Star tier -> (display stars, SCHOLARSHIP COST, men's talent-grade center).
# CANONICAL RECRUIT COSTS (in scholarships) — do NOT change without reading
# CLAUDE.md + the recruiting-economy AARs. A recruit COSTS scholarships from the
# program's recruiting budget:
#   Blue Chip = 7 · 5★ = 3.5 · 4★ = 3 · 3★ = 2 · 2★ = 1 · 1★ = free (0).
# Steep curve: a blue-chip core is a major investment, so only the deepest-funded
# powers stack them. Women run lower on talent (GRADE_OFFSET below); 1★ are the
# free walk-on depth pieces.
#   tier key   stars  cost  men-grade(~UTR)
# Compressed + lifted (talent-boost redesign): the grade gap between tiers is tight so a
# roster's 1-6 are near-equal on court (results/attributes separate them, not talent), and
# the whole ladder sits higher. A blue-blood runs ~2-3 UTR deep (not the old 7-UTR cliff),
# a low-major fields UTR ~9-12, all overlapping. See docs AAR-talent-compression.
TIERS = [
    ("Blue Chip", 5, 7.0, 74.0),   # cost 7   · ~UTR 15
    ("5-Star",    5, 3.5, 71.0),   # cost 3.5 · ~UTR 14.2
    ("4-Star",    4, 3.0, 67.0),   # cost 3   · ~UTR 13.2
    ("3-Star",    3, 2.0, 62.0),   # cost 2   · ~UTR 11.9
    ("2-Star",    2, 1.0, 56.0),   # cost 1   · ~UTR 10.3
    ("1-Star",    1, 0.0, 50.0),   # FREE     · ~UTR 8.8 (walk-on, still good)
]
_GRADE_OFFSET = {"men": 0.0, "women": -9.0}   # women's grades sit a tier lower

# A program must clear a budget FLOOR to attract a tier at all — not just afford
# the cost. This is what makes blue-chips cluster: only programs funded ~14+
# (powers) can land them; 5★ need ~10.5 (powers/high-majors); 4★ need ~8.5; 3★
# and below go anywhere. So a budget-8 program can't simply buy two blue-chips.
_TIER_FLOOR = {"Blue Chip": 16.5, "5-Star": 10.5, "4-Star": 5.0, "3-Star": 0.0}

# Budget bands by D1 conference TIER (scholarship equivalency). Tiers are the
# master hierarchy (ncaa.CONF_TIER); a program funds WITHIN its tier's band by its
# own prestige (so a stronger program funds higher in the band), plus a per-world
# jitter. Only the top tier redraws season to season within its wide band.
_D1_TIER_BANDS = {
    "top":   (16.0, 33.5),   # Blue Blood — wide so the blue-bloods separate; cap raised to
    "major": ( 9.0, 16.0),   # High-major — a 5★/4★ core, the odd blue-chip reach
    "mid":   ( 6.0,  9.0),   # Mid-major — 4★/3★ core
    "low":   ( 6.0,  7.0),   # Low-major — 3★ core, thin; the floor sits just above D2
}
_D2_BAND = (4.0, 6.0)   # stabilized: D2 funds a tight 4-6, brushing D1 low-major at the top
# D4 is academic-first but IS in the scholarship economy (owner rule 2027-07): every
# D4 program funds a floor of 3, the top-academic programs 6-8, positioned by prestige.
# D4 stays weaker than D2 ON AVERAGE (most D4 sit at 3-5) even though a top D4 out-funds
# a mid D2 — because the ACADEMIC GATE below stops D4 from admitting all the talent it
# can afford, so the open divisions (D2 especially) soak up what D4 must pass on.
_D4_BAND = (3.0, 8.0)
# D4 prestige spans ~0.09 (low regional academic) to ~0.40 (NESCAC/UAA/SCIAC elites,
# lifted above the base band by the academic-conference recruiting draw). Position the
# 3-8 budget across that span so the elite academic programs spread 6-8 by brand.
_D4_PRES_LO, _D4_PRES_HI = 0.09, 0.40

# D4 admissions gate — a recruit needs a minimum test score (academic_rating, 59-99)
# to sign at a D4 program. The minimum is PER-PROGRAM (scaled by the program's academic
# profile, so a Caltech/MIT-tier school always demands a high score while a lower D4
# admits more broadly) and swings a little year to year (a lenient class admits a touch
# lower) but never below the absolute D4 floor. This is what keeps D4 distinct: it can
# AFFORD top talent but can't ADMIT all of it, so talent flows to the open divisions.
D4_MIN_FLOOR = 72       # absolute admissions floor for ANY D4 program (~SAT 1060)
D4_MIN_CEIL = 90        # a top-academic D4's strict-year minimum (~SAT 1400 — MIT never admits low)
D4_MIN_SWING = 5        # year-to-year leniency; the min never dips below D4_MIN_FLOOR
# D4 program academics span roughly 0.60 (regional academic) to 0.99 (MIT/Caltech);
# normalize the gate across that so the least-selective D4 sits at the floor and the
# most-selective at the ceiling (a real spread, not everyone bunched high).
_D4_ACAD_LO, _D4_ACAD_HI = 0.60, 0.99


def d4_academic_min(program, year: int = 0, salt: str = "") -> float:
    """Minimum admissions index (59-99) a recruit needs to sign at this D4 program."""
    acad = float(getattr(program, "academics", 0.5))
    acad_n = max(0.0, min(1.0, (acad - _D4_ACAD_LO) / (_D4_ACAD_HI - _D4_ACAD_LO)))
    base = D4_MIN_FLOOR + (D4_MIN_CEIL - D4_MIN_FLOOR) * acad_n
    swing = random.Random(f"{salt}|d4acad|{program.key}|{year}").uniform(0.0, D4_MIN_SWING)
    return max(float(D4_MIN_FLOOR), base - swing)

# A program whose OWN prestige outranks its conference tier funds UP to its prestige
# tier — so a program genuinely better than its league isn't capped by it (the
# decoupling lever: give such a school a PRESTIGE_SCHOOLS bump big enough to cross a
# cut, or an editor prestige override). Normally a program's prestige matches its
# conf tier (CONF_PRESTIGE is re-leveled to agree), so this is a no-op. Cuts sit in
# the gaps between the re-leveled tier prestige bands.
_TIER_RANK = {"low": 0, "mid": 1, "major": 2, "top": 3}
_PRESTIGE_TIER_CUTS = ((0.82, "top"), (0.685, "major"), (0.565, "mid"), (0.0, "low"))


def _prestige_tier(prestige: float) -> str:
    return next(t for cut, t in _PRESTIGE_TIER_CUTS if prestige >= cut)
# Standout D2 programs (Barry/Washburn-tier) fully fund — they max their
# scholarships every year, so the per-world jitter never drops them off the
# 4-star floor. Keyed to the D2 recruiting-prestige scale.
_ELITE_D2_PRESTIGE = 0.28   # top of the D2 prestige band (0.20-0.30)

# D3/D4 carry no athletic money EXCEPT a thin 1-3 allocation for the very top, so a
# handful of programs can "sop up hidden gems" (out-recruit their peers for one
# undervalued player). Who qualifies:
#   • D4 — the academic-elite leagues/flagships (academics ≥ 0.85), which ARE tagged.
#   • D3 — academic conferences aren't tagged in D3 anymore, so cap it to the top
#     programs by prestige in the division (recomputed per save, so overrides count).
#     The gem pool scales with the division: max(50, 15% of D3 programs), so adding
#     conferences (or a per-save prestige shuffle) doesn't over-squeeze it, and the
#     hidden-gem hunt is spread across the country rather than a tiny elite.
_D3D4_BAND = (1.0, 3.0)
_D3_TOP_MIN = 50
_D3_TOP_FRAC = 0.15
_ELITE_D3D4_ACADEMICS = 0.85   # matches scholarships.ELITE_D3_ACADEMICS
_d3_top_cache: dict = {}


def _d3_top_keys(gender: str) -> set:
    g = gender or "men"
    if g not in _d3_top_cache:
        from .ncaa import load_division
        progs = load_division("D3", g).programs
        n = max(_D3_TOP_MIN, round(len(progs) * _D3_TOP_FRAC))
        top = sorted(progs, key=lambda p: float(getattr(p, "prestige", 0.0)),
                     reverse=True)[:n]
        _d3_top_cache[g] = {p.key for p in top}
    return _d3_top_cache[g]


def reset_d3_top_cache() -> None:
    _d3_top_cache.clear()


def _d3d4_funded(program) -> bool:
    """Whether a D3 program gets the thin gem-hunting allocation. D4 is now in the
    FULL scholarship economy (see program_budget) — it never uses this thin path."""
    if program.division == "D3":
        return program.key in _d3_top_keys(getattr(program, "gender", "men"))
    return False


def _free_fill_stars(prestige: float, division: str) -> str:
    """Depth pieces a program fills the bottom of the roster with once the budget
    is spent. Better programs still attract a higher floor (2★ vs 1★)."""
    if division == "D1" and prestige >= 0.62:
        return "2-Star"
    return "1-Star"


def program_budget(program, salt: str = "", year: int = 0) -> float:
    """Recruiting budget for a program: its conference TIER sets the band, the
    program's own prestige positions it within the band, and a per-world jitter
    varies funding run to run. Only the top tier (Blue Bloods) redraws season to
    season within its wide band. D2 is a single low band; D3/D4 carry none."""
    div = program.division
    if div == "D3":               # non-scholarship — only the top few get a thin gem allocation
        if not _d3d4_funded(program):
            return 0.0
        lo, hi = _D3D4_BAND
        pres = float(getattr(program, "prestige", 0.5))
        frac = max(0.0, min(1.0, (pres - 0.10) / (0.20 - 0.10)))   # within the D3 prestige band
        base = lo + frac * (hi - lo)
        jit = random.Random(f"{salt}|budget|{program.key}").uniform(-0.4, 0.4)
        return max(lo, min(hi, base + jit))
    pres = float(getattr(program, "prestige", 0.5))
    if div == "D4":               # academic-first, but IN the scholarship economy (3 floor, 6-8 top)
        lo, hi = _D4_BAND
        frac = max(0.0, min(1.0, (pres - _D4_PRES_LO) / (_D4_PRES_HI - _D4_PRES_LO)))
        base = lo + frac * (hi - lo)
        jit = random.Random(f"{salt}|budget|{program.key}").uniform(-0.5, 0.5)
        return max(lo, min(hi, base + jit))
    if div == "D2":
        lo, hi = _D2_BAND
        if pres >= _ELITE_D2_PRESTIGE:      # standout D2: fully funded, every year
            return hi
        frac = max(0.0, min(1.0, (pres - 0.20) / 0.10))   # D2 prestige band 0.20-0.30
        base = lo + frac * (hi - lo)
        jit = random.Random(f"{salt}|budget|{program.key}").uniform(-0.5, 0.5)
        return max(lo, base + jit)
    # D1: the budget band follows the program's PRESTIGE tier. At baseline a
    # program's prestige is re-leveled to its conference tier (so conf sets the
    # starting band), but dynamic prestige momentum then moves it BOTH ways — a
    # program that keeps overperforming funds up a tier, a sliding one funds down —
    # and a genuinely strong program in a weak league funds up regardless.
    tier = _prestige_tier(pres)
    lo, hi = _D1_TIER_BANDS.get(tier, _D1_TIER_BANDS["low"])
    frac = max(0.0, min(1.0, (pres - 0.44) / (0.97 - 0.44)))   # position by overall prestige
    base = lo + frac * (hi - lo)
    if tier == "top":
        # Blue Bloods redraw within the wide band each season (year-seeded), swing
        # scaled to the band so their funding genuinely rises and falls year to year.
        swing = (hi - lo) * 0.30
        jit = random.Random(f"{salt}|budget|{program.key}|{year}").uniform(-swing, swing)
        return max(0.0, min(hi, base + jit))
    # Every other tier holds a fixed value in its band — a per-world jitter, same
    # every season, clamped to the band floor (so "low = 6" really means ≥6).
    jit = random.Random(f"{salt}|budget|{program.key}").uniform(-0.5, 0.5)
    return max(lo, base + jit)


def roster_star_plan(program, salt: str = "", *, roster_size: int = 8,
                     schol_slots: int = 6) -> list[str]:
    """The star tiers a program lands across its roster. The funded slots are
    filled by spending the budget on the best tiers the program can afford AND
    attract (greedy, best first); the rest are free depth pieces. Returns a list
    of tier names, best → worst."""
    pres = float(getattr(program, "prestige", 0.5))
    div = program.division
    budget = program_budget(program, salt)
    paid = [(name, cost, grade) for (name, _st, cost, grade) in TIERS if cost > 0]
    plan: list[str] = []
    remaining = budget
    for _ in range(min(schol_slots, roster_size)):
        pick = None
        for name, cost, _grade in paid:                 # best tier affordable AND attainable
            if cost <= remaining + 1e-9 and budget >= _TIER_FLOOR.get(name, 1e9):
                pick = (name, cost)
                break
        if pick is None:
            break
        plan.append(pick[0])
        remaining -= pick[1]
    free = _free_fill_stars(pres, div)
    while len(plan) < roster_size:
        plan.append(free)
    return plan


def recruit_budget_floor(caliber: float) -> float:
    """The minimum program budget a recruit of this caliber will sign with — the
    running-recruiting mirror of the roster floors. A blue-chip/5★ only goes to a
    power (budget ~13.5+); a 4★ needs a funded program; 3★ and below go anywhere."""
    if caliber >= 0.62:          # 5★ / blue-chip — a Major+ budget (Blue Bloods win them via seat-holding)
        return 10.5
    if caliber >= 0.55:          # 4★ — any funded D1 program, or a top D2 (spillover)
        return 5.0
    return 0.0


# The caliber a budget tier *courts* — the program-side mirror of the recruit
# floors above. A funded program holds out for talent worthy of its money early in
# the cycle so it doesn't burn a premium seat on a walk-on-calibre 3★.
_PROGRAM_CEILING = ((16.5, 0.70), (10.5, 0.62), (8.5, 0.55))
_STANDARD_HOLD = 0.75       # hold the full standard for this fraction of the window,
                            # then ramp it to 0 by signing day so seats still fill


def program_caliber_floor(budget: float, progress: float) -> float:
    """Minimum recruit caliber a program will accept RIGHT NOW. A well-funded
    program courts blue-chips/5★ for most of the cycle (won't spend a premium seat
    on a 3★ rushing in early), holding its standard through `_STANDARD_HOLD` of the
    window, then ramping it to zero by signing day (`progress` 1.0) so seats still
    fill. Unfunded programs (ceiling 0) take anyone, always."""
    ceiling = 0.0
    for b, c in _PROGRAM_CEILING:
        if budget >= b:
            ceiling = c
            break
    if ceiling <= 0.0:
        return 0.0
    if progress <= _STANDARD_HOLD:
        return ceiling
    return ceiling * max(0.0, (1.0 - progress) / (1.0 - _STANDARD_HOLD))


# How far below its OWN level a program will reach during the main cycle. The
# level floor is the mechanism that keeps the divisions from bleeding into each
# other: a program only pursues recruits playing at (or just below) its level while
# the cycle runs, so the class tiers itself — a D1 program never even SEES a sub-D1
# recruit until the very end. Unlike the budget floor above, the level floor is
# measured against the recruit's CURRENT ability (public STR), not the scouting
# projection, so a raw kid with a huge hidden ceiling still slots to their level and
# doesn't flood D1. It holds through `_STANDARD_HOLD` of the window, then ramps to 0
# so D1 programs with open seats "sop up" the best leftovers on signing day.
_LEVEL_STANDARD_BAND = 0.06
# On signing day the level floor does NOT fully collapse — it ramps down to this
# fraction of itself. That residual is what makes a power "sop up the BEST leftovers,
# not much": with open seats late, a D1 still requires a recruit playing near its
# level, so only the strongest sub-D1 leftovers reach up. Everyone else slots to
# their division (and the power's still-empty seats fill later as pool walk-ons,
# where a sub-level kid belongs — not as a signed scholarship recruit).
_LEVEL_RESIDUAL = 0.65
# D2 reaches much further below its own level than the other divisions (owner rule
# 2027-07): it aggressively ABSORBS mid-tier talent that would otherwise sink to
# D3/D4, so it pursues recruits a wide band beneath its level from the start of the
# cycle. This is a deliberate, owner-authorized relaxation of the strict per-level
# radar for D2 only.
_D2_REACH_BAND = 0.22


def program_level_floor(level_caliber: float | None, progress: float,
                        division: str | None = None) -> float:
    """Minimum CURRENT-ability caliber a program pursues right now, from its own
    level (`level_caliber`, the program's talent-mean on the caliber scale). Holds
    at `level_caliber - band` through `_STANDARD_HOLD` of the window, then ramps DOWN
    to `_LEVEL_RESIDUAL` of that by signing day — never to 0 — so a power with open
    seats sops up only the best remaining recruits and the rest slot to their level.
    `band` is wide for D2 (`_D2_REACH_BAND`, aggressive absorption) and standard
    (`_LEVEL_STANDARD_BAND`) otherwise. See docs/AAR-recruiting-division-radar."""
    if level_caliber is None:
        return 0.0
    band = _D2_REACH_BAND if division == "D2" else _LEVEL_STANDARD_BAND
    floor = level_caliber - band
    if floor <= 0.0:
        return 0.0
    if progress <= _STANDARD_HOLD:
        return floor
    t = (progress - _STANDARD_HOLD) / (1.0 - _STANDARD_HOLD)      # 0..1 across the tail
    return floor * (1.0 - (1.0 - _LEVEL_RESIDUAL) * t)


def tier_grade(tier_name: str, gender: str, rng: random.Random) -> float:
    """A talent grade drawn for a star tier, calibrated to the UTR ladder. Women
    sit a tier lower. Small gauss spread so same-tier players aren't identical."""
    grade = next(g for (name, _s, _c, g) in TIERS if name == tier_name)
    grade += _GRADE_OFFSET.get(gender, 0.0)
    return max(24.0, min(80.0, rng.gauss(grade, 2.0)))
