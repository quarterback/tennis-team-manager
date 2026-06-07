"""Player persistence: the schema now stores origins + scholarships, and a
generated prospect round-trips through the DB without losing them."""
import random

from app import db
from app.development import generate_prospect


def test_schema_has_origin_columns(tmp_path):
    path = str(tmp_path / "t.db")
    db.init_db(path)
    conn = db.connect(path)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(players)")}
    conn.close()
    for c in ("pid", "hometown", "high_school", "birthday", "major",
              "secondary_country", "academic_rating", "scholarship", "walk_on",
              "school", "division", "class_year"):
        assert c in cols


def test_prospect_round_trip(tmp_path):
    path = str(tmp_path / "t.db")
    db.init_db(path)
    rng = random.Random(7)
    pr = generate_prospect(rng, "Test Player", "US", gender="male", talent=60.0)
    pr.class_year = "Jr"
    pr.scholarship = 0.5
    pr.walk_on = False

    conn = db.connect(path)
    db.save_prospect(conn, pr, school="Test U", division="D1")
    conn.commit()
    conn.close()

    conn = db.connect(path)
    row = db.load_player_row(conn, pr.pid)
    conn.close()

    assert row is not None
    assert row["name"] == "Test Player"
    assert row["hometown"] == pr.hometown and pr.hometown   # non-empty + preserved
    assert row["major"] == pr.major
    assert row["birthday"] == pr.birthday
    assert row["high_school"] == pr.high_school
    assert row["academic_rating"] == pr.academic_rating
    assert row["scholarship"] == 0.5
    assert row["walk_on"] == 0
    assert row["school"] == "Test U" and row["division"] == "D1"
    assert row["class_year"] == "Jr"


def test_save_is_idempotent_upsert(tmp_path):
    path = str(tmp_path / "t.db")
    db.init_db(path)
    rng = random.Random(11)
    pr = generate_prospect(rng, "Up Sert", "FR", gender="male", talent=55.0)
    conn = db.connect(path)
    db.save_prospect(conn, pr, school="A", division="D1")
    pr.scholarship = 1.0
    db.save_prospect(conn, pr, school="B", division="D2")   # same pid → update
    conn.commit()
    n = conn.execute("SELECT COUNT(*) AS c FROM players").fetchone()["c"]
    row = db.load_player_row(conn, pr.pid)
    conn.close()
    assert n == 1                       # upserted, not duplicated
    assert row["school"] == "B" and row["scholarship"] == 1.0


def test_migration_backfills_old_table(tmp_path):
    """An older players table (no origin cols) gets the columns added."""
    path = str(tmp_path / "old.db")
    conn = db.connect(path)
    conn.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, name TEXT, country TEXT)")
    conn.commit()
    conn.close()

    db.init_db(path)                    # should ALTER in the missing columns
    conn = db.connect(path)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(players)")}
    conn.close()
    assert {"pid", "hometown", "scholarship", "walk_on"} <= cols
