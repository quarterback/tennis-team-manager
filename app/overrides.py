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
import logging
import sqlite3

from . import dbpath
from .dbpath import resolve_db_path

log = logging.getLogger("baseline.overrides")

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
CREATE TABLE IF NOT EXISTS pro_signing (
  year INTEGER, cycle TEXT, gender TEXT, pid TEXT,
  dest_school TEXT, dest_div TEXT,
  PRIMARY KEY (year, cycle, pid)
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
        " WHERE kind IN ('move','lineup','doubles') ORDER BY kind, key").fetchall()
    conn.close()
    h = hashlib.md5()
    for r in rows:
        h.update(repr(tuple(r)).encode())
    return h.hexdigest()


def move_version() -> str:
    """Fingerprint of only the COMPOSITION-changing overrides — transfers
    (`move`). This is the version `world.prime()` keys on, and it deliberately
    EXCLUDES `lineup`/`doubles` pins (which `roster_version()` includes).

    A lineup or doubles pin only reorders who plays S1–S6 / which pairs take the
    court; it is applied LIVE downstream in `ncaa.build_roster` /
    `season.coach_lineup` and never changes the developed roster SET that
    `prime()` caches. Folding pins into the prime stamp made every lineup save
    invalidate the prime stamp, so the next full-world page (Analytics Bureau,
    rankings, hub) or the background warm re-primed the entire ~170MB world on
    the request thread → GIL held → `/api/health` starved → slow render → client
    `[Errno 110]` write timeout. A move-only stamp still catches every
    composition change prime must react to — editor moves and the fall-portal /
    preseason-portal commits all land as `move` rows (`ov.set_move`). See
    docs/AAR-cache-invalidation-scope-lineup-stall.md (§ prime re-prime)."""
    import hashlib
    conn = _db()
    rows = conn.execute(
        "SELECT kind, key, value FROM roster_overrides"
        " WHERE kind='move' ORDER BY key").fetchall()
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


def get_doubles() -> dict:
    """school -> ordered list of 6 pids forming the 3 doubles pairs
    [(0,1),(2,3),(4,5)]. INDEPENDENT of the singles lineup, so a doubles specialist
    who isn't a singles starter can be paired here."""
    conn = _db()
    rows = conn.execute("SELECT key, value FROM roster_overrides WHERE kind='doubles'").fetchall()
    conn.close()
    return {k: json.loads(v) for k, v in rows}


def set_doubles(school: str, pids: list[str]) -> None:
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO roster_overrides (kind, key, value) VALUES ('doubles',?,?)",
                 (school, json.dumps(pids)))
    conn.commit(); conn.close()


def clear_doubles(school: str) -> None:
    conn = _db()
    conn.execute("DELETE FROM roster_overrides WHERE kind='doubles' AND key=?", (school,))
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


# --- JHSAA program archetype (durable program conditions) ---------------------
# A per-PROGRAM tag — blue_blood / development / doubles — describing facilities, feeder
# networks, community participation, coaching tradition and reputation. NOT current team
# strength, and NOT derived from classification or public/private: those may inform who
# gets seeded onto the list, but the property belongs to the individual school and is
# editable, so the owner can promote and demote programs as Jefferson's history develops.
#
# Keyed on SCHOOL NAME alone. A school's courts, coaching and feeder programme serve its
# boys' and girls' teams alike, so the tag covers both.
#
# `upstart` deliberately does NOT live here: it is a temporary multi-year run, rolled per
# world from the season seed and expiring on its own (`jhsaa.upstarts`). A stored tag
# would make it permanent, which is the one thing it must not be.

def get_jhsaa_archetypes() -> dict:
    """{school: archetype} for every tagged JHSAA program."""
    conn = _db()
    rows = conn.execute(
        "SELECT key, value FROM roster_overrides WHERE kind='jhsaa_arch'").fetchall()
    conn.close()
    return {k: v for k, v in rows if v}


def set_jhsaa_archetype(school: str, archetype: str) -> None:
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO roster_overrides (kind, key, value)"
                 " VALUES ('jhsaa_arch',?,?)", (school, archetype))
    conn.commit(); conn.close()


def clear_jhsaa_archetype(school: str) -> None:
    conn = _db()
    conn.execute("DELETE FROM roster_overrides WHERE kind='jhsaa_arch' AND key=?", (school,))
    conn.commit(); conn.close()


def jhsaa_archetype_version() -> str:
    """Fingerprint of the archetype table — rosters are generated from it, so the JHSAA
    season cache has to fall when it changes."""
    import hashlib
    conn = _db()
    rows = conn.execute("SELECT key, value FROM roster_overrides WHERE kind='jhsaa_arch'"
                        " ORDER BY key").fetchall()
    conn.close()
    h = hashlib.md5()
    for r in rows:
        h.update(repr(tuple(r)).encode())
    return h.hexdigest()


