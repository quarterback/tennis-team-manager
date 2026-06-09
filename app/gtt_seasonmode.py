"""
GTT career mode — a persistent, multi-season co-ed pro league with a college
pipeline.

Forked in spirit from ``app.seasonmode`` but rebuilt as a **career engine**:
franchises carry rosters of **real, persisted players** season over season; the
inaugural league is generated (those founding pros never went to college), and
from then on each off-season pulls that year's **college graduates** out of the
world (``world_roster`` seniors) into a free-agent pool, ages and retires the
veterans, runs a **keeper + snake draft**, then plays the season.

Why this shape (per the design):

  * **Honors follow a player college → pro.** A graduate keeps their real college
    ``pid``, so a GTT MVP/championship is stamped to the same id as their college
    Player-of-the-Year — the player's page shows one continuous career. Founding
    pros get a generated pid (no college history, which is correct).
  * **Multi-season.** Players persist in ``gtt_players``; rosters age, retire, and
    refresh from the graduate pool each off-season.
  * **Draft + keepers.** Each off-season every franchise keeps its holdovers and
    a reverse-standings snake draft fills the open slots from the pool.

Identity is keyed off the franchise *id* and the player *pid*, never display
names — so renaming/relocating a franchise is purely cosmetic.

Phases of a season: ``regular`` → ``playoffs`` → ``complete``. Advancing from
``complete`` runs the off-season and opens the next season at ``regular`` week 1.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3

from . import dbpath
from .dbpath import resolve_db_path

from engine import simulate_gtt_dual, GTTTeam
from generators import make_name_picker, random_town
from .development import generate_prospect

DB_PATH = resolve_db_path()

DEFAULT_TEAMS = 8
ROUND_ROBINS = 2            # double round-robin
PLAYOFF_FIELD = 4           # top-N make the single-elimination playoff
TARGET_MEN = 4              # roster targets per gender (lineup fields the top 3)
TARGET_WOMEN = 4
LINES_TO_CLINCH = 5
ENTRY_AGE = 22              # a graduate's age on turning pro
RETIRE_AGE = 34            # hard retirement age
RETIRE_FROM = 30           # probabilistic retirement begins here
BASE_YEAR = 2027           # GTT calendar starts the year after the college baseline

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gtt_leagues (
  id INTEGER PRIMARY KEY, name TEXT, world_seed INTEGER, current_year INTEGER,
  current_week INTEGER, total_weeks INTEGER, phase TEXT, champion INTEGER
);
CREATE TABLE IF NOT EXISTS gtt_franchises (
  id INTEGER PRIMARY KEY, league_id INTEGER, name TEXT, city TEXT, abbrev TEXT
);
CREATE TABLE IF NOT EXISTS gtt_players (
  id INTEGER PRIMARY KEY, league_id INTEGER, pid TEXT, gender TEXT,
  fid INTEGER, status TEXT, age INTEGER, seasons INTEGER, joined_year INTEGER,
  origin TEXT, data TEXT
);
CREATE TABLE IF NOT EXISTS gtt_seasons (
  league_id INTEGER, year INTEGER, phase TEXT, champion INTEGER, mvp_pid TEXT
);
CREATE TABLE IF NOT EXISTS gtt_duals (
  id INTEGER PRIMARY KEY, league_id INTEGER, year INTEGER, week INTEGER, round TEXT,
  home INTEGER, away INTEGER, status TEXT,
  home_points INTEGER, away_points INTEGER, winner INTEGER, lines_json TEXT,
  round_no INTEGER DEFAULT 0, bpos INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_gtt_duals ON gtt_duals(league_id, year, round, week);
CREATE INDEX IF NOT EXISTS idx_gtt_pl ON gtt_players(league_id, fid, status);
CREATE INDEX IF NOT EXISTS idx_gtt_fr ON gtt_franchises(league_id);
"""

_schema_ready_for = None


def init_schema() -> None:
    global _schema_ready_for
    conn = dbpath.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    _schema_ready_for = DB_PATH


def _db() -> sqlite3.Connection:
    if _schema_ready_for != DB_PATH:
        init_schema()
    return dbpath.connect(DB_PATH)


def _h(*parts) -> int:
    raw = "|".join(str(p) for p in parts).encode()
    return int.from_bytes(hashlib.blake2s(raw, digest_size=4).digest(), "big")


def _dual_seed(seed, home_fid, away_fid, tag) -> int:
    return _h(seed, home_fid, away_fid, tag)


# --------------------------------------------------------------------------
# Player (de)hydration — players are stored as Prospect dicts
# --------------------------------------------------------------------------

def _prospect(data):
    from app.world import prospect_from_dict
    return prospect_from_dict(json.loads(data) if isinstance(data, str) else data)


