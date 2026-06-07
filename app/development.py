"""
Player talent + development model - the heart of the sim.

Tennis prospects now persist a rich 20-80 attribute set, while the match engine
continues to receive the compact nine-driver ``engine.Player`` it was built for.
That keeps the point engine stable and gives career/recruiting mode a realistic
profile: serve and return detail, groundstrokes, tactics, doubles tools,
physical/mental traits, hardcourt conditions, and team/program fit.

Current ability is visible because match results and STR expose it. The hidden
part is trajectory: true per-attribute ceilings plus a deterministic interest
rate that closes the gap every year.
"""
from __future__ import annotations

import copy
import hashlib
import random
from dataclasses import dataclass, field

from engine import Player, ATTRS
from app.player_attributes import (
    GRADE_MIN, GRADE_MAX, RICH_ATTRS, TRAIT_DEFAULTS, PlayerAttributes,
    clamp_grade, normalize_grades,
)

GROWTH_K = 0.12
FOG_MIN, FOG_MAX = 7, 31
MATURITY_MIN, MATURITY_MAX = 0.45, 0.95
STR_MIN, STR_MAX = 31.0, 57.0
ACADEMIC_MIN, ACADEMIC_MAX = 59, 99

# Interest-rate tiers: (label, probability, rate range, growth multiplier).
TIERS = {
    1: ("ordinary", 0.75, (0.05, 0.50), 1.0),
    2: ("late bloomer", 0.20, (0.50, 1.20), 1.3),
    3: ("super-bloomer", 0.05, (1.20, 2.20), 1.6),
}


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def overall_to_str(g: float) -> float:
    """Map a 20-80 current grade onto Baseline's STR display band.

    STR is intentionally game-native (31-57), not real UTR's public scale. Later
    results-based STR can replace the source of the grade without changing the
    visible band or callers that consume ``str_value()``.
    """
    return round(STR_MIN + (g - GRADE_MIN) / (GRADE_MAX - GRADE_MIN) * (STR_MAX - STR_MIN), 2)


def make_pid(*parts: object) -> str:
    """Stable short id for generated prospects. Never use Python ``hash()`` for
    this; it is salted per process and would break cross-run determinism.
    """
    raw = "|".join(str(p) for p in parts)
    return hashlib.blake2s(raw.encode("utf-8"), digest_size=8).hexdigest()


def _draw_interest(rng: random.Random) -> tuple[int, float, float]:
    roll, cum = rng.random(), 0.0
    for tier, (_, prob, (lo, hi), mult) in TIERS.items():
        cum += prob
        if roll < cum:
            return tier, rng.uniform(lo, hi), mult
    return 1, rng.uniform(0.05, 0.50), 1.0


def _draw_traits(rng: random.Random) -> dict[str, str]:
    handedness = "left" if rng.random() < 0.12 else "right"
    return {
        "handedness": handedness,
        "backhand_style": rng.choice(("two_handed", "one_handed")),
        "play_style": rng.choice(("balanced", "aggressive_baseliner", "counterpuncher", "all_court", "serve_first")),
        "temperament": rng.choice(("steady", "fiery", "analytical", "fearless", "volatile")),
    }


def _draw_academic_rating(rng: random.Random, country: str) -> int:
    """Admissions-only academic index on a SAT-like 59-99 band.

    This is not a tennis skill and never feeds the match engine. It exists so
    Ivy/top-D3/high-academic programs can gate admissions or weight fit when the
    recruiting layer evaluates offers.
    """
    base = 79 if country in {"US", "USA", "United States"} else 77
    return int(_clamp(round(rng.gauss(base, 9)), ACADEMIC_MIN, ACADEMIC_MAX))


