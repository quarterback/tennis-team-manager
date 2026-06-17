"""Career honors — one flat table of awards stamped once and keyed to the
subject's stable id (player pid or coach id). Query by id == career; because
rows store the school *as of that season*, honors follow a player or coach
through transfers automatically. Nothing here recomputes — awards are stamped
at season end and never change.

Award keys (the `award` column groups by type; `label` is the display text):
  national_poty / conf_poty            Player of the Year (national / conference)
  national_coty / conf_coty            Coach of the Year  (national / conference)
  all_american / all_conference        team honors with a tier in `label`
  national_champion / conf_champion    team titles (credited to the whole roster + coach)
"""
from __future__ import annotations

import sqlite3

from app.db import connect

_SCHEMA = """
CREATE TABLE IF NOT EXISTS honors (
  subject_type TEXT NOT NULL,            -- 'player' | 'coach'
  subject_id   TEXT NOT NULL,
  name         TEXT,
  year         INTEGER NOT NULL,
  season_no    INTEGER,
  division     TEXT,
  gender       TEXT,
  school       TEXT,
  award        TEXT NOT NULL,
  label        TEXT,
  sort         REAL DEFAULT 0,           -- higher = more prestigious (ordering)
  PRIMARY KEY (subject_type, subject_id, year, award)
);
CREATE INDEX IF NOT EXISTS idx_honors_subject ON honors(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_honors_season ON honors(year, division, gender);
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


def stamp(records: list[dict]) -> int:
    """Write honor rows (idempotent on the PK so re-stamping a season is safe).
    Each record: subject_type, subject_id, name, year, season_no, division,
    gender, school, award, label, sort."""
    if not records:
        return 0
    conn = _conn()
    conn.executemany(
        "INSERT OR REPLACE INTO honors (subject_type, subject_id, name, year, "
        "season_no, division, gender, school, award, label, sort) "
        "VALUES (:subject_type, :subject_id, :name, :year, :season_no, :division, "
        ":gender, :school, :award, :label, :sort)",
        [{"season_no": None, "sort": 0, "name": None, "school": None,
          "division": None, "gender": None, **r} for r in records],
    )
    conn.commit()
    n = len(records)
    conn.close()
    return n


def clear_season(year: int, division: str, gender: str) -> None:
    """Drop a season's honors before re-stamping it (keeps re-finalize clean)."""
    conn = _conn()
    conn.execute("DELETE FROM honors WHERE year=? AND division=? AND gender=?",
                 (year, division, gender))
    conn.commit()
    conn.close()


def career(subject_id: str, subject_type: str = "player") -> list[dict]:
    """Every honor for one subject, newest year first then most prestigious."""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM honors WHERE subject_type=? AND subject_id=? "
        "ORDER BY year DESC, sort DESC", (subject_type, subject_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def career_by_year(subject_id: str, subject_type: str = "player") -> list[dict]:
    """Career honors grouped into [{year, season_no, school, items:[...]}]."""
    groups: dict[int, dict] = {}
    for h in career(subject_id, subject_type):
        g = groups.setdefault(h["year"], {"year": h["year"], "season_no": h["season_no"],
                                          "school": h["school"], "awards": []})
        g["awards"].append(h)
    return [groups[y] for y in sorted(groups, reverse=True)]


def has_season(year: int, division: str, gender: str) -> bool:
    conn = _conn()
    row = conn.execute("SELECT 1 FROM honors WHERE year=? AND division=? AND gender=? LIMIT 1",
                       (year, division, gender)).fetchone()
    conn.close()
    return row is not None


def years() -> list[int]:
    """Distinct stamped season-years, newest first (the Hall of Fame index)."""
    conn = _conn()
    rows = conn.execute("SELECT DISTINCT year FROM honors ORDER BY year DESC").fetchall()
    conn.close()
    return [r["year"] for r in rows]


def winners(year: int, awards: list[str]) -> list[dict]:
    """Honor rows for a year filtered to the given award keys."""
    if not awards:
        return []
    ph = ",".join("?" * len(awards))
    conn = _conn()
    rows = conn.execute(
        f"SELECT * FROM honors WHERE year=? AND award IN ({ph}) ORDER BY division, gender, sort DESC",
        (year, *awards)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def for_season(year: int, division: str, gender: str) -> list[dict]:
    """Every stamped honor for one universe-year (most prestigious first) — the
    archive of that season's award winners, read straight from the store rather
    than recomputed."""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM honors WHERE year=? AND division=? AND gender=? "
        "ORDER BY sort DESC, school", (year, division, gender)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def at_school(year: int, division: str, gender: str, school: str,
              subject_type: str = "player") -> list[dict]:
    """Honor rows for one program in one year (e.g. the players a coach's team had
    win awards that season), most prestigious first."""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM honors WHERE year=? AND division=? AND gender=? AND school=?"
        " AND subject_type=? ORDER BY sort DESC",
        (year, division, gender, school, subject_type)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reset() -> None:
    conn = _conn()
    conn.execute("DELETE FROM honors")
    conn.commit()
    conn.close()
