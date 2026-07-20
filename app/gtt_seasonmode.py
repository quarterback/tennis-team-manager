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
LINEUP_MEN = 3              # the lineup core that actually plays (3 MS + 3 WS)
LINEUP_WOMEN = 3
RESERVE_MEN = 2             # bench depth beyond the lineup — carries the add/drop
RESERVE_WOMEN = 2           # churn so franchise starters are never the cut bait
TARGET_MEN = LINEUP_MEN + RESERVE_MEN      # roster target per gender (5)
TARGET_WOMEN = LINEUP_WOMEN + RESERVE_WOMEN
WAIVER_POOL_MEN = 6         # surplus free agents kept on the wire for in-season
WAIVER_POOL_WOMEN = 6       # add/drop (a fantasy-style waiver pool per gender)
WAIVER_MARGIN = 0.40        # a free agent must clear a club's WEAKEST roster player
                            # by this STR margin to be signed — a clear upgrade only,
                            # so churn stays low and the lineup core is never at risk
LINES_TO_CLINCH = 5
ENTRY_AGE = 22              # a graduate's age on turning pro
PEAK_AGE = 28              # decline (development in reverse) kicks in past here
RETIRE_AGE = 34            # hard retirement age
RETIRE_FROM = 30           # probabilistic retirement begins here
# GTT runs on the SAME clock as the college world (owner rule 2027-07): season
# index i is played CONCURRENT with college calendar 2026+i, and the class that
# graduates college year y joins the GTT for index y+1. The off-season gate in
# `advance` + the `on_world_rollover` hook keep the two in lockstep — the pro
# league can never sim ahead of the college game or stamp future-dated honors.
BASE_YEAR = 2026
GRAD_D1_SHARE = 0.95       # target share of each off-season intake from D1
NON_D1_MIN_STR = 58.0      # small-school pro competitiveness bar
NON_D1_MIN_OVR = 58.0

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
CREATE TABLE IF NOT EXISTS gtt_hof (
  id INTEGER PRIMARY KEY, league_id INTEGER, pid TEXT, name TEXT, gender TEXT,
  year_enshrined INTEGER, data TEXT, honors_json TEXT, record TEXT, peak_str REAL
);
CREATE TABLE IF NOT EXISTS gtt_duals (
  id INTEGER PRIMARY KEY, league_id INTEGER, year INTEGER, week INTEGER, round TEXT,
  home INTEGER, away INTEGER, status TEXT,
  home_points INTEGER, away_points INTEGER, winner INTEGER, lines_json TEXT,
  round_no INTEGER DEFAULT 0, bpos INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS gtt_transactions (
  id INTEGER PRIMARY KEY, league_id INTEGER, year INTEGER, week INTEGER,
  fid INTEGER, gender TEXT, add_pid TEXT, drop_pid TEXT, add_str REAL, drop_str REAL
);
CREATE INDEX IF NOT EXISTS idx_gtt_duals ON gtt_duals(league_id, year, round, week);
CREATE INDEX IF NOT EXISTS idx_gtt_pl ON gtt_players(league_id, fid, status);
CREATE INDEX IF NOT EXISTS idx_gtt_fr ON gtt_franchises(league_id);
CREATE INDEX IF NOT EXISTS idx_gtt_tx ON gtt_transactions(league_id, year, week);
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


def _active_unis_via(conn) -> set:
    """Active division×gender universes, read THROUGH the caller's connection
    (worldconfig's own accessors open a fresh connection, which deadlocks against
    an in-transaction off-season on the shared SQLite file). Defaults to all."""
    def lst(key, allv):
        try:
            r = conn.execute("SELECT value FROM world_setting WHERE key=?", (key,)).fetchone()
            v = list(json.loads(r["value"])) if r and r["value"] else []
        except (sqlite3.OperationalError, ValueError, TypeError):
            v = []
        return [x for x in allv if x in v] or allv
    return {(d, g) for d in lst("active_divisions", ["D1", "D2", "D3", "D4"])
            for g in lst("active_genders", ["men", "women"])}


def _world_graduates(conn, world_seed, exclude_pids, limit):
    """Latest persisted college graduates for the pro intake, 95% D1 / 5% non-D1.

    Reads ``world_graduates`` (and active config) through the caller's transaction
    because world and GTT tables share one SQLite file — opening a second
    connection mid-off-season deadlocks. Returns (gender, pid, data, str) rows.
    """
    try:
        wid = conn.execute("SELECT id FROM world WHERE seed=?", (world_seed,)).fetchone()
    except sqlite3.OperationalError:
        return []
    if not wid or limit <= 0:
        return []
    wid = wid["id"]
    try:
        active = _active_unis_via(conn)
        year = conn.execute("SELECT MAX(year) y FROM world_graduates WHERE world_id=?",
                            (wid,)).fetchone()["y"]
    except sqlite3.OperationalError:
        return []
    if year is None:
        return []
    rows = conn.execute("SELECT division, gender, pid, str, ovr, data FROM world_graduates "
                        "WHERE world_id=? AND year=?", (wid, year)).fetchall()
    d1, non = [], []
    for r in rows:
        division, gender = r["division"], r["gender"]
        if r["pid"] in exclude_pids or (division, gender) not in active:
            continue
        g = "m" if gender in ("men", "male", "m") else "w"
        item = (g, r["pid"], r["data"], float(r["str"] or 0.0), float(r["ovr"] or 0.0), division)
        if division == "D1":
            d1.append(item)
        elif item[3] >= NON_D1_MIN_STR and item[4] >= NON_D1_MIN_OVR:
            non.append(item)
    d1.sort(key=lambda x: (x[3], x[4], x[1]), reverse=True)
    non.sort(key=lambda x: (x[3], x[4], x[1]), reverse=True)
    non_target = max(1, round(limit * (1.0 - GRAD_D1_SHARE))) if limit >= 10 else 0
    picked = non[:non_target] + d1[:max(0, limit - min(non_target, len(non)))]
    if len(picked) < limit:
        picked.extend(non[non_target:limit - len(picked) + non_target])
    picked.sort(key=lambda x: (x[3], x[4], x[1]), reverse=True)
    return [(g, pid, data, st) for g, pid, data, st, _ovr, _div in picked[:limit]]


def _intake(conn, league, needed_by_gender):
    """Fill the free-agent pool for the off-season: real college graduates first,
    topped up with generated rookies so the league is always playable. Beyond the
    open roster spots we draw a surplus per gender (WAIVER_POOL_*) so a standing
    free-agent wire survives the draft for in-season add/drop."""
    lid, seed, year = league["id"], league["world_seed"], league["current_year"]
    have = {r["pid"] for r in conn.execute("SELECT pid FROM gtt_players WHERE league_id=?",
                                           (lid,)).fetchall()}
    pool_target = {"m": needed_by_gender["m"] + WAIVER_POOL_MEN,
                   "w": needed_by_gender["w"] + WAIVER_POOL_WOMEN}
    target = pool_target["m"] + pool_target["w"]
    # Ex-pros (Gr grad transfers leaving college) enter tagged origin='pro' —
    # they are draftable ONLY in the draft's single Pro Round (one pick per
    # franchise), so cap the pro intake at the franchise count and never let
    # them consume the normal graduates' pool slots. Their elite STR tops the
    # selector's ranking, so request headroom for both groups.
    from .pros import is_pro as _is_pro
    n_fr = len(_fr_rows(conn, lid))
    grads = _world_graduates(conn, seed, have, target + 2 * n_fr)
    pool_rows, pro_rows, used = {"m": [], "w": []}, {"m": [], "w": []}, set(have)
    for g, pid, data, _str in grads:
        if pid in used:
            continue
        if _is_pro(_prospect(data)):
            if len(pro_rows[g]) < n_fr:
                pro_rows[g].append({"pid": pid, "gender": g, "data": data,
                                    "age": ENTRY_AGE, "joined_year": year,
                                    "origin": "pro"})
                used.add(pid)
            continue
        if len(pool_rows[g]) >= pool_target[g]:
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
        for r in pool_rows[g] + pro_rows[g]:
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
    """Top men + top women by STR → a GTTTeam, plus the ordered pid lists. The
    lineup is the top LINEUP_* of each gender; deeper roster players are reserves
    who only crack the lineup if they out-rate a starter (the engine of the
    add/drop wire — a hot reserve plays, a cold one is cut bait)."""
    def top(gender, n):
        ps = _active(conn, lid, fid, gender)
        ps.sort(key=lambda r: _prospect(r["data"]).str_value(), reverse=True)
        return ps[:n]
    men, women = top("m", LINEUP_MEN), top("w", LINEUP_WOMEN)
    team = GTTTeam(name=name,
                   men=[_prospect(r["data"]).engine_player() for r in men],
                   women=[_prospect(r["data"]).engine_player() for r in women])
    return team, [r["pid"] for r in men], [r["pid"] for r in women]


# Per-play-date FORM — the pro game's chaos engine. Each play date every player's
# whole level is multiplied by a fresh form factor in [-17%, +20%]: a coherent
# day-to-day swing (a star can show up flat, a journeyman can catch fire), unlike
# per-attribute noise which just cancels out. Fires in GTT only — college/juniors
# never call this. Tuned so upsets are common night to night yet class still sorts
# the standings over a season.
CHAOS_FORM_LO = 0.83    # -17% off day
CHAOS_FORM_HI = 1.20    # +20% on day


# Per-play-date FORM, player-based: every player's whole level is multiplied by a
# fresh, wide, slightly upside-skewed form factor each play date. A star can show
# up flat; a journeyman can catch fire. It's drawn per player (not per team), so
# individual lines swing hard night to night; over a 9-line dual the noise partly
# averages out, so class still tells in the standings (favourites ~70% of duals).
CHAOS_FORM_LO, CHAOS_FORM_HI = 0.70, 1.45        # -30% .. +45%


def _scale_player(player, f):
    from engine import Player, ATTRS
    fields = {k: getattr(player, k) for k in player.__dataclass_fields__}
    for a in ATTRS:
        fields[a] = min(1.0, max(0.0, fields[a] * f))
    return Player(**fields)


def _apply_form(team, rng):
    """Stamp a per-play-date, per-player form on the lineup in place. Lineup order
    and the mixed-pair index map are preserved."""
    def formed(p):
        return _scale_player(p, rng.uniform(CHAOS_FORM_LO, CHAOS_FORM_HI))

    team.men = [formed(p) for p in team.men]
    team.women = [formed(p) for p in team.women]


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


def _active_world_seed(conn, preferred=None):
    """The seed of THE ACTIVE WORLD in this save — the college game actually
    being played. There is only ever one real world per save (`world.start_new`
    resets before creating, always at the default seed; freshness comes from the
    salt), so this binds to the OLDEST world row. Any later row is a stray
    artifact (a derived-seed bug once wrote them — see
    scripts/cleanup_stray_worlds.py). `preferred` is honored only when a world
    with that exact seed exists; a typed number that matches nothing (e.g. a
    year typed into the old form's Seed box) never silently unbinds the league
    from the player's game."""
    try:
        if preferred is not None and conn.execute("SELECT 1 FROM world WHERE seed=?",
                                                  (preferred,)).fetchone():
            return preferred
        row = conn.execute("SELECT seed FROM world ORDER BY id ASC LIMIT 1").fetchone()
        if row:
            return row["seed"]
    except sqlite3.OperationalError:
        pass
    return preferred if preferred is not None else 2026


def create_league(name="Global Team Tennis", *, seed=None, n_teams=DEFAULT_TEAMS):
    """Create a league BORN INTO the active world: it starts at the world's
    CURRENT year (so its calendar runs concurrent with the college game from
    day one) and its founding rosters draft the save's latest graduating class
    first — real college players, real pids — with the Pro Round rule applied
    at founding too (at most one ex-pro per club; leftover pros never enter).
    Generated founders fill only the seats the class can't. A fresh save with
    no graduates yet gets the classic all-founder inaugural league."""
    conn = _db()
    seed = _active_world_seed(conn, seed)
    start_year = _world_year(conn, seed) or 0
    cur = conn.execute(
        "INSERT INTO gtt_leagues (name, world_seed, current_year, current_week,"
        " total_weeks, phase, champion) VALUES (?,?,?,?,?,?,?)",
        (name, seed, start_year, 1, 0, "regular", None))
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

    def _seat(fid, gender, pid, data, origin, age=ENTRY_AGE):
        conn.execute(
            "INSERT INTO gtt_players (league_id, pid, gender, fid, status, age,"
            " seasons, joined_year, origin, data) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (lid, pid, gender, fid, "active", age, 0, start_year, origin, data))

    # --- Founding draft from the latest graduating class (STR order, snake) ---
    from .pros import is_pro as _is_pro
    pool, pro_pool = {"m": [], "w": []}, {"m": [], "w": []}
    for g, pid, data, st in _world_graduates(conn, seed, set(), 10_000):
        (pro_pool if _is_pro(_prospect(data)) else pool)[g].append((pid, data, st))
    for g in ("m", "w"):
        pool[g].sort(key=lambda x: -x[2])
        pro_pool[g].sort(key=lambda x: -x[2])
    counts = {fid: {"m": 0, "w": 0} for fid in fids}
    pro_taken: set = set()
    rnd = 0
    while True:
        placed = False
        seq = fids if rnd % 2 == 0 else fids[::-1]
        for fid in seq:
            for g, tgt in (("m", TARGET_MEN), ("w", TARGET_WOMEN)):
                if counts[fid][g] >= tgt:
                    continue
                if (fid not in pro_taken and pro_pool[g]
                        and (not pool[g] or pro_pool[g][0][2] >= pool[g][0][2])):
                    pid, data, _st = pro_pool[g].pop(0)
                    _seat(fid, g, pid, data, "pro")
                    pro_taken.add(fid)
                elif pool[g]:
                    pid, data, _st = pool[g].pop(0)
                    _seat(fid, g, pid, data, "college")
                else:
                    continue
                counts[fid][g] += 1
                placed = True
        rnd += 1
        if not placed:
            break
    # Leftover pros never enter (the Pro Round is the only door, founding included).

    # Seats the class couldn't fill: generated founders, banded per club.
    for fid in fids:
        base = 48 + 16 * (_h(seed, fid, "base") / 0xFFFFFFFF)
        prng = random.Random(_h(seed, fid, "founders"))
        men_fn = make_name_picker(random.Random(_h(seed, fid, "m")), gender="male")
        women_fn = make_name_picker(random.Random(_h(seed, fid, "w")), gender="female")
        for gender, name_fn, tgt in (("m", men_fn, TARGET_MEN), ("w", women_fn, TARGET_WOMEN)):
            while counts[fid][gender] < tgt:
                r = _gen_player(prng, name_fn, gender, prng.gauss(base, 5), start_year)
                _seat(fid, gender, r["pid"], r["data"], "founder", age=r["age"])
                counts[fid][gender] += 1

    # The free-agent wire: leftover real graduates first, generated fodder only
    # to top up — so in-season add/drop signs the save's players when there are
    # any left to sign.
    fa_rng = random.Random(_h(seed, "founding_fa"))
    fa_men = make_name_picker(random.Random(_h(seed, "fa_m")), gender="male")
    fa_women = make_name_picker(random.Random(_h(seed, "fa_w")), gender="female")
    for gender, name_fn, n in (("m", fa_men, WAIVER_POOL_MEN), ("w", fa_women, WAIVER_POOL_WOMEN)):
        wired = 0
        for pid, data, _st in pool[gender][:n]:
            _seat(None, gender, pid, data, "college")
            wired += 1
        while wired < n:
            r = _gen_player(fa_rng, name_fn, gender, fa_rng.uniform(48, 60), start_year,
                            origin="founder")
            _seat(None, gender, r["pid"], r["data"], "founder", age=r["age"])
            wired += 1

    _build_schedule(conn, lid, start_year, seed)
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


def draft_board(league_id, year=None):
    """The year's draft as a real board: the Pro Round, then numbered snake
    rounds of college/rookie picks. Off-season drafts read the week-0
    transaction log; the FOUNDING draft (which seats players directly) is
    reconstructed from seating order (gtt_players id order = pick order)."""
    s = load_league(league_id)
    if not s:
        return None
    year = year if year is not None else s["current_year"]
    conn = _db()
    names = _franchise_names(league_id)
    origin_of = {r["pid"]: r["origin"] for r in conn.execute(
        "SELECT pid, origin FROM gtt_players WHERE league_id=?", (league_id,)).fetchall()}
    picks = [dict(r) for r in conn.execute(
        "SELECT fid, gender, add_pid AS pid, add_str AS str FROM gtt_transactions"
        " WHERE league_id=? AND year=? AND week=0 AND add_pid IS NOT NULL ORDER BY id",
        (league_id, year)).fetchall()]
    is_founding = not picks
    if not picks:                        # founding draft: reconstruct from seating order
        live = league_player_str(league_id)
        for r in conn.execute(
                "SELECT pid, gender, fid, origin, data FROM gtt_players WHERE league_id=?"
                " AND joined_year=? AND fid IS NOT NULL AND origin IN ('college','pro')"
                " ORDER BY id", (league_id, year)).fetchall():
            p = _prospect(r["data"])
            picks.append({"fid": r["fid"], "gender": r["gender"], "pid": r["pid"],
                          "str": round(live.get(r["pid"], (p.str_value(), 0))[0], 1)})
    nm = {}
    for pk in picks:
        if pk["pid"] not in nm:
            r = conn.execute("SELECT data FROM gtt_players WHERE league_id=? AND pid=?",
                             (league_id, pk["pid"])).fetchone()
            nm[pk["pid"]] = _prospect(r["data"]).name if r else pk["pid"]
    conn.close()
    pro_round, rounds, taken = [], [], {}
    n = 0
    for pk in picks:
        row = {"franchise": names.get(pk["fid"], str(pk["fid"])), "fid": pk["fid"],
               "pid": pk["pid"], "name": nm[pk["pid"]], "gender": pk["gender"],
               "str": pk["str"], "origin": origin_of.get(pk["pid"], "")}
        if row["origin"] == "pro":
            row["no"] = len(pro_round) + 1
            pro_round.append(row)
            continue
        n += 1
        row["no"] = n
        rnd = taken[pk["fid"]] = taken.get(pk["fid"], 0) + 1
        while len(rounds) < rnd:
            rounds.append([])
        rounds[rnd - 1].append(row)
    return {"year": year, "cal_year": BASE_YEAR + year, "is_founding": is_founding,
            "pro_round": pro_round, "rounds": rounds, "total": len(pro_round) + n}


def delete_league(league_id):
    """Delete a league and everything it owns (franchises, players, duals,
    seasons, transactions, Hall of Fame). Irreversible; the world it drew
    graduates from is untouched."""
    conn = _db()
    for t in ("gtt_duals", "gtt_players", "gtt_franchises", "gtt_seasons",
              "gtt_transactions", "gtt_hof"):
        conn.execute(f"DELETE FROM {t} WHERE league_id=?", (league_id,))
    conn.execute("DELETE FROM gtt_leagues WHERE id=?", (league_id,))
    conn.commit()
    conn.close()


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


def move_player(league_id, pid, dest_fid):
    """God-mode roster edit — reassign a player to another franchise, or to free
    agency (``dest_fid=None``). The college-side editor's player move, for the
    pros: direct and unconstrained (you're editing), and keyed off the pid so the
    player keeps their identity, gender, record, STR, and honors — only the
    franchise changes. Returns True on success."""
    conn = _db()
    row = conn.execute("SELECT id FROM gtt_players WHERE league_id=? AND pid=?",
                       (league_id, pid)).fetchone()
    if not row:
        conn.close()
        return False
    if dest_fid is not None and not conn.execute(
            "SELECT 1 FROM gtt_franchises WHERE id=? AND league_id=?",
            (dest_fid, league_id)).fetchone():
        conn.close()
        return False
    # Assigning to a club reactivates a retired player; a NULL dest waives them.
    conn.execute("UPDATE gtt_players SET fid=?, status='active' WHERE id=?",
                 (dest_fid, row["id"]))
    conn.commit()
    conn.close()
    return True


def rename_franchise(franchise_id, name):
    edit_franchise(franchise_id, name=name)


def relocate_franchise(franchise_id, city, abbrev=None):
    edit_franchise(franchise_id, city=city, abbrev=abbrev)


# --------------------------------------------------------------------------
# Playing a dual
# --------------------------------------------------------------------------

def _stat_summary(stats_list):
    """Raw ATP-style stat counts for one side (a singles player, or both partners
    summed in doubles) — the box score formats these into `% (made/total)`."""
    agg = {"aces": 0, "df": 0, "fs_in": 0, "sp_won": 0, "sp_total": 0,
           "rp_won": 0, "rp_total": 0, "bp_saved": 0, "bp_faced": 0, "bp_conv": 0,
           "winners": 0, "ue": 0, "points": 0}
    for s in stats_list:
        agg["aces"] += s.aces; agg["df"] += s.double_faults
        agg["fs_in"] += s.first_serves_in
        agg["sp_won"] += s.serve_points_won; agg["sp_total"] += s.serve_points_total
        agg["rp_won"] += s.return_points_won; agg["rp_total"] += s.return_points_total
        agg["bp_saved"] += s.break_points_saved; agg["bp_faced"] += s.break_points_faced
        agg["bp_conv"] += s.break_points_converted
        agg["winners"] += s.winners; agg["ue"] += s.unforced_errors
        agg["points"] += s.points_won
    return agg


def _play_and_store(conn, league, dual_id, home_fid, away_fid, tag, fidelity):
    lid, seed = league["id"], league["world_seed"]
    names = _fr_names(conn, lid)
    home, hm, hw = _lineup(conn, lid, home_fid, names.get(home_fid, str(home_fid)))
    away, am, aw = _lineup(conn, lid, away_fid, names.get(away_fid, str(away_fid)))
    ds = _dual_seed(seed, home_fid, away_fid, tag)
    # The pro game is volatile: each player carries a fresh per-dual "form" that
    # swings their level well beyond college/junior noise, so a lesser team can
    # take down the best on the night — yet class still tells over a season.
    _apply_form(home, random.Random(ds ^ 0xF0F0))
    _apply_form(away, random.Random(ds ^ 0x0A0A))
    res = simulate_gtt_dual(home, away, seed=ds, fidelity=fidelity)
    lines = []
    for ln in res.lines:
        entry = {"slot": ln.slot, "home_won": ln.home_won, "completed": ln.completed,
                 "scoreline": (ln.result.scoreline if ln.completed and ln.result else None),
                 "home_pids": _line_pids(ln.slot, hm, hw) if ln.completed else [],
                 "away_pids": _line_pids(ln.slot, am, aw) if ln.completed else []}
        if ln.completed and ln.result is not None:
            st = ln.result.stats
            if ln.slot.startswith("XD"):
                entry["home_stats"] = _stat_summary([st[0], st[1]])
                entry["away_stats"] = _stat_summary([st[2], st[3]])
            else:
                entry["home_stats"] = _stat_summary([st[0]])
                entry["away_stats"] = _stat_summary([st[1]])
        lines.append(entry)
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
        # The add/drop wire runs after the week's duals are committed, so it reads
        # this week's fresh results (STR absorbs them). Skip after the final week —
        # there's no next lineup to shape going into the playoffs.
        moves = _process_waivers(league_id, year, wk) if phase == "regular" else []
        return {"phase": "regular", "year": year, "week": wk, "played": len(due),
                "next_phase": phase, "moves": len(moves)}

    if s["phase"] == "playoffs":
        out = _advance_playoff_round(conn, s, fidelity)
        conn.commit(); conn.close()
        _flush_honors(out)
        return out

    if s["phase"] == "complete":
        # Lockstep with the college world: the GTT off-season (draft + intake)
        # only runs once the college season for the SAME year has finalized —
        # that's when the graduating class exists to be drafted. Until then the
        # league holds ("waiting on college"), so the pro game can never sim
        # ahead of the universe it draws from. world._finalize_year calls
        # on_world_rollover() to run this automatically at finalize.
        ws = _active_world_seed(conn, s["world_seed"])
        wy = _world_year(conn, ws)
        if wy is not None and s["current_year"] + 1 > wy:
            conn.close()
            return {"phase": "complete", "year": s["current_year"],
                    "waiting_on_college": True}
        out = _offseason(conn, s, fidelity)
        conn.commit(); conn.close()
        return out

    conn.close()
    return {"phase": s["phase"]}


def _world_year(conn, world_seed):
    """The college world's current year index (None when no world exists —
    standalone leagues keep their own clock)."""
    try:
        r = conn.execute("SELECT year FROM world WHERE seed=?", (world_seed,)).fetchone()
        return int(r["year"]) if r else None
    except sqlite3.OperationalError:
        return None


def can_start_next(league_id) -> bool:
    """Whether this league's next off-season is unlocked (the college world has
    finalized past it). Standalone leagues (no world) are always unlocked."""
    s = load_league(league_id)
    if not s or s["phase"] != "complete":
        return False
    conn = _db()
    try:
        wy = _world_year(conn, _active_world_seed(conn, s["world_seed"]))
    finally:
        conn.close()
    return wy is None or s["current_year"] + 1 <= wy


def on_world_rollover() -> int:
    """Called by world._finalize_year AFTER the rollover commits: every league
    bound to the world whose season is complete rolls its off-season now — the
    intake reads the class that just graduated. Mid-season leagues are left
    alone (their off-season unlocks when they finish). Returns leagues rolled."""
    rolled = 0
    for lg in list_leagues():
        s = load_league(lg["id"])
        if not s or s["phase"] != "complete":
            continue
        if can_start_next(lg["id"]):
            advance(lg["id"], fidelity="fast")
            rolled += 1
    return rolled


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

    # Self-heal the world linkage: a league whose stored world_seed matches no
    # existing world (a number typed into the old Seed box, or a world that was
    # reset) re-binds to the save's ACTIVE world — the college league the player
    # is actually running — and the fix is persisted. Without this the graduate
    # lookup silently finds nothing and the league fills with synthetic players.
    ws = _active_world_seed(conn, s["world_seed"])
    if ws != s["world_seed"]:
        conn.execute("UPDATE gtt_leagues SET world_seed=? WHERE id=?", (ws, lid))
        s = dict(s)
        s["world_seed"] = ws

    # Age everyone a year; retire the veterans; decline those past their peak
    # (development run in reverse — the slide steepens with each year past peak).
    for r in conn.execute("SELECT id, pid, age, data FROM gtt_players WHERE league_id=?"
                          " AND status='active'", (lid,)).fetchall():
        age = (r["age"] or ENTRY_AGE) + 1
        if _should_retire(r["pid"], age, year):
            conn.execute("UPDATE gtt_players SET age=?, status='retired', fid=NULL WHERE id=?",
                         (age, r["id"]))
            continue
        data = r["data"]
        if age > PEAK_AGE:
            p = _prospect(data)
            p.decline(scale=age - PEAK_AGE)
            data = json.dumps(_prospect_dict(p))
        conn.execute("UPDATE gtt_players SET age=?, seasons=seasons+1, data=? WHERE id=?",
                     (age, data, r["id"]))

    # --- College takeover: synthetic founders don't hold seats once the college
    # pipeline is live (owner rule 2027-07). Each off-season, every FOUNDER still
    # on a roster is released — weakest first, capped at the number of real
    # graduates actually available to replace them — and the open seats are filled
    # by the intake + draft below. A league started on founders converges to
    # college-fed rosters, then operates naturally (no roster founders remain).
    # Released founders retire rather than joining the wire, so they can't creep
    # back via in-season add/drop. Every release is logged to gtt_transactions
    # (week 0 = off-season) so the turnover is visible on the hub wire.
    have_pids = {r["pid"] for r in conn.execute(
        "SELECT pid FROM gtt_players WHERE league_id=?", (lid,)).fetchall()}
    grads_avail = {"m": 0, "w": 0}
    for gg, _pid, _data, _str in _world_graduates(conn, s["world_seed"], have_pids, 10_000):
        grads_avail[gg] += 1
    if grads_avail["m"] or grads_avail["w"]:
        by_g = {"m": [], "w": []}
        for r in conn.execute("SELECT id, pid, gender, fid, data FROM gtt_players"
                              " WHERE league_id=? AND status='active' AND fid IS NOT NULL"
                              " AND origin='founder'", (lid,)).fetchall():
            by_g[r["gender"]].append((_prospect(r["data"]).str_value(), r))
        for gg in ("m", "w"):
            by_g[gg].sort(key=lambda x: x[0])            # weakest released first
            for st, r in by_g[gg][:grads_avail[gg]]:
                conn.execute("UPDATE gtt_players SET status='retired', fid=NULL"
                             " WHERE id=?", (r["id"],))
                conn.execute("INSERT INTO gtt_transactions (league_id, year, week, fid,"
                             " gender, add_pid, drop_pid, add_str, drop_str)"
                             " VALUES (?,?,?,?,?,?,?,?,?)",
                             (lid, year, 0, r["fid"], gg, None, r["pid"],
                              None, round(st, 1)))

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
    """Reverse-standings snake draft of the free-agent pool into open slots.
    Opens with the PRO ROUND (owner rule 2027-07): one single round, worst
    record first, where each franchise may take at most ONE ex-pro (the best
    available of either gender that fits an open slot). Pros are draftable ONLY
    here — every undrafted pro retires immediately, so they never sit in the
    general pool or the waiver wire. The normal snake draft then fills the rest
    from graduates and rookies."""
    order = [r["fid"] for r in _standings_rows(conn, lid, prev_year)]
    if not order:
        order = [f["id"] for f in _fr_rows(conn, lid)]
    order = order[::-1]                                   # worst record drafts first

    pool = {"m": [], "w": []}
    pro_pool = {"m": [], "w": []}
    for r in conn.execute("SELECT id, pid, gender, origin, data FROM gtt_players"
                          " WHERE league_id=? AND fid IS NULL AND status='active'",
                          (lid,)).fetchall():
        dest = pro_pool if r["origin"] == "pro" else pool
        dest[r["gender"]].append((r["id"], r["pid"], _prospect(r["data"]).str_value()))
    for g in ("m", "w"):
        pool[g].sort(key=lambda x: x[2], reverse=True)    # best available first
        pro_pool[g].sort(key=lambda x: x[2], reverse=True)

    counts = {fid: {"m": len(_active(conn, lid, fid, "m")),
                    "w": len(_active(conn, lid, fid, "w"))} for fid in order}

    # --- The Pro Round: one pick per franchise, then the pros are done ---
    targets = {"m": TARGET_MEN, "w": TARGET_WOMEN}
    for fid in order:
        best = max(((g, pro_pool[g][0]) for g in ("m", "w")
                    if pro_pool[g] and counts[fid][g] < targets[g]),
                   key=lambda t: t[1][2], default=None)
        if best is None:
            continue
        g, (pid_id, pid, st) = best
        pro_pool[g].pop(0)
        conn.execute("UPDATE gtt_players SET fid=? WHERE id=?", (fid, pid_id))
        conn.execute("INSERT INTO gtt_transactions (league_id, year, week, fid,"
                     " gender, add_pid, drop_pid, add_str, drop_str)"
                     " VALUES (?,?,?,?,?,?,?,?,?)",
                     (lid, year, 0, fid, g, pid, None, round(st, 1), None))
        counts[fid][g] += 1
    for g in ("m", "w"):                                  # undrafted pros retire
        for pid_id, _pid, _st in pro_pool[g]:
            conn.execute("UPDATE gtt_players SET status='retired' WHERE id=?", (pid_id,))
    for g, tgt in (("m", TARGET_MEN), ("w", TARGET_WOMEN)):
        rnd = 0
        while pool[g]:
            seq = order if rnd % 2 == 0 else order[::-1]
            picked = False
            for fid in seq:
                if counts[fid][g] >= tgt or not pool[g]:
                    continue
                pid_id, pid, st = pool[g].pop(0)
                conn.execute("UPDATE gtt_players SET fid=? WHERE id=?", (fid, pid_id))
                # Week-0 log row: the draft pick, so off-season intake is visible
                # on the hub wire (add-only — no one was dropped for a draftee).
                conn.execute("INSERT INTO gtt_transactions (league_id, year, week, fid,"
                             " gender, add_pid, drop_pid, add_str, drop_str)"
                             " VALUES (?,?,?,?,?,?,?,?,?)",
                             (lid, year, 0, fid, g, pid, None, round(st, 1), None))
                counts[fid][g] += 1
                picked = True
            rnd += 1
            if not picked:
                break


# --------------------------------------------------------------------------
# In-season add/drop wire — release a slumping fringe player, sign a free agent
#
# No trades, gender-locked (a man can only be replaced by a man, a woman by a
# woman — enforced by construction, since each move swaps within one gender
# group and never changes the per-gender count). Ability + performance, never
# random: the signal is the results-based STR (`league_player_str`), which folds
# a player's pro results into their rating, so a genuine slump shows up as a
# falling number. Each club, each gender, each week considers ONLY its weakest
# rostered player against the best available free agent and acts only on a clear
# upgrade (WAIVER_MARGIN) — so franchise starters (who are never the weakest) are
# never cut, and churn stays low.
# --------------------------------------------------------------------------

def _process_waivers(league_id, year, week):
    """Run the weekly add/drop across every franchise. Reads committed results
    (called after the week's duals commit), writes the roster moves, and logs each
    to `gtt_transactions`. Deterministic — purely a function of the data."""
    s = load_league(league_id)
    if not s:
        return []
    live = league_player_str(league_id)
    conn = _db()

    def strv(pid, data):
        v = live.get(pid)
        return v[0] if v else _prospect(data).str_value()

    fas = {"m": [], "w": []}
    for r in conn.execute("SELECT pid, gender, data FROM gtt_players WHERE league_id=?"
                          " AND fid IS NULL AND status='active'", (league_id,)).fetchall():
        fas[r["gender"]].append([strv(r["pid"], r["data"]), r["pid"]])
    for g in fas:
        fas[g].sort(key=lambda x: x[0], reverse=True)

    moves = []
    for fid in [f["id"] for f in _fr_rows(conn, league_id)]:
        for g, lineup_n in (("m", LINEUP_MEN), ("w", LINEUP_WOMEN)):
            if not fas[g]:
                continue
            roster = _active(conn, league_id, fid, g)
            if len(roster) <= lineup_n:
                continue                              # never cut into the lineup core
            roster.sort(key=lambda x: strv(x["pid"], x["data"]))
            weak = roster[0]
            weak_str = strv(weak["pid"], weak["data"])
            best_str, best_pid = fas[g][0]
            if best_str < weak_str + WAIVER_MARGIN:
                continue                              # no clear upgrade — stand pat
            conn.execute("UPDATE gtt_players SET fid=NULL WHERE league_id=? AND pid=?",
                         (league_id, weak["pid"]))
            conn.execute("UPDATE gtt_players SET fid=? WHERE league_id=? AND pid=?",
                         (fid, league_id, best_pid))
            conn.execute("INSERT INTO gtt_transactions (league_id, year, week, fid, gender,"
                         " add_pid, drop_pid, add_str, drop_str) VALUES (?,?,?,?,?,?,?,?,?)",
                         (league_id, year, week, fid, g, best_pid, weak["pid"],
                          round(best_str, 1), round(weak_str, 1)))
            fas[g].pop(0)                             # the signed FA leaves the wire,
            fas[g].append([weak_str, weak["pid"]])    # the cut player joins it
            fas[g].sort(key=lambda x: x[0], reverse=True)
            moves.append({"fid": fid, "gender": g, "add": best_pid, "drop": weak["pid"]})

    conn.commit()
    conn.close()
    return moves


def free_agents(league_id):
    """The current waiver wire — unsigned active players, best STR first within
    gender (men then women)."""
    conn = _db()
    rows = conn.execute("SELECT pid, gender, age, origin, data FROM gtt_players WHERE"
                        " league_id=? AND fid IS NULL AND status='active'",
                        (league_id,)).fetchall()
    conn.close()
    live = league_player_str(league_id)
    out = []
    for r in rows:
        p = _prospect(r["data"])
        strv = live.get(r["pid"], (p.str_value(), 0.0))[0]
        out.append({"pid": r["pid"], "name": p.name, "country": p.country,
                    "gender": r["gender"], "age": r["age"], "origin": r["origin"],
                    "str": round(strv, 1), "overall": round(p.current_overall())})
    out.sort(key=lambda x: (x["gender"] != "m", -x["str"]))
    return out


def transactions(league_id, year=None, limit=200):
    """The season's add/drop log, newest week first, with player + franchise names."""
    s = load_league(league_id)
    if not s:
        return []
    year = year if year is not None else s["current_year"]
    conn = _db()
    rows = conn.execute("SELECT * FROM gtt_transactions WHERE league_id=? AND year=?"
                        " ORDER BY week DESC, id DESC LIMIT ?",
                        (league_id, year, limit)).fetchall()
    names = _fr_names(conn, league_id)
    name_cache: dict = {}

    def meta(pid):
        """(name, origin) for a pid — null-safe: off-season rows are one-sided
        (a draft pick has no drop; a founder release has no add)."""
        if pid is None:
            return "", ""
        if pid not in name_cache:
            r = conn.execute("SELECT data, origin FROM gtt_players WHERE league_id=? AND pid=?",
                             (league_id, pid)).fetchone()
            name_cache[pid] = (_prospect(r["data"]).name, r["origin"] or "") if r else (pid, "")
        return name_cache[pid]

    out = []
    for r in rows:
        add_name, add_origin = meta(r["add_pid"])
        drop_name, drop_origin = meta(r["drop_pid"])
        out.append({"week": r["week"], "fid": r["fid"], "franchise": names.get(r["fid"], ""),
                    "gender": r["gender"], "add_pid": r["add_pid"], "add_name": add_name,
                    "add_origin": add_origin, "drop_pid": r["drop_pid"],
                    "drop_name": drop_name, "drop_origin": drop_origin,
                    "add_str": r["add_str"], "drop_str": r["drop_str"]})
    conn.close()
    return out


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


def _team_records_for_year(conn, lid, year):
    """Per (pid, franchise) W-L for the season. A GTT player can change clubs ANY
    week (the editor or the add/drop wire), unlike college's annual cycle — so a
    match is credited to the club the player actually suited up for that night
    (which the dual's home/away + the line's stored pids pin down exactly), not to
    whatever club they happen to be on now. Returns {pid: {fid: [w, l]}}."""
    rows = conn.execute("SELECT home, away, lines_json FROM gtt_duals WHERE league_id=?"
                        " AND year=? AND status='final'", (lid, year)).fetchall()
    rec: dict = {}
    for r in rows:
        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed"):
                continue
            hw = ln["home_won"]
            for pid in ln.get("home_pids", []):
                d = rec.setdefault(pid, {}).setdefault(r["home"], [0, 0]); d[0 if hw else 1] += 1
            for pid in ln.get("away_pids", []):
                d = rec.setdefault(pid, {}).setdefault(r["away"], [0, 0]); d[1 if hw else 0] += 1
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


# --------------------------------------------------------------------------
# STR continuity (P4) — pro results feed the same rating engine as college.
#
# Singles lines (MS/WS) feed `converge_ids` as pid -> [(opp, gw, gl)], oldest
# to newest so the rating's recency window works. Each player's PRIOR is the
# STR implied by their stored profile — for a graduate that profile is their
# college-exit snapshot, so the rating carries over with no seam and drifts as
# pro matches accumulate. Mixed doubles is display-only (two players a side).
# There is deliberately NO pro ranking page: the number computes and shows on
# profiles, but is never sorted into a leaderboard.
# --------------------------------------------------------------------------

_str_cache: dict = {}


def _parse_games(scoreline, home_won):
    """(home_games, away_games) from a winner-perspective scoreline ('6-4 3-6 6-2').
    GTT singles use the ncaa_dual format (no match-tiebreak), so every pair is a
    real set score."""
    wg = lg = 0
    for s in (scoreline or "").split():
        try:
            a, b = s.split("-")
            wg += int(a)
            lg += int(b)
        except ValueError:
            continue
    return (wg, lg) if home_won else (lg, wg)


def league_player_str(league_id):
    """Live results-based STR/reliability for every pro, from all completed GTT
    singles across the league's history (cached by completed-dual count)."""
    from .str_rating import converge_ids
    conn = _db()
    cnt = conn.execute("SELECT COUNT(*) c FROM gtt_duals WHERE league_id=? AND status='final'",
                       (league_id,)).fetchone()["c"]
    key = (league_id, cnt)
    cached = _str_cache.get(key)    # .get + local return: a concurrent clear is safe
    if cached is not None:
        conn.close()
        return cached
    rows = conn.execute("SELECT lines_json FROM gtt_duals WHERE league_id=? AND status='final'"
                        " ORDER BY year, week, id", (league_id,)).fetchall()
    priors = {r["pid"]: _prospect(r["data"]).str_value()
              for r in conn.execute("SELECT pid, data FROM gtt_players WHERE league_id=?",
                                    (league_id,)).fetchall()}
    conn.close()
    corpus: dict = {}
    for r in rows:
        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed") or not ln["slot"][:2] in ("MS", "WS"):
                continue
            hp, ap = ln.get("home_pids") or [], ln.get("away_pids") or []
            if len(hp) != 1 or len(ap) != 1:
                continue
            hg, ag = _parse_games(ln.get("scoreline"), ln["home_won"])
            corpus.setdefault(hp[0], []).append((ap[0], hg, ag))
            corpus.setdefault(ap[0], []).append((hp[0], ag, hg))
    # Wider gap window than college: a drafted pro league is a small closed
    # pool, so the best player legitimately out-rates the field by > 2.0 and
    # UTR's blowout exclusion would discard ALL of an outlier's matches.
    res = converge_ids(corpus, priors=priors, max_diff=6.0) if corpus else {}
    for k in list(_str_cache):          # prune this league only — see sm._prune_season
        if k[0] == league_id:
            _str_cache.pop(k, None)
    _str_cache[key] = res
    return res


def dual_detail(league_id, dual_id):
    """One dual's full line-by-line result (the 9 games), with player names — so
    every game in the season can be inspected individually on the full engine."""
    conn = _db()
    r = conn.execute("SELECT * FROM gtt_duals WHERE id=? AND league_id=?",
                     (dual_id, league_id)).fetchone()
    if not r:
        conn.close()
        return None
    names = _fr_names(conn, league_id)
    meta = _player_meta(conn, league_id)
    conn.close()
    d = dict(r)
    lines = []
    for ln in json.loads(d["lines_json"] or "[]"):
        lines.append({"slot": ln["slot"], "completed": ln.get("completed"),
                      "home_won": ln.get("home_won"), "scoreline": ln.get("scoreline"),
                      "home_stats": ln.get("home_stats"), "away_stats": ln.get("away_stats"),
                      "home_players": [{"pid": p, "name": meta.get(p, {}).get("name", p)}
                                       for p in ln.get("home_pids", [])],
                      "away_players": [{"pid": p, "name": meta.get(p, {}).get("name", p)}
                                       for p in ln.get("away_pids", [])]})
    return {"id": d["id"], "week": d["week"], "year": d["year"], "round": d["round"],
            "home_name": names.get(d["home"], str(d["home"])), "home_fid": d["home"],
            "away_name": names.get(d["away"], str(d["away"])), "away_fid": d["away"],
            "home_points": d["home_points"], "away_points": d["away_points"],
            "winner": d["winner"], "status": d["status"], "lines": lines}


def champion(league_id):
    s = load_league(league_id)
    if not s or s["phase"] != "complete" or s["champion"] is None:
        return None
    return {f["id"]: f for f in franchises(league_id)}.get(s["champion"])


def mvp(league_id, year=None):
    """The season MVP — a SEASON-ENDING award, like the champion. Mid-season there
    is no MVP (returns None); see `player_of_week` for in-season flavor."""
    s = load_league(league_id)
    if not s:
        return None
    year = year if year is not None else s["current_year"]
    if year == s["current_year"] and s["phase"] != "complete":
        return None
    conn = _db()
    row = _compute_mvp(conn, league_id, year)
    conn.close()
    return row


def player_of_week(league_id):
    """The standout of the most recently completed play week — in-season flavor,
    explicitly NOT the MVP (which is only awarded once the season ends). Best
    single-week record, win% then wins, minimum one win."""
    s = load_league(league_id)
    if not s:
        return None
    conn = _db()
    year = s["current_year"]
    week = conn.execute("SELECT MAX(week) w FROM gtt_duals WHERE league_id=? AND year=?"
                        " AND status='final'", (league_id, year)).fetchone()["w"]
    if week is None:
        conn.close()
        return None
    rec: dict = {}
    for r in conn.execute("SELECT lines_json FROM gtt_duals WHERE league_id=? AND year=?"
                          " AND week=? AND status='final'", (league_id, year, week)).fetchall():
        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed"):
                continue
            hw = ln["home_won"]
            for pid in ln.get("home_pids", []):
                d = rec.setdefault(pid, [0, 0]); d[0 if hw else 1] += 1
            for pid in ln.get("away_pids", []):
                d = rec.setdefault(pid, [0, 0]); d[1 if hw else 0] += 1
    meta = _player_meta(conn, league_id)
    names = _fr_names(conn, league_id)
    conn.close()
    best = None
    for pid, (w, l) in rec.items():
        if w == 0:
            continue
        key = (w / (w + l), w)
        if best is None or key > best[0]:
            best = (key, pid, w, l)
    if not best:
        return None
    _k, pid, w, l = best
    m = meta.get(pid, {})
    return {"pid": pid, "name": m.get("name", pid), "w": w, "l": l, "week": week,
            "fid": m.get("fid"), "franchise": names.get(m.get("fid"), "")}


def honors_board(league_id):
    board = {"champion": champion(league_id), "mvp": mvp(league_id)}
    if not board["mvp"]:                 # in-season: a player of the week, not an MVP
        board["potw"] = player_of_week(league_id)
    return board


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
    trec = _team_records_for_year(conn, league_id, year)
    rows = conn.execute("SELECT pid, gender, age, origin, data FROM gtt_players WHERE league_id=?"
                        " AND fid=? AND status='active'", (league_id, fid)).fetchall()
    conn.close()
    live = league_player_str(league_id)
    players = []
    for r in rows:
        p = _prospect(r["data"])
        by_team = trec.get(r["pid"], {})
        w, l = by_team.get(fid, [0, 0])        # record WITH this club (not lumped
        elsewhere = sum(v[0] + v[1] for f, v in by_team.items() if f != fid)
        strv = live.get(r["pid"], (p.str_value(), 0.0))[0]
        players.append({"pid": r["pid"], "name": p.name, "country": p.country, "gender": r["gender"],
                        "age": r["age"], "origin": r["origin"], "str": round(strv, 1),
                        "overall": round(p.current_overall()), "w": w, "l": l,
                        "elsewhere": elsewhere,        # matches this season for other clubs
                        "honors": player_honors(league_id, r["pid"])})
    # men by STR then women by STR
    players.sort(key=lambda x: (x["gender"] != "m", -x["str"]))
    for i, p in enumerate(players):
        block = [q for q in players if q["gender"] == p["gender"]]
        rank = block.index(p)
        lineup_n = LINEUP_MEN if p["gender"] == "m" else LINEUP_WOMEN
        p["reserve"] = rank >= lineup_n
        p["slot"] = ("RES" if p["reserve"]
                     else f"{'M' if p['gender'] == 'm' else 'W'}S{rank + 1}")
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
    trec = _team_records_for_year(conn, league_id, year)
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
                team_fid, opp_fid, won = r["home"], r["away"], ln["home_won"]
            elif pid in ln.get("away_pids", []):
                team_fid, opp_fid, won = r["away"], r["home"], not ln["home_won"]
            else:
                continue
            log.append({"week": r["week"], "round": r["round"], "slot": ln["slot"],
                        "team": names.get(team_fid, str(team_fid)), "team_fid": team_fid,
                        "opp": names.get(opp_fid, str(opp_fid)), "scoreline": ln.get("scoreline"),
                        "won": won})

    # Per-club split for the season — populated only when the player suited up for
    # more than one club this year (a mid-season move), so the stats track the 2nd
    # or 3rd team rather than crediting everything to the current club.
    by_team = trec.get(pid, {})
    teams = [{"fid": f, "team": names.get(f, str(f)), "w": v[0], "l": v[1]}
             for f, v in by_team.items()]
    teams.sort(key=lambda t: t["w"] + t["l"], reverse=True)
    multi_team = len(teams) > 1

    # --- Career by season: the college years (carried on the prospect's own
    # history, written by world._record_world_history before graduation) followed
    # by every pro season — the same table shape as the college player card, so a
    # graduate's four college years persist onto their pro page. ---
    strv, str_rel = league_player_str(league_id).get(pid, (p.str_value(), 0.0))
    career_rows = []
    for h in (p.history or []):
        career_rows.append({
            "kind": "college", "cal_year": 2026 + int(h.get("year", 0)),
            "team": h.get("school", ""), "division": h.get("division", ""),
            "gender": h.get("gender", ""), "cls": h.get("class", ""),
            "pos": h.get("line") or "—", "w": h.get("w"), "l": h.get("l"),
            "str": h.get("str"), "stint": h.get("stint", 0)})
    career_rows.sort(key=lambda r: (r["cal_year"], r["stint"]))
    conn3 = _db()
    for y in range(0, year + 1):
        ww, ll = _records_for_year(conn3, league_id, y).get(pid, [0, 0])
        if ww + ll == 0 and y != year:
            continue                                   # not in the league that season
        clubs = _team_records_for_year(conn3, league_id, y).get(pid, {})
        club = " / ".join(names.get(f, str(f)) for f in clubs) or names.get(row["fid"], "")
        career_rows.append({
            "kind": "pro", "cal_year": BASE_YEAR + y, "team": club,
            "division": "GTT", "gender": row["gender"],
            "cls": f"Pro {y - (row['joined_year'] or 0) + 1}" if row["origin"] != "founder" else "Pro",
            "pos": "—", "w": ww, "l": ll,
            "str": round(strv, 1) if y == year else None, "stint": 0})
    # The player's own transaction history (drafted / signed / waived), all years.
    tx_rows = conn3.execute(
        "SELECT year, week, fid, add_pid, drop_pid, add_str, drop_str FROM gtt_transactions"
        " WHERE league_id=? AND (add_pid=? OR drop_pid=?) ORDER BY year DESC, week DESC, id DESC",
        (league_id, pid, pid)).fetchall()
    moves = []
    for t in tx_rows:
        added = t["add_pid"] == pid
        kind = ("Drafted / signed" if t["week"] == 0 else "Signed off the wire") if added \
            else ("Released" if t["week"] == 0 else "Waived")
        moves.append({"cal_year": BASE_YEAR + t["year"], "week": t["week"],
                      "kind": kind, "added": added,
                      "franchise": names.get(t["fid"], str(t["fid"]))})
    conn3.close()

    # Scouting grades for the attribute panel — same 20-80 scale the college card
    # shows, so the pro card reads like the same player sheet.
    attributes = [(lbl, p.current_grade(a)) for lbl, a in (
        ("Serve Power", "first_serve_power"), ("Serve Accuracy", "first_serve_accuracy"),
        ("Return", "return_quality"), ("Forehand", "forehand_power"),
        ("Backhand", "backhand_power"), ("Consistency", "groundstroke_consistency"),
        ("Net Play", "net_play"), ("Speed", "speed"), ("Stamina", "stamina"),
        ("Composure", "composure"), ("Clutch", "clutch"))]

    enshrined = conn2 = None
    conn2 = _db()
    enshrined = conn2.execute("SELECT 1 FROM gtt_hof WHERE league_id=? AND pid=?",
                              (league_id, pid)).fetchone() is not None
    conn2.close()

    import app.honors as honors
    career = honors.career_by_year(pid, "player")
    return {"pid": pid, "name": p.name, "country": p.country, "gender": row["gender"],
            "age": row["age"], "origin": row["origin"], "status": row["status"],
            "fid": row["fid"], "franchise": names.get(row["fid"], "Free agent"),
            "str": round(strv, 1), "str_reliability": round(str_rel, 2),
            "overall": round(p.current_overall()),
            "w": w, "l": l, "honors": player_honors(league_id, pid),
            "season_teams": teams, "multi_team": multi_team,
            "career_honors": career, "log": log, "enshrined": enshrined,
            "career_table": career_rows, "moves": moves, "attributes": attributes,
            "college_school": next((r["team"] for r in career_rows
                                    if r["kind"] == "college"), None)}


# --------------------------------------------------------------------------
# Hall of Fame (freeze a profile + archive) and the awards archive
# --------------------------------------------------------------------------

def _career_record(conn, league_id, pid):
    w = l = 0
    for r in conn.execute("SELECT lines_json FROM gtt_duals WHERE league_id=? AND status='final'",
                          (league_id,)).fetchall():
        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed"):
                continue
            if pid in ln.get("home_pids", []):
                w, l = (w + 1, l) if ln["home_won"] else (w, l + 1)
            elif pid in ln.get("away_pids", []):
                w, l = (w + 1, l) if not ln["home_won"] else (w, l + 1)
    return w, l


def is_enshrined(league_id, pid):
    conn = _db()
    row = conn.execute("SELECT 1 FROM gtt_hof WHERE league_id=? AND pid=?",
                       (league_id, pid)).fetchone()
    conn.close()
    return row is not None


def enshrine(league_id, pid):
    """Freeze a player's profile as it stands and file it in the Hall of Fame
    archive. The snapshot (attributes, career record, honors) never changes after
    — even as the live player keeps declining or retires."""
    s = load_league(league_id)
    if not s:
        return False
    conn = _db()
    row = conn.execute("SELECT * FROM gtt_players WHERE league_id=? AND pid=?",
                       (league_id, pid)).fetchone()
    if not row or conn.execute("SELECT 1 FROM gtt_hof WHERE league_id=? AND pid=?",
                               (league_id, pid)).fetchone():
        conn.close()
        return False
    w, l = _career_record(conn, league_id, pid)
    conn.close()
    p = _prospect(row["data"])
    import app.honors as honors
    snapshot = honors.career_by_year(pid, "player")     # frozen honors snapshot
    conn = _db()
    conn.execute("INSERT INTO gtt_hof (league_id, pid, name, gender, year_enshrined, data,"
                 " honors_json, record, peak_str) VALUES (?,?,?,?,?,?,?,?,?)",
                 (league_id, pid, p.name, row["gender"], BASE_YEAR + s["current_year"],
                  row["data"], json.dumps(snapshot), f"{w}-{l}", round(p.str_value(), 1)))
    conn.commit()
    conn.close()
    return True


def hall_of_fame(league_id):
    """The frozen archive — every enshrined profile, newest first."""
    conn = _db()
    rows = conn.execute("SELECT * FROM gtt_hof WHERE league_id=? ORDER BY year_enshrined DESC, id DESC",
                        (league_id,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        p = _prospect(r["data"])
        out.append({"pid": r["pid"], "name": r["name"], "gender": r["gender"], "country": p.country,
                    "year": r["year_enshrined"], "record": r["record"], "str": r["peak_str"],
                    "overall": round(p.current_overall()),
                    "honors": json.loads(r["honors_json"] or "[]")})
    return out


def season_history(league_id):
    """The awards archive: champion + MVP for every completed season, newest first."""
    conn = _db()
    names = _fr_names(conn, league_id)
    rows = conn.execute("SELECT * FROM gtt_seasons WHERE league_id=? ORDER BY year DESC",
                        (league_id,)).fetchall()
    out = []
    for r in rows:
        mvp_name = None
        if r["mvp_pid"]:
            pr = conn.execute("SELECT data FROM gtt_players WHERE league_id=? AND pid=?",
                              (league_id, r["mvp_pid"])).fetchone()
            mvp_name = _prospect(pr["data"]).name if pr else None
        out.append({"year": r["year"], "cal_year": BASE_YEAR + r["year"],
                    "champion": names.get(r["champion"]), "champion_fid": r["champion"],
                    "mvp": mvp_name, "mvp_pid": r["mvp_pid"]})
    conn.close()
    return out
