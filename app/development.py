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
import math
import random
from dataclasses import dataclass, field

from engine import Player, ATTRS
from app.player_attributes import (
    GRADE_MIN, GRADE_MAX, GRADE_CEIL, RICH_ATTRS, TRAIT_DEFAULTS, PlayerAttributes,
    clamp_grade, normalize_grades, grade_to_unit, OVERALL_WEIGHTS, _WEIGHT_TOTAL,
)

GROWTH_K = 0.12
DECLINE_K = 0.05            # per-year erosion (the reverse of GROWTH_K), scaled by age past peak

# --- Playing-style profiles -------------------------------------------------
# Without a profile, generate_prospect draws all 49 attributes as INDEPENDENT
# noise around one talent mean, so every player is a clone of their own average —
# net play ≈ baseline ≈ overall, and doubles ability never diverges from singles.
# These correlated cluster shifts give players a real SHAPE (net specialist,
# baseliner, big server). Shifts are WEIGHT-NORMALIZED (see `_apply_style_profile`)
# so a player's overall grade — hence STR and the whole talent distribution — is
# preserved; only the shape moves. That's what lets a genuine "1-doubles /
# 5-singles" specialist exist: same overall, but net-weighted doubles_rating well
# above their all-around singles level.
_STYLE_CLUSTERS = {
    "serve":    ("first_serve_power", "first_serve_accuracy", "second_serve_quality", "serve_variety"),
    "return":   ("return_quality", "return_aggression", "return_depth"),
    "baseline": ("forehand_power", "forehand_control", "backhand_power", "backhand_control",
                 "groundstroke_consistency", "shot_tolerance", "rally_patience", "pattern_execution"),
    "net":      ("net_play", "volley_touch", "overhead", "poaching", "doubles_chemistry",
                 "approach_shot", "transition_game"),
    "movement": ("footwork", "speed", "agility", "balance"),
}
# Pre-normalization cluster shifts in grade points (20-80 scale).
_STYLE_BIAS = {
    "balanced":             {},
    "aggressive_baseliner": {"baseline": 5, "serve": 2, "net": -4, "movement": -1},
    "counterpuncher":       {"return": 4, "movement": 3, "baseline": 1, "serve": -3, "net": -3},
    "all_court":            {"net": 5, "movement": 2, "return": 1, "baseline": -2},
    "serve_first":          {"serve": 6, "net": 2, "return": -3, "movement": -2},
}
# A minority are pronounced net/doubles specialists regardless of style label —
# big at the net, ordinary off the ground. This is the main source of doubles-vs-
# singles divergence (real "doubles specialists").
NET_SPECIALIST_RATE = 0.18
_NET_SPECIALIST_BIAS = {"net": 11, "movement": 3, "baseline": -7, "serve": -2}


def _apply_style_profile(potential: dict, style: str, rng: random.Random) -> None:
    """Shift correlated attribute clusters by play-style + a net-specialist roll,
    in place on `potential` (ceilings, so the profile persists through growth).
    Weight-normalized: a uniform offset is removed so the OVERALL grade is
    unchanged — specialists TRADE strengths, they don't gain overall level, which
    keeps the STR/talent distribution intact."""
    shifts = dict(_STYLE_BIAS.get(style, {}))
    if rng.random() < NET_SPECIALIST_RATE:
        for cl, d in _NET_SPECIALIST_BIAS.items():
            shifts[cl] = shifts.get(cl, 0) + d
    if not shifts:
        return
    # per-player jitter so same-style players aren't identical
    shifts = {cl: v + rng.gauss(0, 1.2) for cl, v in shifts.items()}
    delta = {a: 0.0 for a in RICH_ATTRS}
    for cl, v in shifts.items():
        for a in _STYLE_CLUSTERS[cl]:
            delta[a] += v
    # weight-normalize: subtract the weighted-mean shift from every attribute so
    # the overall grade (Σ weight·grade) is preserved.
    k = sum(OVERALL_WEIGHTS[a] * delta[a] for a in RICH_ATTRS) / _WEIGHT_TOTAL
    for a in RICH_ATTRS:
        potential[a] = clamp_grade(potential[a] + delta[a] - k)
FOG_MIN, FOG_MAX = 7, 31
MATURITY_MIN, MATURITY_MAX = 0.45, 0.95
STR_MIN, STR_MAX = 31.0, 57.0
ACADEMIC_MIN, ACADEMIC_MAX = 59, 99

# The PUBLIC board/AI-facing signal (docs/DESIGN-recruit-rating-clarity.md,
# 2026-08-12): a light, honest-ish fog over TODAY (current ability + results),
# not over the invisible ceiling. Replaces scouting_report() as what the
# recruiting board displays and what recruiting.talent_caliber feeds the AI's
# perceived_caliber, so a recruit whose current level and results both read as
# ordinary can never randomly land a top grade the way a ceiling-fogged read
# could. scouting_report() itself is untouched — this is a second, separate read.
TODAY_RESULTS_W = 0.4                      # how far results can move the read
                                            # beyond current ability alone — up
                                            # from 0% pre-redesign, per owner:
                                            # "performance should dictate more"
