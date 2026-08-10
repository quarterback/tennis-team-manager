"""
Program home-city generation.

The NCAA program data carries a school name and a conference but no location —
so every team page reads as a name floating in space. This module gives each
program a deterministic home **city + state**, the team-level analogue of the
per-player `roll_hometown` flavor.

Ported in spirit from o27v2's `team_naming.py`, which generates a city for every
(generated) club. Tennis programs are *real* schools, so rather than invent a
team name we just place each one in a believable American college town, drawn
deterministically from the school's name. The pool is real (city, state) pairs
weighted toward the regions that actually produce college tennis — so the result
reads like a plausible campus location even though it isn't the literal one.

Deterministic: `program_city(school)` is a pure function of the school name, so
the men's and women's "Texas" share a home city and it never drifts between
loads or processes.
"""
from __future__ import annotations

import hashlib

# A pool of real US college towns as (city, state-abbr). Weighted by the
# tennis-recruiting heat of the region: the Sun Belt / California / Texas
# corridor is heavy, the cold-weather north lighter. Repeats are intentional —
# they ARE the weighting (a town listed twice is twice as likely).
_COLLEGE_TOWNS: tuple[tuple[str, str], ...] = (
    # California (heavy — biggest tennis pipeline)
    ("Los Angeles", "CA"), ("Berkeley", "CA"), ("Stanford", "CA"),
    ("San Diego", "CA"), ("Irvine", "CA"), ("Santa Barbara", "CA"),
    ("Malibu", "CA"), ("Fresno", "CA"), ("Riverside", "CA"), ("Davis", "CA"),
    ("Los Angeles", "CA"), ("San Diego", "CA"), ("Berkeley", "CA"),
    # Florida (heavy)
    ("Gainesville", "FL"), ("Tallahassee", "FL"), ("Miami", "FL"),
    ("Coral Gables", "FL"), ("Orlando", "FL"), ("Tampa", "FL"),
    ("Boca Raton", "FL"), ("Winter Park", "FL"), ("Gainesville", "FL"),
    ("Miami", "FL"),
    # Texas (heavy)
    ("Austin", "TX"), ("Fort Worth", "TX"), ("Waco", "TX"),
    ("College Station", "TX"), ("Lubbock", "TX"), ("Houston", "TX"),
    ("Dallas", "TX"), ("San Antonio", "TX"), ("Austin", "TX"),
    ("Fort Worth", "TX"),
    # Georgia / Carolinas / Virginia (SEC-ACC core, heavy)
    ("Athens", "GA"), ("Atlanta", "GA"), ("Chapel Hill", "NC"),
    ("Durham", "NC"), ("Raleigh", "NC"), ("Winston-Salem", "NC"),
    ("Charlottesville", "VA"), ("Blacksburg", "VA"), ("Clemson", "SC"),
    ("Columbia", "SC"), ("Athens", "GA"), ("Chapel Hill", "NC"),
    # Deep South
    ("Tuscaloosa", "AL"), ("Auburn", "AL"), ("Baton Rouge", "LA"),
    ("Oxford", "MS"), ("Starkville", "MS"), ("Knoxville", "TN"),
    ("Nashville", "TN"), ("Lexington", "KY"), ("Fayetteville", "AR"),
    # Southwest / Mountain
    ("Tempe", "AZ"), ("Tucson", "AZ"), ("Las Vegas", "NV"),
    ("Albuquerque", "NM"), ("Boulder", "CO"), ("Salt Lake City", "UT"),
    ("Provo", "UT"),
    # Midwest
    ("Ann Arbor", "MI"), ("Columbus", "OH"), ("Bloomington", "IN"),
    ("Champaign", "IL"), ("Evanston", "IL"), ("Madison", "WI"),
    ("Minneapolis", "MN"), ("Iowa City", "IA"), ("Lincoln", "NE"),
    ("Lawrence", "KS"), ("Columbia", "MO"), ("Notre Dame", "IN"),
    # Northeast / Mid-Atlantic
    ("Princeton", "NJ"), ("New Haven", "CT"), ("Cambridge", "MA"),
    ("Ithaca", "NY"), ("New York", "NY"), ("Philadelphia", "PA"),
    ("State College", "PA"), ("Providence", "RI"), ("Hanover", "NH"),
    # Pacific Northwest
    ("Eugene", "OR"), ("Corvallis", "OR"), ("Seattle", "WA"),
    ("Pullman", "WA"),
)


