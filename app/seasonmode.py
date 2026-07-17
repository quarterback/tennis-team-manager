"""
Season mode — a persistent, navigable, week-by-week season.

Structure (per the design): a schedule of **non-conference duals first**, then a
**conference round-robin** (double for small conferences, single for large ones
so the season stays ~13–16 weeks), then **conference tournaments** (top-N H2H
single-elim; champion = NCAA autobid), then the **NCAA bracket** (autobids +
at-large by Power Index). Everything is stored in SQLite so a season persists
and can be returned to; results are computed deterministically from the season
seed as weeks are advanced.

Phases: ``regular`` → ``conf_tournaments`` → ``ncaa`` → ``complete``.

Rosters/players are regenerated deterministically from the seed (app.ncaa); only
the schedule + results are persisted. Standings, STR and Power Index are derived
from the *completed* duals, so they grow as the season is advanced.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections import Counter
from dataclasses import fields as _dc_fields

from engine import PlayerStats

from . import dbpath

from .ncaa import load_division
from .season import dual_between, build_corpus, forced_appearances
from . import injuries
from .rating import compute_ratings
from .str_rating import converge_ids
from .bracket import (select_field, run_bracket, _seed_positions, ROUND_NAMES,
                      clamp_field, field_for_division)
from . import ita
from . import regions

from .dbpath import resolve_db_path

DB_PATH = resolve_db_path()   # volume path if writable, else a local fallback

# Fall transfer portal — the post-ITA talent reshuffle. When on, a finished ITA
# opener parks the season in the 'fall_portal' hold phase (see `_finish_indoor`
# and `advance`) until `world.commit_fall_portal` releases it. Set False to
# restore the old ita_indoor → regular flow.
FALL_PORTAL_ENABLED = True

# Schedule shape: every team plays toward TARGET_DUALS, non-conf front-loaded,
# then conference play. Conferences under 10 teams play a DOUBLE round-robin
# (where it fits); larger ones play a single round-robin, with the balance made
# up in non-conference so each team lands near the target slate (~1-2 duals/wk).
TARGET_DUALS = 25            # realistic Division I dual slate per team
NONCONF_MIN = 6              # floor on non-conference even for big conferences
CONF_SHARE = 0.60            # aim for ~60% of the slate in conference (standings that mean something)
CONF_DOUBLE_MAX = 10         # conferences with < this many teams play a double round-robin
MAX_CONF_MEETINGS = 3        # cap on how many times two conference mates can meet when padding
CONF_TOURNEY_FIELD = 8       # top-N per conference make the conference tournament
MAX_PER_WEEK = 3            # up to a 3-dual weekend; keeps the ~25-slate to ~12-14 weeks
NATIONAL_FIELD = 64

# Result corpora. The overall *record* (standings, schedules, player logs) counts
# every phase. The *ranking* corpus that feeds the live Power Index also counts the
# ITA opener — an early-season test of who's good — but not the conference-tournament
# or NCAA brackets being seeded by it. The *seeding* corpus that selects the NCAA
# field adds the conference tournaments, as the selection always has.
RANKING_ROUNDS = ("REG", "ITAK", "ITAI")
SEED_ROUNDS = ("REG", "CT", "ITAK", "ITAI")

# The furthest round a program reached, in bracket vocabulary. The NCAA field's
# non-power-of-two play-in (D1's 96) is the Round of 96; the rest follow the draw.
NCAA_ROUND_LABEL = {
    "First Round": "R96", "Round of 96": "R96", "Round of 64": "R64",
    "Round of 32": "R32", "Round of 16": "S16", "Quarterfinals": "E8",
    "Semifinals": "🥉 Final Four", "Final": "Final",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seasons (
  id INTEGER PRIMARY KEY, division TEXT, gender TEXT, seed INTEGER,
  current_week INTEGER, total_weeks INTEGER, phase TEXT, champion TEXT
);
CREATE TABLE IF NOT EXISTS duals (
  id INTEGER PRIMARY KEY, season_id INTEGER, week INTEGER, round TEXT,
  conf TEXT, is_conf INTEGER, home TEXT, away TEXT, status TEXT,
  home_points INTEGER, away_points INTEGER, winner INTEGER, lines_json TEXT,
  round_no INTEGER DEFAULT 0, bpos INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_duals_season ON duals(season_id, round, week);
CREATE TABLE IF NOT EXISTS injuries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  season_id INTEGER, pid TEXT, school TEXT, name TEXT,
  week INTEGER DEFAULT 0, tag TEXT,
  total INTEGER DEFAULT 0, duals_remaining INTEGER DEFAULT 0,
  season_ending INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_injuries_season ON injuries(season_id, school);
"""


_schema_ready_for = None        # the DB_PATH the schema was last created for


def init_schema() -> None:
    """Eagerly create schema + column migrations (auto-committing connection)
    so the lazy path never writes inside a held transaction — the cause of the
    'database is locked' 500s during sim."""
    global _schema_ready_for
    conn = dbpath.connect(DB_PATH)
    # The injuries table grew from a per-pid state row into an event log (id/name/
    # week/tag/total). Drop the old shape so the richer CREATE below takes effect —
    # injury state is per-save and cheap to re-accrue, never authoritative history.
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(injuries)").fetchall()}
        if cols and "total" not in cols:
            conn.execute("DROP TABLE injuries")
    except sqlite3.OperationalError:
        pass
    conn.executescript(_SCHEMA)
    for col in ("round_no INTEGER DEFAULT 0", "bpos INTEGER DEFAULT 0"):
        try:
            conn.execute(f"ALTER TABLE duals ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
    _schema_ready_for = DB_PATH


def _db() -> sqlite3.Connection:
    """Tuned connection (WAL + busy timeout). Schema is created once per (path),
    eagerly, so read helpers don't take a write lock while a sim holds one open.
    Keyed on DB_PATH so tests that repoint the DB still get a schema."""
    if _schema_ready_for != DB_PATH:
        init_schema()
    return dbpath.connect(DB_PATH)


def _dual_seed(seed: int, home: str, away: str, tag: str) -> int:
    raw = f"{seed}|{home}|{away}|{tag}".encode()
    return int.from_bytes(hashlib.blake2s(raw, digest_size=4).digest(), "big")


# --------------------------------------------------------------------------
# Schedule generation
# --------------------------------------------------------------------------

def _gen_regular_schedule(div, seed: int):
    import random
    rng = random.Random(f"{seed}|sched")
    school_conf = {p.school: p.conf for p in div.programs}

    conf_games = []
    conf_count = {p.school: 0 for p in div.programs}
    conf_meet: dict = {}      # unordered pair -> times scheduled (cap repeats)

    # Aim each team's conference slate at CONF_SHARE of the target. A round-robin
    # (double under 10 teams) is the base; for leagues too small to reach the
    # share that way we pad with extra intra-conference duals beyond the
    # round-robin (deliberately not a clean round-robin — the point is more
    # conference results, not symmetry).
    conf_target = min(round(TARGET_DUALS * CONF_SHARE), TARGET_DUALS - NONCONF_MIN)
    for name, members in div.conferences.items():
        schools = [p.school for p in members]
        n = len(schools)
        if n < 2:
            continue
        double = n < CONF_DOUBLE_MAX

        def add_meeting(x, y):
            conf_games.append((x, y, name))
            conf_count[x] += 1
            conf_count[y] += 1
            k = (x, y) if x < y else (y, x)
            conf_meet[k] = conf_meet.get(k, 0) + 1

        base_pairs = [(schools[i], schools[j])
                      for i in range(n) for j in range(i + 1, n)]
        for (x, y) in base_pairs:
            add_meeting(x, y)
            if double:
                add_meeting(y, x)            # home-and-away

        base_per_team = (n - 1) * (2 if double else 1)
        if conf_target > base_per_team:
            pool = base_pairs[:]
            rng.shuffle(pool)
            changed = True
            while changed:
                changed = False
                for (x, y) in pool:
                    if conf_count[x] >= conf_target or conf_count[y] >= conf_target:
                        continue
                    k = (x, y) if x < y else (y, x)
                    if conf_meet.get(k, 0) >= MAX_CONF_MEETINGS:
                        continue
                    add_meeting(y, x)        # alternate the host on the repeat
                    changed = True

    allschools = [p.school for p in div.programs]
    prestige = {p.school: getattr(p, "prestige", 0.5) for p in div.programs}
    # Non-conference just fills the rest of the slate up to the target, so the
    # total stays ~TARGET_DUALS while conference carries the larger share.
    want = {s: max(0, TARGET_DUALS - conf_count[s]) for s in allschools}
    pairs = set()
    nonconf = []
    order = allschools[:]
    rng.shuffle(order)

    def _accept(s, o) -> float:
        """Preference weight for s scheduling o non-conference. Powerhouses load
        up on mid/low-majors (and host them); they rarely play each other in the
        regular season because a loss dents record + seeding. Used as a weight,
        never a hard reject, so every team still fills its slate."""
        ps, po = prestige[s], prestige[o]
        if ps > 0.62 and po > 0.62:
            return 0.05                         # two heavyweights — almost never
        gap = ps - po
        if gap > 0.08:
            return 0.92                         # classic cupcake / regional draw
        if gap < -0.08:
            return 0.45                         # scheduling up (guarantee game)
        return 0.55                             # non-elite peers

    # Greedy fill: each round every still-short team takes its best available
    # partner (different conference, not already paired), preferring the prestige
    # match-ups above while biasing toward whoever else still needs games. This
    # reliably converges to the per-team targets instead of falling short.
    remaining = dict(want)
    for _round in range(TARGET_DUALS + 4):
        progressed = False
        for s in order:
            if remaining[s] <= 0:
                continue
            best, best_w = None, -1.0
            for o in order:
                if o == s or remaining[o] <= 0 or school_conf[o] == school_conf[s]:
                    continue
                if (s, o) in pairs or (o, s) in pairs:
                    continue
                w = _accept(s, o) * (1.0 + 0.10 * remaining[o]) * (0.85 + 0.30 * rng.random())
                if w > best_w:
                    best_w, best = w, o
            if best is None:
                continue
            pairs.add((s, best))
            remaining[s] -= 1
            remaining[best] -= 1
            # The stronger program almost always hosts; the cupcake travels.
            host_strong = prestige[s] >= prestige[best]
            if rng.random() < 0.8:
                home, away = (s, best) if host_strong else (best, s)
            else:
                home, away = (best, s) if host_strong else (s, best)
            nonconf.append((home, away, None))
            progressed = True
        if not progressed:
            break

    # Assign to weeks: non-conf front-loaded from week 1, then each team's
    # conference play gated behind *its own* last non-conf week (not a global
    # barrier) so the slate packs to ~2 duals/week and the season stays ~13-14
    # weeks instead of stretching out.
    rng.shuffle(conf_games)
    rows = []
    cnt: dict = {}        # (week, team) -> duals that week
    used: set = set()     # (week, home, away) — no repeat pairing in a week
    nc_last: dict = {}    # team -> last week it plays a non-conference dual

    def place(h, a, cn, floor):
        w = floor
        while (cnt.get((w, h), 0) >= MAX_PER_WEEK or cnt.get((w, a), 0) >= MAX_PER_WEEK
               or (w, h, a) in used or (w, a, h) in used):
            w += 1
        cnt[(w, h)] = cnt.get((w, h), 0) + 1
        cnt[(w, a)] = cnt.get((w, a), 0) + 1
        used.add((w, h, a))
        rows.append((w, h, a, cn))
        return w

    for (h, a, cn) in nonconf:
        w = place(h, a, cn, 1)
        nc_last[h] = max(nc_last.get(h, 0), w)
        nc_last[a] = max(nc_last.get(a, 0), w)
    for (h, a, cn) in conf_games:
        place(h, a, cn, max(nc_last.get(h, 0), nc_last.get(a, 0)) + 1)
    return rows


def create_season(division: str = "D1", gender: str = "men", *, seed: int = 2026) -> int:
    div = load_division(division, gender)
    rows = _gen_regular_schedule(div, seed)
    # Divisions that run the ITA opener push their regular slate back so the Kickoff
    # Weekend + Indoor occupy the first weeks; the season then starts in the ITA
    # phase rather than the regular season (see `advance`). D1 opens on the Kickoff
    # Weekend; D2/D3 have no Kickoff, opening straight on their top-8 Indoor.
    lead = ita.lead_weeks(division)
    if lead:
        rows = [(w + lead, h, a, cn) for (w, h, a, cn) in rows]
    total_weeks = max((r[0] for r in rows), default=0)
    phase = ("ita_kickoff" if ita.runs_kickoff(division)
             else "ita_indoor" if ita.runs_indoor(division) else "regular")
    first_reg_week = lead + 1
    conn = _db()
    cur = conn.execute(
        "INSERT INTO seasons (division, gender, seed, current_week, total_weeks, phase, champion)"
        " VALUES (?,?,?,?,?,?,?)",
        (division, gender, seed, first_reg_week, total_weeks, phase, None))
    sid = cur.lastrowid
    conn.executemany(
        "INSERT INTO duals (season_id, week, round, conf, is_conf, home, away, status,"
        " home_points, away_points, winner, lines_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [(sid, w, "REG", cn, 1 if cn else 0, h, a, "scheduled", None, None, None, None)
         for (w, h, a, cn) in rows])
    conn.commit()
    conn.close()
    # Draw the ITA opener's first fixtures (scheduled, unplayed) so the bracket is
    # visible before it's advanced. Done AFTER the season is committed, in its own
    # transaction: _ita_ranking opens a second connection (and may create config tables
    # on a fresh DB), which would deadlock against this still-open write transaction.
    _draw_opening_fixtures(division, gender, seed, sid)
    return sid