def _prospect_dict(p):
    from app.world import prospect_to_dict
    return prospect_to_dict(p)


# --------------------------------------------------------------------------
# Default franchise identities (cosmetic — fully user-editable)
# --------------------------------------------------------------------------

_MASCOTS = None


def _mascots():
    global _MASCOTS
    if _MASCOTS is None:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "generators", "data", "names", "team_naming.json")
        pool = []
        try:
            with open(path) as f:
                mp = json.load(f).get("category_3_traditional_mascots", {}).get("mascot_pool", {})
            for grp in mp.values():
                if isinstance(grp, list):
                    pool.extend(grp)
        except (OSError, ValueError):
            pass
        _MASCOTS = pool or ["Aces", "Smash", "Strings", "Breakers", "Lobsters"]
    return _MASCOTS


def _abbrev(city, mascot):
    base = "".join(ch for ch in city.upper() if ch.isalpha())
    return (base[:3] or mascot.upper()[:3]).ljust(3, "X")[:3]


def _default_franchise(rng):
    city, state = random_town(rng)
    mascot = rng.choice(_mascots())
    return f"{city} {mascot}", (f"{city}, {state}" if state else city), _abbrev(city, mascot)


# --------------------------------------------------------------------------
# Player generation (founding pros) + the college pipeline (graduates)
# --------------------------------------------------------------------------

def _gen_player(rng, name_fn, gender, talent, joined_year, origin="founder", age=None):
    name, country = name_fn()
    p = generate_prospect(rng, name, country, gender=gender, talent=talent)
    return {"pid": p.pid, "gender": gender, "data": json.dumps(_prospect_dict(p)),
            "age": age if age is not None else rng.randint(23, 28),
            "joined_year": joined_year, "origin": origin}


def _world_graduates(conn, world_seed, exclude_pids, limit):
    """This year's college graduates (seniors in the world) as (gender, pid, data),
    best STR first, excluding pids already in the league. Empty if no world.

    Queried through the caller's connection because the world tables live in the
    same DB file — opening a second connection mid-transaction would deadlock."""
    try:
        wid = conn.execute("SELECT id FROM world WHERE seed=?", (world_seed,)).fetchone()
    except sqlite3.OperationalError:
        return []                                       # world tables not created yet
    if not wid:
        return []
    wid = wid["id"]
    year = conn.execute("SELECT MAX(year) y FROM world_roster WHERE world_id=?",
                        (wid,)).fetchone()["y"]
    if year is None:
        return []
    rows = conn.execute("SELECT gender, pid, data FROM world_roster WHERE world_id=? AND year=?",
                        (wid, year)).fetchall()
    grads = []
    for r in rows:
        if r["pid"] in exclude_pids:
            continue
        d = json.loads(r["data"])
        if d.get("class_year") != "Sr":
            continue
        g = "m" if r["gender"] in ("men", "male", "m") else "w"
        grads.append((g, r["pid"], r["data"], _prospect(r["data"]).str_value()))
    grads.sort(key=lambda x: x[3], reverse=True)
    return grads[:limit]


def _intake(conn, league, needed_by_gender):
    """Fill the free-agent pool for the off-season: real college graduates first,
    topped up with generated rookies so the league is always playable."""
    lid, seed, year = league["id"], league["world_seed"], league["current_year"]
    have = {r["pid"] for r in conn.execute("SELECT pid FROM gtt_players WHERE league_id=?",
                                           (lid,)).fetchall()}
    total = needed_by_gender["m"] + needed_by_gender["w"]
    grads = _world_graduates(conn, seed, have, total + 4)
    pool_rows, used = {"m": [], "w": []}, set(have)
    for g, pid, data, _str in grads:
        if pid in used or len(pool_rows[g]) >= needed_by_gender[g] + 1:
            continue
        pool_rows[g].append({"pid": pid, "gender": g, "data": data, "age": ENTRY_AGE,
                             "joined_year": year, "origin": "college"})
        used.add(pid)
    # top up with generated rookies if the pipeline came up short
    rng = random.Random(_h(seed, lid, "rookies", year))
    for g, full in (("m", "male"), ("w", "female")):
        name_fn = make_name_picker(random.Random(_h(seed, lid, g, year)), gender=full)
        while len(pool_rows[g]) < needed_by_gender[g]:
            row = _gen_player(rng, name_fn, g, rng.uniform(46, 60), year,
                              origin="rookie", age=ENTRY_AGE)
            if row["pid"] in used:
                continue
            pool_rows[g].append(row)
            used.add(row["pid"])
    for g in ("m", "w"):
        for r in pool_rows[g]:
            conn.execute(
                "INSERT INTO gtt_players (league_id, pid, gender, fid, status, age,"
                " seasons, joined_year, origin, data) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (lid, r["pid"], g, None, "active", r["age"], 0, r["joined_year"],
                 r["origin"], r["data"]))


