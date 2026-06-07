"""
NCAA program model + division loader.

Reads the conference/team JSON in data/ncaa/ (compiled from NCAA/ITA/Wikipedia)
and turns each school into a `Program` with:
  - crest abbr + color (real overrides for marquee schools, deterministic else)
  - a hidden **latent strength** in [0,1] — the program's true tennis quality,
    seeded deterministically from (school, gender, season) with a per-conference
    prestige prior. The season is simulated from these; the Power Index (P5) then
    *estimates* them back out of results. Strength is never shown directly.

`build_squad()` turns a Program into a deterministic 6-player engine Team
(ladder: court 1 strongest → court 6 weakest).
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field

from engine import random_player, Team

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
    "UCLA": ("UCLA", "#2d68c4"), "Georgia": ("UGA", "#ba0c2f"), "Ohio State": ("OSU", "#bb0000"),
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
    autobid: bool = True

    @property
    def key(self) -> str:
        return f"{self.school}|{self.division}|{self.gender}"


@dataclass
class Division:
    division: str
    gender: str
    programs: list[Program] = field(default_factory=list)
    conferences: dict[str, list[Program]] = field(default_factory=dict)

    def by_school(self, school: str) -> Program | None:
        return next((p for p in self.programs if p.school == school), None)


def crest(school: str) -> tuple[str, str]:
    """(abbr, color) for a school — real override or deterministic fallback."""
    if school in SCHOOL_META:
        return SCHOOL_META[school]
    abbr = "".join(w[0] for w in school.split()[:4]).upper() or school[:3].upper()
    hue = (sum(ord(c) for c in school) * 47) % 360
    return abbr, f"oklch(0.52 0.13 {hue})"


def _latent_strength(school: str, conf_abbr: str, gender: str, division: str) -> float:
    prior = CONF_PRESTIGE.get(conf_abbr, 0.50)
    rng = random.Random(f"{school}|{conf_abbr}|{gender}|{division}|{SEASON_SEED}")
    return max(0.12, min(0.95, rng.gauss(prior, 0.11)))


def load_division(division: str, gender: str) -> Division:
    """Load a division×gender universe from data/ncaa/<div>_<gender>.json."""
    path = os.path.join(_DATA_DIR, f"{division.lower()}_{gender.lower()}.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    div = Division(division=division, gender=gender)
    for c in data.get("conferences", []):
        abbr = c.get("abbr", c["name"][:4].upper())
        members: list[Program] = []
        for school in c.get("teams", []):
            cab, color = crest(school)
            members.append(Program(
                school=school, conf=c["name"], conf_abbr=abbr,
                division=division, gender=gender, abbr=cab, color=color,
                strength=_latent_strength(school, abbr, gender, division),
                autobid=bool(c.get("autobid", True)),
            ))
        div.conferences[c["name"]] = members
        div.programs.extend(members)
    return div


def _base_from_strength(s: float) -> float:
    return max(0.38, min(0.74, 0.40 + 0.34 * s))


_squad_cache: dict[str, Team] = {}


def build_squad(p: Program) -> Team:
    """Deterministic 6-player squad for a program (cached)."""
    if p.key in _squad_cache:
        return _squad_cache[p.key]
    base = _base_from_strength(p.strength)
    seed = abs(hash(p.key)) & 0xFFFFFFFF
    rng = random.Random(seed)
    from generators import make_name_picker, region_preset
    name_fn = make_name_picker(random.Random(seed ^ 0x5EED), gender=p.gender,
                               region_weights=region_preset("global"))
    singles = []
    for i in range(6):
        name, country = name_fn()
        singles.append(random_player(rng, name, country, base=base - i * 0.012))
    team = Team(name=p.school, singles=singles)
    _squad_cache[p.key] = team
    return team
