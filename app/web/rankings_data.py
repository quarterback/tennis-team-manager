"""
Power-Index ranking rows for the rankings page.

SEED DATA for now: the real-school Division I men's field from the design
prototype. This module is the seam where the **rating engine (roadmap P5 —
modified-UTR / Power Index = 50% APR + 50% FQI)** will plug in: replace
`get_rankings()` with a query over simulated dual results and the shape below
stays identical, so the template never changes.

Row shape:
    rk, school, conf, tier ('P5'|'MID'|'IVY'), cr (conference rank),
    rec, h2h=(text, tone), crec, pi, apr, fqi, me (bool, "your team")
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RankRow:
    rk: int
    school: str
    conf: str
    tier: str
    cr: int
    rec: str
    h2h_text: str
    h2h_tone: str
    crec: str
    pi: float
    apr: float
    fqi: float
    me: bool = False

    # --- presentation helpers (mirror Rankings.jsx / baseline-kit.jsx) ---
    @property
    def rank_class(self) -> str:
        if self.rk == 1:
            return "gold"
        if self.rk <= 3:
            return "bronze"
        return ""

    @property
    def confrk_class(self) -> str:
        if self.cr == 1:
            return "lead"
        if self.cr <= 3:
            return "bronze"
        return ""

    @property
    def apr_kind(self) -> str:
        return "muted" if self.apr < 0.72 else "good"

    @property
    def fqi_kind(self) -> str:
        return "muted" if self.fqi < 0.72 else "good"

    def fmt(self, v: float) -> str:
        return f"{v:.4f}"


_SEED = [
    (1,  "TCU",            "Big 12",   "P5", 1, "24-2",  "5-0",   "win",  "12-1", 0.9312, 0.9109, 0.9508),
    (2,  "Ohio State",     "Big Ten",  "P5", 1, "22-3",  "6-1",   "win",  "11-1", 0.9128, 0.8766, 0.9470),
    (3,  "Texas",          "SEC",      "P5", 1, "21-4",  "8-1",   "win",  "10-2", 0.8917, 0.8528, 0.9249),
    (4,  "Wake Forest",    "ACC",      "P5", 1, "20-5",  "10-0",  "win",  "12-0", 0.8719, 0.7997, 0.9345),
    (5,  "Virginia",       "ACC",      "P5", 2, "19-5",  "6-0",   "win",  "8-0",  0.8664, 0.8180, 0.9001),
    (6,  "Kentucky",       "SEC",      "P5", 2, "19-6",  "5-2",   "win",  "8-1",  0.8391, 0.7964, 0.8643),
    (7,  "Stanford",       "ACC",      "P5", 3, "18-6",  "5-1",   "win",  "8-1",  0.8295, 0.7889, 0.8527),
    (8,  "Tennessee",      "SEC",      "P5", 3, "18-7",  "6-3",   "win",  "5-3",  0.8222, 0.7971, 0.8398),
    (9,  "Oregon",         "Big Ten",  "P5", 2, "18-4",  "9-0",   "win",  "11-0", 0.8174, 0.7896, 0.8351, True),
    (10, "Florida",        "SEC",      "P5", 4, "17-7",  "7-3",   "win",  "9-3",  0.8068, 0.7633, 0.8400),
    (11, "USC",            "Big Ten",  "P5", 3, "17-8",  "10-2",  "win",  "10-2", 0.8011, 0.7605, 0.8236),
    (12, "Baylor",         "Big 12",   "P5", 2, "16-8",  "9-3",   "win",  "9-3",  0.7807, 0.7502, 0.8015),
    (13, "Texas A&M",      "SEC",      "P5", 5, "16-9",  "6-4",   "win",  "8-4",  0.7784, 0.7648, 0.7866),
    (14, "Michigan",       "Big Ten",  "P5", 4, "15-9",  "7-0",   "win",  "11-0", 0.7765, 0.7648, 0.7807),
    (15, "NC State",       "ACC",      "P5", 4, "15-10", "9-1",   "win",  "9-1",  0.7659, 0.7536, 0.7780),
    (16, "Columbia",       "Ivy",      "IVY",1, "14-3",  "9-3",   "win",  "9-0",  0.7634, 0.7605, 0.7662),
    (17, "San Diego",      "WCC",      "MID",1, "18-5",  "6-1",   "win",  "7-0",  0.7481, 0.7102, 0.7615),
    (18, "Old Dominion",   "Sun Belt", "MID",1, "17-6",  "4-5-1", "loss", "8-1",  0.7407, 0.7050, 0.7515),
    (19, "Cornell",        "Ivy",      "IVY",2, "14-6",  "7-0",   "win",  "7-0",  0.7384, 0.7184, 0.7484),
    (20, "UC Santa Barbara","Big West","MID",1, "16-7",  "6-6",   "even", "6-0",  0.7365, 0.7391, 0.7181),
    (21, "Pepperdine",     "WCC",      "MID",2, "15-9",  "8-4",   "win",  "5-2",  0.7327, 0.7507, 0.7252),
    (22, "Harvard",        "Ivy",      "IVY",3, "13-8",  "6-5",   "win",  "6-1",  0.7290, 0.6952, 0.7276),
    (23, "South Florida",  "AAC",      "MID",1, "14-9",  "3-4",   "loss", "5-3",  0.7233, 0.7129, 0.6871),
    (24, "Princeton",      "Ivy",      "IVY",4, "12-9",  "6-1-1", "win",  "5-2",  0.7156, 0.6804, 0.7570),
]

CONFERENCES = ["All", "ACC", "SEC", "Big Ten", "Big 12", "Ivy", "WCC", "Sun Belt", "Big West", "AAC"]
TIERS = ["All", "P5", "MID", "IVY"]


def get_rankings(conf: str = "All", tier: str = "All", sort: str = "Rank") -> list[RankRow]:
    rows = [
        RankRow(rk, school, c, t, cr, rec, h2h, tone, crec, pi, apr, fqi, *(rest or (False,)))
        for (rk, school, c, t, cr, rec, h2h, tone, crec, pi, apr, fqi, *rest) in _SEED
    ]
    if conf != "All":
        rows = [r for r in rows if r.conf == conf]
    if tier != "All":
        rows = [r for r in rows if r.tier == tier]
    if sort == "Power Index":
        rows.sort(key=lambda r: r.pi, reverse=True)
    elif sort == "APR":
        rows.sort(key=lambda r: r.apr, reverse=True)
    return rows
