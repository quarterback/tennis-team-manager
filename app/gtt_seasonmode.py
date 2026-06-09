"""
GTT season mode — a persistent, week-by-week pro-league season.

Forked from ``app.seasonmode`` (the NCAA college season) and stripped of the
college-only machinery: no divisions, no conferences, no conference tournaments,
no Power-Index NCAA bracket. A GTT league is a **flat set of co-ed franchises**
that play a double round-robin of GTT duals, then a single-elimination playoff.

Phases: ``regular`` → ``playoffs`` → ``complete``.

Two things differ deliberately from the college fork:

  * **Franchises are a stored, editable registry.** College programs are
    regenerated from the seed and never persisted; GTT franchises carry a
    name + home city the user can rename/relocate at will (purely cosmetic — see
    below). They live in their own table.
  * **Everything is keyed off the franchise *id*, not its name.** Match seeds and
    roster generation use the immutable franchise id, so renaming or relocating a
    team never changes a single result — identity is cosmetic, the id is real.

Rosters are generated deterministically from ``(league seed, franchise id)`` for
now; the graduate-fed talent pool + draft (design doc P5/P6) will replace that.
Standings are derived from the completed duals, never stored authoritatively, so
they grow as the season is advanced. Scoring is team W/L — GTT is scored like any
other team sport, not with WTT cumulative-game scoring.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3

from . import dbpath
from .dbpath import resolve_db_path

from engine import random_player, simulate_gtt_dual, GTTTeam
from generators import make_name_picker, random_town

DB_PATH = resolve_db_path()

# League shape — small, snappy seasons. A double round-robin of N franchises runs
# 2*(N-1) weeks; 8 teams ⇒ 14 weeks, in line with the college cadence.
DEFAULT_TEAMS = 8
ROUND_ROBINS = 2            # double round-robin (home/away swapped on the return)
PLAYOFF_FIELD = 4           # top-N franchises make the single-elimination playoff
ROSTER_SINGLES = 3          # 3 men + 3 women fielded per dual (MS/WS/XD x3)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gtt_leagues (
  id INTEGER PRIMARY KEY, name TEXT, seed INTEGER,
  current_week INTEGER, total_weeks INTEGER, phase TEXT, champion INTEGER
);
CREATE TABLE IF NOT EXISTS gtt_franchises (
  id INTEGER PRIMARY KEY, league_id INTEGER, name TEXT, city TEXT, abbrev TEXT
);
CREATE TABLE IF NOT EXISTS gtt_duals (
  id INTEGER PRIMARY KEY, league_id INTEGER, week INTEGER, round TEXT,
  home INTEGER, away INTEGER, status TEXT,
  home_points INTEGER, away_points INTEGER, winner INTEGER, lines_json TEXT,
  round_no INTEGER DEFAULT 0, bpos INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_gtt_duals ON gtt_duals(league_id, round, week);
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


def _dual_seed(seed: int, home_fid: int, away_fid: int, tag: str) -> int:
    raw = f"{seed}|{home_fid}|{away_fid}|{tag}".encode()
    return int.from_bytes(hashlib.blake2s(raw, digest_size=4).digest(), "big")


# --------------------------------------------------------------------------
# Default franchise identities (cosmetic — the user edits these freely)
# --------------------------------------------------------------------------

_MASCOTS: list[str] | None = None


def _mascots() -> list[str]:
    """Flat pool of mascots from the shared team-naming data, for default
    ``<City> <Mascot>`` franchise names. Cosmetic only."""
    global _MASCOTS
    if _MASCOTS is None:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "generators", "data", "names", "team_naming.json")
        pool: list[str] = []
        try:
            with open(path) as f:
                data = json.load(f)
            mp = data.get("category_3_traditional_mascots", {}).get("mascot_pool", {})
            for group in mp.values():
                if isinstance(group, list):
                    pool.extend(group)
        except (OSError, ValueError):
            pass
        _MASCOTS = pool or ["Aces", "Smash", "Strings", "Breakers", "Lobsters"]
    return _MASCOTS


def _abbrev(city: str, mascot: str) -> str:
    base = "".join(ch for ch in city.upper() if ch.isalpha())
    return (base[:3] or mascot.upper()[:3]).ljust(3, "X")[:3]


def _default_franchise(rng: random.Random) -> tuple[str, str, str]:
    """A plausible default (name, city, abbrev) — `<City> <Mascot>`."""
    city, state = random_town(rng)
    mascot = rng.choice(_mascots())
    loc = f"{city}, {state}" if state else city
    return f"{city} {mascot}", loc, _abbrev(city, mascot)


# --------------------------------------------------------------------------
# Rosters — deterministic from (league seed, franchise id) for now
# --------------------------------------------------------------------------

_roster_cache: dict = {}


def _franchise_base(seed: int, fid: int) -> float:
    """A franchise's talent band in [0.50, 0.66], deterministic from id — so the
    league has genuine haves and have-nots and standings mean something."""
    h = hashlib.blake2s(f"{seed}|{fid}|base".encode(), digest_size=2).digest()
    return 0.50 + 0.16 * (int.from_bytes(h, "big") / 65535.0)


def _gen_player(rng: random.Random, name_fn, base: float):
    name, country = name_fn()
    return random_player(rng, name, country, base=base)


def build_gtt_team(seed: int, fid: int, name: str) -> GTTTeam:
    """The fielded GTTTeam for a franchise: 3 men + 3 women, strength-ordered.
    Cached by (seed, fid) so every dual in a season reuses identical players."""
    key = (seed, fid)
    cached = _roster_cache.get(key)
    if cached is not None:
        return GTTTeam(name=name, men=cached[0], women=cached[1])
    base = _franchise_base(seed, fid)
    men_fn = make_name_picker(random.Random(seed ^ (fid << 8) ^ 0x4D), gender="male")
    women_fn = make_name_picker(random.Random(seed ^ (fid << 8) ^ 0x57), gender="female")
    rng = random.Random(f"{seed}|{fid}|roster")
    men = [_gen_player(rng, men_fn, base) for _ in range(ROSTER_SINGLES)]
    women = [_gen_player(rng, women_fn, base) for _ in range(ROSTER_SINGLES)]
    men.sort(key=lambda p: p.overall, reverse=True)
    women.sort(key=lambda p: p.overall, reverse=True)
    _roster_cache[key] = (men, women)
    return GTTTeam(name=name, men=men, women=women)


# --------------------------------------------------------------------------
# Schedule generation — flat (double) round-robin via the circle method
# --------------------------------------------------------------------------

def _round_robin(fids: list[int]) -> list[list[tuple[int, int]]]:
    """One single round-robin as a list of rounds; each round is a list of
    (home, away) franchise-id pairs. Standard circle method; an odd field gets a
    bye (the None slot is dropped)."""
    teams = list(fids)
    if len(teams) % 2:
        teams.append(None)              # bye marker
    n = len(teams)
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = teams[i], teams[n - 1 - i]
            if a is None or b is None:
                continue
            # alternate home/away by round so hosting is balanced
            pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        rounds.append(pairs)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]   # rotate, fixing teams[0]
    return rounds


def _build_schedule(fids: list[int], seed: int) -> list[tuple[int, int, int]]:
    """(week, home_fid, away_fid) rows for a double round-robin. The franchise
    order is shuffled by the seed so the fixture pattern varies league to league.
    The second round-robin swaps home/away (the 'return leg')."""
    order = list(fids)
    random.Random(f"{seed}|order").shuffle(order)
    rows: list[tuple[int, int, int]] = []
    week = 0
    for rr in range(ROUND_ROBINS):
        for rnd in _round_robin(order):
            week += 1
            for (h, a) in rnd:
                if rr % 2 == 1:
                    h, a = a, h                      # return leg: flip hosting
                rows.append((week, h, a))
    return rows


# --------------------------------------------------------------------------
# League creation
# --------------------------------------------------------------------------

def create_league(name: str = "Global Team Tennis", *, seed: int = 2026,
                  n_teams: int = DEFAULT_TEAMS) -> int:
    conn = _db()
    cur = conn.execute(
        "INSERT INTO gtt_leagues (name, seed, current_week, total_weeks, phase, champion)"
        " VALUES (?,?,?,?,?,?)", (name, seed, 1, 0, "regular", None))
    lid = cur.lastrowid

    rng = random.Random(f"{seed}|franchises")
    fids = []
    seen = set()
    for _ in range(n_teams):
        fname, city, abbrev = _default_franchise(rng)
        while fname in seen:                            # avoid accidental dupes
            fname, city, abbrev = _default_franchise(rng)
        seen.add(fname)
        c = conn.execute(
            "INSERT INTO gtt_franchises (league_id, name, city, abbrev) VALUES (?,?,?,?)",
            (lid, fname, city, abbrev))
        fids.append(c.lastrowid)

    rows = _build_schedule(fids, seed)
    total_weeks = max((w for (w, _, _) in rows), default=0)
    conn.executemany(
        "INSERT INTO gtt_duals (league_id, week, round, home, away, status,"
        " home_points, away_points, winner, lines_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(lid, w, "REG", h, a, "scheduled", None, None, None, None) for (w, h, a) in rows])
    conn.execute("UPDATE gtt_leagues SET total_weeks=? WHERE id=?", (total_weeks, lid))
    conn.commit()
    conn.close()
    return lid


def load_league(league_id: int) -> dict | None:
    conn = _db()
    row = conn.execute("SELECT * FROM gtt_leagues WHERE id=?", (league_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_leagues() -> list[dict]:
    conn = _db()
    rows = conn.execute("SELECT * FROM gtt_leagues ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def franchises(league_id: int) -> list[dict]:
    conn = _db()
    rows = conn.execute("SELECT * FROM gtt_franchises WHERE league_id=? ORDER BY id",
                        (league_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _franchise_names(league_id: int) -> dict[int, str]:
    return {f["id"]: f["name"] for f in franchises(league_id)}


# --------------------------------------------------------------------------
# Editor — rename / relocate (cosmetic; never affects results)
# --------------------------------------------------------------------------

def rename_franchise(franchise_id: int, name: str) -> None:
    """Rename a franchise. The name is independent of the city — a team needn't
    carry its city in its name. Results are keyed off the id, so this is purely
    cosmetic."""
    conn = _db()
    conn.execute("UPDATE gtt_franchises SET name=? WHERE id=?", (name.strip(), franchise_id))
    conn.commit()
    conn.close()


def relocate_franchise(franchise_id: int, city: str, abbrev: str | None = None) -> None:
    """Set a franchise's home city (and optionally its abbreviation). Cosmetic —
    the roster and every result are tied to the id, not the city."""
    conn = _db()
    if abbrev is not None:
        conn.execute("UPDATE gtt_franchises SET city=?, abbrev=? WHERE id=?",
                     (city.strip(), abbrev.strip().upper()[:3], franchise_id))
    else:
        conn.execute("UPDATE gtt_franchises SET city=? WHERE id=?", (city.strip(), franchise_id))
    conn.commit()
    conn.close()


def edit_franchise(franchise_id: int, *, name: str | None = None,
                   city: str | None = None, abbrev: str | None = None) -> None:
    """Combined editor write — set any of name / city / abbrev in one call."""
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


# --------------------------------------------------------------------------
# Advancing the season
# --------------------------------------------------------------------------

def _play_and_store(conn, s, dual_id, home_fid, away_fid, tag, fidelity):
    names = {f["id"]: f["name"] for f in
             [dict(r) for r in conn.execute(
                 "SELECT id, name FROM gtt_franchises WHERE id IN (?,?)",
                 (home_fid, away_fid)).fetchall()]}
    home = build_gtt_team(s["seed"], home_fid, names.get(home_fid, str(home_fid)))
    away = build_gtt_team(s["seed"], away_fid, names.get(away_fid, str(away_fid)))
    res = simulate_gtt_dual(home, away, seed=_dual_seed(s["seed"], home_fid, away_fid, tag),
                            fidelity=fidelity)
    winner = res.winner
    lines = [{"slot": ln.slot, "home_won": ln.home_won, "completed": ln.completed,
              "scoreline": (ln.result.scoreline if ln.completed and ln.result else None)}
             for ln in res.lines]
    conn.execute("UPDATE gtt_duals SET status='final', home_points=?, away_points=?,"
                 " winner=?, lines_json=? WHERE id=?",
                 (res.home_points, res.away_points, winner, json.dumps(lines), dual_id))
    return res


def advance(league_id: int, *, fidelity: str = "full") -> dict:
    """Play the next due slate. In ``regular`` that's the current week; in
    ``playoffs`` it's the current bracket round. Returns a small summary dict."""
    s = load_league(league_id)
    if not s or s["phase"] == "complete":
        return {"phase": "complete"}
    conn = _db()

    if s["phase"] == "regular":
        wk = s["current_week"]
        due = conn.execute("SELECT * FROM gtt_duals WHERE league_id=? AND round='REG' AND week=?"
                           " AND status='scheduled'", (league_id, wk)).fetchall()
        for d in due:
            _play_and_store(conn, s, d["id"], d["home"], d["away"], f"reg{wk}", fidelity)
        nxt = wk + 1
        phase = "regular" if nxt <= s["total_weeks"] else "playoffs"
        conn.execute("UPDATE gtt_leagues SET current_week=?, phase=? WHERE id=?",
                     (nxt, phase, league_id))
        conn.commit(); conn.close()
        return {"phase": "regular", "week": wk, "played": len(due), "next_phase": phase}

    if s["phase"] == "playoffs":
        out = _advance_playoff_round(conn, s, fidelity)
        conn.commit(); conn.close()
        return out

    conn.close()
    return {"phase": s["phase"]}