def _draw_opening_fixtures(division: str, gender: str, seed: int, sid: int) -> None:
    """Seed the ITA opener's visible round-1 fixtures: the Kickoff sites for D1, the
    top-8 Indoor for D2/D3. Its own short transaction (see `create_season`)."""
    if not ita.runs_indoor(division):
        return
    s0 = {"id": sid, "division": division, "gender": gender, "seed": seed}
    conn = _db()
    try:
        _draw_kickoff(conn, s0) if ita.runs_kickoff(division) else _draw_indoor(conn, s0)
        conn.commit()
    finally:
        conn.close()


def get_or_create(division: str = "D1", gender: str = "men", *, seed: int = 2026) -> int:
    conn = _db()
    row = conn.execute("SELECT id FROM seasons WHERE division=? AND gender=? AND seed=?",
                       (division, gender, seed)).fetchone()
    conn.close()
    if row:
        return row["id"]
    return create_season(division, gender, seed=seed)


def find_season(division: str, gender: str, *, seed: int) -> int | None:
    """The season id for (division, gender, seed) if it already exists — WITHOUT
    creating one. Used to read a past world-year's stored season (its duals/bracket
    survive the rollover under that year's seed)."""
    conn = _db()
    row = conn.execute("SELECT id FROM seasons WHERE division=? AND gender=? AND seed=?",
                       (division, gender, seed)).fetchone()
    conn.close()
    return row["id"] if row else None


