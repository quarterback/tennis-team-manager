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
from generators.cities import program_city

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
    city: str = ""              # home city (generated, deterministic — see generators.cities)
    state: str = ""            # home state abbr

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
            city, st = program_city(school)
            members.append(Program(
                school=school, conf=c["name"], conf_abbr=abbr,
                division=division, gender=gender, abbr=cab, color=color,
                strength=_latent_strength(school, abbr, gender, division),
                autobid=bool(c.get("autobid", True)),
                city=city, state=st,
            ))
        div.conferences[c["name"]] = members
        div.programs.extend(members)
    return div


ROSTER_SIZE = 8
SCHOLARSHIP_SLOTS = 6        # top of the roster carry scholarships; the rest are walk-ons
CLASS_YEARS = ["Fr", "So", "Jr", "Sr"]


def _talent_from_strength(s: float) -> float:
    """Program latent strength (0–1) → a talent-grade mean (20–80) for the roster,
    targeting the calibration STR bands (top D1 ~52–55, low-major ~44)."""
    return max(24.0, min(78.0, 32.0 + 44.0 * s))


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
    from generators import make_name_picker, region_preset
    from .development import generate_prospect, make_pid
    seed = _stable_seed(p.key) & 0xFFFFFFFF
    rng = random.Random(seed)
    name_fn = make_name_picker(random.Random(seed ^ 0x5EED), gender=_pick_gender(p.gender),
                               region_weights=region_preset("tennis_global"))
    tmean = _talent_from_strength(p.strength)
    roster = []
    for i in range(ROSTER_SIZE):
        name, country = name_fn()
        talent = max(24.0, min(80.0, rng.gauss(tmean, 5.0)))
        pr = generate_prospect(rng, name, country, gender=_pick_gender(p.gender),
                               talent=talent, pid=make_pid(p.key, i))
        pr.class_year = CLASS_YEARS[i % len(CLASS_YEARS)]
        # hometown / high_school / domestic are wired by generate_prospect from
        # the player's nation (real city pools + flags), so no synthetic override.
        roster.append(pr)
    roster.sort(key=lambda pr: pr.current_overall(), reverse=True)
    # Equivalency scholarships: walk-ons (bottom of roster) + fractional aid
    # spread across the recruited core within the division/gender cap.
    from app import economy
    economy.allocate_scholarships(roster, p.division, p.gender,
                                  scholarship_slots=SCHOLARSHIP_SLOTS)
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
                                  scholarship_slots=SCHOLARSHIP_SLOTS)
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
