import app.seasonmode as sm
from app.web.server import create_app


def test_season_web_flow(tmp_path):
    sm.DB_PATH = str(tmp_path / "season.db")
    c = create_app().test_client()
    assert b"Season" in c.get("/", follow_redirects=True).data   # nav (dashboard, or onboarding if no world yet)
    assert c.get("/season?u=D1-men").status_code == 200       # creates the season
    sm.advance(sm.get_or_create("D1", "men", seed=2026))   # standalone: no world driver
    hub = c.get("/season?u=D1-men")
    assert hub.status_code == 200 and b"Power Index" in hub.data
    portal = c.get("/data?u=D1-men")
    assert portal.status_code == 200 and b"Tour-style data center" in portal.data
    assert c.get("/season/standings?u=D1-men").status_code == 200
    assert c.get("/season/schedule?u=D1-men&school=Oregon").status_code == 200


def test_data_portal_export_reflects_live_sim(tmp_path):
    """The vroomtv export feed must read the same live season the /data page does.
    Regression: the feed once keyed universes by a lowercase 'd1', which forks a
    fresh preseason season (get_or_create matches division literally) and reports
    week-0/no-results while the sim is mid-season."""
    sm.DB_PATH = str(tmp_path / "season.db")
    c = create_app().test_client()
    c.get("/season?u=D1-men")                          # create the D1-men season
    sid0 = sm.get_or_create("D1", "men", seed=2026)
    for _ in range(3):                                 # play a few weeks of duals
        sm.advance(sid0)                               # standalone: no world driver

    sid = sm.get_or_create("D1", "men", seed=2026)
    season = sm.load_season(sid)
    assert season["current_week"] > 1                  # the live season has advanced

    feed = c.get("/export/data_portal.json").get_json()
    d1m = next(u for u in feed["universes"]
               if u["division"] == "d1" and u["gender"] == "men")
    # The feed mirrors the advanced season, not a fresh preseason fork.
    assert d1m["current_week"] == season["current_week"]
    assert d1m["has_live_results"] is True
    assert d1m["completed_duals"] > 0
