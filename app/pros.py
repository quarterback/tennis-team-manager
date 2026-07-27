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
from .player_attributes import RICH_ATTRS, clamp_grade

PRO_BADGE = "PRO"                    # green profile label (Prospect.junior_badges)
PRO_ATTR = (80.0, 90.0)            # pros live ABOVE the 80 college ceiling — every attribute
                                    # drawn in 80-90, so OVR lands ~82-87 and their drivers
                                    # normalize above 1.0 (clearly better on court). Only the
                                    # pro tier reaches this headroom; everyone else stays <= 80.
PRO_PER_CYCLE = (15, 20)           # up to this many per gender, per portal cycle
# STR-indexed cost band. Pitched HIGH on purpose (near the elite budget cap of 33.5): a pro
# eats most of a program's one budget, so even a blue-blood affords ONE without gutting its
# recruit class and majors can't afford one at all — pros SPREAD instead of stacking at a
# handful of rich clubs. Still ≤ the elite cap so a pro a program CAN fund is always signable.
PRO_COST_LO, PRO_COST_HI = 18.0, 30.0

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
    """A deterministic pro cohort for one gender in one portal cycle. Attributes in the
    80-90 headroom (above the college ceiling), pro badge, real STR. `cycle_key` (e.g.
    "2026-fall") + salt key the RNG so each cycle in each league is fresh but reproducible."""
    from generators import make_name_picker
    if n is None:
        from . import worldconfig
        n = worldconfig.pros_per_cycle()          # UI-tunable, even, per gender per cycle
    seed = f"{salt}|pros|{gender}|{cycle_key}"
    rng = random.Random(seed)
    pgender = "male" if gender in ("men", "male") else "female"
    name_fn = make_name_picker(random.Random(f"{seed}|names"), gender=pgender,
                               region_weights=_PRO_REGION_WEIGHTS)
    pros = []
    for i in range(n):
        name, country = name_fn()
        p = generate_prospect(rng, name=name, country=country, gender=pgender,
                              talent=80.0, pid=make_pid(salt, "pro", gender, cycle_key, i),
                              maturity_range=(1.0, 1.0))     # fully developed — they're pros
        # Lift every attribute into the 80-90 pro headroom (a per-pro centre with a small
        # per-attribute jitter, so pros differ from each other but all read elite). This
        # bypasses the 80 generation clamp — only pros reach here.
        centre = rng.uniform(83.0, 88.0)
        for a in RICH_ATTRS:
            v = clamp_grade(rng.gauss(centre, 2.0))
            v = min(PRO_ATTR[1], max(PRO_ATTR[0], v))
            p.current[a] = v
            p.potential[a] = v
        p.junior_badges = list(p.junior_badges or []) + [PRO_BADGE]
        p.recruit_stars = 6            # above the 5-star ladder
        # Pros are GRAD TRANSFERS (owner rule 2027-07): class "Gr", one season of
        # eligibility, gone at the year rollover like a graduating senior. They're
        # deliberately one-and-done — an elite distortion that passes through the
        # ecosystem, never a fixture of it. world.graduate() retires "Gr" with the
        # seniors, and departing pros DO enter world_graduates, so an ex-pro can
        # continue their career in the GTT (their elite STR tops the draft).
        p.class_year = "Gr"
        pros.append(p)
    return pros


def assign_pros(cohort: list, programs: list) -> list:
    """Decide which program signs each pro. `programs` is a list of dicts with keys
    `school`, `budget` (recruiting-budget headroom), `prestige`, and optionally
    `us_only` (a service academy — US citizens only, so it never signs an
    international pro). Best pro first goes to the highest-prestige program that can
    still AFFORD them, and that program's budget is then DEPLETED by the cost — so a
    blue-blood can stack 2-3 pros while its money lasts, then the flow spills to the
    next-best program (a natural funnel-then-spread, not a hard 1-each cap).

    Budget-gated (used by the fall/transfer auto cycles; the pre-season portal signs pros by
    hand instead). A club only signs a pro it can AFFORD, and with the cost pitched high
    (`PRO_COST_LO/HI`) that eats most of a budget, so a club realistically takes ONE and the
    flow SPREADS to the next-best club rather than stacking — no overspend, no funnel. Pros a
    club can't fund simply go unsigned that cycle. Returns [{pid, school, cost, str}] in
    signing order."""
    from .ncaa import is_domestic_player
    ranked = sorted(cohort, key=lambda p: (-overall_to_str(p.current_overall()), p.pid))
    prog = {pr["school"]: pr for pr in programs}
    budget_left = {s: pr["budget"] for s, pr in prog.items()}
    out = []
    for pro in ranked:
        cost = pro_cost(pro, cohort)
        intl = not is_domestic_player(pro)
        cands = [s for s, b in budget_left.items()
                 if b >= cost and not (intl and prog[s].get("us_only"))]
        if not cands:                                  # nobody affluent enough left — unsigned
            continue
        dest = max(cands, key=lambda s: (prog[s]["prestige"], s))
        budget_left[dest] -= cost                      # spend it — deplete for the next pro
        out.append({"pid": pro.pid, "school": dest, "cost": cost,
                    "str": round(overall_to_str(pro.current_overall()), 1)})
    return out


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
