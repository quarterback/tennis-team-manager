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

# Star tier -> (scholarship cost, men's talent-grade center). Women run lower
# (GRADE_OFFSET below). 2★/1★ are free depth pieces; blue-chips eat the most.
#   tier key   stars  cost  men-grade(~UTR)
TIERS = [
    ("Blue Chip", 5, 3.0, 70.0),   # ~UTR 14
    ("5-Star",    5, 2.0, 64.5),   # ~UTR 12.5
    ("4-Star",    4, 1.5, 58.7),   # ~UTR 11
    ("3-Star",    3, 1.0, 52.9),   # ~UTR 9.5
    ("2-Star",    2, 0.0, 47.0),   # ~UTR 8   (free depth)
    ("1-Star",    1, 0.0, 41.0),   # ~UTR 6.7 (free walk-on)
]
_GRADE_OFFSET = {"men": 0.0, "women": -9.0}   # women's grades sit a tier lower

# A program must clear a budget FLOOR to attract a tier at all — not just afford
# the cost. This is what makes blue-chips cluster: only programs funded ~14+
# (powers) can land them; 5★ need ~10.5 (powers/high-majors); 4★ need ~8.5; 3★
# and below go anywhere. So a budget-8 program can't simply buy two blue-chips.
_TIER_FLOOR = {"Blue Chip": 13.5, "5-Star": 10.5, "4-Star": 8.5, "3-Star": 0.0}

# Budget bands by D1 prestige tier (scholarship equivalency); D2 lower; D3 none.
# (low, high) — placed within the band by the program's prestige + a per-world
# random jitter so funding varies run to run.
_D1_BANDS = [
    (0.79, 14.0, 16.0),   # power
    (0.62, 12.0, 14.0),   # high-major
    (0.50, 10.0, 12.0),   # mid-major
    (0.00,  8.0, 10.0),   # low-major
]
_D2_BAND = (4.0, 8.0)


def _free_fill_stars(prestige: float, division: str) -> str:
    """Depth pieces a program fills the bottom of the roster with once the budget
    is spent. Better programs still attract a higher floor (2★ vs 1★)."""
    if division == "D1" and prestige >= 0.62:
        return "2-Star"
    return "1-Star"


def program_budget(program, salt: str = "") -> float:
    """Recruiting budget for a program: a prestige-banded base plus a small,
    deterministic per-world jitter (so each sim funds slightly differently)."""
    div = program.division
    if div == "D3":
        return 0.0
    pres = float(getattr(program, "prestige", 0.5))
    if div == "D2":
        lo, hi = _D2_BAND
        frac = max(0.0, min(1.0, (pres - 0.40) / 0.30))
    else:  # D1
        lo, hi = next((l, h) for cut, l, h in _D1_BANDS if pres >= cut)
        # position within the band by where the program sits inside its tier
        frac = 0.5
        for cut, l, h in _D1_BANDS:
            if pres >= cut:
                span = 0.97 - cut
                frac = max(0.0, min(1.0, (pres - cut) / span)) if span > 0 else 0.5
                break
    base = lo + frac * (hi - lo)
    jit = random.Random(f"{salt}|budget|{program.key}").uniform(-1.0, 1.0)
    return max(0.0, base + jit)


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
    if caliber >= 0.70:          # 5★ / blue-chip
        return 13.5
    if caliber >= 0.62:          # high 4★ / low 5★
        return 10.5
    if caliber >= 0.55:          # 4★
        return 8.5
    return 0.0


def tier_grade(tier_name: str, gender: str, rng: random.Random) -> float:
    """A talent grade drawn for a star tier, calibrated to the UTR ladder. Women
    sit a tier lower. Small gauss spread so same-tier players aren't identical."""
    grade = next(g for (name, _s, _c, g) in TIERS if name == tier_name)
    grade += _GRADE_OFFSET.get(gender, 0.0)
    return max(24.0, min(80.0, rng.gauss(grade, 2.0)))
