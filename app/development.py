"""
Player talent + development model — the heart of the sim.

Adapted from the O27 baseball prospect model (Ron Bronson's hidden-potential /
deterministic-development / scouting-fog philosophy), but **corrected for
tennis**: you can't hide current ability the way baseball hides scouting
grades, because every player carries a UTR-style rating and results don't lie.

So in tennis what's visible vs hidden is different:

  • CURRENT ability is VISIBLE. Each attribute has a `current` value (20–80);
    the engine plays it and it's what a player's results / UTR reflect. You can
    always see roughly how good a junior is *right now*.
  • The TRAJECTORY is HIDDEN. Each attribute also has a true `potential`
    ceiling, and the player has a static `interest_rate` (tiered: ordinary /
    late bloomer / super-bloomer) that deterministically closes the gap between
    current and ceiling each year. No rerolls, no regression — the slope is set
    at birth; you just don't know it.
  • Per-attribute breakdowns are hidden until a recruit SIGNS; the ceiling stays
    a projection (two noisy scouting reports, ±fog) until the pro REVEAL.

The recruiting gamble is therefore about growth, not measurement. A high-UTR
early bloomer who's already near his ceiling is the bust; the modest-UTR late
bloomer with a high hidden ceiling and steep slope is the gem. `star_rating`
tracks the visible current ability (so gems are under-rated, busts over-rated).

`Prospect.engine_player()` produces the `engine.Player` the match engine runs.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from engine import Player, ATTRS

GRADE_MIN, GRADE_MAX = 20, 80
GROWTH_K = 0.12                   # interest_rate × tier → fraction of the gap closed per year
FOG_MIN, FOG_MAX = 7, 31
MATURITY_MIN, MATURITY_MAX = 0.45, 0.95   # share of ceiling already realized at generation

# Interest-rate tiers: (label, probability, rate range, growth multiplier).
TIERS = {
    1: ("ordinary",      0.75, (0.05, 0.50), 1.0),
    2: ("late bloomer",  0.20, (0.50, 1.20), 1.3),
    3: ("super-bloomer", 0.05, (1.20, 2.20), 1.6),
}

# Overall-rating weights across the shot attributes (sum = 1).
_W = {
    "serve_power": 0.15, "serve_placement": 0.12, "return_game": 0.15,
    "forehand": 0.15, "backhand": 0.13, "movement": 0.12,
    "stamina": 0.06, "mental": 0.06, "consistency": 0.06,
}


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def grade_to_unit(g: float) -> float:
    """20–80 scouting grade → 0–1 the engine tables expect."""
    return _clamp((g - GRADE_MIN) / (GRADE_MAX - GRADE_MIN), 0.0, 1.0)


def overall_to_str(g: float) -> float:
    """Map an overall grade (20–80) to a STR — this game's synthetic, UTR-style
    rating (≈1.0–16.5). STR is opponent-relative and visible; it's the single
    yardstick across juniors → college → pro."""
    return round(1.0 + (g - GRADE_MIN) / (GRADE_MAX - GRADE_MIN) * 15.5, 2)


def _draw_interest(rng: random.Random) -> tuple[int, float, float]:
    roll, cum = rng.random(), 0.0
    for tier, (_, prob, (lo, hi), mult) in TIERS.items():
        cum += prob
        if roll < cum:
            return tier, rng.uniform(lo, hi), mult
    return 1, rng.uniform(0.05, 0.50), 1.0


@dataclass
class Prospect:
    name: str
    country: str = ""
    gender: str = "male"
    year: int = 0
    current: dict = field(default_factory=dict)      # VISIBLE current ability (what plays / UTR reflects)
    potential: dict = field(default_factory=dict)    # hidden true ceilings (20–80)
    interest_rate: float = 0.2                        # hidden static development rate
    tier: int = 1
    tier_mult: float = 1.0
    fog: float = 15.0
    consensus_seed: int = 0
    committed: bool = False                           # signed → per-attribute current grades visible to you
    pro: bool = False                                # the reveal → the true ceiling is known
    # Origin / recruiting context (set by app.juniors; US = city+state, intl = city+nation)
    hometown: str = ""
    region: str = ""                                 # US state name, or nation
    domestic: bool = True                            # US recruit?
    grad_year: int = 0                               # graduating class

    # ---- current ability (visible) ----
    def current_grade(self, attr: str) -> int:
        return int(_clamp(round(self.current[attr]), GRADE_MIN, GRADE_MAX))

    def current_overall(self) -> int:
        return round(sum(_W[a] * self.current[a] for a in ATTRS))

    def str_value(self) -> float:
        """The player's STR (synthetic UTR-style rating) — derived from current
        ability, public. Results don't lie, so STR is visible; the trajectory
        behind it is not."""
        return overall_to_str(self.current_overall())

    # ---- ceiling (hidden / projected) ----
    def ceiling_overall(self) -> int:
        return round(sum(_W[a] * self.potential[a] for a in ATTRS))

    # ---- what the engine plays: always current ability ----
    def engine_player(self) -> Player:
        return Player(name=self.name, country=self.country,
                      **{a: grade_to_unit(self.current[a]) for a in ATTRS})

    # ---- development: deterministically close the gap to the ceiling ----
    def develop_year(self) -> None:
        frac = self.interest_rate * GROWTH_K * self.tier_mult
        for a in ATTRS:
            gap = self.potential[a] - self.current[a]
            if gap > 0:
                self.current[a] += max(0.0, min(gap, frac * gap))
        self.year += 1

    def project(self, years: int) -> int:
        clone = copy.deepcopy(self)
        for _ in range(years):
            clone.develop_year()
        return clone.current_overall()

    # ---- scouting: two independent noisy reads of the hidden CEILING ----
    def scouting_report(self, source: str) -> int:
        rng = random.Random(f"{self.consensus_seed}:{source}")
        blurred = self.ceiling_overall() + rng.uniform(-self.fog, self.fog)
        return int(_clamp(round(blurred), GRADE_MIN, GRADE_MAX))

    # ---- public prospect signal: a star rating off the VISIBLE current level ----
    def star_rating(self) -> int:
        g = self.current_overall()       # tennis: stars track current results/UTR, not the hidden ceiling
        return 5 if g >= 62 else 4 if g >= 54 else 3 if g >= 46 else 2 if g >= 38 else 1

    def public_view(self) -> dict:
        return {"name": self.name, "country": self.country,
                "str": self.str_value(), "stars": self.star_rating(), "year": self.year}


def generate_prospect(rng: random.Random, name: str, country: str = "",
                      gender: str = "male", talent: float | None = None) -> Prospect:
    """Create an incoming prospect. Ceilings cluster around `talent`; a hidden
    `maturity` sets how much of the ceiling is realized now (early vs late
    bloomer), and a hidden interest tier sets how fast the gap closes."""
    if talent is None:
        talent = _clamp(rng.gauss(46, 9), 24, 78)
    potential = {a: _clamp(rng.gauss(talent, 6), GRADE_MIN, GRADE_MAX) for a in ATTRS}
    maturity = rng.uniform(MATURITY_MIN, MATURITY_MAX)
    current = {a: _clamp(potential[a] * maturity, GRADE_MIN, GRADE_MAX) for a in ATTRS}
    tier, rate, mult = _draw_interest(rng)
    return Prospect(
        name=name, country=country, gender=gender,
        current=current, potential=potential,
        interest_rate=rate, tier=tier, tier_mult=mult,
        fog=rng.uniform(FOG_MIN, FOG_MAX),
        consensus_seed=rng.randrange(1 << 30),
    )