def advance_all(league_id: int, *, fidelity: str = "full") -> dict:
    """Advance until the league is complete; returns the final summary."""
    out = {}
    for _ in range(10_000):                          # generous guard against loops
        out = advance(league_id, fidelity=fidelity)
        if out.get("phase") == "complete" or out.get("champion") is not None:
            break
        s = load_league(league_id)
        if s and s["phase"] == "complete":
            break
    return out


# --------------------------------------------------------------------------
# Playoffs — single elimination, top-N by standings
# --------------------------------------------------------------------------

def _pow2_le(n: int) -> int:
    p = 1
    while p * 2 <= n:
        p *= 2
    return p


def _seed_positions(n: int) -> list[int]:
    """Standard bracket order for power-of-two n (1 vs n, 2 vs n-1, ...)."""
    pos = [1, 2]
    while len(pos) < n:
        m = len(pos) * 2
        pos = [x for p in pos for x in (p, m + 1 - p)]
    return pos


def _next_post_week(conn, lid):
    return (conn.execute("SELECT MAX(week) w FROM gtt_duals WHERE league_id=?",
                         (lid,)).fetchone()["w"] or 0) + 1


def _insert_playoff(conn, lid, week, round_no, bpos, home_fid, away_fid):
    conn.execute("INSERT INTO gtt_duals (league_id, week, round, home, away, status,"
                 " round_no, bpos) VALUES (?,?,?,?,?,?,?,?)",
                 (lid, week, "PO", home_fid, away_fid, "scheduled", round_no, bpos))


