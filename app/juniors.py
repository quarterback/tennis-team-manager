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
                        roll_us_hometown, roll_high_school, country_abbrev)
from .development import Prospect, generate_prospect, make_pid

# US states + DC (name, abbr).
US_STATES = [
    ("Alabama", "AL"), ("Alaska", "AK"), ("Arizona", "AZ"), ("Arkansas", "AR"),
    ("California", "CA"), ("Colorado", "CO"), ("Connecticut", "CT"), ("Delaware", "DE"),
    ("District of Columbia", "DC"), ("Florida", "FL"), ("Georgia", "GA"), ("Hawaii", "HI"),
    ("Idaho", "ID"), ("Illinois", "IL"), ("Indiana", "IN"), ("Iowa", "IA"),
    # Jefferson: the fictional West Coast state imported from `prep-network` — its
    # 20 counties stand on real southern-Oregon / northern-California / northern-
    # Nevada / western-Idaho ground. Ordinary state in every respect here.
    # See docs/AAR-jefferson-state-integration.md.
    ("Jefferson", "JF"),
    ("Kansas", "KS"), ("Kentucky", "KY"), ("Louisiana", "LA"), ("Maine", "ME"),
    ("Maryland", "MD"), ("Massachusetts", "MA"), ("Michigan", "MI"), ("Minnesota", "MN"),
    ("Mississippi", "MS"), ("Missouri", "MO"), ("Montana", "MT"), ("Nebraska", "NE"),
    ("Nevada", "NV"), ("New Hampshire", "NH"), ("New Jersey", "NJ"), ("New Mexico", "NM"),
    ("New York", "NY"), ("North Carolina", "NC"), ("North Dakota", "ND"), ("Ohio", "OH"),
    ("Oklahoma", "OK"), ("Oregon", "OR"), ("Pennsylvania", "PA"), ("Rhode Island", "RI"),
    ("South Carolina", "SC"), ("South Dakota", "SD"), ("Tennessee", "TN"), ("Texas", "TX"),
    ("Utah", "UT"), ("Vermont", "VT"), ("Virginia", "VA"), ("Washington", "WA"),
    ("West Virginia", "WV"), ("Wisconsin", "WI"), ("Wyoming", "WY"),
    # US territories — treated as US states here (their players are US dual-citizens,
    # rendered with two flags), so they generate readily. Puerto Rico in particular
    # has a robust tennis pipeline; Guam is a Pacific territory with Chamorro names.
    ("Puerto Rico", "PR"), ("U.S. Virgin Islands", "VI"), ("Guam", "GU"),
]
# Calibrated junior-tennis origin distribution — the real (USTA-ish) share each
# state/territory contributes to the domestic recruit pool. Drives BOTH which
# states supply more recruits on average (hotbeds CA/FL/TX/NY heavy) AND, with the
# guaranteed per-state floor in generate_class, that every state generates yearly.
# Relative weights (need not sum to 1); rng.choices renormalizes.
#
# JEFFERSON (JF) is deliberately the LARGEST share (owner rule 2027-08): the state
# is ~17.6M and is meant to both DEVELOP and DRAW like Texas/California/Florida, so
# it edges California as a talent source. The four states
# whose real counties Jefferson stands on are shaved by the population share it
# actually takes from them — OR ~17% (nine counties), NV ~16% (Washoe, Humboldt),
# ID ~12% (Canyon, Owyhee), CA ~1.8% (seven far-northern counties) — and the rest
# of Jefferson's weight is its invented population. That leaves the table summing
# to ~1.064 rather than 1.0, which is fine and is why the note above exists: these
# are RELATIVE weights. Do not "fix" it by rescaling all 55 numbers.
US_JUNIOR_TENNIS_ORIGIN_WEIGHTS = {
    "AK": 0.0011, "AL": 0.0102, "AR": 0.0064, "AZ": 0.0166, "CA": 0.1317,
    "CO": 0.0214, "CT": 0.0122, "DC": 0.0010, "DE": 0.0020, "FL": 0.1126,
    "GA": 0.0354, "GU": 0.0005, "HI": 0.0038, "IA": 0.0120, "ID": 0.0050,
    "IL": 0.0325, "IN": 0.0185, "JF": 0.1400, "KS": 0.0122, "KY": 0.0115,
    "LA": 0.0076, "MA": 0.0231, "MD": 0.0130, "ME": 0.0038, "MI": 0.0334,
    "MN": 0.0195, "MO": 0.0144, "MS": 0.0074, "MT": 0.0038, "NC": 0.0276,
    "ND": 0.0024, "NE": 0.0066, "NH": 0.0034, "NJ": 0.0424, "NM": 0.0033,
    "NV": 0.0045, "NY": 0.0545, "OH": 0.0240, "OK": 0.0074, "OR": 0.0092,
    "PA": 0.0160, "PR": 0.0061, "RI": 0.0033, "SC": 0.0111, "SD": 0.0017,
    "TN": 0.0161, "TX": 0.0886, "UT": 0.0100, "VA": 0.0202, "VI": 0.0006,
    "VT": 0.0003, "WA": 0.0420, "WI": 0.0156, "WV": 0.0030, "WY": 0.0017,
}
_DEFAULT_STATE_WEIGHT = 0.0005      # any abbr missing from the table above
_US_TERRITORIES = {"PR", "VI", "GU"}   # country = US, secondary = the territory (dual flag)

