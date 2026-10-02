"""The season-row backfill must never hold the write lock across a fold.

A `_SEASON_ROW_VERSION` bump re-folds EVERY archived season on the first
program page opened. It used to do that inside one write transaction
(opened at the first season's DELETE, committed after the last), so another
writer on the file waited out its busy timeout and the program page 500'd
with "database is locked". Each season is now folded with no transaction open
and committed on its own."""
import json
import sqlite3
import threading

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


class _RecordingLock:
    """A real lock that logs every acquire/release, so the test can SEE where
    the refold holds it and where it lets go."""

    def __init__(self, log):
        self._lock = threading.Lock()
        self._log = log

    def __enter__(self):
        self._lock.acquire()
        self._log.append("acquire")

    def __exit__(self, *exc):
        self._log.append("release")
        self._lock.release()


def _seed_stale(world_id, gender, years, v):
    _seed(world_id, gender, years)
    conn = wd._db()
    try:
        conn.executemany(
            "INSERT INTO world_jhsaa_season_row (world_id, year, gender, school, v, data)"
            " VALUES (?,?,?,?,?,?)",
            [(world_id, y, gender, "Alpha", v, json.dumps({"year": y, "v": "old"}))
             for y in years])
        conn.commit()
    finally:
        conn.close()


def test_the_background_refold_releases_the_lock_between_seasons(monkeypatch):
    """Held across the whole loop, every same-gender request waited out a
    refold that takes minutes on a long save — the stale rows a reader is
    meant to be served meanwhile sat behind that very lock."""
    world_id, gender, years = 987655, "boys", [1, 2, 3]
    _seed_stale(world_id, gender, years, wd._SEASON_ROW_VERSION - 1)
    log = []
    key = (wd.WORLD_DB, world_id, gender)
    monkeypatch.setitem(wd._season_row_locks, key, _RecordingLock(log))

    def fake_fold(conn, wid, year, g):
        log.append(("fold", year))
        return {"Alpha": {"year": year}}
    monkeypatch.setattr(wd, "_fold_season_rows", fake_fold)

    wd._refold_stale_rows(world_id, gender, years)
    assert log == ["acquire", ("fold", 1), "release",
                   "acquire", ("fold", 2), "release",
                   "acquire", ("fold", 3), "release"]


def test_a_page_read_serves_stale_rows_while_an_export_waits_for_current_ones(monkeypatch):
    """The program page shows last version's rows and re-derives them off the
    request thread; the research export (and so the Clinch Report, which
    caches its zip) must never package a row at an older version."""
    world_id, gender, years = 987656, "girls", [7, 8]
    _seed_stale(world_id, gender, years, wd._SEASON_ROW_VERSION - 1)
    folded = []

    def fake_fold(conn, wid, year, g):
        folded.append(year)
        return {"Alpha": {"year": year, "v": "new"}}
    monkeypatch.setattr(wd, "_fold_season_rows", fake_fold)
    # Keep the background refold from running so the inline behaviour is
    # observable on its own.
    monkeypatch.setattr(wd, "_refolding", {(wd.WORLD_DB, world_id, gender)})

    conn = wd._db()
    try:
        wd._ensure_season_rows(conn, world_id, gender)            # a page read
        assert folded == []                                        # served as is
        stored = {r["year"]: r["v"] for r in conn.execute(
            "SELECT year, v FROM world_jhsaa_season_row WHERE world_id=?",
            (world_id,)).fetchall()}
        assert stored == {y: wd._SEASON_ROW_VERSION - 1 for y in years}
    finally:
        conn.close()

    rows = wd.jhsaa_history_rows(world_id, gender)                 # an export
    assert sorted(folded) == years
    assert all(r["v"] == "new" for r in rows["Alpha"])
    conn = wd._db()
    try:
        stored = {r["year"]: r["v"] for r in conn.execute(
            "SELECT year, v FROM world_jhsaa_season_row WHERE world_id=?",
            (world_id,)).fetchall()}
    finally:
        conn.close()
    assert stored == {y: wd._SEASON_ROW_VERSION for y in years}
