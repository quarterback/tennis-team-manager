import app.honors as honors
from app.web.server import create_app
from app.web.awards import honor_records, stamp_world_honors, player_career_honors


def test_honor_records_cover_all_award_types():
    create_app()                       # bootstrap schemas
    recs = honor_records("D1", "men")
    awards = {r["award"] for r in recs}
    for key in ("national_poty", "conf_poty", "all_american", "all_conference",
                "conf_champion", "national_champion"):
        assert key in awards, f"missing {key}"
    # exactly one national POTY and one national champion roster's worth.
    assert sum(1 for r in recs if r["award"] == "national_poty") == 1


def test_hall_of_fame_archives_stamped_years():
    import app.world as wd
    app = create_app()
    wd.start_new()
    c = app.test_client()
    assert c.get("/hall-of-fame?u=D1-men").status_code == 200      # empty is fine
    stamp_world_honors()
    assert 2026 in honors.years()
    champs = honors.winners(2026, ["national_champion"])
    assert champs and all(r["award"] == "national_champion" for r in champs)
    body = c.get("/hall-of-fame?u=D1-men").get_data(as_text=True)
    assert "2026" in body and "Player of the Year" in body


def test_stamp_persists_and_follows_pid():
    create_app()
    poty = next(r for r in honor_records("D1", "men") if r["award"] == "national_poty")
    stamp_world_honors()
    car = honors.career(poty["subject_id"], "player")
    assert car, "stamped honors should be queryable by pid"
    labels = {h["label"] for h in car}
    assert "National Player of the Year" in labels
    # grouped-by-year view used by the player card
    groups = player_career_honors("D1", "men", poty["subject_id"])
    assert groups and groups[0]["awards"]