_STATE_ABBR = dict(US_STATES)   # full state name -> postal abbr
_ABBR_STATE = {a: s for s, a in US_STATES}   # postal abbr -> full state name

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


def recruit_grade(rank: int, class_size: int = 400) -> tuple[int, float]:
    """Industry-style numeric grade for a board-ranked recruit, returned as
    ``(rating, composite)``. The composite (0.7400–0.9999) decays from the very
    top on a power curve so the elite tail clusters near 1.0 — exactly the shape
    a real recruiting composite has (blue chip ~0.99, 5★ ~0.98, 4★ ~0.89–0.97,
    3★ ~0.80–0.89). The 0–100 rating is that same scale rounded. A pure function
    of board rank, so the number is identical everywhere the recruit appears."""
    if class_size <= 1:
        q = 0.0
    else:
        q = (rank - 1) / (class_size - 1)
    q = max(0.0, min(1.0, q))
    composite = 0.74 + 0.26 * (1.0 - q) ** 1.8
    composite = max(0.60, min(0.9999, composite))
    return int(round(composite * 100)), round(composite, 4)


@dataclass
class RecruitClass:
    grad_year: int
    gender: str
    recruits: list[Prospect]
    circuit_done: bool = False   # guard: junior circuit has been run + frozen on


def _recruiting_score(p: Prospect) -> float:
    """The recruiting service's published ranking signal — a NOISY projection of
    the recruit's ceiling (the scouting 'feel'), deliberately NOT the hidden truth
    and NOT performance. Stars derive from this; junior points/STR (performance)
    are a separate axis, so the board and the results ledger diverge — the gem
    signal. See docs/AAR-fog-of-war-recruiting.md."""
    return p.scouting_report("service")


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
    # Puerto Rico players are US dual-citizens but read authentically (Hispanic names);
    # Guam likewise reads authentically with Chamorro names.
    latin_name = make_name_picker(random.Random(rng.randrange(1 << 30)), gender=gender,
                                  region_weights={"latin_america": 1.0})
    chamorro_name = make_name_picker(random.Random(rng.randrange(1 << 30)), gender=gender,
                                     region_weights={"guam": 1.0})
    state_abbrs = [s[1] for s in US_STATES]
    state_weights = [US_JUNIOR_TENNIS_ORIGIN_WEIGHTS.get(a, _DEFAULT_STATE_WEIGHT)
                     for a in state_abbrs]

    # Decide domestic vs international up front so we can GUARANTEE every state a
    # recruit: the domestic slots are filled FLOOR-first (one of every state, so no
    # state — incl. DC/PR/VI/GU — is empty in a year) then the remainder by the
    # calibrated origin weights (hotbeds supply more on average). Each recruit's
    # talent is still an independent N(mean, sd) draw, so every state gets a full
    # range of talent.
    domestic_flags = [rng.random() >= intl_share for _ in range(n)]
    n_domestic = sum(domestic_flags)
    if n_domestic >= len(state_abbrs):
        state_queue = list(state_abbrs)        # guaranteed floor: one of every state
        state_queue += rng.choices(state_abbrs, weights=state_weights,
                                   k=n_domestic - len(state_abbrs))
    else:                                       # tiny class (tests): no floor possible
        state_queue = rng.choices(state_abbrs, weights=state_weights, k=n_domestic)
    rng.shuffle(state_queue)                    # so the floor states aren't front-loaded
    _state_iter = iter(state_queue)

    recruits: list[Prospect] = []
    for i in range(n):
        domestic = domestic_flags[i]
        secondary = None
        hs_state = None
        if domestic:
            abbr = next(_state_iter)
            state = _ABBR_STATE.get(abbr, abbr)
            name, _ = (latin_name() if abbr == "PR"
                       else chamorro_name() if abbr == "GU"
                       else us_name())
            region, country = state, "US"
            if abbr in _US_TERRITORIES:           # US territory → dual flag (US + terr.)
                secondary = abbr
            # Real city that ACTUALLY belongs to the drawn state — the city → state →
            # nation middle tier (generators hometowns.json `us_states`), so a hometown
            # reads "Boca Raton, FL", never "Dallas, GA".
            city = roll_us_hometown(abbr, rng) or roll_hometown("US", rng) or rng.choice(_CITIES)
            hometown = f"{city}, {abbr}"
            hs_state = abbr
        else:
            name, ccode = intl_name()
            if ccode in _US_TERRITORIES:          # treat PR/VI as US dual-citizens, not foreign
                domestic, country, secondary = True, "US", ccode
                region = _ABBR_STATE.get(ccode, ccode)
                city = roll_us_hometown(ccode, rng) or rng.choice(_CITIES)
                hometown = f"{city}, {ccode}"
                hs_state = ccode
            else:
                country, region = ccode, (ccode or "INT")
                city = roll_hometown(ccode, rng) or rng.choice(_CITIES)
                hometown = f"{city}, {country_abbrev(ccode)}" if ccode else city
        talent = max(24.0, min(80.0, rng.gauss(talent_mean, talent_sd)))
        p = generate_prospect(rng, name, country, gender=gender, talent=talent,
                              pid=make_pid("recruit", grad_year, gender, i))
        p.hometown = hometown
        p.region = region
        p.domestic = domestic
        # High school must match the state-board hometown set above (generate_prospect
        # rolled it off a different random state); internationals get none.
        p.high_school = (roll_high_school("US", rng, state=hs_state, home_city=city)
                         if domestic else "")
        if secondary:
            p.secondary_country = secondary
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


