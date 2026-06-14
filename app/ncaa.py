"""
NCAA program model + division loader.

Reads the conference/team JSON in data/ncaa/ (compiled from NCAA/ITA/Wikipedia)
and turns each school into a `Program` with:
  - crest abbr + color (real overrides for marquee schools, deterministic else)
  - a hidden latent strength in [0,1] - the program's true tennis quality,
    seeded deterministically from (school, gender, season) with a per-conference
    prestige prior. The season is simulated from these; the Power Index (P5) then
    estimates them back out of results. Strength is never shown directly.

`build_squad()` turns a Program into a deterministic 6-player engine Team
(ladder: court 1 strongest -> court 6 weakest).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import random
from dataclasses import dataclass, field

from engine import random_player, Team
from . import scholarships

SEASON_SEED = 2026
# Per-league generation salt. Mixed into the roster RNG and roster pids so the
# SAME school|division|gender produces a DIFFERENT roster (players, attributes,
# pids) in each New League save. Set by app.world for the active world; ""
# means no active world (legacy). Determinism holds only WITHIN a league because
# the salt is stable for that league's lifetime.
WORLD_SALT = ""
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "ncaa")

# Real crest abbr + color for marquee programs; everything else is derived.
SCHOOL_META = {
    "TCU": ("TCU", "#4d1979"), "Ohio State": ("OSU", "#bb0000"), "Texas": ("TEX", "#bf5700"),
    "Wake Forest": ("WAKE", "#9e7e38"), "Virginia": ("UVA", "#232d4b"), "Kentucky": ("UK", "#0033a0"),
    "Stanford": ("STAN", "#8c1515"), "Tennessee": ("TENN", "#ff8200"), "Oregon": ("ORE", "#154733"),
    "Florida": ("FLA", "#0021a5"), "USC": ("USC", "#990000"), "Baylor": ("BAY", "#154734"),
    "Texas A&M": ("TAMU", "#500000"), "Michigan": ("MICH", "#00274c"), "NC State": ("NCST", "#cc0000"),
    "Columbia": ("CLMB", "#9bcbeb"), "San Diego": ("USD", "#182b49"), "Old Dominion": ("ODU", "#003057"),
    "Cornell": ("COR", "#b31b1b"), "UC Santa Barbara": ("UCSB", "#003660"), "Pepperdine": ("PEPP", "#00205b"),
    "Harvard": ("HARV", "#a51c30"), "South Florida": ("USF", "#006747"), "Princeton": ("PRIN", "#ff6600"),
    "UCLA": ("UCLA", "#2d68c4"), "Georgia": ("UGA", "#ba0c2f"),
    "North Carolina": ("UNC", "#4b9cd3"), "Duke": ("DUKE", "#003087"), "Notre Dame": ("ND", "#0c2340"),
}

# Per-conference tennis prestige prior (mean latent strength). Default 0.50.
CONF_PRESTIGE = {
    # Power conferences
    "ACC": 0.78, "SEC": 0.78, "Big 12": 0.76, "Big Ten": 0.73, "Pac-12": 0.59,
    # High / strong mid-majors
    "Ivy": 0.68, "WCC": 0.63, "American": 0.60, "MW": 0.58, "Big West": 0.57,
    "CUSA": 0.56, "Sun Belt": 0.55,
    # Mid-majors
    "A-10": 0.52, "ASUN": 0.52, "SoCon": 0.51, "Big East": 0.50, "MAC": 0.49,
    "CAA": 0.49, "WAC": 0.49, "Patriot": 0.48,
    # Low-majors
    "Southland": 0.45, "Big Sky": 0.44, "Summit": 0.44, "Horizon": 0.43,
    "Big South": 0.43, "OVC": 0.42, "MAAC": 0.40, "NEC": 0.38, "MEAC": 0.34,
    "SWAC": 0.33,
    # Not in the supplied list — placeholders pending values
    "MVC": 0.44, "America East": 0.42,
}

# D2 / D3 priors are keyed by conference NAME (abbrs collide across divisions —
# e.g. MIAA is D2 Mid-America AND D3 Michigan, GNAC is D2 Great Northwest AND D3
# Great Northeast). The ALIASES map the data-file abbr (optionally suffixed -D2 /
# -D3 to disambiguate collisions) to the name. Resolved via conf_prestige().
CONF_PRESTIGE_D2 = {
    "Sunshine State": 0.62, "Peach Belt": 0.61, "Gulf South": 0.59, "Lone Star": 0.57,
    "Mid-America Intercollegiate": 0.56, "Pacific West": 0.55, "Great Lakes Intercollegiate": 0.54,
    "Great Lakes Valley": 0.53, "South Atlantic": 0.52, "Conference Carolinas": 0.51,
    "California Collegiate": 0.50, "Great Midwest": 0.49, "Pennsylvania State Athletic": 0.48,
    "Rocky Mountain Athletic": 0.47, "Northeast-10": 0.46, "East Coast": 0.45, "Great American": 0.45,
    "Great Northwest Athletic": 0.44, "Mountain East": 0.44, "Northern Sun": 0.43,
    "Central Atlantic": 0.42, "D2 Independent": 0.40, "Southern Intercollegiate Athletic": 0.36,
    "Central Intercollegiate Athletic": 0.35,
}
CONF_PRESTIGE_D2_ALIASES = {
    "SSC": "Sunshine State", "PBC": "Peach Belt", "GSC": "Gulf South", "LSC": "Lone Star",
    "MIAA": "Mid-America Intercollegiate", "PacWest": "Pacific West",
    "GLIAC": "Great Lakes Intercollegiate", "GLVC": "Great Lakes Valley", "SAC": "South Atlantic",
    "CC": "Conference Carolinas", "CCAA": "California Collegiate", "G-MAC": "Great Midwest",
    "PSAC": "Pennsylvania State Athletic", "RMAC": "Rocky Mountain Athletic", "NE10": "Northeast-10",
    "ECC": "East Coast", "GAC": "Great American", "GNAC-D2": "Great Northwest Athletic",
    "MEC": "Mountain East", "NSIC": "Northern Sun", "CACC": "Central Atlantic",
    "SIAC": "Southern Intercollegiate Athletic", "CIAA": "Central Intercollegiate Athletic",
}
CONF_PRESTIGE_D3 = {
    "University Athletic Association": 0.65, "NESCAC": 0.63, "SCIAC": 0.61, "Centennial": 0.58,
    "North Coast Athletic": 0.56, "NEWMAC": 0.55, "Liberty League": 0.54,
    "Southern Collegiate Athletic": 0.53, "Old Dominion Athletic": 0.52, "Coast-To-Coast": 0.52,
    "Southern Athletic Association": 0.51, "MIAC": 0.50, "Northwest Conference": 0.50,
    "SUNYAC": 0.49, "Landmark": 0.48, "CCIW": 0.48, "Middle Atlantic": 0.48,
    "MAC Commonwealth": 0.48, "MAC Freedom": 0.48, "American Rivers": 0.47, "Ohio Athletic": 0.46,
    "Empire 8": 0.46, "Michigan Intercollegiate": 0.45, "WIAC": 0.45, "American Southwest": 0.44,
    "United East": 0.44, "Conference of New England": 0.44, "Atlantic East": 0.43, "USA South": 0.43,
    "Heartland Collegiate": 0.43, "Presidents' Athletic": 0.42, "St. Louis Intercollegiate": 0.42,
    "Little East": 0.41, "Northern Athletics Collegiate": 0.41, "Allegheny Mountain Collegiate": 0.40,
    "Skyline": 0.40, "Great Northeast Athletic": 0.40, "North Atlantic": 0.39,
    "Upper Midwest Athletic": 0.38, "MASCAC": 0.37, "CUNYAC": 0.35, "D3 Independent": 0.40,
    "Collegiate Conference of the South": 0.58, "Midwest Conference": 0.46,
    "New Jersey Athletic": 0.60,
}
CONF_PRESTIGE_D3_ALIASES = {
    "CCS": "Collegiate Conference of the South", "MWC": "Midwest Conference",
    "NJAC": "New Jersey Athletic",
    "UAA": "University Athletic Association", "NCAC": "North Coast Athletic",
    "SCAC": "Southern Collegiate Athletic", "ODAC": "Old Dominion Athletic", "C2C": "Coast-To-Coast",
    "SAA": "Southern Athletic Association", "NWC": "Northwest Conference", "ARC": "American Rivers",
    "OAC": "Ohio Athletic", "MIAA-D3": "Michigan Intercollegiate", "ASC": "American Southwest",
    "CNE": "Conference of New England", "HCAC": "Heartland Collegiate", "PAC": "Presidents' Athletic",
    "SLIAC": "St. Louis Intercollegiate", "LEC": "Little East", "NACC": "Northern Athletics Collegiate",
    "AMCC": "Allegheny Mountain Collegiate", "GNAC-D3": "Great Northeast Athletic", "NAC": "North Atlantic",
    "UMAC": "Upper Midwest Athletic",
    # MAC Commonwealth / MAC Freedom data abbrs carry spaces and match by name.
}


def _merge_div_priors(names: dict, aliases: dict) -> dict:
    """Flatten a name-keyed division prior dict to data-file abbrs."""
    out = {abbr: names[nm] for abbr, nm in aliases.items() if nm in names}
    for nm, val in names.items():        # conferences whose data abbr IS the name
        out.setdefault(nm, val)
    return out


# Fold D2/D3 priors into the one abbr-keyed table. Abbrs are unique across
# divisions — the only collisions (MIAA, GNAC) were renamed in the data to
# MIAA-D3 / GNAC-D2 / GNAC-D3, matching the alias suffixes.
CONF_PRESTIGE.update(_merge_div_priors(CONF_PRESTIGE_D2, CONF_PRESTIGE_D2_ALIASES))
CONF_PRESTIGE.update(_merge_div_priors(CONF_PRESTIGE_D3, CONF_PRESTIGE_D3_ALIASES))


def conf_prestige(conf_abbr: str, division: str | None = None) -> float:
    """Conference prestige prior for a data-file abbr (now unique across all
    divisions). `division` is accepted for caller compatibility but unused."""
    return CONF_PRESTIGE.get(conf_abbr, 0.50)

# --------------------------------------------------------------------------
# Prestige + academics — the two recruiting levers.
#   • prestige  = athletic brand pull (a low-major D1 still outdraws most D3s).
#   • academics = academic profile (Ivies, NESCAC/UAA/Centennial D3s, the
#     service academies). High-academic recruits weigh this heavily, so a
#     smart, strong kid can pick an Ivy or a NESCAC school over a low-major D1 —
#     which is exactly how the real tennis world distributes that talent.
# Both are stable program traits in [0,1], separate from the hidden per-season
# `strength` (current on-court quality).
# --------------------------------------------------------------------------
DIVISION_PRESTIGE = {"D1": 0.62, "D2": 0.47, "D3": 0.33}

# Athletic brand bump on top of the conference prior, per program. Keys are the
# canonical school names used in the data files (e.g. UNC → "North Carolina").
PRESTIGE_SCHOOLS = {
    # --- D1 ---
    "Texas": 0.14, "Virginia": 0.14, "Ohio State": 0.14, "TCU": 0.13,
    "Georgia": 0.12, "Stanford": 0.12, "Wake Forest": 0.12,
    "Florida": 0.10, "Texas A&M": 0.10, "North Carolina": 0.10, "USC": 0.10,
    "UCLA": 0.10, "Baylor": 0.09, "Duke": 0.09, "Oklahoma": 0.09, "Auburn": 0.09,
    "Tennessee": 0.07, "Michigan": 0.07, "Illinois": 0.07, "South Carolina": 0.07,
    "Kentucky": 0.08, "Mississippi State": 0.06, "NC State": 0.06,
    "Arizona": 0.06, "Arizona State": 0.06, "Pepperdine": 0.08, "San Diego": 0.07,
    "Columbia": 0.07, "Harvard": 0.07, "Princeton": 0.06, "Cornell": 0.06,
    "Penn": 0.05, "Yale": 0.05, "Dartmouth": 0.03, "Brown": 0.03,
    "Cal": 0.06, "Oklahoma State": 0.06, "UCF": 0.05, "LSU": 0.05, "Clemson": 0.05,
    "Florida State": 0.05, "Miami": 0.04, "Texas Tech": 0.04, "Rice": 0.04,
    "Tulsa": 0.04, "Middle Tennessee": 0.04, "Old Dominion": 0.03,
    "UC Santa Barbara": 0.03, "Santa Clara": 0.03, "Memphis": 0.03, "South Florida": 0.03,
    "Liberty": 0.02, "Boise State": 0.02, "Grand Canyon": 0.02, "East Tennessee State": 0.02,
    # --- D2 ---
    "Barry": 0.20, "West Florida": 0.17, "Flagler": 0.16, "Valdosta State": 0.16,
    "Nova Southeastern": 0.14, "Columbus State": 0.13, "Washburn": 0.12, "UT Tyler": 0.11,
    "North Georgia": 0.11, "Embry-Riddle": 0.10, "Saint Leo": 0.10, "Lynn": 0.10,
    "Azusa Pacific": 0.09, "Lubbock Christian": 0.08, "Catawba": 0.08,
    "Florida Southern": 0.07, "Rollins": 0.07, "Midwestern State": 0.07,
    "Grand Valley State": 0.06, "Wayne State (MI)": 0.06, "West Alabama": 0.06,
    "Indianapolis": 0.05, "Wingate": 0.05, "Lee": 0.04, "Mississippi College": 0.04,
    "Lander": 0.04, "Harding": 0.03, "Tiffin": 0.03, "Charleston (WV)": 0.03,
    "Findlay": 0.02, "Point Loma Nazarene": 0.02, "St. Mary's (TX)": 0.02,
    # --- D3 ---
    "Chicago": 0.15, "Emory": 0.18, "Claremont-Mudd-Scripps": 0.17,
    "Grinnell": 0.08, "TCNJ": 0.05,
    "Case Western Reserve": 0.16, "Washington University in St. Louis": 0.15,
    "Middlebury": 0.15, "Williams": 0.14, "Tufts": 0.14, "Bowdoin": 0.13,
    "Johns Hopkins": 0.12, "MIT": 0.11, "Carnegie Mellon": 0.11, "Amherst": 0.11,
    "Pomona-Pitzer": 0.11, "Swarthmore": 0.10, "Wesleyan": 0.10, "Denison": 0.10,
    "Trinity (TX)": 0.08, "Washington and Lee": 0.08, "Gustavus Adolphus": 0.08,
    "Kenyon": 0.07, "NYU": 0.06, "Brandeis": 0.06, "Babson": 0.06, "Rochester": 0.05,
    "Vassar": 0.05, "Skidmore": 0.05, "Redlands": 0.05, "Whitman": 0.04,
    "Mary Washington": 0.04, "Christopher Newport": 0.04,
}

# Per-conference academic prior (default by division below). Academic leagues
# across all three divisions.
ACADEMIC_CONF = {
    "Ivy": 0.97, "Patriot": 0.82, "Big East": 0.62, "ACC": 0.62, "Big Ten": 0.60,
    # D3 academic conferences
    "NESCAC": 0.96, "UAA": 0.95, "Centennial": 0.92, "Liberty League": 0.86,
    "NEWMAC": 0.86, "SCIAC": 0.86, "NCAC": 0.82, "MWC": 0.80, "SAA": 0.80,
    "ODAC": 0.70, "CCIW": 0.68, "Empire 8": 0.66,
}

# Academic powerhouses regardless of league (overrides the conference prior).
ACADEMIC_SCHOOLS = {
    # D1
    "Stanford": 0.97, "Duke": 0.95, "Northwestern": 0.93, "Vanderbilt": 0.93,
    "Notre Dame": 0.93, "Rice": 0.93, "Virginia": 0.90, "Georgia Tech": 0.90,
    "Michigan": 0.88, "North Carolina": 0.88, "California": 0.90, "Wake Forest": 0.88,
    "Boston College": 0.85, "USC": 0.82, "Columbia": 0.97, "Cornell": 0.95,
    "Harvard": 0.99, "Princeton": 0.99, "Yale": 0.98, "Pennsylvania": 0.97,
    "Brown": 0.96, "Dartmouth": 0.96, "Army": 0.86, "Navy": 0.86, "Air Force": 0.85,
    # D3 academic flagships
    "MIT": 0.99, "Caltech": 0.99, "Chicago": 0.98, "Washington University": 0.96,
    "Johns Hopkins": 0.96, "Emory": 0.95, "Carnegie Mellon": 0.95, "Swarthmore": 0.97,
    "Williams": 0.96, "Amherst": 0.96, "Pomona-Pitzer": 0.95, "Bowdoin": 0.95,
    "Middlebury": 0.94, "Tufts": 0.93, "Wellesley": 0.93, "Carleton": 0.94,
    "Haverford": 0.93, "Wesleyan": 0.92, "Bates": 0.91, "Colby": 0.91,
    "Case Western Reserve": 0.92, "Brandeis": 0.92, "NYU": 0.90, "Rochester": 0.90,
    "Kenyon": 0.88, "Claremont-Mudd-Scripps": 0.93,
}


def _prestige_with_prior(school: str, conf_prior: float, division: str) -> float:
    """Per-school prestige from a conference prestige prior, preserving each
    school's blue-blood bump. Used both for the base value and when a conference
    prestige override shifts the whole league."""
    base = DIVISION_PRESTIGE.get(division, 0.40)
    p = base + (conf_prior - 0.50) * 0.6 + PRESTIGE_SCHOOLS.get(school, 0.0)
    return max(0.12, min(0.97, p))


def _prestige(school: str, conf_abbr: str, division: str) -> float:
    return _prestige_with_prior(school, conf_prestige(conf_abbr, division), division)


def _academic_prior(conf_abbr: str, division: str) -> float:
    """The default academic prior for a conference (before per-school flagships)."""
    if conf_abbr in ACADEMIC_CONF:
        return ACADEMIC_CONF[conf_abbr]
    return {"D1": 0.55, "D2": 0.48, "D3": 0.62}.get(division, 0.55)


def _academics_with_prior(school: str, conf_prior: float, division: str) -> float:
    """Per-school academics from a conference academic prior. Academic flagships
    (ACADEMIC_SCHOOLS) keep their listed profile; everyone else tracks the prior,
    with a small deterministic spread so peers aren't identical."""
    a = ACADEMIC_SCHOOLS.get(school, conf_prior)
    jitter = (_stable_seed(f"acad|{school}") % 1000) / 1000.0 - 0.5
    return max(0.20, min(0.99, a + jitter * 0.06))


