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
    from app.web.state import coaching_staff
    recs = coach_honor_records("D1", "men")
    winners = [r for r in recs if r["award"] == "national_asst_coty"]
    assert winners and all(w["subject_type"] == "coach"
                           and w["label"].startswith("National Assistant") for w in winners)
    # every winner is a top-25 program tied at the most bottom-of-lineup wins (4/5/6
    # singles + 3rd doubles) — player development, not the head-coach W-L — and the
    # honoree is a non-head (assistant) coach on that staff. Usually one; ties repeat.
    sid = sm.get_or_create("D1", "men", seed=2026)
    rows = ranking_rows("D1", "men")
    top25 = [r.school for r in sorted(rows, key=lambda r: r.pi, reverse=True)[:25]]
    dev = sm.developmental_wins(sid)
    best = max(dev.get(s, 0) for s in top25)
    for w in winners:
        assert w["school"] in top25 and dev.get(w["school"], 0) == best
        staff = {c["coach_id"]: c["role"] for c in coaching_staff("D1", "men", w["school"])}
        assert staff.get(w["subject_id"]) in ("assoc", "asst")
    assert len({w["school"] for w in winners}) == sum(1 for s in top25 if dev.get(s, 0) == best)


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


def test_coach_move_preserves_both_programs_in_career_path():
    """Moving a head or assistant records where both coaches came from instead
    of rewriting their identity as though they had always held the new job."""
    import app.coachreg as coachreg
    create_app()
    coachreg.reset()
    a = coachreg.ensure_seat("D1", "men", "Stanford", "head", name="A",
                             home_country="US", archetype="x", dev=1, rec=1, tac=1,
                             tenure=5)
    b = coachreg.ensure_seat("D2", "men", "Barry", "asst", name="B",
                             home_country="US", archetype="x", dev=1, rec=1, tac=1,
                             tenure=2)

    assert coachreg.move_to(a["coach_id"], "men", "D2", "Barry", "asst", year=2028)
    assert [(j["school"], j["role"]) for j in coachreg.assignments(a["coach_id"])] == [
        ("Stanford", "head"), ("Barry", "asst")]
    assert [(j["school"], j["role"]) for j in coachreg.assignments(b["coach_id"])] == [
        ("Barry", "asst"), ("Stanford", "head")]


def test_player_coach_is_a_normal_movable_coach():
    import app.coachreg as coachreg
    create_app()
    coachreg.reset()
    coachreg.ensure_seat("D2", "women", "Barry", "asst", name="Incumbent",
                         home_country="US", archetype="x", dev=1, rec=1, tac=1,
                         tenure=2)
    converted = coachreg.create_from_player(
        "player-1", name="Graduate", home_country="US", division="D2",
        gender="women", school="Barry", role="asst", dev=55, rec=48, tac=52)
    coachreg.ensure_seat("D1", "women", "Stanford", "head", name="Other Coach",
                         home_country="US", archetype="x", dev=1, rec=1, tac=1,
                         tenure=4)

    assert coachreg.move_to(converted["coach_id"], "women", "D1", "Stanford", "head",
                            year=2029)
    moved = coachreg.get(converted["coach_id"])
    assert (moved["school"], moved["role"], moved["player_pid"]) == (
        "Stanford", "head", "player-1")
    assert [job["school"] for job in coachreg.assignments(converted["coach_id"])] == [
        "Barry", "Stanford"]


def test_coach_honors_persist_and_follow_id(played_season):
    nat = next(r for r in coach_honor_records("D1", "men") if r["award"] == "national_coty")
    stamp_world_honors()
    car = honors.career(nat["subject_id"], "coach")
    assert any("Coach of the Year" in h["label"] for h in car)
    groups = coach_career_honors("D1", "men", nat["subject_id"])
    assert groups and groups[0]["awards"]
