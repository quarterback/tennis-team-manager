"""
Playing-style ARCHETYPES — grounded in real tennis, and revolving by era.

Replaces the original five-way `offensive_style` ({balanced, serve-first,
baseline, counterpunch, all-court}), which was too coarse to produce recognisable
clubs: "baseline" covers most of the professional game and "serve-first" covers a
handful of specialists, so almost every club landed in the same two buckets.

Two things this module gets right that a flat list of attributes cannot:

**Weighted attributes, not sets.** Each archetype maps attribute -> weight, so a
serve-and-volley staff builds the volley harder than the overhead, and a
counterpuncher's legs move more than their slice. Flat sets made every emphasised
attribute move by exactly the same amount, which reads as a bulk buff rather than
a style.

**Format weighting.** The pro (GTT) tie is 3 men's singles + 3 women's singles +
**3 mixed doubles** = 9 lines, first to 5 — doubles is a THIRD of every tie,
against one point of seven in a college dual. `engine/doubles.py` reads
`net_play`, `poaching`, `volley_touch`, `overhead` and `doubles_chemistry`
directly, so net skills are roughly 2.3x more load-bearing for the pros than for
the college game. `FORMAT_WEIGHTS` lets a caller say so instead of pretending
every attribute is worth the same everywhere.

**Revolving eras.** Real tennis has metas that come and go — serve-and-volley
gives way to power baseline, which gives way to athletic defence, which gives way
to first-strike. `era_for(year)` rotates a prevailing style through the league, so
new staffs skew toward what is currently winning and the game's texture changes
across decades instead of being fixed at world creation.
"""
from __future__ import annotations

# Every attribute named here must exist in development.RICH_ATTRS (enforced by
# tests/test_playstyles.py, so a typo can't silently become a no-op boost).
ARCHETYPES: dict[str, dict[str, float]] = {
    # Sampras / Edberg / Rafter — first strike then forward. Lethal in a format
    # where a third of the lines are doubles.
    "serve-and-volley": {
        "first_serve_power": 0.8, "first_serve_accuracy": 1.0, "serve_variety": 0.7,
        "net_play": 1.0, "volley_touch": 1.0, "approach_shot": 0.9,
        "transition_game": 0.8, "overhead": 0.6, "poaching": 0.5,
    },
    # Isner / Karlovic / Raonic — hold serve, steal one break, go home.
    "big-server": {
        "first_serve_power": 1.0, "first_serve_accuracy": 0.8,
        "second_serve_quality": 0.7, "serve_variety": 0.5, "overhead": 0.5,
        "composure": 0.4, "clutch": 0.4,
    },
    # Agassi / Serena — stand on the baseline and take time away.
    "aggressive-baseliner": {
        "forehand_power": 1.0, "backhand_power": 0.9, "return_aggression": 0.9,
        "return_depth": 0.7, "pattern_execution": 0.6, "groundstroke_consistency": 0.5,
        "balance": 0.4,
    },
    # Nadal / Muster — heavy shape, endless legs, wins the long ones.
    "topspin-grinder": {
        "forehand_control": 0.9, "groundstroke_consistency": 1.0, "shot_tolerance": 1.0,
        "rally_patience": 0.8, "stamina": 0.9, "recovery": 0.7, "strength": 0.5,
        "resilience": 0.6,
    },
    # Hewitt / Murray / Simon — absorb, redirect, pass.
    "counterpuncher": {
        "rally_patience": 1.0, "shot_tolerance": 0.9, "passing_precision": 0.9,
        "footwork": 0.9, "speed": 0.8, "slice_control": 0.6, "court_vision": 0.7,
        "resilience": 0.6,
    },
    # Djokovic / Sabalenka on defence — outrun the shot rather than out-hit it.
    "athletic-retriever": {
        "speed": 1.0, "agility": 1.0, "footwork": 0.9, "recovery": 0.8,
        "flexibility": 0.7, "shot_tolerance": 0.6, "stamina": 0.6,
    },
    # Federer / Navratilova — no hole, and comfortable forward.
    "all-court": {
        "serve_variety": 0.6, "forehand_control": 0.6, "backhand_control": 0.6,
        "court_vision": 0.8, "approach_shot": 0.7, "net_play": 0.8,
        "volley_touch": 0.7, "transition_game": 0.6, "pattern_execution": 0.6,
    },
    # Del Potro / Sharapova — three shots or fewer, every time.
    "first-strike": {
        "first_serve_power": 0.7, "return_depth": 0.8, "return_aggression": 0.9,
        "forehand_power": 1.0, "backhand_power": 0.8, "pattern_execution": 0.7,
        "clutch": 0.4,
    },
    # Santoro / Bartoli — junk, angles, nothing you practised for.
    "variety-junkballer": {
        "slice_control": 1.0, "drop_touch": 0.9, "lob_touch": 0.8, "serve_variety": 0.7,
        "court_vision": 0.8, "pattern_execution": 0.6, "focus": 0.5,
    },
    # Bryan brothers / Mattek-Sands — a doubles-first club, which in a 3-of-9
    # mixed-doubles format is a legitimate way to build a whole roster.
    "net-poacher": {
        "poaching": 1.0, "net_play": 1.0, "volley_touch": 0.9, "doubles_chemistry": 1.0,
        "overhead": 0.7, "agility": 0.6, "court_vision": 0.6,
    },
}