# --- PLAYING UP (owner rule 2027-08, multi-step 2027-09) ----------------------
# A school competing a classification ABOVE its enrollment class, the way real
# associations let a strong program do. Stored exactly like an archetype — a seed
# list in `data/jhsaa/schools.json` (`play_up`) with this editable table on top.
#
# ‼️ THE STORED VALUE IS A TARGET GROUP, NOT A BOOL (owner rule 2027-09). Real
# associations approve play-up applications annually and for all kinds of reasons,
# not just "one class up" — a 3A program can play in 7A. The value is either a real
# group string ("7A") naming exactly where the program competes, or "no" (an
# explicit hold, reverting a seeded play-up to its own class); clearing the row
# reverts to the seed list's one-step default. `jhsaa.plays_up` re-validates a
# stored group on every read (never sideways, never down, never past
# `PLAY_UP_MAX_GROUP` eligibility) so a stale or crafted row can't promote past
# what the rule allows.
#
# ‼️ IT MOVES `group`, NEVER `classification`. `group` is the championship you
# enter; `classification` is how many students you have, and `_TALENT` is a
# statement about enrollment (`School.talent_group`). Move both and playing up
# silently becomes a free roster upgrade, which inverts the choice: it is meant
# to cost you a harder field, not buy you better players.

def get_jhsaa_playups() -> dict:
    """{school: target_group|"no"} for every program the editor has ruled on."""
    conn = _db()
    rows = conn.execute(
        "SELECT key, value FROM roster_overrides WHERE kind='jhsaa_playup'").fetchall()
    conn.close()
    return {k: v for k, v in rows if v}


def set_jhsaa_playup(school: str, target: str) -> None:
    """`target` is a real group string ("7A") to play up TO, or "no" to hold the
    program in its own class. Validated on the READ side (`jhsaa.plays_up`), not
    here — see the module note above."""
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO roster_overrides (kind, key, value)"
                 " VALUES ('jhsaa_playup',?,?)", (school, target))
    conn.commit(); conn.close()


def clear_jhsaa_playup(school: str) -> None:
    conn = _db()
    conn.execute("DELETE FROM roster_overrides WHERE kind='jhsaa_playup' AND key=?",
                 (school,))
    conn.commit(); conn.close()


def jhsaa_playup_version() -> str:
    """Fingerprint of the play-up table. It decides which CHAMPIONSHIP a program
    enters, so the school cache and the season cache both have to fall when it
    changes — a wider blast radius than an archetype, which only moves ability."""
    import hashlib
    conn = _db()
    rows = conn.execute("SELECT key, value FROM roster_overrides WHERE kind='jhsaa_playup'"
                        " ORDER BY key").fetchall()
    conn.close()
    h = hashlib.md5()
    for r in rows:
        h.update(repr(tuple(r)).encode())
    return h.hexdigest()


# --- JHSAA offseason transfers (owner rule 2027-08) ---------------------------
# A JHSAA player is not a persisted row — `jhsaa.build_roster` rebuilds them fresh
# from (school identity, gender, entry year, seat) every call — so "moving" one
# means recording enough to REGENERATE the same person under a different school
# rather than mutating a roster list the way the college editor's `set_move` does.
# Deliberately no eligibility/search logic here (owner rule 2027-08): this is a
# manual, always-approved, offseason-only relocation — the owner picks who moves,
# the module just makes it stick every year from `year` onward. Keyed on pid.

def get_jhsaa_transfers() -> dict:
    """{pid: {from, gender, entry, seat, to, year}} for every transferred player."""
    conn = _db()
    rows = conn.execute(
        "SELECT key, value FROM roster_overrides WHERE kind='jhsaa_transfer'").fetchall()
    conn.close()
    out = {}
    for k, v in rows:
        if not v:
            continue
        try:
            out[k] = json.loads(v)
        except (TypeError, ValueError):
            continue
    return out


