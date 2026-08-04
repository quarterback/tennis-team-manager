"""Final CTA rankings archive — the season's last rankings, stamped ONCE per
season-year at the moment the conference tournaments finish (the same boundary
where the NCAA field is selected), then never recomputed. The year-over-year
record of who finished ranked where — the rankings analogue of `app.honors`.

One flat table, one row per ranked entry (not a JSON blob) so it can be queried
per player (`player_final_ranks`) as well as per board. Boards mirror the live
/rankings page at its default settings: teams (top 75 / D2 50), singles (125 /
75, min 3 matches), doubles pairs (60 / 40, min 3 together). Rows carry the
school's CTA region and the player's class so the archived board can be viewed
through the same national / regional / newcomer scopes as the live one.

Stamping is idempotent (the season's boards are cleared and rewritten), and the
caller must NOT hold an open write transaction on the shared SQLite file — the
seasonmode driver stamps after committing the phase flip (see honors.stamp's
deadlock note).
"""
from __future__ import annotations

import sqlite3

from app.db import connect

BOARDS = ("teams", "singles", "doubles")

# Final-board sizes, mirroring the live page caps (small = D2).
TEAM_CAP = {False: 75, True: 50}
SINGLES_CAP = {False: 125, True: 75}
DOUBLES_CAP = {False: 60, True: 40}
MIN_MATCHES = 3                     # the live page's default ranking gate

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cta_rankings (
  year      INTEGER NOT NULL,          -- calendar year (2026 + world year)
  season_no INTEGER,
  division  TEXT NOT NULL,
  gender    TEXT NOT NULL,
  board     TEXT NOT NULL,             -- 'teams' | 'singles' | 'doubles'
  rk        INTEGER NOT NULL,
  school    TEXT,
  conf_abbr TEXT,
  region    TEXT,                      -- CTA region of the school (census divisions)
  pid       TEXT,                      -- singles: the player; doubles: pair half 1
  name      TEXT,
  pid2      TEXT,                      -- doubles: pair half 2
  name2     TEXT,
  cls       TEXT,                      -- singles: class year as of the season (Fr/RS-Fr/...)
  w         INTEGER,
  l         INTEGER,
  points    REAL,
  PRIMARY KEY (year, division, gender, board, rk)
);
CREATE INDEX IF NOT EXISTS idx_cta_rankings_pid ON cta_rankings(pid);
CREATE INDEX IF NOT EXISTS idx_cta_rankings_season ON cta_rankings(year, division, gender);
"""

_ready_for = None       # the DB path the schema was last created on


def _db_path() -> str:
    """The archive lives in the SAME file as the seasons it archives (sm.DB_PATH
    — identical to app.db's path in production, but tests repoint seasonmode at
    temp files, and the stamp fires implicitly from sm.advance: following
    sm.DB_PATH keeps a temp season's archive in the temp file, never leaking
    into the main save)."""
    import app.seasonmode as sm
    return sm.DB_PATH


def init_schema() -> None:
    global _ready_for
    path = _db_path()
    with connect(path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _ready_for = path


def _conn() -> sqlite3.Connection:
    if _ready_for != _db_path():
        init_schema()
    return connect(_db_path())


def _season_year() -> tuple[int, int]:
    """(calendar year, season_no) for the CURRENT world year — or season 1 / 2026
    for a standalone season with no world (tests, calibration)."""
    import app.world as world
    yr = world.load_world()["year"] if world.exists() else 0
    return 2026 + yr, yr + 1


def _region_map(division: str, gender: str) -> dict:
    from app.ncaa import load_division
    from app.scout_intel import US_REGIONS
    return {p.school: US_REGIONS.get((p.state or "").upper(), "")
            for p in load_division(division, gender).programs}


def _build_rows(season_id: int) -> list[dict]:
    """All boards' rows for one season, in stampable form."""
    import app.seasonmode as sm
    from app.ncaa import load_division
    s = sm.load_season(season_id)
    division, gender = s["division"], s["gender"]
    small = division == "D2"
    year, season_no = _season_year()
    region_of = _region_map(division, gender)
    progs = load_division(division, gender).programs
    conf_abbr = {p.school: p.conf_abbr for p in progs}
    base = {"year": year, "season_no": season_no, "division": division,
            "gender": gender, "pid": None, "name": None, "pid2": None,
            "name2": None, "cls": None}
    rows: list[dict] = []

    # Teams — ordered by CTA team points, W-L from the Power Index lines.
    pts = sm.ita_team_points(season_id)
    ratings = sm.power_index(season_id)
    for rk, school in enumerate(sorted(pts, key=lambda x: (-pts[x], x))[:TEAM_CAP[small]], 1):
        r = ratings.get(school)
        rows.append({**base, "board": "teams", "rk": rk, "school": school,
                     "conf_abbr": conf_abbr.get(school, ""),
                     "region": region_of.get(school, ""),
                     "w": r.wins if r else 0, "l": r.losses if r else 0,
                     "points": round(pts[school], 2)})

    # Singles — players, with class + region so newcomer/regional scopes replay.
    spts = sm.ita_singles_points(season_id, MIN_MATCHES)
    pidx = sm._pid_index(division, gender)
    recs = sm.player_records(season_id)
    rk = 0
    for pid in sorted(spts, key=lambda x: (-spts[x], x)):
        info = pidx.get(pid)
        if not info:
            continue
        rk += 1
        if rk > SINGLES_CAP[small]:
            break
        w, l = recs.get(pid, (0, 0))
        rows.append({**base, "board": "singles", "rk": rk, "school": info["school"],
                     "conf_abbr": conf_abbr.get(info["school"], ""),
                     "region": region_of.get(info["school"], ""),
                     "pid": pid, "name": info["name"], "cls": info.get("class", ""),
                     "w": w, "l": l, "points": round(spts[pid], 2)})

    # Doubles — pairs (both pids so either half's page can find the row).
    dpts, members, wl = sm.ita_doubles_points(season_id, MIN_MATCHES)
    rk = 0
    for pr in sorted(dpts, key=lambda x: -dpts[x]):
        m = members.get(pr)
        i1 = pidx.get(m[0]) if m else None
        i2 = pidx.get(m[1]) if m else None
        if not i1 or not i2:
            continue
        rk += 1
        if rk > DOUBLES_CAP[small]:
            break
        w, l = wl.get(pr, [0, 0])
        rows.append({**base, "board": "doubles", "rk": rk, "school": i1["school"],
                     "conf_abbr": conf_abbr.get(i1["school"], ""),
                     "region": region_of.get(i1["school"], ""),
                     "pid": m[0], "name": i1["name"], "pid2": m[1], "name2": i2["name"],
                     "w": w, "l": l, "points": round(dpts[pr], 2)})
    return rows