# What each archetype is worth per line-type, used to explain a club rather than
# to score it: singles-heavy archetypes are not "worse", they just win different
# lines. (Kept as data so a future board can show it.)
DOUBLES_LEANING = ("net-poacher", "serve-and-volley", "all-court")

# Per-format attribute weighting. The pro tie is a THIRD doubles, so the skills
# `engine/doubles.py` actually reads are worth more there than in a college dual
# where doubles is one point of seven. A weight of 1.0 is "normal".
FORMAT_WEIGHTS: dict[str, dict[str, float]] = {
    "gtt": {
        "net_play": 1.6, "volley_touch": 1.6, "poaching": 1.6,
        "doubles_chemistry": 1.6, "overhead": 1.3, "approach_shot": 1.2,
        "transition_game": 1.2,
    },
    "college": {},          # college doubles is 1 point of 7 — no thumb on the scale
}

# ---------------------------------------------------------------------------
# Revolving eras — the league's prevailing style, which changes over decades.
# ---------------------------------------------------------------------------
# Ordered so consecutive eras are a real swing rather than a shuffle: forward
# pressure -> raw power -> defence -> junk -> doubles-first, then round again.
ERA_CYCLE = (
    ("serve-and-volley", "net-poacher"),
    ("aggressive-baseliner", "first-strike"),
    ("athletic-retriever", "counterpuncher"),
    ("topspin-grinder", "all-court"),
    ("variety-junkballer", "big-server"),
)
ERA_LENGTH = 6          # seasons an era holds before the meta turns over
ERA_PULL = 0.65         # share of NEW staffs that adopt the prevailing styles


def era_for(year: int) -> tuple[str, ...]:
    """The archetypes in fashion in this league-year. Deterministic and cyclic:
    the game's texture turns over roughly every `ERA_LENGTH` seasons, so a save
    played for decades isn't stuck in one meta forever."""
    return ERA_CYCLE[(max(0, year) // ERA_LENGTH) % len(ERA_CYCLE)]


def era_name(year: int) -> str:
    """Human label for the prevailing meta, e.g. 'Serve-and-volley era'."""
    first = era_for(year)[0]
    return f"{first.replace('-', ' ').capitalize()} era"


def pick_archetype(rng, year: int) -> str:
    """An archetype for a new staff, pulled toward the era but never locked to it —
    a counter-trend club is how the next era gets seeded."""
    if rng.random() < ERA_PULL:
        return rng.choice(era_for(year))
    return rng.choice(tuple(ARCHETYPES))


def emphasis(archetype: str, fmt: str = "gtt") -> dict[str, float]:
    """{attribute: weight} this archetype builds, scaled for the format's demands.
    Empty for an unknown archetype (never a silent uniform buff)."""
    base = ARCHETYPES.get(archetype)
    if not base:
        return {}
    fw = FORMAT_WEIGHTS.get(fmt, {})
    return {a: w * fw.get(a, 1.0) for a, w in base.items()}