TODAY_FOG_MIN, TODAY_FOG_MAX = 4.0, 10.0   # far lighter than FOG_MIN/FOG_MAX —
                                            # an honest read of TODAY should
                                            # rarely be wildly off

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


# --- Talent compression (owner rule 2026-08) ----------------------------------
# The universe was tuned when it held 100-200 schools; at ~850 JHSAA programs
# plus a 2,500/gender national pool, the SAME distributions produce five times
# the lottery tickets and the tail piles onto the 80 clamp — players "maxing
# out my college scales, which was never supposed to happen". So generated
# CEILINGS are squashed above a knee: ordinary talent tops out around UTR 12-13
# (boys) / 10-11 (girls) as a ceiling, and a 1-in-500 ELITE roll is exempt —
# those few still reach where today's elite sit. The squash is a transform on
# the ALREADY-DRAWN value (tanh above the knee, identity below, monotonic so
# every ordering survives) and the elite roll runs on blake2s off the player's
# stable identity — NO extra rng draws, so a gated source's pre-era cohorts
# stay byte-identical and new cohorts don't shift sibling draws.
#
# Anchors (grade 20-80 ⇄ STR 31-57 ⇄ UTR 1-16.5, ~3.87 grade pts per UTR):
#   boys  knee 54.8 (UTR 10.0) → cap 66.5 (UTR 13.0)
#   girls knee 49.0 (UTR  8.5) → cap 58.7 (UTR 11.0)
# Sources: JHSAA generation (era-gated by entry year — `jhsaa.talent_era()`),
# the national recruit pool, and college base-roster builds, so no feed runs
# hotter than the others. See docs/AAR-talent-compression.md.
TALENT_KNEE = {"male": 54.8, "female": 49.0}
TALENT_CAP = {"male": 66.5, "female": 58.7}
ELITE_TALENT_RATE = 1 / 500
#: `ceiling_overall()` sits ABOVE the talent passed to `generate_prospect` —
#: attribute potentials and playstyle shaping lift the displayed ceiling a
#: measured median +6 / p90 +7 over the input. The squash therefore aims this
#: far BELOW the displayed targets above, so what the owner sees (the census
#: ceiling, the recruit board) lands on the UTR anchors rather than a lift
#: above them. Measured by scripts/talent_compression_calibration.py.
_ATTR_LIFT = 7.0


def _talent_sex(gender) -> str:
    return ("female" if str(gender).lower().startswith(("f", "w", "g"))
            else "male")


def elite_talent(key) -> bool:
    """The 1-in-500 exemption, off a stable identity — never the main rng
    (an extra draw would regenerate everyone) and never `hash()` (salted per
    process). The same key answers the same way forever, so an elite kid is
    elite all four years."""
    raw = "|".join(str(p) for p in (key if isinstance(key, tuple) else (key,)))
    h = int(hashlib.blake2s(raw.encode("utf-8"), digest_size=6).hexdigest(), 16)
    return (h % 500) == 0


def compress_talent(raw: float, gender, key=None) -> float:
    """Squash a drawn talent CEILING above the gender's knee; identity below it,
    monotonic throughout, asymptoting at the cap. A key that rolls elite keeps
    the raw draw (clamped 80) — the old sky, for one player in five hundred."""
    sex = _talent_sex(gender)
    knee = TALENT_KNEE[sex] - _ATTR_LIFT
    cap = TALENT_CAP[sex] - _ATTR_LIFT
    if raw <= knee:
        return raw
    if key is not None and elite_talent(key):
        return min(80.0, raw)
    span = cap - knee
    return round(knee + span * math.tanh((raw - knee) / span), 2)


