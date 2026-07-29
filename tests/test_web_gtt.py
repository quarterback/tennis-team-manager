import os
import re

import app.gtt_seasonmode as gs
from app.web.server import create_app


def _client(tmp_path):
    """A client on a genuinely isolated DB.

    `world.WORLD_DB` is resolved at IMPORT, so repointing only the GTT/season paths
    left the world tables on the repo-level tennis.db. A world left there by an
    earlier test module made `_prime_world` serve its cold-start loader page instead
    of the hub, and these tests failed only when run after that module.
    """
    import app.world as wd
    import app.seasonmode as sm
    p = str(tmp_path / "gtt.db")
    os.environ["TENNIS_DB_PATH"] = p
    gs.DB_PATH = p
    gs._schema_ready_for = None
    sm.DB_PATH = p
    sm._schema_ready_for = None
    wd.WORLD_DB = p
    wd._schema_ready_for = None
    wd._primed.clear()
    wd._base_cache.clear()
    wd._dev_cache.clear()
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


def test_gtt_advance_both_modes(tmp_path):
    c = _client(tmp_path)
    lid = gs.create_league("L", seed=11, n_teams=4)
    # "step" plays one full-engine week
    assert c.post("/gtt/advance", data={"lg": lid, "mode": "step"}).status_code in (302, 303)
    assert gs.load_league(lid)["current_week"] == 2
    # "finish" fast-sims the rest to a champion
    assert c.post("/gtt/advance", data={"lg": lid, "mode": "finish"}).status_code in (302, 303)
    hub = c.get(f"/gtt?lg={lid}")
    assert b"Champion" in hub.data and b"MVP" in hub.data


def test_gtt_dual_box_score(tmp_path):
    c = _client(tmp_path)
    lid = gs.create_league("L", seed=5, n_teams=4)
    c.post("/gtt/advance", data={"lg": lid})         # play week 1 on the full engine
    conn = gs._db()
    did = conn.execute("SELECT id FROM gtt_duals WHERE league_id=? AND status='final' LIMIT 1",
                       (lid,)).fetchone()["id"]
    conn.close()
    page = c.get(f"/gtt/dual/{did}?lg={lid}")
    assert page.status_code == 200
    assert b"Aces" in page.data and b"Service Points Won" in page.data   # ATP-style stats
    assert b"/gtt/player/" in page.data and b"/gtt/franchise/" in page.data  # player + team links


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
    # Assert on what the page ACTUALLY renders. This used to look for "Match log"
    # and "GTT MVP", neither of which has existed in gtt_player.html for a while —
    # the template was reworked and the test kept passing a stale expectation until
    # it didn't. The season-by-season career table is the page's real spine.
    assert page.status_code == 200
    body = page.data
    assert b"Career &mdash; by season" in body or b"Career \xe2\x80\x94 by season" in body \
        or b"by season" in body, "the career table is missing"
    assert bytes(gs.player_detail(lid, pid)["name"], "utf-8") in body


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


def test_clubless_player_page_renders(tmp_path):
    """A player with no club carries fid=NULL — free agents AND every retired
    player (retirement nulls the fid). The franchise back-link used to call
    url_for with that None, which raised BuildError and 500'd the page; since the
    Hall of Fame links straight to these pages, every enshrined player was a 500."""
    c = _client(tmp_path)
    lid = gs.create_league("Clubless", seed=5, n_teams=4)
    conn = gs._db()
    row = conn.execute("SELECT pid FROM gtt_players WHERE league_id=? LIMIT 1",
                       (lid,)).fetchone()
    pid = row["pid"]
    for status in ("active", "retired"):          # free agent, then retired
        conn.execute("UPDATE gtt_players SET fid=NULL, status=? WHERE league_id=? AND pid=?",
                     (status, lid, pid))
        conn.commit()
        r = c.get(f"/gtt/player/{pid}?lg={lid}")
        assert r.status_code == 200, f"{status} clubless player 500'd"
        assert b"Retired" in r.data if status == "retired" else b"Free agent" in r.data
    conn.close()
