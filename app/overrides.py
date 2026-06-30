"""
Roster overrides — the editor's persistence layer.

Lets you (for testing) move a player to ANY program in ANY division, and set a
team's lineup order. Stored in the same SQLite DB. `ncaa.build_roster` applies
these on top of the deterministic base rosters, so the dual simulator, team
pages, and new season sims all reflect your edits — e.g. drop a great D1 player
onto a D3 roster and watch what happens.
"""
from __future__ import annotations

import json
import sqlite3

from . import dbpath
from .dbpath import resolve_db_path

DB_PATH = resolve_db_path()   # volume path if writable, else a local fallback

_SCHEMA = """
CREATE TABLE IF NOT EXISTS roster_overrides (
  kind TEXT, key TEXT, value TEXT, PRIMARY KEY (kind, key)
);
CREATE TABLE IF NOT EXISTS fall_portal (
  year INTEGER, gender TEXT, pid TEXT,
  src_school TEXT, dest_school TEXT, src_div TEXT, dest_div TEXT,
  str REAL, status TEXT,
  ita_w INTEGER, ita_l INTEGER, ita_line TEXT,
  cascade_from TEXT,
  PRIMARY KEY (year, gender, pid)
);
CREATE TABLE IF NOT EXISTS preseason_portal (
  year INTEGER, gender TEXT, pid TEXT,
  src_school TEXT, dest_school TEXT, src_div TEXT, dest_div TEXT,
  str REAL, status TEXT, cascade_from TEXT, name TEXT,
  PRIMARY KEY (year, gender, pid)
);
"""

_schema_ready_for = None        # the DB_PATH the schema was last created for


def init_schema() -> None:
    """Create the schema eagerly with a short-lived, auto-committing connection.
    Call this at startup BEFORE any long write transaction so the lazy path in
    `_db()` never has to write (which would deadlock against a held sim lock)."""
    global _schema_ready_for
    conn = dbpath.connect(DB_PATH, row=False)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    _schema_ready_for = DB_PATH


def _db():
    """Tuned connection. Schema is created once per (path), not on every call,
    so read helpers don't take a write lock while a sim holds one open."""
    if _schema_ready_for != DB_PATH:
        init_schema()
    return dbpath.connect(DB_PATH, row=False)


def _retry_locked(fn, *, tries: int = 6, delay: float = 0.3):
    """Retry a DB op on a transient 'database is locked' (busy_timeout already
    WAITS on normal contention; this backstops the rare overrun under heavy load)."""
    import time
    for attempt in range(tries):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower() or attempt == tries - 1:
                raise
            time.sleep(delay * (attempt + 1))


def roster_version() -> str:
    """Cheap fingerprint of the roster-affecting overrides — transfers (`move`)
    and pinned lineups (`lineup`). Changes the instant such an edit lands,
    INCLUDING the fall-portal commit, so caches keyed on it refresh without
    waiting for a week tick (a fall-portal commit changes per-season phase but
    not the world week, so a week-only stamp would serve stale rosters). Prestige
    / academic overrides are excluded: they only shift at the year rollover, which
    already bumps the world year. The table is tiny, so hashing it per call is
    negligible next to the scan/prime it guards."""
    import hashlib
    conn = _db()
    rows = conn.execute(
        "SELECT kind, key, value FROM roster_overrides"
        " WHERE kind IN ('move','lineup') ORDER BY kind, key").fetchall()
    conn.close()
    h = hashlib.md5()
    for r in rows:
        h.update(repr(tuple(r)).encode())
    return h.hexdigest()


def get_moves() -> dict:
    """pid -> destination school."""
    conn = _db()
    rows = conn.execute("SELECT key, value FROM roster_overrides WHERE kind='move'").fetchall()
    conn.close()
    return {k: v for k, v in rows}


def get_lineups() -> dict:
    """school -> ordered list of pids (front of the lineup)."""
    conn = _db()
    rows = conn.execute("SELECT key, value FROM roster_overrides WHERE kind='lineup'").fetchall()
    conn.close()
    return {k: json.loads(v) for k, v in rows}


def set_move(pid: str, dest_school: str) -> None:
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO roster_overrides (kind, key, value) VALUES ('move',?,?)",
                 (pid, dest_school))
    conn.commit(); conn.close()


def clear_move(pid: str) -> None:
    conn = _db()
    conn.execute("DELETE FROM roster_overrides WHERE kind='move' AND key=?", (pid,))
    conn.commit(); conn.close()


