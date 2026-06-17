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

from . import dbpath

from .ncaa import load_division
from .season import dual_between, build_corpus, forced_appearances
from .rating import compute_ratings
from .str_rating import converge_ids
from .bracket import select_field, run_bracket, _seed_positions, ROUND_NAMES, clamp_field

from .dbpath import resolve_db_path

DB_PATH = resolve_db_path()   # volume path if writable, else a local fallback
# Tuned to docs/calibration-season-schedule.md: ~13-14 weeks, ~22 duals/team,
# non-conf front-loaded, conference single round-robin (double only for small
# leagues), 1-2 duals/week.
NONCONF_PER_TEAM = 7
CONF_DOUBLE_MAX = 8          # conferences with < this many teams play a double round-robin
CONF_TOURNEY_FIELD = 8       # top-N per conference make the conference tournament
MAX_PER_WEEK = 2
NATIONAL_FIELD = 64

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
"""


_schema_ready_for = None        # the DB_PATH the schema was last created for


def init_schema() -> None:
    """Eagerly create schema + column migrations (auto-committing connection)
    so the lazy path never writes inside a held transaction — the cause of the
    'database is locked' 500s during sim."""
    global _schema_ready_for
    conn = dbpath.connect(DB_PATH)
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
    for name, members in div.conferences.items():
        schools = [p.school for p in members]
        double = len(schools) < CONF_DOUBLE_MAX
        for i in range(len(schools)):
            for j in range(i + 1, len(schools)):
                x, y = schools[i], schools[j]
                conf_games.append((x, y, name))
                if double:
                    conf_games.append((y, x, name))

    allschools = [p.school for p in div.programs]
    prestige = {p.school: getattr(p, "prestige", 0.5) for p in div.programs}
    nc_count = {s: 0 for s in allschools}
    pairs = set()
    nonconf = []
    order = allschools[:]
    rng.shuffle(order)

    def _accept(s, o) -> float:
        """How likely program s schedules o non-conference. Powerhouses load up
        on mid/low-majors (and host them); they rarely play each other in the
        regular season because a loss dents record + seeding."""
        ps, po = prestige[s], prestige[o]
        if ps > 0.62 and po > 0.62:
            return 0.05                         # two heavyweights — almost never
        gap = ps - po
        if gap > 0.08:
            return 0.92                         # classic cupcake / regional draw
        if gap < -0.08:
            return 0.45                         # scheduling up (guarantee game)
        return 0.55                             # non-elite peers

    for s in order:
        tries = 0
        while nc_count[s] < NONCONF_PER_TEAM and tries < 140:
            tries += 1
            o = rng.choice(allschools)
            if o == s or school_conf[o] == school_conf[s] or nc_count[o] >= NONCONF_PER_TEAM:
                continue
            key = tuple(sorted((s, o)))
            if key in pairs:
                continue
            if rng.random() > _accept(s, o):
                continue
            pairs.add(key)
            nc_count[s] += 1
            nc_count[o] += 1
            # The stronger program almost always hosts; the cupcake travels.
            host_strong = prestige[s] >= prestige[o]
            if rng.random() < 0.8:
                home, away = (s, o) if host_strong else (o, s)
            else:
                home, away = (o, s) if host_strong else (s, o)
            nonconf.append((home, away, None))

    # assign to weeks: non-conf first, then conference
    rows = []
    def assign(games, start):
        cnt, used = {}, set()
        last = start - 1
        for (h, a, cn) in games:
            w = start
            while (cnt.get((w, h), 0) >= MAX_PER_WEEK or cnt.get((w, a), 0) >= MAX_PER_WEEK
                   or (w, h, a) in used or (w, a, h) in used):
                w += 1
            cnt[(w, h)] = cnt.get((w, h), 0) + 1
            cnt[(w, a)] = cnt.get((w, a), 0) + 1
            used.add((w, h, a))
            rows.append((w, h, a, cn))
            last = max(last, w)
        return last
    last = assign(nonconf, 1)
    assign(conf_games, last + 1)
    return rows


def create_season(division: str = "D1", gender: str = "men", *, seed: int = 2026) -> int:
    div = load_division(division, gender)
    rows = _gen_regular_schedule(div, seed)
    total_weeks = max(r[0] for r in rows) if rows else 0
    conn = _db()
    cur = conn.execute(
        "INSERT INTO seasons (division, gender, seed, current_week, total_weeks, phase, champion)"
        " VALUES (?,?,?,?,?,?,?)",
        (division, gender, seed, 1, total_weeks, "regular", None))
    sid = cur.lastrowid
    conn.executemany(
        "INSERT INTO duals (season_id, week, round, conf, is_conf, home, away, status,"
        " home_points, away_points, winner, lines_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [(sid, w, "REG", cn, 1 if cn else 0, h, a, "scheduled", None, None, None, None)
         for (w, h, a, cn) in rows])
    conn.commit()
    conn.close()
    return sid


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
    if key not in _forced_cache:
        rows = conn.execute(
            "SELECT id, home, away FROM duals WHERE season_id=? AND round='REG'"
            " AND (home=? OR away=?) ORDER BY week, id",
            (s["id"], school, school)).fetchall()
        duals = []
        for r in rows:
            opp = r["away"] if r["home"] == school else r["home"]
            duals.append((r["id"], getattr(progs.get(opp), "prestige", 0.5)))
        _forced_cache[key] = forced_appearances(progs[school], build_roster(progs[school]), duals)
    return _forced_cache[key]


def _play_and_store(conn, s, progs, dual_id, home, away, is_conf, tag, form=None):
    # Playing-time guarantee: each team has one dual per roster player where that
    # player is seated into a completing slot (weakest players land in the most
    # favorable duals, so the bench plays up in non-conference).
    fh = _forced_for(conn, s, progs, home).get(dual_id)
    fa = _forced_for(conn, s, progs, away).get(dual_id)
    rec = dual_between(progs[home], progs[away],
                       seed=_dual_seed(s["seed"], home, away, tag), conf=bool(is_conf),
                       form=form, lineup_seed=s["seed"], forced_home=fh, forced_away=fa)
    winner = 0 if rec["home_won"] else 1
    conn.execute("UPDATE duals SET status='final', home_points=?, away_points=?, winner=?,"
                 " lines_json=? WHERE id=?",
                 (rec["home_points"], rec["away_points"], winner, json.dumps(rec["lines"]), dual_id))
    return rec


def _completed(conn, season_id, rounds=("REG", "CT", "NCAA")) -> list[dict]:
    """All completed duals (any phase by default) as record dicts."""
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


def _completed_reg_duals(conn, season_id) -> list[dict]:
    return _completed(conn, season_id, ("REG",))


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
    for d in due:
        _play_and_store(conn, s, progs, d["id"], d["home"], d["away"], d["is_conf"],
                        f"{prefix}{round_no}b{d['bpos']}", form=form)
    return due


def _advance_conf_round(conn, s, progs) -> dict:
    sid = s["id"]
    div = load_division(s["division"], s["gender"])
    reg = _completed(conn, sid, ("REG",))
    wl = _conf_standings(reg, div)
    ratings = compute_ratings(reg)
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


def _advance_ncaa_round(conn, s, progs) -> dict:
    sid = s["id"]
    div = load_division(s["division"], s["gender"])
    existing = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND round='NCAA'",
                            (sid,)).fetchone()["c"]
    if existing == 0:                                  # select + seed the 64-team field
        ratings = compute_ratings(_completed(conn, sid, ("REG", "CT")))
        champs_map = json.loads(load_season(sid)["champion"] or "{}")
        champions = [progs[v] for v in champs_map.values() if v in progs]
        seeded, _ = select_field(div.programs, ratings, champions, size=NATIONAL_FIELD)
        week = _next_post_week(conn, sid)
        for bpos, h, a in _round1_pairs([p.school for p in seeded]):
            _insert_dual(conn, sid, week, "NCAA", _round_name(NATIONAL_FIELD), 0, 1, bpos, h, a)
        round_no = 1
    else:
        round_no = conn.execute("SELECT MIN(round_no) r FROM duals WHERE season_id=? AND round='NCAA'"
                                " AND status='scheduled'", (sid,)).fetchone()["r"]

    due = _sim_round(conn, s, progs, "NCAA", round_no, "ncaa")
    wins = conn.execute("SELECT home, away, winner FROM duals WHERE season_id=? AND round='NCAA'"
                        " AND round_no=? ORDER BY bpos", (sid, round_no)).fetchall()
    winners = [w["home"] if w["winner"] == 0 else w["away"] for w in wins]
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


# Below this many games per team the Power Index is too noisy to project a field;
# the Bubble Watch stays hidden until the season has run a few weeks.
BUBBLE_MIN_GAMES = 5


def _games_played(rec: str) -> int:
    try:
        w, l = rec.split("-")
        return int(w) + int(l)
    except (ValueError, AttributeError):
        return 0


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


def _project(season_id: int, size: int = NATIONAL_FIELD, edge: int = 4) -> dict | None:
    """Core field projection shared by `bubble_watch` and `field_projection`.

    Projects this tournament's NCAA field "if it were held today". Each (division,
    gender) season is its own separate tournament, so the projection is naturally
    scoped to it. Selection mirrors the real format and the engine's own bracket
    logic (`select_field`): projected conference leaders take the automatic bids,
    then the remaining at-large spots in the bracket are filled strictly by Power
    Index — nothing else. Returns None until enough duals are final for the
    projection to mean anything (or when the field would swallow everyone)."""
    s = load_season(season_id)
    if not s:
        return None
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
    non_aq = sorted((p for p in rated if p.school not in aq_keys),
                    key=lambda p: ratings[p.school].pi, reverse=True)
    if at_large_spots < edge or len(non_aq) <= at_large_spots:
        return None

    def row(p, **extra):
        r = ratings[p.school]
        return {"school": p.school, "conf": p.conf_abbr, "pi": round(r.pi, 3),
                "rec": r.record, **extra}

    aq = sorted((row(p) for p in rated if p.school in aq_keys),
                key=lambda d: d["pi"], reverse=True)
    in_board = [row(p, al_rank=i + 1) for i, p in enumerate(non_aq[:at_large_spots])]
    out_board = [row(p, al_rank=at_large_spots + i + 1)
                 for i, p in enumerate(non_aq[at_large_spots:])]
    return {"division": s["division"], "gender": s["gender"], "field": field, "edge": edge,
            "aq": aq, "at_large_spots": at_large_spots, "in_board": in_board, "out_board": out_board}


def bubble_watch(season_id: int, size: int = NATIONAL_FIELD, edge: int = 4) -> dict | None:
    """The cut line only: the Last Four In (lowest at-large teams currently
    projected into the field) and the First Four Out (highest-rated teams left out).
    A thin slice of `_project` for the standings page and season-hub card."""
    proj = _project(season_id, size, edge)
    if not proj:
        return None
    return {"field": proj["field"], "aq_count": len(proj["aq"]),
            "at_large_spots": proj["at_large_spots"],
            "last_in": proj["in_board"][-edge:], "first_out": proj["out_board"][:edge]}


def field_projection(season_id: int, size: int = NATIONAL_FIELD, out_n: int = 12) -> dict | None:
    """The full projected bracket field for the dedicated projection page: every
    projected automatic qualifier plus the complete at-large board (teams in, then
    the next `out_n` teams chasing the cut), all ranked by Power Index."""
    proj = _project(season_id, size)
    if not proj:
        return None
    proj["out_board"] = proj["out_board"][:out_n]
    return proj


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
    duals = _completed_reg_duals(conn, season_id)
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


def power_index(season_id: int) -> dict:
    """Full Power Index ratings (school -> RatingLine with pi/apr/fqi/record) from
    the season's completed regular-season duals. Empty in preseason. Cached by how
    many duals are final, so it refreshes as the season advances."""
    conn = _db()
    cnt = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND status='final'",
                       (season_id,)).fetchone()["c"]
    key = (season_id, cnt)
    if key not in _pi_cache:
        duals = _completed_reg_duals(conn, season_id)
        _pi_cache.clear()
        _pi_cache[key] = compute_ratings(duals) if duals else {}
    conn.close()
    return _pi_cache[key]


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


def bracket_field(season_id: int, size: int = NATIONAL_FIELD):
    """The NCAA field as it stands: seed the Power-Index-rated programs (conference
    champions get autobids once the conference tournaments have run), run the
    bracket. Returns a BracketResult, or None in preseason (no results yet)."""
    s = load_season(season_id)
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
    seeded, autobids = select_field(rated, ratings, champions, size=clamp_field(size))
    return run_bracket(seeded, autobids, seed=s["seed"])


def ncaa_field(season_id: int, size: int = NATIONAL_FIELD, out_n: int = 8):
    """The locked NCAA field for the bracket reveal — (seeded programs, autobid
    keys, snub board, ratings), selected exactly as the tournament will use it
    (conference champions auto-in, the rest at-large by Power Index). The snub
    board is the `out_n` highest-Power-Index teams that JUST missed the field —
    'who's out'. Available once the conference tournaments crown champions."""
    s = load_season(season_id)
    conn = _db()
    ratings = compute_ratings(_completed(conn, season_id, ("REG", "CT")))
    conn.close()
    div = load_division(s["division"], s["gender"])
    progs = {p.school: p for p in div.programs}
    champs_map = json.loads(s["champion"] or "{}")
    champions = [progs[v] for v in champs_map.values() if v in progs and v in ratings]
    rated = [p for p in div.programs if p.school in ratings]
    seeded, autobids = select_field(rated, ratings, champions, size=clamp_field(size))
    field_keys = {p.key for p in seeded}
    out = sorted((p for p in rated if p.key not in field_keys),
                 key=lambda p: ratings[p.school].pi, reverse=True)[:out_n]
    out_board = [{"school": p.school, "conf": p.conf_abbr,
                  "pi": round(ratings[p.school].pi, 3), "rec": ratings[p.school].record}
                 for p in out]
    return seeded, autobids, out_board, ratings


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
    conn = _db()
    rows = conn.execute("SELECT * FROM duals WHERE season_id=? AND round='REG' AND (home=? OR away=?)"
                        " ORDER BY week", (season_id, school, school)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
    if key not in _pid_idx_cache:
        from app import economy
        idx = {}
        for p in load_division(division, gender).programs:
            for pr in build_roster(p):
                idx[pr.pid] = {"name": pr.name, "school": p.school, "class": pr.class_year,
                               "country": pr.country, "hometown": pr.hometown, "major": pr.major,
                               "walk_on": pr.walk_on, "high_school": pr.high_school,
                               "secondary_country": pr.secondary_country,
                               "school_city": p.location,
                               "scholarship": getattr(pr, "scholarship", 0.0),
                               "scholarship_label": economy.fraction_label(
                                   getattr(pr, "scholarship", 0.0))}
        _pid_idx_cache[key] = idx
    return _pid_idx_cache[key]


def player_info(season_id: int, pid: str) -> dict | None:
    s = load_season(season_id)
    return _pid_index(s["division"], s["gender"]).get(pid)


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
    _str_cache.clear()
    _str_cache[key] = res
    return res


_prec_cache: dict = {}


def player_records(season_id: int) -> dict:
    """One-pass ``pid -> (wins, losses)`` over all completed singles lines —
    cheaper than calling player_log per player. Cached by completed-dual count."""
    conn = _db()
    cnt = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND status='final'",
                       (season_id,)).fetchone()["c"]
    key = (season_id, cnt)
    if key not in _prec_cache:
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
        _prec_cache.clear()
        _prec_cache[key] = {k: (v[0], v[1]) for k, v in rec.items()}
    conn.close()
    return _prec_cache[key]