# --------------------------------------------------------------------------
# Roster / lineup helpers
# --------------------------------------------------------------------------

def _active(conn, lid, fid, gender=None):
    q = "SELECT pid, gender, age, data FROM gtt_players WHERE league_id=? AND fid=? AND status='active'"
    args = [lid, fid]
    if gender:
        q += " AND gender=?"
        args.append(gender)
    return [dict(r) for r in conn.execute(q, args).fetchall()]


def _lineup(conn, lid, fid, name):
    """Top 3 men + top 3 women by STR → a GTTTeam, plus the ordered pid lists."""
    def top(gender):
        ps = _active(conn, lid, fid, gender)
        ps.sort(key=lambda r: _prospect(r["data"]).str_value(), reverse=True)
        return ps[:3]
    men, women = top("m"), top("w")
    team = GTTTeam(name=name,
                   men=[_prospect(r["data"]).engine_player() for r in men],
                   women=[_prospect(r["data"]).engine_player() for r in women])
    return team, [r["pid"] for r in men], [r["pid"] for r in women]


def _line_pids(slot, men_pids, women_pids):
    kind, num = slot[:2], int(slot[2:]) - 1
    if kind == "MS":
        return [men_pids[num]] if num < len(men_pids) else []
    if kind == "WS":
        return [women_pids[num]] if num < len(women_pids) else []
    out = []
    if num < len(men_pids):
        out.append(men_pids[num])
    if num < len(women_pids):
        out.append(women_pids[num])
    return out


# --------------------------------------------------------------------------
# League creation (the founding season)
# --------------------------------------------------------------------------

def _round_robin(fids):
    teams = list(fids)
    if len(teams) % 2:
        teams.append(None)
    n = len(teams)
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = teams[i], teams[n - 1 - i]
            if a is None or b is None:
                continue
            pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        rounds.append(pairs)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return rounds


def _build_schedule(conn, lid, year, seed):
    fids = [f["id"] for f in _fr_rows(conn, lid)]
    order = list(fids)
    random.Random(_h(seed, "order", year)).shuffle(order)
    week = 0
    rows = []
    for rr in range(ROUND_ROBINS):
        for rnd in _round_robin(order):
            week += 1
            for (h, a) in rnd:
                if rr % 2 == 1:
                    h, a = a, h
                rows.append((lid, year, week, "REG", h, a, "scheduled"))
    conn.executemany(
        "INSERT INTO gtt_duals (league_id, year, week, round, home, away, status)"
        " VALUES (?,?,?,?,?,?,?)", rows)
    total = max((w for (_, _, w, *_rest) in rows), default=0)
    conn.execute("UPDATE gtt_leagues SET total_weeks=?, current_week=1 WHERE id=?", (total, lid))


