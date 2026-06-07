"""
College coach model.

Coaches are not just program labels. They shape development, recruiting reach,
and fit. The model is intentionally separate from player attributes: a coach's
academic or recruiting skill can influence admissions/recruiting decisions later,
but it never becomes a player's tennis talent.

All ratings use the same 20-80 scouting scale used by players. Pipeline strengths
are also 20-80 grades and answer a narrower question: "how much does this coach
help with recruits from this region or country?"
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Mapping

GRADE_MIN, GRADE_MAX = 20, 80
PIPELINE_MIN, PIPELINE_MAX = 20, 80

SOURCE_HIGH_SCHOOL = "high_school"
SOURCE_INTERNATIONAL = "international"
SOURCE_BLEND = "blend"
SOURCE_PREFERENCES = (SOURCE_HIGH_SCHOOL, SOURCE_INTERNATIONAL, SOURCE_BLEND)

COACH_ATTRS = (
    "teaching_skill",
    "charisma",
    "match_tactics",
    "lineup_management",
    "training_design",
    "fitness_program",
    "mental_coaching",
    "talent_evaluation",
    "academic_support",
    "program_builder",
    "discipline",
    "adaptability",
)

RECRUITING_ATTRS = (
    "salesmanship",
    "relationship_building",
    "loyalty",
    "player_development_pitch",
    "talent_projection",
    "academic_pitch",
    "domestic_scouting",
    "international_scouting",
    "persistence",
    "trustworthiness",
)


def _clamp(v: float, lo: int = GRADE_MIN, hi: int = GRADE_MAX) -> float:
    return float(lo if v < lo else hi if v > hi else v)


def _stable_seed(*parts: object) -> int:
    raw = "|".join(str(p) for p in parts)
    return int.from_bytes(hashlib.blake2s(raw.encode("utf-8"), digest_size=8).digest(), "big")


def _normalize_grades(data: Mapping[str, float] | None, keys: tuple[str, ...], default: float = 50.0) -> dict[str, float]:
    data = data or {}
    return {k: _clamp(float(data.get(k, default))) for k in keys}


def _normalize_pipeline(data: Mapping[str, float] | None) -> dict[str, float]:
    data = data or {}
    return {str(k): _clamp(float(v), PIPELINE_MIN, PIPELINE_MAX) for k, v in data.items()}


@dataclass(frozen=True)
class RecruitingSkill:
    grades: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "grades", _normalize_grades(self.grades, RECRUITING_ATTRS))

    def grade(self, attr: str) -> float:
        if attr not in self.grades:
            raise KeyError(attr)
        return self.grades[attr]

    @property
    def domestic_score(self) -> float:
        g = self.grades
        return (g["salesmanship"] + g["relationship_building"] + g["domestic_scouting"] + g["persistence"]) / 4.0

    @property
    def international_score(self) -> float:
        g = self.grades
        return (g["salesmanship"] + g["relationship_building"] + g["international_scouting"] + g["trustworthiness"]) / 4.0

    @property
    def development_pitch(self) -> float:
        g = self.grades
        return (g["player_development_pitch"] + g["talent_projection"] + g["loyalty"]) / 3.0

    @property
    def overall(self) -> float:
        weights = {
            "salesmanship": 0.15,
            "relationship_building": 0.13,
            "loyalty": 0.10,
            "player_development_pitch": 0.10,
            "talent_projection": 0.10,
            "academic_pitch": 0.08,
            "domestic_scouting": 0.09,
            "international_scouting": 0.09,
            "persistence": 0.08,
            "trustworthiness": 0.08,
        }
        return sum(weights[k] * self.grades[k] for k in RECRUITING_ATTRS)


@dataclass
class Coach:
    name: str
    school: str = ""
    attrs: dict = field(default_factory=dict)
    recruiting: RecruitingSkill = field(default_factory=RecruitingSkill)
    source_preference: str = SOURCE_BLEND
    region_pipelines: dict = field(default_factory=dict)
    country_pipelines: dict = field(default_factory=dict)
    personality: str = "balanced"
    offensive_style: str = "balanced"
    pid: str = ""

    def __post_init__(self) -> None:
        self.attrs = _normalize_grades(self.attrs, COACH_ATTRS)
        if not isinstance(self.recruiting, RecruitingSkill):
            self.recruiting = RecruitingSkill(self.recruiting)
        if self.source_preference not in SOURCE_PREFERENCES:
            self.source_preference = SOURCE_BLEND
        self.region_pipelines = _normalize_pipeline(self.region_pipelines)
        self.country_pipelines = _normalize_pipeline(self.country_pipelines)
        if not self.pid:
            self.pid = hashlib.blake2s(f"{self.name}|{self.school}".encode("utf-8"), digest_size=8).hexdigest()

    def grade(self, attr: str) -> float:
        if attr not in self.attrs:
            raise KeyError(attr)
        return self.attrs[attr]

    @property
    def development_score(self) -> float:
        return (
            self.attrs["teaching_skill"] * 0.34
            + self.attrs["training_design"] * 0.18
            + self.attrs["fitness_program"] * 0.12
            + self.attrs["mental_coaching"] * 0.14
            + self.recruiting.development_pitch * 0.22
        )

    @property
    def recruiting_score(self) -> float:
        return self.recruiting.overall * 0.70 + self.attrs["charisma"] * 0.20 + self.attrs["program_builder"] * 0.10

    @property
    def tactical_score(self) -> float:
        return (self.attrs["match_tactics"] + self.attrs["lineup_management"] + self.attrs["adaptability"]) / 3.0

    def pipeline_grade(self, prospect) -> float:
        """Return the best region/country pipeline grade for a prospect.

        Country pipelines intentionally beat broad region pipelines when both
        exist. Country values should use whatever code the prospect uses, such as
        ``US``, ``ESP``, or ``Spain``; this layer just matches strings.
        """
        country = getattr(prospect, "country", "") or ""
        region = getattr(prospect, "region", "") or ""
        if country in self.country_pipelines:
            return self.country_pipelines[country]
        if region in self.region_pipelines:
            return self.region_pipelines[region]
        return 50.0

    def source_fit(self, prospect) -> float:
        domestic = bool(getattr(prospect, "domestic", False))
        if self.source_preference == SOURCE_BLEND:
            return 1.0
        if self.source_preference == SOURCE_HIGH_SCHOOL:
            return 1.10 if domestic else 0.92
        if self.source_preference == SOURCE_INTERNATIONAL:
            return 1.12 if not domestic else 0.90
        return 1.0

    def pipeline_multiplier(self, prospect) -> float:
        """Convert a 20-80 pipeline grade into a gentle signing multiplier."""
        grade = self.pipeline_grade(prospect)
        return 1.0 + (grade - 50.0) / 100.0

    def recruiting_fit(self, prospect) -> float:
        """Coach-side recruiting fit for a prospect on a roughly 20-80 scale.

        This is not the final recruit decision model. It is the coach contribution
        that later systems can combine with school prestige, scholarship money,
        playing-time path, academic admissions, and recruit motivations.
        """
        domestic = bool(getattr(prospect, "domestic", False))
        base = self.recruiting.domestic_score if domestic else self.recruiting.international_score
        pipeline = self.pipeline_multiplier(prospect)
        source = self.source_fit(prospect)
        academic = getattr(prospect, "academic_rating", 79)
        academic_edge = 1.0 + max(-0.06, min(0.06, (academic - 79) / 250.0)) * ((self.recruiting.grade("academic_pitch") - 50.0) / 30.0)
        return _clamp(base * pipeline * source * academic_edge)


def generate_coach(rng: random.Random, name: str, school: str = "", *, base: float = 50.0,
                   source_preference: str | None = None) -> Coach:
    """Generate a deterministic coach profile from a caller-owned RNG."""
    attrs = {a: _clamp(rng.gauss(base, 8)) for a in COACH_ATTRS}
    recruiting = {a: _clamp(rng.gauss(base, 9)) for a in RECRUITING_ATTRS}
    pref = source_preference or rng.choice(SOURCE_PREFERENCES)
    region_pool = ("domestic", "europe", "latin_america", "asia_pacific", "canada", "australia")
    country_pool = ("US", "ESP", "FRA", "GBR", "ARG", "BRA", "CAN", "AUS", "JPN", "CHN")
    region_pipelines = {r: _clamp(rng.gauss(base + 6, 7), PIPELINE_MIN, PIPELINE_MAX)
                        for r in rng.sample(region_pool, k=2)}
    country_pipelines = {c: _clamp(rng.gauss(base + 8, 7), PIPELINE_MIN, PIPELINE_MAX)
                         for c in rng.sample(country_pool, k=2)}
    return Coach(
        name=name,
        school=school,
        attrs=attrs,
        recruiting=RecruitingSkill(recruiting),
        source_preference=pref,
        region_pipelines=region_pipelines,
        country_pipelines=country_pipelines,
        personality=rng.choice(("balanced", "player-first", "hard-driving", "tactician", "closer")),
        offensive_style=rng.choice(("balanced", "serve-first", "baseline", "counterpunch", "all-court")),
    )


def coach_for_program(school: str, *, seed: int = 2026, base: float = 50.0) -> Coach:
    """Stable generated coach for a school until a career save persists one."""
    rng = random.Random(_stable_seed("coach", school, seed))
    return generate_coach(rng, f"{school} Head Coach", school=school, base=base)
