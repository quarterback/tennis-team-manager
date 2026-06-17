"""
The unified tennis World — one clock, every division and both genders, advanced
WEEK BY WEEK with a season-long itemized drip (not an overnight batch).

A `World` (keyed by seed) spans all six universes (D1/D2/D3 × men/women) on one
shared calendar. Each weekly tick:

  1. simulates that week's match slate for every universe (reusing season mode,
     so schedules / standings / box scores all come for free),
  2. develops every rostered player a slice of a year (the slow drip),
  3. signs a slice of the next national recruiting class — preferences resolve
     and commitments trickle in across the year, blue-chips to powerhouses and
     high-academic talent to Ivies / NESCAC / academies (prestige + academics).

When every universe has finished its NCAA bracket, the next tick FINALIZES the
year: graduate seniors, execute the cross-division transfer portal off the
season's real results, bring in the signed class, top up with walk-ons — then
roll to next year, week 1.

Persistence is deliberately small: only each year's *starting* rosters and the
accumulating signing class are stored; the in-season development drip is a
deterministic replay of the week counter, and match results live in season mode.
The rollover steps are pure functions over plain roster dicts, so they unit-test
without any DB or simulation.
"""
from __future__ import annotations

import bisect
import copy
import json
import random
import secrets
import sqlite3
import threading
from dataclasses import asdict, fields

import app.seasonmode as sm
from .season import dual_between
from . import dbpath, worldconfig, ncaa
from .dbpath import resolve_db_path
from .development import (Prospect, generate_prospect, make_pid, overall_to_str,
                          stagger_scale)
from .ncaa import (Program, load_division, build_roster, reset_caches, _roster_cache,
                   _talent_from_strength, _talent_mean, _pick_gender, region_proximity,
                   REGION_ADJACENT, ROSTER_SIZE, SCHOLARSHIP_SLOTS)
from .recruiting import (program_appeal, recruit_caliber, recruit_academic01,
                         home_region, academic_gate, GEO_WEIGHT, FAC_WEIGHT, ACA_PULL)
from .juniors import generate_class, rank_class
from generators import make_name_picker

WORLD_DB = resolve_db_path()        # shares the file with season mode; own tables
UNIVERSES = [("D1", "men"), ("D1", "women"), ("D2", "men"),
             ("D2", "women"), ("D3", "men"), ("D3", "women")]
GENDERS = ["men", "women"]
DEFAULT_SEED = 2026
BASE_YEAR = 2026

_NEXT_CLASS = {"Fr": "So", "So": "Jr", "Jr": "Sr"}

# Development drip: a full season's growth spread across ~this many ticks.
DEV_WEEKS = 16
# Signings spread across roughly this many ticks; the rest sign at finalize.
SIGNING_WEEKS = 13

# Transfer churn (NCAA tennis: ~14% men / ~11% women; most moves are DOWN/OUT).
BASE_MOVE = {"men": 0.155, "women": 0.12}
UP_THRESHOLD = 0.8
UP_SUCCESS = 0.35
RELIABILITY_GATE = 0.4

# National recruiting pool per gender — large + bottom-heavy so it feeds freshman
# openings across all three divisions with a realistic long tail.
RECRUIT_POOL = 1000     # a bounded recruiting cadre, not a full-blast class; teams
                        # sign from it, unsigned become walk-ons, and remaining
                        # roster seats are backfilled with generated walk-ons.
# The national recruit pool is drawn from the ONE talent scale (ncaa._talent_mean),
# centred on a mid-tier (D2, median-strength) program for that gender — a dense,
# bulb-shaped class: a high floor (only college-caliber juniors), a thick middle,
# a thin elite tail. The blue-chip top develops into D1 stars; recruiting
# allocation tiers the pool to programs (so genuine talent can fall to a smaller
# school). Women's ceiling sits below men's. Small SD → thin margins between tiers.
RECRUIT_TALENT_SD = 7.0


def _recruit_talent_mean(gender: str) -> float:
    return _talent_mean(0.5, "D2", gender)
# Share of the national class that is international — the default for HOW MANY
# internationals exist. It is now player-tunable per league via worldconfig
# (set at onboarding); this constant is just the fallback default.
RECRUIT_INTL_SHARE = worldconfig.DEFAULT_INTL_SHARE
# Where internationals land: a per-tier pull (D1 most, then D2, then academically
# elite D3; ordinary D3 stays local). Tunable — internationals concentrate at the
# top because they have no homecooking and chase prestige/academics. Real men's
# D1 tennis runs very international; lower these to dampen it.
INTL_TIER_PULL = {"D1": 1.0, "D2": 0.72, "D3_elite": 0.5, "D3": 0.15}


def _intl_tier(division: str, academics: float) -> str:
    if division == "D3":
        return "D3_elite" if academics >= ELITE_D3_ACADEMICS else "D3"
    return division


# ==========================================================================
# Prospect (de)serialization
# ==========================================================================
_FIELDS = {f.name for f in fields(Prospect)}


def prospect_to_dict(p: Prospect) -> dict:
    return asdict(p)


def prospect_from_dict(d: dict) -> Prospect:
    return Prospect(**{k: v for k, v in d.items() if k in _FIELDS})


# ==========================================================================
# Persistence
# ==========================================================================
_SCHEMA = """
CREATE TABLE IF NOT EXISTS world (
  id INTEGER PRIMARY KEY, seed INTEGER UNIQUE, year INTEGER, week INTEGER
);
CREATE TABLE IF NOT EXISTS world_roster (
  world_id INTEGER, year INTEGER, division TEXT, gender TEXT, school TEXT,
  pid TEXT, data TEXT
);
CREATE TABLE IF NOT EXISTS world_signing (
  world_id INTEGER, year INTEGER, gender TEXT, school TEXT, pid TEXT, data TEXT,
  week_signed INTEGER DEFAULT 0, flips INTEGER DEFAULT 0, commit_history TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS world_crossmatch (
  world_id INTEGER, year INTEGER, gender TEXT, home TEXT, away TEXT,
  home_div TEXT, away_div TEXT, home_pts INTEGER, away_pts INTEGER,
  winner INTEGER, lines TEXT
);
CREATE TABLE IF NOT EXISTS world_championship (
  world_id INTEGER, year INTEGER, division TEXT, gender TEXT, event TEXT, data TEXT
);
CREATE TABLE IF NOT EXISTS world_graduates (
  world_id INTEGER, year INTEGER, division TEXT, gender TEXT, pid TEXT,
  str REAL, ovr REAL, data TEXT
);
CREATE INDEX IF NOT EXISTS idx_wr ON world_roster(world_id, year);
CREATE INDEX IF NOT EXISTS idx_ws ON world_signing(world_id, year, gender);
CREATE INDEX IF NOT EXISTS idx_wx ON world_crossmatch(world_id, year, gender);
CREATE INDEX IF NOT EXISTS idx_wg ON world_graduates(world_id, year, division, gender);
"""

DIV_RANK = {"D1": 1, "D2": 2, "D3": 3}      # 1 = highest classification
MAX_CROSS = 3                               # cross-classification duals per team / year
ELITE_D3_ACADEMICS = 0.85                   # a D3 this academic can reach up to D1


_schema_ready_for = None        # the WORLD_DB the schema was last created for


