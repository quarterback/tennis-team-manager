"""
Juniors / recruiting pool + ranking surfaces.

Generates a recruiting class of `Prospect`s (app.development) with origins and
exposes the ranking lists coaches actually recruit off of — the "recruiting
surface" from the design:

  • National Top-N (by graduating class)
  • State-by-state (domestic depth)
  • International Top-N + Top-N by nation

A recruit's CURRENT ability (STR) is visible; the development trajectory is not
(see app.development). Recruiting rank is a consensus blend of visible current
ability and the shared scouting service's ceiling projection — so the board can
be wrong (gems under-ranked, busts over-ranked), which is the point.

Origins: US recruits get a city + state; international recruits a city + nation
(incl. Canada). Hometowns are synthetic placeholders until real HS data is
scraped (MaxPreps/On3) — see design doc §11.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from generators import (make_name_picker, region_preset, roll_hometown,
                        country_abbrev)
from .development import Prospect, generate_prospect, make_pid

# US states + DC (name, abbr).
US_STATES = [
    ("Alabama", "AL"), ("Alaska", "AK"), ("Arizona", "AZ"), ("Arkansas", "AR"),
    ("California", "CA"), ("Colorado", "CO"), ("Connecticut", "CT"), ("Delaware", "DE"),
    ("District of Columbia", "DC"), ("Florida", "FL"), ("Georgia", "GA"), ("Hawaii", "HI"),
    ("Idaho", "ID"), ("Illinois", "IL"), ("Indiana", "IN"), ("Iowa", "IA"),
    ("Kansas", "KS"), ("Kentucky", "KY"), ("Louisiana", "LA"), ("Maine", "ME"),
    ("Maryland", "MD"), ("Massachusetts", "MA"), ("Michigan", "MI"), ("Minnesota", "MN"),
    ("Mississippi", "MS"), ("Missouri", "MO"), ("Montana", "MT"), ("Nebraska", "NE"),
    ("Nevada", "NV"), ("New Hampshire", "NH"), ("New Jersey", "NJ"), ("New Mexico", "NM"),
    ("New York", "NY"), ("North Carolina", "NC"), ("North Dakota", "ND"), ("Ohio", "OH"),
    ("Oklahoma", "OK"), ("Oregon", "OR"), ("Pennsylvania", "PA"), ("Rhode Island", "RI"),
    ("South Carolina", "SC"), ("South Dakota", "SD"), ("Tennessee", "TN"), ("Texas", "TX"),
    ("Utah", "UT"), ("Vermont", "VT"), ("Virginia", "VA"), ("Washington", "WA"),
    ("West Virginia", "WV"), ("Wisconsin", "WI"), ("Wyoming", "WY"),
]
# Population-ish weighting so tennis hotbeds (CA/FL/TX) supply more recruits.
_STATE_WEIGHT = {"CA": 8, "FL": 7, "TX": 7, "NY": 5, "GA": 4, "NC": 3, "IL": 3,
                 "PA": 3, "OH": 3, "VA": 3, "NJ": 3, "AZ": 2, "WA": 2, "MA": 2}

_STATE_ABBR = dict(US_STATES)   # full state name -> postal abbr

# Fallback city pool for nations with no entry in hometowns.json — generic but
# broadly plausible, so an international recruit always has a believable city.
_CITIES = ["Riverside", "Fairview", "Oakdale", "Lakewood", "Highland", "Westport",
           "Brookfield", "Clearwater", "Maplewood", "Glenwood", "Belmont", "Franklin"]


# Recruiting tiers as a fraction of the ranked class — a full TennisRecruiting.net
# pyramid: a thin elite top (Blue Chip / 5-star), a thick 3-2 star body, a long
# 1-star tail, then unrated. Stars are a pure function of talent (rank sorts on
# ability + ceiling), so this scales to any class size. (cum_fraction, label, stars)
TIER_CUTOFFS = [
    (0.015, "Blue Chip", 5), (0.04, "5-Star", 5), (0.12, "4-Star", 4),
    (0.30, "3-Star", 3), (0.58, "2-Star", 2), (0.85, "1-Star", 1),
]


def tier_for_rank(rank: int, class_size: int = 400) -> tuple[str, int]:
    q = rank / max(1, class_size)
    for cut, label, stars in TIER_CUTOFFS:
        if q <= cut:
            return label, stars
    return "Unrated", 0


@dataclass
class RecruitClass:
    grad_year: int
    gender: str
    recruits: list[Prospect]


def _recruiting_score(p: Prospect) -> float:
    """Consensus recruiting signal: mostly visible current ability, partly the
    shared service's ceiling projection. Deliberately NOT the hidden truth."""
    return 0.6 * p.current_overall() + 0.4 * p.scouting_report("service")


