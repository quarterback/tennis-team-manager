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
HOME_COUNTRY_PIPELINE = 66.0

SOURCE_HIGH_SCHOOL = "high_school"
SOURCE_INTERNATIONAL = "international"
SOURCE_BLEND = "blend"
SOURCE_PREFERENCES = (SOURCE_HIGH_SCHOOL, SOURCE_INTERNATIONAL, SOURCE_BLEND)

ARCHETYPE_LIFER = "coaching_lifer"
ARCHETYPE_FORMER_PRO = "former_pro"
ARCHETYPE_RECRUITING_CLOSER = "recruiting_closer"
ARCHETYPE_DEVELOPMENT_GURU = "development_guru"
ARCHETYPE_TACTICIAN = "tactician"
ARCHETYPES = (
    ARCHETYPE_LIFER,
    ARCHETYPE_FORMER_PRO,
    ARCHETYPE_RECRUITING_CLOSER,
    ARCHETYPE_DEVELOPMENT_GURU,
    ARCHETYPE_TACTICIAN,
)

COUNTRY_REGIONS = {
    "US": "domestic", "USA": "domestic", "CAN": "canada",
    "ESP": "europe", "FRA": "europe", "GBR": "europe", "GER": "europe",
    "ITA": "europe", "SWE": "europe", "CZE": "europe", "SRB": "europe",
    "ARG": "latin_america", "BRA": "latin_america", "COL": "latin_america",
    "MEX": "latin_america", "CHI": "latin_america",
    "AUS": "australia", "NZL": "australia",
    "JPN": "asia_pacific", "CHN": "asia_pacific", "KOR": "asia_pacific",
    "IND": "asia_pacific",
    "RSA": "africa", "MAR": "africa", "TUN": "africa",
}
COUNTRY_POOL = tuple(COUNTRY_REGIONS.keys())

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

ARCHETYPE_ATTR_BONUSES = {
    ARCHETYPE_LIFER: {"teaching_skill": 4, "lineup_management": 4, "discipline": 3, "loyalty": 4, "trustworthiness": 3},
    ARCHETYPE_FORMER_PRO: {"charisma": 5, "match_tactics": 4, "talent_evaluation": 3, "salesmanship": 4, "international_scouting": 3},
    ARCHETYPE_RECRUITING_CLOSER: {"charisma": 4, "program_builder": 3, "salesmanship": 6, "relationship_building": 4, "persistence": 4},
    ARCHETYPE_DEVELOPMENT_GURU: {"teaching_skill": 6, "training_design": 5, "mental_coaching": 3, "player_development_pitch": 5, "talent_projection": 4},
    ARCHETYPE_TACTICIAN: {"match_tactics": 6, "lineup_management": 5, "adaptability": 4, "talent_projection": 2},
}


def _clamp(v: float, lo: int = GRADE_MIN, hi: int = GRADE_MAX) -> float:
    return float(lo if v < lo else hi if v > hi else v)


def _stable_seed(*parts: object) -> int:
    raw = "|".join(str(p) for p in parts)
    return int.from_bytes(hashlib.blake2s(raw.encode("utf-8"), digest_size=8).digest(), "big")


def _normalize_country(country: str) -> str:
    return (country or "").strip().upper()


def _region_for_country(country: str) -> str:
    return COUNTRY_REGIONS.get(_normalize_country(country), "global")


def _normalize_grades(data: Mapping[str, float] | None, keys: tuple[str, ...], default: float = 50.0) -> dict[str, float]:
    data = data or {}
    return {k: _clamp(float(data.get(k, default))) for k in keys}


def _normalize_pipeline(data: Mapping[str, float] | None) -> dict[str, float]:
    data = data or {}
    return {str(k): _clamp(float(v), PIPELINE_MIN, PIPELINE_MAX) for k, v in data.items()}