def set_lineup(school: str, pids: list[str]) -> None:
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO roster_overrides (kind, key, value) VALUES ('lineup',?,?)",
                 (school, json.dumps(pids)))
    conn.commit(); conn.close()


def clear_lineup(school: str) -> None:
    conn = _db()
    conn.execute("DELETE FROM roster_overrides WHERE kind='lineup' AND key=?", (school,))
    conn.commit(); conn.close()


def get_prestige() -> dict:
    """school -> overridden prestige (0..1)."""
    conn = _db()
    rows = conn.execute("SELECT key, value FROM roster_overrides WHERE kind='prestige'").fetchall()
    conn.close()
    out = {}
    for k, v in rows:
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            pass
    return out


def set_prestige(school: str, prestige: float) -> None:
    prestige = max(0.0, min(1.0, float(prestige)))
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO roster_overrides (kind, key, value) VALUES ('prestige',?,?)",
                 (school, f"{prestige:.4f}"))
    conn.commit(); conn.close()


def clear_prestige(school: str) -> None:
    conn = _db()
    conn.execute("DELETE FROM roster_overrides WHERE kind='prestige' AND key=?", (school,))
    conn.commit(); conn.close()


# --- Dynamic prestige momentum (YoY drift from on-court overperformance) ------
# A SIGNED per-(school, gender) delta, distinct from the absolute editor override
# above. The world rollover recomputes it each year; load_division adds it to the
# base prestige (clamped to the division band). Keyed "school|gender".

def get_prestige_momentum() -> dict:
    """{(school, gender): signed momentum} — dynamic YoY prestige drift."""
    conn = _db()
    rows = conn.execute("SELECT key, value FROM roster_overrides WHERE kind='prestige_dyn'").fetchall()
    conn.close()
    out = {}
    for k, v in rows:
        try:
            school, gender = k.rsplit("|", 1)
            out[(school, gender)] = float(v)
        except (TypeError, ValueError):
            pass
    return out


def set_prestige_momentum_batch(items: dict) -> None:
    """Persist {(school, gender): momentum} in one transaction (rollover writes all)."""
    if not items:
        return
    conn = _db()
    conn.executemany(
        "INSERT OR REPLACE INTO roster_overrides (kind, key, value) VALUES ('prestige_dyn',?,?)",
        [(f"{s}|{g}", f"{float(m):.4f}") for (s, g), m in items.items()])
    conn.commit(); conn.close()


# --------------------------------------------------------------------------
# Academics + conference-level ratings — the rest of the recruiting levers.
#   kind='academics'      key=school  → overridden academic profile (0..1)
#   kind='conf_prestige'  key=conf    → overridden conference prestige prior
#   kind='conf_academics' key=conf    → overridden conference academic prior
# All are stored on the same [0,1] scale as the base priors in ncaa.py.
# --------------------------------------------------------------------------
def _get_floats(kind: str) -> dict:
    conn = _db()
    rows = conn.execute("SELECT key, value FROM roster_overrides WHERE kind=?", (kind,)).fetchall()
    conn.close()
    out = {}
    for k, v in rows:
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            pass
    return out


def _set_float(kind: str, key: str, value: float) -> None:
    value = max(0.0, min(1.0, float(value)))
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO roster_overrides (kind, key, value) VALUES (?,?,?)",
                 (kind, key, f"{value:.4f}"))
    conn.commit(); conn.close()


def _clear(kind: str, key: str) -> None:
    conn = _db()
    conn.execute("DELETE FROM roster_overrides WHERE kind=? AND key=?", (kind, key))
    conn.commit(); conn.close()


def get_academics() -> dict:
    """school -> overridden academic profile (0..1)."""
    return _get_floats("academics")


def set_academics(school: str, academics: float) -> None:
    _set_float("academics", school, academics)


def clear_academics(school: str) -> None:
    _clear("academics", school)


def get_conf_prestige() -> dict:
    """conference name -> overridden prestige prior (0..1)."""
    return _get_floats("conf_prestige")


def set_conf_prestige(conf: str, prior: float) -> None:
    _set_float("conf_prestige", conf, prior)


def clear_conf_prestige(conf: str) -> None:
    _clear("conf_prestige", conf)


def get_conf_academics() -> dict:
    """conference name -> overridden academic prior (0..1)."""
    return _get_floats("conf_academics")


def set_conf_academics(conf: str, prior: float) -> None:
    _set_float("conf_academics", conf, prior)


def clear_conf_academics(conf: str) -> None:
    _clear("conf_academics", conf)


