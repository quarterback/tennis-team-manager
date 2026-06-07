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

from generators import make_name_picker, region_preset
from .development import Prospect, generate_prospect

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

# Synthetic city pool (placeholder until real HS data) — generic, broadly plausible.
_CITIES = ["Springfield", "Riverside", "Fairview", "Kingsport", "Oakdale", "Bridgeport",
           "Lakewood", "Highland", "Westport", "Ashford", "Brookfield", "Clearwater",
           "Maplewood", "Stonebridge", "Cedar Park", "Glenwood", "Hartwell", "Ridgefield",
           "Auburn", "Belmont", "Carmel", "Dover", "Easton", "Franklin"]


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
                   gender: str = "male", intl_share: float = 0.35) -> RecruitClass:
    """Generate a recruiting class: `intl_share` of the pool is international."""
    us_name = make_name_picker(random.Random(rng.randrange(1 << 30)), gender=gender,
                               region_weights=region_preset("us_only"))
    intl_name = make_name_picker(random.Random(rng.randrange(1 << 30)), gender=gender,
                                 region_weights=region_preset("global"))
    state_names = [s[0] for s in US_STATES]
    state_weights = [_STATE_WEIGHT.get(s[1], 1) for s in US_STATES]

    recruits: list[Prospect] = []
    for _ in range(n):
        domestic = rng.random() >= intl_share
        if domestic:
            name, _ = us_name()
            state = rng.choices(state_names, weights=state_weights, k=1)[0]
            region, country = state, "US"
        else:
            name, country = intl_name()
            region = country or "INT"
        city = rng.choice(_CITIES)
        p = generate_prospect(rng, name, country, gender=gender)
        p.hometown = f"{city}, {region}"
        p.region = region
        p.domestic = domestic
        p.grad_year = grad_year
        recruits.append(p)
    return RecruitClass(grad_year=grad_year, gender=gender, recruits=recruits)


def national_rankings(klass: RecruitClass) -> list[Prospect]:
    return sorted(klass.recruits, key=_recruiting_score, reverse=True)


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
