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

# Bumped on every reset() so callers that cache coach ids (e.g. the web layer's
# staff cache) can key on it and drop entries pointing at coaches the wipe removed.
_GENERATION = 0


def generation() -> int:
    """A counter that increments whenever the registry is wiped (`reset`). Fold it
    into any cache of coach ids so a reset naturally invalidates that cache."""
    return _GENERATION


_SCHEMA = """
CREATE TABLE IF NOT EXISTS coach (
  coach_id     TEXT PRIMARY KEY,
  name         TEXT,
  home_country TEXT,
  archetype    TEXT,
  dev          REAL,
  rec          REAL,
  tac          REAL,
  player_pid   TEXT
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
CREATE TABLE IF NOT EXISTS coach_assignment (
  assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  coach_id TEXT, year INTEGER,
  division TEXT, gender TEXT, school TEXT, role TEXT,
  event TEXT
);
CREATE INDEX IF NOT EXISTS idx_coachassign_cid ON coach_assignment(coach_id, assignment_id);
"""

_ready = False


def init_schema() -> None:
    global _ready
    with connect() as conn:
        conn.executescript(_SCHEMA)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(coach)")}
        if "player_pid" not in cols:  # migrate saves created before player→coach links
            conn.execute("ALTER TABLE coach ADD COLUMN player_pid TEXT")
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
    if seat is not None:
        if not seat["coach_id"]:        # the seat exists but is VACANT (coach retired
            conn.close()                # or moved on) — respect the vacancy, don't backfill
            return None
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
    conn.execute("INSERT INTO coach_assignment (coach_id, year, division, gender, school, role, event)"
                 " VALUES (?,?,?,?,?,?,?)", (cid, None, division, gender, school, role, "hired"))
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


def retire(coach_id: str) -> bool:
    """Retire a coach: vacate their seat (leave it empty rather than backfilling),
    so you can promote someone into it without anyone being pushed down. The coach
    entity, career record and honors persist (keyed to the id) — they're just no
    longer on a staff."""
    conn = _conn()
    cur = conn.execute("UPDATE coach_seat SET coach_id='', tenure=0 WHERE coach_id=?",
                       (coach_id,))
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n > 0


def _log_assignment(conn, coach_id: str, seat, year: int | None, event: str) -> None:
    if coach_id and seat:
        conn.execute("INSERT INTO coach_assignment (coach_id, year, division, gender, school, role, event)"
                     " VALUES (?,?,?,?,?,?,?)",
                     (coach_id, year, seat["division"], seat["gender"], seat["school"],
                      seat["role"], event))


def assignments(coach_id: str) -> list[dict]:
    """Every distinct job held by a coach, in chronological order.

    Unlike season results this is written when a move happens, so an in-season
    editor move or carousel change never erases the program the coach came from.
    """
    conn = _conn()
    rows = conn.execute("SELECT * FROM coach_assignment WHERE coach_id=? ORDER BY assignment_id",
                        (coach_id,)).fetchall()
    conn.close()
    out = []
    for row in rows:
        item = dict(row)
        if not out or any(item[k] != out[-1][k] for k in ("division", "gender", "school", "role")):
            out.append(item)
    return out


def coach_for_player(player_pid: str) -> dict | None:
    """Return the separate coaching identity linked to a former player."""
    conn = _conn()
    row = conn.execute("SELECT coach_id FROM coach WHERE player_pid=? LIMIT 1",
                       (player_pid,)).fetchone()
    conn.close()
    return get(row["coach_id"]) if row else None


def create_from_player(player_pid: str, *, name: str, home_country: str,
                       division: str, gender: str, school: str, role: str,
                       dev: float, rec: float, tac: float) -> dict:
    """Create a distinct coach page for an alumnus and appoint them to a seat.

    The old player pid remains untouched and is linked from the new coach entity.
    If the seat is occupied, its incumbent becomes a free agent rather than being
    deleted; their own history and honors remain available.
    """
    existing = coach_for_player(player_pid)
    if existing:
        return existing
    conn = _conn()
    cid = uuid.uuid4().hex[:12]
    conn.execute("INSERT INTO coach (coach_id, name, home_country, archetype, dev, rec, tac, player_pid)"
                 " VALUES (?,?,?,?,?,?,?,?)",
                 (cid, name, home_country, "Former Player", dev, rec, tac, player_pid))
    seat = conn.execute("SELECT * FROM coach_seat WHERE division=? AND gender=? AND school=? AND role=?",
                        (division, gender, school, role)).fetchone()
    if seat:
        conn.execute("UPDATE coach_seat SET coach_id=?, tenure=1 WHERE division=? AND gender=? AND school=? AND role=?",
                     (cid, division, gender, school, role))
    else:
        conn.execute("INSERT INTO coach_seat VALUES (?,?,?,?,?,1)",
                     (division, gender, school, role, cid))
    conn.execute("INSERT INTO coach_assignment (coach_id, year, division, gender, school, role, event)"
                 " VALUES (?,?,?,?,?,?,?)", (cid, None, division, gender, school, role, "hired"))
    conn.commit()
    conn.close()
    return get(cid)