_pline_cache: dict = {}


def player_primary_lines(season_id: int) -> dict:
    """``pid -> primary singles line`` (the lineup slot played most this season),
    one pass over completed lines. Cached by completed-dual count."""
    conn = _db()
    cnt = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND status='final'",
                       (season_id,)).fetchone()["c"]
    key = (season_id, cnt)
    if key not in _pline_cache:
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
        _pline_cache.clear()
        _pline_cache[key] = {pid: max(d, key=d.get) for pid, d in tally.items() if d}
    conn.close()
    return _pline_cache[key]


_plrec_cache: dict = {}


def player_line_records(season_id: int) -> dict:
    """Per-player W-L by lineup line —
    ``{pid: {'singles': {n: [w, l]}, 'doubles': {n: [w, l]}}}`` (n = 1..6 singles,
    1..3 doubles). One pass over completed dual lines; cached by completed count."""
    conn = _db()
    cnt = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND status='final'",
                       (season_id,)).fetchone()["c"]
    key = (season_id, cnt)
    if key not in _plrec_cache:
        rows = conn.execute("SELECT lines_json FROM duals WHERE season_id=? AND status='final'",
                            (season_id,)).fetchall()
        rec: dict = {}

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
        _plrec_cache.clear()
        _plrec_cache[key] = rec
    conn.close()
    return _plrec_cache[key]


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
            if ln.get("home_pid") == pid:
                gf, ga, won, opp, opp_school = (ln["home_games"], ln["away_games"],
                                                ln["home_won"], ln.get("away_pid"), r["away"])
                sets = [[h, a] for (h, a) in raw_sets]
            elif ln.get("away_pid") == pid:
                gf, ga, won, opp, opp_school = (ln["away_games"], ln["home_games"],
                                                not ln["home_won"], ln.get("home_pid"), r["home"])
                sets = [[a, h] for (h, a) in raw_sets]   # flip to the player's POV
            else:
                continue
            phase = "Regular" if r["round"] == "REG" else (r["conf"] or r["round"])
            log.append({"phase": phase, "round": r["round"], "slot": ln["slot"],
                        "opp": idx.get(opp, {}).get("name", "—"), "opp_pid": opp,
                        "opp_school": opp_school, "week": r["week"],
                        "sets": sets, "gf": gf, "ga": ga, "won": won})
    return log