def _academics(school: str, conf_abbr: str, division: str) -> float:
    return _academics_with_prior(school, _academic_prior(conf_abbr, division), division)


def _facilities(school: str, conf_abbr: str, division: str) -> float:
    """A plain 0..1 facilities grade — tracks prestige with per-school spread."""
    pres = _prestige(school, conf_abbr, division)
    jitter = (_stable_seed(f"fac|{school}") % 1000) / 1000.0 - 0.5
    return max(0.20, min(0.97, 0.30 + 0.55 * pres + 0.30 * jitter))


# --------------------------------------------------------------------------
# Geography — real campus locations (data/ncaa/locations.json, researched per
# school). State → coarse region drives recruiting proximity and cross-division
# scheduling (nearby schools across classifications can meet).
# --------------------------------------------------------------------------
STATE_REGION = {
    # Northeast
    "ME": "NE", "NH": "NE", "VT": "NE", "MA": "NE", "RI": "NE", "CT": "NE",
    # Mid-Atlantic
    "NY": "MATL", "NJ": "MATL", "PA": "MATL", "MD": "MATL", "DE": "MATL", "DC": "MATL",
    # Southeast
    "VA": "SE", "WV": "SE", "NC": "SE", "SC": "SE", "GA": "SE", "FL": "SE",
    "KY": "SE", "TN": "SE", "AL": "SE", "MS": "SE",
    # Midwest
    "OH": "MW", "MI": "MW", "IN": "MW", "IL": "MW", "WI": "MW", "MN": "MW",
    "IA": "MW", "MO": "MW", "ND": "MW", "SD": "MW", "NE": "MW", "KS": "MW",
    # South Central
    "TX": "SC", "OK": "SC", "AR": "SC", "LA": "SC",
    # Mountain / West
    "CO": "MTN", "UT": "MTN", "NV": "MTN", "AZ": "MTN", "NM": "MTN",
    "MT": "MTN", "ID": "MTN", "WY": "MTN",
    # Pacific
    "CA": "W", "OR": "W", "WA": "W", "AK": "W", "HI": "W", "BC": "W",
}
# Adjacent regions (share a meaningful border) → a mid proximity bump.
REGION_ADJACENT = {
    "NE": {"MATL"}, "MATL": {"NE", "SE", "MW"}, "SE": {"MATL", "MW", "SC"},
    "MW": {"MATL", "SE", "SC", "MTN"}, "SC": {"SE", "MW", "MTN"},
    "MTN": {"MW", "SC", "W"}, "W": {"MTN"},
}

