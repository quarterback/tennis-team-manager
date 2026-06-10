import os
import re

import app.gtt_seasonmode as gs
from app.web.server import create_app


def _client(tmp_path):
    p = str(tmp_path / "gtt.db")
    os.environ["TENNIS_DB_PATH"] = p
    gs.DB_PATH = p
    gs._schema_ready_for = None
    return create_app().test_client()


def test_gtt_hub_empty_then_create(tmp_path):
    c = _client(tmp_path)
    # empty hub renders with the new-league form
    r = c.get("/gtt")
    assert r.status_code == 200 and b"New league" in r.data
    # create a league
    r = c.post("/gtt/new", data={"name": "Test GTT", "seed": "7", "teams": "4"})
    assert r.status_code in (302, 303)
    lid = int(re.search(r"lg=(\d+)", r.headers["Location"]).group(1))
    hub = c.get(f"/gtt?lg={lid}")
    assert hub.status_code == 200 and b"Test GTT" in hub.data and b"Standings" in hub.data


def test_gtt_advance_and_champion(tmp_path):
    c = _client(tmp_path)
    lid = gs.create_league("L", seed=11, n_teams=4)
    # one step
    assert c.post("/gtt/advance", data={"lg": lid, "mode": "step"}).status_code in (302, 303)
    # finish to a champion
    assert c.post("/gtt/advance", data={"lg": lid, "mode": "finish"}).status_code in (302, 303)
    hub = c.get(f"/gtt?lg={lid}")
    assert b"Champion" in hub.data and b"MVP" in hub.data


def test_gtt_franchise_page_and_editor(tmp_path):
    c = _client(tmp_path)
    lid = gs.create_league("L", seed=5, n_teams=4)
    gs.advance_all(lid, fidelity="fast")
    fid = gs.franchises(lid)[0]["id"]
    page = c.get(f"/gtt/franchise/{fid}?lg={lid}")
    assert page.status_code == 200 and b"Edit franchise" in page.data
    # edit via the web form
    r = c.post(f"/gtt/franchise/{fid}/edit",
               data={"lg": lid, "name": "Webname FC", "city": "Test City, TC", "abbrev": "WEB"})
    assert r.status_code in (302, 303)
    page = c.get(f"/gtt/franchise/{fid}?lg={lid}")
    assert b"Webname FC" in page.data and b"Test City, TC" in page.data


def test_gtt_player_page(tmp_path):
    c = _client(tmp_path)
    lid = gs.create_league("L", seed=9, n_teams=4)
    gs.advance_all(lid, fidelity="fast")
    pid = gs.mvp(lid)["pid"]
    page = c.get(f"/gtt/player/{pid}?lg={lid}")
    assert page.status_code == 200 and b"Match log" in page.data and b"GTT MVP" in page.data


def test_gtt_in_nav(tmp_path):
    c = _client(tmp_path)
    r = c.get("/gtt")
    assert b"Global Team Tennis" in r.data and b"League Hub" in r.data and b"Hall of Fame" in r.data


def test_gtt_enshrine_and_hall_of_fame(tmp_path):
    c = _client(tmp_path)
    lid = gs.create_league("L", seed=9, n_teams=4)
    gs.advance_all(lid, fidelity="fast")
    pid = gs.mvp(lid)["pid"]
    # enshrine via the web, then it shows on the HoF page and as a badge
    r = c.post(f"/gtt/player/{pid}/enshrine", data={"lg": lid})
    assert r.status_code in (302, 303)
    hall = c.get(f"/gtt/hall-of-fame?lg={lid}")
    assert hall.status_code == 200 and b"Hall of Fame" in hall.data
    assert gs.is_enshrined(lid, pid)
    player = c.get(f"/gtt/player/{pid}?lg={lid}")
    assert b"Hall of Fame" in player.data            # frozen badge


def test_gtt_season_history_archive(tmp_path):
    c = _client(tmp_path)
    lid = gs.create_league("L", seed=3, n_teams=4)
    gs.advance_all(lid, fidelity="fast")             # one complete season
    hub = c.get(f"/gtt?lg={lid}")
    assert b"Season history" in hub.data
    hall = c.get(f"/gtt/hall-of-fame?lg={lid}")
    assert b"Champions" in hall.data


def test_decline_reduces_str_over_seasons(tmp_path):
    _client(tmp_path)
    lid = gs.create_league("L", seed=2026, n_teams=4)
    conn = gs._db()
    # an oldest founder will be past peak soonest
    pid = conn.execute("SELECT pid FROM gtt_players WHERE league_id=? ORDER BY age DESC LIMIT 1",
                       (lid,)).fetchone()["pid"]
    conn.close()
    start = gs.player_detail(lid, pid)["str"]
    for _ in range(3):
        gs.advance_all(lid, fidelity="fast")
        gs.advance(lid, fidelity="fast")
    d = gs.player_detail(lid, pid)
    # whether still active or retired, a past-peak player's frozen STR has dropped
    assert d["str"] < start