def set_jhsaa_transfer(pid: str, from_school: str, gender: str, entry: int, seat: int,
                       to_school: str, year: int) -> None:
    """Record that `pid` (a real seat: school+gender+entry year+seat, so their
    generated identity can be rebuilt) moves to `to_school` for season `year`.

    ‼️ APPENDS TO A HISTORY, never replaces the record (owner rule 2026-08). A
    career can hold several moves — a third school, or a move back to the first —
    and each one is a fact about a season that was played. Replacing meant a second
    move erased the first, and because the player card DERIVES which school each
    season belonged to from this record, the seasons at the forgotten school were
    silently re-attributed to the origin and their results read 0-0.

    `from` is always the ORIGIN and is never rewritten: the pid is a one-way hash of
    (origin identity, gender, entry year, seat), so it is the only school this player
    can be regenerated from. A later move records a destination, never a new origin.

    Re-recording a move for a year that already has one REPLACES that entry — that is
    an edit of one decision, not a second move."""
    rows = get_jhsaa_transfers()
    rec = rows.get(pid) or {}
    moves = rec.get("moves")
    if moves is None:                       # legacy single-move record, or brand new
        moves = ([{"to": rec.get("to"), "year": rec.get("year")}]
                 if rec.get("to") else [])
    moves = [m for m in moves if m.get("to") and m.get("year") != year]
    moves.append({"to": to_school, "year": year})
    moves.sort(key=lambda m: (m.get("year") or 0))
    value = json.dumps({"from": rec.get("from") or from_school,
                        "gender": rec.get("gender") or gender,
                        "entry": rec.get("entry", entry), "seat": rec.get("seat", seat),
                        "moves": moves})
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO roster_overrides (kind, key, value)"
                 " VALUES ('jhsaa_transfer',?,?)", (pid, value))
    conn.commit(); conn.close()


def clear_jhsaa_transfer(pid: str, year: int | None = None) -> None:
    """Undo. With `year`, drop just that MOVE — the rest of the career stands, and a
    record left with no moves is deleted outright rather than kept as a row that says
    a player transferred nowhere. Without it, drop the whole history."""
    if year is not None:
        rec = get_jhsaa_transfers().get(pid)
        if rec is not None:
            moves = rec.get("moves")
            if moves is None:
                moves = ([{"to": rec.get("to"), "year": rec.get("year")}]
                         if rec.get("to") else [])
            moves = [m for m in moves if m.get("to") and m.get("year") != year]
            if moves:
                conn = _db()
                conn.execute(
                    "INSERT OR REPLACE INTO roster_overrides (kind, key, value)"
                    " VALUES ('jhsaa_transfer',?,?)",
                    (pid, json.dumps({**{k: v for k, v in rec.items()
                                         if k not in ("to", "year")},
                                      "moves": moves})))
                conn.commit(); conn.close()
                return
    conn = _db()
    conn.execute("DELETE FROM roster_overrides WHERE kind='jhsaa_transfer' AND key=?", (pid,))
    conn.commit(); conn.close()


def jhsaa_transfer_version() -> str:
    """Fingerprint of the transfer table — rosters are generated from it, so the
    JHSAA season cache has to fall when it changes, same as archetype/play-up."""
    import hashlib
    conn = _db()
    rows = conn.execute("SELECT key, value FROM roster_overrides WHERE kind='jhsaa_transfer'"
                        " ORDER BY key").fetchall()
    conn.close()
    h = hashlib.md5()
    for r in rows:
        h.update(repr(tuple(r)).encode())
    return h.hexdigest()


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


def dedupe_slate(rows: list[dict], table: str = "portal") -> list[dict]:
    """One row per pid, first-seen order — the LAST line of defence for the portal
    tables' (year, gender, pid) key.

    A player transfers once, so `world._FPPlanner` already refuses a second move for
    a pid; this makes the persistence layer agree structurally instead of trusting
    every caller's loop. Before the planner tracked moved pids, a rider displaced as
    another rider's cascade was placed AGAIN at their own intent, and the duplicate
    row blew up the /fall-portal commit with an IntegrityError (a 500 mid-commit,
    with the movers' ITA stints already stamped). A resolver bug should cost a
    dropped duplicate and a log line, never the commit. A rider's own intent
    (`cascade_from is None`) outranks a cascade demotion of the same player."""
    seen: dict[str, dict] = {}
    for r in rows:
        pid = r["pid"]
        prev = seen.get(pid)
        if prev is None:
            seen[pid] = r
            continue
        if prev.get("cascade_from") is not None and r.get("cascade_from") is None:
            seen[pid] = r                     # the rider row wins over the cascade
        keep = seen[pid]
        log.warning("%s: duplicate slate row for pid=%s (%s→%s and %s→%s) — keeping %s→%s",
                    table, pid, prev["src_school"], prev["dest_school"],
                    r["src_school"], r["dest_school"], keep["src_school"],
                    keep["dest_school"])
    return list(seen.values())


def set_proposals(year: int, gender: str, rows: list[dict]) -> None:
    """Replace this (year, gender) slate with a fresh set of 'proposed' rows."""
    rows = dedupe_slate(rows, "fall_portal")
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
    rows = dedupe_slate(rows, "preseason_portal")
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


