"""The season-row backfill must never hold the write lock across a fold.

A `_SEASON_ROW_VERSION` bump re-folds EVERY archived season on the first
program page opened. It used to do that inside one write transaction
(opened at the first season's DELETE, committed after the last), so another
writer on the file waited out its busy timeout and the program page 500'd
with "database is locked". Each season is now folded with no transaction open
and committed on its own."""
import json
import sqlite3

import app.world as wd


def _seed(world_id, gender, years):
    conn = wd._db()
    try:
        conn.execute("DELETE FROM world_jhsaa WHERE world_id=?", (world_id,))
        conn.execute("DELETE FROM world_jhsaa_season_row WHERE world_id=?", (world_id,))
        conn.executemany("INSERT INTO world_jhsaa (world_id, year, gender, data)"
                         " VALUES (?,?,?,?)",
                         [(world_id, y, gender, json.dumps({})) for y in years])
        conn.commit()
    finally:
        conn.close()


def test_no_fold_runs_inside_a_write_and_other_writers_get_in(monkeypatch):
    world_id, gender, years = 987654, "girls", [3, 4, 5]
    _seed(world_id, gender, years)
    seen = []

    def fake_fold(conn, wid, year, g):
        # The backfill's own connection holds no write transaction...
        assert not conn.in_transaction
        # ...so a different connection can take the write lock right now,
        # without waiting at all.
        other = sqlite3.connect(wd.WORLD_DB, timeout=0)
        try:
            other.execute("BEGIN IMMEDIATE")
            other.rollback()
        finally:
            other.close()
        seen.append(year)
        return {"Alpha": {"year": year}}

    monkeypatch.setattr(wd, "_fold_season_rows", fake_fold)
    conn = wd._db()
    try:
        wd._ensure_season_rows(conn, world_id, gender)
        assert not conn.in_transaction
        stored = conn.execute(
            "SELECT year, v FROM world_jhsaa_season_row WHERE world_id=?"
            " ORDER BY year", (world_id,)).fetchall()
    finally:
        conn.close()
    assert sorted(seen) == years
    assert [(r["year"], r["v"]) for r in stored] == [
        (y, wd._SEASON_ROW_VERSION) for y in years]

    # Current rows are never re-folded.
    seen.clear()
    conn = wd._db()
    try:
        wd._ensure_season_rows(conn, world_id, gender)
    finally:
        conn.close()
    assert seen == []
