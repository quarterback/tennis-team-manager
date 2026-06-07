"""
SQLite persistence scaffold.

Lifted in idiom from o27v2's `db.py`: a single connection helper, an
idempotent `init_db()` that creates the schema, and writes wrapped in a
transaction. This is the skeleton schema (players, matches, match_stats) —
leagues / seasons / ratings / circuits / recruiting land on top in later
phases (see docs/DESIGN-college-tennis-sim-fork.md §6).

DB path: $TENNIS_DB_PATH or ./tennis.db
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager

from engine.match import MatchResult

DB_PATH = os.environ.get("TENNIS_DB_PATH", os.path.join(os.getcwd(), "tennis.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    country     TEXT,
    gender      TEXT,
    serve_power REAL, serve_placement REAL, return_game REAL,
    forehand REAL, backhand REAL, movement REAL,
    stamina REAL, mental REAL, consistency REAL,
    rating      REAL,           -- modified-UTR (filled by rating pass, P5)
    reliability REAL
);

CREATE TABLE IF NOT EXISTS matches (
    id          INTEGER PRIMARY KEY,
    seed        INTEGER NOT NULL,
    fidelity    TEXT NOT NULL,
    fmt         TEXT,           -- JSON of MatchFormat
    p0_id       INTEGER, p1_id INTEGER,
    winner      INTEGER,
    scoreline   TEXT,
    games_p0    INTEGER, games_p1 INTEGER
);

CREATE TABLE IF NOT EXISTS match_stats (
    match_id    INTEGER NOT NULL,
    side        INTEGER NOT NULL,   -- 0 or 1
    aces INTEGER, double_faults INTEGER,
    first_serve_pct REAL, serve_points_won_pct REAL,
    break_points_faced INTEGER, break_points_saved INTEGER,
    break_points_converted INTEGER,
    winners INTEGER, unforced_errors INTEGER, points_won INTEGER,
    PRIMARY KEY (match_id, side)
);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def transaction(path: str | None = None):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_match(conn: sqlite3.Connection, result: MatchResult, *, seed: int,
               fmt_json: str = "", p0_id: int | None = None,
               p1_id: int | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO matches (seed, fidelity, fmt, p0_id, p1_id, winner, "
        "scoreline, games_p0, games_p1) VALUES (?,?,?,?,?,?,?,?,?)",
        (seed, result.fidelity, fmt_json, p0_id, p1_id, result.winner,
         result.scoreline, result.games_won[0], result.games_won[1]),
    )
    match_id = cur.lastrowid
    if result.fidelity != "fast":
        for side, s in enumerate(result.stats):
            conn.execute(
                "INSERT INTO match_stats (match_id, side, aces, double_faults, "
                "first_serve_pct, serve_points_won_pct, break_points_faced, "
                "break_points_saved, break_points_converted, winners, "
                "unforced_errors, points_won) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (match_id, side, s.aces, s.double_faults, s.first_serve_pct,
                 s.serve_points_won_pct, s.break_points_faced, s.break_points_saved,
                 s.break_points_converted, s.winners, s.unforced_errors, s.points_won),
            )
    return match_id
