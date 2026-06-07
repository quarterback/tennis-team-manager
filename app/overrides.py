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
import os
import sqlite3

DB_PATH = os.environ.get("TENNIS_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "tennis.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS roster_overrides (
  kind TEXT, key TEXT, value TEXT, PRIMARY KEY (kind, key)
);
"""


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


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


def clear_all() -> None:
    conn = _db()
    conn.execute("DELETE FROM roster_overrides")
    conn.commit(); conn.close()


def any_overrides() -> bool:
    conn = _db()
    n = conn.execute("SELECT COUNT(*) FROM roster_overrides").fetchone()[0]
    conn.close()
    return n > 0
