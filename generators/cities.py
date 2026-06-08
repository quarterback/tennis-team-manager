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


def random_town(rng) -> tuple[str, str]:
    """A random real (city, state-abbr) from the US college-town pool — used for
    American player hometowns so they read 'City, ST' with a real state."""
    return rng.choice(_COLLEGE_TOWNS)