def trim_prospect_ceiling(p, gender, key=None):
    """The guarantee half of the compression (the squash above is the SHAPE
    half): attribute noise and playstyle shaping lift the displayed ceiling a
    median +6 over the input talent with a tail to +16, so a squashed centre
    alone still leaks hundreds of over-cap ceilings per gender. After
    generation, a non-elite prospect whose `ceiling_overall()` exceeds the cap
    has the overshoot subtracted uniformly from every attribute potential
    (never below the attribute's current value). The landing point is spread
    deterministically over [cap-2, cap] off the identity key, so the trimmed
    tail does not pile onto one visible number — the wall of maxed players is
    the thing this whole rule exists to remove. Elite keys are exempt."""
    if key is not None and elite_talent(key):
        return p
    cap = TALENT_CAP[_talent_sex(gender)]
    if key is not None:
        raw = "|".join(str(x) for x in (key if isinstance(key, tuple) else (key,)))
        h = int(hashlib.blake2s(raw.encode("utf-8"), digest_size=4).hexdigest(), 16)
        cap -= (h % 101) / 50.0                     # 0.00-2.00 below the cap
    # ‼️ The weighted mean DIRECTLY, never `p.ceiling_overall()` — that
    # constructs a full PlayerAttributes per call, and this runs once per
    # generated player: measured, it took a JHSAA roster build 0.10s → 0.35s,
    # which compounds into every census, career page and season build (the
    # cost-class rule — CLAUDE.md's fingerprint-in-a-loop lesson, this
    # feature's own instance).
    from app.player_attributes import OVERALL_WEIGHTS, _WEIGHT_TOTAL
    ceil = sum(OVERALL_WEIGHTS[a] * v for a, v in p.potential.items()) / _WEIGHT_TOTAL
    over = ceil - cap
    if over > 0:
        for a, v in p.potential.items():
            p.potential[a] = max(p.current.get(a, GRADE_MIN), v - over)
    return p


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
    # High-school career, for players who came through a simulated association (today
    # only Jefferson's JHSAA). A real dataclass FIELD, not an ad-hoc attribute, because
    # `world.prospect_to_dict` is `asdict()` — anything not declared here vanishes the
    # moment a recruit signs, taking their whole high-school past with them.
    jhsaa: dict = field(default_factory=dict)
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
    # TennisEye = the results-based second star service (juniors.tenniseye_rankings).
    # Declared fields (not dynamic attrs) so they survive prospect_to_dict/asdict and
    # round-trip through the parallel board build (prime_recruit_classes); otherwise
    # the web board reads them off reconstructed prospects and they'd all be 0.
    tenniseye_rank: int = 0
    tenniseye_tier: str = ""
    tenniseye_stars: int = 0
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
        # Ceiling is GRADE_CEIL so a pro's 80-90 attributes display truthfully; normal
        # players are all <= GRADE_MAX anyway, so this is a no-op for them.
        return int(_clamp(round(self._attrs().grade(attr)), GRADE_MIN, GRADE_CEIL))

    def current_overall(self) -> int:
        return round(self._attrs().overall_grade())

    def str_value(self) -> float:
        return overall_to_str(self.current_overall())

    # ---- ceiling (hidden / projected) ----
    def ceiling_overall(self) -> int:
        return round(self._attrs(self.potential).overall_grade())

    # ---- what the engine plays: always current ability ----
    def engine_player(self) -> Player:
        attrs = self._attrs()
        drivers = attrs.derive_drivers()
        g = self.current
        drivers.update({
            "indoor_comfort": (g["indoor_comfort"] - GRADE_MIN) / (GRADE_MAX - GRADE_MIN),
            "outdoor_comfort": (g["outdoor_comfort"] - GRADE_MIN) / (GRADE_MAX - GRADE_MIN),
            "wind_tolerance": (g["wind_tolerance"] - GRADE_MIN) / (GRADE_MAX - GRADE_MIN),
            "heat_tolerance": (g["heat_tolerance"] - GRADE_MIN) / (GRADE_MAX - GRADE_MIN),
            "crowd_pressure": (g["crowd_pressure"] - GRADE_MIN) / (GRADE_MAX - GRADE_MIN),
        })
        # Carry the full rich table (as [0,1] units) so the point engine can read
        # specific attributes, not just the 9 collapsed drivers.
        rich = {a: grade_to_unit(attrs.grades[a]) for a in RICH_ATTRS}
        return Player(name=self.name, country=self.country, rich=rich, **drivers)

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

    # ---- the public board read: current ability + results, TRUTH-anchored ----
    def today_grade(self) -> float:
        """Current ability blended with demonstrated junior-circuit results, both
        real, both on the 20-80 grade scale — the honest 'how good are they right
        now' read, as opposed to ceiling_overall()'s 'how good could they become'.
        Results pull the read by up to TODAY_RESULTS_W, scaled by how much junior
        evidence actually exists (junior_str_reliability) — a thin or absent
        résumé is judged on current ability alone, same reliability-gating idea as
        recruiting.perceived_caliber."""
        cur = self.current_overall()
        rel = float(self.junior_str_reliability or 0.0)
        if not self.junior_str or rel <= 0:
            return float(cur)
        results_grade = GRADE_MIN + (self.junior_str - STR_MIN) / (STR_MAX - STR_MIN) * (GRADE_MAX - GRADE_MIN)
        results_grade = _clamp(results_grade, GRADE_MIN, GRADE_MAX)
        w = TODAY_RESULTS_W * min(1.0, rel)
        return (1 - w) * cur + w * results_grade

    def scouted_read(self, source: str) -> int:
        """The ONE public, fogged signal the recruiting board displays and every
        program's AI actually recruits on (juniors._recruiting_score,
        recruiting.talent_caliber both call this) — today_grade() blurred by a
        light, per-recruit-fixed offset, deterministic per `source` so it's
        stable across page loads. See docs/DESIGN-recruit-rating-clarity.md."""
        fog = random.Random(f"{self.consensus_seed}:todayfog").uniform(TODAY_FOG_MIN, TODAY_FOG_MAX)
        rng = random.Random(f"{self.consensus_seed}:today:{source}")
        blurred = self.today_grade() + rng.uniform(-fog, fog)
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
    traits = _draw_traits(rng)
    potential = {a: _clamp(rng.gauss(talent, 6), GRADE_MIN, GRADE_MAX) for a in RICH_ATTRS}
    # Give the player a real SHAPE (net specialist / baseliner / server) instead of
    # a flat draw around one mean — weight-normalized so overall/STR is unchanged.
    _apply_style_profile(potential, traits["play_style"], rng)

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
