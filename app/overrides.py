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


def clear_all() -> None:
    conn = _db()
    conn.execute("DELETE FROM roster_overrides")
    conn.commit(); conn.close()


def any_overrides() -> bool:
    conn = _db()
    n = conn.execute("SELECT COUNT(*) FROM roster_overrides").fetchone()[0]
    conn.close()
    return n > 0
