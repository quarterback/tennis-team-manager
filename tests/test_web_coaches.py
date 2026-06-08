import app.honors as honors
from app.web.server import create_app
from app.web.state import coaching_staff, get_coach
from app.web.awards import coach_honor_records, stamp_world_honors, coach_career_honors


def test_coaches_have_stable_ids_and_pages():
    create_app()
    staff = coaching_staff("D1", "men", "Stanford")
    assert staff and all(s.get("coach_id") for s in staff)
    # ids are stable across calls (persisted, not regenerated)
    again = coaching_staff("D1", "men", "Stanford")
    assert [s["coach_id"] for s in staff] == [s["coach_id"] for s in again]
    head = next(s for s in staff if s["role"] == "head")
    c = get_coach(head["coach_id"])
    assert c["name"] == head["coach"].name and c["school"] == "Stanford"
    assert c["role_label"] == "Head Coach"


def test_coach_of_the_year_national_and_per_conference():
    create_app()
    recs = coach_honor_records("D1", "men")
    awards = [r["award"] for r in recs]
    assert awards.count("national_coty") == 1
    assert awards.count("conf_coty") >= 1
    # title credit reaches head coaches too
    assert "national_champion" in awards


def test_coach_honors_persist_and_follow_id():
    create_app()
    nat = next(r for r in coach_honor_records("D1", "men") if r["award"] == "national_coty")
    stamp_world_honors()
    car = honors.career(nat["subject_id"], "coach")
    assert any("Coach of the Year" in h["label"] for h in car)
    groups = coach_career_honors("D1", "men", nat["subject_id"])
    assert groups and groups[0]["awards"]