def create_league(name="Global Team Tennis", *, seed=2026, n_teams=DEFAULT_TEAMS):
    conn = _db()
    cur = conn.execute(
        "INSERT INTO gtt_leagues (name, world_seed, current_year, current_week,"
        " total_weeks, phase, champion) VALUES (?,?,?,?,?,?,?)",
        (name, seed, 0, 1, 0, "regular", None))
    lid = cur.lastrowid

    rng = random.Random(_h(seed, "franchises"))
    fids, seen = [], set()
    for _ in range(n_teams):
        fname, city, abbrev = _default_franchise(rng)
        while fname in seen:
            fname, city, abbrev = _default_franchise(rng)
        seen.add(fname)
        c = conn.execute("INSERT INTO gtt_franchises (league_id, name, city, abbrev)"
                         " VALUES (?,?,?,?)", (lid, fname, city, abbrev))
        fids.append(c.lastrowid)

    # Founding rosters: generated pros (no college history), strength banded per club.
    for fid in fids:
        base = 48 + 16 * (_h(seed, fid, "base") / 0xFFFFFFFF)
        prng = random.Random(_h(seed, fid, "founders"))
        men_fn = make_name_picker(random.Random(_h(seed, fid, "m")), gender="male")
        women_fn = make_name_picker(random.Random(_h(seed, fid, "w")), gender="female")
        for gender, name_fn, tgt in (("m", men_fn, TARGET_MEN), ("w", women_fn, TARGET_WOMEN)):
            for _ in range(tgt):
                r = _gen_player(prng, name_fn, gender, prng.gauss(base, 5), 0)
                conn.execute(
                    "INSERT INTO gtt_players (league_id, pid, gender, fid, status, age,"
                    " seasons, joined_year, origin, data) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (lid, r["pid"], gender, fid, "active", r["age"], 0, 0, "founder", r["data"]))

    _build_schedule(conn, lid, 0, seed)
    conn.commit()
    conn.close()
    return lid


def load_league(league_id):
    conn = _db()
    row = conn.execute("SELECT * FROM gtt_leagues WHERE id=?", (league_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_leagues():
    conn = _db()
    rows = conn.execute("SELECT * FROM gtt_leagues ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def franchises(league_id):
    conn = _db()
    rows = conn.execute("SELECT * FROM gtt_franchises WHERE league_id=? ORDER BY id",
                        (league_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _franchise_names(league_id):
    return {f["id"]: f["name"] for f in franchises(league_id)}


def _fr_rows(conn, league_id):
    """Franchises read through an OPEN connection — sees rows written in the same
    (uncommitted) transaction, which the public helper's fresh connection cannot."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM gtt_franchises WHERE league_id=? ORDER BY id", (league_id,)).fetchall()]


def _fr_names(conn, league_id):
    return {f["id"]: f["name"] for f in _fr_rows(conn, league_id)}


# --------------------------------------------------------------------------
# Editor — rename / relocate (cosmetic; keyed off the id, never the name)
# --------------------------------------------------------------------------

def edit_franchise(franchise_id, *, name=None, city=None, abbrev=None):
    sets, vals = [], []
    if name is not None:
        sets.append("name=?"); vals.append(name.strip())
    if city is not None:
        sets.append("city=?"); vals.append(city.strip())
    if abbrev is not None:
        sets.append("abbrev=?"); vals.append(abbrev.strip().upper()[:3])
    if not sets:
        return
    vals.append(franchise_id)
    conn = _db()
    conn.execute(f"UPDATE gtt_franchises SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    conn.close()


def rename_franchise(franchise_id, name):
    edit_franchise(franchise_id, name=name)


def relocate_franchise(franchise_id, city, abbrev=None):
    edit_franchise(franchise_id, city=city, abbrev=abbrev)


# --------------------------------------------------------------------------
# Playing a dual
# --------------------------------------------------------------------------

def _play_and_store(conn, league, dual_id, home_fid, away_fid, tag, fidelity):
    lid, seed = league["id"], league["world_seed"]
    names = _fr_names(conn, lid)
    home, hm, hw = _lineup(conn, lid, home_fid, names.get(home_fid, str(home_fid)))
    away, am, aw = _lineup(conn, lid, away_fid, names.get(away_fid, str(away_fid)))
    res = simulate_gtt_dual(home, away, seed=_dual_seed(seed, home_fid, away_fid, tag),
                            fidelity=fidelity)
    lines = []
    for ln in res.lines:
        lines.append({"slot": ln.slot, "home_won": ln.home_won, "completed": ln.completed,
                      "scoreline": (ln.result.scoreline if ln.completed and ln.result else None),
                      "home_pids": _line_pids(ln.slot, hm, hw) if ln.completed else [],
                      "away_pids": _line_pids(ln.slot, am, aw) if ln.completed else []})
    conn.execute("UPDATE gtt_duals SET status='final', home_points=?, away_points=?,"
                 " winner=?, lines_json=? WHERE id=?",
                 (res.home_points, res.away_points, res.winner, json.dumps(lines), dual_id))
    return res


# --------------------------------------------------------------------------
# Advancing — the season + off-season state machine
# --------------------------------------------------------------------------

def advance(league_id, *, fidelity="full"):
    s = load_league(league_id)
    if not s:
        return {"phase": "none"}
    conn = _db()
    year = s["current_year"]

    if s["phase"] == "regular":
        wk = s["current_week"]
        due = conn.execute("SELECT * FROM gtt_duals WHERE league_id=? AND year=? AND round='REG'"
                           " AND week=? AND status='scheduled'", (league_id, year, wk)).fetchall()
        for d in due:
            _play_and_store(conn, s, d["id"], d["home"], d["away"], f"y{year}w{wk}", fidelity)
        nxt = wk + 1
        phase = "regular" if nxt <= s["total_weeks"] else "playoffs"
        conn.execute("UPDATE gtt_leagues SET current_week=?, phase=? WHERE id=?",
                     (nxt, phase, league_id))
        conn.commit(); conn.close()
        return {"phase": "regular", "year": year, "week": wk, "played": len(due), "next_phase": phase}

    if s["phase"] == "playoffs":
        out = _advance_playoff_round(conn, s, fidelity)
        conn.commit(); conn.close()
        _flush_honors(out)
        return out

    if s["phase"] == "complete":
        out = _offseason(conn, s, fidelity)
        conn.commit(); conn.close()
        return out

    conn.close()
    return {"phase": s["phase"]}


def advance_all(league_id, *, fidelity="fast"):
    """Advance to the end of the CURRENT season (stops at 'complete')."""
    out = {}
    for _ in range(10_000):
        s = load_league(league_id)
        if not s or s["phase"] == "complete":
            break
        out = advance(league_id, fidelity=fidelity)
    return out or {"phase": "complete"}


def advance_seasons(league_id, n, *, fidelity="fast"):
    """Play `n` whole seasons (finishing the current one, then rolling onward)."""
    for _ in range(n):
        advance_all(league_id, fidelity=fidelity)
        s = load_league(league_id)
        if s and s["phase"] == "complete":
            advance(league_id, fidelity=fidelity)      # roll the off-season into next season
    return load_league(league_id)


# --------------------------------------------------------------------------
# Playoffs
# --------------------------------------------------------------------------

def _pow2_le(n):
    p = 1
    while p * 2 <= n:
        p *= 2
    return p


def _seed_positions(n):
    pos = [1, 2]
    while len(pos) < n:
        m = len(pos) * 2
        pos = [x for p in pos for x in (p, m + 1 - p)]
    return pos


def _next_post_week(conn, lid, year):
    return (conn.execute("SELECT MAX(week) w FROM gtt_duals WHERE league_id=? AND year=?",
                         (lid, year)).fetchone()["w"] or 0) + 1


def _insert_po(conn, lid, year, week, round_no, bpos, home, away):
    conn.execute("INSERT INTO gtt_duals (league_id, year, week, round, home, away, status,"
                 " round_no, bpos) VALUES (?,?,?,?,?,?,?,?,?)",
                 (lid, year, week, "PO", home, away, "scheduled", round_no, bpos))


def _advance_playoff_round(conn, s, fidelity):
    lid, year = s["id"], s["current_year"]
    existing = conn.execute("SELECT COUNT(*) c FROM gtt_duals WHERE league_id=? AND year=?"
                            " AND round='PO'", (lid, year)).fetchone()["c"]
    if existing == 0:
        order = [r["fid"] for r in _standings_rows(conn, lid, year)]
        field = _pow2_le(min(PLAYOFF_FIELD, len(order)))
        if field < 2:
            return _crown(conn, s, order[0] if order else None)
        seeded = order[:field]
        slots = [seeded[i - 1] for i in _seed_positions(field)]
        week = _next_post_week(conn, lid, year)
        for k in range(field // 2):
            a, b = slots[2 * k], slots[2 * k + 1]
            hi = a if seeded.index(a) < seeded.index(b) else b
            lo = b if hi == a else a
            _insert_po(conn, lid, year, week, 1, k, hi, lo)
        round_no = 1
    else:
        round_no = conn.execute("SELECT MIN(round_no) r FROM gtt_duals WHERE league_id=? AND year=?"
                                " AND round='PO' AND status='scheduled'", (lid, year)).fetchone()["r"]
    if round_no is None:
        return _crown(conn, s, s["champion"])

    due = conn.execute("SELECT * FROM gtt_duals WHERE league_id=? AND year=? AND round='PO'"
                       " AND round_no=? AND status='scheduled' ORDER BY bpos",
                       (lid, year, round_no)).fetchall()
    for d in due:
        _play_and_store(conn, s, d["id"], d["home"], d["away"], f"y{year}po{round_no}b{d['bpos']}", fidelity)

    wins = conn.execute("SELECT home, away, winner FROM gtt_duals WHERE league_id=? AND year=?"
                        " AND round='PO' AND round_no=? ORDER BY bpos", (lid, year, round_no)).fetchall()
    winners = [w["home"] if w["winner"] == 0 else w["away"] for w in wins]
    if len(winners) > 1:
        week = _next_post_week(conn, lid, year)
        for k in range(len(winners) // 2):
            _insert_po(conn, lid, year, week, round_no + 1, k, winners[2 * k], winners[2 * k + 1])
        return {"phase": "playoffs", "year": year, "round": round_no, "played": len(due)}
    return _crown(conn, s, winners[0])


def _crown(conn, s, champ_fid):
    lid, year = s["id"], s["current_year"]
    mvp_row = _compute_mvp(conn, lid, year)
    mvp_pid = mvp_row["pid"] if mvp_row else None
    conn.execute("UPDATE gtt_leagues SET phase='complete', champion=? WHERE id=?", (champ_fid, lid))
    conn.execute("DELETE FROM gtt_seasons WHERE league_id=? AND year=?", (lid, year))
    conn.execute("INSERT INTO gtt_seasons (league_id, year, phase, champion, mvp_pid)"
                 " VALUES (?,?,?,?,?)", (lid, year, "complete", champ_fid, mvp_pid))
    # Honor rows are computed here but stamped after this connection commits/closes
    # (app.honors opens its own connection — stamping mid-transaction would deadlock).
    recs = _honor_records(conn, s, champ_fid, mvp_row)
    return {"phase": "playoffs", "year": year, "champion": champ_fid, "mvp": mvp_pid, "_honors": recs}


def _flush_honors(out):
    """Stamp any honor rows a just-finished crown produced, after the season DB
    write has been committed and its connection closed."""
    recs = (out or {}).pop("_honors", None)
    if recs:
        import app.honors as honors
        honors.stamp(recs)


# --------------------------------------------------------------------------
# Off-season: age → retire → intake → keeper/snake draft → schedule
# --------------------------------------------------------------------------

def _should_retire(pid, age, year):
    if age >= RETIRE_AGE:
        return True
    if age < RETIRE_FROM:
        return False
    prob = (age - RETIRE_FROM + 1) * 0.18
    return (_h(pid, "retire", year) / 0xFFFFFFFF) < prob


def _offseason(conn, s, fidelity):
    lid, prev_year = s["id"], s["current_year"]
    year = prev_year + 1

    # Age everyone a year; retire the veterans (off active rosters).
    for r in conn.execute("SELECT id, pid, age FROM gtt_players WHERE league_id=? AND status='active'",
                          (lid,)).fetchall():
        age = (r["age"] or ENTRY_AGE) + 1
        if _should_retire(r["pid"], age, year):
            conn.execute("UPDATE gtt_players SET age=?, status='retired', fid=NULL WHERE id=?",
                         (age, r["id"]))
        else:
            conn.execute("UPDATE gtt_players SET age=?, seasons=seasons+1 WHERE id=?", (age, r["id"]))

    # Open slots per franchise drive how many graduates we need.
    fids = [f["id"] for f in _fr_rows(conn, lid)]
    need = {"m": 0, "w": 0}
    for fid in fids:
        for g, tgt in (("m", TARGET_MEN), ("w", TARGET_WOMEN)):
            have = len(_active(conn, lid, fid, g))
            need[g] += max(0, tgt - have)
    league_row = {**s, "current_year": year}
    _intake(conn, league_row, need)

    # Keepers stay on roster; a reverse-standings snake draft fills the gaps.
    _draft(conn, lid, year, prev_year)

    conn.execute("UPDATE gtt_leagues SET current_year=?, phase='regular', current_week=1,"
                 " champion=NULL WHERE id=?", (year, lid))
    _build_schedule(conn, lid, year, s["world_seed"])
    return {"phase": "offseason", "year": year,
            "intake": need["m"] + need["w"]}


def _draft(conn, lid, year, prev_year):
    """Reverse-standings snake draft of the free-agent pool into open slots."""
    order = [r["fid"] for r in _standings_rows(conn, lid, prev_year)]
    if not order:
        order = [f["id"] for f in _fr_rows(conn, lid)]
    order = order[::-1]                                   # worst record drafts first

    pool = {"m": [], "w": []}
    for r in conn.execute("SELECT id, pid, gender, data FROM gtt_players WHERE league_id=?"
                          " AND fid IS NULL AND status='active'", (lid,)).fetchall():
        pool[r["gender"]].append((r["id"], _prospect(r["data"]).str_value()))
    for g in pool:
        pool[g].sort(key=lambda x: x[1], reverse=True)    # best available first

    counts = {fid: {"m": len(_active(conn, lid, fid, "m")),
                    "w": len(_active(conn, lid, fid, "w"))} for fid in order}
    for g, tgt in (("m", TARGET_MEN), ("w", TARGET_WOMEN)):
        rnd = 0
        while pool[g]:
            seq = order if rnd % 2 == 0 else order[::-1]
            picked = False
            for fid in seq:
                if counts[fid][g] >= tgt or not pool[g]:
                    continue
                pid_id, _str = pool[g].pop(0)
                conn.execute("UPDATE gtt_players SET fid=? WHERE id=?", (fid, pid_id))
                counts[fid][g] += 1
                picked = True
            rnd += 1
            if not picked:
                break


# --------------------------------------------------------------------------
# Honors (P3) — stamped to the player's real pid so they follow college → pro
# --------------------------------------------------------------------------

def _player_meta(conn, lid):
    rows = conn.execute("SELECT pid, gender, fid, data FROM gtt_players WHERE league_id=?",
                        (lid,)).fetchall()
    out = {}
    for r in rows:
        p = _prospect(r["data"])
        out[r["pid"]] = {"name": p.name, "country": p.country, "gender": r["gender"], "fid": r["fid"]}
    return out


def _records_for_year(conn, lid, year):
    rows = conn.execute("SELECT lines_json FROM gtt_duals WHERE league_id=? AND year=?"
                        " AND status='final'", (lid, year)).fetchall()
    rec = {}
    for r in rows:
        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed"):
                continue
            hw = ln["home_won"]
            for pid in ln.get("home_pids", []):
                d = rec.setdefault(pid, [0, 0]); d[0 if hw else 1] += 1
            for pid in ln.get("away_pids", []):
                d = rec.setdefault(pid, [0, 0]); d[1 if hw else 0] += 1
    return rec


def _compute_mvp(conn, lid, year):
    rec = _records_for_year(conn, lid, year)
    meta = _player_meta(conn, lid)
    best = None
    for pid, (w, l) in rec.items():
        if w + l < 3:
            continue
        key = (w, w / (w + l))
        if best is None or key > best[0]:
            best = (key, pid, w, l)
    if not best:
        return None
    _key, pid, w, l = best
    m = meta.get(pid, {})
    return {"pid": pid, "name": m.get("name", pid), "w": w, "l": l, "fid": m.get("fid"),
            "franchise": _fr_names(conn, lid).get(m.get("fid"), "")}


def _honor_records(conn, s, champ_fid, mvp_row):
    """Build GTT honor rows under each player's real pid, so a graduate's college
    + pro honors live on one career page. Stamped by the caller post-commit."""
    lid, year = s["id"], s["current_year"]
    cal_year = BASE_YEAR + year
    names = _fr_names(conn, lid)
    recs = []
    if champ_fid:
        cname = names.get(champ_fid, "")
        for r in conn.execute("SELECT pid, gender, data FROM gtt_players WHERE league_id=?"
                              " AND fid=? AND status='active'", (lid, champ_fid)).fetchall():
            recs.append({"subject_type": "player", "subject_id": r["pid"],
                         "name": _prospect(r["data"]).name, "year": cal_year, "season_no": year + 1,
                         "division": "GTT", "gender": r["gender"], "school": cname,
                         "award": "gtt_champion", "label": f"{s['name']} Champion", "sort": 90})
    if mvp_row:
        recs.append({"subject_type": "player", "subject_id": mvp_row["pid"],
                     "name": mvp_row["name"], "year": cal_year, "season_no": year + 1,
                     "division": "GTT", "gender": None, "school": mvp_row["franchise"],
                     "award": "gtt_mvp", "label": f"{s['name']} MVP", "sort": 120})
    return recs


# --------------------------------------------------------------------------
# Standings & views
# --------------------------------------------------------------------------

def _standings_rows(conn, lid, year):
    fr = {f["id"]: f for f in [dict(r) for r in conn.execute(
        "SELECT * FROM gtt_franchises WHERE league_id=? ORDER BY id", (lid,)).fetchall()]}
    rec = {fid: {"w": 0, "l": 0, "lf": 0, "la": 0} for fid in fr}
    rows = conn.execute("SELECT home, away, home_points, away_points, winner FROM gtt_duals"
                        " WHERE league_id=? AND year=? AND round='REG' AND status='final'",
                        (lid, year)).fetchall()
    for d in rows:
        h, a = d["home"], d["away"]
        if h not in rec or a not in rec:
            continue
        rec[h]["lf"] += d["home_points"]; rec[h]["la"] += d["away_points"]
        rec[a]["lf"] += d["away_points"]; rec[a]["la"] += d["home_points"]
        if d["winner"] == 0:
            rec[h]["w"] += 1; rec[a]["l"] += 1
        else:
            rec[a]["w"] += 1; rec[h]["l"] += 1
    out = []
    for fid, f in fr.items():
        r = rec[fid]
        out.append({"fid": fid, "name": f["name"], "city": f["city"], "abbrev": f["abbrev"],
                    "w": r["w"], "l": r["l"], "lf": r["lf"], "la": r["la"], "diff": r["lf"] - r["la"]})
    out.sort(key=lambda x: (x["w"], x["diff"], -x["fid"]), reverse=True)
    return out


def standings(league_id, year=None):
    conn = _db()
    if year is None:
        year = (load_league(league_id) or {}).get("current_year", 0)
    rows = _standings_rows(conn, league_id, year)
    conn.close()
    return rows


def week_duals(league_id, week, year=None):
    conn = _db()
    s = load_league(league_id)
    year = year if year is not None else (s["current_year"] if s else 0)
    names = _franchise_names(league_id)
    rows = conn.execute("SELECT * FROM gtt_duals WHERE league_id=? AND year=? AND week=?"
                        " ORDER BY round, bpos, id", (league_id, year, week)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["home_name"] = names.get(d["home"], str(d["home"]))
        d["away_name"] = names.get(d["away"], str(d["away"]))
        d["lines"] = json.loads(d["lines_json"] or "[]")
        out.append(d)
    return out


def champion(league_id):
    s = load_league(league_id)
    if not s or s["phase"] != "complete" or s["champion"] is None:
        return None
    return {f["id"]: f for f in franchises(league_id)}.get(s["champion"])


def mvp(league_id, year=None):
    s = load_league(league_id)
    if not s:
        return None
    year = year if year is not None else s["current_year"]
    conn = _db()
    row = _compute_mvp(conn, league_id, year)
    conn.close()
    return row


def honors_board(league_id):
    return {"champion": champion(league_id), "mvp": mvp(league_id)}


def player_records(league_id, year=None):
    """gtt_pid (==real pid) -> record dict, for the current (or given) season."""
    s = load_league(league_id)
    if not s:
        return {}
    year = year if year is not None else s["current_year"]
    conn = _db()
    rec = _records_for_year(conn, league_id, year)
    meta = _player_meta(conn, league_id)
    conn.close()
    out = {}
    for pid, (w, l) in rec.items():
        m = meta.get(pid, {})
        out[pid] = {"pid": pid, "name": m.get("name", pid), "country": m.get("country", ""),
                    "fid": m.get("fid"), "franchise": _franchise_names(league_id).get(m.get("fid"), ""),
                    "gender": m.get("gender", ""), "w": w, "l": l}
    return out


def player_honors(league_id, pid):
    out = []
    m = mvp(league_id)
    if m and m["pid"] == pid:
        out.append("GTT MVP")
    ch = champion(league_id)
    if ch:
        conn = _db()
        row = conn.execute("SELECT fid FROM gtt_players WHERE league_id=? AND pid=?",
                           (league_id, pid)).fetchone()
        conn.close()
        if row and row["fid"] == ch["id"]:
            out.append("GTT Champion")
    return out


def franchise_roster(league_id, fid, year=None):
    """The franchise's current active roster with season records + honors."""
    s = load_league(league_id)
    if not s:
        return []
    year = year if year is not None else s["current_year"]
    conn = _db()
    rec = _records_for_year(conn, league_id, year)
    rows = conn.execute("SELECT pid, gender, age, origin, data FROM gtt_players WHERE league_id=?"
                        " AND fid=? AND status='active'", (league_id, fid)).fetchall()
    conn.close()
    players = []
    for r in rows:
        p = _prospect(r["data"])
        w, l = rec.get(r["pid"], [0, 0])
        players.append({"pid": r["pid"], "name": p.name, "country": p.country, "gender": r["gender"],
                        "age": r["age"], "origin": r["origin"], "str": round(p.str_value(), 1),
                        "overall": round(p.current_overall()), "w": w, "l": l,
                        "honors": player_honors(league_id, r["pid"])})
    # men by STR then women by STR
    players.sort(key=lambda x: (x["gender"] != "m", -x["str"]))
    for i, p in enumerate(players):
        block = [q for q in players if q["gender"] == p["gender"]]
        p["slot"] = f"{'M' if p['gender'] == 'm' else 'W'}S{block.index(p) + 1}"
    return players


def player_detail(league_id, pid):
    """A GTT player's page: identity, season record, GTT honors, full career
    honors (college + pro via the shared honors table), and a match log."""
    s = load_league(league_id)
    if not s:
        return None
    conn = _db()
    row = conn.execute("SELECT * FROM gtt_players WHERE league_id=? AND pid=?",
                       (league_id, pid)).fetchone()
    if not row:
        conn.close()
        return None
    row = dict(row)
    p = _prospect(row["data"])
    year = s["current_year"]
    rec = _records_for_year(conn, league_id, year)
    w, l = rec.get(pid, [0, 0])
    names = _franchise_names(league_id)
    rows = conn.execute("SELECT week, round, year, home, away, lines_json FROM gtt_duals"
                        " WHERE league_id=? AND year=? AND status='final' AND lines_json LIKE ?"
                        " ORDER BY week", (league_id, year, f"%{pid}%")).fetchall()
    conn.close()
    log = []
    for r in rows:
        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed"):
                continue
            if pid in ln.get("home_pids", []):
                opp_fid, won = r["away"], ln["home_won"]
            elif pid in ln.get("away_pids", []):
                opp_fid, won = r["home"], not ln["home_won"]
            else:
                continue
            log.append({"week": r["week"], "round": r["round"], "slot": ln["slot"],
                        "opp": names.get(opp_fid, str(opp_fid)), "scoreline": ln.get("scoreline"),
                        "won": won})

    import app.honors as honors
    career = honors.career_by_year(pid, "player")
    return {"pid": pid, "name": p.name, "country": p.country, "gender": row["gender"],
            "age": row["age"], "origin": row["origin"], "status": row["status"],
            "fid": row["fid"], "franchise": names.get(row["fid"], "Free agent"),
            "str": round(p.str_value(), 1), "overall": round(p.current_overall()),
            "w": w, "l": l, "honors": player_honors(league_id, pid),
            "career_honors": career, "log": log}
