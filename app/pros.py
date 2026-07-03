"""The pro tier — elite ex-pros who enter college ONLY through the transfer portal.

A small cohort a cut ABOVE blue-chips: grade 78-80 (beyond the recruit "gates" we set —
Blue Chip tops at 74 — but still inside the engine's 80 ceiling), green-badged, and shown
with a REAL STR like any other player (the whole point: see how they stack). Up to
`PRO_PER_CYCLE` per gender per portal cycle, across all three cycles.

Cost rolls within `PRO_COST` **indexed to the pro's STR relative to the cohort**, so a pro
is never priced above what some program can afford → they always get signed by somebody.

This module is the pure generator + costing core; wiring the cohort into the live portal
cycles + the green badge in the UI + persistence is the integration layer on top of it.
See docs/AAR-talent-compression.md.
"""
from __future__ import annotations

import random

from .development import generate_prospect, make_pid, overall_to_str

PRO_BADGE = "PRO"                    # green profile label (Prospect.junior_badges)
PRO_GRADE = (79.0, 80.0)            # talent at the top of the band (Blue Chip is 74); after
                                    # the attribute spread + full maturity, OVR lands ~76-79,
                                    # a clear cut above a blue-chip recruit, within the 80 cap
PRO_PER_CYCLE = (15, 20)           # up to this many per gender, per portal cycle
PRO_COST_LO, PRO_COST_HI = 8.5, 15.0

# Pros are drawn from the pro tour, which is overwhelmingly international — mirror that
# with a heavy non-US mix (the name picker fills nationalities from these weights).
_PRO_REGION_WEIGHTS = {
    "us": 0.22, "europe_western": 0.16, "europe_eastern": 0.10, "spain": 0.08,
    "south_america": 0.09, "british_isles": 0.06, "italy": 0.05, "germany": 0.05,
    "nordic": 0.04, "east_asia": 0.04, "anzac": 0.03, "serbia": 0.03, "russia": 0.03,
    "turkey": 0.02,
}


def is_pro(p) -> bool:
    """Whether a player carries the pro badge (green label, portal-only origin)."""
    return PRO_BADGE in (getattr(p, "junior_badges", None) or ())


def generate_pros(salt: str, gender: str, cycle_key: str, n: int | None = None) -> list:
    """A deterministic pro cohort for one gender in one portal cycle. Grades 78-80, pro
    badge, real STR. `cycle_key` (e.g. "2026-fall") + salt key the RNG so each cycle in
    each league is fresh but reproducible."""
    from generators import make_name_picker
    seed = f"{salt}|pros|{gender}|{cycle_key}"
    rng = random.Random(seed)
    n = n if n is not None else rng.randint(*PRO_PER_CYCLE)
    pgender = "male" if gender in ("men", "male") else "female"
    name_fn = make_name_picker(random.Random(f"{seed}|names"), gender=pgender,
                               region_weights=_PRO_REGION_WEIGHTS)
    pros = []
    for i in range(n):
        name, country = name_fn()
        grade = rng.uniform(*PRO_GRADE)
        p = generate_prospect(rng, name=name, country=country, gender=pgender,
                              talent=grade, pid=make_pid(salt, "pro", gender, cycle_key, i),
                              maturity_range=(0.98, 1.0))   # fully developed — they're pros
        p.junior_badges = list(p.junior_badges or []) + [PRO_BADGE]
        p.recruit_stars = 6            # above the 5-star ladder
        pros.append(p)
    return pros


def pro_cost(pro, cohort: list) -> float:
    """Recruiting-budget cost for a pro, indexed to their STR relative to the cohort:
    the cohort's best pays `PRO_COST_HI`, its weakest `PRO_COST_LO`, linear between. This
    guarantees a pro is never more expensive than the top program can afford (the cap is
    raised to 33.5), so every pro finds a buyer. A single-member cohort costs the midpoint.
    """
    strs = sorted(overall_to_str(p.current_overall()) for p in cohort)
    lo, hi = strs[0], strs[-1]
    s = overall_to_str(pro.current_overall())
    frac = 0.5 if hi <= lo else (s - lo) / (hi - lo)
    return round(PRO_COST_LO + frac * (PRO_COST_HI - PRO_COST_LO), 2)