@dataclass
class Prospect:
    name: str
    country: str = ""
    gender: str = "male"
    year: int = 0
    current: dict = field(default_factory=dict)      # visible rich grades (20-80)
    potential: dict = field(default_factory=dict)    # hidden rich ceilings (20-80)
    traits: dict = field(default_factory=lambda: dict(TRAIT_DEFAULTS))
    academic_rating: int = 79                         # admissions-only, 59-99
    interest_rate: float = 0.2
    tier: int = 1
    tier_mult: float = 1.0
    fog: float = 15.0
    consensus_seed: int = 0
    committed: bool = False
    pro: bool = False

    # Compatibility fields used by newer recruiting/league/web layers. They are
    # intentionally light here; richer systems can fill them without changing the
    # core development contract.
    hometown: str = ""
    region: str = "global"
    domestic: bool = False
    grad_year: int = 0
    recruit_rank: int = 0
    recruit_tier: str = ""
    recruit_stars: int = 0
    pid: str = ""
    class_year: int = 0

    def __post_init__(self) -> None:
        self.current = normalize_grades(self.current)
        self.potential = normalize_grades(self.potential)
        self.academic_rating = int(_clamp(round(self.academic_rating), ACADEMIC_MIN, ACADEMIC_MAX))
        merged_traits = dict(TRAIT_DEFAULTS)
        merged_traits.update(self.traits or {})
        self.traits = merged_traits
        if not self.pid:
            self.pid = make_pid(self.name, self.country, self.gender, self.consensus_seed)
        if not self.class_year and self.grad_year:
            self.class_year = self.grad_year
        if not self.grad_year and self.class_year:
            self.grad_year = self.class_year
        if not self.recruit_stars:
            self.recruit_stars = self.star_rating()

    def _attrs(self, source: dict | None = None) -> PlayerAttributes:
        return PlayerAttributes(source or self.current, **self.traits)

    # ---- current ability (visible) ----
    def current_grade(self, attr: str) -> int:
        return int(_clamp(round(self._attrs().grade(attr)), GRADE_MIN, GRADE_MAX))

    def current_overall(self) -> int:
        return round(self._attrs().overall_grade())

    def str_value(self) -> float:
        return overall_to_str(self.current_overall())

    # ---- ceiling (hidden / projected) ----
    def ceiling_overall(self) -> int:
        return round(self._attrs(self.potential).overall_grade())

    # ---- what the engine plays: always current ability ----
    def engine_player(self) -> Player:
        drivers = self._attrs().derive_drivers()
        g = self.current
        drivers.update({
            "indoor_comfort": (g["indoor_comfort"] - GRADE_MIN) / (GRADE_MAX - GRADE_MIN),
            "outdoor_comfort": (g["outdoor_comfort"] - GRADE_MIN) / (GRADE_MAX - GRADE_MIN),
            "wind_tolerance": (g["wind_tolerance"] - GRADE_MIN) / (GRADE_MAX - GRADE_MIN),
            "heat_tolerance": (g["heat_tolerance"] - GRADE_MIN) / (GRADE_MAX - GRADE_MIN),
            "crowd_pressure": (g["crowd_pressure"] - GRADE_MIN) / (GRADE_MAX - GRADE_MIN),
        })
        return Player(name=self.name, country=self.country, **drivers)

    # ---- development: deterministically close the gap to the ceiling ----
    def develop_year(self) -> None:
        frac = self.interest_rate * GROWTH_K * self.tier_mult
        for a in RICH_ATTRS:
            gap = self.potential[a] - self.current[a]
            if gap > 0:
                self.current[a] += max(0.0, min(gap, frac * gap))
                self.current[a] = clamp_grade(self.current[a])
        self.year += 1
        self.recruit_stars = self.star_rating()

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
        g = self.current_overall()
        return 5 if g >= 62 else 4 if g >= 54 else 3 if g >= 46 else 2 if g >= 38 else 1

    def public_view(self) -> dict:
        return {"name": self.name, "country": self.country,
                "str": self.str_value(), "stars": self.star_rating(),
                "academic": self.academic_rating, "year": self.year}


def generate_prospect(rng: random.Random, name: str, country: str = "",
                      gender: str = "male", talent: float | None = None) -> Prospect:
    """Create an incoming prospect with reproducible rich attributes.

    Ceilings cluster around ``talent``; maturity determines how much is visible
    today; the interest tier determines how fast the remaining gap closes.
    """
    if talent is None:
        talent = _clamp(rng.gauss(46, 9), 24, 78)
    potential = {a: _clamp(rng.gauss(talent, 6), GRADE_MIN, GRADE_MAX) for a in RICH_ATTRS}
    maturity = rng.uniform(MATURITY_MIN, MATURITY_MAX)
    current = {a: _clamp(potential[a] * maturity, GRADE_MIN, GRADE_MAX) for a in RICH_ATTRS}
    tier, rate, mult = _draw_interest(rng)
    consensus_seed = rng.randrange(1 << 30)
    traits = _draw_traits(rng)
    domestic = country in {"US", "USA", "United States"}
    grad_year = 0
    p = Prospect(
        name=name, country=country, gender=gender,
        current=current, potential=potential, traits=traits,
        academic_rating=_draw_academic_rating(rng, country),
        interest_rate=rate, tier=tier, tier_mult=mult,
        fog=rng.uniform(FOG_MIN, FOG_MAX),
        consensus_seed=consensus_seed,
        domestic=domestic, grad_year=grad_year, class_year=grad_year,
        pid=make_pid(name, country, gender, consensus_seed),
    )
    p.recruit_stars = p.star_rating()
    p.recruit_tier = TIERS[p.tier][0]
    return p
