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
DECLINE_K = 0.05            # per-year erosion (the reverse of GROWTH_K), scaled by age past peak
FOG_MIN, FOG_MAX = 7, 31
MATURITY_MIN, MATURITY_MAX = 0.45, 0.95
STR_MIN, STR_MAX = 31.0, 57.0
ACADEMIC_MIN, ACADEMIC_MAX = 59, 99

# Staggered development: a league doesn't develop all at once. Each player develops
# inside a window of `STAGGER_BLOCK_FRAC` of the season's ticks, phase-shifted by a
# stable per-player key (senate-style staggered terms). By the final tick everyone
# has banked the same year of growth — only the *timing* differs, so at any midseason
# snapshot some players have already jumped, some are mid-climb, and some haven't
# moved yet. See docs/DEV-MODEL-tennis-adaptation.md.
STAGGER_BLOCK_FRAC = 0.45

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


def _stable_phase(key: str, slots: int) -> int:
    """Deterministic phase in [0, slots) from a stable key — never Python ``hash()``
    (salted per process). Drives which window of the season a player develops in."""
    if slots <= 1:
        return 0
    h = int(hashlib.blake2s(str(key).encode("utf-8"), digest_size=4).hexdigest(), 16)
    return h % slots


def stagger_scale(key: str, tick: int, ticks: int, *, total: float = 1.0,
                  block_frac: float = STAGGER_BLOCK_FRAC) -> float:
    """How much of a year's development a player keyed by `key` banks at 0-indexed
    `tick` of a `ticks`-long season, under staggered (not all-at-once) development.

    Each player's growth is concentrated in a contiguous window of ``block``
    consecutive ticks whose START is phase-shifted by `key`. The per-tick slices in
    a player's window sum to `total`, and every window finishes by the final tick,
    so the season-end total is identical for everyone — only WHEN they climb differs
    (senate-style staggered terms). Deterministic; no RNG.
    """
    if ticks <= 0:
        return 0.0
    block = max(1, min(ticks, round(ticks * block_frac)))
    phase = _stable_phase(key, ticks - block + 1)
    return (total / block) if phase <= tick < phase + block else 0.0



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
    commit_school: str | None = None
    pro: bool = False

    # Compatibility fields used by newer recruiting/league/web layers. They are
    # intentionally light here; richer systems can fill them without changing the
    # core development contract.
    hometown: str = ""
    high_school: str = ""
    region: str = "global"
    domestic: bool = False
    grad_year: int = 0
    recruit_rank: int = 0
    recruit_tier: str = ""
    recruit_stars: int = 0
    pid: str = ""
    class_year: str = ""                              # eligibility: "Fr"/"So"/"Jr"/"Sr"
    walk_on: bool = False                             # non-scholarship roster filler
    scholarship: float = 0.0                           # equivalency fraction (app.economy)
    major: str = ""                                   # academic major (bio flavor)
    birthday: str = ""                                # cosmetic "Mar 14" (no year)
    secondary_country: str = ""                       # dual-nationality flavor tag
    elite_origin: bool = False                        # rolled a nation elite spike
    homecooking: float = 0.0                           # 0..1 desire to stay near home
                                                       # (recruit-side only; intl = 0)
    # Career log: one entry per season played — {year, school, class, str, rel,
    # w, l}. School changing between entries = a transfer (see app.league).
    history: list = field(default_factory=list)

    # Junior circuit (app.junior_circuit): the pre-college résumé frozen onto the
    # recruit before recruiting opens. The full match engine plays out a junior
    # season in a closed ecosystem (every opponent is another recruit), so STR is
    # results-based and dynamic — it grows and regresses with actual form, exactly
    # like the college STR (seeded by ability, solved from results).
    junior_tier: int = 0
    junior_str: float = 0.0                              # results-based STR (evolved)
    junior_str_reliability: float = 0.0                  # 0..1, grows with match count
    junior_results: list = field(default_factory=list)   # [{date, tournament, level, result}]
    junior_matches: list = field(default_factory=list)   # [{date, tournament, round, opponent, score, won}]
    ranking_history: list = field(default_factory=list)  # [{date, primary*, secondary*, str}]
    junior_badges: list = field(default_factory=list)    # permanent profile labels
    # Junior-circuit performance counters the board/almanac read. Fields (not bare
    # dynamic attrs) with zero defaults so EVERY recruit has them — the circuit only
    # runs over the recruited cadre (world.CIRCUIT_FIELD), and the walk-on tail must
    # still read as a clean 0-record, not an AttributeError. See AAR-fog-of-war-recruiting.
    junior_points: int = 0
    singles_points: int = 0
    doubles_points: int = 0
    tournaments_played: int = 0
    doubles_played: int = 0
    points_rank: int = 0
    junior_doubles_str: float | None = None
    junior_doubles_results: list = field(default_factory=list)
    junior_doubles_matches: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.current = normalize_grades(self.current)
        self.potential = normalize_grades(self.potential)
        self.academic_rating = int(_clamp(round(self.academic_rating), ACADEMIC_MIN, ACADEMIC_MAX))
        merged_traits = dict(TRAIT_DEFAULTS)
        merged_traits.update(self.traits or {})
        self.traits = merged_traits
        if not self.pid:
            self.pid = make_pid(self.name, self.country, self.gender, self.consensus_seed)
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
    def develop(self, scale: float = 1.0) -> None:
        """Close part of the gap to the ceiling. `scale` < 1 applies a fraction
        of a year's growth — the season-long weekly drip (the world advances a
        slice each week and trues up to a full year at season's end)."""
        frac = self.interest_rate * GROWTH_K * self.tier_mult * scale
        for a in RICH_ATTRS:
            gap = self.potential[a] - self.current[a]
            if gap > 0:
                self.current[a] += max(0.0, min(gap, frac * gap))
                self.current[a] = clamp_grade(self.current[a])
        self.recruit_stars = self.star_rating()

    def develop_year(self) -> None:
        self.develop(1.0)
        self.year += 1

    # ---- decline: the inverse of develop, for aging pros ----
    def decline(self, scale: float = 1.0) -> None:
        """Erode CURRENT ability — develop() run in reverse. Where develop closes
        the gap UP toward the ceiling, decline opens a gap DOWN from where the
        player is now, each year shaving a fraction of their remaining ability
        toward the floor. Activated only once a player turns pro and ages past
        their peak (the college game never calls this); `scale` grows with age so
        the slide accelerates into a veteran's thirties."""
        frac = min(0.9, DECLINE_K * scale)
        if frac <= 0:
            return
        for a in RICH_ATTRS:
            cur = self.current[a]
            self.current[a] = clamp_grade(cur - frac * (cur - GRADE_MIN))

    def regress_to_younger(self, years: float = 1.0) -> None:
        """Roll CURRENT *back* toward where this player was ~`years` ago, given their
        fixed development rate — the exact inverse of ``develop``. Nobody actually
        regresses in the model; this only REPLAYS the climb, letting the junior
        circuit start a recruit at their younger self and develop them back up to
        their current (recruiting-time) ability across the junior season. A
        super-bloomer was far weaker at 14; an early bloomer was always near here."""
        frac = min(0.9, self.interest_rate * GROWTH_K * self.tier_mult * years)
        if frac <= 0:
            return
        for a in RICH_ATTRS:
            pot, cur = self.potential[a], self.current[a]
            prev = (cur - frac * pot) / (1.0 - frac)      # invert cur += frac*(pot-cur)
            self.current[a] = clamp_grade(min(cur, prev))
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
                      gender: str = "male", talent: float | None = None,
                      pid: str = "", maturity_range: tuple | None = None,
                      town_pool: list | None = None) -> Prospect:
    """Create an incoming prospect with reproducible rich attributes.

    Ceilings cluster around ``talent``; maturity determines how much is visible
    today; the interest tier determines how fast the remaining gap closes.
    `pid` lets callers (roster/juniors builders) assign a stable id; if omitted
    a deterministic one is derived.
    """
    from generators import (nation_talent, roll_hometown, roll_birthday,
                            roll_secondary_country, roll_high_school,
                            country_abbrev, random_town)
    from generators.majors import pick_major

    if talent is None:
        talent = _clamp(rng.gauss(46, 9), 24, 78)
    # Expansive world model: a nation's grassroots breadth lifts (or, for the
    # weakest, nudges) the average ceiling of every player it produces. Nations
    # absent from the table are neutral (shift 0), so non-major markets are
    # never penalised — they generate at tour-average with full variance.
    talent = _clamp(talent + nation_talent.talent_shift(country), 24.0, float(GRADE_MAX))
    potential = {a: _clamp(rng.gauss(talent, 6), GRADE_MIN, GRADE_MAX) for a in RICH_ATTRS}

    # Elite spike: a small, investment-scaled chance the nation produced a
    # blue-chip. Floors the ceiling bands so the player reads world-class at
    # seed time (Elite+ growth is still earned through development).
    elite = nation_talent.roll_elite(country, rng)
    if elite:
        marquee = rng.sample(RICH_ATTRS, k=max(1, len(RICH_ATTRS) // 4))
        for a in RICH_ATTRS:
            band = nation_talent.ELITE_HEADLINE if a in marquee else nation_talent.ELITE_SUPPORT
            potential[a] = _clamp(max(potential[a], rng.uniform(*band)), GRADE_MIN, GRADE_MAX)

    lo, hi = maturity_range or (MATURITY_MIN, MATURITY_MAX)
    maturity = rng.uniform(lo, hi)
    current = {a: _clamp(potential[a] * maturity, GRADE_MIN, GRADE_MAX) for a in RICH_ATTRS}
    tier, rate, mult = _draw_interest(rng)
    consensus_seed = rng.randrange(1 << 30)
    traits = _draw_traits(rng)
    domestic = country in {"US", "USA", "United States"}
    p = Prospect(
        name=name, country=country, gender=gender,
        current=current, potential=potential, traits=traits,
        academic_rating=_draw_academic_rating(rng, country),
        interest_rate=rate, tier=tier, tier_mult=mult,
        fog=rng.uniform(FOG_MIN, FOG_MAX),
        consensus_seed=consensus_seed, domestic=domestic,
        pid=pid or make_pid(name, country, gender, consensus_seed),
        major=pick_major(rng),
        birthday=roll_birthday(rng),
        secondary_country=roll_secondary_country(country, rng),
        elite_origin=elite,
    )
    # Believable birthplace: Americans read "City, ST" from the real US
    # college-town (city, state) pool; everyone else "City, NATION" from the
    # nation's city pool. (juniors overrides domestic recruits with the
    # state-board dimension.)
    if domestic:
        # `town_pool` (when provided) biases the birthplace toward the program's own
        # region — a real (city, state) drawn from its backyard rather than nationwide.
        city, st = rng.choice(town_pool) if town_pool else random_town(rng)
        p.hometown = f"{city}, {st}"
        p.high_school = roll_high_school(country, rng, state=st, home_city=city)
    else:
        # Never leave an international player without a birthplace: fall back to a
        # generic town when the nation has no city pool on file.
        city = roll_hometown(country, rng) or random_town(rng)[0]
        p.hometown = f"{city}, {country_abbrev(country)}" if country else city
        p.high_school = ""          # international players: no US high school listed
    # Homecooking: a recruit-side desire to stay near home (some kids strongly,
    # most a little, some not at all). International recruits have none — there
    # are no schools near home — so their geographic pull is always zero.
    p.homecooking = round(rng.random() ** 1.4, 3) if domestic else 0.0
    p.recruit_stars = p.star_rating()
    p.recruit_tier = TIERS[p.tier][0]
    return p
