"""Coach identity registry — coaches are persisted entities with their own
stable id (like a player's pid), not values regenerated from a school. A coach
holds a *seat* (division, gender, school, role); the id is intrinsic, so when a
coach changes seats their honors (keyed to the id) follow them. Seats are
assigned once on first sight and read from the store thereafter.

(Coach free-agent *movement* — reassigning seats at year rollover — is the next
step; the schema already supports it since the id is independent of the seat.)
"""
from __future__ import annotations

import sqlite3
import uuid

from app.db import connect

_SCHEMA = """
CREATE TABLE IF NOT EXISTS coach (
  coach_id     TEXT PRIMARY KEY,
  name         TEXT,
  home_country TEXT,
  archetype    TEXT,
  dev          REAL,
  rec          REAL,
  tac          REAL
);
CREATE TABLE IF NOT EXISTS coach_seat (
  division TEXT, gender TEXT, school TEXT, role TEXT,
  coach_id TEXT, tenure INTEGER,
  PRIMARY KEY (division, gender, school, role)
);
CREATE INDEX IF NOT EXISTS idx_coachseat_cid ON coach_seat(coach_id);
"""

_ready = False


def init_schema() -> None:
    global _ready
    with connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _ready = True


def _conn() -> sqlite3.Connection:
    if not _ready:
        init_schema()
    return connect()


def seat_coach_id(division: str, gender: str, school: str, role: str,
                  *, name: str, home_country: str, archetype: str,
                  dev: float, rec: float, tac: float, tenure: int) -> str:
    """Return the stable coach_id holding this seat, creating the coach entity
    on first sight. Idempotent — later calls just read the existing id."""
    conn = _conn()
    row = conn.execute(
        "SELECT coach_id FROM coach_seat WHERE division=? AND gender=? AND school=? AND role=?",
        (division, gender, school, role)).fetchone()
    if row:
        conn.close()
        return row["coach_id"]
    cid = uuid.uuid4().hex[:12]
    conn.execute("INSERT OR IGNORE INTO coach (coach_id, name, home_country, archetype, dev, rec, tac)"
                 " VALUES (?,?,?,?,?,?,?)", (cid, name, home_country, archetype, dev, rec, tac))
    conn.execute("INSERT OR REPLACE INTO coach_seat (division, gender, school, role, coach_id, tenure)"
                 " VALUES (?,?,?,?,?,?)", (division, gender, school, role, cid, tenure))
    conn.commit()
    conn.close()
    return cid


def get(coach_id: str) -> dict | None:
    """Coach entity + current seat (division/gender/school/role/tenure)."""
    conn = _conn()
    c = conn.execute("SELECT * FROM coach WHERE coach_id=?", (coach_id,)).fetchone()
    if not c:
        conn.close()
        return None
    seat = conn.execute("SELECT * FROM coach_seat WHERE coach_id=? LIMIT 1", (coach_id,)).fetchone()
    conn.close()
    out = dict(c)
    if seat:
        out.update(division=seat["division"], gender=seat["gender"],
                   school=seat["school"], role=seat["role"], tenure=seat["tenure"])
    return out


def reset() -> None:
    conn = _conn()
    conn.executescript("DELETE FROM coach_seat; DELETE FROM coach;")
    conn.commit()
    conn.close()
