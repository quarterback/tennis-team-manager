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


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    for col in ("round_no INTEGER DEFAULT 0", "bpos INTEGER DEFAULT 0"):
        try:
            conn.execute(f"ALTER TABLE duals ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
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
        for d in due:
            _play_and_store(conn, s, progs, d["id"], d["home"], d["away"], d["is_conf"], f"reg{wk}")
        nxt = wk + 1
        phase = "regular" if nxt <= s["total_weeks"] else "conf_tournaments"
        conn.execute("UPDATE seasons SET current_week=?, phase=? WHERE id=?", (nxt, phase, season_id))
        conn.commit(); conn.close()
        return {"phase": "regular", "week": wk, "played": len(due), "next_phase": phase}

    if s["phase"] == "conf_tournaments":
        out = _advance_conf_round(conn, s, progs)
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
    for d in due:
        _play_and_store(conn, s, progs, d["id"], d["home"], d["away"], d["is_conf"],
                        f"{prefix}{round_no}b{d['bpos']}")
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
    conn.execute("UPDATE seasons SET phase='ncaa', champion=? WHERE id=?",
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
    out = {}
    for conf, members in div.conferences.items():
        table = sorted(members, key=lambda p: (cf.get(p.school, [0, 0])[0]
                       - cf.get(p.school, [0, 0])[1]), reverse=True)
        out[conf] = [{"school": p.school, "ow": ov.get(p.school, [0, 0])[0],
                      "ol": ov.get(p.school, [0, 0])[1], "cw": cf.get(p.school, [0, 0])[0],
                      "cl": cf.get(p.school, [0, 0])[1]} for p in table]
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


# --------------------------------------------------------------------------
# Player cards — match-by-match log + season STR
# --------------------------------------------------------------------------

from .ncaa import build_roster

_pid_idx_cache: dict = {}
_str_cache: dict = {}


def _pid_index(division: str, gender: str) -> dict:
    key = (division, gender)
    if key not in _pid_idx_cache:
        idx = {}
        for p in load_division(division, gender).programs:
            for pr in build_roster(p):
                idx[pr.pid] = {"name": pr.name, "school": p.school, "class": pr.class_year,
                               "country": pr.country, "hometown": pr.hometown, "major": pr.major,
                               "walk_on": pr.walk_on, "high_school": pr.high_school,
                               "secondary_country": pr.secondary_country}
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
    if key in _str_cache:
        conn.close()
        return _str_cache[key]
    duals = _completed(conn, season_id)
    conn.close()
    s = load_season(season_id)
    priors = {pr.pid: pr.str_value() for p in load_division(s["division"], s["gender"]).programs
              for pr in build_roster(p)}
    res = converge_ids(build_corpus(duals), priors=priors)
    _str_cache.clear()
    _str_cache[key] = res
    return res


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
            if ln.get("home_pid") == pid:
                gf, ga, won, opp, opp_school = (ln["home_games"], ln["away_games"],
                                                ln["home_won"], ln.get("away_pid"), r["away"])
            elif ln.get("away_pid") == pid:
                gf, ga, won, opp, opp_school = (ln["away_games"], ln["home_games"],
                                                not ln["home_won"], ln.get("home_pid"), r["home"])
            else:
                continue
            phase = "Regular" if r["round"] == "REG" else (r["conf"] or r["round"])
            log.append({"phase": phase, "round": r["round"], "slot": ln["slot"],
                        "opp": idx.get(opp, {}).get("name", "—"), "opp_school": opp_school,
                        "gf": gf, "ga": ga, "won": won})
    return log
