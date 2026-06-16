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
CREATE TABLE IF NOT EXISTS coach_history (
  coach_id TEXT, year INTEGER, season_no INTEGER,
  division TEXT, gender TEXT, school TEXT, role TEXT,
  wins INTEGER, losses INTEGER,
  PRIMARY KEY (coach_id, year, division, gender, school, role)
);
CREATE INDEX IF NOT EXISTS idx_coachhist_cid ON coach_history(coach_id);
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


def ensure_seat(division: str, gender: str, school: str, role: str,
                *, name: str, home_country: str, archetype: str,
                dev: float, rec: float, tac: float, tenure: int) -> dict:
    """Return the coach record holding this seat — the PERSISTED entity, which is
    authoritative (so a coach who has moved here shows correctly rather than a
    freshly-generated one). Creates the entity on first sight."""
    conn = _conn()
    seat = conn.execute(
        "SELECT coach_id, tenure FROM coach_seat WHERE division=? AND gender=? AND school=? AND role=?",
        (division, gender, school, role)).fetchone()
    if seat:
        c = conn.execute("SELECT * FROM coach WHERE coach_id=?", (seat["coach_id"],)).fetchone()
        conn.close()
        rec_ = dict(c)
        rec_["tenure"] = seat["tenure"]
        return rec_
    cid = uuid.uuid4().hex[:12]
    conn.execute("INSERT OR IGNORE INTO coach (coach_id, name, home_country, archetype, dev, rec, tac)"
                 " VALUES (?,?,?,?,?,?,?)", (cid, name, home_country, archetype, dev, rec, tac))
    conn.execute("INSERT OR REPLACE INTO coach_seat (division, gender, school, role, coach_id, tenure)"
                 " VALUES (?,?,?,?,?,?)", (division, gender, school, role, cid, tenure))
    conn.commit()
    conn.close()
    return {"coach_id": cid, "name": name, "home_country": home_country,
            "archetype": archetype, "dev": dev, "rec": rec, "tac": tac, "tenure": tenure}


def seat_coach_id(division: str, gender: str, school: str, role: str, **kw) -> str:
    return ensure_seat(division, gender, school, role, **kw)["coach_id"]


def head_seats(division: str, gender: str) -> dict:
    """{school: coach_id} for every registered head seat in a universe."""
    conn = _conn()
    rows = conn.execute(
        "SELECT school, coach_id FROM coach_seat WHERE division=? AND gender=? AND role='head'",
        (division, gender)).fetchall()
    conn.close()
    return {r["school"]: r["coach_id"] for r in rows}


def record_season(coach_id: str, year: int, season_no: int, division: str, gender: str,
                  school: str, role: str, wins: int, losses: int) -> None:
    """Stamp one concluded season onto a coach's history — the seat they held and
    that team's final record. Idempotent (re-finalizing a year overwrites). A
    coach's *career* wins count only their HEAD-coach seasons (assistants don't
    bank wins until they run a program); the row is stored for every role so the
    table can still show where an assistant served."""
    conn = _conn()
    conn.execute("INSERT OR REPLACE INTO coach_history (coach_id, year, season_no,"
                 " division, gender, school, role, wins, losses) VALUES (?,?,?,?,?,?,?,?,?)",
                 (coach_id, year, season_no, division, gender, school, role, wins, losses))
    conn.commit()
    conn.close()


def history(coach_id: str) -> list[dict]:
    """A coach's recorded seasons, newest year first."""
    conn = _conn()
    rows = conn.execute("SELECT * FROM coach_history WHERE coach_id=? ORDER BY year DESC, role",
                        (coach_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def swap_seats(g1: str, d1: str, s1: str, r1: str,
               g2: str, d2: str, s2: str, r2: str) -> bool:
    """Swap the coaches holding two seats (any role, possibly across divisions),
    resetting both tenures to 1. Both seats must already exist. The god-mode
    editor primitive — every seat stays filled, so no coach is orphaned."""
    conn = _conn()
    a = conn.execute("SELECT coach_id FROM coach_seat WHERE division=? AND gender=? AND school=? AND role=?",
                     (d1, g1, s1, r1)).fetchone()
    b = conn.execute("SELECT coach_id FROM coach_seat WHERE division=? AND gender=? AND school=? AND role=?",
                     (d2, g2, s2, r2)).fetchone()
    if not a or not b:
        conn.close()
        return False
    conn.execute("UPDATE coach_seat SET coach_id=?, tenure=1 WHERE division=? AND gender=? AND school=? AND role=?",
                 (b["coach_id"], d1, g1, s1, r1))
    conn.execute("UPDATE coach_seat SET coach_id=?, tenure=1 WHERE division=? AND gender=? AND school=? AND role=?",
                 (a["coach_id"], d2, g2, s2, r2))
    conn.commit()
    conn.close()
    return True


def swap_head_coaches(g: str, d1: str, s1: str, d2: str, s2: str) -> None:
    """Swap the head coaches of two programs (possibly across divisions) and
    reset both tenures to 1. Both head seats must already exist."""
    conn = _conn()
    a = conn.execute("SELECT coach_id FROM coach_seat WHERE division=? AND gender=? AND school=? AND role='head'",
                     (d1, g, s1)).fetchone()
    b = conn.execute("SELECT coach_id FROM coach_seat WHERE division=? AND gender=? AND school=? AND role='head'",
                     (d2, g, s2)).fetchone()
    if not a or not b:
        conn.close()
        return
    conn.execute("UPDATE coach_seat SET coach_id=?, tenure=1 WHERE division=? AND gender=? AND school=? AND role='head'",
                 (b["coach_id"], d1, g, s1))
    conn.execute("UPDATE coach_seat SET coach_id=?, tenure=1 WHERE division=? AND gender=? AND school=? AND role='head'",
                 (a["coach_id"], d2, g, s2))
    conn.commit()
    conn.close()


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
    conn.executescript("DELETE FROM coach_seat; DELETE FROM coach; DELETE FROM coach_history;")
    conn.commit()
    conn.close()