def _seed(school: str) -> int:
    return int.from_bytes(
        hashlib.blake2s((school or "").encode("utf-8"), digest_size=8).digest(),
        "big",
    )


def program_city(school: str) -> tuple[str, str]:
    """Deterministic (city, state-abbr) home for a program, derived purely from
    the school name. Stable across loads, processes, division and gender."""
    if not school:
        return ("", "")
    return _COLLEGE_TOWNS[_seed(school) % len(_COLLEGE_TOWNS)]


def program_location(school: str) -> str:
    """'City, ST' display string (empty when the school is unknown)."""
    city, state = program_city(school)
    return f"{city}, {state}" if city else ""


# Tennis-recruiting heat by USPS state/territory — biases the nationwide
# birthplace pool toward the regions that actually produce college tennis (the
# CA / TX / FL Sun Belt corridor heavy, the cold-weather north lighter). A state
# absent from the table draws at weight 1. Territories are US, so kept.
_STATE_HEAT: dict[str, int] = {
    "CA": 8, "TX": 7, "FL": 7, "GA": 4, "NY": 4, "NC": 3, "IL": 3, "OH": 3,
    "PA": 3, "VA": 3, "NJ": 3, "AZ": 3, "TN": 2, "SC": 2, "MI": 2, "MA": 2,
    "MD": 2, "WA": 2, "CO": 2, "IN": 2, "MO": 2, "AL": 2, "LA": 2, "UT": 2,
    "OR": 2, "MN": 2, "WI": 2, "KY": 2, "OK": 2, "NV": 2,
    # ⚠️ "JF" (Jefferson) is DELIBERATELY ABSENT — it draws at the default 1 and
    # must stay there. Its city list is already population-repeated at export
    # (scripts/import_jefferson.py), so weight 1 alone puts it at ~8.7% of this
    # pool — between Texas and Florida, matching its ~6.6% share of the recruit
    # board. Giving it a hotbed heat here would multiply an existing weighting and
    # blow it past California.
}

# Valid US birthplace codes: 50 states + DC + the territories that carry US
# players — drops any stray non-US code (e.g. a Canadian province) that shares
# the city data.
_US_CODES = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY", "PR", "VI", "GU", "AS",
    "JF",   # Jefferson — a full state, so its towns belong in the generic pool too
})

_US_TOWNS: tuple[tuple[str, str], ...] | None = None


def _us_towns() -> tuple[tuple[str, str], ...]:
    """The expansive nationwide (city, state-abbr) birthplace pool: every real US
    city in the per-state tier of `hometowns.json` (~1.5k towns spanning all 50
    states + territories), each state repeated by its tennis-recruiting heat so the
    mix still leans Sun Belt. Built once and cached; falls back to the compact
    college-town list only if the data can't be loaded."""
    global _US_TOWNS
    if _US_TOWNS is None:
        from .flavor import _load_us_states
        pool: list[tuple[str, str]] = []
        for st, cities in _load_us_states().items():
            code = (st or "").upper()
            if code not in _US_CODES:
                continue
            weight = _STATE_HEAT.get(code, 1)
            for city in cities:
                pool.extend([(city, code)] * weight)
        _US_TOWNS = tuple(pool) or _COLLEGE_TOWNS
    return _US_TOWNS


def random_town(rng) -> tuple[str, str]:
    """A random real (city, state-abbr) drawn from the expansive nationwide US city
    pool — used for American player hometowns so they read 'City, ST' with the city
    actually located in its state, from a broad base rather than a handful of
    college towns."""
    return rng.choice(_us_towns())
