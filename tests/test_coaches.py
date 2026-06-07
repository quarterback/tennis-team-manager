from app.coaches import (
    Coach,
    RecruitingSkill,
    SOURCE_BLEND,
    SOURCE_HIGH_SCHOOL,
    SOURCE_INTERNATIONAL,
    coach_for_program,
)
from app.development import Prospect
from engine import ATTRS


def _prospect(country="US", region="domestic", domestic=True, academic=79):
    return Prospect(
        name="Recruit",
        country=country,
        region=region,
        domestic=domestic,
        academic_rating=academic,
        current={a: 50.0 for a in ATTRS},
        potential={a: 60.0 for a in ATTRS},
    )


def _coach(pref=SOURCE_BLEND):
    return Coach(
        name="Coach",
        school="Baseline State",
        attrs={
            "teaching_skill": 70,
            "charisma": 65,
            "match_tactics": 55,
            "lineup_management": 54,
            "training_design": 68,
            "fitness_program": 58,
            "mental_coaching": 62,
            "talent_evaluation": 64,
            "academic_support": 60,
            "program_builder": 66,
            "discipline": 52,
            "adaptability": 57,
        },
        recruiting=RecruitingSkill({
            "salesmanship": 70,
            "relationship_building": 68,
            "loyalty": 66,
            "player_development_pitch": 72,
            "talent_projection": 65,
            "academic_pitch": 60,
            "domestic_scouting": 69,
            "international_scouting": 48,
            "persistence": 64,
            "trustworthiness": 67,
        }),
        source_preference=pref,
        region_pipelines={"domestic": 72, "europe": 45},
        country_pipelines={"ESP": 78},
    )


def test_coach_scores_and_grades_are_stable_band():
    c = _coach()
    assert 20 <= c.grade("teaching_skill") <= 80
    assert c.development_score > 60
    assert c.recruiting_score > 55
    assert 20 <= c.tactical_score <= 80


def test_country_pipeline_beats_region_pipeline():
    c = _coach()
    spanish = _prospect(country="ESP", region="europe", domestic=False)
    assert c.pipeline_grade(spanish) == 78
    assert c.pipeline_multiplier(spanish) > 1.0


def test_source_preference_changes_recruiting_fit():
    domestic = _prospect(country="US", region="domestic", domestic=True)
    international = _prospect(country="ESP", region="europe", domestic=False)
    hs_coach = _coach(SOURCE_HIGH_SCHOOL)
    intl_coach = _coach(SOURCE_INTERNATIONAL)
    assert hs_coach.source_fit(domestic) > hs_coach.source_fit(international)
    assert intl_coach.source_fit(international) > intl_coach.source_fit(domestic)


def test_pipeline_improves_fit_for_target_area():
    c = _coach(SOURCE_BLEND)
    domestic = _prospect(country="US", region="domestic", domestic=True)
    no_pipe = _prospect(country="NZL", region="oceania", domestic=False)
    assert c.recruiting_fit(domestic) > c.recruiting_fit(no_pipe)


def test_program_coach_generation_is_deterministic():
    a = coach_for_program("Oregon", seed=2026)
    b = coach_for_program("Oregon", seed=2026)
    assert a.pid == b.pid
    assert a.attrs == b.attrs
    assert a.region_pipelines == b.region_pipelines
    assert a.country_pipelines == b.country_pipelines