_LOCATIONS: dict | None = None


def _locations() -> dict:
    global _LOCATIONS
    if _LOCATIONS is None:
        path = os.path.join(_DATA_DIR, "locations.json")
        try:
            with open(path, encoding="utf-8") as fh:
                _LOCATIONS = json.load(fh).get("schools", {})
        except FileNotFoundError:
            _LOCATIONS = {}
    return _LOCATIONS


def location(school: str) -> tuple[str, str, str]:
    """(city, state, region) for a school; ('', '', '') if unknown."""
    loc = _locations().get(school)
    if not loc:
        return "", "", ""
    state = loc.get("state", "")
    return loc.get("city", ""), state, STATE_REGION.get(state, "")


_CITIES_BY_STATE: dict | None = None


def cities_by_state() -> dict[str, list[str]]:
    """{state-abbr: [real city, ...]} from the researched campus-location database —
    the real (city, state) pairs, so a hometown's city actually belongs to its state."""
    global _CITIES_BY_STATE
    if _CITIES_BY_STATE is None:
        out: dict[str, list[str]] = {}
        for loc in _locations().values():
            city, state = loc.get("city"), loc.get("state")
            if city and state:
                lst = out.setdefault(state, [])
                if city not in lst:
                    lst.append(city)
        _CITIES_BY_STATE = out
    return _CITIES_BY_STATE