def generate_class(rng: random.Random, n: int = 200, grad_year: int = 2026,
                   gender: str = "male", intl_share: float = 0.35,
                   talent_mean: float = 50.0, talent_sd: float = 12.0,
                   intl_weights: dict | None = None) -> RecruitClass:
    """Generate a recruiting class: `intl_share` of the pool is international.

    `intl_weights` is the effective {region: weight} mix for the international
    pool (the onboarding band + any per-region tuning); the domestic pool is
    always US. Per-recruit talent is drawn from N(talent_mean, talent_sd) so the
    elite tail reaches blue-chip STR while the bulk sit lower — the bottom-heavy
    distribution real recruiting has."""
    us_name = make_name_picker(random.Random(rng.randrange(1 << 30)), gender=gender,
                               region_weights=region_preset("us_only"))
    # International board = the chosen mix minus the US (domestic is handled
    # separately), so an "international" recruit is never an American.
    if intl_weights is None:
        intl_weights = region_preset("tennis_global")
    intl_weights = {k: v for k, v in intl_weights.items() if k != "us"}
    intl_name = make_name_picker(random.Random(rng.randrange(1 << 30)), gender=gender,
                                 region_weights=intl_weights)
    state_names = [s[0] for s in US_STATES]
    state_weights = [_STATE_WEIGHT.get(s[1], 1) for s in US_STATES]

    recruits: list[Prospect] = []
    for i in range(n):
        domestic = rng.random() >= intl_share
        if domestic:
            name, _ = us_name()
            state = rng.choices(state_names, weights=state_weights, k=1)[0]
            region, country = state, "US"
            # Real US city from the hometowns pool; suffix the drawn state
            # (cosmetic — the state is the recruiting-board dimension).
            city = roll_hometown("US", rng) or rng.choice(_CITIES)
            hometown = f"{city}, {_STATE_ABBR.get(state, state)}"
        else:
            name, country = intl_name()
            region = country or "INT"
            city = roll_hometown(country, rng) or rng.choice(_CITIES)
            hometown = f"{city}, {country_abbrev(country)}" if country else city
        talent = max(24.0, min(80.0, rng.gauss(talent_mean, talent_sd)))
        p = generate_prospect(rng, name, country, gender=gender, talent=talent,
                              pid=make_pid("recruit", grad_year, gender, i))
        p.hometown = hometown
        p.region = region
        p.domestic = domestic
        p.grad_year = grad_year
        recruits.append(p)
    return RecruitClass(grad_year=grad_year, gender=gender, recruits=recruits)


def rank_class(klass: RecruitClass) -> list[Prospect]:
    """Assign each recruit a national rank + count-based star tier (Blue Chip /
    5★ / 4★ / 3★ / Unrated). Returns the nationally-ranked list."""
    ranked = sorted(klass.recruits, key=_recruiting_score, reverse=True)
    n = len(ranked)
    for i, p in enumerate(ranked, 1):
        p.recruit_rank = i
        p.recruit_tier, p.recruit_stars = tier_for_rank(i, n)
    return ranked


def national_rankings(klass: RecruitClass) -> list[Prospect]:
    return rank_class(klass)


def state_rankings(klass: RecruitClass, state: str) -> list[Prospect]:
    return [p for p in national_rankings(klass) if p.domestic and p.region == state]


def international_rankings(klass: RecruitClass) -> list[Prospect]:
    return [p for p in national_rankings(klass) if not p.domestic]


def top_by_nation(klass: RecruitClass, per: int = 10) -> dict[str, list[Prospect]]:
    out: dict[str, list[Prospect]] = {}
    for p in international_rankings(klass):
        out.setdefault(p.region, [])
        if len(out[p.region]) < per:
            out[p.region].append(p)
    return out
