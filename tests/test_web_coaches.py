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
    assert c["name"] == head["name"] and c["school"] == "Stanford"
    assert c["role_label"] == "Head Coach"


def test_coach_of_the_year_national_and_per_conference(played_season):
    recs = coach_honor_records("D1", "men")
    awards = [r["award"] for r in recs]
    assert awards.count("national_coty") == 1
    assert awards.count("conf_coty") >= 1
    # title credit reaches head coaches too
    assert "national_champion" in awards


def test_coach_carousel_moves_coaches_and_followers():
    import copy
    import random
    import app.world as wd
    import app.coachreg as coachreg
    create_app()
    wd.start_new()
    w = wd.load_world()
    rosters = copy.deepcopy(wd.developed_rosters(w))   # don't mutate the cache
    res = wd.coach_carousel(rosters, {}, random.Random(7), "men")
    assert res["moves"] > 0
    # a moved coach now resolves to a different school in the registry
    src, dest, _k = res["sample"][0]
    # dest's head coach is whoever moved up (came from src); their id resolves to dest
    dest_div = next(d for (d, g) in rosters if g == "men" and dest in rosters[(d, g)])
    head_id = coachreg.head_seats(dest_div, "men")[dest]
    assert coachreg.get(head_id)["school"] == dest


def test_national_assistant_coach_of_the_year(played_season):
    import app.seasonmode as sm
    from app.web.awards import ranking_rows
    recs = coach_honor_records("D1", "men")
    awards = [r["award"] for r in recs]
    assert awards.count("national_asst_coty") == 1
    asst = next(r for r in recs if r["award"] == "national_asst_coty")
    assert asst["subject_type"] == "coach" and asst["label"].startswith("National Assistant")
    # it goes to the top-25 program with the most bottom-of-lineup wins (4/5/6
    # singles + 3rd doubles) — player development, not the head-coach W-L.
    sid = sm.get_or_create("D1", "men", seed=2026)
    rows = ranking_rows("D1", "men")
    top25 = [r.school for r in sorted(rows, key=lambda r: r.pi, reverse=True)[:25]]
    dev, pi_by = sm.developmental_wins(sid), {r.school: r.pi for r in rows}
    assert asst["school"] == max(top25, key=lambda s: (dev.get(s, 0), pi_by.get(s, 0.0), s))
    # the honoree is a non-head (assistant) coach on that staff
    from app.web.state import coaching_staff
    staff = {c["coach_id"]: c["role"] for c in coaching_staff("D1", "men", asst["school"])}
    assert staff.get(asst["subject_id"]) in ("assoc", "asst")


def test_coach_career_record_counts_head_seasons_only():
    import app.coachreg as coachreg
    from app.web.awards import coach_career_table
    create_app()
    coachreg.reset()
    coachreg.record_season("c1", 2026, 1, "D1", "men", "Stanford", "head", 20, 4)
    coachreg.record_season("c1", 2025, 0, "D1", "men", "UCLA", "asst", 10, 8)
    ct = coach_career_table("c1")
    # only the head-coach season banks career wins; the assistant year is shown but flagged
    assert ct["career_w"] == 20 and ct["career_l"] == 4 and ct["head_seasons"] == 1
    assert next(r for r in ct["rows"] if r["role"] == "asst")["counts"] is False
    assert next(r for r in ct["rows"] if r["role"] == "head")["counts"] is True


def test_swap_seats_moves_a_coach_between_seats():
    import app.coachreg as coachreg
    create_app()
    coachreg.reset()
    coachreg.ensure_seat("D1", "men", "Stanford", "head", name="A", home_country="USA",
                         archetype="x", dev=1, rec=1, tac=1, tenure=5)
    b = coachreg.ensure_seat("D1", "men", "Stanford", "asst", name="B", home_country="USA",
                             archetype="x", dev=1, rec=1, tac=1, tenure=2)
    assert coachreg.swap_seats("men", "D1", "Stanford", "head", "men", "D1", "Stanford", "asst")
    assert coachreg.head_seats("D1", "men")["Stanford"] == b["coach_id"]


def test_coach_honors_persist_and_follow_id(played_season):
    nat = next(r for r in coach_honor_records("D1", "men") if r["award"] == "national_coty")
    stamp_world_honors()
    car = honors.career(nat["subject_id"], "coach")
    assert any("Coach of the Year" in h["label"] for h in car)
    groups = coach_career_honors("D1", "men", nat["subject_id"])
    assert groups and groups[0]["awards"]
