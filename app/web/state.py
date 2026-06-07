"""
Web-layer state: run each division×gender season + bracket once and cache it
(a season is ~2s, far too heavy per request). Also shapes ranking rows for
the Power Index table.
"""
from __future__ import annotations

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