def stamp_final_rankings(season_id: int) -> int:
    """Persist the season's final boards. Stamped ONCE and never recomputed
    (like honors): a later call for an already-archived season-year is a no-op —
    the player-points corpus keeps growing through the NCAAs, and the archived
    board is defined as the one that stood when the conference tournaments
    ended, not a moving target."""
    import app.seasonmode as sm
    s = sm.load_season(season_id)
    year, _ = _season_year()
    conn = _conn()
    try:
        done = conn.execute(
            "SELECT 1 FROM cta_rankings WHERE year=? AND division=? AND gender=? LIMIT 1",
            (year, s["division"], s["gender"])).fetchone()
    finally:
        conn.close()
    if done:
        return 0
    rows = _build_rows(season_id)
    if not rows:
        return 0
    year, division, gender = rows[0]["year"], rows[0]["division"], rows[0]["gender"]
    conn = _conn()
    try:
        conn.execute("DELETE FROM cta_rankings WHERE year=? AND division=? AND gender=?",
                     (year, division, gender))
        conn.executemany(
            "INSERT INTO cta_rankings (year, season_no, division, gender, board, rk,"
            " school, conf_abbr, region, pid, name, pid2, name2, cls, w, l, points)"
            " VALUES (:year, :season_no, :division, :gender, :board, :rk, :school,"
            " :conf_abbr, :region, :pid, :name, :pid2, :name2, :cls, :w, :l, :points)",
            rows)
        conn.commit()
    finally:
        conn.close()
    return len(rows)


def years(division: str, gender: str) -> list[int]:
    """Archived calendar years for a universe, newest first."""
    conn = _conn()
    try:
        return [r["year"] for r in conn.execute(
            "SELECT DISTINCT year FROM cta_rankings WHERE division=? AND gender=?"
            " ORDER BY year DESC", (division, gender)).fetchall()]
    finally:
        conn.close()


def board(year: int, division: str, gender: str, which: str) -> list[dict]:
    """One archived board, in final rank order."""
    conn = _conn()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM cta_rankings WHERE year=? AND division=? AND gender=?"
            " AND board=? ORDER BY rk", (year, division, gender, which)).fetchall()]
    finally:
        conn.close()


def player_final_ranks(pid: str) -> list[dict]:
    """Every final ranking a player ever earned (singles + doubles), newest
    first — the year-over-year 'how did they rank' record for the player page."""
    conn = _conn()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM cta_rankings WHERE (pid=? OR pid2=?) AND board!='teams'"
            " ORDER BY year DESC, board", (pid, pid)).fetchall()]
    finally:
        conn.close()
