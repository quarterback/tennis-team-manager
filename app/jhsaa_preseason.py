"""THE PRESEASON STATE — what the rung derives about every program, stored so no
page rebuilds it (read-path fix #3, owner directive 2026-09,
docs/reports/AUDIT-jhsaa-read-paths-2026-09.md).

A JHSAA roster is a recipe re-run on every read, and the coach's preseason
ladder on top of it — his lens, his read of each player, last season's proof,
Future Value, Program Interest — is derived again every time anything asks.
The season rung already builds all of it for every program; this module WRITES
it down, one row per program per season (`world_jhsaa_preseason_state`):

  * the roster in COACH ORDER, each seat with the display fields a page shows
    (grade, OVR, potential estimate, stars, STR, country, sibling) and the
    evaluation it was ranked on (`eval`, the `_order` key with no results —
    the preseason ladder) plus its parts (read, future, interest, tenure, prior);
  * the V1 cut (`district_need(group)` — the class's DISTRICT lineup, which is
    its State format since owner rule 2026-10) and the **V1 FLOOR** — the key
    of the last V1 seat — so "would this player make V1 here?" is one key and a
    comparison, never a roster build;
  * the staff effect the ladder was read with (lens, future/loyalty weights).

Two kinds of row. The season's own rows are written INSIDE the rung's
transaction from the teams it just played (`record`). The NEXT season's rows are
written after the commit (`write_provisional`, `provisional=1`): the rung builds
S+1's rosters once — the only whole-association build the rising-freshman portal
ever needs — and the portal eliminates destinations against these floors. They
are a filter, not an answer: a candidate that clears a stored floor is confirmed
against the LIVE projection before it is proposed, and once a move consumes a
seat the live ladder replaces the stored one for that school. Provisional rows
are replaced by the real ones when S+1 is played.

`v` is `VERSION`; rows at an older version read as absent (callers fall back to
building, then the next rung rewrites them). The table can be dropped and the
next rung rebuilds it: a materialisation, never a second source of truth.
"""
from __future__ import annotations

import bisect
import json

from . import jhsaa as jh

VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS world_jhsaa_preseason_state (
  world_id INTEGER, year INTEGER, gender TEXT, school TEXT,
  provisional INTEGER DEFAULT 0, v INTEGER, data TEXT,
  PRIMARY KEY (world_id, year, gender, school)
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_preseason_state
  ON world_jhsaa_preseason_state(world_id, year, gender);
CREATE TABLE IF NOT EXISTS world_jhsaa_sibling (
  world_id INTEGER, younger_pid TEXT, older_pid TEXT, gender TEXT, school TEXT,
  name TEXT, entry INTEGER, year INTEGER,
  PRIMARY KEY (world_id, younger_pid)
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_sibling_older ON world_jhsaa_sibling(world_id, older_pid);
CREATE TABLE IF NOT EXISTS world_jhsaa_sibling_cover (
  world_id INTEGER, gender TEXT, year INTEGER, PRIMARY KEY (world_id, gender, year)
);
"""


# --------------------------------------------------------------- the key ----

def ladder_key(ts, p, read: float, future: float, interest: float) -> tuple:
    """`_order`'s sort key for `p` on `ts` BEFORE a ball is struck (no results):
    higher sorts first. One definition, shared by the store and the portal."""
    return (jh.coach_eval(p, None, prior=ts.prior.get(p.pid), lens=ts.lens, read=read,
                          future=future, interest=interest), p.str_value())


def newcomer_key(state: dict, p, season_year: int, salt: str, prior=None) -> tuple:
    """The key `p` would carry on the STORED ladder of `state`'s program — this
    coach's read of them, their own prior, his future weight, no program interest
    (a move resets it): exactly what `jhsaa_portal._with` gives a mover."""
    st = state["staff"]
    lens = jh.CoachLens(**st["lens"])
    read = jh.coach_read(p.pid, state["school"], season_year, lens, salt) if lens.read > 0 else 0.0
    ev = jh.coach_eval(p, None, prior=prior, lens=lens, read=read,
                       future=jh.future_value(p, st["future_w"]), interest=0.0)
    return (ev, p.str_value())


def seat_on(state: dict, key: tuple) -> int | None:
    """Where `key` lands on the stored ladder (0-based), or None if off V1 — a
    bisect over the stored keys, ties behind (the newcomer joins the roster last,
    which is where a stable sort puts an equal key)."""
    neg = [(-e, -s) for e, s in state["keys"]]           # ascending
    idx = bisect.bisect_right(neg, (-key[0], -key[1]))
    return idx if idx < state["v1"] else None


# ------------------------------------------------------------- the rows ----

def team_state(ts, season_year: int) -> dict:
    """One program's preseason state off a built `TeamSeason`."""
    fut, itr, ten = ts.future or {}, ts.interest or {}, ts.tenure or {}
    entries = []
    for p in ts.roster:
        read = ts.read.get(p.pid, 0.0)
        key = ladder_key(ts, p, read, fut.get(p.pid, 0.0), itr.get(p.pid, 0.0))
        pr = ts.prior.get(p.pid)
        jd = p.jhsaa or {}
        entries.append({
            "pid": p.pid, "name": p.name, "grade": p.grade, "entry": p.entry_year,
            "seat": jd.get("seat"), "country": p.country,
            "ovr": round(p.current_overall(), 1), "ceiling": round(jh.pot_display(p), 1),
            "stars": p.star_rating(), "str": p.str_value(),
            "sibling": jd.get("sibling"), "sibling_name": jd.get("sibling_name", ""),
            "sibling_school": jd.get("sibling_school", ""),
            "sibling_gender": jd.get("sibling_gender", ""),
            "early": list(jd.get("early") or ()),
            "eval": round(key[0], 4), "read": round(read, 4),
            "future": round(fut.get(p.pid, 0.0), 4), "interest": round(itr.get(p.pid, 0.0), 4),
            "tenure": ten.get(p.pid),
            "prior": ({"apps": pr.apps, "wins": pr.wins, "losses": pr.losses, "rank": pr.rank}
                      if pr else None)})
    entries.sort(key=lambda e: (-e["eval"], -e["str"]))
    v1 = jh.district_need(ts.school.group)   # the class's district lineup (owner rule 2026-10)
    keys = [(e["eval"], e["str"]) for e in entries]
    return {"school": ts.school.name, "ident": ts.school.ident, "season_year": season_year,
            "classification": ts.school.classification, "group": ts.school.group,
            "district": ts.school.district, "county": ts.school.county, "area": ts.school.area,
            "v1": v1, "floor": keys[v1 - 1] if len(keys) >= v1 else None,
            "keys": keys, "ladder": entries,
            "staff": {"lens": {"read": ts.lens.read, "trust": ts.lens.trust, "form": ts.lens.form},
                      "future_w": ts.future_w, "loyalty_w": ts.loyalty_w,
                      "culture": ts.culture, "strategy": ts.strategy}}


def record(conn, world_id: int, year: int, gender: str, teams, season_year: int,
           provisional: int = 0) -> None:
    """Write every team's state on the caller's connection (the rung's own
    transaction for the played season; `write_provisional`'s for the next)."""
    conn.executemany(
        "INSERT OR REPLACE INTO world_jhsaa_preseason_state"
        " (world_id, year, gender, school, provisional, v, data) VALUES (?,?,?,?,?,?,?)",
        [(world_id, year, gender, t.school.name, provisional, VERSION,
          json.dumps(team_state(t, season_year))) for t in teams])


def write_provisional(world_id: int, year: int, gender: str, season_year: int,
                      salt: str) -> int:
    """Build NEXT season's teams once, at the rung, and store their state as
    provisional. `year` is the world index the season will be archived under
    (this rung's + 1). Reads the standing the rung just COMMITTED, so it runs
    after the commit. Returns how many programs were written."""
    from . import world as wd
    prior = wd.jhsaa_prior_for_season(season_year, gender, world_id)
    staff = wd.jhsaa_staff_for_season(season_year, gender, world_id)
    teams = jh.district_teams(jh.load_schools(gender), season_year, salt,
                              prior=prior, staff=staff)
    conn = wd._db()
    try:
        # Never downgrade a REAL row to a provisional one.
        real = {r[0] for r in conn.execute(
            "SELECT school FROM world_jhsaa_preseason_state WHERE world_id=? AND year=?"
            " AND gender=? AND provisional=0", (world_id, year, gender))}
        record(conn, world_id, year, gender, [t for t in teams if t.school.name not in real],
               season_year, provisional=1)
        conn.commit()
    finally:
        conn.close()
    return len(teams)


# ----------------------------------------------------------------- reads ----

def load(world_id: int, year: int, gender: str) -> dict:
    """`{school: state}` for one season — one indexed query, rows at the current
    version only (an older version reads as absent, so callers build instead)."""
    from . import world as wd
    conn = wd._db()
    try:
        rows = conn.execute(
            "SELECT school, provisional, data FROM world_jhsaa_preseason_state WHERE world_id=?"
            " AND year=? AND gender=? AND v=?", (world_id, year, gender, VERSION)).fetchall()
    finally:
        conn.close()
    return {r["school"]: {**json.loads(r["data"]), "provisional": bool(r["provisional"])}
            for r in rows}


def load_school(world_id: int, year: int, gender: str, school: str) -> dict | None:
    """One program's stored state, under any name it has carried, or None."""
    from . import world as wd
    names = jh.known_names(school, gender)
    conn = wd._db()
    try:
        r = conn.execute(
            "SELECT provisional, data FROM world_jhsaa_preseason_state WHERE world_id=? AND year=?"
            " AND gender=? AND v=? AND school IN (%s) LIMIT 1" % ",".join("?" * len(names)),
            (world_id, year, gender, VERSION, *names)).fetchone()
    finally:
        conn.close()
    return {**json.loads(r["data"]), "provisional": bool(r["provisional"])} if r else None


class StoredPlayer:
    """A roster row read back from the store, wearing the slice of the `Prospect`
    interface a PAGE reads (never the engine: no attributes, no development)."""
    __slots__ = ("pid", "name", "grade", "entry_year", "country", "high_school",
                 "jhsaa", "_e")

    def __init__(self, e: dict, school: str):
        self.pid, self.name, self.grade = e["pid"], e["name"], e["grade"]
        self.entry_year, self.country, self.high_school = e["entry"], e.get("country", "US"), school
        self.jhsaa = {k: e.get(k) for k in ("seat", "sibling", "sibling_name", "sibling_school",
                                           "sibling_gender", "early")}
        self._e = e

    def current_overall(self):
        return self._e["ovr"]

    def star_rating(self):
        return self._e["stars"]

    def str_value(self):
        return self._e["str"]

    @property
    def ceiling_estimate(self):
        return self._e["ceiling"]


def stored_roster(world_id: int, year: int, gender: str, school: str) -> list | None:
    """The program's roster for an ARCHIVED season as the rung stored it, in coach
    order, or None when the store has no REAL row (a season archived before the
    store, or a provisional next-season row) — the caller builds instead."""
    st = load_school(world_id, year, gender, school)
    if not st or st.get("provisional"):
        return None
    return [StoredPlayer(e, st["school"]) for e in st["ladder"]]


# --------------------------------------------------------- the sibling index ----
#
# READ-PATH FIX #4. A generated sibling tie is rolled by the YOUNGER seat and
# points at the older pid, so "who are this player's younger siblings?" was a
# scan: build the roster of every program in the town for the three cohorts
# after the player's, both genders (9-39 roster builds on the fixture, ~250 for
# a Port Veles player). The rung sees every rostered player's link when it
# archives a season, so it writes the tie the other way round — one row per
# younger player — and the page reads an indexed query. `world_jhsaa_sibling_
# cover` records which (gender, season) the rung has indexed; a cohort whose
# first season predates the index still falls back to the scan for that year.

def record_siblings(conn, world_id: int, year: int, gender: str, rosters) -> None:
    """Index every generated tie on these rosters (idempotent) and mark the
    season covered. `rosters` is an iterable of player lists."""
    rows = []
    for roster in rosters:
        for p in roster:
            older = (p.jhsaa or {}).get("sibling")
            if older:
                rows.append((world_id, p.pid, older, gender, p.high_school or "",
                             p.name, p.entry_year, year))
    conn.executemany(
        "INSERT OR IGNORE INTO world_jhsaa_sibling"
        " (world_id, younger_pid, older_pid, gender, school, name, entry, year)"
        " VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.execute("INSERT OR IGNORE INTO world_jhsaa_sibling_cover (world_id, gender, year)"
                 " VALUES (?,?,?)", (world_id, gender, year))


def sibling_cover(world_id: int) -> set:
    """{(gender, world-year)} the index covers."""
    from . import world as wd
    conn = wd._db()
    try:
        return {(r[0], r[1]) for r in conn.execute(
            "SELECT gender, year FROM world_jhsaa_sibling_cover WHERE world_id=?",
            (world_id,))}
    except Exception:
        return set()
    finally:
        conn.close()


def younger_siblings(world_id: int, older_pid: str) -> list[dict]:
    """Every indexed younger sibling of `older_pid`, as member dicts."""
    from . import world as wd
    conn = wd._db()
    try:
        rows = conn.execute(
            "SELECT younger_pid, name, gender, school, entry FROM world_jhsaa_sibling"
            " WHERE world_id=? AND older_pid=? ORDER BY entry, name",
            (world_id, older_pid)).fetchall()
    finally:
        conn.close()
    return [{"pid": r["younger_pid"], "name": r["name"], "gender": r["gender"],
             "school": jh.current_name(r["school"], r["gender"]), "entry": r["entry"],
             "relation": "sibling"} for r in rows]