def _apply_archetype(attrs: dict[str, float], recruiting: dict[str, float], archetype: str) -> None:
    for key, bonus in ARCHETYPE_ATTR_BONUSES.get(archetype, {}).items():
        if key in attrs:
            attrs[key] = _clamp(attrs[key] + bonus)
        elif key in recruiting:
            recruiting[key] = _clamp(recruiting[key] + bonus)


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
    home_country: str = "US"
    home_region: str = ""
    archetype: str = ARCHETYPE_LIFER
    personality: str = "balanced"
    offensive_style: str = "balanced"
    pid: str = ""

    def __post_init__(self) -> None:
        self.attrs = _normalize_grades(self.attrs, COACH_ATTRS)
        if not isinstance(self.recruiting, RecruitingSkill):
            self.recruiting = RecruitingSkill(self.recruiting)
        if self.source_preference not in SOURCE_PREFERENCES:
            self.source_preference = SOURCE_BLEND
        if self.archetype not in ARCHETYPES:
            self.archetype = ARCHETYPE_LIFER
        self.home_country = _normalize_country(self.home_country or "US")
        self.home_region = self.home_region or _region_for_country(self.home_country)
        self.region_pipelines = _normalize_pipeline(self.region_pipelines)
        self.country_pipelines = _normalize_pipeline(self.country_pipelines)
        if not self.pid:
            self.pid = hashlib.blake2s(f"{self.name}|{self.school}|{self.home_country}".encode("utf-8"), digest_size=8).hexdigest()

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

    def home_country_match(self, prospect) -> bool:
        return _normalize_country(getattr(prospect, "country", "")) == self.home_country

    def pipeline_grade(self, prospect) -> float:
        """Return the best region/country pipeline grade for a prospect.

        Explicit country pipelines beat the automatic home-country boost. The
        home-country boost still beats broad region pipelines because a coach's
        personal network should matter even without a formal pipeline entry.
        """
        country = _normalize_country(getattr(prospect, "country", "") or "")
        region = getattr(prospect, "region", "") or ""
        if country in self.country_pipelines:
            return self.country_pipelines[country]
        if country == self.home_country:
            return HOME_COUNTRY_PIPELINE
        if region in self.region_pipelines:
            return self.region_pipelines[region]
        if region == self.home_region and self.home_region != "global":
            return 56.0
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

    def archetype_fit(self, prospect) -> float:
        if self.archetype == ARCHETYPE_FORMER_PRO:
            return 1.04 if not bool(getattr(prospect, "domestic", False)) else 1.01
        if self.archetype == ARCHETYPE_RECRUITING_CLOSER:
            return 1.04
        if self.archetype == ARCHETYPE_DEVELOPMENT_GURU:
            return 1.03 if getattr(prospect, "star_rating", lambda: 3)() <= 3 else 1.01
        if self.archetype == ARCHETYPE_TACTICIAN:
            return 1.02
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
        archetype = self.archetype_fit(prospect)
        academic = getattr(prospect, "academic_rating", 79)
        academic_edge = 1.0 + max(-0.06, min(0.06, (academic - 79) / 250.0)) * ((self.recruiting.grade("academic_pitch") - 50.0) / 30.0)
        return _clamp(base * pipeline * source * archetype * academic_edge)


def generate_coach(rng: random.Random, name: str, school: str = "", *, base: float = 50.0,
                   source_preference: str | None = None, home_country: str | None = None,
                   archetype: str | None = None) -> Coach:
    """Generate a deterministic coach profile from a caller-owned RNG."""
    archetype = archetype or rng.choice(ARCHETYPES)
    home_country = _normalize_country(home_country or rng.choice(COUNTRY_POOL))
    attrs = {a: _clamp(rng.gauss(base, 8)) for a in COACH_ATTRS}
    recruiting = {a: _clamp(rng.gauss(base, 9)) for a in RECRUITING_ATTRS}
    _apply_archetype(attrs, recruiting, archetype)
    pref = source_preference or rng.choice(SOURCE_PREFERENCES)
    region_pool = ("domestic", "europe", "latin_america", "asia_pacific", "canada", "australia", "africa")
    region_pipelines = {r: _clamp(rng.gauss(base + 6, 7), PIPELINE_MIN, PIPELINE_MAX)
                        for r in rng.sample(region_pool, k=2)}
    country_pipelines = {c: _clamp(rng.gauss(base + 8, 7), PIPELINE_MIN, PIPELINE_MAX)
                         for c in rng.sample(COUNTRY_POOL, k=2)}
    return Coach(
        name=name,
        school=school,
        attrs=attrs,
        recruiting=RecruitingSkill(recruiting),
        source_preference=pref,
        region_pipelines=region_pipelines,
        country_pipelines=country_pipelines,
        home_country=home_country,
        home_region=_region_for_country(home_country),
        archetype=archetype,
        personality=rng.choice(("balanced", "player-first", "hard-driving", "tactician", "closer")),
        offensive_style=rng.choice(("balanced", "serve-first", "baseline", "counterpunch", "all-court")),
    )


def coach_for_program(school: str, *, seed: int = 2026, base: float = 50.0) -> Coach:
    """Stable generated coach for a school until a career save persists one."""
    rng = random.Random(_stable_seed("coach", school, seed))
    return generate_coach(rng, f"{school} Head Coach", school=school, base=base)