def cities_in_state(state_abbr: str) -> list[str]:
    """Real cities located in `state_abbr` (USPS), empty if none on file."""
    return cities_by_state().get(state_abbr, [])


def region_proximity(region_a: str, region_b: str) -> float:
    """0..1 closeness of two regions: same=1, adjacent=0.5, else 0."""
    if not region_a or not region_b:
        return 0.0
    if region_a == region_b:
        return 1.0
    return 0.5 if region_b in REGION_ADJACENT.get(region_a, ()) else 0.0


@dataclass
class Program:
    school: str
    conf: str
    conf_abbr: str
    division: str
    gender: str
    abbr: str
    color: str
    strength: float
    prestige: float = 0.50
    academics: float = 0.50
    facilities: float = 0.50
    city: str = ""              # real campus location (data/ncaa/locations.json)
    state: str = ""
    region: str = ""            # coarse region (STATE_REGION) for recruiting proximity
    autobid: bool = True

    @property
    def key(self) -> str:
        return f"{self.school}|{self.division}|{self.gender}"

    @property
    def location(self) -> str:
        return f"{self.city}, {self.state}" if self.city else ""


@dataclass
class Division:
    division: str
    gender: str
    programs: list[Program] = field(default_factory=list)
    conferences: dict[str, list[Program]] = field(default_factory=dict)

    def by_school(self, school: str) -> Program | None:
        return next((p for p in self.programs if p.school == school), None)


