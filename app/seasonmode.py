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

from .ncaa import load_division
from .season import dual_between, build_corpus
from .rating import compute_ratings
from .str_rating import converge_ids
from .bracket import select_field, run_bracket, _seed_positions, ROUND_NAMES, clamp_field

DB_PATH = os.environ.get("TENNIS_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "tennis.db"))
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
  home_points INTEGER, away_points INTEGER, winner INTEGER, lines_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_duals_season ON duals(season_id, round, week);
"""


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


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
    nc_count = {s: 0 for s in allschools}
    pairs = set()
    nonconf = []
    order = allschools[:]
    rng.shuffle(order)
    for s in order:
        tries = 0
        while nc_count[s] < NONCONF_PER_TEAM and tries < 60:
            tries += 1
            o = rng.choice(allschools)
            if o == s or school_conf[o] == school_conf[s] or nc_count[o] >= NONCONF_PER_TEAM:
                continue
            key = tuple(sorted((s, o)))
            if key in pairs:
                continue
            pairs.add(key)
            nc_count[s] += 1
            nc_count[o] += 1
            home, away = (s, o) if rng.random() < 0.5 else (o, s)
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

def _play_and_store(conn, s, progs, dual_id, home, away, is_conf, tag):
    rec = dual_between(progs[home], progs[away],
                       seed=_dual_seed(s["seed"], home, away, tag), conf=bool(is_conf))
    winner = 0 if rec["home_won"] else 1
    conn.execute("UPDATE duals SET status='final', home_points=?, away_points=?, winner=?,"
                 " lines_json=? WHERE id=?",
                 (rec["home_points"], rec["away_points"], winner, json.dumps(rec["lines"]), dual_id))
    return rec


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
        for d in due:
            _play_and_store(conn, s, progs, d["id"], d["home"], d["away"], d["is_conf"], f"reg{wk}")
        nxt = wk + 1
        phase = "regular" if nxt <= s["total_weeks"] else "conf_tournaments"
        conn.execute("UPDATE seasons SET current_week=?, phase=? WHERE id=?", (nxt, phase, season_id))
        conn.commit(); conn.close()
        return {"phase": "regular", "week": wk, "played": len(due), "next_phase": phase}

    if s["phase"] == "conf_tournaments":
        champions = _run_conf_tournaments(conn, s, progs)
        conn.execute("UPDATE seasons SET phase='ncaa', champion=? WHERE id=?",
                     (json.dumps(champions), season_id))
        conn.commit(); conn.close()
        return {"phase": "conf_tournaments", "champions": champions}

    if s["phase"] == "ncaa":
        champ = _run_ncaa(conn, s, progs)
        conn.execute("UPDATE seasons SET phase='complete', champion=? WHERE id=?", (champ, season_id))
        conn.commit(); conn.close()
        return {"phase": "ncaa", "champion": champ}

    conn.close()
    return {"phase": s["phase"]}


def _completed_reg_duals(conn, season_id) -> list[dict]:
    rows = conn.execute("SELECT home, away, is_conf, home_points, away_points, winner, lines_json"
                        " FROM duals WHERE season_id=? AND round='REG' AND status='final'",
                        (season_id,)).fetchall()
    out = []
    for r in rows:
        out.append({"home": r["home"], "away": r["away"], "conf": bool(r["is_conf"]),
                    "home_won": r["winner"] == 0, "home_points": r["home_points"],
                    "away_points": r["away_points"], "lines": json.loads(r["lines_json"] or "[]")})
    return out


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


def _run_conf_tournaments(conn, s, progs) -> dict:
    div = load_division(s["division"], s["gender"])
    duals = _completed_reg_duals(conn, season_id=s["id"])
    wl = _conf_standings(duals, div)
    ratings = compute_ratings(duals)
    champions = {}
    for conf, members in div.conferences.items():
        order = sorted(members, key=lambda p: (wl.get(p.school, [0, 0])[0]
                       / max(1, sum(wl.get(p.school, [0, 0]))), ratings[p.school].pi
                       if p.school in ratings else 0), reverse=True)
        seeds = order[:min(CONF_TOURNEY_FIELD, len(order))]
        champ = _single_elim(conn, s, progs, seeds, conf)
        champions[conf] = champ
    return champions


def _single_elim(conn, s, progs, seeds, conf_tag) -> str:
    import random
    n = 1
    while n < len(seeds):
        n *= 2
    positions = _seed_positions(n)
    slots = [seeds[i - 1].school if i <= len(seeds) else None for i in positions]
    rnd = 1
    while len([x for x in slots if x]) > 1:
        nxt = []
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if not a or not b:
                nxt.append(a or b); continue
            cur = conn.execute(
                "INSERT INTO duals (season_id, week, round, conf, is_conf, home, away, status)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (s["id"], 0, f"CT-{conf_tag}", conf_tag, 1, a, b, "scheduled"))
            rec = _play_and_store(conn, s, progs, cur.lastrowid, a, b, 1, f"ct{conf_tag}{rnd}")
            nxt.append(a if rec["home_won"] else b)
        slots = nxt; rnd += 1
    return next(x for x in slots if x)


def _run_ncaa(conn, s, progs) -> str:
    div = load_division(s["division"], s["gender"])
    duals = _completed_reg_duals(conn, season_id=s["id"])
    ratings = compute_ratings(duals)
    champs_map = json.loads(load_season(s["id"])["champion"] or "{}")
    champions = [progs[v] for v in champs_map.values() if v in progs]
    seeded, autobids = select_field(div.programs, ratings, champions, size=NATIONAL_FIELD)
    br = run_bracket(seeded, autobids, seed=s["seed"], fidelity="fast", final_fidelity="fast")
    seedmap = {p.school: i + 1 for i, p in enumerate(seeded)}
    for rnd in br.rounds:
        for m in rnd:
            conn.execute(
                "INSERT INTO duals (season_id, week, round, conf, is_conf, home, away, status,"
                " winner) VALUES (?,?,?,?,?,?,?,?,?)",
                (s["id"], 0, f"NCAA-{m.rnd}", None, 0, m.hi.school, m.lo.school, "final",
                 0 if m.winner is m.hi else 1))
    conn.commit()
    return br.champion.school


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------

def standings(season_id: int) -> dict:
    s = load_season(season_id)
    div = load_division(s["division"], s["gender"])
    conn = _db()
    duals = _completed_reg_duals(conn, season_id)
    conn.close()
    # overall + conference W/L
    ov, cf = {}, {}
    for d in duals:
        for t in (d["home"], d["away"]):
            ov.setdefault(t, [0, 0]); cf.setdefault(t, [0, 0])
        hw = d["home_won"]
        ov[d["home"]][0 if hw else 1] += 1
        ov[d["away"]][1 if hw else 0] += 1
        if d["conf"]:
            cf[d["home"]][0 if hw else 1] += 1
            cf[d["away"]][1 if hw else 0] += 1
    out = {}
    for conf, members in div.conferences.items():
        table = sorted(members, key=lambda p: (cf.get(p.school, [0, 0])[0]
                       - cf.get(p.school, [0, 0])[1]), reverse=True)
        out[conf] = [{"school": p.school, "ow": ov.get(p.school, [0, 0])[0],
                      "ol": ov.get(p.school, [0, 0])[1], "cw": cf.get(p.school, [0, 0])[0],
                      "cl": cf.get(p.school, [0, 0])[1]} for p in table]
    return out


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