def load_season(season_id: int) -> dict | None:
    conn = _db()
    row = conn.execute("SELECT * FROM seasons WHERE id=?", (season_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_seasons() -> list[dict]:
    conn = _db()
    rows = conn.execute("SELECT * FROM seasons ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Advancing the season
# --------------------------------------------------------------------------

def _programs(division: str, gender: str) -> dict:
    return {p.school: p for p in load_division(division, gender).programs}


_forced_cache: dict = {}


def _forced_for(conn, s, progs, school) -> dict:
    """Cached per-team ``dual_id -> {pid}`` playing-time guarantee. Every roster
    player is assigned one regular-season dual; weakest players get the most
    favorable (weakest-opponent) duals, so the bench plays up in non-conference.
    Spread across all of a team's duals so each carries at most ~one guaranteed
    player. Keyed by dual id (a team can play two duals in a week)."""
    from .ncaa import build_roster
    key = (s["seed"], s["division"], s["gender"], school)
    out = _forced_cache.get(key)    # .get + local return: world-advance clears this
    if out is None:                 # from another thread (world.py/state.py)
        rows = conn.execute(
            "SELECT id, home, away FROM duals WHERE season_id=? AND round='REG'"
            " AND (home=? OR away=?) ORDER BY week, id",
            (s["id"], school, school)).fetchall()
        duals = []
        for r in rows:
            opp = r["away"] if r["home"] == school else r["home"]
            duals.append((r["id"], getattr(progs.get(opp), "prestige", 0.5)))
        out = forced_appearances(progs[school], build_roster(progs[school]), duals)
        _forced_cache[key] = out
    return out


def _unavailable(conn, season_id, school) -> set:
    """Pids on `school` that are injured (out 1+ duals or season-ending) — to be
    dropped from this dual's lineup."""
    rows = conn.execute(
        "SELECT pid FROM injuries WHERE season_id=? AND school=?"
        " AND (season_ending=1 OR duals_remaining>0)", (season_id, school)).fetchall()
    return {r["pid"] for r in rows}


def _recover_team(conn, season_id, school) -> None:
    """`school` just played a dual, so its injury clocks tick.

    Short-term injuries count DOWN while out (duals_remaining > 0). When one would
    reach zero the player is back — but rather than land on 0 it drops into a
    NEGATIVE "recovery grace" window (−RETURN_GRACE_DUALS): the player is available
    and plays, but the model treats them as freshly-returned and won't re-injure
    them, so we don't get instant re-injury chains. The grace window then ticks UP
    toward 0 (fully recovered). The row is kept throughout as the log entry.
    Season-ending injuries don't tick — they're out until a medical redshirt."""
    # 1) existing grace windows recover toward 0 (do this first so a row that drops
    #    into grace THIS dual isn't also ticked up in the same call)
    conn.execute(
        "UPDATE injuries SET duals_remaining=duals_remaining+1"
        " WHERE season_id=? AND school=? AND season_ending=0 AND duals_remaining<0",
        (season_id, school))
    # 2) active injuries burn a dual; one that heals drops straight into grace
    conn.execute(
        "UPDATE injuries SET duals_remaining = CASE WHEN duals_remaining-1<=0 THEN ?"
        " ELSE duals_remaining-1 END"
        " WHERE season_id=? AND school=? AND season_ending=0 AND duals_remaining>0",
        (-injuries.RETURN_GRACE_DUALS, season_id, school))


def _roll_new_injuries(conn, season_id, school, played_pids, roster, week=0, tag="") -> None:
    """After a dual, roll fresh injuries on exactly the players who competed.
    Players with an ACTIVE injury are skipped (they were filtered out and didn't
    play); healed log rows don't block a fresh injury. Each new injury is logged
    with the player's name, the week/round it happened, and its length."""
    if not injuries.is_enabled() or not played_pids:
        return
    by_pid = {p.pid: p for p in roster}
    # Injury-AWARE: skip anyone currently out (duals_remaining>0), season-ending, OR
    # in the post-return grace window (duals_remaining<0). A nonzero clock means the
    # model already knows they're hurt or just back — never injure on top of that.
    protected = {r["pid"] for r in conn.execute(
        "SELECT pid FROM injuries WHERE season_id=? AND school=?"
        " AND (season_ending=1 OR duals_remaining<>0)",
        (season_id, school)).fetchall()}
    for pid in played_pids:
        if pid in protected or pid not in by_pid:
            continue
        out = injuries.roll_injury(by_pid[pid])
        if out == 0:
            continue
        name = getattr(by_pid[pid], "name", "")
        if out == injuries.SEASON_ENDING:
            conn.execute(
                "INSERT INTO injuries"
                " (season_id, pid, school, name, week, tag, total, duals_remaining, season_ending)"
                " VALUES (?,?,?,?,?,?,?,?,1)", (season_id, pid, school, name, week, tag, 0, 0))
        else:
            conn.execute(
                "INSERT INTO injuries"
                " (season_id, pid, school, name, week, tag, total, duals_remaining, season_ending)"
                " VALUES (?,?,?,?,?,?,?,?,0)", (season_id, pid, school, name, week, tag, out, out))


def _play_and_store(conn, s, progs, dual_id, home, away, is_conf, tag, form=None,
                    best_six=False):
    # Playing-time guarantee: each team has one dual per roster player where that
    # player is seated into a completing slot (weakest players land in the most
    # favorable duals, so the bench plays up in non-conference).
    fh = _forced_for(conn, s, progs, home).get(dual_id)
    fa = _forced_for(conn, s, progs, away).get(dual_id)
    sid = s["id"]
    rec = dual_between(progs[home], progs[away],
                       seed=_dual_seed(s["seed"], home, away, tag), conf=bool(is_conf),
                       form=form, lineup_seed=s["seed"], forced_home=fh, forced_away=fa,
                       unavailable_home=_unavailable(conn, sid, home),
                       unavailable_away=_unavailable(conn, sid, away),
                       best_six=best_six)
    winner = 0 if rec["home_won"] else 1
    conn.execute("UPDATE duals SET status='final', home_points=?, away_points=?, winner=?,"
                 " lines_json=? WHERE id=?",
                 (rec["home_points"], rec["away_points"], winner, json.dumps(rec["lines"]), dual_id))
    # Injury bookkeeping: this dual counts as a dual of recovery for both teams'
    # short-term injuries, then roll fresh injuries on whoever just competed.
    from .ncaa import build_roster
    week = s.get("current_week", 0)
    _recover_team(conn, sid, home)
    _recover_team(conn, sid, away)
    _roll_new_injuries(conn, sid, home, rec.get("home_played"), build_roster(progs[home]), week, tag)
    _roll_new_injuries(conn, sid, away, rec.get("away_played"), build_roster(progs[away]), week, tag)
    return rec


def _completed(conn, season_id, rounds=("REG", "CT", "NCAA", "ITAK", "ITAI")) -> list[dict]:
    """All completed duals (any phase by default) as record dicts. The ITA Kickoff
    (``ITAK``) and Indoor (``ITAI``) opener counts toward the season record just like
    the conference tournaments and the NCAAs — but, like them, it is excluded from the
    regular-season Power Index (see ``_ranking_duals``)."""
    qs = ",".join("?" for _ in rounds)
    rows = conn.execute(
        f"SELECT home, away, round, is_conf, home_points, away_points, winner, lines_json"
        f" FROM duals WHERE season_id=? AND status='final' AND round IN ({qs})",
        (season_id, *rounds)).fetchall()
    out = []
    for r in rows:
        out.append({"home": r["home"], "away": r["away"], "round": r["round"],
                    "conf": bool(r["is_conf"]), "home_won": r["winner"] == 0,
                    "home_points": r["home_points"], "away_points": r["away_points"],
                    "lines": json.loads(r["lines_json"] or "[]")})
    return out


def _ranking_duals(conn, season_id) -> list[dict]:
    """The corpus that feeds the live Power Index: the regular season plus the ITA
    opener (which counts toward the rankings), but not the CT/NCAA brackets seeded
    from it."""
    return _completed(conn, season_id, RANKING_ROUNDS)


def _conf_standings(duals, div):
    wl = {}
    for d in duals:
        if not d["conf"]:
            continue
        for t in (d["home"], d["away"]):
            wl.setdefault(t, [0, 0])
        if d["home_won"]:
            wl[d["home"]][0] += 1; wl[d["away"]][1] += 1
        else:
            wl[d["away"]][0] += 1; wl[d["home"]][1] += 1
    return wl


def _winpct(wl, school):
    w, l = wl.get(school, [0, 0])
    return w / (w + l) if (w + l) else 0.0


def _pow2_le(n: int) -> int:
    p = 1
    while p * 2 <= n:
        p *= 2
    return p


def _round1_pairs(seeded: list[str]) -> list[tuple[int, str, str]]:
    n = _pow2_le(len(seeded))
    seeded = seeded[:n]
    pos = _seed_positions(n)
    slots = [seeded[i - 1] for i in pos]
    return [(k, slots[2 * k], slots[2 * k + 1]) for k in range(n // 2)]


# Bracketing penalties (lower total = more credible national draw). Seeding and
# bracketing are separate: teams are placed into the standard bracket by seed,
# then swapped WITHIN their seed band to avoid bad first-round matchups. The
# rematch penalty escalates with how often the teams already met — a single
# regular-season meeting stings, a third meeting is a near-veto.
#
# TRUE SEED (whole tournament, both genders, all divisions): the bracket is NOT
# rearranged to keep same-conference teams in separate regions. Real NCAA basketball
# separates a conference's top seeds because that sport is very top-heavy; this sim
# isn't, so the seed order the committee earned is honoured as-is. There is
# deliberately no same-conference penalty and no gender/seed conditional — the draw
# only avoids regular-season rematches and two conference champions (AQs) meeting in
# round one. See docs/AAR-true-seed-no-conference-separation.md.
_PEN_REMATCH = 2500        # met ONCE in the regular season
_PEN_MEET2 = 3000          # met TWICE — a heavier rematch
_PEN_MEET3 = 6000          # met THREE+ times — strongly avoid
_PEN_AQ_VS_AQ = 1000       # two conference champions against each other


def _meeting_penalty(times: int) -> int:
    """Escalating penalty for rematching teams that met `times` in the regular
    season (0 → none, 1 → rematch, 2 → heavier, 3+ → near-veto)."""
    if times >= 3:
        return _PEN_MEET3
    if times == 2:
        return _PEN_MEET2
    if times == 1:
        return _PEN_REMATCH
    return 0


def _pair_penalty(a, b, played_pairs, autobid_set: set) -> int:
    """Bracketing penalty for a first-round matchup: a regular-season rematch (scaled
    by how many times they met) or two conference champions (AQs) meeting in round
    one. `played_pairs` is a count map {frozenset(pair): meetings}. There is no
    same-conference term — the draw is true-seeded (see the module note above)."""
    if not a or not b:
        return 0
    s = _meeting_penalty(played_pairs.get(frozenset((a, b)), 0))
    if a in autobid_set and b in autobid_set:
        s += _PEN_AQ_VS_AQ
    return s


def _deconflict_playin(playin: list[str], played_pairs,
                       autobid_set: set) -> list[tuple[str, str]]:
    """Pair a play-in field high-vs-low (seed 33 v 96, 34 v 95, …), then swap the
    low-seed opponents among games — every game stays a high-vs-low matchup — to avoid
    rematch and AQ-vs-AQ first-rounders. The same bracketing rule the ≤64 main draw
    follows, extended to the >64 play-in round."""
    g = len(playin) // 2
    tops, bots = playin[:g], playin[g:]            # tops outrank every bot, so any pairing is high/low
    assign = list(range(g - 1, -1, -1))            # tops[i] meets bots[assign[i]] (reverse seed)

    def total():
        return sum(_pair_penalty(tops[i], bots[assign[i]], played_pairs, autobid_set)
                   for i in range(g))

    cur = total()
    for _ in range(60):                            # hill-climb on opponent swaps
        improved = False
        for i in range(g):
            for j in range(i + 1, g):
                assign[i], assign[j] = assign[j], assign[i]
                t = total()
                if t < cur:
                    cur, improved = t, True
                else:
                    assign[i], assign[j] = assign[j], assign[i]
        if not improved or cur == 0:
            break
    return [(tops[i], bots[assign[i]]) for i in range(g)]


def _seed_bracket(seeded: list[str], autobid_set: set,
                  played_pairs) -> list[tuple[int, str, str]]:
    """National-championship first round. Place the seeded field into the standard
    bracket (1-seed band vs 16-seed band, etc.), then minimise bracketing penalties
    by swapping teams WITHIN a seed band — preserving seed integrity — to avoid
    regular-season-rematch first-rounders and to keep two conference champions (AQs)
    from meeting in round one. The draw is true-seeded: it is NOT rearranged to keep
    same-conference teams apart."""
    n = _pow2_le(len(seeded))
    seeded = seeded[:n]
    pos = _seed_positions(n)                       # seed number (1..n) at each slot
    slots = [seeded[p - 1] for p in pos]           # baseline placement = pure seed
    lines = max(1, min(16, n // 2))                # seed lines (16 for a 64 field)
    band_size = max(1, n // lines)
    band = [(p - 1) // band_size for p in pos]     # seed band per bracket slot

    def total():
        return sum(_pair_penalty(slots[2 * k], slots[2 * k + 1], played_pairs, autobid_set)
                   for k in range(n // 2))

    cur = total()
    for _ in range(60):                            # hill-climb on same-band swaps
        improved = False
        for i in range(n):
            for j in range(i + 1, n):
                if band[i] != band[j]:
                    continue
                slots[i], slots[j] = slots[j], slots[i]
                t = total()
                if t < cur:
                    cur, improved = t, True
                else:
                    slots[i], slots[j] = slots[j], slots[i]
        if not improved or cur == 0:
            break
    return [(k, slots[2 * k], slots[2 * k + 1]) for k in range(n // 2)]


def _region_play_in(schools: list[str], played_pairs,
                    autobid_set: set) -> list[tuple[int, str, str]]:
    """The 96-team regional opening round. Split the national seed list into four
    24-team regions by S-curve, then in each region pair seed lines 9v24, 10v23,
    … 16v17 (deconflicted to dodge rematch / AQ openers). bpos is region-major
    (region r, game g → r*8 + g) so the winners come back grouped by region for the
    main draw."""
    out = []
    for r, members in enumerate(regions.scurve_regions(schools)):
        pairs = _deconflict_playin(members[8:24], played_pairs, autobid_set)
        for g, (h, a) in enumerate(pairs):
            out.append((r * 8 + g, h, a))
    return out


def _region_r16(byes: list[str], winners: list[str], played_pairs,
                autobid_set: set) -> list[tuple[str, str]]:
    """One region's 16-team bracket: bye seed BYE_SEQ[k] hosts the opening-round
    winner of line (17 − BYE_SEQ[k]). Every winner is lower-seeded than every bye,
    so we may swap which winner faces which bye (seed-safe) to minimise penalties."""
    base = [8 - s for s in regions.BYE_SEQ]        # canonical winner index per game k
    order = list(base)

    def total():
        return sum(_pair_penalty(byes[regions.BYE_SEQ[k] - 1], winners[order[k]],
                                 played_pairs, autobid_set) for k in range(8))

    cur = total()
    for _ in range(60):
        improved = False
        for i in range(8):
            for j in range(i + 1, 8):
                order[i], order[j] = order[j], order[i]
                t = total()
                if t < cur:
                    cur, improved = t, True
                else:
                    order[i], order[j] = order[j], order[i]
        if not improved or cur == 0:
            break
    return [(byes[regions.BYE_SEQ[k] - 1], winners[order[k]]) for k in range(8)]


def _region_main_draw(schools: list[str], winners: list[str],
                      played_pairs, autobid_set: set) -> list[tuple[int, str, str]]:
    """The 64-team main draw after the regional play-in: each region's eight byes
    plus its eight play-in winners, laid out as four 16-brackets concatenated in
    MAIN_DRAW_ORDER so the region champions meet in the national semifinals."""
    regs = regions.scurve_regions(schools)
    out = []
    for slot, r in enumerate(regions.MAIN_DRAW_ORDER):
        rw = winners[r * 8:(r + 1) * 8]            # this region's play-in winners (game order)
        for k, (h, a) in enumerate(_region_r16(regs[r][:8], rw, played_pairs, autobid_set)):
            out.append((slot * 8 + k, h, a))
    return out


def _region_main_draw_64(schools: list[str], played_pairs,
                         autobid_set: set) -> list[tuple[int, str, str]]:
    """A 64-team field by the same regional methodology, without a play-in: split
    into four S-curve regions of 16 (no byes — all 16 play), seed each region's
    16-bracket (within-band deconfliction preserved), and concatenate the four in
    MAIN_DRAW_ORDER so the region champions meet in the national semifinals."""
    regs = regions.scurve_regions(schools)
    out = []
    for slot, r in enumerate(regions.MAIN_DRAW_ORDER):
        for k, h, a in _seed_bracket(regs[r], autobid_set, played_pairs):
            out.append((slot * 8 + k, h, a))
    return out


def _insert_dual(conn, sid, week, rnd, conf, is_conf, round_no, bpos, home, away):
    conn.execute(
        "INSERT INTO duals (season_id, week, round, conf, is_conf, round_no, bpos, home, away,"
        " status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sid, week, rnd, conf, is_conf, round_no, bpos, home, away, "scheduled"))


def advance(season_id: int) -> dict:
    s = load_season(season_id)
    if not s or s["phase"] == "complete":
        return {"phase": "complete"}
    conn = _db()
    progs = _programs(s["division"], s["gender"])

    if s["phase"] == "ita_kickoff":
        out = _advance_kickoff_round(conn, s, progs)
        conn.commit(); conn.close()
        return out

    if s["phase"] == "ita_indoor":
        out = _advance_indoor_round(conn, s, progs)
        conn.commit(); conn.close()
        return out

    if s["phase"] == "fall_portal":
        # Standalone, the fall-portal hold is a transparent pass-through to the
        # regular season. The WORLD driver instead synchronises here: it SKIPS
        # fall_portal universes (never calling advance on them) so they all wait at
        # the post-ITA boundary while the cross-division portal is proposed and
        # committed; `world.commit_fall_portal` then sets phase='regular' directly.
        conn.execute("UPDATE seasons SET phase='regular' WHERE id=?", (season_id,))
        conn.commit(); conn.close()
        return advance(season_id)

    if s["phase"] == "regular":
        wk = s["current_week"]
        due = conn.execute("SELECT * FROM duals WHERE season_id=? AND round='REG' AND week=?"
                           " AND status='scheduled'", (season_id, wk)).fetchall()
        form = season_player_str(season_id)        # results so far drive this week's lineups
        for d in due:
            _play_and_store(conn, s, progs, d["id"], d["home"], d["away"], d["is_conf"],
                            f"reg{wk}", form=form)
        nxt = wk + 1
        phase = "regular" if nxt <= s["total_weeks"] else "conf_tournaments"
        conn.execute("UPDATE seasons SET current_week=?, phase=? WHERE id=?", (nxt, phase, season_id))
        conn.commit(); conn.close()
        return {"phase": "regular", "week": wk, "played": len(due), "next_phase": phase}

    if s["phase"] == "conf_tournaments":
        out = _advance_conf_round(conn, s, progs)
        conn.commit(); conn.close()
        return out

    if s["phase"] == "selection":
        # The bracket reveal is over — start the NCAAs and play the first round.
        conn.execute("UPDATE seasons SET phase='ncaa' WHERE id=?", (season_id,))
        out = _advance_ncaa_round(conn, load_season(season_id), progs)
        conn.commit(); conn.close()
        return out

    if s["phase"] == "ncaa":
        out = _advance_ncaa_round(conn, s, progs)
        conn.commit(); conn.close()
        return out

    conn.close()
    return {"phase": s["phase"]}


def _next_post_week(conn, sid):
    return (conn.execute("SELECT MAX(week) w FROM duals WHERE season_id=?", (sid,)).fetchone()["w"] or 0) + 1


def _sim_round(conn, s, progs, rnd_tag, round_no, prefix):
    """Sim all scheduled duals of one tournament round; return list of rows."""
    due = conn.execute("SELECT * FROM duals WHERE season_id=? AND round=? AND round_no=?"
                       " AND status='scheduled'", (s["id"], rnd_tag, round_no)).fetchall()
    form = season_player_str(s["id"])              # postseason lineups off full-season form
    # Elimination stakes: the conference tournament and the NCAA bracket field the
    # strict best six by form — no starter-resting, no bench reps, no coach noise
    # (owner rule 2027-07). The ITA events keep the normal rotation on purpose:
    # they're early-season tournaments where everyone is supposed to play.
    best_six = rnd_tag in ("CT", "NCAA")
    for d in due:
        _play_and_store(conn, s, progs, d["id"], d["home"], d["away"], d["is_conf"],
                        f"{prefix}{round_no}b{d['bpos']}", form=form, best_six=best_six)
    return due


def _advance_conf_round(conn, s, progs) -> dict:
    sid = s["id"]
    div = load_division(s["division"], s["gender"])
    wl = _conf_standings(_completed(conn, sid, ("REG",)), div)   # conference record: regular only
    ratings = compute_ratings(_ranking_duals(conn, sid))         # Power Index: regular + ITA
    existing = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND round='CT'",
                            (sid,)).fetchone()["c"]
    if existing == 0:                                  # seed round 1 for every conference
        week = _next_post_week(conn, sid)
        for conf, members in div.conferences.items():
            order = sorted(members, key=lambda p: (_winpct(wl, p.school),
                           ratings[p.school].pi if p.school in ratings else 0), reverse=True)
            field = _pow2_le(min(CONF_TOURNEY_FIELD, len(order)))
            if field < 2:
                continue
            for bpos, h, a in _round1_pairs([p.school for p in order[:field]]):
                _insert_dual(conn, sid, week, "CT", conf, 1, 1, bpos, h, a)
        round_no = 1
    else:
        row = conn.execute("SELECT MIN(round_no) r FROM duals WHERE season_id=? AND round='CT'"
                           " AND status='scheduled'", (sid,)).fetchone()
        round_no = row["r"]
    if round_no is None:
        return _finish_conf_phase(conn, s, div, wl)

    due = _sim_round(conn, s, progs, "CT", round_no, "ct")
    next_week = _next_post_week(conn, sid)
    for conf in {d["conf"] for d in due}:
        wins = conn.execute("SELECT home, away, winner FROM duals WHERE season_id=? AND round='CT'"
                            " AND conf=? AND round_no=? ORDER BY bpos", (sid, conf, round_no)).fetchall()
        winners = [w["home"] if w["winner"] == 0 else w["away"] for w in wins]
        if len(winners) > 1:
            for k in range(len(winners) // 2):
                _insert_dual(conn, sid, next_week, "CT", conf, 1, round_no + 1, k,
                             winners[2 * k], winners[2 * k + 1])
    remaining = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND round='CT'"
                             " AND status='scheduled'", (sid,)).fetchone()["c"]
    if remaining == 0:
        return _finish_conf_phase(conn, s, div, wl)
    return {"phase": "conf_tournaments", "round": round_no, "played": len(due)}


def _finish_conf_phase(conn, s, div, wl) -> dict:
    champions = {}
    for conf, members in div.conferences.items():
        last = conn.execute("SELECT home, away, winner FROM duals WHERE season_id=? AND round='CT'"
                            " AND conf=? ORDER BY round_no DESC, bpos ASC LIMIT 1",
                            (s["id"], conf)).fetchone()
        if last:
            champions[conf] = last["home"] if last["winner"] == 0 else last["away"]
        elif members:
            champions[conf] = max(members, key=lambda p: _winpct(wl, p.school)).school
    # Lock the autobids and pause at 'selection' — the bracket reveal. The field
    # is now set (champions + at-large by PI); the NCAAs begin on the next advance.
    conn.execute("UPDATE seasons SET phase='selection', champion=? WHERE id=?",
                 (json.dumps(champions), s["id"]))
    return {"phase": "conf_tournaments", "done": True, "champions": len(champions)}


def _ncaa_seeds(conn, s, progs, div):
    """Deterministically reproduce the seeded national field + bracketing context
    (autobids, regular-season pairings). Used to lay out the bracket and to rebuild
    the byes when a play-in feeds the main draw. Conference affiliation is NOT part
    of the bracketing context: the draw is true-seeded and never separates
    same-conference teams (see the bracketing-penalties note above)."""
    sid = s["id"]
    ratings = compute_ratings(_completed(conn, sid, SEED_ROUNDS))
    champions = [progs[v] for v in conf_champions(sid) if v in progs and v in ratings]
    # Select + seed by the Committee Seed Score (strength + résumé + AQ pedigree),
    # so power-conference champions are seeded above comparable at-large teams.
    seeded, autobids = select_field(div.programs, ratings, champions,
                                    size=field_for_division(s["division"]),
                                    score=committee_seed_score(sid, {c.school for c in champions}))
    schools = [p.school for p in seeded]
    autobid_set = {p.school for p in seeded if p.key in autobids}
    # COUNT regular-season meetings (not just whether they met) so the bracketer can
    # penalise a 2nd/3rd-meeting first-rounder harder than a single rematch.
    played = Counter(frozenset((d["home"], d["away"]))
                     for d in conn.execute("SELECT home, away FROM duals WHERE season_id=?"
                                           " AND round='REG' AND status='final'", (sid,)).fetchall())
    return schools, autobid_set, played


def _advance_ncaa_round(conn, s, progs) -> dict:
    sid = s["id"]
    div = load_division(s["division"], s["gender"])
    existing = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND round='NCAA'",
                            (sid,)).fetchone()["c"]
    if existing == 0:                                  # select + seed the national field
        schools, autobid_set, played = _ncaa_seeds(conn, s, progs, div)
        main = _pow2_le(len(schools))
        week = _next_post_week(conn, sid)
        if len(schools) == 96:
            # D1's 96-team field: four S-curve regions of 24. Top 8 per region get
            # byes; lines 9–24 play the regional opening round (9v24, …, 16v17).
            for bpos, h, a in _region_play_in(schools, played, autobid_set):
                _insert_dual(conn, sid, week, "NCAA", "First Round", 0, 1, bpos, h, a)
        elif len(schools) > main:
            # Other non-power-of-two field: a flat play-in (top seeds bye, 33 v 96, …).
            byes_n = 2 * main - len(schools)
            playin = schools[byes_n:]
            for i, (h, a) in enumerate(_deconflict_playin(playin, played, autobid_set)):
                _insert_dual(conn, sid, week, "NCAA", "First Round", 0, 1, i, h, a)
        elif len(schools) == 64:
            # D2/D3/D4: four S-curve regions of 16, no play-in (all 16 play).
            for bpos, h, a in _region_main_draw_64(schools, played, autobid_set):
                _insert_dual(conn, sid, week, "NCAA", "Round of 64", 0, 1, bpos, h, a)
        else:                                          # other clean power-of-two field
            for bpos, h, a in _seed_bracket(schools, autobid_set, played):
                _insert_dual(conn, sid, week, "NCAA", _round_name(len(schools)), 0, 1, bpos, h, a)
        round_no = 1
    else:
        round_no = conn.execute("SELECT MIN(round_no) r FROM duals WHERE season_id=? AND round='NCAA'"
                                " AND status='scheduled'", (sid,)).fetchone()["r"]

    due = _sim_round(conn, s, progs, "NCAA", round_no, "ncaa")
    wins = conn.execute("SELECT home, away, winner FROM duals WHERE season_id=? AND round='NCAA'"
                        " AND round_no=? ORDER BY bpos", (sid, round_no)).fetchall()
    winners = [w["home"] if w["winner"] == 0 else w["away"] for w in wins]

    # Play-in just finished → seed the main draw from the byes + play-in winners.
    if round_no == 1:
        schools, autobid_set, played = _ncaa_seeds(conn, s, progs, div)
        main = _pow2_le(len(schools))
        if len(schools) == 96:
            # Regional main draw: each region's byes + its play-in winners, four
            # 16-brackets laid out so the region champions meet in the semifinals.
            week = _next_post_week(conn, sid)
            for bpos, h, a in _region_main_draw(schools, winners, played, autobid_set):
                _insert_dual(conn, sid, week, "NCAA", "Round of 64", 0, 2, bpos, h, a)
            return {"phase": "ncaa", "round": 1, "round_name": "First Round", "played": len(due)}
        if len(schools) > main:
            byes_n = 2 * main - len(schools)
            r64 = schools[:byes_n] + winners           # byes (top seeds) + play-in winners
            week = _next_post_week(conn, sid)
            for bpos, h, a in _seed_bracket(r64, autobid_set, played):
                _insert_dual(conn, sid, week, "NCAA", _round_name(len(r64)), 0, 2, bpos, h, a)
            return {"phase": "ncaa", "round": 1, "round_name": "First Round", "played": len(due)}

    if len(winners) > 1:
        week = _next_post_week(conn, sid)
        alive = len(winners)
        for k in range(len(winners) // 2):
            _insert_dual(conn, sid, week, "NCAA", _round_name(alive), 0, round_no + 1, k,
                         winners[2 * k], winners[2 * k + 1])
        return {"phase": "ncaa", "round": round_no, "round_name": _round_name(alive * 2),
                "played": len(due)}
    champ = winners[0]
    conn.execute("UPDATE seasons SET phase='complete', champion=? WHERE id=?", (champ, sid))
    return {"phase": "ncaa", "champion": champ}


def _round_name(alive: int) -> str:
    return ROUND_NAMES.get(alive, f"Round of {alive}")


# --------------------------------------------------------------------------
# ITA Kickoff Weekend + National Team Indoor Championship (the season opener)
# --------------------------------------------------------------------------

def _ita_ranking(s) -> list[str]:
    """Schools best-first for the ITA seedings. Uses the prior world-year's final
    ranking — the Power Index over that season's completed duals — when a completed
    prior season exists (its seed is this year's seed minus the per-year stride);
    otherwise, in year 0 with no season to rank from, roster **Power 6**."""
    div = load_division(s["division"], s["gender"])
    prior_sid = find_season(s["division"], s["gender"], seed=s["seed"] - 1000)
    if prior_sid is not None:
        prior = load_season(prior_sid)
        if prior and prior["phase"] == "complete":
            conn = _db()
            ratings = compute_ratings(_completed(conn, prior_sid, SEED_ROUNDS))
            conn.close()
            rated = [p for p in div.programs if p.school in ratings]
            if rated:
                return [p.school for p in
                        sorted(rated, key=lambda p: ratings[p.school].pi, reverse=True)]
    return [p.school for p in sorted(div.programs, key=ita.power6, reverse=True)]


def _draw_kickoff(conn, s) -> None:
    """Draw the Kickoff Weekend round-1 fixtures (scheduled, unplayed) so the bracket
    is visible before it's played. Idempotent — a no-op once any ITAK dual exists."""
    sid = s["id"]
    if conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND round='ITAK'",
                    (sid,)).fetchone()["c"]:
        return
    for k, site in enumerate(ita.kickoff_sites(_ita_ranking(s))):
        label = f"Site {k + 1}"
        for m, (h, a) in enumerate(ita.site_pairs(site)):
            _insert_dual(conn, sid, 1, "ITAK", label, 0, 1, k * 2 + m, h, a)


def _draw_indoor(conn, s) -> None:
    """Draw the Indoor round-1 fixtures (scheduled, unplayed). D1's field is the
    Kickoff site winners; D2/D3 is the top 8 by prior-year ranking. Idempotent."""
    sid = s["id"]
    if conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND round='ITAI'",
                    (sid,)).fetchone()["c"]:
        return
    div = s["division"]
    winners = _site_winners(conn, sid) if ita.runs_kickoff(div) else []
    field = ita.indoor_field(winners, _ita_ranking(s), ita.indoor_size(div))
    week = ita.kickoff_rounds(div) + 1
    for bpos, h, a in _round1_pairs(field):
        _insert_dual(conn, sid, week, "ITAI", _round_name(len(field)), 0, 1, bpos, h, a)


def _advance_kickoff_round(conn, s, progs) -> dict:
    """Play one round of the ITA Kickoff Weekend — the site semifinals (round 1) then
    the site finals (round 2) — and draw the next round's fixtures so they're visible
    before being played. The site winners go on to the Indoor."""
    sid = s["id"]
    _draw_kickoff(conn, s)                              # ensure round-1 fixtures exist
    round_no = conn.execute("SELECT MIN(round_no) r FROM duals WHERE season_id=? AND round='ITAK'"
                            " AND status='scheduled'", (sid,)).fetchone()["r"]
    if round_no is None:                               # nothing left → enter the Indoor
        conn.execute("UPDATE seasons SET phase='ita_indoor' WHERE id=?", (sid,))
        _draw_indoor(conn, s)
        return {"phase": "ita_kickoff", "done": True}

    due = _sim_round(conn, s, progs, "ITAK", round_no, "itak")
    if round_no == 1:                                  # site semifinals done → draw site finals
        n_sites = conn.execute("SELECT COUNT(DISTINCT conf) c FROM duals WHERE season_id=?"
                               " AND round='ITAK'", (sid,)).fetchone()["c"]
        for k in range(n_sites):
            label = f"Site {k + 1}"
            wins = conn.execute("SELECT home, away, winner FROM duals WHERE season_id=? AND round='ITAK'"
                                " AND conf=? AND round_no=1 ORDER BY bpos", (sid, label)).fetchall()
            winners = [w["home"] if w["winner"] == 0 else w["away"] for w in wins]
            if len(winners) == 2:
                _insert_dual(conn, sid, 2, "ITAK", label, 0, 2, k, winners[0], winners[1])
    else:                                              # site finals done → enter Indoor, draw it
        conn.execute("UPDATE seasons SET phase='ita_indoor' WHERE id=?", (sid,))
        _draw_indoor(conn, s)
    return {"phase": "ita_kickoff", "round": round_no, "played": len(due)}


def _site_winners(conn, sid) -> list[str]:
    """The site champions — each site final's (round_no=2) winner, in site order."""
    rows = conn.execute("SELECT home, away, winner FROM duals WHERE season_id=? AND round='ITAK'"
                        " AND round_no=2 AND status='final' ORDER BY bpos", (sid,)).fetchall()
    return [r["home"] if r["winner"] == 0 else r["away"] for r in rows]


def _advance_indoor_round(conn, s, progs) -> dict:
    """One round of the ITA National Team Indoor Championship — a seeded single-elim
    run akin to the NCAAs. D1's draw is 16 teams (one per Kickoff site); the D2/D3
    draws are simply the top 8 by prior-year ranking. On the final, the season rolls
    into its regular-season opener."""
    sid = s["id"]
    div = s["division"]
    kickoff_lead = ita.kickoff_rounds(div)
    _draw_indoor(conn, s)                              # ensure round-1 fixtures exist
    round_no = conn.execute("SELECT MIN(round_no) r FROM duals WHERE season_id=? AND round='ITAI'"
                            " AND status='scheduled'", (sid,)).fetchone()["r"]
    if round_no is None:
        return _finish_indoor(conn, s)

    due = _sim_round(conn, s, progs, "ITAI", round_no, "itai")
    wins = conn.execute("SELECT home, away, winner FROM duals WHERE season_id=? AND round='ITAI'"
                        " AND round_no=? ORDER BY bpos", (sid, round_no)).fetchall()
    winners = [w["home"] if w["winner"] == 0 else w["away"] for w in wins]
    if len(winners) > 1:
        week = kickoff_lead + round_no + 1
        alive = len(winners)
        for k in range(len(winners) // 2):
            _insert_dual(conn, sid, week, "ITAI", _round_name(alive), 0, round_no + 1, k,
                         winners[2 * k], winners[2 * k + 1])
        return {"phase": "ita_indoor", "round": round_no, "round_name": _round_name(alive * 2),
                "played": len(due)}
    return _finish_indoor(conn, s, champion=winners[0] if winners else None)


def _finish_indoor(conn, s, champion: str | None = None) -> dict:
    """Close the ITA opener. With the fall portal enabled the season HOLDS in
    'fall_portal' (the world-level reshuffle runs, then releases it to 'regular');
    otherwise it goes straight to the regular season. Either way `current_week` is
    pre-set to the offset first regular-season week, so the release is a no-op bump."""
    nxt = "fall_portal" if FALL_PORTAL_ENABLED else "regular"
    conn.execute("UPDATE seasons SET phase=?, current_week=? WHERE id=?",
                 (nxt, ita.lead_weeks(s["division"]) + 1, s["id"]))
    return {"phase": "ita_indoor", "done": True, "indoor_champion": champion}


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------

def standings(season_id: int) -> dict:
    s = load_season(season_id)
    div = load_division(s["division"], s["gender"])
    conn = _db()
    duals = _completed(conn, season_id)        # overall counts every phase, incl. postseason
    conn.close()
    ov, cf = {}, {}
    for d in duals:
        for t in (d["home"], d["away"]):
            ov.setdefault(t, [0, 0]); cf.setdefault(t, [0, 0])
        hw = d["home_won"]
        ov[d["home"]][0 if hw else 1] += 1
        ov[d["away"]][1 if hw else 0] += 1
        if d["round"] == "REG" and d["conf"]:   # conference record is regular-season only
            cf[d["home"]][0 if hw else 1] += 1
            cf[d["away"]][1 if hw else 0] += 1
    def _pct(rec):
        w, l = rec
        return w / (w + l) if (w + l) else 0.0

    out = {}
    for conf, members in div.conferences.items():
        # Order like a real NCAA conference table: by conference win %, then
        # conference margin, then overall win % as the tiebreaker.
        table = sorted(members, key=lambda p: (
            _pct(cf.get(p.school, [0, 0])),
            cf.get(p.school, [0, 0])[0] - cf.get(p.school, [0, 0])[1],
            _pct(ov.get(p.school, [0, 0])),
            ov.get(p.school, [0, 0])[0] - ov.get(p.school, [0, 0])[1],
        ), reverse=True)
        out[conf] = [{"school": p.school, "ow": ov.get(p.school, [0, 0])[0],
                      "ol": ov.get(p.school, [0, 0])[1], "cw": cf.get(p.school, [0, 0])[0],
                      "cl": cf.get(p.school, [0, 0])[1], "autobid": p.autobid} for p in table]
    return out


def _reg_conf_champions(season_id: int) -> set:
    """Every regular-season conference champion — by conference win %, with NO
    tiebreaker, so teams tied atop a conference are ALL co-champions."""
    champs: set = set()
    for rows in standings(season_id).values():
        best = -1.0
        for r in rows:
            g = r["cw"] + r["cl"]
            if g and r["cw"] / g > best:
                best = r["cw"] / g
        if best < 0:
            continue
        for r in rows:
            g = r["cw"] + r["cl"]
            if g and r["cw"] / g == best:
                champs.add(r["school"])
    return champs


def season_program_result(season_id: int, school: str) -> dict | None:
    """A program's one-season summary for its history: overall record, conference,
    regular-season + conference-tournament titles, and the furthest NCAA / ITA Indoor
    round reached (champion / runner-up special-cased). None if the team has no
    completed duals that season. `ncaa` is only resolved once the season is complete."""
    s = load_season(season_id)
    if not s:
        return None
    div = load_division(s["division"], s["gender"])
    prog = div.by_school(school)
    if prog is None:
        return None
    conn = _db()
    duals = conn.execute(
        "SELECT round, conf, round_no, home, away, winner FROM duals WHERE season_id=?"
        " AND status='final' AND (home=? OR away=?)", (season_id, school, school)).fetchall()
    if not duals:
        conn.close()
        return None

    def won(d) -> bool:
        return (d["winner"] == 0 and d["home"] == school) or (d["winner"] == 1 and d["away"] == school)

    wins = sum(1 for d in duals if won(d))

    def furthest(tag, labels, champ_label, runner_label):
        rs = [d for d in duals if d["round"] == tag]
        if not rs:
            return None
        top = conn.execute("SELECT MAX(round_no) m FROM duals WHERE season_id=? AND round=?",
                           (season_id, tag)).fetchone()["m"]
        last = max(rs, key=lambda d: d["round_no"])
        if last["round_no"] == top:
            return champ_label if won(last) else runner_label
        return labels.get(last["conf"], last["conf"])

    complete = s["phase"] == "complete"
    ncaa = furthest("NCAA", NCAA_ROUND_LABEL, "🏆 National Champion", "🥈 National Runner-Up") if complete else None
    ita = furthest("ITAI", {}, "Preseason NIT Champion", "Preseason NIT Runner-Up")
    # Regional champion = won the Elite Eight (the regional final), i.e. reached the
    # Final Four / national semifinals (`Semifinals` round). Each region crowns one.
    regional_champ = any(d["round"] == "NCAA" and d["conf"] == "Semifinals" for d in duals)
    conn.close()

    return {
        "conf": prog.conf_abbr,
        "wins": wins, "losses": len(duals) - wins,
        "reg_conf_champ": school in _reg_conf_champions(season_id),
        "ct_champ": school in conf_champions(season_id),
        "ncaa": ncaa,
        "ita": ita,
        "national_champ": national_champion(season_id) == school,
        "indoor_champ": indoor_champion(season_id) == school,
        "regional_champ": regional_champ,
        "live": not complete,
    }


def ncaa_participants(season_id: int) -> set[str]:
    """Schools that made the NCAA field (appeared in any NCAA dual)."""
    conn = _db()
    rows = conn.execute(
        "SELECT home FROM duals WHERE season_id=? AND round='NCAA'"
        " UNION SELECT away FROM duals WHERE season_id=? AND round='NCAA'",
        (season_id, season_id)).fetchall()
    conn.close()
    return {r[0] for r in rows}


def ncaa_semifinalists(season_id: int) -> set[str]:
    """The four region champions — schools that reached the Final Four (Semifinals)."""
    conn = _db()
    rows = conn.execute("SELECT home, away FROM duals WHERE season_id=? AND round='NCAA'"
                        " AND conf='Semifinals'", (season_id,)).fetchall()
    conn.close()
    out: set[str] = set()
    for r in rows:
        out.add(r["home"]); out.add(r["away"])
    return out


# Below this many games per team the Power Index is too noisy to project a field;
# the Bubble Watch stays hidden until the season has run a few weeks.
BUBBLE_MIN_GAMES = 5


def _games_played(rec: str) -> int:
    try:
        w, l = rec.split("-")
        return int(w) + int(l)
    except (ValueError, AttributeError):
        return 0


# --- Committee seed score ----------------------------------------------------
# The selection committee is not a single sort. It blends three signals — base
# strength (Power Index), recent résumé (ITA-style points), and championship
# pedigree (the AQ bonus, tiered by how strong the conference is) — exactly the way
# a human committee weighs "how good are you", "what have you done", and "did you win
# something". A power-conference champion gets the biggest AQ bonus, so it seeds
# above a comparable at-large; a low-major AQ gets only a token bump.
#
# Conference tiers = the master 4-tier hierarchy (ncaa.CONF_TIER): Blue Blood
# (top) / Major / Mid / Low. For D1 we read the canonical hand-curated map so the
# seeding bonus agrees exactly with the recruiting-budget tiers; for D2–D4 (which
# have no curated tier list) we fall back to a prestige-percentile split so the
# bonus still travels. AQ bonus is tiered: a Blue Blood champion's title is worth
# far more pedigree than a low-major's. "Power" = top + major.
_CONF_TIER_PCTL = [(0.78, "top"), (0.55, "major"), (0.30, "mid"), (0.0, "low")]
_AQ_BONUS = {"top": 100.0, "major": 65.0, "mid": 35.0, "low": 12.0}
POWER_TIERS = {"top", "major"}

# Committee Seed Score weights (must sum to 1.0).
_W_PI, _W_PTS, _W_AQ, _W_RESUME = 0.45, 0.30, 0.15, 0.10


def _conf_tier_map(division: str, gender: str) -> dict:
    """{conf_abbr: tier} where tier ∈ top/major/mid/low. D1 uses the canonical
    ncaa.CONF_TIER map (so seeding tiers match the recruiting-budget tiers); other
    divisions fall back to a prestige-percentile split among their conferences."""
    from .ncaa import conf_prestige, CONF_TIER
    confs = {p.conf_abbr for p in load_division(division, gender).programs}
    if division == "D1":
        return {c: CONF_TIER.get(c, "low") for c in confs}
    ranked = sorted(confs, key=lambda c: conf_prestige(c, division), reverse=True)
    n = max(1, len(ranked))
    out = {}
    for i, c in enumerate(ranked):
        pctl = (n - i) / n
        out[c] = next(tier for tier_cut, tier in _CONF_TIER_PCTL if pctl >= tier_cut)
    return out


def committee_seed_score(season_id: int, aq_set: set) -> dict:
    """The committee's seed value per team: a weighted blend, NOT a single ranking.

        45%  Power Index rank      — base strength ("how good are you")
        30%  ITA-points rank       — résumé / recent results ("what have you done")
        15%  AQ bonus (tiered)     — championship pedigree ("did you win something")
        10%  recent form           — last-five record ("are you hot right now")

    Each rank is turned into a 0–100 score (#1 ≈ 100, last ≈ 0). `aq_set` is the
    schools holding automatic bids; only they earn the AQ bonus. The same score is
    used to SELECT at-large teams and to SEED the whole field, so a power-conference
    champion can out-seed a comparable at-large without anyone hand-sorting it."""
    pi = power_index(season_id)
    if not pi:
        return {}
    pts = ita_team_points(season_id)
    s = load_season(season_id)
    div = load_division(s["division"], s["gender"])
    conf_of = {p.school: p.conf_abbr for p in div.programs}
    tier_of = _conf_tier_map(s["division"], s["gender"])
    form = team_form(season_id)
    schools = list(pi.keys())
    n = max(1, len(schools))
    pi_rank = {sc: i + 1 for i, sc in enumerate(
        sorted(schools, key=lambda x: pi[x].pi, reverse=True))}
    # Rank ONLY teams that actually have ITA points. ita_team_points deliberately
    # omits teams with no quality wins, so default them to 0.0 — but a 0.0 team must
    # NOT get a unique rank by dict order. Every point-less team shares the floor
    # rank `n` below (`.get(sc, n)`), so their 30% résumé component is identical
    # rather than an arbitrary spread.
    pts_rank = {sc: i + 1 for i, sc in enumerate(
        sorted((sc for sc in schools if pts.get(sc, 0.0) > 0.0),
               key=lambda x: pts[x], reverse=True))}

    def rank_score(rank: int) -> float:
        return 100.0 * (n - rank + 1) / n               # #1 ≈ 100, last ≈ ~0

    def recent(sc: str) -> float:
        f = form.get(sc) or {}
        l5 = f.get("last5") or ""
        return 100.0 * l5.count("W") / len(l5) if l5 else 50.0

    out = {}
    for sc in schools:
        aqb = 0.0
        if sc in aq_set:
            aqb = _AQ_BONUS[tier_of.get(conf_of.get(sc, ""), "low")]
        out[sc] = (_W_PI * rank_score(pi_rank[sc])
                   + _W_PTS * rank_score(pts_rank.get(sc, n))
                   + _W_AQ * aqb
                   + _W_RESUME * recent(sc))
    return out



def _conf_leaders(div, cf: dict, ratings: dict) -> set[str]:
    """Projected automatic qualifiers — the team currently atop each conference
    (by conference record, Power Index as the tiebreak), as the race stands. Only
    conferences that award an automatic bid contribute one."""
    aq: set[str] = set()
    for members in div.conferences.values():
        elig = [p for p in members if p.school in ratings]
        if not elig:
            continue
        leader = max(elig, key=lambda p: (cf.get(p.school, [0, 0])[0] - cf.get(p.school, [0, 0])[1],
                                          ratings[p.school].pi))
        if leader.autobid:
            aq.add(leader.school)
    return aq


def _project(season_id: int, size: int | None = None, edge: int = 4) -> dict | None:
    """Core field projection shared by `bubble_watch` and `field_projection`.

    Projects this tournament's NCAA field "if it were held today". Each (division,
    gender) season is its own separate tournament, so the projection is naturally
    scoped to it. Selection mirrors the real format and the engine's own bracket
    logic (`select_field`): projected conference leaders take the automatic bids,
    then the remaining at-large spots are filled by the ITA team-ranking points
    (`ita_team_points`), the same metric the bracket seeds by. Returns None until
    enough duals are final for the projection to mean anything (or when the field
    would swallow everyone)."""
    s = load_season(season_id)
    if not s:
        return None
    if size is None:
        size = field_for_division(s["division"])
    ratings = power_index(season_id)
    if not ratings:
        return None
    div = load_division(s["division"], s["gender"])
    rated = [p for p in div.programs if p.school in ratings]
    field = clamp_field(min(size, len(rated)))
    # Too early, or the field swallows everyone (no real bubble) → nothing to show.
    if max((_games_played(ratings[p.school].record) for p in rated), default=0) < BUBBLE_MIN_GAMES:
        return None
    if len(rated) <= field + edge:
        return None

    conn = _db()
    cf: dict = {}
    for d in _completed(conn, season_id, ("REG",)):
        if not d["conf"]:
            continue
        for t in (d["home"], d["away"]):
            cf.setdefault(t, [0, 0])
        hw = d["home_won"]
        cf[d["home"]][0 if hw else 1] += 1
        cf[d["away"]][1 if hw else 0] += 1
    conn.close()

    aq_keys = _conf_leaders(div, cf, ratings)
    at_large_spots = max(0, field - len(aq_keys))
    # Selection AND seeding both run on the Committee Seed Score (strength + résumé
    # + championship pedigree), not a single ranking.
    committee = committee_seed_score(season_id, set(aq_keys))

    def sv(school):
        return committee.get(school, 0.0)

    non_aq = sorted((p for p in rated if p.school not in aq_keys),
                    key=lambda p: sv(p.school), reverse=True)
    if at_large_spots < edge or len(non_aq) <= at_large_spots:
        return None

    in_al = non_aq[:at_large_spots]          # at-large selections
    out_al = non_aq[at_large_spots:]         # missed the cut
    aq_progs = sorted((p for p in rated if p.school in aq_keys),
                      key=lambda p: sv(p.school), reverse=True)

    # SELECTION is done (AQ + the top at-large). Now SEED: rank the chosen field
    # purely by strength — AQ and at-large INTERLEAVED, never AQ-first. Method of
    # qualification answers "why is this team in?", not "how good is it?", so a weak
    # conference champ can sit at the bottom of the field and a strong at-large near
    # the top. The unpicked teams are ranked just BELOW the field, so the last team
    # in is #field and the first four out are #field+1.. — the real seed-list cut.
    selected = sorted(list(aq_progs) + list(in_al), key=lambda p: sv(p.school), reverse=True)
    seed_of = {p.school: i + 1 for i, p in enumerate(selected)}

    def row(p, seed, bid, **extra):
        r = ratings[p.school]
        return {"school": p.school, "conf": p.conf_abbr, "pi": round(r.pi, 3),
                "score": round(sv(p.school), 1),        # the Committee Seed Score the field is seeded by
                "rec": r.record, "seed": seed, "field_rank": seed, "bid": bid, **extra}

    seed_list = [row(p, seed_of[p.school], "AQ" if p.school in aq_keys else "AL")
                 for p in selected]
    out_board = [row(p, field + i + 1, "AL") for i, p in enumerate(out_al)]
    aq = [r for r in seed_list if r["bid"] == "AQ"]
    in_board = [r for r in seed_list if r["bid"] == "AL"]       # at-large teams, true seeds
    # The cut line shows the FIELD boundary so it lines up with the seed list: the
    # weakest teams still IN (#field-3 … #field) vs the strongest left OUT
    # (#field+1 …). Each row carries an AQ/AL tag, so it's clear when a team is in on
    # an automatic bid rather than strength. (Both are ranked by the same seeding
    # metric — ITA team points — so the displayed order is monotonic.)
    last_in = seed_list[-edge:]                                 # weakest four still in the field
    first_out = out_board[:edge]                                # strongest four left out
    return {"division": s["division"], "gender": s["gender"], "field": field, "edge": edge,
            "aq": aq, "aq_count": len(aq), "at_large_spots": at_large_spots,
            "seed_list": seed_list, "in_board": in_board, "out_board": out_board,
            "last_in": last_in, "first_out": first_out}


def bubble_watch(season_id: int, size: int | None = None, edge: int = 4) -> dict | None:
    """The cut line only: the Last Four In (lowest at-large teams currently
    projected into the field) and the First Four Out (highest-rated teams left out).
    A thin slice of `_project` for the standings page and season-hub card."""
    proj = _project(season_id, size, edge)
    if not proj:
        return None
    return {"field": proj["field"], "aq_count": proj["aq_count"],
            "at_large_spots": proj["at_large_spots"],
            "last_in": proj["last_in"], "first_out": proj["first_out"]}


def field_projection(season_id: int, size: int | None = None, out_n: int = 12) -> dict | None:
    """The full projected bracket field for the dedicated projection page: every
    projected automatic qualifier plus the complete at-large board (teams in, then
    the next `out_n` teams chasing the cut), all ranked by Power Index."""
    proj = _project(season_id, size)
    if not proj:
        return None
    proj["out_board"] = proj["out_board"][:out_n]
    return proj


def team_form(season_id: int) -> dict:
    """Per-team current streak and last-5 form from all final duals, in play order.
    {school: {'streak': +wins/-losses, 'last5': 'WWLWL', 'w': int, 'l': int}}."""
    conn = _db()
    rows = conn.execute("SELECT home, away, winner FROM duals WHERE season_id=? AND status='final'"
                        " ORDER BY week, round_no, id", (season_id,)).fetchall()
    conn.close()
    seq: dict = {}
    for r in rows:
        hw = r["winner"] == 0
        seq.setdefault(r["home"], []).append(hw)
        seq.setdefault(r["away"], []).append(not hw)
    out: dict = {}
    for school, res in seq.items():
        streak = 0
        for won in reversed(res):                  # trailing run of same result
            if streak == 0:
                streak = 1 if won else -1
            elif (streak > 0) == won:
                streak += 1 if won else -1
            else:
                break
        out[school] = {"streak": streak, "w": sum(res), "l": len(res) - sum(res),
                       "last5": "".join("W" if x else "L" for x in res[-5:])}
    return out


def recent_duals(season_id: int) -> list[dict]:
    """The most recently completed slate (last regular week or last postseason
    round) — drives the hub's 'latest results'."""
    conn = _db()
    mw = conn.execute("SELECT MAX(week) w FROM duals WHERE season_id=? AND status='final'",
                      (season_id,)).fetchone()["w"]
    if mw is None:
        conn.close()
        return []
    rows = conn.execute("SELECT * FROM duals WHERE season_id=? AND status='final' AND week=?"
                        " ORDER BY round, bpos, home", (season_id, mw)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def week_duals(season_id: int, week: int) -> list[dict]:
    conn = _db()
    rows = conn.execute("SELECT * FROM duals WHERE season_id=? AND round='REG' AND week=?"
                        " ORDER BY home", (season_id, week)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def national_top(season_id: int, n: int = 15) -> list[dict]:
    """Live Power Index ranking from the season's completed duals so far."""
    s = load_season(season_id)
    div = load_division(s["division"], s["gender"])
    conn = _db()
    duals = _ranking_duals(conn, season_id)
    conn.close()
    if not duals:
        return []
    ratings = compute_ratings(duals)
    ranked = sorted((p for p in div.programs if p.school in ratings),
                    key=lambda p: ratings[p.school].pi, reverse=True)
    return [{"rk": i, "school": p.school, "conf": p.conf_abbr,
             "pi": ratings[p.school].pi, "rec": ratings[p.school].record}
            for i, p in enumerate(ranked[:n], 1)]


_pi_cache: dict = {}
_movers_cache: dict = {}


def power_index(season_id: int) -> dict:
    """Full Power Index ratings (school -> RatingLine with pi/apr/fqi/record) from
    the season's completed regular-season duals. Empty in preseason. Cached by how
    many duals are final, so it refreshes as the season advances."""
    conn = _db()
    cnt = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND status='final'",
                       (season_id,)).fetchone()["c"]
    key = (season_id, cnt)
    # Thread-safe: the gunicorn worker is threaded, so several requests hit this
    # concurrently with DIFFERENT season_ids. Compute into a LOCAL and return that —
    # never `_pi_cache[key]`, which another thread's .clear() (a different sid) can
    # evict between store and return (KeyError → 500s → the app goes unhealthy).
    ratings = _pi_cache.get(key)
    if ratings is None:
        duals = _ranking_duals(conn, season_id)
        ratings = compute_ratings(duals) if duals else {}
        _prune_season(_pi_cache, season_id)      # per-season, not clear(): a career page
        _prune_season(_movers_cache, season_id)  # loops seasons — a global clear thrashes
        _pi_cache[key] = ratings                 # them all (movers derive from ratings —
        # invalidate together)
    conn.close()
    return ratings


def weekly_movers(season_id: int, poll: int = 25) -> dict:
    """Poll-style week-to-week movement for teams currently in the top ``poll``: the
    move caused by the most recent week of ranking-corpus results. {school: positions
    gained (+) / lost (-) within the poll, or None if NEW to the poll this week}. Only
    poll positions are compared, so moves stay bounded and meaningful rather than the
    100-spot swings a 390-team Power Index reshuffle produces. Empty until there are at
    least two weeks of results.

    Cached by completed-dual count (like `power_index`) and reuses the already-cached
    Power Index for the CURRENT board, so ranking_rows — which is called on many pages
    — pays for at most ONE extra (prior-week) rating pass, not two full ones per call."""
    conn = _db()
    cnt = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND status='final'",
                       (season_id,)).fetchone()["c"]
    ck = (season_id, poll, cnt)
    cached = _movers_cache.get(ck)       # .get, not `in`+[]: a concurrent clear is safe
    if cached is not None:
        conn.close()
        return cached
    qs = ",".join("?" for _ in RANKING_ROUNDS)
    rows = conn.execute(
        f"SELECT week, home, away, is_conf, winner, lines_json FROM duals WHERE season_id=?"
        f" AND status='final' AND round IN ({qs})", (season_id, *RANKING_ROUNDS)).fetchall()
    conn.close()
    weeks = sorted({r["week"] for r in rows})
    if len(weeks) < 2:
        _movers_cache[ck] = {}
        return {}
    cutoff = weeks[-1]                                  # the most recent week of results

    def _rec(r):
        return {"home": r["home"], "away": r["away"], "home_won": r["winner"] == 0,
                "conf": bool(r["is_conf"]), "lines": json.loads(r["lines_json"] or "[]")}

    def _rank(ratings):
        order = sorted(ratings, key=lambda x: ratings[x].pi, reverse=True)[:poll]
        return {s: i + 1 for i, s in enumerate(order)}

    cur = _rank(power_index(season_id))                # cached full-season ratings
    prior = _rank(compute_ratings([_rec(r) for r in rows if r["week"] < cutoff]))
    out = {s: (prior[s] - r if s in prior else None) for s, r in cur.items()}
    _movers_cache[ck] = out
    return out


_ITA_CONF_W = 0.30     # weight on conference prestige in opponent quality (0 = results only)


def ita_team_points(season_id: int) -> dict:
    """A simple ITA-style team ranking: the average quality of a team's best-10 wins,
    dragged down by its losses (a loss to a WEAK team hurts most), with a +10% road-win
    bonus — the shape of the real ITA algorithm. Opponent quality blends the Power
    Index's rank-percentile with conference prestige (`_ITA_CONF_W`), so a win over a
    deep power-conference team counts for more — the conference-strength signal the old
    bracket seed_score preference provided, now living in the ranking itself. Anchoring
    to the Power Index also keeps it iteration-free (a raw opponent-quality *iteration*
    degenerates in a synthetic field — a tight mid-major round-robin bootstraps itself
    to the top). Returns {school: points on a ~0-92 scale}; only teams with a win are
    ranked (as in the ITA)."""
    from .ncaa import conf_prestige
    pi = power_index(season_id)
    if not pi:
        return {}
    conn = _db()
    qs = ",".join("?" for _ in RANKING_ROUNDS)
    rows = conn.execute(f"SELECT home, away, winner FROM duals WHERE season_id=? AND status='final'"
                        f" AND round IN ({qs})", (season_id, *RANKING_ROUNDS)).fetchall()
    conn.close()
    wins: dict = {}
    losses: dict = {}
    teams: set = set()
    for d in rows:
        h, a = d["home"], d["away"]
        teams |= {h, a}
        if d["winner"] == 0:
            wins.setdefault(h, []).append((a, False)); losses.setdefault(a, []).append(h)
        else:
            wins.setdefault(a, []).append((h, True)); losses.setdefault(h, []).append(a)

    s = load_season(season_id)
    conf_of = {p.school: p.conf_abbr for p in load_division(s["division"], s["gender"]).programs}
    cps = {t: conf_prestige(conf_of.get(t, "")) for t in teams}
    clo, chi = (min(cps.values()), max(cps.values())) if cps else (0.0, 1.0)
    crange = (chi - clo) or 1.0
    order = sorted((t for t in teams if t in pi), key=lambda t: pi[t].pi, reverse=True)
    n = len(order) or 1
    pct = {t: (n - i) / n for i, t in enumerate(order)}    # Power-Index percentile, 1.0 best
    # Opponent quality = results percentile blended with conference prestige.
    qual = {t: (1 - _ITA_CONF_W) * pct.get(t, 1.0 / n) + _ITA_CONF_W * (cps[t] - clo) / crange
            for t in teams}

    raw: dict = {}
    for t in teams:
        w = wins.get(t)
        if not w:                                          # no win → not ranked
            continue
        wv = sorted((qual[o] * (1.10 if road else 1.0) for o, road in w), reverse=True)[:10]
        drag = sum(1 - qual[o] for o in losses.get(t, []))
        raw[t] = sum(wv) / (len(wv) + drag)
    if not raw:
        return {}
    mx = max(raw.values()) or 1.0
    return {t: round(92.0 * (v / mx) ** 1.8, 2) for t, v in raw.items()}


def _ita_scale(raw: dict, steep: float = 1.8, top: float = 92.0) -> dict:
    """Scale raw ITA scores to a ~0..`top` points spread (leader = `top`)."""
    if not raw:
        return {}
    mx = max(raw.values()) or 1.0
    return {k: round(top * (v / mx) ** steep, 2) for k, v in raw.items()}


def _ita_score(entities, wins, losses, qual, cap: int = 10) -> dict:
    """Generic ITA-style score: best-`cap` win quality dragged by losses (a loss to a
    weak opponent — low qual — hurts most), +10% for road wins. Only entities with a
    win are scored. wins[e] = [(opp, road_bool)], losses[e] = [opp], qual[e] in 0..1."""
    raw = {}
    for e in entities:
        w = wins.get(e)
        if not w:
            continue
        wv = sorted((qual.get(o, 0.0) * (1.10 if road else 1.0) for o, road in w), reverse=True)[:cap]
        drag = sum(1 - qual.get(o, 0.0) for o in losses.get(e, []))
        raw[e] = sum(wv) / (len(wv) + drag)
    return raw


def _singles_results(season_id: int):
    """One pass over final dual lines → the singles player-vs-player graph.
    Returns (wins, losses, players, wl) where wins[pid]=[(opp_pid, road)], wl[pid]=[w,l]."""
    conn = _db()
    rows = conn.execute("SELECT lines_json FROM duals WHERE season_id=? AND status='final'",
                        (season_id,)).fetchall()
    conn.close()
    wins, losses, players = {}, {}, set()
    wl: dict = {}
    for r in rows:
        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed") or not str(ln.get("slot", "")).startswith("S"):
                continue
            hp, ap = ln.get("home_pid"), ln.get("away_pid")
            if hp is None or ap is None:
                continue
            players |= {hp, ap}
            wl.setdefault(hp, [0, 0]); wl.setdefault(ap, [0, 0])
            if ln.get("home_won"):
                wins.setdefault(hp, []).append((ap, False)); losses.setdefault(ap, []).append(hp)
                wl[hp][0] += 1; wl[ap][1] += 1
            else:                                          # away player won on the road
                wins.setdefault(ap, []).append((hp, True)); losses.setdefault(hp, []).append(ap)
                wl[ap][0] += 1; wl[hp][1] += 1
    return wins, losses, players, wl


def _doubles_results(season_id: int):
    """One pass over final dual lines → the doubles PAIR-vs-pair graph. A pair is the
    unordered set of its two pids. Returns (wins, losses, pairs, members, wl)."""
    conn = _db()
    rows = conn.execute("SELECT lines_json FROM duals WHERE season_id=? AND status='final'",
                        (season_id,)).fetchall()
    conn.close()
    wins, losses, pairs, members = {}, {}, set(), {}
    wl: dict = {}
    for r in rows:
        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed") or not str(ln.get("slot", "")).startswith("D"):
                continue
            hps, aps = ln.get("home_pids"), ln.get("away_pids")
            if not hps or not aps or len(set(hps)) != 2 or len(set(aps)) != 2:
                continue
            hp, ap = frozenset(hps), frozenset(aps)
            pairs |= {hp, ap}; members[hp] = tuple(hps); members[ap] = tuple(aps)
            wl.setdefault(hp, [0, 0]); wl.setdefault(ap, [0, 0])
            if ln.get("home_won"):
                wins.setdefault(hp, []).append((ap, False)); losses.setdefault(ap, []).append(hp)
                wl[hp][0] += 1; wl[ap][1] += 1
            else:
                wins.setdefault(ap, []).append((hp, True)); losses.setdefault(hp, []).append(ap)
                wl[ap][0] += 1; wl[hp][1] += 1
    return wins, losses, pairs, members, wl


def _str_percentile(keys, str_of) -> dict:
    """Map keys → quality in (0,1] by descending `str_of(key)` rank-percentile."""
    order = sorted(keys, key=str_of, reverse=True)
    n = len(order) or 1
    q = {k: (n - i) / n for i, k in enumerate(order)}
    for k in keys:
        q.setdefault(k, 1.0 / n)
    return q


def ita_singles_points(season_id: int, min_matches: int = 3) -> dict:
    """ITA-style singles player ranking points {pid: points}, anchored to player STR.
    Only players who have played at least `min_matches` singles are ranked — a 1-0
    record isn't a ranking, so the board doesn't crown someone off a single result
    (mirrors the doubles gate)."""
    strs = season_player_str(season_id)
    if not strs:
        return {}
    wins, losses, players, wl = _singles_results(season_id)
    qual = _str_percentile(players, lambda p: strs.get(p, (0.0,))[0])
    eligible = {p for p in players if wl.get(p, [0, 0])[0] + wl[p][1] >= min_matches}
    return _ita_scale(_ita_score(eligible, wins, losses, qual))


def ita_doubles_points(season_id: int, min_matches: int = 3):
    """ITA-style doubles ranking points for PAIRS that have played together at least
    `min_matches` times. Returns ({pair: points}, {pair: (pid, pid)}, {pair: [w, l]})."""
    strs = season_player_str(season_id)
    if not strs:
        return {}, {}, {}
    wins, losses, pairs, members, wl = _doubles_results(season_id)
    qual = _str_percentile(pairs, lambda pr: sum(strs.get(p, (0.0,))[0] for p in pr) / 2)
    eligible = {pr for pr in pairs if wl.get(pr, [0, 0])[0] + wl[pr][1] >= min_matches}
    return _ita_scale(_ita_score(eligible, wins, losses, qual)), members, wl


def conf_rank(season_id: int) -> dict:
    """school -> (conference_rank, conf_wins, conf_losses) from live standings."""
    out: dict = {}
    for table in standings(season_id).values():
        for i, row in enumerate(table, 1):
            out[row["school"]] = (i, row["cw"], row["cl"])
    return out


def conf_champions(season_id: int) -> list[str]:
    """Conference-tournament winners (school names) so far — the last CT round's
    winner per conference. Empty until the conference tournaments have run.
    Survives NCAA completion (which overwrites the season's `champion` field)."""
    s = load_season(season_id)
    div = load_division(s["division"], s["gender"])
    conn = _db()
    out = []
    for conf in div.conferences:
        last = conn.execute(
            "SELECT home, away, winner FROM duals WHERE season_id=? AND round='CT'"
            " AND conf=? AND status='final' ORDER BY round_no DESC, bpos ASC LIMIT 1",
            (season_id, conf)).fetchone()
        if last and last["winner"] is not None:
            out.append(last["home"] if last["winner"] == 0 else last["away"])
    conn.close()
    return out


def national_champion(season_id: int) -> str | None:
    """The NCAA champion school once the season is complete, else None."""
    s = load_season(season_id)
    return s["champion"] if s and s["phase"] == "complete" else None


def indoor_champion(season_id: int) -> str | None:
    """The ITA National Team Indoor champion once the opener has been played, else
    None (it's crowned the moment the season leaves the ITA phases for the regular
    season). The Final is the last ITAI dual."""
    s = load_season(season_id)
    if not s or s["phase"] in ("ita_kickoff", "ita_indoor"):
        return None
    conn = _db()
    last = conn.execute("SELECT home, away, winner FROM duals WHERE season_id=? AND round='ITAI'"
                        " AND status='final' ORDER BY round_no DESC, bpos ASC LIMIT 1",
                        (season_id,)).fetchone()
    conn.close()
    if not last or last["winner"] is None:
        return None
    return last["home"] if last["winner"] == 0 else last["away"]


def bracket_field(season_id: int, size: int | None = None):
    """The NCAA field as it stands: seed the Power-Index-rated programs (conference
    champions get autobids once the conference tournaments have run), run the
    bracket. Returns a BracketResult, or None in preseason (no results yet)."""
    s = load_season(season_id)
    if size is None:
        size = field_for_division(s["division"])
    ratings = power_index(season_id)
    rated = [p for p in load_division(s["division"], s["gender"]).programs
             if p.school in ratings]
    if len(rated) < 2:
        return None
    champions = []
    if s["phase"] in ("selection", "ncaa", "complete") and s["champion"]:
        try:
            progs = _programs(s["division"], s["gender"])
            champions = [progs[v] for v in json.loads(s["champion"]).values()
                         if v in progs and v in ratings]
        except (ValueError, TypeError):
            champions = []
    seeded, autobids = select_field(rated, ratings, champions, size=clamp_field(size),
                                    score=committee_seed_score(season_id, {c.school for c in champions}))
    return run_bracket(seeded, autobids, seed=s["seed"])


def ncaa_field(season_id: int, size: int | None = None, out_n: int = 8):
    """The locked NCAA field for the bracket reveal — (seeded programs, autobid
    keys, snub board, ratings), selected exactly as the tournament will use it
    (conference champions auto-in, the rest at-large by Power Index). The snub
    board is the `out_n` highest-Power-Index teams that JUST missed the field —
    'who's out'. Available once the conference tournaments crown champions."""
    s = load_season(season_id)
    if size is None:
        size = field_for_division(s["division"])
    conn = _db()
    ratings = compute_ratings(_completed(conn, season_id, SEED_ROUNDS))
    conn.close()
    div = load_division(s["division"], s["gender"])
    progs = {p.school: p for p in div.programs}
    # Conference champions are derived from the CT results (the reliable source) —
    # NOT from season.champion, which holds the conf-champ map only during the
    # selection window and is overwritten with the NATIONAL champion's name once the
    # tournament completes (parsing it as JSON then would fail and drop the seeds).
    champions = [progs[v] for v in conf_champions(season_id) if v in progs and v in ratings]
    rated = [p for p in div.programs if p.school in ratings]
    # Select + seed by the SAME Committee Seed Score the actual draw uses
    # (`_ncaa_seeds`), so the revealed seeds/labels match the scheduled matchups.
    committee = committee_seed_score(season_id, {c.school for c in champions})
    seeded, autobids = select_field(rated, ratings, champions, size=clamp_field(size), score=committee)
    field_keys = {p.key for p in seeded}
    out = sorted((p for p in rated if p.key not in field_keys),
                 key=lambda p: committee.get(p.school, 0.0), reverse=True)[:out_n]
    out_board = [{"school": p.school, "conf": p.conf_abbr,
                  "pi": round(ratings[p.school].pi, 3), "rec": ratings[p.school].record}
                 for p in out]
    return seeded, autobids, out_board, ratings


def ita_view(season_id: int) -> dict | None:
    """The stored ITA opener for rendering: each cosmetic Kickoff site (its two
    semifinals + final) and the Indoor bracket (rounds in order), plus the Indoor
    champion once crowned. None for non-ITA divisions or before the draw is made."""
    s = load_season(season_id)
    if not s or not ita.runs_ita(s["division"]):
        return None
    conn = _db()
    krows = conn.execute("SELECT * FROM duals WHERE season_id=? AND round='ITAK'"
                         " ORDER BY conf, round_no, bpos", (season_id,)).fetchall()
    irows = conn.execute("SELECT * FROM duals WHERE season_id=? AND round='ITAI'"
                         " ORDER BY round_no, bpos", (season_id,)).fetchall()
    conn.close()
    if not krows and not irows:        # nothing drawn yet (D2/D3 have no Kickoff sites)
        return None
    sites: dict = {}
    for r in krows:
        site = sites.setdefault(r["conf"], {"label": r["conf"], "semis": [], "final": None})
        (site["semis"].append(dict(r)) if r["round_no"] == 1
         else site.__setitem__("final", dict(r)))
    site_list = sorted(sites.values(), key=lambda x: int(x["label"].split()[-1]))
    indoor: dict = {}
    for r in irows:
        indoor.setdefault((r["round_no"], r["conf"]), []).append(dict(r))
    indoor_rounds = [{"name": name, "duals": duals}
                     for (rno, name), duals in sorted(indoor.items())]
    return {"sites": site_list, "indoor": indoor_rounds,
            "indoor_champion": indoor_champion(season_id), "phase": s["phase"]}


def dual_detail(dual_id: int) -> dict | None:
    conn = _db()
    r = conn.execute("SELECT * FROM duals WHERE id=?", (dual_id,)).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    d["lines"] = json.loads(d["lines_json"] or "[]")
    return d


def team_schedule(season_id: int, school: str) -> list[dict]:
    """A team's full season slate — regular season AND postseason (conference
    tournament + NCAAs), week-ordered. All of it counts toward the season record,
    as in real college tennis. `round` ('REG'/'CT'/'NCAA') lets callers label the
    postseason rows."""
    conn = _db()
    rows = conn.execute("SELECT * FROM duals WHERE season_id=? AND (home=? OR away=?)"
                        " ORDER BY week, round_no, id", (season_id, school, school)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Coached-team non-conference scheduling (career mode, preseason planning) ---
# The slate is generated once and persisted; at preseason nothing's been played, so
# a coach can re-opponent their own non-conf duals by editing the persisted rows.
# One `duals` row IS the dual for both teams, so a swap stays symmetric automatically
# (the dropped opponent loses the game, the chosen one gains it). Only unplayed,
# non-conf REGULAR-season duals that the school actually plays are editable.

def nonconf_duals(season_id: int, school: str) -> list[dict]:
    """`school`'s editable non-conference duals as {id, week, opponent, home}."""
    conn = _db()
    rows = conn.execute(
        "SELECT id, week, home, away FROM duals WHERE season_id=? AND round='REG'"
        " AND is_conf=0 AND status='scheduled' AND (home=? OR away=?) ORDER BY week, id",
        (season_id, school, school)).fetchall()
    conn.close()
    out = []
    for r in rows:
        home = r["home"] == school
        out.append({"id": r["id"], "week": r["week"], "home": home,
                    "opponent": r["away"] if home else r["home"]})
    return out


def _slate_opponents(conn, season_id: int, school: str) -> set:
    rows = conn.execute("SELECT home, away FROM duals WHERE season_id=? AND (home=? OR away=?)",
                        (season_id, school, school)).fetchall()
    return {(r["away"] if r["home"] == school else r["home"]) for r in rows}


def eligible_nonconf_opponents(season_id: int, division: str, gender: str, school: str) -> list[str]:
    """Programs in the same division/gender a coach may add: not themselves and not
    already anywhere on their slate (so no accidental double-booking)."""
    conn = _db()
    booked = _slate_opponents(conn, season_id, school)
    conn.close()
    progs = sorted(p.school for p in load_division(division, gender).programs)
    return [s for s in progs if s != school and s not in booked]


def _editable_nonconf(conn, season_id: int, dual_id: int, school: str):
    r = conn.execute("SELECT home, away, is_conf, round, status FROM duals"
                     " WHERE id=? AND season_id=?", (dual_id, season_id)).fetchone()
    if (not r or r["is_conf"] or r["round"] != "REG" or r["status"] != "scheduled"
            or school not in (r["home"], r["away"])):
        return None
    return r


def swap_nonconf_opponent(season_id: int, dual_id: int, school: str, new_opp: str,
                          division: str, gender: str) -> bool:
    """Replace the opponent on one of `school`'s unplayed non-conf duals, keeping
    `school` on its home/away side. Returns False unless the dual is editable and
    new_opp is eligible."""
    if new_opp not in eligible_nonconf_opponents(season_id, division, gender, school):
        return False
    conn = _db()
    r = _editable_nonconf(conn, season_id, dual_id, school)
    if not r:
        conn.close(); return False
    col = "away" if r["home"] == school else "home"
    conn.execute(f"UPDATE duals SET {col}=? WHERE id=?", (new_opp, dual_id))
    conn.commit(); conn.close()
    return True


def set_nonconf_home(season_id: int, dual_id: int, school: str, home: bool) -> bool:
    """Flip home/away for `school` on one of its unplayed non-conf duals."""
    conn = _db()
    r = _editable_nonconf(conn, season_id, dual_id, school)
    if not r:
        conn.close(); return False
    if (r["home"] == school) != home:
        conn.execute("UPDATE duals SET home=?, away=? WHERE id=?",
                     (r["away"], r["home"], dual_id))
        conn.commit()
    conn.close()
    return True


DEV_LINE_SLOTS = {"S4", "S5", "S6", "D3"}   # the developmental bottom of the lineup


def developmental_wins(season_id: int) -> dict:
    """Per-team regular-season wins at the BOTTOM of the lineup — 4/5/6 singles
    and 3rd doubles. A proxy for player development / depth (those courts are
    where an assistant's work shows), used to pick the Assistant Coach of the
    Year. Returns {school: wins}."""
    conn = _db()
    rows = conn.execute("SELECT home, away, lines_json FROM duals WHERE season_id=?"
                        " AND round='REG' AND status='final'", (season_id,)).fetchall()
    conn.close()
    out: dict = {}
    for r in rows:
        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed") or ln.get("slot") not in DEV_LINE_SLOTS:
                continue
            winner = r["home"] if ln["home_won"] else r["away"]
            out[winner] = out.get(winner, 0) + 1
    return out


def all_results(season_id: int) -> list[dict]:
    """Every completed dual this season (regular + conference tournament + NCAA),
    week-ordered — the source for a week-by-week results browser. `conf` holds the
    conference for REG/CT and the round name (e.g. 'Round of 16') for NCAA."""
    conn = _db()
    rows = conn.execute(
        "SELECT week, round, conf, round_no, bpos, home, away, home_points, away_points, winner"
        " FROM duals WHERE season_id=? AND status='final'"
        " ORDER BY week, round, round_no, bpos", (season_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Player cards — match-by-match log + season STR
# --------------------------------------------------------------------------

from .ncaa import build_roster

_pid_idx_cache: dict = {}
_str_cache: dict = {}


def _pid_index(division: str, gender: str) -> dict:
    key = (division, gender)
    idx = _pid_idx_cache.get(key)   # .get + local return: world-advance clears this
    if idx is None:                 # from another thread (world.py/state.py)
        from app import economy
        idx = {}
        for p in load_division(division, gender).programs:
            for pr in build_roster(p):
                idx[pr.pid] = {"name": pr.name, "school": p.school, "class": pr.class_year,
                               "country": pr.country, "hometown": pr.hometown, "major": pr.major,
                               "overall": pr.current_overall(), "ceiling": pr.ceiling_overall(),
                               "walk_on": pr.walk_on, "high_school": pr.high_school,
                               "secondary_country": pr.secondary_country,
                               "school_city": p.location,
                               "recruit_stars": getattr(pr, "recruit_stars", 0),
                               "recruit_tier": getattr(pr, "recruit_tier", ""),
                               "scholarship": getattr(pr, "scholarship", 0.0),
                               "scholarship_label": economy.fraction_label(
                                   getattr(pr, "scholarship", 0.0))}
        _pid_idx_cache[key] = idx
    return idx


def player_info(season_id: int, pid: str) -> dict | None:
    s = load_season(season_id)
    return _pid_index(s["division"], s["gender"]).get(pid)


def injury_log(season_id: int, school: str | None = None) -> list[dict]:
    """The season's injury log — one entry per injury event (active and returned),
    newest first. Each entry: pid, school, name, week, tag, length (duals out, or
    'Season' for season-ending), remaining, season_ending, and a status label.
    Filter by `school` for a program page; omit it for the league-wide list."""
    conn = _db()
    try:
        q = ("SELECT pid, school, name, week, tag, total, duals_remaining, season_ending"
             " FROM injuries WHERE season_id=?")
        args: list = [season_id]
        if school:
            q += " AND school=?"
            args.append(school)
        # active first (season-ending, then still-out), then returned; recent week first
        q += (" ORDER BY (season_ending=1 OR duals_remaining>0) DESC,"
              " season_ending DESC, week DESC, id DESC")
        rows = conn.execute(q, args).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        se = bool(r["season_ending"])
        rem = r["duals_remaining"]
        if se:
            status, length, left = "Season-ending", "Season", "Out for season"
        elif rem > 0:
            status = f"Out — {rem} more"
            length = f"{r['total']} duals"
            left = f"{rem} of {r['total']} left"      # matches still to miss
        else:
            status, length, left = "Returned", f"{r['total']} duals", "Returned"
        out.append({
            "pid": r["pid"], "school": r["school"], "name": r["name"] or r["pid"],
            "week": r["week"], "tag": r["tag"] or "", "length": length, "left": left,
            "total": r["total"], "remaining": rem, "season_ending": se,
            "active": se or rem > 0, "status": status,
        })
    return out


def season_ending_pids(season_id: int) -> set:
    """Pids that suffered a season-ending injury this season — the medical-redshirt
    cohort the world rollover grants a returning (RS-tagged) year of eligibility."""
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT pid FROM injuries WHERE season_id=? AND season_ending=1",
            (season_id,)).fetchall()
    finally:
        conn.close()
    return {r["pid"] for r in rows}


def season_player_str(season_id: int) -> dict:
    """Live STR/reliability for every player, from the season's completed duals
    (cached by how many duals are final, so it refreshes as the season advances)."""
    conn = _db()
    cnt = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND status='final'",
                       (season_id,)).fetchone()["c"]
    key = (season_id, cnt)
    cached = _str_cache.get(key)
    if cached is not None:
        conn.close()
        return cached
    duals = _completed(conn, season_id)
    conn.close()
    s = load_season(season_id)
    priors = {pr.pid: pr.str_value() for p in load_division(s["division"], s["gender"]).programs
              for pr in build_roster(p)}
    res = converge_ids(build_corpus(duals), priors=priors)
    _prune_season(_str_cache, season_id)
    _str_cache[key] = res
    return res


_prec_cache: dict = {}


def _prune_season(cache: dict, season_id: int) -> None:
    """Invalidate only THIS season's stale entries ((season_id, cnt)-keyed caches).

    These caches used to `cache.clear()` on every rebuild, which is doubly broken
    under the threaded worker: (1) a career page loops seasons, so each season's
    rebuild wiped every OTHER season's entry — quadratic recompute, the slow
    /player pages; (2) one thread's clear could evict another thread's key between
    its store and its `return cache[key]` — the KeyError → 500 → unhealthy-instance
    outage (same disease power_index had). Prune per-season, and callers must
    return their LOCAL value, never re-read the shared cache."""
    for k in list(cache):
        if k[0] == season_id:
            cache.pop(k, None)


def player_records(season_id: int) -> dict:
    """One-pass ``pid -> (wins, losses)`` over all completed singles lines —
    cheaper than calling player_log per player. Cached by completed-dual count."""
    conn = _db()
    cnt = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND status='final'",
                       (season_id,)).fetchone()["c"]
    key = (season_id, cnt)
    out = _prec_cache.get(key)          # .get + local return: concurrent prune is safe
    if out is None:
        rows = conn.execute("SELECT lines_json FROM duals WHERE season_id=? AND status='final'",
                            (season_id,)).fetchall()
        rec: dict = {}
        for r in rows:
            for ln in json.loads(r["lines_json"] or "[]"):
                if not ln.get("completed") or ln.get("home_pid") is None:
                    continue
                hw = ln["home_won"]
                rec.setdefault(ln["home_pid"], [0, 0])[0 if hw else 1] += 1
                rec.setdefault(ln["away_pid"], [0, 0])[1 if hw else 0] += 1
        out = {k: (v[0], v[1]) for k, v in rec.items()}
        _prune_season(_prec_cache, season_id)
        _prec_cache[key] = out
    conn.close()
    return out


_pstats_cache: dict = {}


def _stat_block(ps: PlayerStats, matches: int) -> dict:
    """A PlayerStats total as a display-ready dict: full field names, match
    count, and the derived serve/return rates."""
    d = {f.name: getattr(ps, f.name) for f in _dc_fields(PlayerStats)}
    d["matches"] = matches
    d["first_serve_pct"] = ps.first_serve_pct
    d["serve_pts_pct"] = ps.serve_points_won_pct
    d["return_pts_pct"] = (ps.return_points_won / ps.return_points_total
                           if ps.return_points_total else 0.0)
    return d


def player_season_stats(season_id: int) -> dict:
    """Season box-stat totals per player, aggregated from the per-line stats
    persisted in lines_json — ``pid -> {"singles": {...}, "doubles": {...}}``
    (a kind is present only if the player logged stats in it). Counters carry
    full PlayerStats field names plus ``matches`` and derived rates. Completed
    lines only; duals played before box stats existed (older saves) simply
    don't contribute. One pass, cached by completed-dual count."""
    conn = _db()
    cnt = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND status='final'",
                       (season_id,)).fetchone()["c"]
    key = (season_id, cnt)
    cached = _pstats_cache.get(key)     # .get + local return: concurrent prune is safe
    if cached is None:
        rows = conn.execute("SELECT lines_json FROM duals WHERE season_id=? AND status='final'",
                            (season_id,)).fetchall()
        agg: dict = {}                      # (pid, kind) -> [PlayerStats, matches]

        def bump(pid, kind, d):
            cell = agg.setdefault((pid, kind), [PlayerStats(), 0])
            cell[0].add(PlayerStats.from_dict(d))
            cell[1] += 1

        for r in rows:
            for ln in json.loads(r["lines_json"] or "[]"):
                st = ln.get("stats")
                if not ln.get("completed") or not st:
                    continue
                slot = ln.get("slot") or ""
                if slot.startswith("S") and ln.get("home_pid") is not None:
                    bump(ln["home_pid"], "singles", st["home"])
                    bump(ln["away_pid"], "singles", st["away"])
                elif slot.startswith("D") and ln.get("home_pids"):
                    for pid, d in zip(ln["home_pids"], st["home"]):
                        bump(pid, "doubles", d)
                    for pid, d in zip(ln.get("away_pids", []), st["away"]):
                        bump(pid, "doubles", d)
        cached = {}
        for (pid, kind), (ps, n) in agg.items():
            cached.setdefault(pid, {})[kind] = _stat_block(ps, n)
        _prune_season(_pstats_cache, season_id)
        _pstats_cache[key] = cached
    conn.close()
    return cached


_pline_cache: dict = {}


def player_primary_lines(season_id: int) -> dict:
    """``pid -> primary singles line`` (the lineup slot played most this season),
    one pass over completed lines. Cached by completed-dual count."""
    conn = _db()
    cnt = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND status='final'",
                       (season_id,)).fetchone()["c"]
    key = (season_id, cnt)
    out = _pline_cache.get(key)         # .get + local return: concurrent prune is safe
    if out is None:
        rows = conn.execute("SELECT lines_json FROM duals WHERE season_id=? AND status='final'",
                            (season_id,)).fetchall()
        tally: dict = {}
        for r in rows:
            for ln in json.loads(r["lines_json"] or "[]"):
                if not ln.get("completed") or ln.get("home_pid") is None:
                    continue            # doubles / unplayed lines carry no singles slot
                slot = ln.get("slot")
                for pid in (ln["home_pid"], ln["away_pid"]):
                    tally.setdefault(pid, {})[slot] = tally.setdefault(pid, {}).get(slot, 0) + 1
        out = {pid: max(d, key=d.get) for pid, d in tally.items() if d}
        _prune_season(_pline_cache, season_id)
        _pline_cache[key] = out
    conn.close()
    return out


_plrec_cache: dict = {}


def player_line_records(season_id: int) -> dict:
    """Per-player W-L by lineup line —
    ``{pid: {'singles': {n: [w, l]}, 'doubles': {n: [w, l]}}}`` (n = 1..6 singles,
    1..3 doubles). One pass over completed dual lines; cached by completed count."""
    conn = _db()
    cnt = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND status='final'",
                       (season_id,)).fetchone()["c"]
    key = (season_id, cnt)
    rec = _plrec_cache.get(key)         # .get + local return: concurrent prune is safe
    if rec is None:
        rows = conn.execute("SELECT lines_json FROM duals WHERE season_id=? AND status='final'",
                            (season_id,)).fetchall()
        rec = {}

        def bump(pid, kind, n, won):
            cell = rec.setdefault(pid, {"singles": {}, "doubles": {}})[kind].setdefault(n, [0, 0])
            cell[0 if won else 1] += 1

        for r in rows:
            for ln in json.loads(r["lines_json"] or "[]"):
                if not ln.get("completed"):
                    continue
                slot = ln.get("slot") or ""
                hw = ln.get("home_won")
                if slot.startswith("S") and ln.get("home_pid") is not None:
                    n = int(slot[1:])
                    bump(ln["home_pid"], "singles", n, hw)
                    bump(ln["away_pid"], "singles", n, not hw)
                elif slot.startswith("D") and ln.get("home_pids"):
                    n = int(slot[1:])
                    for pid in ln["home_pids"]:
                        bump(pid, "doubles", n, hw)
                    for pid in ln.get("away_pids", []):
                        bump(pid, "doubles", n, not hw)
        _prune_season(_plrec_cache, season_id)
        _plrec_cache[key] = rec
    conn.close()
    return rec


def player_log(season_id: int, pid: str) -> list[dict]:
    """A player's match-by-match singles results across the whole season
    (regular + conference tournament + NCAA), newest phase last."""
    s = load_season(season_id)
    idx = _pid_index(s["division"], s["gender"])
    conn = _db()
    rows = conn.execute("SELECT week, round, conf, home, away, winner, lines_json FROM duals"
                        " WHERE season_id=? AND status='final' AND lines_json LIKE ?"
                        " ORDER BY week", (season_id, f"%{pid}%")).fetchall()
    conn.close()
    log = []
    for r in rows:
        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed"):
                continue
            raw_sets = ln.get("sets") or []
            line_stats = ln.get("stats") or {}
            if ln.get("home_pid") == pid:
                gf, ga, won, opp, opp_school = (ln["home_games"], ln["away_games"],
                                                ln["home_won"], ln.get("away_pid"), r["away"])
                sets = [[h, a] for (h, a) in raw_sets]
                stats = line_stats.get("home")
            elif ln.get("away_pid") == pid:
                gf, ga, won, opp, opp_school = (ln["away_games"], ln["home_games"],
                                                not ln["home_won"], ln.get("home_pid"), r["home"])
                sets = [[a, h] for (h, a) in raw_sets]   # flip to the player's POV
                stats = line_stats.get("away")
            else:
                continue
            phase = "Regular" if r["round"] == "REG" else (r["conf"] or r["round"])
            log.append({"phase": phase, "round": r["round"], "slot": ln["slot"],
                        "opp": idx.get(opp, {}).get("name", "—"), "opp_pid": opp,
                        "opp_school": opp_school, "week": r["week"],
                        "sets": sets, "gf": gf, "ga": ga, "won": won,
                        # per-match box stats (compact engine.state.STAT_KEYS
                        # form, this player's side) — None on pre-stats saves
                        "stats": stats})
    return log