def crest(school: str) -> tuple[str, str]:
    """(abbr, color) for a school - real override or deterministic fallback."""
    if school in SCHOOL_META:
        return SCHOOL_META[school]
    abbr = "".join(w[0] for w in school.split()[:4]).upper() or school[:3].upper()
    hue = (sum(ord(c) for c in school) * 47) % 360
    return abbr, f"oklch(0.52 0.13 {hue})"


def _stable_seed(value: str) -> int:
    return int.from_bytes(hashlib.blake2s(value.encode("utf-8"), digest_size=8).digest(), "big")


def _latent_strength(school: str, conf_abbr: str, gender: str, division: str) -> float:
    # Mean tracks the (fixed) conference prestige prior; the draw is salted by the
    # active league so a program's on-court strength varies per New League within
    # its prestige-derived range, while the prestige baselines stay constant.
    prior = conf_prestige(conf_abbr, division)
    rng = random.Random(f"{WORLD_SALT}|{school}|{conf_abbr}|{gender}|{division}|{SEASON_SEED}")
    return max(0.12, min(0.95, rng.gauss(prior, 0.11)))


def load_division(division: str, gender: str) -> Division:
    """Load a division x gender universe from data/ncaa/<div>_<gender>.json."""
    path = os.path.join(_DATA_DIR, f"{division.lower()}_{gender.lower()}.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    div = Division(division=division, gender=gender)
    for c in data.get("conferences", []):
        abbr = c.get("abbr", c["name"][:4].upper())
        members: list[Program] = []
        for school in c.get("teams", []):
            cab, color = crest(school)
            city, state, region = location(school)
            members.append(Program(
                school=school, conf=c["name"], conf_abbr=abbr,
                division=division, gender=gender, abbr=cab, color=color,
                strength=_latent_strength(school, abbr, gender, division),
                prestige=_prestige(school, abbr, division),
                academics=_academics(school, abbr, division),
                facilities=_facilities(school, abbr, division),
                city=city, state=state, region=region,
                autobid=bool(c.get("autobid", True)),
            ))
        div.conferences[c["name"]] = members
        div.programs.extend(members)
    # Editor ratings overrides (recruiting levers only — on-court strength is
    # left untouched). Conference-level priors shift a whole league first
    # (preserving each school's relative bump); per-team overrides then win.
    try:
        from . import overrides
        conf_pres = overrides.get_conf_prestige()
        conf_acad = overrides.get_conf_academics()
        if conf_pres or conf_acad:
            for p in div.programs:
                if p.conf in conf_pres:
                    p.prestige = _prestige_with_prior(p.school, conf_pres[p.conf], p.division)
                if p.conf in conf_acad:
                    p.academics = _academics_with_prior(p.school, conf_acad[p.conf], p.division)
        pres = overrides.get_prestige()
        acad = overrides.get_academics()
        if pres or acad:
            for p in div.programs:
                if p.school in pres:
                    p.prestige = pres[p.school]
                if p.school in acad:
                    p.academics = acad[p.school]
    except Exception:
        pass
    return div


ROSTER_SIZE = 8
SCHOLARSHIP_SLOTS = 6        # top of the roster carry scholarships; the rest are walk-ons
CLASS_YEARS = ["Fr", "So", "Jr", "Sr"]


# --- Talent calibration (grade units, 20-80) -----------------------------------
# Visible college ability (after class-scaled development) should land in
# realistic UTR-equivalent STR bands per division x gender: D1 > D2 > D3, men a
# ~2.6-UTR ceiling above women, dense within a flight. The grade clamp (80) and
# overall_to_str ceiling (57) act as the governor — even the best sit near, but
# rarely at, the top of the band.
# Per (division, gender): (talent-grade mean at MEDIAN program strength, spread
# across program tiers). Men sit a ceiling above women, and the women's pools use
# a flatter spread so their distribution is *compressed* (lower top, not merely
# shifted) — mirroring real UTR, where the women's band is both lower and tighter
# than the men's. D1 > D2 > D3.
_TALENT = {
    ("D1", "men"):   (68.5, 12.0), ("D1", "women"): (58.0, 8.0),
    ("D2", "men"):   (63.5, 12.0), ("D2", "women"): (53.0, 8.0),
    ("D3", "men"):   (58.5, 12.0), ("D3", "women"): (48.0, 8.0),
}
# College players are largely developed; class year scales how much of the
# ceiling is realized (freshmen keep headroom to grow year over year).
_CLASS_MATURITY = {"Fr": (0.83, 0.90), "So": (0.87, 0.93),
                   "Jr": (0.90, 0.96), "Sr": (0.93, 0.99)}


def _talent_mean(strength: float, division: str, gender: str) -> float:
    """Program strength + division + gender → a roster talent-grade mean."""
    base, spread = _TALENT.get((division, gender), (60.0, 12.0))
    return max(24.0, min(80.0, base + spread * (strength - 0.5)))


def _talent_from_strength(strength: float, division: str = "D1", gender: str = "men") -> float:
    """Back-compat alias for `_talent_mean` (callers should pass the program's
    division/gender so recruit + transfer talent stay on the same calibrated
    scale as rosters)."""
    return _talent_mean(strength, division, gender)


def _pick_gender(g: str) -> str:
    return "male" if g == "men" else "female" if g == "women" else g


_roster_cache: dict[str, list] = {}
_squad_cache: dict[str, Team] = {}
_eff_cache: dict[str, list] = {}             # roster AFTER editor overrides
_index_cache: dict[str, object] = {}         # pid -> base Prospect, across all universes

# Every division×gender universe — used to build the global pid→player index so
# the editor can move a player from ANY program to ANY other.
UNIVERSE_PAIRS = [("D1", "men"), ("D1", "women"), ("D2", "men"),
                  ("D2", "women"), ("D3", "men"), ("D3", "women")]


def reset_caches() -> None:
    """Clear roster/squad caches — required when a League mutates rosters or the
    editor changes an override."""
    _roster_cache.clear()
    _squad_cache.clear()
    _eff_cache.clear()
    _index_cache.clear()


def _base_roster(p: Program):
    """Deterministic roster of persistent Prospects for a program (cached),
    sorted best → worst (the ladder). Talent prior tracks program strength;
    class years distributed Fr–Sr; top-6 scholarship / rest walk-ons; stable
    pids. Each Prospect carries the full rich attribute model. This is the
    un-edited base — `build_roster` layers editor overrides on top."""
    if p.key in _roster_cache:
        return _roster_cache[p.key]
    from generators import make_name_picker
    from .development import generate_prospect, make_pid
    from . import worldconfig
    seed = _stable_seed(f"{WORLD_SALT}|{p.key}") & 0xFFFFFFFF
    rng = random.Random(seed)
    name_fn = make_name_picker(random.Random(seed ^ 0x5EED), gender=_pick_gender(p.gender),
                               region_weights=worldconfig.region_weights())
    tmean = _talent_mean(p.strength, p.division, p.gender)
    roster = []
    for i in range(ROSTER_SIZE):
        name, country = name_fn()
        cls = CLASS_YEARS[i % len(CLASS_YEARS)]
        talent = max(24.0, min(80.0, rng.gauss(tmean, 2.5)))    # tight: dense lineups
        pr = generate_prospect(rng, name, country, gender=_pick_gender(p.gender),
                               talent=talent, pid=make_pid(WORLD_SALT, p.key, i),
                               maturity_range=_CLASS_MATURITY.get(cls, (0.86, 0.98)))
        pr.class_year = cls
        # hometown / high_school / domestic are wired by generate_prospect from
        # the player's nation (real city pools + flags), so no synthetic override.
        roster.append(pr)
    roster.sort(key=lambda pr: pr.current_overall(), reverse=True)
    # Funded headcount varies by classification (app.scholarships); the
    # equivalency split + display fractions layer on top (app.economy).
    from app import economy
    economy.allocate_scholarships(roster, p.division, p.gender,
                                  scholarship_slots=scholarships.slots(p))
    _roster_cache[p.key] = roster
    return roster


def _global_index() -> dict:
    """pid → base Prospect, over every program in every universe. Lets the editor
    pull a moved-in player by pid regardless of their original school/division."""
    if _index_cache:
        return _index_cache
    for division, gender in UNIVERSE_PAIRS:
        try:
            div = load_division(division, gender)
        except FileNotFoundError:
            continue
        for prog in div.programs:
            for pr in _base_roster(prog):
                _index_cache[pr.pid] = pr
    return _index_cache


def player_by_pid(pid: str):
    """Look up a base Prospect by pid across all universes (editor support)."""
    return _global_index().get(pid)


def build_roster(p: Program):
    """Program roster with editor overrides applied. With no overrides this is
    exactly the deterministic `_base_roster`. Overrides can (a) move a player to
    any program in any division and (b) pin a team's lineup order — so the dual
    simulator, team pages and season sims all reflect your edits."""
    from app import overrides as ov
    if not ov.any_overrides():
        return _base_roster(p)
    if p.key in _eff_cache:
        return _eff_cache[p.key]
    moves = ov.get_moves()        # pid -> destination school
    lineups = ov.get_lineups()    # school -> ordered pids

    # Base players minus anyone moved away to a different school.
    roster = [pr for pr in _base_roster(p)
              if moves.get(pr.pid, p.school) == p.school]
    # Players moved INTO this school from elsewhere (deep-copied so we never
    # mutate the cached base roster of their origin program).
    idx = _global_index()
    present = {pr.pid for pr in roster}
    pg = _pick_gender(p.gender)
    for pid, dest in moves.items():
        if dest == p.school and pid not in present and pid in idx:
            src = idx[pid]
            if getattr(src, "gender", pg) != pg:      # don't bleed across men's/women's
                continue
            roster.append(copy.deepcopy(src))
            present.add(pid)

    roster.sort(key=lambda pr: pr.current_overall(), reverse=True)
    order = lineups.get(p.school)
    if order:
        pos = {pid: i for i, pid in enumerate(order)}
        big = len(order) + len(roster)
        roster.sort(key=lambda pr: pos.get(pr.pid, big))   # stable; pinned to front
    from app import economy
    economy.allocate_scholarships(roster, p.division, p.gender,
                                  scholarship_slots=scholarships.slots(p))
    _eff_cache[p.key] = roster
    return roster


def squad_and_ladder(p: Program) -> tuple[Team, list]:
    """(engine Team, top-6 ladder of Prospects). Team.singles[i] is exactly
    ladder[i], so a singles line's player identity (pid) is unambiguous."""
    ladder = sorted(build_roster(p), key=lambda pr: pr.current_overall(), reverse=True)[:6]
    return Team(name=p.school, singles=[pr.engine_player() for pr in ladder]), ladder


def build_squad(p: Program) -> Team:
    """Deterministic engine Team (top-6 ladder) for a program (cached)."""
    if p.key in _squad_cache:
        return _squad_cache[p.key]
    team = squad_and_ladder(p)[0]
    _squad_cache[p.key] = team
    return team