def init_schema() -> None:
    """Eagerly create the world schema (auto-committing connection) so the lazy
    path never writes inside a held transaction."""
    global _schema_ready_for
    conn = dbpath.connect(WORLD_DB)
    conn.executescript(_SCHEMA)
    for col, typ in (("week_signed", "INTEGER DEFAULT 0"), ("flips", "INTEGER DEFAULT 0"),
                     ("commit_history", "TEXT DEFAULT '[]'")):
        try:
            conn.execute(f"ALTER TABLE world_signing ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute("ALTER TABLE world ADD COLUMN salt TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
    _schema_ready_for = WORLD_DB


def _db() -> sqlite3.Connection:
    """Tuned connection (WAL + busy timeout); schema created once per (path)."""
    if _schema_ready_for != WORLD_DB:
        init_schema()
    return dbpath.connect(WORLD_DB)


def _save_rosters(conn, world_id, year, rosters) -> None:
    conn.execute("DELETE FROM world_roster WHERE world_id=? AND year=?", (world_id, year))
    rows = [(world_id, year, d, g, school, p.pid, json.dumps(prospect_to_dict(p)))
            for (d, g), schools in rosters.items()
            for school, roster in schools.items() for p in roster]
    conn.executemany("INSERT INTO world_roster VALUES (?,?,?,?,?,?,?)", rows)


def _save_graduates(conn, world_id, year, rosters, player_str: dict | None = None) -> int:
    """Persist the authoritative graduating cohort before ``graduate`` drops it."""
    conn.execute("DELETE FROM world_graduates WHERE world_id=? AND year=?", (world_id, year))
    rows = []
    player_str = player_str or {}
    for (d, g), schools in rosters.items():
        if not worldconfig.is_active(d, g):
            continue
        for roster in schools.values():
            for p in roster:
                if p.class_year != "Sr":
                    continue
                rows.append((world_id, year, d, g, p.pid, float(_str_of(player_str, p)),
                             float(p.current_overall()), json.dumps(prospect_to_dict(p))))
    conn.executemany("INSERT INTO world_graduates VALUES (?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def _active_unis() -> list[tuple[str, str]]:
    """The division×gender universes the player chose to run in detail. The rest
    are seeded (players exist) but left dormant — the memory/CPU saving."""
    return [(d, g) for (d, g) in UNIVERSES if worldconfig.is_active(d, g)]


def _load_rosters(conn, world_id, year, unis=None) -> dict:
    rows = conn.execute("SELECT division, gender, school, data FROM world_roster"
                        " WHERE world_id=? AND year=?", (world_id, year)).fetchall()
    active = set(unis) if unis is not None else None
    out: dict = {}
    for r in rows:
        if active is not None and (r["division"], r["gender"]) not in active:
            continue                      # dormant universe — don't materialise it
        out.setdefault((r["division"], r["gender"]), {}).setdefault(r["school"], []).append(
            prospect_from_dict(json.loads(r["data"])))
    return out


def _seed_year0(division, gender) -> dict:
    div = load_division(division, gender)
    return {p.school: [copy.deepcopy(q) for q in build_roster(p)] for p in div.programs}


def get_or_create(seed: int = DEFAULT_SEED, salt: str | None = None) -> dict:
    conn = _db()
    row = conn.execute("SELECT * FROM world WHERE seed=?", (seed,)).fetchone()
    if row:
        conn.close()
        d = dict(row)
        ncaa.WORLD_SALT = d.get("salt") or ""    # publish the active league's salt
        return d
    # Fresh league: a random salt makes every New League produce different
    # rosters/recruits/pids for the same schools. Publish it BEFORE building so
    # the year-0 rosters are generated against it.
    salt = salt or secrets.token_hex(8)
    ncaa.WORLD_SALT = salt
    cur = conn.execute("INSERT INTO world (seed, year, week, salt) VALUES (?,0,0,?)", (seed, salt))
    wid = cur.lastrowid
    # Seed year-0 rosters ONE universe at a time, persisting and freeing each
    # before building the next. Building all six universes' rich rosters at once
    # (~17k prospects) was the memory spike behind the OOM; this caps the peak at
    # roughly a single universe.
    reset_caches()
    conn.execute("DELETE FROM world_roster WHERE world_id=? AND year=?", (wid, 0))
    for (d, g) in UNIVERSES:
        uni = _seed_year0(d, g)
        rows = [(wid, 0, d, g, school, p.pid, json.dumps(prospect_to_dict(p)))
                for school, roster in uni.items() for p in roster]
        conn.executemany("INSERT INTO world_roster VALUES (?,?,?,?,?,?,?)", rows)
        del uni, rows
        reset_caches()                               # free this universe before the next
    conn.commit()
    row = conn.execute("SELECT * FROM world WHERE id=?", (wid,)).fetchone()
    conn.close()
    return dict(row)


def load_world(seed: int = DEFAULT_SEED) -> dict | None:
    conn = _db()
    row = conn.execute("SELECT * FROM world WHERE seed=?", (seed,)).fetchone()
    conn.close()
    return dict(row) if row else None


def exists(seed: int = DEFAULT_SEED) -> bool:
    return load_world(seed) is not None


def reset(seed: int = DEFAULT_SEED) -> None:
    """Wipe all season-to-season state so the next get_or_create() starts a fresh
    league at preseason (year 0, week 0, nothing played). Single-player sandbox,
    so this clears the dynamic tables wholesale; the deterministic base rosters
    are regenerated from seed. Career/legend archives (added later) are NOT
    touched by this."""
    conn = _db()
    conn.executescript(
        "DELETE FROM world_crossmatch; DELETE FROM world_signing; "
        "DELETE FROM world_graduates; DELETE FROM world_roster; DELETE FROM world;"
    )
    conn.commit()
    conn.close()
    # Season-mode schedule/results live in their own tables — clear them too.
    sconn = sm._db()
    sconn.executescript("DELETE FROM duals; DELETE FROM seasons;")
    sconn.commit()
    sconn.close()
    # Career honors + coach identities are season-to-season state too.
    import app.honors as honors
    import app.coachreg as coachreg
    honors.reset()
    coachreg.reset()
    # Stored individual championships are keyed to the (now-deleted) world; clear
    # them so a new save can't surface a prior league's champions.
    conn = _db()
    conn.execute("DELETE FROM world_championship")
    conn.commit()
    conn.close()
    # God-mode editor overrides (player moves, lineups, prestige/academics priors,
    # scholarship limits) are per-save tweaks — wipe them so each new league is
    # distinct and no prior save's artifacts leak into the Active Overrides list.
    import app.overrides as overrides
    import app.scholarships as scholarships
    overrides.clear_all()
    scholarships.clear_overrides()
    # Drop every in-memory cache so nothing stale survives the reset.
    _base_cache.clear()
    _dev_cache.clear()
    _primed.clear()
    _class_cache.clear()
    ncaa.WORLD_SALT = ""
    reset_caches()
    sm._pid_idx_cache.clear()
    sm._str_cache.clear()
    for _c in (sm._prec_cache, sm._pline_cache, sm._plrec_cache, sm._pi_cache, sm._forced_cache):
        _c.clear()


def start_new(seed: int = DEFAULT_SEED, salt: str | None = None) -> dict:
    """Reset and create a brand-new league at preseason (week 0, nothing
    played). The onboarding 'Start new league' action. A fresh random salt
    (unless one is supplied, e.g. for tests) means the new league's rosters and
    recruits differ from every previous save."""
    reset(seed)
    return get_or_create(seed, salt=salt)


def current_year_seed(seed: int = DEFAULT_SEED) -> int:
    w = load_world(seed)
    return year_seed(seed, w["year"]) if w else seed


def active_salt(seed: int = DEFAULT_SEED) -> str:
    """The active league's generation salt (or '' if no world exists yet). All
    roster + recruit generation is keyed by this, so each New League is fresh
    while staying deterministic within the league."""
    w = load_world(seed)
    salt = (w.get("salt") or "") if w else ""
    ncaa.WORLD_SALT = salt        # keep the ncaa generator in sync with the active world
    return salt


def signed_counts(seed: int = DEFAULT_SEED) -> dict:
    w = load_world(seed)
    if not w:
        return {}
    conn = _db()
    rows = conn.execute("SELECT gender, COUNT(*) c FROM world_signing WHERE world_id=? AND year=?"
                        " GROUP BY gender", (w["id"], w["year"])).fetchall()
    conn.close()
    return {r["gender"]: r["c"] for r in rows}


def recruiting_grad_year(seed: int = DEFAULT_SEED) -> int:
    """The ONE active recruiting class — the HS grad-year the sim is currently
    signing (next year's incoming freshmen). There is only ever a single class
    in the pool: this year's. It is the only class eligible to be recruited and
    to play the junior circuit, and matches `national_class` (BASE_YEAR + year + 1)
    so the board, the recruit pages, and the signing drip all read the same pool."""
    w = load_world(seed)
    return BASE_YEAR + (w["year"] if w else 0) + 1


def signings(seed: int = DEFAULT_SEED) -> dict:
    """{gender: {school: [Prospect, ...]}} for the class signed so far this world-year
    — the live commitments the Signing Tracker reads (fills as the season advances)."""
    w = load_world(seed)
    if not w:
        return {}
    conn = _db()
    try:
        return _load_signings(conn, w)
    finally:
        conn.close()


def find_persisted_player(pid: str, seed: int = DEFAULT_SEED):
    """Look up a player by pid in the active league's PERSISTED data — committed
    signees first (world_signing), then rostered players (world_roster, newest
    year first). Returns a Prospect or None. This is step 1 of the /recruit/<pid>
    lookup order: anyone already tied to a team is found here regardless of which
    recruiting class they originally came from."""
    w = load_world(seed)
    if not w:
        return None
    conn = _db()
    try:
        r = conn.execute("SELECT data, flips, week_signed, commit_history FROM world_signing"
                         " WHERE world_id=? AND pid=? LIMIT 1", (w["id"], pid)).fetchone()
        if r:
            p = prospect_from_dict(json.loads(r["data"]))
            p.flips = r["flips"] or 0
            p.week_signed = r["week_signed"] or 0
            try:
                p.commit_history = json.loads(r["commit_history"] or "[]")
            except (ValueError, TypeError):
                p.commit_history = []
            return p
        r = conn.execute("SELECT data FROM world_roster WHERE world_id=? AND pid=?"
                         " ORDER BY year DESC LIMIT 1", (w["id"], pid)).fetchone()
        if r:
            return prospect_from_dict(json.loads(r["data"]))
        return None
    finally:
        conn.close()


# ==========================================================================
# Rosters as-of the current week: year-start rosters + a development replay.
# ==========================================================================
_base_cache: dict = {}      # (world_id, year) -> year-start rosters
_dev_cache: dict = {}       # (world_id, year, week) -> developed rosters
_primed: dict = {}          # seed -> (world_id, year, week) currently in ncaa cache
_prime_lock = threading.Lock()   # serialize the ~170MB cache build across gthreads


def _base_rosters(world: dict) -> dict:
    key = (world["id"], world["year"])
    if key not in _base_cache:
        conn = _db()
        _base_cache[key] = _load_rosters(conn, world["id"], world["year"], _active_unis())
        conn.close()
    return _base_cache[key]


def developed_rosters(world: dict) -> dict:
    """Year-start rosters advanced to `week` of STAGGERED development (deterministic).

    Players don't all develop at once: each banks a full year of growth inside a
    phase-shifted window of the DEV_WEEKS-long season (app.development.stagger_scale),
    so midseason some have already jumped, some are mid-climb, and some haven't moved
    — but by season's end everyone has banked the same year. Replayed week-by-week so
    any week's snapshot is reproducible."""
    key = (world["id"], world["year"], world["week"])
    if key in _dev_cache:
        return _dev_cache[key]
    rosters = {uni: {s: [copy.deepcopy(p) for p in r] for s, r in schools.items()}
               for uni, schools in _base_rosters(world).items()}
    for wk in range(world["week"]):
        for schools in rosters.values():
            for roster in schools.values():
                for p in roster:
                    s = stagger_scale(p.pid, wk, DEV_WEEKS)
                    if s:
                        p.develop(s)
    _dev_cache[key] = rosters
    return rosters


def prime(seed: int = DEFAULT_SEED) -> dict:
    """Load this world's as-of-now rosters into the shared roster cache so every
    consumer — season mode, run_season rankings, team pages, box scores — sees
    the same evolving players. The one-world hinge."""
    w = get_or_create(seed)
    stamp = (w["id"], w["year"], w["week"])
    if _primed.get(seed) == stamp and _roster_cache:
        return w
    # Only one thread builds the full-world cache at a time; the rest wait and
    # reuse it. Without this, concurrent gthreads each materialise ~170MB of
    # rosters on a cold cache and the worker OOMs.
    with _prime_lock:
        if _primed.get(seed) == stamp and _roster_cache:     # built while we waited
            return w
        rosters = developed_rosters(w)
        reset_caches()
        for (division, gender), schools in rosters.items():
            for school, roster in schools.items():
                _roster_cache[f"{school}|{division}|{gender}"] = roster
        sm._pid_idx_cache.clear(); sm._str_cache.clear()
        _primed[seed] = stamp
    return w


def season_complete(seed: int = DEFAULT_SEED) -> bool:
    """True when every universe has finished its postseason — i.e. the season is
    ready for the awards phase and year rollover."""
    if not exists(seed):
        return False
    return _all_complete(seed, get_or_create(seed))


def year_seed(seed: int, year: int) -> int:
    return seed + 1000 * year


def universe_sid(seed: int, world: dict, division: str, gender: str) -> int:
    return sm.get_or_create(division, gender, seed=year_seed(seed, world["year"]))


def universe_states(seed: int = DEFAULT_SEED) -> list[dict]:
    w = get_or_create(seed)
    out = []
    for (d, g) in _active_unis():
        s = sm.load_season(universe_sid(seed, w, d, g))
        out.append({"division": d, "gender": g, **s})
    return out


def _all_complete(seed: int, world: dict) -> bool:
    return all(sm.load_season(universe_sid(seed, world, d, g))["phase"] == "complete"
               for (d, g) in _active_unis())


# ==========================================================================
# Recruiting — national class + the weekly signing drip.
# ==========================================================================
_class_cache: dict = {}


# The class generator (pids included via make_pid) is keyed by the gender string,
# so the sim's world-vocab ("men"/"women") and the recruit board's juniors-vocab
# ("male"/"female") MUST collapse to one canonical token — otherwise they build
# two disjoint classes with different pids and a signed recruit never appears in
# the board's pool.
_GENDER_CANON = {"men": "male", "women": "female", "male": "male", "female": "female"}


def recruit_class(gender: str, grad_year: int, salt: str):
    """THE canonical recruiting class for an active league — the single source of
    truth shared by the web board, the recruit detail pages, committed-player
    lookup, and the sim's signing logic. Keyed by (salt, canonical-gender,
    grad_year) so it is fresh per New League but stable within a league, and so
    "women"/"female" (and "men"/"male") resolve to the SAME class. Enriched with
    the junior circuit so the web board's results/rankings are present; pids and
    identities are identical to what the sim signs from."""
    gender = _GENDER_CANON.get(gender, gender)
    key = (salt, gender, grad_year)
    if key not in _class_cache:
        rng = random.Random(f"{salt}|recruits|{gender}|{grad_year}")
        klass = generate_class(rng, n=RECRUIT_POOL, grad_year=grad_year,
                               gender=gender, talent_mean=_recruit_talent_mean(gender),
                               talent_sd=RECRUIT_TALENT_SD, intl_share=worldconfig.intl_share(),
                               intl_weights=worldconfig.region_weights())
        rank_class(klass)                          # national rank + star ladder
        from app.junior_circuit import run_junior_circuit
        run_junior_circuit(klass, seed=salt)       # junior results/points for the board
        from app.juniors import points_rankings
        points_rankings(klass)                     # freeze points-ledger rank
        _class_cache[key] = klass
    return _class_cache[key]


def national_class(seed: int, year: int, gender: str) -> list:
    """The sim's signing pool for a world-year: the canonical class ranked by
    recruiting score. grad_year = BASE_YEAR + year + 1."""
    return rank_class(recruit_class(gender, BASE_YEAR + year + 1, active_salt(seed)))


def _flat_programs(gender: str) -> dict[str, Program]:
    out = {}
    for division in ("D1", "D2", "D3"):
        try:
            for p in load_division(division, gender).programs:
                out[p.school] = p
        except FileNotFoundError:
            continue
    return out


def _openings(base_rosters: dict, gender: str) -> dict[str, int]:
    """Projected freshman seats per program for next year = seniors graduating
    (rosters are otherwise full)."""
    out = {}
    for (division, g), schools in base_rosters.items():
        if g != gender:
            continue
        for school, roster in schools.items():
            out[school] = sum(1 for p in roster if p.class_year == "Sr")
    return out


def _recruit_market(world: dict, gender: str) -> dict:
    """Precomputed program tables a recruit consults to pick a school —
    prestige-sorted window, top-academic set, region buckets, and per-school
    seat capacity. Shared by the weekly drip and the decommit pass."""
    progs = _flat_programs(gender)
    traits = {s: (p.prestige, p.academics, p.region, p.division, p.facilities)
              for s, p in progs.items()}
    cap = _openings(_base_rosters(world), gender)
    by_pres = sorted(progs, key=lambda s: traits[s][0])
    pres_arr = [traits[s][0] for s in by_pres]
    academic_top = sorted(progs, key=lambda s: -traits[s][1])[:40]
    by_region: dict[str, list] = {}
    for s in progs:
        by_region.setdefault(traits[s][2], []).append(s)
    return {"progs": progs, "traits": traits, "cap": cap, "by_pres": by_pres,
            "pres_arr": pres_arr, "academic_top": academic_top, "by_region": by_region}


def _pick_school(p, market: dict, avail: dict, *, jitter_salt: str,
                 exclude: set | None = None) -> str | None:
    """Score every plausible program for prospect `p` and return the best one
    with an open seat. `exclude` blocks specific schools (used for decommits)."""
    traits = market["traits"]
    by_pres, pres_arr = market["by_pres"], market["pres_arr"]
    cal, ac = recruit_caliber(p), recruit_academic01(p)
    hr = home_region(p)
    hc = float(getattr(p, "homecooking", 0.0))
    intl = not getattr(p, "domestic", False)
    # Window: from a bit below their level up to well above it, so a recruit will
    # reach UP to a strong program that has an opening (a chance to play for a
    # major beats being a star at a much smaller school) — the upside isn't capped.
    lo = bisect.bisect_left(pres_arr, cal - 0.30)
    hi = bisect.bisect_left(pres_arr, cal + 0.55)
    cands = set(by_pres[lo:hi]) | set(market["academic_top"])
    if hc > 0.0 and not intl:
        cands |= set(market["by_region"].get(hr, ()))
    if exclude:
        cands -= exclude
    best, best_score = None, -1.0
    jit = random.Random(f"{p.pid}|{jitter_salt}").uniform(-0.05, 0.05)
    for s in cands:
        if avail.get(s, 0) <= 0:
            continue
        pres, acad, reg, div, fac = traits[s]
        geo = hc * region_proximity(hr, reg)
        # Recruits aspire UP to the most prestigious program that still has a seat
        # for them. With best-recruits-first + seat caps, the class tiers itself —
        # a program fills with whoever's left near its own level once it signs,
        # so it never starves chasing names above its band. A mild pull toward
        # their own level keeps elite talent from slumming far below it; academics
        # pull sub-elite recruits down to academic programs (gated by talent).
        level = 1.0 - 0.30 * max(0.0, cal - pres)      # only penalize signing BELOW your level
        score = ((0.15 + pres) * level
                 * (1.0 + ACA_PULL * acad * ac * academic_gate(cal))
                 * (1.0 + GEO_WEIGHT * geo) * (1.0 + FAC_WEIGHT * fac) * (1 + jit))
        if intl:
            score *= INTL_TIER_PULL[_intl_tier(div, acad)]
        if score > best_score:
            best, best_score = s, score
    if best is None:                              # nothing in range with a seat — widen once
        best = next((s for s in reversed(by_pres)
                     if avail.get(s, 0) > 0 and (not exclude or s not in exclude)), None)
    return best


# Rank-dependent decision timing: where in the signing window a recruit's
# commitment peaks, as a fraction of the window. Blue-chips hold out and decide
# LATE (they take every visit, weigh every offer); lower-rated recruits commit
# EARLY — locking in a program (often one above what their ranking warrants)
# before the seat is gone. The per-recruit week is drawn around this peak so the
# tiers interleave (a 5★ can still pop early, a 3★ can drag late) but the bulk
# of the elite tier lands deep in the season.
SIGNING_MODE_TOP = 0.82     # #1 recruit's decision-week peak (× window) — latest
SIGNING_MODE_BOTTOM = 0.12  # lowest recruit's peak — earliest
SIGNING_FLOOR_TOP = 0.40    # #1 recruit can't commit before this much of the season
                            # has elapsed (the back of the class can commit week 0)


def _decision_week(p, salt: str, rank_frac: float = 0.5, window: int = SIGNING_WEEKS) -> int:
    """The 0-based week WITHIN the signing window at which this recruit commits —
    deterministic per recruit, and SKEWED BY RANK so signings drip across the whole
    regular season: top recruits decide late, lower recruits decide early.

    `rank_frac` is the recruit's position in the national class (0.0 = the #1
    recruit, 1.0 = the last). It sets both the EARLIEST week a recruit will commit
    (blue-chips hold out — they can't sign in the opening weeks) and the mode of a
    triangular draw, so the elite tier clusters late while the back of the class
    signs quickly — instead of one fat weekly quota clearing the board by mid-season."""
    window = max(1, window)
    rng = random.Random(f"{getattr(p, 'pid', '')}|decision|{salt}")
    lo = window * SIGNING_FLOOR_TOP * (1.0 - rank_frac)          # top recruits can't go early
    mode_frac = SIGNING_MODE_TOP - (SIGNING_MODE_TOP - SIGNING_MODE_BOTTOM) * rank_frac
    mode = max(lo, window * mode_frac)
    wk = int(rng.triangular(lo, window, mode))
    return max(0, min(window - 1, wk))


def _sign_batch(conn, world: dict, gender: str, quota: int, *, final: bool = False,
                window: int = SIGNING_WEEKS) -> int:
    """Sign up to `quota` more recruits this tick. Each unsigned recruit that has
    REACHED ITS DECISION WEEK (best first) commits to the open program with the
    highest fit that still has a projected seat. At `final` (year rollover) the
    decision-week gate is lifted so anyone still uncommitted signs."""
    wid, week = world["id"], world["week"]
    salt = world.get("salt") or ""
    rows = conn.execute("SELECT pid, school FROM world_signing WHERE world_id=? AND year=? AND gender=?",
                        (wid, world["year"], gender)).fetchall()
    signed = {r["pid"] for r in rows}
    taken: dict[str, int] = {}
    for r in rows:
        taken[r["school"]] = taken.get(r["school"], 0) + 1

    market = _recruit_market(world, gender)
    avail = {s: market["cap"].get(s, 0) - taken.get(s, 0) for s in market["progs"]}

    klass = national_class(world["seed"], world["year"], gender)
    denom = max(1, len(klass) - 1)
    new = []
    signed_n = 0
    for i, p in enumerate(klass):
        if signed_n >= quota:
            break
        if p.pid in signed:
            continue
        # rank_frac: 0.0 = the #1 recruit (decides latest), 1.0 = back of the class
        if not final and _decision_week(p, salt, i / denom, window) > week:
            continue                                        # hasn't decided to commit yet
        best = _pick_school(p, market, avail, jitter_salt="sign")
        if best is None:
            continue
        avail[best] -= 1
        signed.add(p.pid)
        new.append((wid, world["year"], gender, best, p.pid,
                    json.dumps(prospect_to_dict(p)), week, 0,
                    json.dumps([{"school": best, "week": week}])))
        signed_n += 1
    if new:
        conn.executemany(
            "INSERT INTO world_signing (world_id, year, gender, school, pid, data,"
            " week_signed, flips, commit_history) VALUES (?,?,?,?,?,?,?,?,?)", new)
    return signed_n


DECOMMIT_WINDOW_WEEKS = 3       # only signings this fresh can flip
DECOMMIT_RATE = 0.067           # per eligible recruit per tick. Over a 3-week
                                # window this is 1 - 0.933**3 ≈ 18.8% lifetime
                                # flip rate — the Power Four CFB benchmark.
DECOMMIT_CUTOFF_WEEK = 10       # no flips after this point in the signing window


def _decommit_pass(conn, world: dict, gender: str) -> int:
    """Recent signings (within DECOMMIT_WINDOW_WEEKS) each roll a flip; flippers
    move to the next-best open school on their list — they do NOT re-enter the
    pool. Capped after DECOMMIT_CUTOFF_WEEK so late commits stick."""
    wid, week = world["id"], world["week"]
    if week >= DECOMMIT_CUTOFF_WEEK:
        return 0
    cutoff = week - DECOMMIT_WINDOW_WEEKS
    rows = conn.execute(
        "SELECT rowid, pid, school, data, flips, commit_history FROM world_signing"
        " WHERE world_id=? AND year=? AND gender=? AND week_signed>=?",
        (wid, world["year"], gender, cutoff)).fetchall()
    if not rows:
        return 0

    all_rows = conn.execute(
        "SELECT school FROM world_signing WHERE world_id=? AND year=? AND gender=?",
        (wid, world["year"], gender)).fetchall()
    taken: dict[str, int] = {}
    for r in all_rows:
        taken[r["school"]] = taken.get(r["school"], 0) + 1
    market = _recruit_market(world, gender)
    avail = {s: market["cap"].get(s, 0) - taken.get(s, 0) for s in market["progs"]}

    flips = 0
    for r in rows:
        if random.random() >= DECOMMIT_RATE:
            continue
        original = r["school"]
        p = prospect_from_dict(json.loads(r["data"]))
        avail[original] = avail.get(original, 0) + 1            # free the old seat first
        new_school = _pick_school(p, market, avail,
                                  jitter_salt=f"flip|{week}", exclude={original})
        if new_school is None or new_school == original:        # nowhere to go — stay put
            avail[original] -= 1
            continue
        avail[new_school] -= 1
        try:
            trail = json.loads(r["commit_history"] or "[]")
        except (ValueError, TypeError):
            trail = []
        trail.append({"school": new_school, "week": week})
        conn.execute("UPDATE world_signing SET school=?, week_signed=?, flips=flips+1,"
                     " commit_history=? WHERE rowid=?",
                     (new_school, week, json.dumps(trail), r["rowid"]))
        flips += 1
    return flips


def _load_signings(conn, world: dict) -> dict[str, dict[str, list]]:
    """{gender: {school: [Prospect, ...]}} for the class that's signed so far.
    Each prospect carries the live `flips` count (how many times they've
    decommitted) and `week_signed` of their current commit."""
    rows = conn.execute("SELECT gender, school, data, flips, week_signed FROM world_signing"
                        " WHERE world_id=? AND year=?", (world["id"], world["year"])).fetchall()
    out: dict = {}
    for r in rows:
        p = prospect_from_dict(json.loads(r["data"]))
        p.flips = r["flips"] or 0
        p.week_signed = r["week_signed"] or 0
        out.setdefault(r["gender"], {}).setdefault(r["school"], []).append(p)
    return out


# ==========================================================================
# Rollover steps — pure functions over {(division,gender): {school: [Prospect]}}.
# ==========================================================================

def _str_of(player_str: dict, p: Prospect) -> float:
    v = player_str.get(p.pid)
    return v[0] if v else p.str_value()


def _rel_of(player_str: dict, p: Prospect) -> float:
    v = player_str.get(p.pid)
    return v[1] if v else 0.0


def _prog_level(prog: Program) -> float:
    return overall_to_str(_talent_from_strength(prog.prestige, prog.division, prog.gender))


def _scholarship_count(roster: list) -> int:
    return sum(1 for p in roster if not p.walk_on)


def graduate(rosters: dict) -> int:
    """Graduate seniors and bump everyone else up a class. (Development for the
    year already happened via the weekly drip.)"""
    grads = 0
    for schools in rosters.values():
        for school, roster in schools.items():
            kept = []
            for p in roster:
                if p.class_year == "Sr":
                    grads += 1
                    continue
                p.class_year = _NEXT_CLASS.get(p.class_year, "So")
                kept.append(p)
            schools[school] = kept
    return grads


def intake_signings(rosters: dict, signings: dict) -> int:
    """Add the signed recruiting class onto rosters as freshmen."""
    n = 0
    for (division, gender), schools in rosters.items():
        gsign = signings.get(gender, {})
        for school, roster in schools.items():
            for p in gsign.get(school, []):
                fr = copy.deepcopy(p)
                fr.class_year = "Fr"
                fr.committed = True
                fr.walk_on = _scholarship_count(roster) >= SCHOLARSHIP_SLOTS
                roster.append(fr)
                n += 1
    return n


def _churn_mult(s: float, level: float) -> float:
    if s < level - 1.0:
        return 1.5
    if s > level + UP_THRESHOLD:
        return 1.0
    return 0.6


def _relocate(pool, p, src, dest, *, walk_on):
    pool[src].remove(p)
    p.walk_on = walk_on
    pool[dest].append(p)


PRESTIGE_BAND = 0.30        # how far up/down a program tier a transfer reaches


def transfer_portal(rosters: dict, player_str: dict, rng: random.Random, gender: str) -> dict:
    """Global, cross-division portal for one gender. Up/down are decided by
    program PRESTIGE, so a buried D1 player can drop to D2/D3 for playing time
    and a D3 star can climb. Ranked by the season's live STR.

    Indexed for speed: per-school sorted STR arrays give O(log n) lineup-fit
    lookups, and candidate destinations are restricted to a prestige band, so the
    whole world's portal resolves in seconds rather than scanning every program
    for every mover."""
    progs = _flat_programs(gender)
    pool: dict[str, list] = {}
    for (division, g), schools in rosters.items():
        if g != gender:
            continue
        pool.update(schools)
    schools = [s for s in pool if s in progs]
    prestige = {s: progs[s].prestige for s in schools}
    facilities = {s: progs[s].facilities for s in schools}
    level = {s: _prog_level(progs[s]) for s in schools}
    strs = {s: sorted(_str_of(player_str, p) for p in pool[s]) for s in schools}
    schol = {s: _scholarship_count(pool[s]) for s in schools}
    by_pres = sorted(schools, key=lambda s: prestige[s])
    pres_arr = [prestige[s] for s in by_pres]

    def open_slot(s):
        return len(pool[s]) < ROSTER_SIZE and schol[s] < SCHOLARSHIP_SLOTS

    def line_of(s, val):
        a = strs[s]
        return 1 + (len(a) - bisect.bisect_right(a, val))

    def band(lo, hi):                       # schools with prestige in [lo, hi)
        return by_pres[bisect.bisect_left(pres_arr, lo):bisect.bisect_left(pres_arr, hi)]

    def relocate(p, src, dest, sval, *, walk_on):
        pool[src].remove(p)
        a = strs[src]; i = bisect.bisect_left(a, sval)
        a.pop(i if i < len(a) and a[i] == sval else a.index(sval))
        if not p.walk_on:
            schol[src] -= 1
        p.walk_on = walk_on
        pool[dest].append(p)
        bisect.insort(strs[dest], sval)
        if not walk_on:
            schol[dest] += 1

    base = BASE_MOVE.get(gender, 0.13)
    movers = []
    for school in schools:
        lvl = level[school]
        for p in list(pool[school]):
            s = _str_of(player_str, p)
            if p.walk_on:
                movers.append((p, school, s, "schol"))
            elif rng.random() < base * _churn_mult(s, lvl):
                movers.append((p, school, s, "churn"))
    movers.sort(key=lambda m: -m[2])

    out = {"movers": len(movers), "up": 0, "down": 0, "schol": 0, "depart": 0, "sample": []}
    for p, src, s, reason in movers:
        src_pres = prestige[src]
        cl = line_of(src, s)

        if reason == "schol":              # walk-on wants a scholarship (top-6 spot)
            dest = None
            for d in reversed(band(src_pres - PRESTIGE_BAND, src_pres + 0.06)):
                if d != src and open_slot(d) and line_of(d, s) <= SCHOLARSHIP_SLOTS:
                    dest = d; break
            if dest:
                relocate(p, src, dest, s, walk_on=False)
                out["schol"] += 1
                out["sample"].append(("schol", p.name, src, dest, round(s, 1)))
            else:
                pool[src].remove(p)
                a = strs[src]; i = bisect.bisect_left(a, s)
                a.pop(i if i < len(a) and a[i] == s else a.index(s))
                out["depart"] += 1
            continue

        up_dest, up_draw = None, -1.0      # best reach where they'd contribute
        for d in band(src_pres + 1e-9, src_pres + PRESTIGE_BAND):
            if open_slot(d) and line_of(d, s) <= 6:
                draw = prestige[d] + 0.3 * facilities[d]   # facilities sweeten the move
                if draw > up_draw:
                    up_dest, up_draw = d, draw
        down_dest, down_line = None, cl    # weaker program where they'd play higher
        for d in band(src_pres - PRESTIGE_BAND, src_pres):
            if open_slot(d):
                ln = line_of(d, s)
                if ln < down_line:
                    down_dest, down_line = d, ln
        rel = _rel_of(player_str, p)
        order = (["up", "down"] if cl <= 2 else ["down", "up"] if cl >= 4
                 else (["up", "down"] if rng.random() < 0.5 else ["down", "up"]))
        moved = False
        for d in order:
            if d == "up" and up_dest and rel >= RELIABILITY_GATE \
                    and (s - level[src]) >= UP_THRESHOLD and rng.random() < UP_SUCCESS:
                relocate(p, src, up_dest, s, walk_on=False)
                out["up"] += 1
                out["sample"].append(("up", p.name, src, up_dest, round(s, 1)))
                moved = True; break
            if d == "down" and down_dest:
                relocate(p, src, down_dest, s, walk_on=False)
                out["down"] += 1
                out["sample"].append(("down", p.name, src, down_dest, round(s, 1)))
                moved = True; break
        if not moved:
            pool[src].remove(p)
            a = strs[src]; i = bisect.bisect_left(a, s)
            a.pop(i if i < len(a) and a[i] == s else a.index(s))
            out["depart"] += 1
    return out


def refill_walkons(rosters: dict, year: int, seed: int) -> int:
    """Top every roster back up to size with walk-on freshmen."""
    intake = 0
    for (division, gender), schools in rosters.items():
        progs = {p.school: p for p in load_division(division, gender).programs}
        for school, roster in schools.items():
            prog = progs.get(school)
            need = ROSTER_SIZE - len(roster)
            if not prog or need <= 0:
                continue
            prng = random.Random(f"{seed}|{prog.key}|walkon|{year}")
            name_fn = make_name_picker(random.Random(f"{seed}|{prog.key}|wn|{year}"),
                                       gender=_pick_gender(gender),
                                       region_weights=worldconfig.region_weights())
            tmean = max(28.0, _talent_from_strength(prog.strength, prog.division, prog.gender) - 8.0)
            for k in range(need):
                name, country = name_fn()
                talent = max(24.0, min(70.0, prng.gauss(tmean, 5.0)))
                fr = generate_prospect(prng, name, country, gender=_pick_gender(gender),
                                       talent=talent, pid=make_pid(prog.key, "wo", year, k))
                fr.class_year = "Fr"; fr.walk_on = True
                roster.append(fr)
                intake += 1
    return intake


def _normalize(rosters: dict) -> None:
    for schools in rosters.values():
        for school, roster in schools.items():
            roster.sort(key=lambda p: p.current_overall(), reverse=True)
            del roster[ROSTER_SIZE:]


def coach_carousel(rosters: dict, player_str: dict, rng: random.Random, gender: str) -> dict:
    """Free-agent coach movement, run BEFORE the player portal. A slice of head
    coaches move up to higher-prestige programs (a swap with the program they
    join). When a coach moves, up to half of their old roster MAY follow — but
    only players good enough for the new program's level, so a D3 coach reaching
    D1 brings at most their very best. Mutates `rosters` + the coach registry."""
    import app.coachgen as coachgen
    import app.coachreg as coachreg

    progs: dict[str, tuple] = {}
    for (d, g), schools in rosters.items():
        if g != gender:
            continue
        div = load_division(d, g)
        for school in schools:
            p = div.by_school(school)
            if p:
                progs[school] = (d, p.prestige)
    if len(progs) < 4:
        return {"moves": 0, "followers": 0, "sample": []}

    by_pres = sorted(progs, key=lambda s: progs[s][1])          # ascending prestige
    n_move = max(1, int(len(by_pres) * 0.10))
    movers_pool = by_pres[:int(len(by_pres) * 0.85)]            # leave the very top put
    rng.shuffle(movers_pool)

    used: set[str] = set()
    moves = followers = 0
    sample = []
    for src in movers_pool:
        if moves >= n_move:
            break
        if src in used:
            continue
        sdiv, spres = progs[src]
        dests = [s for s in by_pres if s not in used and s != src and progs[s][1] > spres + 0.05]
        if not dests:
            continue
        dest = rng.choice(dests[:max(1, len(dests) // 2)])     # an ambitious-but-real jump
        ddiv, _ = progs[dest]
        coachgen.ensure(sdiv, gender, src, "head")             # register both seats so we can swap
        coachgen.ensure(ddiv, gender, dest, "head")
        coachreg.swap_head_coaches(gender, sdiv, src, ddiv, dest)
        used.add(src); used.add(dest); moves += 1

        # Followers: src's coach is now at dest. Up to half of src's roster may
        # follow, gated to players who'd make dest's lineup (its 6th-best STR).
        sr = rosters[(sdiv, gender)][src]
        dr = rosters[(ddiv, gender)][dest]
        dstr = sorted((_str_of(player_str, p) for p in dr), reverse=True)
        floor = (dstr[5] if len(dstr) >= 6 else (dstr[-1] if dstr else 0.0)) - 1.0
        eligible = [p for p in sr if _str_of(player_str, p) >= floor]
        cap = min(len(sr) // 2, len(eligible))
        k = rng.randint(0, cap) if cap > 0 else 0
        for p in (rng.sample(eligible, k) if k else []):
            sr.remove(p); dr.append(p)
            followers += 1
        if k:
            sample.append((src, dest, k))
    return {"moves": moves, "followers": followers, "sample": sample[:6]}


def finalize_rollover(rosters: dict, signings: dict, player_str: dict, *,
                      seed: int, year: int) -> dict:
    """The post-season: graduate → coach carousel → transfer portal (per gender)
    → bring in the signed class → refill with walk-ons. Mutates `rosters`."""
    rng = random.Random(f"{seed}|finalize|{year}")
    grads = graduate(rosters)
    carousel = {"moves": 0, "followers": 0, "sample": []}
    for gender in GENDERS:
        if not any(g == gender for (_, g) in rosters):
            continue
        cr = coach_carousel(rosters, player_str, rng, gender)
        carousel["moves"] += cr["moves"]
        carousel["followers"] += cr["followers"]
        carousel["sample"].extend(cr["sample"][:3])
    portal = {"movers": 0, "up": 0, "down": 0, "schol": 0, "depart": 0, "sample": []}
    for gender in GENDERS:
        if not any(g == gender for (_, g) in rosters):
            continue
        pr = transfer_portal(rosters, player_str, rng, gender)
        for k in ("movers", "up", "down", "schol", "depart"):
            portal[k] += pr[k]
        portal["sample"].extend(pr["sample"][:6])
    committed = intake_signings(rosters, signings)
    intake = refill_walkons(rosters, year + 1, seed)
    _normalize(rosters)
    return {"graduated": grads, "committed": committed, "walkons": intake,
            "coach_moves": carousel["moves"], "coach_followers": carousel["followers"],
            "coach_sample": carousel["sample"],
            **{f"portal_{k}": v for k, v in portal.items()}}


# ==========================================================================
# Cross-classification (cross-division) non-conference scheduling.
#   • Adjacent classes (D1↔D2, D2↔D3) plus elite (high-academic) D3 reaching D1.
#   • Geography-driven (same / adjacent region) and capped per team per year.
#   • The higher classification hosts.
# ==========================================================================
from .ncaa import location  # noqa: E402  (geography for cross-division pairing)


def _allowed_cross(a, b) -> bool:
    """Is a cross-class dual between programs a, b allowed?"""
    if a.division == b.division:
        return False
    ra, rb = DIV_RANK[a.division], DIV_RANK[b.division]
    if abs(ra - rb) == 1:                                  # D1-D2 or D2-D3
        return True
    # D1-D3 only when the D3 program is academically elite (NESCAC/UAA-type).
    d3 = a if a.division == "D3" else b
    return d3.academics >= ELITE_D3_ACADEMICS


def cross_schedule(seed: int, year: int) -> list[dict]:
    """Deterministic cross-division non-conference slate. Each team gets up to
    MAX_CROSS duals against nearby programs in an allowed other classification;
    the higher classification hosts. Pure (no DB / no sim)."""
    rng = random.Random(f"{seed}|cross|{year}")
    out: list[dict] = []
    for gender in GENDERS:
        progs = _flat_programs(gender)
        by_region: dict[str, list] = {}
        for p in progs.values():
            if p.region:
                by_region.setdefault(p.region, []).append(p)
        count = {s: 0 for s in progs}
        pairs = set()
        order = list(progs.values())
        rng.shuffle(order)
        for p in order:
            # nearby pool = same region + adjacent regions
            pool = list(by_region.get(p.region, []))
            for r in REGION_ADJACENT.get(p.region, ()):
                pool.extend(by_region.get(r, []))
            tries = 0
            while count[p.school] < MAX_CROSS and tries < 40 and pool:
                tries += 1
                o = rng.choice(pool)
                if o.school == p.school or count[o.school] >= MAX_CROSS:
                    continue
                key = tuple(sorted((p.school, o.school)))
                if key in pairs or not _allowed_cross(p, o):
                    continue
                pairs.add(key)
                count[p.school] += 1
                count[o.school] += 1
                hi, lo = (p, o) if DIV_RANK[p.division] < DIV_RANK[o.division] else (o, p)
                out.append({"gender": gender, "home": hi.school, "away": lo.school,
                            "home_div": hi.division, "away_div": lo.division})
    return out


def simulate_cross(seed: int = DEFAULT_SEED) -> int:
    """Generate + simulate this year's cross-division slate once, storing results.
    Rosters are primed first so the duals use the world's current players (and
    the lineup model rests starters vs a weaker class — bench/walk-ons play)."""
    w = get_or_create(seed)
    conn = _db()
    have = conn.execute("SELECT COUNT(*) c FROM world_crossmatch WHERE world_id=? AND year=?",
                        (w["id"], w["year"])).fetchone()["c"]
    if have:
        conn.close()
        return 0
    prime(seed)
    progs = {g: _flat_programs(g) for g in GENDERS}
    active = set(_active_unis())
    rows = []
    for m in cross_schedule(seed, w["year"]):
        if (m["home_div"], m["gender"]) not in active or (m["away_div"], m["gender"]) not in active:
            continue                      # skip matchups touching a dormant universe
        a, b = progs[m["gender"]][m["home"]], progs[m["gender"]][m["away"]]
        sd = int.from_bytes(__import__("hashlib").blake2s(
            f"{seed}|{w['year']}|{m['home']}|{m['away']}".encode(), digest_size=4).digest(), "big")
        rec = dual_between(a, b, seed=sd, conf=False, lineup_seed=year_seed(seed, w["year"]))
        rows.append((w["id"], w["year"], m["gender"], m["home"], m["away"],
                     m["home_div"], m["away_div"], rec["home_points"], rec["away_points"],
                     0 if rec["home_won"] else 1, json.dumps(rec["lines"])))
    conn.executemany("INSERT INTO world_crossmatch VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return len(rows)


def cross_results_for(seed: int, school: str) -> list[dict]:
    """A school's cross-division results this world-year (for team pages)."""
    w = load_world(seed)
    if not w:
        return []
    conn = _db()
    rows = conn.execute(
        "SELECT home, away, home_div, away_div, home_pts, away_pts, winner FROM world_crossmatch"
        " WHERE world_id=? AND year=? AND (home=? OR away=?)",
        (w["id"], w["year"], school, school)).fetchall()
    conn.close()
    out = []
    for r in rows:
        home = r["home"] == school
        out.append({"opp": r["away"] if home else r["home"],
                    "opp_div": r["away_div"] if home else r["home_div"],
                    "home": home, "won": (r["winner"] == 0) == home,
                    "mine": r["home_pts"] if home else r["away_pts"],
                    "theirs": r["away_pts"] if home else r["home_pts"]})
    return out


# ==========================================================================
# The weekly driver.
# ==========================================================================

def _signing_window(seed: int, w: dict) -> int:
    """The recruiting drip spans the full REGULAR season, so commitments stretch
    across the whole year instead of clearing out by mid-season. Uses the longest
    active-universe regular season (its `total_weeks`); falls back to the constant
    before any season exists."""
    weeks = []
    for (d, g) in _active_unis():
        s = sm.load_season(universe_sid(seed, w, d, g))
        if s and s.get("total_weeks"):
            weeks.append(s["total_weeks"])
    return max(weeks) if weeks else SIGNING_WEEKS


def advance_week(seed: int = DEFAULT_SEED) -> dict:
    """Advance the whole world one week — or finalize the year if every universe
    has finished its postseason."""
    w = get_or_create(seed)
    if _all_complete(seed, w):
        return _finalize_year(seed, w)

    prime(seed)
    cross = 0
    if w["week"] == 0:                      # start of year: play the cross-division slate
        cross = simulate_cross(seed)
    played = 0
    for (d, g) in _active_unis():
        sid = universe_sid(seed, w, d, g)
        if sm.load_season(sid)["phase"] != "complete":
            res = sm.advance(sid)
            played += res.get("played", 0)

    # Recruiting drip: flip a few recent commits, then sign a slice of each
    # active gender's class this week.
    conn = _db()
    signed = 0
    flips = 0
    window = _signing_window(seed, w)        # drip across the whole regular season
    for gender in worldconfig.active_genders():
        flips += _decommit_pass(conn, w, gender)
        quota = max(1, sum(_openings(_base_rosters(w), gender).values()) // window)
        signed += _sign_batch(conn, w, gender, quota, window=window)
    conn.execute("UPDATE world SET week=? WHERE id=?", (w["week"] + 1, w["id"]))
    conn.commit()
    conn.close()
    _primed.pop(seed, None)               # week advanced → re-prime (more dev) next access
    return {"event": "week", "year": w["year"], "week": w["week"] + 1,
            "played": played, "signed": signed, "flips": flips, "cross": cross,
            "complete": _all_complete(seed, get_or_create(seed))}


def _record_world_history(seed: int, world: dict, rosters: dict) -> None:
    """Append each rostered player's just-finished season line to their career
    history — {year, school, division, class, line, record, str}. Called before
    graduation/portal, so `class`/`school` reflect the season actually played; a
    school change between a player's entries is a transfer. Idempotent per year."""
    from app import overrides as ov
    moves = ov.get_moves()                # pid -> destination school (editor moves)
    year, season_no = world["year"], world["year"] + 1
    # Per active universe: that season's stats + a school->division map. A moved
    # player actually PLAYS in their destination universe's duals, so we read
    # their record/line/STR from THAT season, not the source one being iterated.
    udata = {}
    sch_div: dict = {}
    for (d, g) in _active_unis():
        sid = universe_sid(seed, world, d, g)
        udata[(d, g)] = {
            "recs": sm.player_records(sid), "lines": sm.player_primary_lines(sid),
            "line_recs": sm.player_line_records(sid), "strmap": sm.season_player_str(sid),
        }
        if g not in sch_div:
            sch_div[g] = {s: pr.division for s, pr in _flat_programs(g).items()}
    for (division, gender) in _active_unis():
        for school, roster in rosters.get((division, gender), {}).items():
            for p in roster:
                if any(h.get("year") == year for h in p.history):
                    continue                      # already recorded this year
                played_school = moves.get(p.pid, school)   # honor editor moves
                dest_div = sch_div.get(gender, {}).get(played_school, division)
                src = udata.get((dest_div, gender), udata[(division, gender)])
                w_, l_ = src["recs"].get(p.pid, (0, 0))
                s, _rel = src["strmap"].get(p.pid, (p.str_value(), 0.0))
                lr = src["line_recs"].get(p.pid, {"singles": {}, "doubles": {}})
                p.history.append({
                    "year": year, "season_no": season_no,
                    "division": dest_div, "gender": gender, "school": played_school,
                    "class": p.class_year, "line": src["lines"].get(p.pid),
                    "w": w_, "l": l_, "str": round(s, 1),
                    "singles_lines": {str(k): v for k, v in lr["singles"].items()},
                    "doubles_lines": {str(k): v for k, v in lr["doubles"].items()},
                })


def _store_championships(conn, world: dict) -> None:
    """Run + persist the individual singles/doubles championships for each active
    universe at season's end (rosters are still this year's), so the completed
    championship is viewable after the year rolls over."""
    from app.individuals import (run_singles_championship, run_doubles_championship,
                                 championship_to_dict)
    yr = world["year"]
    eff = year_seed(world["seed"], yr)
    for (division, gender) in _active_unis():
        conn.execute("DELETE FROM world_championship WHERE world_id=? AND year=?"
                     " AND division=? AND gender=?", (world["id"], yr, division, gender))
        for event, run in (("Singles", run_singles_championship),
                           ("Doubles", run_doubles_championship)):
            try:
                ch = run(division, gender, seed=eff)
                conn.execute("INSERT INTO world_championship VALUES (?,?,?,?,?,?)",
                             (world["id"], yr, division, gender, event,
                              json.dumps(championship_to_dict(ch))))
            except Exception:
                pass


def latest_championship(seed: int, division: str, gender: str, event: str,
                        year: int | None = None) -> dict | None:
    """A completed individual championship for a universe (None until one has been
    played + stored at a year rollover). `year` is the world-year INDEX for a
    specific past season; default is the most recent stored."""
    w = load_world(seed)
    if not w:
        return None
    conn = _db()
    try:
        if year is None:
            r = conn.execute("SELECT data FROM world_championship WHERE world_id=? AND division=?"
                             " AND gender=? AND event=? ORDER BY year DESC LIMIT 1",
                             (w["id"], division, gender, event)).fetchone()
        else:
            r = conn.execute("SELECT data FROM world_championship WHERE world_id=? AND division=?"
                             " AND gender=? AND event=? AND year=? LIMIT 1",
                             (w["id"], division, gender, event, year)).fetchone()
    finally:
        conn.close()
    return json.loads(r["data"]) if r else None


def championship_years(seed: int, division: str, gender: str) -> list[int]:
    """Calendar years with a stored individual championship for this universe
    (newest first) — the season picker for the championship archive."""
    w = load_world(seed)
    if not w:
        return []
    conn = _db()
    try:
        rows = conn.execute("SELECT DISTINCT year FROM world_championship WHERE world_id=?"
                            " AND division=? AND gender=? ORDER BY year DESC",
                            (w["id"], division, gender)).fetchall()
    finally:
        conn.close()
    return [BASE_YEAR + r["year"] for r in rows]


def _finalize_year(seed: int, w: dict) -> dict:
    """End-of-year: develop to a full year, then graduate / portal / intake."""
    prime(seed)
    # Results-based STR from the just-finished seasons drives the portal.
    player_str: dict = {}
    for (d, g) in _active_unis():
        player_str.update(sm.season_player_str(universe_sid(seed, w, d, g)))

    # Snapshot the individual championships before graduation/portal change rosters.
    _cconn = _db()
    _store_championships(_cconn, w)
    _cconn.commit()
    _cconn.close()

    rosters = developed_rosters(w)        # full-year developed copy
    # Stamp each player's just-finished season onto their career history BEFORE
    # graduation/portal moves them — so the player card (and, later, the pro
    # league) can show where they played year over year.
    _record_world_history(seed, w, rosters)
    # season_player_str above needed the primed cache; the rollover works on
    # `rosters` (an independent copy), so free the ~170MB primed roster cache now
    # rather than holding it alongside `rosters` through the heavy rollover.
    reset_caches(); _primed.pop(seed, None)
    conn = _db()
    _save_graduates(conn, w["id"], w["year"], rosters, player_str)
    signings = _load_signings(conn, w)
    # Sign anyone still unsigned before the class arrives (decision-week gate off).
    for gender in worldconfig.active_genders():
        _sign_batch(conn, w, gender, RECRUIT_POOL, final=True)
    conn.commit()
    signings = _load_signings(conn, w)

    summary = finalize_rollover(rosters, signings, player_str, seed=seed, year=w["year"])

    new_year = w["year"] + 1
    _save_rosters(conn, w["id"], new_year, rosters)
    # Dormant universes don't develop or roll over — carry their rosters forward
    # unchanged with a cheap SQL copy (no Python materialisation), so their
    # players still exist next year.
    active = set(_active_unis())
    for (d, g) in UNIVERSES:
        if (d, g) in active:
            continue
        conn.execute(
            "INSERT INTO world_roster (world_id, year, division, gender, school, pid, data) "
            "SELECT world_id, ?, division, gender, school, pid, data FROM world_roster "
            "WHERE world_id=? AND year=? AND division=? AND gender=?",
            (new_year, w["id"], w["year"], d, g))
    conn.execute("UPDATE world SET year=?, week=0 WHERE id=?", (new_year, w["id"]))
    conn.commit()
    conn.close()
    _base_cache.clear(); _dev_cache.clear(); _primed.pop(seed, None)
    summary.update(event="finalize", year=new_year, week=0)
    return summary