# --- Pro free-agent signings (which pro signed which club, per portal cycle) ----------
def pro_set_sign(year: int, cycle: str, gender: str, pid: str,
                 dest_school: str, dest_div: str) -> None:
    """Sign a free-agent pro to a club (upsert the intent). Committed onto the roster
    when the portal commits; until then it's just the user's chosen destination."""
    def _do():
        conn = _db()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO pro_signing (year,cycle,gender,pid,dest_school,dest_div)"
                " VALUES (?,?,?,?,?,?)", (year, cycle, gender, pid, dest_school, dest_div))
            conn.commit()
        finally:
            conn.close()
    _retry_locked(_do)


def pro_unsign(year: int, cycle: str, pid: str) -> None:
    """Drop a pro's signing — back to an unsigned free agent."""
    def _do():
        conn = _db()
        try:
            conn.execute("DELETE FROM pro_signing WHERE year=? AND cycle=? AND pid=?",
                         (year, cycle, pid))
            conn.commit()
        finally:
            conn.close()
    _retry_locked(_do)


def pro_get_signs(year: int, cycle: str | None = None) -> dict:
    """{pid: {gender, dest_school, dest_div}} for a year (optionally one cycle)."""
    conn = _db()
    if cycle is None:
        rows = conn.execute("SELECT gender,pid,dest_school,dest_div FROM pro_signing"
                            " WHERE year=?", (year,)).fetchall()
    else:
        rows = conn.execute("SELECT gender,pid,dest_school,dest_div FROM pro_signing"
                            " WHERE year=? AND cycle=?", (year, cycle)).fetchall()
    conn.close()
    return {r[1]: {"gender": r[0], "dest_school": r[2], "dest_div": r[3]} for r in rows}


def pro_clear_year(year: int) -> None:
    conn = _db()
    conn.execute("DELETE FROM pro_signing WHERE year=?", (year,))
    conn.commit(); conn.close()


def clear_all() -> None:
    conn = _db()
    conn.execute("DELETE FROM roster_overrides")
    conn.execute("DELETE FROM fall_portal")
    conn.execute("DELETE FROM preseason_portal")
    conn.execute("DELETE FROM pro_signing")
    conn.commit(); conn.close()


def any_overrides() -> bool:
    conn = _db()
    n = conn.execute("SELECT COUNT(*) FROM roster_overrides").fetchone()[0]
    conn.close()
    return n > 0


# --- FAMILY TIES (owner rule 2026-08) ----------------------------------------
# Siblings, twins, cousins and — once a save runs long enough — a former player's
# child. Stored as narrative METADATA over pids that already exist: a tie NEVER
# rewrites a name. That is not merely tidier, it is required. `world_jhsaa_dual.
# lines` archives player NAMES rather than pids, and `state._jh_line_records` keys
# its whole season-record lookup off them, so renaming a player would silently
# zero their archived record — no error, plausible-looking wrong data, the failure
# this codebase keeps relearning. Metadata makes that impossible instead of fixing
# it, and needs no era gate (unlike `jhsaa.name_era`): a tie shifts no rng draw and
# no generated name, so every archived season is untouched by construction.
#
# ONE ROW PER FAMILY, keyed on an opaque id — never a slug built from a school
# name, because schools get renamed and the slug would rot. Family-keyed rather
# than player-keyed so the label and note live in exactly one place.

def get_jhsaa_families() -> dict:
    """{family_id: {label, relation, note, members:[{pid, gender, school, name, entry}]}}"""
    conn = _db()
    rows = conn.execute(
        "SELECT key, value FROM roster_overrides WHERE kind='jhsaa_family'").fetchall()
    conn.close()
    out = {}
    for k, v in rows:
        if not v:
            continue
        try:
            out[k] = json.loads(v)
        except (TypeError, ValueError):
            continue
    return out


def set_jhsaa_family(family_id: str, data: dict) -> None:
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO roster_overrides (kind, key, value)"
                 " VALUES ('jhsaa_family',?,?)", (family_id, json.dumps(data)))
    conn.commit(); conn.close()


def clear_jhsaa_family(family_id: str) -> None:
    conn = _db()
    conn.execute("DELETE FROM roster_overrides WHERE kind='jhsaa_family' AND key=?",
                 (family_id,))
    conn.commit(); conn.close()


def jhsaa_family_version() -> str:
    """Fingerprint of the family table. Ties are DISPLAY-only — they change no
    roster and no generated player — so this does NOT need to key the roster cache
    the way the archetype fingerprint does; it exists so the memo in
    `jhsaa.families()` falls when a tie is added or removed."""
    import hashlib
    conn = _db()
    rows = conn.execute("SELECT key, value FROM roster_overrides WHERE kind='jhsaa_family'"
                        " ORDER BY key").fetchall()
    conn.close()
    h = hashlib.md5()
    for r in rows:
        h.update(repr(tuple(r)).encode())
    return h.hexdigest()