def move_to(coach_id: str, g2: str, d2: str, s2: str, r2: str,
            *, year: int | None = None) -> bool:
    """Move a coach into a seat. If the target seat is occupied the two swap; if
    it's VACANT the coach simply takes it and their old seat is left vacant (no
    forced demotion). Both tenures reset. The target seat row must already exist."""
    conn = _conn()
    src = conn.execute("SELECT division, gender, school, role FROM coach_seat WHERE coach_id=? LIMIT 1",
                       (coach_id,)).fetchone()
    tgt = conn.execute("SELECT * FROM coach_seat WHERE division=? AND gender=? AND school=? AND role=?",
                       (d2, g2, s2, r2)).fetchone()
    if not src or tgt is None:
        conn.close()
        return False
    displaced = tgt["coach_id"] or ""          # whoever was in the target (or vacant)
    conn.execute("UPDATE coach_seat SET coach_id=?, tenure=1 WHERE division=? AND gender=? AND school=? AND role=?",
                 (coach_id, d2, g2, s2, r2))
    conn.execute("UPDATE coach_seat SET coach_id=?, tenure=? WHERE division=? AND gender=? AND school=? AND role=?",
                 (displaced, 1 if displaced else 0,
                  src["division"], src["gender"], src["school"], src["role"]))
    _log_assignment(conn, coach_id, tgt, year, "moved")
    _log_assignment(conn, displaced, src, year, "moved")
    conn.commit()
    conn.close()
    return True


def swap_seats(g1: str, d1: str, s1: str, r1: str,
               g2: str, d2: str, s2: str, r2: str, *, year: int | None = None) -> bool:
    """Swap the coaches holding two seats (any role, possibly across divisions),
    resetting both tenures to 1. Both seats must already exist. The god-mode
    editor primitive — every seat stays filled, so no coach is orphaned."""
    conn = _conn()
    a = conn.execute("SELECT * FROM coach_seat WHERE division=? AND gender=? AND school=? AND role=?",
                     (d1, g1, s1, r1)).fetchone()
    b = conn.execute("SELECT * FROM coach_seat WHERE division=? AND gender=? AND school=? AND role=?",
                     (d2, g2, s2, r2)).fetchone()
    if not a or not b:
        conn.close()
        return False
    conn.execute("UPDATE coach_seat SET coach_id=?, tenure=1 WHERE division=? AND gender=? AND school=? AND role=?",
                 (b["coach_id"], d1, g1, s1, r1))
    conn.execute("UPDATE coach_seat SET coach_id=?, tenure=1 WHERE division=? AND gender=? AND school=? AND role=?",
                 (a["coach_id"], d2, g2, s2, r2))
    _log_assignment(conn, b["coach_id"], a, year, "moved")
    _log_assignment(conn, a["coach_id"], b, year, "moved")
    conn.commit()
    conn.close()
    return True


def swap_head_coaches(g: str, d1: str, s1: str, d2: str, s2: str,
                      *, year: int | None = None) -> None:
    """Swap the head coaches of two programs (possibly across divisions) and
    reset both tenures to 1. Both head seats must already exist."""
    conn = _conn()
    a = conn.execute("SELECT * FROM coach_seat WHERE division=? AND gender=? AND school=? AND role='head'",
                     (d1, g, s1)).fetchone()
    b = conn.execute("SELECT * FROM coach_seat WHERE division=? AND gender=? AND school=? AND role='head'",
                     (d2, g, s2)).fetchone()
    if not a or not b:
        conn.close()
        return
    conn.execute("UPDATE coach_seat SET coach_id=?, tenure=1 WHERE division=? AND gender=? AND school=? AND role='head'",
                 (b["coach_id"], d1, g, s1))
    conn.execute("UPDATE coach_seat SET coach_id=?, tenure=1 WHERE division=? AND gender=? AND school=? AND role='head'",
                 (a["coach_id"], d2, g, s2))
    _log_assignment(conn, b["coach_id"], a, year, "moved")
    _log_assignment(conn, a["coach_id"], b, year, "moved")
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
    global _GENERATION
    _GENERATION += 1
    conn = _conn()
    conn.executescript("DELETE FROM coach_seat; DELETE FROM coach; DELETE FROM coach_history;"
                       " DELETE FROM coach_assignment;")
    conn.commit()
    conn.close()