# ---- POINTS rankings (the junior accomplishment ledger; see junior_circuit) ----
# Distinct from the recruiting board above: this ranks on what a recruit EARNED on
# the junior circuit (best-6 results + ranked-win bonuses), not consensus ability.
# The two diverging is the gem signal — a kid buried on the board but high on points
# is a riser; the reverse is an over-scouted name.

def points_rankings(klass: RecruitClass) -> list[Prospect]:
    """Whole pool ranked #1..N by junior ranking points (pid breaks ties). Assigns
    `points_rank` to every recruit."""
    ranked = sorted(klass.recruits,
                    key=lambda p: (-getattr(p, "junior_points", 0), p.pid))
    for i, p in enumerate(ranked, 1):
        p.points_rank = i
    return ranked


# ---- TennisEye: a SECOND star rating, from RESULTS (not projection) ----------
# The consensus board (rank_class) rates on projected ability + ceiling — the
# scout's eye, correlated with the overall composite. TennisEye instead rates what
# a junior actually DID: ranking points (accomplishments) + demonstrated junior STR
# (level). Same TIER_CUTOFFS pyramid, so the two star sets are directly comparable,
# and where they DISAGREE is the read teams care about — a high-TennisEye /
# low-consensus kid is proven-but-unhyped; the reverse is hype without results.
_TE_W_POINTS, _TE_W_STR = 0.6, 0.4


def _tenniseye_score(p, pmax: float, smin: float, sspan: float) -> float:
    pts = (getattr(p, "junior_points", 0) or 0) / pmax
    st = ((getattr(p, "junior_str", 0.0) or 0.0) - smin) / sspan
    return _TE_W_POINTS * pts + _TE_W_STR * st


def tenniseye_rankings(klass: RecruitClass) -> list[Prospect]:
    """Assign each recruit a TennisEye rank + star tier from junior RESULTS
    (ranking points + STR). Same pyramid as the consensus board; sets
    `tenniseye_rank`, `tenniseye_tier`, `tenniseye_stars` on every recruit."""
    recs = klass.recruits
    pmax = max((getattr(p, "junior_points", 0) or 0 for p in recs), default=0) or 1.0
    strs = [getattr(p, "junior_str", 0.0) or 0.0 for p in recs]
    smin = min(strs, default=0.0)
    sspan = (max(strs, default=0.0) - smin) or 1.0
    ranked = sorted(recs, key=lambda p: (-_tenniseye_score(p, pmax, smin, sspan), p.pid))
    for i, p in enumerate(ranked, 1):
        p.tenniseye_rank = i
        p.tenniseye_tier, p.tenniseye_stars = tier_for_rank(i, len(ranked))
    return ranked


def us_points_rankings(klass: RecruitClass) -> list[Prospect]:
    return [p for p in points_rankings(klass) if p.domestic]


def intl_points_rankings(klass: RecruitClass) -> list[Prospect]:
    """The whole pool minus the domestic (US) players — every international, ranked
    by points. The complement of `us_points_rankings`."""
    return [p for p in points_rankings(klass) if not p.domestic]


def dense_nations(klass: RecruitClass, min_players: int = 8) -> list[str]:
    """International nations with enough pool depth to warrant a Top-10 board,
    ordered by that depth (talent density)."""
    counts: dict[str, int] = {}
    for p in klass.recruits:
        if not p.domestic:
            counts[p.region] = counts.get(p.region, 0) + 1
    return [n for n, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            if c >= min_players]


def nation_points_top(klass: RecruitClass, per: int = 10,
                      min_players: int = 8) -> list[tuple[str, list[Prospect]]]:
    """[(nation, top-`per` by points)] for each talent-dense nation, densest first."""
    order = dense_nations(klass, min_players)
    dense = set(order)
    out: dict[str, list[Prospect]] = {}
    for p in points_rankings(klass):
        if p.domestic or p.region not in dense:
            continue
        out.setdefault(p.region, [])
        if len(out[p.region]) < per:
            out[p.region].append(p)
    return [(n, out[n]) for n in order if n in out]