# --------------------------------------------------------------------------
# Fall transfer portal — the post-ITA talent reshuffle. Proposals are generated
# by the sim (status='proposed'), the user approves/removes them, and a commit
# pass relocates the approved movers (via set_move) and flips them to
# 'committed'. Distinct from `kind='move'` (the always-on editor relocation) so
# the year-end history pass knows which movers earned a two-stint season record.
# --------------------------------------------------------------------------
_FP_COLS = ("year", "gender", "pid", "src_school", "dest_school", "src_div",
            "dest_div", "str", "status", "ita_w", "ita_l", "ita_line", "cascade_from")


def _fp_row(r) -> dict:
    return dict(zip(_FP_COLS, r))


def set_proposals(year: int, gender: str, rows: list[dict]) -> None:
    """Replace this (year, gender) slate with a fresh set of 'proposed' rows."""
    def _do():
        conn = _db()
        try:
            conn.execute("DELETE FROM fall_portal WHERE year=? AND gender=?", (year, gender))
            conn.executemany(
                "INSERT INTO fall_portal (year,gender,pid,src_school,dest_school,src_div,"
                "dest_div,str,status,ita_w,ita_l,ita_line,cascade_from)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(year, gender, r["pid"], r["src_school"], r["dest_school"], r["src_div"],
                  r["dest_div"], float(r.get("str", 0.0)), r.get("status", "proposed"),
                  int(r.get("ita_w", 0)), int(r.get("ita_l", 0)),
                  (None if r.get("ita_line") is None else str(r["ita_line"])),
                  r.get("cascade_from")) for r in rows])
            conn.commit()
        finally:
            conn.close()
    _retry_locked(_do)


def get_proposals(year: int, status: str | None = None) -> list[dict]:
    """All fall-portal rows for a year (optionally filtered by status), strongest
    riser first."""
    conn = _db()
    if status is None:
        rows = conn.execute("SELECT year,gender,pid,src_school,dest_school,src_div,"
                            "dest_div,str,status,ita_w,ita_l,ita_line,cascade_from"
                            " FROM fall_portal WHERE year=? ORDER BY str DESC", (year,)).fetchall()
    else:
        rows = conn.execute("SELECT year,gender,pid,src_school,dest_school,src_div,"
                            "dest_div,str,status,ita_w,ita_l,ita_line,cascade_from"
                            " FROM fall_portal WHERE year=? AND status=? ORDER BY str DESC",
                            (year, status)).fetchall()
    conn.close()
    return [_fp_row(r) for r in rows]


def upsert_proposal(year: int, gender: str, r: dict) -> None:
    """Insert or replace a single rider intent (used when the user ADDS a mover)."""
    def _do():
        conn = _db()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO fall_portal (year,gender,pid,src_school,dest_school,"
                "src_div,dest_div,str,status,ita_w,ita_l,ita_line,cascade_from)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (year, gender, r["pid"], r["src_school"], r["dest_school"], r["src_div"],
                 r["dest_div"], float(r.get("str", 0.0)), r.get("status", "proposed"),
                 int(r.get("ita_w", 0)), int(r.get("ita_l", 0)),
                 (None if r.get("ita_line") is None else str(r["ita_line"])),
                 r.get("cascade_from")))
            conn.commit()
        finally:
            conn.close()
    _retry_locked(_do)


def set_dest(year: int, gender: str, pid: str, dest_school: str, dest_div: str) -> None:
    """Redirect a rider to a different destination (the cascade re-derives at resolve)."""
    def _do():
        conn = _db()
        try:
            conn.execute("UPDATE fall_portal SET dest_school=?, dest_div=?"
                         " WHERE year=? AND gender=? AND pid=?",
                         (dest_school, dest_div, year, gender, pid))
            conn.commit()
        finally:
            conn.close()
    _retry_locked(_do)


def delete_proposal(year: int, gender: str, pid: str) -> None:
    def _do():
        conn = _db()
        try:
            conn.execute("DELETE FROM fall_portal WHERE year=? AND gender=? AND pid=?",
                         (year, gender, pid))
            conn.commit()
        finally:
            conn.close()
    _retry_locked(_do)


def set_status(year: int, gender: str, pid: str, status: str) -> None:
    def _do():
        conn = _db()
        try:
            conn.execute("UPDATE fall_portal SET status=? WHERE year=? AND gender=? AND pid=?",
                         (status, year, gender, pid))
            conn.commit()
        finally:
            conn.close()
    _retry_locked(_do)


def committed_movers(year: int) -> set:
    """pids that fall-transferred (committed) this year — drives the two-stint
    history record at rollover."""
    conn = _db()
    rows = conn.execute("SELECT pid FROM fall_portal WHERE year=? AND status='committed'",
                        (year,)).fetchall()
    conn.close()
    return {r[0] for r in rows}


