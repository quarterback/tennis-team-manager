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
    "ACC": 0.74, "SEC": 0.74, "Big 12": 0.70, "Pac-12": 0.70, "Big Ten": 0.64,
    "WCC": 0.60, "AAC": 0.58, "Big West": 0.58, "Ivy": 0.60, "CUSA": 0.54,
    "Sun Belt": 0.52, "MVC": 0.50, "Mountain West": 0.54, "MW": 0.54, "A-10": 0.52,
    "Big East": 0.56, "ASUN": 0.50, "CAA": 0.50, "Horizon": 0.46, "MAC": 0.48,
    "Patriot": 0.48, "SoCon": 0.48, "Summit": 0.44, "Southland": 0.44, "Big Sky": 0.42,
    "Big South": 0.44, "NEC": 0.42, "OVC": 0.44, "MAAC": 0.46, "WAC": 0.50,
    "SWAC": 0.38, "MEAC": 0.38, "America East": 0.44,
}

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
DIVISION_PRESTIGE = {"D1": 0.62, "D2": 0.40, "D3": 0.30}

# Athletic blue-bloods get a brand bump on top of their conference prior.
PRESTIGE_SCHOOLS = {
    "TCU": 0.12, "Texas": 0.12, "USC": 0.10, "UCLA": 0.10, "Georgia": 0.10,
    "Florida": 0.10, "Ohio State": 0.10, "Virginia": 0.10, "Wake Forest": 0.10,
    "Baylor": 0.08, "Kentucky": 0.08, "Tennessee": 0.08, "Stanford": 0.10,
    "Texas A&M": 0.08, "North Carolina": 0.08, "Michigan": 0.06, "Pepperdine": 0.06,
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


def _prestige(school: str, conf_abbr: str, division: str) -> float:
    base = DIVISION_PRESTIGE.get(division, 0.40)
    conf = CONF_PRESTIGE.get(conf_abbr, 0.50)
    p = base + (conf - 0.50) * 0.6 + PRESTIGE_SCHOOLS.get(school, 0.0)
    return max(0.12, min(0.97, p))


def _academics(school: str, conf_abbr: str, division: str) -> float:
    if school in ACADEMIC_SCHOOLS:
        a = ACADEMIC_SCHOOLS[school]
    elif conf_abbr in ACADEMIC_CONF:
        a = ACADEMIC_CONF[conf_abbr]
    else:
        a = {"D1": 0.55, "D2": 0.48, "D3": 0.62}.get(division, 0.55)
    # Small deterministic per-school spread so unlisted peers aren't identical.
    jitter = (_stable_seed(f"acad|{school}") % 1000) / 1000.0 - 0.5
    return max(0.20, min(0.99, a + jitter * 0.06))


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
    prior = CONF_PRESTIGE.get(conf_abbr, 0.50)
    rng = random.Random(f"{school}|{conf_abbr}|{gender}|{division}|{SEASON_SEED}")
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
    # Editor prestige overrides — let specific programs stand out (and recruit)
    # regardless of their default conference-derived prestige.
    try:
        from . import overrides
        pres = overrides.get_prestige()
        if pres:
            for p in div.programs:
                if p.school in pres:
                    p.prestige = pres[p.school]
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
    seed = _stable_seed(p.key) & 0xFFFFFFFF
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
                               talent=talent, pid=make_pid(p.key, i),
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
