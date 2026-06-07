"""
Web-layer state: run each division×gender season + bracket once and cache it
(a season is ~2s, far too heavy per request). Also shapes ranking rows for
the Power Index table.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from app.season import run_season
from app.bracket import select_field, run_bracket, clamp_field, FIELD_DEFAULT

DEFAULT_SEED = 2026
MY_TEAM = "Oregon"
FIELD_PRESETS = [32, 64, 76, 96]    # offered in the UI; any 16–128 works

# Division×gender universes exposed in the UI (value, division, gender, label).
UNIVERSES = [
    ("D1-men", "D1", "men", "D1 Men"),
    ("D1-women", "D1", "women", "D1 Women"),
    ("D2-men", "D2", "men", "D2 Men"),
    ("D2-women", "D2", "women", "D2 Women"),
    ("D3-men", "D3", "men", "D3 Men"),
    ("D3-women", "D3", "women", "D3 Women"),
]

# Conference → display tier (mirrors the design's P5 / MID / IVY badges).
_P5 = {"ACC", "SEC", "Big Ten", "Big 12", "Pac-12"}

_season_cache: dict = {}
_bracket_cache: dict = {}


def get_season(division: str, gender: str, seed: int = DEFAULT_SEED):
    key = (division, gender, seed)
    if key not in _season_cache:
        _season_cache[key] = run_season(division, gender, seed=seed)
    return _season_cache[key]


def get_bracket(division: str, gender: str, seed: int = DEFAULT_SEED, size: int = FIELD_DEFAULT):
    size = clamp_field(size)
    key = (division, gender, seed, size)
    if key not in _bracket_cache:
        sr = get_season(division, gender, seed)
        seeded, autobids = select_field(sr.programs, sr.ratings, sr.champions, size=size)
        _bracket_cache[key] = run_bracket(seeded, autobids, seed=seed)
    return _bracket_cache[key]


def _tier(division: str, conf_abbr: str, conf: str) -> str:
    if division != "D1":
        return division   # D2 / D3 — flat tiers, badge shows the division
    if conf == "Ivy League" or conf_abbr == "Ivy":
        return "IVY"
    return "P5" if conf_abbr in _P5 else "MID"


@dataclass
class LiveRow:
    rk: int
    school: str
    conf: str
    conf_abbr: str
    tier: str
    cr: int
    rec: str
    crec: str
    pi: float
    apr: float
    fqi: float
    me: bool = False

    @property
    def rank_class(self) -> str:
        return "gold" if self.rk == 1 else "bronze" if self.rk <= 3 else ""

    @property
    def confrk_class(self) -> str:
        return "lead" if self.cr == 1 else "bronze" if self.cr <= 3 else ""

    @property
    def apr_kind(self) -> str:
        return "muted" if self.apr < 0.60 else "good"

    @property
    def fqi_kind(self) -> str:
        return "muted" if self.fqi < 0.72 else "good"

    def fmt(self, v: float) -> str:
        return f"{v:.4f}"


def ranking_rows(division: str, gender: str, seed: int = DEFAULT_SEED) -> list[LiveRow]:
    sr = get_season(division, gender, seed)
    # conference rank + record lookup
    conf_pos: dict[str, tuple[int, int, int]] = {}
    for conf, table in sr.standings.items():
        for i, (p, w, l) in enumerate(table, 1):
            conf_pos[p.school] = (i, w, l)
    rows: list[LiveRow] = []
    for rk, p in enumerate(sr.ranked(), 1):
        r = sr.ratings[p.school]
        cr, cw, cl = conf_pos.get(p.school, (0, 0, 0))
        rows.append(LiveRow(
            rk=rk, school=p.school, conf=p.conf, conf_abbr=p.conf_abbr,
            tier=_tier(division, p.conf_abbr, p.conf), cr=cr, rec=r.record, crec=f"{cw}-{cl}",
            pi=r.pi, apr=r.apr, fqi=r.fqi, me=(p.school == MY_TEAM),
        ))
    return rows


def conferences_for(division: str, gender: str) -> list[str]:
    sr = get_season(division, gender)
    return ["All"] + sorted(sr.standings.keys())


# --------------------------------------------------------------------------
# Recruiting (juniors) — board + profile
# --------------------------------------------------------------------------
from app.juniors import (generate_class, national_rankings, state_rankings,
                         international_rankings, US_STATES)
from app.development import overall_to_str

_recruit_cache: dict = {}
RECRUIT_GENDERS = {"men": "male", "women": "female"}


def get_recruits(gender: str, grad_year: int, seed: int = DEFAULT_SEED):
    """Cached recruiting class. `gender` is "male"/"female" (juniors vocab)."""
    key = (gender, grad_year, seed)
    if key not in _recruit_cache:
        rng = random.Random(f"{seed}|recruits|{gender}|{grad_year}")
        klass = generate_class(rng, n=400, grad_year=grad_year, gender=gender)
        national_rankings(klass)        # assigns recruit_rank / tier / stars
        _recruit_cache[key] = klass
    return _recruit_cache[key]


def get_recruit(gender: str, grad_year: int, pid: str, seed: int = DEFAULT_SEED):
    return next((p for p in get_recruits(gender, grad_year, seed).recruits if p.pid == pid), None)


def recruit_rows(gender: str, grad_year: int, scope: str = "national", state: str = ""):
    klass = get_recruits(gender, grad_year)
    if scope == "state":
        src = state_rankings(klass, state)
    elif scope == "intl":
        src = international_rankings(klass)
    else:
        src = national_rankings(klass)
    return list(enumerate(src, 1))      # (board_rank, Prospect)


def recruit_profile(p, gender: str, grad_year: int):
    """Build the profile view: national/regional rankings + scouting reports."""
    klass = get_recruits(gender, grad_year)
    if p.domestic:
        regional = state_rankings(klass, p.region)
        region_rank = next((i for i, q in enumerate(regional, 1) if q.pid == p.pid), None)
        region_label = p.region
    else:
        intl = international_rankings(klass)
        region_rank = next((i for i, q in enumerate(intl, 1) if q.pid == p.pid), None)
        region_label = "International"
    return {
        "national_rank": p.recruit_rank,
        "region_rank": region_rank,
        "region_label": region_label,
        "service": overall_to_str(p.scouting_report("service")),   # two independent ceiling reads
        "dept": overall_to_str(p.scouting_report("dept")),
        "projection": overall_to_str(p.project(4)),
    }


def teams_by_conference(division: str, gender: str, conf_filter: str = "All"):
    """[(conference, [ {school, abbr, color, pi, rec, tier} ... ]) ...] for the
    Teams index — teams grouped by conference, ranked within each by Power Index."""
    from .rankings_data import crest
    rows = ranking_rows(division, gender)
    groups: dict[str, list] = {}
    for r in rows:
        if conf_filter != "All" and r.conf != conf_filter:
            continue
        abbr, color = crest(r.school)
        groups.setdefault(r.conf, []).append(
            {"school": r.school, "abbr": abbr, "color": color, "pi": r.pi,
             "rec": r.rec, "tier": r.tier})
    return sorted(groups.items())


def head_coach(school: str, division: str = "D1", gender: str = "men"):
    """A deterministic head coach (real name) for a program."""
    import random
    from generators import make_name_picker, region_preset
    from app.coaches import generate_coach
    name_fn = make_name_picker(random.Random(f"coachname|{school}|{gender}"),
                               gender="mixed", region_weights=region_preset("global"))
    nm, _ = name_fn()
    return generate_coach(random.Random(f"coach|{school}|{gender}"), nm, school=school)


def team_roster(division: str, gender: str, school: str):
    """Roster rows for a Team page: (player, line, live STR, reliability, W-L)."""
    sr = get_season(division, gender)
    roster = sr.rosters.get(school, [])
    rows = []
    for p in sorted(roster, key=lambda q: q.current_overall(), reverse=True):
        s, rel = sr.player_str.get(p.pid, (p.str_value(), 0.0))
        w, l = sr.player_record.get(p.pid, (0, 0))
        rows.append({"p": p, "str": round(s, 1), "rel": rel, "w": w, "l": l})
    for i, r in enumerate(rows, 1):
        r["line"] = i if i <= 6 else None       # top 6 are the singles lineup
    return rows
