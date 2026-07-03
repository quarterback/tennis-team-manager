"""
Rich tennis player attributes plus derived engine drivers.

The persistent player model lives on the 20-80 scouting scale and is intentionally
wider than the match engine. The engine still consumes the nine stable [0, 1]
drivers from ``engine.state.ATTRS``; this module owns the translation so rally
logic can stay small while career/recruiting screens get a real tennis profile.

The current build is hardcourt-only. Condition comfort is modeled through indoor,
outdoor, wind, heat, and crowd traits rather than clay/grass surface ratings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

GRADE_MIN, GRADE_MAX = 20, 80
# GRADE_MAX (80) stays the NORMALIZATION reference — grade 80 == unit 1.0 == "college
# ceiling" — so every normal player is completely unchanged. GRADE_CEIL is a separate,
# higher HARD clamp: only the pro tier (app.pros) is generated into the 80-GRADE_CEIL
# headroom, so pros read above 80 (OVR/STR) and their drivers normalize ABOVE 1.0, making
# them measurably better on court (the engine clamps the final probability, not the input).
# Normal generation still clamps to GRADE_MAX, so raising this ceiling touches nobody else.
GRADE_CEIL = 100

RICH_ATTRS = (
    # Serve / return
    "first_serve_power", "first_serve_accuracy", "second_serve_quality",
    "serve_variety", "return_quality", "return_aggression", "return_depth",
    # Groundstrokes
    "forehand_power", "forehand_control", "backhand_power", "backhand_control",
    "groundstroke_consistency", "shot_tolerance", "rally_patience",
    # Point construction / tactical tools
    "court_vision", "pattern_execution", "approach_shot", "transition_game",
    "drop_touch", "lob_touch", "passing_precision", "slice_control",
    # Net / doubles
    "net_play", "volley_touch", "overhead", "poaching", "doubles_chemistry",
    # Movement / physical
    "footwork", "speed", "agility", "balance", "stamina", "strength",
    "flexibility", "recovery",
    # Mental
    "composure", "focus", "clutch", "resilience", "competitiveness",
    "coachability", "discipline",
    # Hardcourt conditions
    "indoor_comfort", "outdoor_comfort", "wind_tolerance", "heat_tolerance",
    "crowd_pressure",
    # Team / program fit
    "academic_fit", "team_culture", "leadership", "training_drive",
)

DRIVER_ATTRS = (
    "serve_power", "serve_placement", "return_game", "forehand", "backhand",
    "movement", "stamina", "mental", "consistency",
)

TRAIT_DEFAULTS = {
    "handedness": "right",
    "backhand_style": "two_handed",
    "play_style": "balanced",
    "temperament": "steady",
}

OVERALL_WEIGHTS = {
    "first_serve_power": 0.040, "first_serve_accuracy": 0.038,
    "second_serve_quality": 0.032, "serve_variety": 0.018,
    "return_quality": 0.050, "return_aggression": 0.025, "return_depth": 0.025,
    "forehand_power": 0.040, "forehand_control": 0.045,
    "backhand_power": 0.035, "backhand_control": 0.040,
    "groundstroke_consistency": 0.055, "shot_tolerance": 0.030,
    "rally_patience": 0.025, "court_vision": 0.025, "pattern_execution": 0.027,
    "approach_shot": 0.015, "transition_game": 0.015,
    "drop_touch": 0.006, "lob_touch": 0.006, "passing_precision": 0.012,
    "slice_control": 0.010, "net_play": 0.022, "volley_touch": 0.018,
    "overhead": 0.012, "poaching": 0.010, "doubles_chemistry": 0.020,
    "footwork": 0.038, "speed": 0.032, "agility": 0.030, "balance": 0.014,
    "stamina": 0.030, "strength": 0.012, "flexibility": 0.010, "recovery": 0.016,
    "composure": 0.026, "focus": 0.026, "clutch": 0.024,
    "resilience": 0.020, "competitiveness": 0.022, "coachability": 0.014,
    "discipline": 0.014, "indoor_comfort": 0.006, "outdoor_comfort": 0.006,
    "wind_tolerance": 0.008, "heat_tolerance": 0.008, "crowd_pressure": 0.008,
    "academic_fit": 0.004, "team_culture": 0.004, "leadership": 0.006,
    "training_drive": 0.012,
}
_WEIGHT_TOTAL = sum(OVERALL_WEIGHTS.values())


def clamp_grade(v: float) -> float:
    # Upper bound is GRADE_CEIL (pros live in 80-GRADE_CEIL); normal generation clamps to
    # GRADE_MAX itself, so ordinary players never reach the headroom.
    return float(GRADE_MIN if v < GRADE_MIN else GRADE_CEIL if v > GRADE_CEIL else v)


def grade_to_unit(g: float) -> float:
    # No upper clamp: grade 80 -> 1.0 (unchanged), and a pro's 80-90 attribute normalizes
    # ABOVE 1.0 so it reads as genuinely better through the engine's driver formulas (which
    # clamp the resulting probability, not this input). Reference stays GRADE_MAX (80).
    return max(0.0, (g - GRADE_MIN) / (GRADE_MAX - GRADE_MIN))


def unit_to_grade(v: float) -> float:
    return clamp_grade(GRADE_MIN + max(0.0, min(1.0, v)) * (GRADE_MAX - GRADE_MIN))


def _avg(values: tuple[float, ...]) -> float:
    return sum(values) / len(values)


def _legacy_to_rich(data: Mapping[str, float]) -> dict[str, float]:
    base = {k: float(data[k]) for k in data if k in DRIVER_ATTRS}
    fallback = _avg(tuple(base.values())) if base else 50.0

    def g(name: str, default: float = fallback) -> float:
        return clamp_grade(float(base.get(name, default)))

    serve_power = g("serve_power")
    serve_place = g("serve_placement")
    ret = g("return_game")
    fh = g("forehand")
    bh = g("backhand")
    move = g("movement")
    stam = g("stamina")
    mental = g("mental")
    cons = g("consistency")
    return {
        "first_serve_power": serve_power,
        "first_serve_accuracy": serve_place,
        "second_serve_quality": _avg((serve_place, cons)),
        "serve_variety": _avg((serve_power, serve_place, mental)),
        "return_quality": ret,
        "return_aggression": _avg((ret, mental)),
        "return_depth": _avg((ret, cons)),
        "forehand_power": fh,
        "forehand_control": _avg((fh, cons)),
        "backhand_power": bh,
        "backhand_control": _avg((bh, cons)),
        "groundstroke_consistency": cons,
        "shot_tolerance": _avg((cons, stam, mental)),
        "rally_patience": _avg((cons, mental)),
        "court_vision": _avg((fh, bh, mental)),
        "pattern_execution": _avg((fh, bh, cons, mental)),
        "approach_shot": _avg((fh, move)),
        "transition_game": _avg((move, fh, bh)),
        "drop_touch": _avg((fh, bh, mental)),
        "lob_touch": _avg((bh, mental, cons)),
        "passing_precision": _avg((ret, fh, bh)),
        "slice_control": _avg((bh, cons)),
        "net_play": _avg((move, mental, cons)),
        "volley_touch": _avg((move, mental)),
        "overhead": _avg((serve_power, move)),
        "poaching": _avg((move, mental)),
        "doubles_chemistry": _avg((mental, cons)),
        "footwork": move,
        "speed": move,
        "agility": move,
        "balance": _avg((move, cons)),
        "stamina": stam,
        "strength": _avg((serve_power, stam)),
        "flexibility": _avg((move, stam)),
        "recovery": _avg((stam, mental)),
        "composure": mental,
        "focus": _avg((mental, cons)),
        "clutch": mental,
        "resilience": _avg((mental, stam)),
        "competitiveness": mental,
        "coachability": _avg((mental, cons)),
        "discipline": _avg((mental, cons)),
        "indoor_comfort": _avg((serve_place, mental)),
        "outdoor_comfort": _avg((move, stam)),
        "wind_tolerance": _avg((serve_place, cons, mental)),
        "heat_tolerance": _avg((stam, mental)),
        "crowd_pressure": mental,
        "academic_fit": _avg((mental, cons)),
        "team_culture": _avg((mental, cons)),
        "leadership": mental,
        "training_drive": _avg((stam, mental)),
    }


def normalize_grades(data: Mapping[str, float] | None) -> dict[str, float]:
    if not data:
        return {a: 50.0 for a in RICH_ATTRS}
    if all(a in data for a in RICH_ATTRS):
        return {a: clamp_grade(float(data[a])) for a in RICH_ATTRS}
    rich = _legacy_to_rich(data)
    for a in RICH_ATTRS:
        rich.setdefault(a, 50.0)
    return {a: clamp_grade(rich[a]) for a in RICH_ATTRS}


@dataclass(frozen=True)
class PlayerAttributes:
    grades: Mapping[str, float]
    handedness: str = TRAIT_DEFAULTS["handedness"]
    backhand_style: str = TRAIT_DEFAULTS["backhand_style"]
    play_style: str = TRAIT_DEFAULTS["play_style"]
    temperament: str = TRAIT_DEFAULTS["temperament"]

    def __post_init__(self) -> None:
        object.__setattr__(self, "grades", normalize_grades(self.grades))

    def grade(self, attr: str) -> float:
        if attr in self.grades:
            return self.grades[attr]
        drivers = self.derive_drivers()
        if attr in drivers:
            return unit_to_grade(drivers[attr])
        raise KeyError(attr)

    @property
    def drop_shot(self) -> float:
        return _avg((self.grades["drop_touch"], self.grades["court_vision"], self.grades["forehand_control"]))

    @property
    def lob(self) -> float:
        return _avg((self.grades["lob_touch"], self.grades["court_vision"], self.grades["backhand_control"]))

    @property
    def passing_shot(self) -> float:
        return _avg((self.grades["passing_precision"], self.grades["speed"], self.grades["return_quality"]))

    @property
    def slice(self) -> float:
        return _avg((self.grades["slice_control"], self.grades["backhand_control"], self.grades["rally_patience"]))

    def overall_grade(self) -> float:
        return sum(OVERALL_WEIGHTS[a] * self.grades[a] for a in RICH_ATTRS) / _WEIGHT_TOTAL

    def derive_driver_grades(self) -> dict[str, float]:
        g = self.grades
        return {
            "serve_power": _avg((g["first_serve_power"], g["second_serve_quality"], g["strength"])),
            "serve_placement": _avg((g["first_serve_accuracy"], g["second_serve_quality"], g["serve_variety"])),
            "return_game": _avg((g["return_quality"], g["return_aggression"], g["return_depth"])),
            "forehand": _avg((g["forehand_power"], g["forehand_control"], g["pattern_execution"])),
            "backhand": _avg((g["backhand_power"], g["backhand_control"], g["slice_control"])),
            "movement": _avg((g["footwork"], g["speed"], g["agility"], g["balance"])),
            "stamina": _avg((g["stamina"], g["recovery"], g["heat_tolerance"])),
            "mental": _avg((g["composure"], g["focus"], g["clutch"], g["resilience"], g["competitiveness"])),
            "consistency": _avg((g["groundstroke_consistency"], g["shot_tolerance"], g["discipline"])),
        }

    def derive_drivers(self) -> dict[str, float]:
        return {a: grade_to_unit(v) for a, v in self.derive_driver_grades().items()}