def _advance_playoff_round(conn, s, fidelity) -> dict:
    lid = s["id"]
    existing = conn.execute("SELECT COUNT(*) c FROM gtt_duals WHERE league_id=? AND round='PO'",
                            (lid,)).fetchone()["c"]
    if existing == 0:
        order = [row["fid"] for row in _standings_rows(conn, lid)]
        field = _pow2_le(min(PLAYOFF_FIELD, len(order)))
        if field < 2:
            conn.execute("UPDATE gtt_leagues SET phase='complete', champion=? WHERE id=?",
                         (order[0] if order else None, lid))
            return {"phase": "playoffs", "champion": order[0] if order else None}
        seeded = order[:field]
        slots = [seeded[i - 1] for i in _seed_positions(field)]
        week = _next_post_week(conn, lid)
        for k in range(field // 2):
            # higher seed (earlier in `seeded`) hosts
            a, b = slots[2 * k], slots[2 * k + 1]
            hi = a if seeded.index(a) < seeded.index(b) else b
            lo = b if hi == a else a
            _insert_playoff(conn, lid, week, 1, k, hi, lo)
        round_no = 1
    else:
        round_no = conn.execute("SELECT MIN(round_no) r FROM gtt_duals WHERE league_id=?"
                                " AND round='PO' AND status='scheduled'", (lid,)).fetchone()["r"]
    if round_no is None:
        return {"phase": "playoffs", "done": True}

    due = conn.execute("SELECT * FROM gtt_duals WHERE league_id=? AND round='PO' AND round_no=?"
                       " AND status='scheduled' ORDER BY bpos", (lid, round_no)).fetchall()
    for d in due:
        _play_and_store(conn, s, d["id"], d["home"], d["away"], f"po{round_no}b{d['bpos']}", fidelity)

    wins = conn.execute("SELECT home, away, winner FROM gtt_duals WHERE league_id=? AND round='PO'"
                        " AND round_no=? ORDER BY bpos", (lid, round_no)).fetchall()
    winners = [w["home"] if w["winner"] == 0 else w["away"] for w in wins]
    if len(winners) > 1:
        week = _next_post_week(conn, lid)
        for k in range(len(winners) // 2):
            _insert_playoff(conn, lid, week, round_no + 1, k, winners[2 * k], winners[2 * k + 1])
        return {"phase": "playoffs", "round": round_no, "played": len(due)}

    champ = winners[0]
    conn.execute("UPDATE gtt_leagues SET phase='complete', champion=? WHERE id=?", (champ, lid))
    return {"phase": "playoffs", "round": round_no, "played": len(due), "champion": champ}


# --------------------------------------------------------------------------
# Standings & views
# --------------------------------------------------------------------------

def _completed(conn, league_id, rounds=("REG",)) -> list[dict]:
    qs = ",".join("?" for _ in rounds)
    rows = conn.execute(
        f"SELECT home, away, round, home_points, away_points, winner FROM gtt_duals"
        f" WHERE league_id=? AND status='final' AND round IN ({qs})",
        (league_id, *rounds)).fetchall()
    return [dict(r) for r in rows]


def _standings_rows(conn, league_id) -> list[dict]:
    """Flat regular-season table: wins, then line differential, then name."""
    fr = {f["id"]: f for f in [dict(r) for r in conn.execute(
        "SELECT * FROM gtt_franchises WHERE league_id=? ORDER BY id", (league_id,)).fetchall()]}
    rec = {fid: {"w": 0, "l": 0, "lf": 0, "la": 0} for fid in fr}
    for d in _completed(conn, league_id, ("REG",)):
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
                    "w": r["w"], "l": r["l"], "lf": r["lf"], "la": r["la"],
                    "diff": r["lf"] - r["la"]})
    out.sort(key=lambda x: (x["w"], x["diff"], -x["fid"]), reverse=True)
    return out


def standings(league_id: int) -> list[dict]:
    conn = _db()
    rows = _standings_rows(conn, league_id)
    conn.close()
    return rows


def week_duals(league_id: int, week: int) -> list[dict]:
    conn = _db()
    names = _franchise_names(league_id)
    rows = conn.execute("SELECT * FROM gtt_duals WHERE league_id=? AND week=? ORDER BY round, bpos, id",
                        (league_id, week)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["home_name"] = names.get(d["home"], str(d["home"]))
        d["away_name"] = names.get(d["away"], str(d["away"]))
        d["lines"] = json.loads(d["lines_json"] or "[]")
        out.append(d)
    return out


def champion(league_id: int) -> dict | None:
    """The champion franchise once the league is complete, else None."""
    s = load_league(league_id)
    if not s or s["phase"] != "complete" or s["champion"] is None:
        return None
    return {f["id"]: f for f in franchises(league_id)}.get(s["champion"])