def clear_year(year: int) -> None:
    conn = _db()
    conn.execute("DELETE FROM fall_portal WHERE year=?", (year,))
    conn.commit(); conn.close()


# --------------------------------------------------------------------------
# Pre-season portal — the week-0 misallocation reshuffle. Same shape as the fall
# portal (sim proposes risers, user edits, commit relocates via set_move), but it
# runs BEFORE the season opens, so there's no ITA stint and no two-stint history:
# a committed mover simply starts the year at their new school (a plain relocation).
# Stored in its own table so it never collides with the post-NIT fall portal.
# --------------------------------------------------------------------------
_PS_COLS = ("year", "gender", "pid", "src_school", "dest_school", "src_div",
            "dest_div", "str", "status", "cascade_from", "name")


def _ps_row(r) -> dict:
    return dict(zip(_PS_COLS, r))


_PS_SELECT = ("SELECT year,gender,pid,src_school,dest_school,src_div,dest_div,"
              "str,status,cascade_from,name FROM preseason_portal")


def ps_set_proposals(year: int, gender: str, rows: list[dict]) -> None:
    """Replace this (year, gender) pre-season slate with a fresh 'proposed' set."""
    def _do():
        conn = _db()
        try:
            conn.execute("DELETE FROM preseason_portal WHERE year=? AND gender=?", (year, gender))
            conn.executemany(
                "INSERT INTO preseason_portal (year,gender,pid,src_school,dest_school,"
                "src_div,dest_div,str,status,cascade_from,name) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(year, gender, r["pid"], r["src_school"], r["dest_school"], r["src_div"],
                  r["dest_div"], float(r.get("str", 0.0)), r.get("status", "proposed"),
                  r.get("cascade_from"), r.get("name", "")) for r in rows])
            conn.commit()
        finally:
            conn.close()
    _retry_locked(_do)


def ps_get_proposals(year: int, status: str | None = None) -> list[dict]:
    """All pre-season-portal rows for a year (optionally by status), strongest first."""
    conn = _db()
    if status is None:
        rows = conn.execute(_PS_SELECT + " WHERE year=? ORDER BY str DESC", (year,)).fetchall()
    else:
        rows = conn.execute(_PS_SELECT + " WHERE year=? AND status=? ORDER BY str DESC",
                            (year, status)).fetchall()
    conn.close()
    return [_ps_row(r) for r in rows]


def ps_upsert_proposal(year: int, gender: str, r: dict) -> None:
    """Insert or replace a single rider intent (used when the user ADDS a mover)."""
    def _do():
        conn = _db()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO preseason_portal (year,gender,pid,src_school,"
                "dest_school,src_div,dest_div,str,status,cascade_from,name)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (year, gender, r["pid"], r["src_school"], r["dest_school"], r["src_div"],
                 r["dest_div"], float(r.get("str", 0.0)), r.get("status", "proposed"),
                 r.get("cascade_from"), r.get("name", "")))
            conn.commit()
        finally:
            conn.close()
    _retry_locked(_do)


def ps_set_dest(year: int, gender: str, pid: str, dest_school: str, dest_div: str) -> None:
    """Redirect a rider to a different destination (the cascade re-derives at resolve)."""
    def _do():
        conn = _db()
        try:
            conn.execute("UPDATE preseason_portal SET dest_school=?, dest_div=?"
                         " WHERE year=? AND gender=? AND pid=?",
                         (dest_school, dest_div, year, gender, pid))
            conn.commit()
        finally:
            conn.close()
    _retry_locked(_do)


def ps_set_status(year: int, gender: str, pid: str, status: str) -> None:
    def _do():
        conn = _db()
        try:
            conn.execute("UPDATE preseason_portal SET status=? WHERE year=? AND gender=? AND pid=?",
                         (status, year, gender, pid))
            conn.commit()
        finally:
            conn.close()
    _retry_locked(_do)


def ps_clear_year(year: int) -> None:
    conn = _db()
    conn.execute("DELETE FROM preseason_portal WHERE year=?", (year,))
    conn.commit(); conn.close()


def clear_all() -> None:
    conn = _db()
    conn.execute("DELETE FROM roster_overrides")
    conn.execute("DELETE FROM fall_portal")
    conn.execute("DELETE FROM preseason_portal")
    conn.commit(); conn.close()


def any_overrides() -> bool:
    conn = _db()
    n = conn.execute("SELECT COUNT(*) FROM roster_overrides").fetchone()[0]
    conn.close()
    return n > 0
