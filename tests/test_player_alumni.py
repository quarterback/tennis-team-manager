"""Archive links must not 404: a player who is no longer on any current roster
(graduated, moved on) but persists in the world store renders a historical player
page — past singles/doubles champions and Hall of Fame honorees stay clickable."""
import json
import os
import random
import tempfile

os.environ.setdefault("TENNIS_DB_PATH", tempfile.mktemp(suffix="-alumni.db"))

from app.development import generate_prospect


def test_player_page_hydrates_persisted_alumni(tmp_path):
    import app.seasonmode as sm
    import app.world as world
    prev_sm, prev_w, prev_ready = sm.DB_PATH, world.WORLD_DB, world._schema_ready_for
    sm.DB_PATH = world.WORLD_DB = str(tmp_path / "a.db")
    world._schema_ready_for = None
    try:
        conn = world._db()
        conn.execute("INSERT INTO world (seed, year, week) VALUES (2026, 1, 0)")
        wid = conn.execute("SELECT id FROM world WHERE seed=2026").fetchone()["id"]
        # A graduate: persisted on LAST year's roster (year 0) while the world is in
        # year 1 — absent from every current-season roster, like a past champion.
        p = generate_prospect(random.Random(7), "Grad Champion", "US",
                              gender="male", talent=60)
        p.class_year = "Sr"
        p.history = [{"year": 0, "school": "Old State", "division": "D1", "class": "Sr",
                      "w": 20, "l": 2, "str": 61.0, "line": "S1", "season_no": 1}]
        conn.execute("INSERT INTO world_roster VALUES (?,?,?,?,?,?,?)",
                     (wid, 0, "D1", "men", "Old State", p.pid,
                      json.dumps(world.prospect_to_dict(p))))
        conn.commit()
        conn.close()

        import time
        from app.web.server import create_app
        c = create_app().test_client()
        # early hits can get the boot-warm "loading…" splash while the world primes
        # in the background — poll until the real page renders
        body = ""
        for _ in range(60):
            r = c.get(f"/player/{p.pid}?u=D1-men")
            body = r.get_data(as_text=True)
            if "loading…" not in body:
                break
            time.sleep(0.5)
        assert r.status_code == 200
        assert "Grad Champion" in body          # hydrated from the persisted store
        assert "Old State" in body              # career history renders
        # a pid that exists nowhere still 404s
        assert c.get("/player/nope-xyz?u=D1-men").status_code == 404
    finally:
        sm.DB_PATH, world.WORLD_DB, world._schema_ready_for = prev_sm, prev_w, prev_ready
