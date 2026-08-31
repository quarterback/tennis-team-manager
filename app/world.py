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
import datetime as _dt
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
                   REGION_ADJACENT, ROSTER_SIZE, SCHOLARSHIP_SLOTS, roster_cap,
                   autogen_walkons, admits_nationality, blocked_schools_for,
                   is_domestic_player, us_only_program, lineup_size, walkon_talent)
from .recruiting import (program_appeal, recruit_caliber, recruit_academic01,
                         perceived_caliber, consensus_caliber,
                         home_region, academic_gate, GEO_WEIGHT, FAC_WEIGHT, ACA_PULL,
                         COACH_LOCAL_WEIGHT, LOCAL_TERRITORY_PULL)
from .juniors import generate_class, rank_class
from generators import make_name_picker
from generators.flavor import flag_emoji

WORLD_DB = resolve_db_path()        # shares the file with season mode; own tables
UNIVERSES = [("D1", "men"), ("D1", "women"), ("D2", "men"),
             ("D2", "women"), ("D3", "men"), ("D3", "women"),
             ("D4", "men"), ("D4", "women")]
GENDERS = ["men", "women"]
DEFAULT_SEED = 2026
BASE_YEAR = 2026

_NEXT_CLASS = {"Fr": "So", "So": "Jr", "Jr": "Sr"}
_RS_PREFIX = "RS-"


def _base_class(cy: str) -> str:
    """Class year with any medical-redshirt tag stripped ('RS-Jr' -> 'Jr')."""
    return cy[len(_RS_PREFIX):] if cy.startswith(_RS_PREFIX) else cy


def _departing(p) -> bool:
    """Whether a player leaves at THIS year's rollover: a senior, a pro grad
    transfer ("Gr" — one-and-done, see AAR-pro-grad-transfers), or a legacy
    pre-rule pro with no class year (migrated out at the next rollover). The ONE
    predicate for departure — recruiting seat planning (`_openings`), graduation
    (`graduate`), and the graduate export (`_save_graduates`) must all agree, or
    a program that hosts a pro under-recruits and its roster runs short."""
    base = _base_class(getattr(p, "class_year", "") or "")
    if base in ("Sr", "Gr"):
        return True
    if not base:
        from app.pros import is_pro
        return is_pro(p)
    return False

# Development drip: a full season's growth spread across ~this many ticks.
DEV_WEEKS = 16
# Signings spread across roughly this many ticks; the rest sign at finalize.
SIGNING_WEEKS = 13

# Transfer churn (NCAA tennis: ~14% men / ~11% women; most moves are DOWN/OUT).
BASE_MOVE = {"men": 0.155, "women": 0.12}
UP_THRESHOLD = 0.8
UP_SUCCESS = 0.35
RELIABILITY_GATE = 0.4

# Fall transfer portal calibration. The post-ITA reshuffle is a CURATED event, not
# a mass migration: it should rescue the handful of genuinely mis-allocated players
# (a D1-caliber talent stuck in a lower division), not relocate the best one or two
# players at every program. A riser must (a) be a top-2 starter at their school and
# (b) clear a higher division's TYPICAL (median) expected level — proof they belong
# a tier up, not just that they're the best of a weak team. We then move only the
# most mis-allocated up to a per-gender cap (each can trigger one cascade demotion).
FALL_PORTAL_MAX_RISERS = 30
# The PRE-SEASON portal is a one-time correction of world-GENERATION misallocation, not
# the fall portal's curated mid-season reshuffle — so it gets its OWN, larger cap, tunable
# per save in the UI (worldconfig.preseason_portal_cap, default 250). The fall portal keeps
# FALL_PORTAL_MAX_RISERS. This module-level value is just the fallback default.
PRESEASON_PORTAL_MAX_RISERS = 250

# National recruiting pool per gender — large + bottom-heavy so it feeds freshman
# openings across all three divisions with a realistic long tail.
RECRUIT_POOL = 2500     # sized to cover annual roster TURNOVER (~2,200 pool-filled
                        # slots/gender: D1 12 + D2 10 + D3/D4 core, ÷4 graduating
                        # classes), plus a realistic unsigned tail. Must exceed demand
                        # so D2 fills core AND walk-on depth from real recruits — no
                        # game-generated walk-ons outside D3/D4. (D1 now recruits its
                        # scholarship core ONLY — see _openings — so pool demand fell;
                        # the extra headroom feeds D2-D4 and the unsigned tail.)
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
INTL_TIER_PULL = {"D1": 1.0, "D2": 0.72, "D3_elite": 0.5, "D3": 0.15, "D4": 0.05}

# Playing time as a recruit factor (owner rule 2027-07): recruits prefer programs
# where their OVR would crack the current starting card (the division's lineup size —
# ncaa.lineup_size), so good players stop signing where they'll be buried. A KEY
# factor but BELOW prestige — the prestige term spans a ~4× range and still
# dominates; this is a ±PLAY_TIME_WEIGHT multiplier on top. Programs still oversign
# and some recruits still ride the bench, but the field is more competitive.
# PLAY_TIME_SCALE = OVR points of last-starter margin that saturate the factor.
PLAY_TIME_WEIGHT = 0.35
PLAY_TIME_SCALE = 8.0
# Marginal warm-weather / big-city recruiting tiebreaks (see ncaa.program_geo_flags).
WARM_APPEAL_WEIGHT = 0.06
CITY_APPEAL_WEIGHT = 0.06


def _intl_tier(division: str, academics: float) -> str:
    # D3 and the academic-first D4 both let only their academically elite reach
    # the higher international pull; ordinary programs in either stay local. D4
    # sits below D3, so its baseline pull is the lowest in the world.
    if division in ("D3", "D4"):
        if academics >= ELITE_D3_ACADEMICS:
            return "D3_elite"
        return division
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
CREATE TABLE IF NOT EXISTS world_jhsaa (
  world_id INTEGER, year INTEGER, gender TEXT, data TEXT
);
CREATE TABLE IF NOT EXISTS world_jhsaa_dual (
  world_id INTEGER, year INTEGER, gender TEXT, school TEXT, opp TEXT,
  home INTEGER, phase TEXT, pf REAL, pa REAL, won INTEGER, district INTEGER,
  lines TEXT DEFAULT '[]',
  level TEXT DEFAULT 'v', tied INTEGER DEFAULT 0, shape TEXT DEFAULT '',
  played TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_dual ON world_jhsaa_dual(world_id, year, gender, school);
-- The INDIVIDUAL state tournaments — one row per completed draw, so a page loads the
-- flight it is showing and nothing else.
--
-- ‼️ ITS OWN TABLE, NOT A KEY ON THE `world_jhsaa` SUMMARY, for the reason the duals
-- table already exists: that summary row is read in FULL by every JHSAA page, and a
-- gender's fifty-four draws are ~1.7 MB of JSON. Carried on the summary, rendering the
-- hub's champion list would deserialise every bracket in the association.
--
-- ‼️ AND NOT A ROW IN `world_jhsaa_dual`. That table's row is a DUAL between two
-- SCHOOLS, with pf/pa and a `lines` box score, and six readers fold it into records,
-- court totals and the research export. An individual match is one court between two
-- PLAYERS; dropped in there it would land on programs' records and court totals the
-- way JV duals did before `level` (see the export AAR) — the same fault, one table over.
--
-- `gender` is 'girls'/'boys' for the six flights and 'mixed' for the summer mixed
-- doubles, which belongs to neither and so is stored as its own thing rather than
-- duplicated onto both.
CREATE TABLE IF NOT EXISTS world_jhsaa_individual (
  world_id INTEGER, year INTEGER, gender TEXT, grp TEXT, flight TEXT, data TEXT
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_indiv
  ON world_jhsaa_individual(world_id, year, gender, grp);
-- INJURIES (owner rule 2026-08, ported off the college model) — one row per injury
-- actually rolled, VARSITY only (JV is deliberately injury-blind, see jhsaa.TeamSeason).
-- Its own table, same reason `world_jhsaa_individual` has one: this is per-PLAYER
-- event data with no home on the per-dual `world_jhsaa_dual` row (an injury is rolled
-- AFTER a dual, for a future one) and no home on the `world_jhsaa` summary either (it
-- would bloat the one blob every JHSAA page reads in full). `dual_index` is the
-- injured player's OWN TEAM's dual count when it happened — an ordinal within their
-- season, not a calendar week; the JHSAA has no clock inside a season.
CREATE TABLE IF NOT EXISTS world_jhsaa_injury (
  world_id INTEGER, year INTEGER, gender TEXT, school TEXT, pid TEXT, name TEXT,
  dual_index INTEGER, duals_out INTEGER DEFAULT 0, season_ending INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_injury
  ON world_jhsaa_injury(world_id, year, gender, school);
CREATE TABLE IF NOT EXISTS world_cups (
  world_id INTEGER, year INTEGER, gender TEXT, data TEXT
);
CREATE TABLE IF NOT EXISTS world_pro (
  world_id INTEGER, year INTEGER, cycle TEXT, gender TEXT, division TEXT,
  school TEXT, pid TEXT, cost REAL
);
CREATE INDEX IF NOT EXISTS idx_wpro ON world_pro(world_id, year, cycle);
-- Durable archive of committed portal MOVES (risers + cascade demotions), written at commit
-- so the Portal Rankings board survives the rollover that clears the transient slate tables.
-- Pros are read from world_pro; this covers the transfer (riser/cascade) side.
CREATE TABLE IF NOT EXISTS world_portal_move (
  world_id INTEGER, year INTEGER, cycle TEXT, gender TEXT, kind TEXT,
  pid TEXT, name TEXT, str REAL,
  src_school TEXT, src_div TEXT, dest_school TEXT, dest_div TEXT
);
CREATE INDEX IF NOT EXISTS idx_wpm ON world_portal_move(world_id, year, gender);
CREATE INDEX IF NOT EXISTS idx_wr ON world_roster(world_id, year);
CREATE INDEX IF NOT EXISTS idx_ws ON world_signing(world_id, year, gender);
CREATE INDEX IF NOT EXISTS idx_wx ON world_crossmatch(world_id, year, gender);
CREATE INDEX IF NOT EXISTS idx_wg ON world_graduates(world_id, year, division, gender);
"""

DIV_RANK = {"D1": 1, "D2": 2, "D3": 3, "D4": 4}   # 1 = highest classification
MAX_CROSS = 3                               # cross-classification duals per team / year
CROSS_GAP_DECAY = 0.10                       # per extra class of distance: how much rarer a cross
                                            # dual gets (adjacent=1, two up=0.10, three up=0.01) —
                                            # so a D4 plays mostly D3, with nearby D2/D1 a thin sliver
CROSS_D1_PRESTIGE = 0.25                     # a D1 only reaches down to a D3/D4 this prestigious
                                            # (a lifted academic peer); else same-region only
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
    # The JV season's three columns (owner rule 2026-08). `level` is the one that
    # matters: it is the ONLY thing separating a JV row from a varsity one, since both
    # carry an empty `lines` — JV by design (no per-court detail is archived) and
    # varsity on any dual whose lines failed to record. Defaulting to 'v' is what makes
    # every row written before this migration read correctly as varsity.
    # `played` is the JV participation record — the names that dressed, so a player
    # page can say "played JV, 8-3". It is deliberately NOT part of `lines`: see
    # `jhsaa.play_jv_dual`. A season archived before it reads back as '[]', which is
    # honestly "we did not record who played", not "nobody played".
    for col, typ in (("level", "TEXT DEFAULT 'v'"), ("tied", "INTEGER DEFAULT 0"),
                     ("shape", "TEXT DEFAULT ''"), ("played", "TEXT DEFAULT '[]'")):
        try:
            conn.execute(f"ALTER TABLE world_jhsaa_dual ADD COLUMN {col} {typ}")
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


def _retry_locked(fn, *, tries: int = 6, delay: float = 0.3):
    """Run a DB op, retrying on a transient 'database is locked'. The connection's
    busy_timeout already WAITS on normal contention; this backstops the rare case
    where a lock outlasts it (e.g. a sibling write under heavy suite load) so a
    one-off contention blip can't 500 the world advance. Re-raises anything else."""
    import time
    for attempt in range(tries):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower() or attempt == tries - 1:
                raise
            time.sleep(delay * (attempt + 1))


def _save_rosters(conn, world_id, year, rosters) -> None:
    conn.execute("DELETE FROM world_roster WHERE world_id=? AND year=?", (world_id, year))
    rows = [(world_id, year, d, g, school, p.pid, json.dumps(prospect_to_dict(p)))
            for (d, g), schools in rosters.items()
            for school, roster in schools.items() for p in roster]
    conn.executemany("INSERT INTO world_roster VALUES (?,?,?,?,?,?,?)", rows)


def _save_graduates(conn, world_id, year, rosters, player_str: dict | None = None,
                    redshirts: set | None = None) -> int:
    """Persist the authoritative graduating cohort before ``graduate`` drops it.
    A senior taking a medical redshirt (`redshirts`) is NOT graduating — they
    return next year as RS-Sr — so exclude them here."""
    conn.execute("DELETE FROM world_graduates WHERE world_id=? AND year=?", (world_id, year))
    rows = []
    player_str = player_str or {}
    redshirts = redshirts or set()
    for (d, g), schools in rosters.items():
        if not worldconfig.is_active(d, g):
            continue
        for roster in schools.values():
            for p in roster:
                # Everyone DEPARTING enters the graduate pool — seniors and pro
                # grad transfers alike (an ex-pro continues into the GTT via the
                # draft's Pro Round; owner call 2027-07). Redshirts stay.
                if not _departing(p) or p.pid in redshirts:
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


# Year-0 build runs one universe per worker; each holds a full universe (~3.5k rich
# prospects) in RAM, so cap concurrency to bound the memory peak (the old serial
# build deliberately capped at ONE universe to avoid OOM). 4 is a safe ceiling on a
# 4–8 GB machine; raise alongside RAM. Override with GEN_WORKERS for ops/tests.
_BUILD_WORKER_CAP = 4


def _build_universe(args):
    """Process-pool worker (top-level so it's importable under spawn): build one
    universe's year-0 rosters for `salt` and return them SERIALIZED (picklable
    dicts). Deterministic from the salt + config, so the result is byte-identical
    to building the universe inline in the parent. `cfg` is the parent's worldconfig
    snapshot, primed directly so the child never depends on the DB being readable."""
    salt, cfg, division, gender = args
    from app import worldconfig
    worldconfig.prime_cache(cfg)
    ncaa.WORLD_SALT = salt
    reset_caches()
    uni = _seed_year0(division, gender)
    return (division, gender,
            {school: [prospect_to_dict(p) for p in roster]
             for school, roster in uni.items()})


def get_or_create(seed: int = DEFAULT_SEED, salt: str | None = None,
                  skip_college: bool = False) -> dict:
    """`skip_college=True` inserts a legitimate world row (every reader that does
    `SELECT * FROM world WHERE seed=?` keeps working unmodified) but skips building
    the college universes entirely — for a JHSAA-only "lab" world used to run
    standalone high-school seasons for analysis (`scripts/jhsaa_lab.py`). Never
    pass this from an ordinary call site: a save with no college rosters is not a
    real league. Lab worlds are expected to live in their OWN scratch database
    (via `TENNIS_DB_PATH`), never the real save's — see
    `docs/PLAN-jhsaa-standalone-lab-mode.md`."""
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
    conn.execute("DELETE FROM world_roster WHERE world_id=? AND year=?", (wid, 0))
    conn.commit()                  # make the world row visible to child processes
    reset_caches()
    if skip_college:
        row = conn.execute("SELECT * FROM world WHERE id=?", (wid,)).fetchone()
        conn.close()
        return dict(row)
    # Seed year-0 rosters for all universes IN PARALLEL — each is independent and
    # deterministic from the salt, so child processes rebuild them byte-identically
    # (serial fallback inside pmap if no pool). Worker count is capped: each holds a
    # full universe in RAM, so this trades a higher memory peak for wall-clock. See
    # docs/AAR-parallel-generation.md.
    from app.parallel import pmap, workers_for
    from app import worldconfig
    cfg = worldconfig.snapshot()
    tasks = [(salt, cfg, d, g) for (d, g) in UNIVERSES]
    for (d, g, uni) in pmap(_build_universe, tasks,
                            workers=workers_for(len(tasks), cap=_BUILD_WORKER_CAP)):
        rows = [(wid, 0, d, g, school, p["pid"], json.dumps(p))
                for school, roster in uni.items() for p in roster]
        conn.executemany("INSERT INTO world_roster VALUES (?,?,?,?,?,?,?)", rows)
        del uni, rows
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
        "DELETE FROM world_graduates; DELETE FROM world_pro; "
        "DELETE FROM world_portal_move; "
        "DELETE FROM world_roster; DELETE FROM world;"
    )
    conn.commit()
    conn.close()
    # Season-mode schedule/results live in their own tables — clear them too.
    # `injuries` is keyed by season_id, and seasons.id is a reused INTEGER PRIMARY
    # KEY, so leftover rows would attach to a new save's freshly-numbered seasons —
    # wipe them with the seasons that own them.
    sconn = sm._db()
    sconn.executescript("DELETE FROM duals; DELETE FROM seasons; DELETE FROM injuries;")
    sconn.commit()
    sconn.close()
    # Career honors + coach identities are season-to-season state too.
    import app.honors as honors
    import app.coachreg as coachreg
    honors.reset()
    coachreg.reset()
    # The GTT pro tour is a CONTINUATION of the college world (its founders are
    # this save's graduates; a league binds to the active world's seed). A new
    # save replaces that world, orphaning its old pro leagues — so wipe them, or
    # the League Hub keeps listing prior saves full of now-stale pros.
    import app.gtt_seasonmode as gtt
    gtt.reset()
    # The pro-offseason step's per-save marker goes with those leagues. `reset()`
    # drops the GTT tables but NOT world_setting (or worldconfig's in-memory cache),
    # so a stale "pros_rolled_year" would still read as done for the SAME year number
    # in the next save — the new league's first rollover also lands on year 1 — and
    # its first graduating class would never be drafted. Clear the value AND the memo.
    worldconfig.set("pros_rolled_year", "")
    # The JHSAA name-era cutover is per-save the same way: this reset deletes the
    # world_jhsaa archive below but keeps world_setting, so a stale
    # "jhsaa_name_era" would carry the PRIOR league's cutoff (a calendar year)
    # into the new one and hold its opening cohorts on legacy names for seasons.
    # Clear the value AND the memo (`_name_era_cache` clears with the school
    # caches in `reset_schools`).
    worldconfig.set("jhsaa_name_era", "")
    # The development-era cutover (`jhsaa.dev_era`) is the same idiom with the
    # same failure mode: left behind, a prior save's cutoff would hold the new
    # save's opening cohorts on the legacy lockstep maturity bands for years.
    worldconfig.set("jhsaa_dev_era", "")
    from . import jhsaa as _jhsaa
    _jhsaa.reset_schools()
    # Stored individual championships AND the national-team cups (Davis / BJK) are
    # off-season snapshots keyed by world_id — and SQLite REUSES world_id=1 after
    # this reset drops the world row, so the next save's get_or_create() lands on
    # the same id. Left behind, latest_championship / latest_world_cup would serve
    # the PRIOR league's champions and cup squads (stale players) under the new
    # save. Clear both so each new league starts empty.
    conn = _db()
    conn.executescript("DELETE FROM world_championship; DELETE FROM world_cups;"
                       " DELETE FROM world_jhsaa; DELETE FROM world_jhsaa_dual;"
                       " DELETE FROM world_jhsaa_individual; DELETE FROM world_jhsaa_injury;")
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


def start_new(seed: int = DEFAULT_SEED, salt: str | None = None,
              skip_college: bool = False) -> dict:
    """Reset and create a brand-new league at preseason (week 0, nothing
    played). The onboarding 'Start new league' action. A fresh random salt
    (unless one is supplied, e.g. for tests) means the new league's rosters and
    recruits differ from every previous save. `skip_college` — see
    `get_or_create` — is for JHSAA-only lab worlds only."""
    reset(seed)
    return get_or_create(seed, salt=salt, skip_college=skip_college)


def get_or_create_jhsaa_only(seed: int = DEFAULT_SEED, salt: str | None = None) -> dict:
    """A world row with NO college universes built — just enough for
    `run_jhsaa`/the JHSAA archive tables to work, at a fraction of the cost of a
    real league. Thin wrapper so `skip_college=True` never appears at an
    ordinary call site by accident. Intended ONLY against a scratch database
    dedicated to lab runs (`scripts/jhsaa_lab.py`), never the real save — see
    `docs/PLAN-jhsaa-standalone-lab-mode.md`."""
    return get_or_create(seed, salt=salt, skip_college=True)


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


def signings(seed: int = DEFAULT_SEED, year: int | None = None) -> dict:
    """{gender: {school: [Prospect, ...]}} for the class signed in `year` (default:
    the current world-year — the live commitments the Signing Tracker reads, filling
    as the season advances). `world_signing` rows are never deleted at the rollover,
    so any PAST year returns that season's class exactly as it signed — the
    recruiting-class archive."""
    w = load_world(seed)
    if not w:
        return {}
    conn = _db()
    try:
        return _load_signings(conn, w, year=year)
    finally:
        conn.close()


def signing_years(seed: int = DEFAULT_SEED) -> list[int]:
    """World-years with at least one signing on record, newest first — the
    Signing Tracker's season picker (current cycle + every archived class)."""
    w = load_world(seed)
    if not w:
        return []
    conn = _db()
    try:
        return [r["year"] for r in conn.execute(
            "SELECT DISTINCT year FROM world_signing WHERE world_id=?"
            " ORDER BY year DESC", (w["id"],)).fetchall()]
    finally:
        conn.close()


def persisted_team(pid: str, seed: int = DEFAULT_SEED):
    """(school, division) the player STARTED this year at — their persisted
    world_roster slot, before any in-season editor/portal move override. Lets the
    player card show a mid-season transfer (current school != where they started)
    before the year-end history records it. Returns (None, None) if not found."""
    w = load_world(seed)
    if not w:
        return (None, None)
    conn = _db()
    try:
        r = conn.execute("SELECT school, division FROM world_roster"
                         " WHERE world_id=? AND pid=? ORDER BY year DESC LIMIT 1",
                         (w["id"], pid)).fetchone()
        return (r["school"], r["division"]) if r else (None, None)
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


def is_graduate(pid: str, seed: int = DEFAULT_SEED) -> bool:
    """Whether ``pid`` is in this world's authoritative graduate archive.

    Persisted rosters include active players and therefore are not evidence that
    a person is eligible to start a coaching career.
    """
    w = load_world(seed)
    if not w:
        return False
    conn = _db()
    try:
        return conn.execute("SELECT 1 FROM world_graduates WHERE world_id=? AND pid=? LIMIT 1",
                            (w["id"], pid)).fetchone() is not None
    finally:
        conn.close()


# ==========================================================================
# Rosters as-of the current week: year-start rosters + a development replay.
# ==========================================================================
_base_cache: dict = {}      # (world_id, year) -> year-start rosters
_dev_cache: dict = {}       # (world_id, year, week) -> developed rosters
_primed: dict = {}          # seed -> (world_id, year, week, move_version) in ncaa cache
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
    # Coach development multiplier: the program's head coach scales every player's
    # growth (±30% across the 20-80 development_score band — see
    # coaches.development_multiplier). Same coach source the recruiting sim reads.
    from app.coaches import development_multiplier
    dm_of = {school: development_multiplier(school)
             for schools in rosters.values() for school in schools}
    for wk in range(world["week"]):
        for schools in rosters.values():
            for school, roster in schools.items():
                dm = dm_of[school]
                for p in roster:
                    s = stagger_scale(p.pid, wk, DEV_WEEKS)
                    if s:
                        p.develop(s * dm)
    _dev_cache[key] = rosters
    return rosters


def scan_rosters(seed: int = DEFAULT_SEED) -> dict:
    """Live rosters for EVERY division×gender, built the exact way the Analytics
    Bureau boards are (scout_intel.scan): prime the world, then read `build_roster`
    for every program across all divisions. Unlike `developed_rosters` this is NOT
    limited to the ACTIVE universes — dormant divisions build fresh on a cache miss —
    so a cross-division consumer (the pre-season portal) scans the same universe the
    Underplaced/Playing-Time boards show, never only the active persisted subset."""
    prime(seed)
    from app.ncaa import load_division, build_roster
    out: dict = {}
    for (division, gender) in UNIVERSES:
        try:
            div = load_division(division, gender)
        except FileNotFoundError:
            continue
        out[(division, gender)] = {p.school: build_roster(p) for p in div.programs}
    return out


def prime(seed: int = DEFAULT_SEED) -> dict:
    """Load this world's as-of-now rosters into the shared roster cache so every
    consumer — season mode, run_season rankings, team pages, box scores — sees
    the same evolving players. The one-world hinge."""
    from app import overrides as ov
    w = get_or_create(seed)
    # Fold TRANSFERS (composition changes) into the stamp so a roster mutation
    # that does not advance the week — a fall-portal / preseason-portal commit or
    # an editor move, all of which land as `move` rows — still forces a rebuild.
    # Use `move_version()`, NOT `roster_version()`: the latter also folds in
    # lineup/doubles pins, which only reorder who plays (applied live in
    # build_roster/coach_lineup) and never change the developed roster SET this
    # cache holds. Keying prime on pins made every lineup save trigger a full
    # ~170MB world re-prime on the next page's request thread — a GIL stall that
    # starved /api/health and timed the client out with [Errno 110].
    # See docs/AAR-cache-invalidation-scope-lineup-stall.md.
    stamp = (w["id"], w["year"], w["week"], ov.move_version())
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


def is_primed(seed: int = DEFAULT_SEED) -> bool:
    """True when this world's rosters are already warm for the current
    (year, week, roster-override) stamp — i.e. prime() would be an instant no-op.
    Read-only and cheap (no get_or_create, no roster build): the web layer uses it
    to decide between serving content and showing a loader while a cold prime warms
    in the background, so a slow prime never blocks a request — or the health check."""
    from app import overrides as ov
    if not exists(seed):
        return False
    w = load_world(seed)
    stamp = (w["id"], w["year"], w["week"], ov.move_version())   # MUST match prime()'s stamp
    return _primed.get(seed) == stamp and bool(_roster_cache)


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


# --------------------------------------------------------------------------
# Universe sync — one world, one clock.
#
# Every active universe advances together under `advance_week`; nothing else may
# step one on its own. When something does (the Season Hub's per-universe advance
# used to), the save silently desyncs: the world clock and the untouched universes
# stay put while one runs ahead, so the rankings compare a men's team 25 duals into
# its year against a women's team that has played 12 and barely opened conference
# play. The numbers are all "correct" for their own universe — they're just from
# different weeks. See docs/AAR-universe-desync-season-hub-advance.md.
# --------------------------------------------------------------------------

def pros_rolled(world: dict) -> bool:
    """True once the pro league's off-season has been rolled for the class that just
    graduated into it (i.e. for the world year we rolled OUT of)."""
    return worldconfig.get("pros_rolled_year") == str(world["year"])


def run_pro_offseason(seed: int = DEFAULT_SEED, world: dict | None = None) -> dict:
    """The pro-league step: roll the off-season of every completed GTT league so it
    drafts the college class that just graduated. Its own visible step at week 0 of
    the new year rather than a silent tail of the college rollover.

    This only ever READS college state — the graduates table written by the rollover.
    Nothing here writes a college roster, season or dual; running it cannot disturb
    the college world."""
    w = world or get_or_create(seed)
    from app import gtt_seasonmode as _gtt
    rolled = _gtt.on_world_rollover()
    worldconfig.set("pros_rolled_year", str(w["year"]))
    return {"event": "pro_offseason", "year": 2026 + w["year"], "leagues_rolled": rolled}


def universe_progress(seed: int = DEFAULT_SEED) -> list[dict]:
    """Each active universe with its position in the season year (`key`, from
    `sm.season_progress`). In a healthy save every key is identical."""
    w = get_or_create(seed)
    out = []
    for (d, g) in _active_unis():
        sid = universe_sid(seed, w, d, g)
        s = sm.load_season(sid)
        out.append({"division": d, "gender": g, "sid": sid, "phase": s["phase"],
                    "week": s["current_week"], "total": s["total_weeks"],
                    "key": sm.season_progress(sid)})
    return out


def universes_in_sync(seed: int = DEFAULT_SEED) -> bool:
    """True when every active universe sits at the same point in the year."""
    return len({u["key"] for u in universe_progress(seed)}) <= 1


def resync_universes(seed: int = DEFAULT_SEED, max_steps: int = 500) -> dict:
    """Repair a desynced save: step every lagging universe forward until it stands
    level with the furthest-along one. The world clock is NOT touched — the leader
    already consumed those weeks; this only plays the duals the laggards owe.

    A universe holding at the `fall_portal` barrier is left alone (only the world
    driver may release it — `sm.advance` would pass it straight through and skip
    the portal), so a save stuck there is reported rather than forced."""
    prime(seed)
    steps = 0
    stepped: dict = {}
    blocked: list[str] = []
    while steps < max_steps:
        unis = universe_progress(seed)
        lead = max((u["key"] for u in unis), default=None)
        behind = [u for u in unis if u["key"] < lead]
        if not behind:
            break
        progressed = False
        for u in behind:
            if u["phase"] == "fall_portal":
                blocked.append(f"{u['division']} {u['gender']}")
                continue
            sm.advance(u["sid"])
            key = f"{u['division']} {u['gender']}"
            stepped[key] = stepped.get(key, 0) + 1
            steps += 1
            progressed = True
        if not progressed:
            break                     # only fall_portal holds left — nothing we may do
    _primed.pop(seed, None)
    return {"steps": steps, "stepped": stepped,
            "blocked": sorted(set(blocked)), "in_sync": universes_in_sync(seed)}


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
    "women"/"female" (and "men"/"male") resolve to the SAME class. pids and
    identities are identical to what the sim signs from.

    NOTE: this builds only the class + national/star ranking (`rank_class`), which
    is ALL the simulation's signing logic needs. The junior circuit — a full season
    simulated over the whole RECRUIT_POOL (~2,500/gender), the single most expensive
    compute in the app — is NOT run here. It is purely board enrichment and is
    deferred to `board_class()`, so advancing the world (the hot path) never pays for
    it. See AAR-junior-circuit-lazy-board-enrichment."""
    gender = _GENDER_CANON.get(gender, gender)
    key = (salt, gender, grad_year)
    if key not in _class_cache:
        rng = random.Random(f"{salt}|recruits|{gender}|{grad_year}")
        klass = generate_class(rng, n=RECRUIT_POOL, grad_year=grad_year,
                               gender=gender, talent_mean=_recruit_talent_mean(gender),
                               talent_sd=RECRUIT_TALENT_SD, intl_share=worldconfig.intl_share(),
                               intl_weights=worldconfig.region_weights())
        # Jefferson's slots are not invented: swap in the JHSAA seniors who just
        # graduated, carrying their real high-school records. Identity and ability
        # only — the slot count still comes from the origin weight, and the pids are
        # preserved. Silent no-op if the JHSAA data isn't present.
        try:
            from . import jhsaa
            jhsaa.apply_to_class(klass, gender, grad_year, salt)
        except (OSError, ValueError, KeyError):
            pass
        rank_class(klass)                          # national rank + star ladder
        _class_cache[key] = klass
    return _class_cache[key]


# The junior circuit is simulated over the RECRUITED CADRE — the top of the pool
# by the service's talent read. The walk-on tail sits below every funding floor and
# signs as a walk-on regardless, so it needs no junior résumé; capping the field
# keeps the (expensive) circuit's worst case bounded. Raise for more tail fidelity
# at a roughly linear cost. See docs/AAR-fog-of-war-recruiting.md.
CIRCUIT_FIELD = 1500


def board_class(gender: str, grad_year: int, salt: str):
    """The recruiting class ENRICHED with the junior circuit — the performance
    record the AI's perceived caliber reads at signing AND what the web board /
    recruit pages render. Same cached object `recruit_class` returns, run once
    through the (expensive) junior-circuit simulation over the recruited cadre and
    frozen in place (idempotent via `klass.circuit_done`), so repeat calls are free."""
    klass = recruit_class(gender, grad_year, salt)
    if not getattr(klass, "circuit_done", False):
        from app.junior_circuit import run_junior_circuit
        from app.juniors import (points_rankings, tenniseye_rankings, rank_class,
                                 _recruiting_score, RecruitClass)
        # Field = the recruited cadre (top by the service's talent read); the
        # objects are shared, so the circuit freezes its résumé onto the real
        # prospects. The tail keeps junior defaults (perf_caliber → 0).
        field = sorted(klass.recruits, key=_recruiting_score, reverse=True)[:CIRCUIT_FIELD]
        sub = RecruitClass(grad_year=klass.grad_year, gender=klass.gender, recruits=field)
        run_junior_circuit(sub, seed=salt)         # junior results/STR for the cadre
        # `_recruiting_score` reads junior_str/junior_str_reliability (current
        # ability + results — docs/DESIGN-recruit-rating-clarity.md), which the
        # circuit just populated for the cadre. `recruit_class`'s rank_class() ran
        # BEFORE the circuit (current-ability-only — no junior record existed yet),
        # so recruit_rank/recruit_tier/recruit_stars are stale until re-run here —
        # matching the re-rank `prime_recruit_classes`'s parallel path already does
        # after its own circuit call. Without this, direct board_class() consumers
        # (recruiting_hub, recruit profile pages) show pre-circuit ranks while
        # national_class()'s extra rank_class() wrap and the parallel path both show
        # correct post-circuit ones — three paths, two different answers.
        rank_class(klass)                          # re-rank the FULL pool, now with results
        points_rankings(klass)                     # rank the FULL pool; tail = 0 points
        tenniseye_rankings(klass)                  # results-based TennisEye star rating
        klass.circuit_done = True
    return klass


def _build_board_class(args):
    """Process-pool worker: build one gender's ENRICHED recruit class (the
    expensive junior circuit) for `salt` and return its prospects SERIALIZED.
    Deterministic from salt + config, so identical to building it inline."""
    salt, cfg, gender, grad_year = args
    from app import worldconfig
    worldconfig.prime_cache(cfg)
    ncaa.WORLD_SALT = salt
    klass = board_class(gender, grad_year, salt)
    return (klass.gender, klass.grad_year,
            [prospect_to_dict(p) for p in klass.recruits])


def prime_recruit_classes(seed: int = DEFAULT_SEED, year: int | None = None) -> None:
    """Precompute the active genders' enriched recruit classes — the junior circuit,
    the single most expensive step of an advance — IN PARALLEL, and populate the
    class cache so the per-gender signing that follows is a cache hit (men's and
    women's circuits run at the same time instead of back to back).

    Best-effort: only engages a pool when there are 2+ uncached classes AND 2+
    cores; otherwise it's a no-op and the classes build lazily during signing
    exactly as before. The reconstructed class is re-ranked (`rank_class`, which
    `recruit_class` runs too) so stars/rank are byte-identical to the serial build;
    the circuit's junior fields round-trip losslessly. See docs/AAR-parallel-generation.md."""
    from app.juniors import RecruitClass, rank_class as _rank
    from app.parallel import workers_for
    salt = active_salt(seed)
    if year is None:
        w = load_world(seed)
        year = w["year"] if w else 0
    grad_year = BASE_YEAR + year + 1
    genders, seen = [], set()
    for (_d, g) in _active_unis():
        gc = _GENDER_CANON.get(g, g)
        if gc in seen:
            continue
        seen.add(gc)
        if not getattr(_class_cache.get((salt, gc, grad_year)), "circuit_done", False):
            genders.append(gc)
    if len(genders) < 2 or workers_for(len(genders)) < 2:
        return                                  # nothing to parallelize — let signing build them
    from app.parallel import pmap
    from app import worldconfig
    cfg = worldconfig.snapshot()
    tasks = [(salt, cfg, g, grad_year) for g in genders]
    for (g, gy, dicts) in pmap(_build_board_class, tasks, workers=workers_for(len(tasks))):
        klass = RecruitClass(grad_year=gy, gender=g,
                             recruits=[prospect_from_dict(d) for d in dicts])
        _rank(klass)                            # match serial recruit_class's ranking exactly
        klass.circuit_done = True
        _class_cache[(salt, g, gy)] = klass


def warm_caches(seed: int = DEFAULT_SEED) -> None:
    """Build the expensive caches up front, for a boot-time warm off the request
    path: the as-of-now roster cache (`prime`) and every active gender's ENRICHED
    recruit board (the junior circuit). `prime_recruit_classes` takes the multi-core
    fast path; the `board_class` loop then guarantees each class is actually built
    even when the pool can't engage (single core, one active gender, GEN_WORKERS=1),
    since `prime_recruit_classes` deliberately no-ops in that case. Best-effort and
    idempotent — every step is a cache hit if already warm."""
    if not exists(seed):
        return
    salt = active_salt(seed)
    w = get_or_create(seed)
    prime(seed)                                   # roster cache (~170MB)
    prime_recruit_classes(seed, w["year"])        # parallel recruit prime (no-op if it can't parallelize)
    grad_year = BASE_YEAR + w["year"] + 1
    seen: set[str] = set()
    for (_d, g) in _active_unis():
        gc = _GENDER_CANON.get(g, g)
        if gc in seen:
            continue
        seen.add(gc)
        board_class(gc, grad_year, salt)          # ensure built (covers the serial path)


def national_class(seed: int, year: int, gender: str) -> list:
    """The sim's signing pool for a world-year: the canonical class ranked by the
    service's star signal. Uses `board_class` (not `recruit_class`) because the AI
    now signs on PERCEIVED caliber — a blend of the star projection and junior
    PERFORMANCE — so the junior circuit must be run before signing. grad_year =
    BASE_YEAR + year + 1."""
    return rank_class(board_class(gender, BASE_YEAR + year + 1, active_salt(seed)))


def _flat_programs(gender: str) -> dict[str, Program]:
    out = {}
    for division in ("D1", "D2", "D3", "D4"):
        try:
            for p in load_division(division, gender).programs:
                out[p.school] = p
        except FileNotFoundError:
            continue
    return out


def _openings(base_rosters: dict, gender: str) -> dict[str, int]:
    """Projected freshman seats per program for next year.

    D2–D4: seniors graduating (rosters are otherwise full).

    D1 signs into its SCHOLARSHIP CORE ONLY — a class tops the core back up to
    `SCHOLARSHIP_SLOTS` (6) and stops. A D1 program NEVER recruits a walk-on seat:
    with the transfer portal there's no reason to burn a signing on depth, so those
    seats backfill from the portal or sit open. This frees D1 seats, cascades better
    players down a level, and keeps the portal dynamic (owner rule, 2026-07)."""
    out = {}
    for (division, g), schools in base_rosters.items():
        if g != gender:
            continue
        for school, roster in schools.items():
            # Departures include pro grad transfers ("Gr") and legacy pros —
            # a program hosting a pro MUST recruit the replacement seat now,
            # or the roster (and the D1 scholarship core) runs short next year.
            grads = sum(1 for p in roster if _departing(p))
            if division == "D1":
                returning = len(roster) - grads
                ret_core = sum(1 for p in roster if not p.walk_on
                               and not _departing(p))
                out[school] = max(0, min(SCHOLARSHIP_SLOTS - ret_core,
                                         roster_cap(division) - returning))
            else:
                out[school] = grads
    return out


def _recruit_market(world: dict, gender: str) -> dict:
    """Precomputed program tables a recruit consults to pick a school —
    prestige-sorted window, top-academic set, region buckets, and per-school
    seat capacity. Shared by the weekly drip and the decommit pass."""
    from . import recruit_economy
    progs = _flat_programs(gender)
    traits = {s: (p.prestige, p.academics, p.region, p.division, p.facilities)
              for s, p in progs.items()}
    salt = world.get("salt") or ""
    # ONE budget: pros are paid out of the same pool as the class, so a program's recruiting
    # power is its budget MINUS what it already spent on pros this year.
    _c = _db()
    _spent = _pro_spend(_c, world["id"], world["year"], gender)
    _c.close()
    budget = {s: max(0.0, recruit_economy.program_budget(p, salt, world["year"]) - _spent.get(s, 0.0))
              for s, p in progs.items()}
    # Each program's OWN level on the recruit-caliber scale (talent mean → caliber),
    # feeding the division radar: a program only pursues recruits near its level
    # mid-cycle, so the class tiers itself (see recruit_economy.program_level_floor).
    # STRENGTH, not prestige: rosters are generated from p.strength (ncaa._talent_mean),
    # so strength is the level the lineup actually plays at — a strong low-brand
    # program holds to its real level, not its recruiting brand.
    from .ncaa import program_level_caliber
    level_cal = {s: program_level_caliber(p.strength, p.division, gender)
                 for s, p in progs.items()}
    # D4's per-program admissions gate: the minimum recruit test score each D4 program
    # will admit (academic-first tier — see recruit_economy.d4_academic_min).
    d4_min = {s: recruit_economy.d4_academic_min(p, world["year"], salt)
              for s, p in progs.items() if p.division == "D4"}
    br = _base_rosters(world)
    cap = _openings(br, gender)
    # Playing-time signal: each program's current returning roster OVRs (best→worst)
    # plus its division's lineup size, so a recruit can see whether their OVR would
    # crack the program's actual starting card (see _pick_school). Lineups are
    # per-division now (D1/D4 field 10 singles, D2/D3 eight — ncaa.lineup_size).
    roster_ovrs: dict[str, tuple] = {}
    for (division, g), schools in br.items():
        if g != gender:
            continue
        _lu = lineup_size(division)
        for school, roster in schools.items():
            roster_ovrs[school] = (sorted(
                (pl.current_overall() for pl in roster if not _departing(pl)),
                reverse=True), _lu)
    # Warm-state / big-city recruiting-appeal flags per program (marginal tiebreak).
    from .ncaa import program_geo_flags
    geo_flags = {s: program_geo_flags(p) for s, p in progs.items()}
    from . import coaches
    coachmap = {s: coaches.program_coach(s) for s in progs}        # per-program coach (localism, sourcing tilt, origin pipeline)
    by_pres = sorted(progs, key=lambda s: traits[s][0])
    pres_arr = [traits[s][0] for s in by_pres]
    academic_top = sorted(progs, key=lambda s: -traits[s][1])[:40]
    by_region: dict[str, list] = {}
    for s in progs:
        by_region.setdefault(traits[s][2], []).append(s)
    # Island/remote-state home pull: {school -> (state/terr abbr, share)} for the
    # programs present, plus a reverse {abbr -> [schools]} so a local recruit's own
    # territory schools are always in reach (they'd otherwise fall outside the
    # prestige window).
    from .ncaa import SCHOOL_LOCAL_TERRITORY
    local_terr = {s: SCHOOL_LOCAL_TERRITORY[s] for s in progs if s in SCHOOL_LOCAL_TERRITORY}
    local_by_abbr: dict[str, list] = {}
    for s, (abbr, _share) in local_terr.items():
        local_by_abbr.setdefault(abbr, []).append(s)
    return {"progs": progs, "traits": traits, "cap": cap, "budget": budget, "coaches": coachmap,
            "level_cal": level_cal, "d4_min": d4_min, "roster_ovrs": roster_ovrs,
            "geo_flags": geo_flags,
            "by_pres": by_pres, "pres_arr": pres_arr, "academic_top": academic_top,
            "by_region": by_region, "local_terr": local_terr, "local_by_abbr": local_by_abbr}


def _pick_school(p, market: dict, avail: dict, *, jitter_salt: str,
                 exclude: set | None = None, progress: float = 1.0) -> str | None:
    """Score every plausible program for prospect `p` and return the best one
    with an open seat. `exclude` blocks specific schools (used for decommits).
    `progress` (0→1 across the signing window) drives the program-side caliber
    standard: funded programs hold premium seats for elite talent early, relaxing
    as signing day nears — so blue-chips aren't crowded out by 3★s rushing in."""
    from .recruiting import ELITE_CALIBER, FOUR_STAR
    from . import recruit_economy
    traits = market["traits"]
    budget = market.get("budget", {})
    level_cal = market.get("level_cal", {})
    d4_min = market.get("d4_min", {})
    roster_ovrs = market.get("roster_ovrs", {})
    geo_flags = market.get("geo_flags", {})
    coachmap = market.get("coaches", {})
    p_academic = int(getattr(p, "academic_rating", 79) or 79)
    recruit_ovr = p.current_overall()                 # the recruit's own read of where they'd slot
    from .recruiting import recruit_geo_prefs
    pref_warm, pref_city = recruit_geo_prefs(p)
    by_pres, pres_arr = market["by_pres"], market["pres_arr"]
    # FOG OF WAR: the AI never sees true ability here. `cal` is the recruit's own
    # market-consensus sense of their level (balanced stars-vs-results), driving
    # who they aspire to; each PROGRAM re-reads them through its own philosophy
    # below. recruit_caliber (the truth) is owner-only. See AAR-fog-of-war-recruiting.
    cal, ac = consensus_caliber(p), recruit_academic01(p)
    # DIVISION RADAR (current-ability side): what a program SEES. `cur_cal` is the
    # recruit's CURRENT ability (public STR, on the caliber scale) — what they ARE
    # right now, not the projection. A program only has a sub-level recruit on its
    # radar once the cycle's late enough (the level floor ramps open); so a sub-D1
    # kid can still DREAM of D1 (their `cal`-driven aspiration above is untouched)
    # but never lands on a D1's board mid-cycle, and slots to their level instead of
    # flooding the powers. On signing day D1 programs with open seats sop up the best
    # leftovers. Using CURRENT ability here (not the ceiling projection) is the point:
    # a raw kid with a huge hidden ceiling still slots to their level.
    cur_cal = max(0.0, min(1.0, (p.current_overall() - 20) / 60.0))
    budget_floor = recruit_economy.recruit_budget_floor(cal)   # perceived elites only chase funded programs
    # Division ceiling by tier: a 5★/blue-chip never drops to D3/D4; a 4★ can choose an
    # academic-elite D3/D4 (an Ivy-calibre classroom is worth the athletic step down) but
    # otherwise only rarely; a 3★ (and below) can go anywhere.
    # The D3/D4 gate weighs current ability and the projection EVENLY — the
    # non-scholarship tier's own philosophy (they'll take a project whose game is
    # at their level today, whatever the service projects him to become), while a
    # kid who's genuinely elite RIGHT NOW never drops there.
    d34_cal = (cal + cur_cal) / 2.0

    def _div_ok(div, acad):
        if div not in ("D3", "D4"):
            return True
        if d34_cal >= ELITE_CALIBER:                     # currently-elite: never drops to D3/D4
            return False
        if d34_cal >= FOUR_STAR:                         # 4★-level: open at academic-elite D3/D4
            if acad >= ELITE_D3_ACADEMICS:
                return True
            return random.Random(f"{getattr(p, 'pid', '')}|d3gate").random() < 0.05
        return True
    hr = home_region(p)
    hc = float(getattr(p, "homecooking", 0.0))
    intl = not getattr(p, "domestic", False)
    # Window: from a bit below their level up to well above it, so a recruit will
    # reach UP to a strong program that has an opening (a chance to play for a
    # major beats being a star at a much smaller school) — the upside isn't capped.
    # The FLOOR keys on current ability, not the projection: however high a kid
    # aspires (hi is still `cal`-driven — the D1 dream is intact), the programs at
    # the level he plays TODAY always have him in view and compete for him. Without
    # this a hyped project's window floats above D3/D4 all season and the bottom
    # divisions see nobody until signing day.
    lo = bisect.bisect_left(pres_arr, min(cal, cur_cal) - 0.30)
    hi = bisect.bisect_left(pres_arr, cal + 0.55)
    cands = set(by_pres[lo:hi]) | set(market["academic_top"])
    if hc > 0.0 and not intl:
        cands |= set(market["by_region"].get(hr, ()))
    # Home-territory tug (PR/USVI/Guam/remote-state): a local kid's own island/state
    # schools are always in reach, even if they sit outside the prestige window.
    local_terr = market.get("local_terr", {})
    home_abbr = ""
    if not intl:
        _ht = getattr(p, "hometown", "") or ""
        home_abbr = _ht.rsplit(", ", 1)[-1].strip() if ", " in _ht else ""
        if home_abbr:
            cands |= set(market.get("local_by_abbr", {}).get(home_abbr, ()))
    # Citizenship gate: a service academy takes US citizens only, so an international
    # recruit is never on their board — in any window, and not on signing day either
    # (the relax pass below honors `exclude`). See ncaa.SERVICE_ACADEMIES.
    blocked = blocked_schools_for(p)
    if blocked:
        exclude = (exclude | blocked) if exclude else blocked
    if exclude:
        cands -= exclude
    best, best_score = None, -1.0
    jit = random.Random(f"{p.pid}|{jitter_salt}").uniform(-0.05, 0.05)
    for s in cands:
        if avail.get(s, 0) <= 0:
            continue
        pres, acad, reg, div, fac = traits[s]
        if not _div_ok(div, acad):                    # tier-gated out of this division
            continue
        if div == "D4" and p_academic < d4_min.get(s, 0.0):
            continue                                  # below this D4 program's admissions gate
        if budget.get(s, 0.0) < budget_floor:         # program can't fund a recruit this good
            continue
        coach = coachmap.get(s)
        # Division radar: a recruit playing below this program's level simply isn't
        # in its view yet (the floor ramps open late — see program_level_floor). D2
        # reaches much lower (aggressive absorption), so it's division-aware.
        if cur_cal < recruit_economy.program_level_floor(level_cal.get(s), progress, div):
            continue                                  # not on this program's radar yet (below its level)
        # THIS program's read of the recruit, through its own stars↔results
        # philosophy — so a tape-trusting staff rates a junior-circuit winner the
        # stars missed, and a stars-trusting staff holds out for the projection.
        pcal = perceived_caliber(p, coach.results_bias if coach is not None else 0.5)
        if pcal < recruit_economy.program_caliber_floor(budget.get(s, 0.0), progress):
            continue                                  # a funded program won't burn a premium seat on them (yet)
        prox = region_proximity(hr, reg)
        geo = hc * prox                                # the recruit's own desire to stay home
        # Coach-side localism: a program whose coach recruits its backyard pulls
        # in-region recruits harder, regardless of how homesick the recruit is — so
        # "homer" programs run even more regional. Internationals sit at proximity 0,
        # so this only tugs domestic, in-region kids.
        coach_geo = COACH_LOCAL_WEIGHT * (coach.localism if coach is not None else 0.5) * prox
        # Recruits aspire UP to the most prestigious program that still has a seat
        # for them. With best-recruits-first + seat caps, the class tiers itself —
        # a program fills with whoever's left near its own level once it signs,
        # so it never starves chasing names above its band. A mild pull toward
        # their own level keeps elite talent from slumming far below it; academics
        # pull sub-elite recruits down to academic programs (gated by talent).
        level = 1.0 - 0.30 * max(0.0, cal - pres)      # only penalize signing BELOW your level
        score = ((0.15 + pres) * level
                 * (1.0 + ACA_PULL * acad * ac * academic_gate(cal))
                 * (1.0 + GEO_WEIGHT * geo + coach_geo) * (1.0 + FAC_WEIGHT * fac) * (1 + jit))
        # Playing time: recruits lean toward programs where their OVR would crack the
        # current starting card (would-start) and away from ones where they'd be
        # buried. Key, but below prestige — the (0.15+pres) term still dominates.
        # The card is the division's lineup size (10 for D1/D4, 8 for D2/D3).
        ovrs, _lu = roster_ovrs.get(s, ((), 6))
        if len(ovrs) >= _lu:
            pt = max(-1.0, min(1.0, (recruit_ovr - ovrs[_lu - 1]) / PLAY_TIME_SCALE))
        else:
            pt = 1.0                                   # open lineup — they'd play for sure
        score *= 1.0 + PLAY_TIME_WEIGHT * pt
        # Marginal geography tiebreaks — nudge toward warm-state / big-city programs for
        # recruits who prefer them (can pull against the home-state tug above).
        gw, gc = geo_flags.get(s, (False, False))
        if pref_warm and gw:
            score *= 1.0 + WARM_APPEAL_WEIGHT
        if pref_city and gc:
            score *= 1.0 + CITY_APPEAL_WEIGHT
        lt = local_terr.get(s)
        if lt is not None and lt[0] == home_abbr:      # home-territory pull (island/remote state)
            score *= 1.0 + LOCAL_TERRITORY_PULL * lt[1]
        if coach is not None:
            # Coach sourcing tilt (US coaches lean domestic, foreign lean international)
            # and a foreign coach's home-country compatriot pipeline.
            score *= coach.source_fit(p) * coach.origin_multiplier(p)
        if intl:
            score *= INTL_TIER_PULL[_intl_tier(div, acad)]
        if score > best_score:
            best, best_score = s, score
    if best is None:                              # nothing in range with a seat — widen once
        # Mid-window, hold to the floors (the recruit waits for a worthy seat). On
        # signing day (progress≈1) drop them: an unsigned recruit takes the best seat
        # left rather than VANISH — so an under-scouted gem the fog buried slides DOWN
        # a level (where scout_intel / the fall portal pick them up) instead of
        # disappearing from the world entirely.
        relax = progress >= 0.999
        best = next((s for s in reversed(by_pres)
                     if avail.get(s, 0) > 0
                     and (relax or _div_ok(traits[s][3], traits[s][1]))
                     # the D4 academic gate is a HARD admissions bar — it never relaxes,
                     # even on signing day (a kid below MIT's floor never gets into MIT).
                     and (traits[s][3] != "D4" or p_academic >= d4_min.get(s, 0.0))
                     and (relax or budget.get(s, 0.0) >= budget_floor)
                     and cur_cal >= recruit_economy.program_level_floor(level_cal.get(s), progress, traits[s][3])
                     and (relax or cal >= recruit_economy.program_caliber_floor(budget.get(s, 0.0), progress))
                     and (not exclude or s not in exclude)), None)
    return best


# Rank-dependent decision timing: where in the signing window a recruit's
# commitment peaks, as a fraction of the window. Recruits commit at VARYING times
# across the whole window — the elite tier is spread (centered, no hold-out floor)
# rather than clustered at the end, so blue-chips don't all decide after mid-tier
# recruits have reached up and filled the funded power seats (which left them
# unsigned). Lower-rated recruits still skew early. A recruit can commit anywhere
# from week 0, drawn around its rank-set peak.
SIGNING_MODE_TOP = 0.50     # #1 recruit's decision-week peak (× window) — centered
SIGNING_MODE_BOTTOM = 0.12  # lowest recruit's peak — earliest
SIGNING_FLOOR_TOP = 0.0     # no hold-out floor — any recruit can commit from week 0


def _decision_week(p, salt: str, rank_frac: float = 0.5, window: int = SIGNING_WEEKS) -> int:
    """The 0-based week WITHIN the signing window at which this recruit commits —
    deterministic per recruit, and skewed by rank so signings drip across the whole
    regular season at VARYING times: top recruits spread around the middle of the
    window, lower recruits skew early. No recruit is floored out of the early weeks,
    so the elite tier interleaves with the rest instead of clustering at the end and
    getting crowded out of the funded power seats.

    `rank_frac` is the recruit's position in the national class (0.0 = the #1
    recruit, 1.0 = the last) — it sets the mode of a triangular draw over the window."""
    window = max(1, window)
    rng = random.Random(f"{getattr(p, 'pid', '')}|decision|{salt}")
    lo = window * SIGNING_FLOOR_TOP * (1.0 - rank_frac)          # 0 → anyone can commit early
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
    # How far into the signing window we are — drives the program-side caliber
    # standard (funded programs hold premium seats for elites early, relax late).
    progress = 1.0 if final else min(1.0, week / max(1, window - 1))
    new = []
    signed_n = 0
    for i, p in enumerate(klass):
        if signed_n >= quota:
            break
        if p.pid in signed:
            continue
        # rank_frac: 0.0 = the #1 recruit, 1.0 = back of the class
        if not final and _decision_week(p, salt, i / denom, window) > week:
            continue                                        # hasn't decided to commit yet
        best = _pick_school(p, market, avail, jitter_salt="sign", progress=progress)
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
    window = _signing_window(world["seed"], world)
    progress = min(1.0, week / max(1, window - 1))          # program standard at this point in the cycle
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
                                  jitter_salt=f"flip|{week}", exclude={original},
                                  progress=progress)
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


def _load_signings(conn, world: dict, year: int | None = None) -> dict[str, dict[str, list]]:
    """{gender: {school: [Prospect, ...]}} for the class that's signed so far
    (default: the current world-year; pass `year` for an archived class).
    Each prospect carries the live `flips` count (how many times they've
    decommitted) and `week_signed` of their current commit."""
    rows = conn.execute("SELECT gender, school, data, flips, week_signed FROM world_signing"
                        " WHERE world_id=? AND year=?",
                        (world["id"], world["year"] if year is None else year)).fetchall()
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
    # Through the ceiling compression (owner rule 2026-08): this bar is compared
    # against player STRs, which are compressed — an uncompressed bar would sit
    # above every eligible riser and quietly dry the portal up.
    from .development import compress_talent
    return overall_to_str(compress_talent(
        _talent_from_strength(prog.prestige, prog.division, prog.gender),
        prog.gender))


def _scholarship_count(roster: list) -> int:
    return sum(1 for p in roster if not p.walk_on)


def graduate(rosters: dict, redshirts: set | None = None) -> int:
    """Graduate seniors and bump everyone else up a class. (Development for the
    year already happened via the weekly drip.)

    `redshirts` are pids that suffered a season-ending injury — they take a medical
    redshirt: they do NOT advance a class, they repeat it carrying an `RS-` tag
    that sticks until they graduate (so a hurt Jr replays as RS-Jr, then RS-Sr,
    then graduates — a 5th year of eligibility). The tag is purely cosmetic
    eligibility flavor; it never touches the match engine."""
    redshirts = redshirts or set()
    grads = 0
    for schools in rosters.values():
        for school, roster in schools.items():
            kept = []
            for p in roster:
                base = _base_class(p.class_year)
                if p.pid in redshirts:                  # medical redshirt: repeat, tag RS-, no advance
                    p.class_year = _RS_PREFIX + base
                    kept.append(p)
                    continue
                if _departing(p):                       # seniors + pro grad transfers (incl. legacy)
                    grads += 1
                    continue
                nxt = _NEXT_CLASS.get(base, "So")
                p.class_year = (_RS_PREFIX + nxt) if p.class_year.startswith(_RS_PREFIX) else nxt
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


_UP_DIV = {"D2": "D1", "D3": "D2", "D4": "D3"}      # a transfer climbs at most one level
_DOWN_DIV = {"D1": "D2", "D2": "D3", "D3": "D4"}    # ...and drops at most one — never skipping


def _career_transfers(p) -> int:
    """How many times this player has already changed schools (school changes in
    their season history). The engine moves a player at most ONCE per career — a
    repeat transfer only happens if you do it manually in the editor."""
    hist = sorted((getattr(p, "history", []) or []),
                  key=lambda h: (h.get("year", 0), h.get("stint", 0)))
    seq = [h.get("school") for h in hist if h.get("school")]
    return sum(1 for a, b in zip(seq, seq[1:]) if a != b)


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
    div_of: dict[str, str] = {}
    for (division, g), schools_ in rosters.items():
        if g != gender:
            continue
        pool.update(schools_)
        for s in schools_:
            div_of[s] = division
    schools = [s for s in pool if s in progs]
    prestige = {s: progs[s].prestige for s in schools}
    facilities = {s: progs[s].facilities for s in schools}
    level = {s: _prog_level(progs[s]) for s in schools}
    strs = {s: sorted(_str_of(player_str, p) for p in pool[s]) for s in schools}
    schol = {s: _scholarship_count(pool[s]) for s in schools}
    by_div: dict[str, list] = {}
    for s in schools:
        by_div.setdefault(div_of.get(s, ""), []).append(s)

    def open_slot(s):
        return len(pool[s]) < roster_cap(div_of.get(s, "")) and schol[s] < SCHOLARSHIP_SLOTS

    def line_of(s, val):
        a = strs[s]
        return 1 + (len(a) - bisect.bisect_right(a, val))

    def best_in(div, val, want_line, block=()):
        """Best-prestige program IN ONE DIVISION with an open slot where the player
        would slot at `want_line` or better (so they'd actually be in the lineup).
        `block` drops programs the mover can't join (a service academy for an
        international — see ncaa.blocked_schools_for)."""
        best, draw = None, -1.0
        for d in by_div.get(div, ()):
            if d == "" or d in block or not open_slot(d) or line_of(d, val) > want_line:
                continue
            w = prestige[d] + 0.3 * facilities[d]
            if w > draw:
                best, draw = d, w
        return best

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
            if _career_transfers(p) >= 1:        # engine moves a player only once
                continue
            s = _str_of(player_str, p)
            if p.walk_on:
                movers.append((p, school, s, "schol"))
            elif rng.random() < base * _churn_mult(s, lvl):
                movers.append((p, school, s, "churn"))
    movers.sort(key=lambda m: -m[2])

    out = {"movers": len(movers), "up": 0, "down": 0, "lateral": 0, "schol": 0,
           "depart": 0, "sample": []}
    for p, src, s, reason in movers:
        d_src = div_of.get(src, "")
        cl = line_of(src, s)
        up_d, down_d = _UP_DIV.get(d_src), _DOWN_DIV.get(d_src)
        rel = _rel_of(player_str, p)
        blk = blocked_schools_for(p)       # service academies, for an international

        if reason == "schol":              # walk-on chasing a scholarship / lineup spot
            # Their own division first; only drop ONE level if nothing at home wants
            # them in the lineup. They never leave the universe — worst case they
            # stay a walk-on.
            dest = best_in(d_src, s, SCHOLARSHIP_SLOTS, blk)
            if not dest and down_d:
                dest = best_in(down_d, s, SCHOLARSHIP_SLOTS, blk)
            if dest:
                relocate(p, src, dest, s, walk_on=False)
                out["schol"] += 1
                out["sample"].append(("schol", p.name, src, dest, round(s, 1)))
            continue

        # Rostered player. Stay in-division by default; the elite climb one level,
        # the buried drop one — never skipping a division, never to a far-off level.
        moved = False
        # UP — only a genuine #1/#2 talent, reliable and clearly above their level
        if (cl <= 2 and up_d and rel >= RELIABILITY_GATE
                and (s - level[src]) >= UP_THRESHOLD and rng.random() < UP_SUCCESS):
            dest = best_in(up_d, s, lineup_size(up_d), blk)
            if dest:
                relocate(p, src, dest, s, walk_on=False)
                out["up"] += 1
                out["sample"].append(("up", p.name, src, dest, round(s, 1)))
                moved = True
        # LATERAL — a better program in the SAME division that wants them in the
        # lineup (the common, realistic transfer)
        if not moved:
            same = best_in(d_src, s, lineup_size(d_src), blk)
            if same and same != src and prestige[same] > prestige[src] + 0.03 \
                    and rng.random() < UP_SUCCESS:
                relocate(p, src, same, s, walk_on=False)
                out["lateral"] += 1
                out["sample"].append(("lateral", p.name, src, same, round(s, 1)))
                moved = True
        # DOWN — only the buried (the last two lineup slots or off the card entirely,
        # scaled to the division's singles card), one level, and only if the lower
        # division wants them comfortably IN the lineup (not its last slots).
        if not moved and cl >= lineup_size(d_src) - 1 and down_d:
            dest = best_in(down_d, s, lineup_size(down_d) - 2, blk)
            if dest:
                relocate(p, src, dest, s, walk_on=False)
                out["down"] += 1
                out["sample"].append(("down", p.name, src, dest, round(s, 1)))
                moved = True
        # otherwise they stay put — no forced departure out of the universe
    return out


# ==========================================================================
# Fall transfer portal — the post-ITA talent reshuffle (sim proposes, you
# approve). A D1-caliber player buried in a lower division climbs to the highest
# division whose lineup they'd crack; if their new program is full it sends its
# weakest player back DOWN the ladder (a cascade), ideally into the very seat the
# riser vacated. The net effect: no program runs over cap, and the only roster
# shrinkage is at the very bottom, repaired by `refill_walkons` at rollover.
# Unlike the year-end `transfer_portal`, movers keep BOTH stints of the split
# season (ITA at the old school, regular+postseason at the new one).
# ==========================================================================
_FP_DIV_ORDER = ["D1", "D2", "D3", "D4"]    # high → low


class _FPPlanner:
    """One in-memory snapshot of a gender's cross-division rosters, with the cascade
    engine on top. `discover` finds the sim's risers and places them; `place` puts a
    single rider (auto or at an explicit destination) and cascades — so the same
    machinery serves both the auto proposal and the user's edits/adds at resolve."""

    def __init__(self, rosters: dict, player_str: dict, gender: str,
                 active_divs=None):
        progs = _flat_programs(gender)
        self.player_str = player_str
        # Destinations are limited to these divisions. A player may be discovered as a
        # riser FROM any division (so a stud in a dormant level can be rescued up), but
        # must never be moved INTO an inactive division — that program is never simulated,
        # so the mover would leave the playable season. None = every present division is a
        # valid destination (the fall portal already feeds only active universes).
        self.active_divs = set(active_divs) if active_divs is not None else None
        pool: dict[str, list] = {}
        div_of: dict[str, str] = {}
        for (division, g), schools_ in rosters.items():
            if g != gender:
                continue
            # SHALLOW-COPY each roster list: the planner relocates players by mutating
            # these lists, and `rosters` is the SHARED, cached `developed_rosters` —
            # mutating it in place would corrupt the cache for every later resolve
            # (movers' src would drift to wherever a prior pass placed them).
            for s, roster in schools_.items():
                pool[s] = list(roster)
                div_of[s] = division
        schools = [s for s in pool if s in progs]
        self.pool, self.div_of, self.schools = pool, div_of, schools
        self._sv_cache: dict = {}
        self.prestige = {s: progs[s].prestige for s in schools}
        self.facilities = {s: progs[s].facilities for s in schools}
        self.level = {s: _prog_level(progs[s]) for s in schools}
        self.strs = {s: sorted(self._sv(p) for p in pool[s]) for s in schools}
        # by_div (destination pool + the median bar) holds ONLY valid-destination
        # divisions; sources (pool/schools/by_pid) keep every division.
        by_div: dict[str, list] = {}
        # Destination "draw" weight per school; by_div sorted by it (desc, then name for
        # determinism) so best_in/fullest_below EARLY-EXIT at the first match instead of
        # scanning every program — and receiving programs are dropped from the pool as they
        # fill, so placing N riders is ~linear, not quadratic in N (the portal seed cost).
        self._weight = {s: self.prestige[s] + 0.3 * self.facilities[s] for s in schools}
        for s in schools:
            if not self._dest_ok(div_of.get(s, "")):
                continue
            by_div.setdefault(div_of.get(s, ""), []).append(s)
        for d in by_div:
            by_div[d].sort(key=lambda s: (-self._weight[s], s))
        self.by_div = by_div
        # A division's TYPICAL (median) expected level — the bar a riser must clear.
        self.div_level = {}
        for d, ss in by_div.items():
            lv = sorted(self.level[s] for s in ss)
            self.div_level[d] = lv[len(lv) // 2] if lv else 0.0
        self.moves: list[dict] = []
        self.touched: set = set()
        self.received: set = set()
        # Pids that already have a move in this slate. ONE move per player is a hard
        # invariant: the `fall_portal`/`preseason_portal` tables are keyed
        # (year, gender, pid), so a second move for the same player is an
        # IntegrityError at commit — and semantically a player transfers once.
        self.moved: set = set()
        self.by_pid = {p.pid: (s, p) for s in schools for p in pool[s]}

    def _sv(self, p):
        # Memoize per pid: with an empty player_str (the preseason portal) this falls to
        # p.str_value(), which re-normalizes attributes on every call — and the planner asks
        # for the same players' STR many times over (init, discover, place, cascade). A
        # player's intrinsic STR never changes as it's relocated, so one compute per pid.
        c = self._sv_cache.get(p.pid)
        if c is None:
            c = self._sv_cache[p.pid] = _str_of(self.player_str, p)
        return c

    def _dest_ok(self, division: str) -> bool:
        """Whether a division is a valid MOVE DESTINATION (active/simulated)."""
        return self.active_divs is None or division in self.active_divs

    def deny(self, p) -> frozenset:
        """Programs THIS player may never move to on citizenship grounds — the
        service academies for an international (US citizens only). Folded into the
        `avoid` set every destination search already honors, so a rider, a user
        redirect and a displaced cascade player all respect it."""
        return blocked_schools_for(p)

    def open_slot(self, s):
        return len(self.pool[s]) < roster_cap(self.div_of.get(s, ""))

    def line_of(self, s, val):
        a = self.strs[s]
        return 1 + (len(a) - bisect.bisect_right(a, val))

    def best_in(self, div, val, want_line, avoid=None):
        """Best-prestige program in `div` with an OPEN seat where the player slots at
        `want_line` or better; `avoid` skips programs that already took a riser. by_div is
        weight-sorted, so the FIRST program that passes is the answer (early exit)."""
        for d in self.by_div.get(div, ()):
            if not d or (avoid and d in avoid) or not self.open_slot(d):
                continue
            if self.line_of(d, val) <= want_line:
                return d
        return None

    def best_placement(self, div, val, avoid=None):
        """Diversifying auto-destination (owner rule 2027-07): among open-seat programs
        in `div` where the player would make the lineup (line within the division's
        singles card — ncaa.lineup_size), send them to the one where they'd slot
        HIGHEST — the biggest lineup upgrade / most playing time — tie-broken by
        prestige. This spreads risers across the programs that actually NEED the
        talent instead of funneling them all to the top-prestige few, so
        underutilized players land where they'll play. Scans the division (no early
        exit), but only the ≤30 discovered risers use it, so it stays cheap."""
        best, best_key = None, None
        _lu = lineup_size(div)
        for d in self.by_div.get(div, ()):
            if not d or (avoid and d in avoid) or not self.open_slot(d):
                continue
            line = self.line_of(d, val)
            if line > _lu:
                continue
            key = (line, -self._weight[d], d)   # lowest line first; prestige breaks ties
            if best_key is None or key < best_key:
                best, best_key = d, key
        return best

    def _weakest_eligible(self, s, val):
        cand = [q for q in self.pool[s] if q.pid not in self.touched
                and _career_transfers(q) == 0 and self._sv(q) < val]
        return min(cand, key=lambda q: (self._sv(q), q.pid)) if cand else None

    def fullest_below(self, div, val, avoid=None):
        # Weight-sorted by_div → first full program that can shed a weaker player is the
        # best-prestige one (early exit).
        for d in self.by_div.get(div, ()):
            if not d or (avoid and d in avoid) or self.open_slot(d):
                continue
            if self._weakest_eligible(d, val) is not None:
                return d
        return None

    def _apply(self, p, src, dest):
        sval = self._sv(p)
        self.pool[src].remove(p)
        a = self.strs[src]
        i = bisect.bisect_left(a, sval)
        a.pop(i if i < len(a) and a[i] == sval else a.index(sval))
        self.pool[dest].append(p)
        bisect.insort(self.strs[dest], sval)
        self.by_pid[p.pid] = (dest, p)
        self.moved.add(p.pid)              # one move per player per slate (see __init__)

    def _mk(self, p, src, dest, cascade_from):
        return {"pid": p.pid, "name": getattr(p, "name", ""),
                "src_school": src, "dest_school": dest,
                "src_div": self.div_of[src], "dest_div": self.div_of[dest],
                "str": round(self._sv(p), 1), "cascade_from": cascade_from}

    def over_div(self, src, val):
        """Highest division above the player's whose typical level they already clear."""
        src_rank = _FP_DIV_ORDER.index(self.div_of[src])
        for d in _FP_DIV_ORDER[:src_rank]:
            if val >= self.div_level.get(d, float("inf")):
                return d
        return None

    def highest_fit(self, src, val, avoid=None, *, gated=True):
        """Highest division above the player's where they'd make the lineup (a line
        within that division's singles card). With `gated`, also require clearing
        that division's median level (the auto discovery bar); user picks pass
        gated=False so any climb they'd fit is allowed."""
        src_rank = _FP_DIV_ORDER.index(self.div_of[src])
        for d in _FP_DIV_ORDER[:src_rank]:
            if gated and val < self.div_level.get(d, float("inf")):
                continue
            if (self.best_in(d, val, lineup_size(d), avoid) is not None
                    or self.fullest_below(d, val, avoid) is not None):
                return d
        return None

    def settle(self, p, from_school, prefer):
        """Place a displaced player into an open seat — preferring the seat the riser
        vacated (a clean swap-back), else the best open seat further down."""
        if p.pid in self.moved:            # already relocated this slate — never twice
            return False
        val = self._sv(p)
        deny = self.deny(p)
        from_rank = _FP_DIV_ORDER.index(self.div_of[from_school])
        if (prefer and prefer in self.pool and prefer not in deny
                and self._dest_ok(self.div_of[prefer])
                and self.open_slot(prefer)
                and _FP_DIV_ORDER.index(self.div_of[prefer]) >= from_rank
                and self.line_of(prefer, val) <= roster_cap(self.div_of[prefer])):
            self._apply(p, from_school, prefer)
            self.moves.append(self._mk(p, from_school, prefer, from_school))
            return True
        for d in _FP_DIV_ORDER[from_rank + 1:]:
            dest = self.best_in(d, val, roster_cap(d), deny)
            if dest is not None:
                self._apply(p, from_school, dest)
                self.moves.append(self._mk(p, from_school, dest, from_school))
                return True
        return False

    def place(self, p, src, dest=None, *, gated=True):
        """Place one rider. With no `dest`, auto-pick the highest division they fit;
        with an explicit `dest` (a user redirect/add), honor it. A full destination
        displaces its weakest, who cascades down. Returns the destination, or None if
        no fit was found for an auto placement."""
        if p.pid in self.moved:
            # Already relocated in this slate (e.g. dragged down as another rider's
            # cascade before their own intent was read). A second move would write a
            # duplicate (year, gender, pid) row and 500 the commit.
            return None
        val = self._sv(p)
        deny = self.deny(p)                    # citizenship gate (service academies)
        if dest is None:
            avoid = (self.received | deny) if deny else self.received
            want = self.highest_fit(src, val, avoid, gated=gated)
            if want is None:
                return None
            # Diversify: place the riser where they'd slot highest (most playing time),
            # not simply at the top-prestige program with a seat — spreads the talent.
            open_dest = self.best_placement(want, val, avoid)
            if open_dest is not None:
                self._apply(p, src, open_dest)
                self.moves.append(self._mk(p, src, open_dest, None))
                self.received.add(open_dest)
                return open_dest
            dest = self.fullest_below(want, val, avoid)
            if dest is None:
                return None
        if dest not in self.pool or dest in deny:   # unknown school / can't admit them
            return None
        if self.open_slot(dest):                # open seat — straight promotion
            self._apply(p, src, dest)
            self.moves.append(self._mk(p, src, dest, None))
            self.received.add(dest)
            return dest
        weakest = self._weakest_eligible(dest, val)
        self._apply(p, src, dest)               # a user pick into a full team still lands
        self.moves.append(self._mk(p, src, dest, None))
        self.received.add(dest)
        if weakest is not None:                 # ...sending the weakest down the ladder
            self.touched.add(weakest.pid)
            self.settle(weakest, dest, prefer=src)
        return dest

    def discover(self, cap: int):
        """The sim's auto pass: top-2 lower-division players who clear a higher
        division's median level, the most mis-allocated first up to `cap`."""
        candidates = []
        for s in self.schools:
            if self.div_of[s] == "D1":
                continue
            for p in self.pool[s]:
                if p.walk_on or _career_transfers(p) != 0:
                    continue
                val = self._sv(p)
                if self.line_of(s, val) <= 2 and self.over_div(s, val) is not None:
                    candidates.append((p, s, val, val - self.div_level.get(self.div_of[s], 0.0)))
        candidates.sort(key=lambda r: (-r[3], r[0].pid))
        risers = sorted(candidates[:cap], key=lambda r: (-r[2], r[0].pid))
        for p, s, _v, _g in risers:
            if p.pid in self.touched:
                continue
            self.touched.add(p.pid)
            self.place(p, s)

    def auto_dest(self, pid: str, *, gated: bool = False):
        """The destination the engine would pick for a single player on a clean
        snapshot — used to pre-fill the destination when the user adds a mover."""
        entry = self.by_pid.get(pid)
        if not entry:
            return None
        src, p = entry
        return self.highest_fit(src, self._sv(p), self.deny(p), gated=gated)


def fall_portal_proposals(rosters: dict, player_str: dict, rng: random.Random,
                          gender: str) -> list[dict]:
    """Deterministic cross-division reshuffle for one gender. Returns a list of move
    dicts (pid, src/dest school+division, str, cascade_from) computed on an in-memory
    snapshot — the caller persists the riders as proposals; cascades are re-derived
    at resolve. Only real rosters mutate, on commit, via `overrides.set_move`."""
    if not any(g == gender for (_d, g) in rosters):
        return []
    plan = _FPPlanner(rosters, player_str, gender)
    if not plan.schools:
        return []
    plan.discover(FALL_PORTAL_MAX_RISERS)
    return plan.moves


def _all_in_fall_portal(seed: int, w: dict) -> bool:
    sids = [universe_sid(seed, w, d, g) for (d, g) in _active_unis()]
    phases = [sm.load_season(sid)["phase"] for sid in sids]
    return bool(phases) and all(p == "fall_portal" for p in phases)


def _release_fall_portal(seed: int, w: dict) -> None:
    """Send every held universe on to the regular season (current_week was already
    set to the post-ITA first week when the ITA closed)."""
    def _do():
        conn = _db()
        try:
            for (d, g) in _active_unis():
                sid = universe_sid(seed, w, d, g)
                conn.execute("UPDATE seasons SET phase='regular'"
                             " WHERE id=? AND phase='fall_portal'", (sid,))
            conn.commit()
        finally:
            conn.close()
    _retry_locked(_do)


def _ita_lookup(seed: int, w: dict):
    """(records, lines) keyed (division, gender) for every active universe. With the
    world held at the post-ITA boundary, these ARE the ITA stint's W/L and primary
    line for each mover — what we freeze onto their career history at commit."""
    recs: dict = {}
    lines: dict = {}
    for (d, g) in _active_unis():
        sid = universe_sid(seed, w, d, g)
        recs[(d, g)] = sm.player_records(sid)
        lines[(d, g)] = sm.player_primary_lines(sid)
    return recs, lines


def run_fall_portal(seed: int = DEFAULT_SEED) -> dict:
    """The sim's auto pass: discover RIDER intents across all active universes and
    persist them (status='proposed'). Cascades are NOT stored — they're re-derived
    from these riders by `resolve_fall_portal` on every view/edit/commit, so the user
    can freely redirect or add movers. Returns a pending event for the UI."""
    from app import overrides as ov
    w = get_or_create(seed)
    prime(seed)
    rosters = developed_rosters(w)
    total = 0
    for gender in worldconfig.active_genders():
        rng = random.Random(f"{seed}|fallportal|{w['year']}|{gender}")
        props = fall_portal_proposals(rosters, {}, rng, gender)
        riders = [{**m, "status": "proposed"} for m in props if m["cascade_from"] is None]
        ov.set_proposals(w["year"], gender, riders)
        total += len(riders)
    reset_caches(); _primed.pop(seed, None)
    return {"event": "fall_portal_pending", "year": w["year"], "proposals": total}


def resolve_fall_portal(seed: int = DEFAULT_SEED) -> dict:
    """Resolve the stored rider intents into the full move slate (riders + their
    derived cascade demotions) per gender, on a fresh snapshot. Re-run on every view
    and at commit so user edits (redirect / add / drop) always recompute a correct,
    cap-safe cascade against every other locked-in choice."""
    from app import overrides as ov
    w = get_or_create(seed)
    rosters = developed_rosters(w)
    out: dict = {}
    for gender in worldconfig.active_genders():
        riders = [r for r in ov.get_proposals(w["year"])
                  if r["gender"] == gender and r["cascade_from"] is None
                  and r["status"] != "rejected"]
        riders.sort(key=lambda r: (-r["str"], r["pid"]))      # best pick fits first
        plan = _FPPlanner(rosters, {}, gender, active_divs=worldconfig.active_divisions())
        # Protect EVERY rider up front, not just the one being placed: a rider has their
        # own destination, so they must never be picked as another rider's cascade
        # victim. Touching them one-at-a-time inside the loop let an as-yet-unread rider
        # be dragged down as a cascade and then placed AGAIN at their own intent — two
        # moves for one pid, which is a UNIQUE (year, gender, pid) IntegrityError at
        # commit. `_weakest_eligible` now steps past riders to the weakest non-rider.
        plan.touched.update(r["pid"] for r in riders)
        for r in riders:
            entry = plan.by_pid.get(r["pid"])
            if not entry:
                continue                                       # graduated / not on a roster
            src, p = entry
            plan.place(p, src, dest=r["dest_school"], gated=False)
        # Deduped HERE, not just at the write: commit walks this same list to `set_move`
        # each mover and to archive the window, so a stray duplicate must be gone before
        # anyone acts on it — not silently dropped by the table underneath them.
        out[gender] = ov.dedupe_slate(plan.moves, "fall_portal")
    return out


def _stamp_ita_stint(conn, w: dict, pid: str, src_school: str, src_div: str,
                     gender: str, ita_w: int, ita_l: int, ita_line, strv: float) -> None:
    """Freeze a mover's ITA stint at their old school onto their persisted career
    history (stint 0) so it survives the move — the regular+postseason stint at the
    new school is stamped as stint 1 at year-end by `_record_world_history`."""
    r = conn.execute("SELECT data FROM world_roster WHERE world_id=? AND year=? AND pid=?",
                     (w["id"], w["year"], pid)).fetchone()
    if not r:
        return
    p = prospect_from_dict(json.loads(r["data"]))
    yr = w["year"]
    if any(h.get("year") == yr and h.get("stint", 0) == 0 for h in p.history):
        return
    p.history.append({
        "year": yr, "season_no": yr + 1, "division": src_div, "gender": gender,
        "school": src_school, "class": p.class_year, "line": ita_line,
        "w": ita_w, "l": ita_l, "str": round(strv, 1),
        "singles_lines": {}, "doubles_lines": {}, "stint": 0, "phase": "ita"})
    conn.execute("UPDATE world_roster SET data=? WHERE world_id=? AND year=? AND pid=?",
                 (json.dumps(prospect_to_dict(p)), w["id"], w["year"], pid))


def commit_fall_portal(seed: int = DEFAULT_SEED) -> dict:
    """Resolve the (edited) slate, then for every move — riders AND their cascade
    demotions — relocate the player (set_move), freeze their ITA stint, and record a
    committed row (so the year-end two-stint history + rollover bake cover the whole
    cascade). Finally release every held universe to the regular season."""
    from app import overrides as ov
    w = get_or_create(seed)
    year = w["year"]
    resolved = resolve_fall_portal(seed)              # {gender: [moves]}
    recs, lines = _ita_lookup(seed, w)
    # Freeze every mover's ITA stint on one connection first (a held write lock here
    # would deadlock the per-row override writes, which open their own connections).
    conn = _db()
    committed: dict = {}
    moved = 0
    for gender, moves in resolved.items():
        rows = []
        for m in moves:
            sd = (m["src_div"], gender)
            ww, ll = recs.get(sd, {}).get(m["pid"], (0, 0))
            ln = lines.get(sd, {}).get(m["pid"])
            _stamp_ita_stint(conn, w, m["pid"], m["src_school"], m["src_div"],
                             gender, ww, ll, ln, m["str"])
            rows.append({**m, "status": "committed", "ita_w": ww, "ita_l": ll, "ita_line": ln})
            moved += 1
        committed[gender] = rows
    conn.commit(); conn.close()
    for gender, rows in committed.items():
        ov.set_proposals(year, gender, rows)          # the slate is now the committed moves
        for m in rows:
            ov.set_move(m["pid"], m["dest_school"])
        _archive_portal_moves(seed, w, gender, "fall", rows)   # durable record for Portal Rankings
    _base_cache.pop((w["id"], w["year"]), None)        # ITA stint changed the stored roster
    _dev_cache.clear()
    _release_fall_portal(seed, w)
    reset_caches(); _primed.pop(seed, None)
    signed = _commit_pro_signings(seed, f"{year}-fall")   # persist the free-agent pros signed this window
    return {"event": "fall_portal_committed", "year": year, "moved": moved, "pros": signed}


def _citizenship_error(p, dest_school: str) -> str:
    """The user-facing reason a hand-picked destination is refused, or "" if it's
    allowed. Only one rule: a service academy takes US citizens only, so an
    international can't be sent there by the portals or signed there as a pro."""
    if p is None or admits_nationality(dest_school, p):
        return ""
    return (f"{dest_school} is a US service academy — it can only roster American "
            f"players, and {getattr(p, 'name', 'this player')} is international.")


def _fp_find(seed: int, w: dict, rosters: dict, pid: str):
    """(gender, src_school, src_div, Prospect, planner) for a pid currently on a
    fall-held roster, or None. The planner is a throwaway snapshot for that gender."""
    for gender in worldconfig.active_genders():
        plan = _FPPlanner(rosters, {}, gender)
        if pid in plan.by_pid:
            src, p = plan.by_pid[pid]
            return gender, src, plan.div_of[src], p, plan
    return None


def redirect_fall_portal_mover(seed: int, pid: str, dest_school: str) -> dict:
    """Send a proposed rider to a different destination than the sim picked. The
    cascade is recomputed at the next resolve, so the displaced-player chain updates
    automatically."""
    from app import overrides as ov
    w = get_or_create(seed)
    rosters = developed_rosters(w)
    for gender in worldconfig.active_genders():
        rider = next((r for r in ov.get_proposals(w["year"])
                      if r["gender"] == gender and r["pid"] == pid
                      and r["cascade_from"] is None), None)
        if not rider:
            continue
        plan = _FPPlanner(rosters, {}, gender)
        if dest_school not in plan.div_of:
            return {"error": "unknown destination"}
        err = _citizenship_error(plan.by_pid.get(pid, (None, None))[1], dest_school)
        if err:
            return {"error": err}
        ov.set_dest(w["year"], gender, pid, dest_school, plan.div_of[dest_school])
        return {"ok": True, "pid": pid, "dest": dest_school}
    return {"error": "rider not found"}


def add_fall_portal_mover(seed: int, pid: str, dest_school: str | None = None) -> dict:
    """Add a player the sim didn't propose as a rider (your pick). With no
    destination, the engine pre-fills the best fit (ignoring the auto-discovery
    gates — it's your call). They then ride the same resolve/commit path, so they
    get the cascade balance and two-stint history like any sim mover."""
    from app import overrides as ov
    w = get_or_create(seed)
    rosters = developed_rosters(w)
    found = _fp_find(seed, w, rosters, pid)
    if not found:
        return {"error": "player not on a current roster"}
    gender, src, src_div, p, plan = found
    if dest_school in (None, "", "auto"):
        dest_school = plan.place(p, src, dest=None, gated=False)   # throwaway planner
    if not dest_school or dest_school not in plan.div_of:
        return {"error": "no destination found — pick a school"}
    err = _citizenship_error(p, dest_school)
    if err:
        return {"error": err}
    recs, lines = _ita_lookup(seed, w)
    sd = (src_div, gender)
    ww, ll = recs.get(sd, {}).get(pid, (0, 0))
    ov.upsert_proposal(w["year"], gender, {
        "pid": pid, "name": getattr(p, "name", ""), "src_school": src,
        "dest_school": dest_school, "src_div": src_div, "dest_div": plan.div_of[dest_school],
        "str": round(_str_of({}, p), 1), "status": "proposed", "cascade_from": None,
        "ita_w": ww, "ita_l": ll, "ita_line": lines.get(sd, {}).get(pid)})
    return {"ok": True, "pid": pid, "dest": dest_school, "gender": gender}


def fall_portal_destinations(seed: int = DEFAULT_SEED) -> list[str]:
    """Every program in the active universes (sorted), for the redirect/add picker."""
    names: set = set()
    for gender in worldconfig.active_genders():
        names.update(_flat_programs(gender).keys())
    return sorted(names)


# --------------------------------------------------------------------------
# Pre-season portal — the SAME cross-division reshuffle engine as the fall portal
# (`_FPPlanner`: top-2 lower-division players who clear a higher division's median
# rise UP; the roster they'd overfill cascades its weakest DOWN), but run at week 0
# before the season opens. At week 0 there are no results yet, so the planner reads
# each player's intrinsic ability (`_str_of` falls back to `str_value()`) — exactly
# the talent signal we want for fixing first-launch over-allocation. Commit is a
# plain `set_move` per mover: no NIT stint, no two-stint history, no phase hold —
# the player simply starts the year at the new school. Lives in its own table so it
# never collides with the post-NIT fall portal that may run later the same year.
# --------------------------------------------------------------------------
# The pro tier — elite ex-pros (OVR 81-90) who enter ONLY through the portal, one per
# cycle across all three (pre-season / fall / year-end). Generated by app.pros, assigned
# to the best affordable program, persisted straight into world_roster so they play. Cost
# is STR-indexed and always ≤ the elite budget cap, so every pro signs. Idempotent per
# (year, cycle) via the world_pro ledger. Volume is worldconfig.pros_per_cycle (even, UI).
# --------------------------------------------------------------------------
def _pro_spend(conn, world_id: int, year: int, gender: str) -> dict:
    """Per-school pro-signing spend this year FOR ONE GENDER (men's and women's programs
    are separate). Pros are paid out of the SAME recruiting budget as the class (one pool),
    so this is deducted from a program's budget — a program that signs an expensive pro has
    that much less to spend on recruits, and can even drop below a caliber floor (no more
    blue-chips this year)."""
    rows = conn.execute(
        "SELECT school, SUM(cost) AS spent FROM world_pro "
        "WHERE world_id=? AND year=? AND gender=? AND school!='' GROUP BY school",
        (world_id, year, gender)).fetchall()
    return {r["school"]: (r["spent"] or 0.0) for r in rows}


def inject_pros(seed: int, cycle_key: str) -> dict:
    from app import pros, recruit_economy
    if worldconfig.pros_per_cycle() <= 0:
        return {"event": "pros_disabled"}
    w = get_or_create(seed)
    salt = active_salt(seed)
    conn = _db()
    if conn.execute("SELECT 1 FROM world_pro WHERE world_id=? AND year=? AND cycle=? LIMIT 1",
                    (w["id"], w["year"], cycle_key)).fetchone():
        conn.close()
        return {"event": "pros_exists", "cycle": cycle_key}
    prime(seed)
    rosters = developed_rosters(w)
    roster_rows, pro_rows = [], []
    for gender in worldconfig.active_genders():
        cohort = pros.generate_pros(salt, gender, cycle_key)
        if not cohort:
            continue
        spent = _pro_spend(conn, w["id"], w["year"], gender)   # pro budget already committed this year
        progs = _flat_programs(gender)
        div_of, roster_of, programs = {}, {}, []
        for (d, g), schools in rosters.items():
            if g != gender:
                continue
            for school, roster in schools.items():
                prog = progs.get(school)
                if not prog:
                    continue
                div_of[school] = d
                roster_of[school] = roster
                # ONE budget: what's left after any pros already signed this year.
                budget = recruit_economy.program_budget(prog, salt, w["year"]) - spent.get(school, 0.0)
                programs.append({"school": school, "budget": max(0.0, budget),
                                 "prestige": float(getattr(prog, "prestige", 0.5)),
                                 # service academy: never signs an international pro
                                 "us_only": us_only_program(school)})
        by_pid = {p.pid: p for p in cohort}
        for a in pros.assign_pros(cohort, programs):
            p, school = by_pid[a["pid"]], a["school"]
            d, roster = div_of[school], roster_of[school]
            # If the roster is full, the pro displaces its weakest player (a walk-on gets
            # bumped — the roster refills its walk-on tail at rollover).
            if len(roster) >= roster_cap(d):
                weakest = min(roster, key=lambda q: q.current_overall())
                conn.execute("DELETE FROM world_roster WHERE world_id=? AND year=? AND pid=?",
                             (w["id"], w["year"], weakest.pid))
                roster.remove(weakest)
            roster.append(p)
            roster_rows.append((w["id"], w["year"], d, gender, school, p.pid,
                                json.dumps(prospect_to_dict(p))))
            pro_rows.append((w["id"], w["year"], cycle_key, gender, d, school, p.pid, a["cost"]))
    if roster_rows:
        # Defensive: clear any prior row for these pids this year before inserting, so a pro
        # can never appear twice in world_roster even if this ever runs off a half-cleared
        # ledger (the cycle guard above already prevents a clean double-inject).
        conn.executemany("DELETE FROM world_roster WHERE world_id=? AND year=? AND pid=?",
                         [(w["id"], w["year"], r[5]) for r in roster_rows])
        conn.executemany("INSERT INTO world_roster VALUES (?,?,?,?,?,?,?)", roster_rows)
    # Always leave a ledger marker for the cycle so it never re-injects (even if 0 signed).
    conn.execute("INSERT INTO world_pro VALUES (?,?,?,?,?,?,?,?)",
                 (w["id"], w["year"], cycle_key, "", "", "", "", 0.0))
    if pro_rows:
        conn.executemany("INSERT INTO world_pro VALUES (?,?,?,?,?,?,?,?)", pro_rows)
    conn.commit()
    conn.close()
    _base_cache.clear(); _dev_cache.clear(); _primed.clear()
    reset_caches()
    return {"event": "pros_injected", "year": w["year"], "cycle": cycle_key,
            "signed": len(pro_rows)}


def list_pros(seed: int = DEFAULT_SEED, cycle_key: str | None = None) -> list[dict]:
    """Display rows for the pros that entered via the portal this year — the synthetic
    'Pros' pool → their signing club, carrying the real STR/cost/badge. `cycle_key` limits
    to one cycle (e.g. the pre-season intake); None returns every cycle so far this year.
    Read-only: the assignment is budget-driven and the count is the pros-per-cycle lever."""
    w = load_world(seed)
    if not w:
        return []
    conn = _db()
    try:
        q = ("SELECT cycle, gender, division, school, pid, cost FROM world_pro"
             " WHERE world_id=? AND year=? AND pid!=''")
        args = [w["id"], w["year"]]
        if cycle_key:
            q += " AND cycle=?"
            args.append(cycle_key)
        rows = conn.execute(q, args).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        p = find_persisted_player(r["pid"], seed)
        if not p:
            continue
        out.append({"pid": r["pid"], "gender": r["gender"],
                    "src_school": "Pros", "src_div": "PRO",
                    "dest_school": r["school"], "dest_div": r["division"],
                    "name": getattr(p, "name", r["pid"]),
                    "country": getattr(p, "country", ""),
                    "str": round(p.str_value(), 1), "cost": round(r["cost"] or 0.0, 1),
                    "cycle": r["cycle"], "signed": True})
    out.sort(key=lambda d: (-d["str"], d["pid"]))
    return out


def pro_destinations(seed: int = DEFAULT_SEED) -> list[str]:
    """Every program a free-agent pro can sign with — ALL programs, ANY division."""
    return fall_portal_destinations(seed)


def pro_cohort(seed: int = DEFAULT_SEED, cycle_key: str | None = None) -> list[dict]:
    """This cycle's pro FREE-AGENT pool: the deterministic cohort (regenerated on demand —
    they aren't persisted until signed), each with real STR, an STR-indexed cost, and the club
    the user has signed them to (blank = still a free agent). Pre-commit source for the portal;
    after the slate commits, signed pros live in `world_pro`/`world_roster` — read `list_pros`."""
    from app import pros
    from app import overrides as ov
    w = load_world(seed)
    if not w:
        return []
    cycle_key = cycle_key or f"{w['year']}-preseason"
    salt = active_salt(seed)
    signs = ov.pro_get_signs(w["year"], cycle_key)
    out = []
    for gender in worldconfig.active_genders():
        cohort = pros.generate_pros(salt, gender, cycle_key)
        for p in cohort:
            sg = signs.get(p.pid)
            out.append({"pid": p.pid, "gender": gender,
                        "name": getattr(p, "name", p.pid),
                        "country": getattr(p, "country", ""),
                        "str": round(p.str_value(), 1),
                        "cost": round(pros.pro_cost(p, cohort), 1),
                        "src_school": "Pros", "src_div": "PRO",
                        "dest_school": sg["dest_school"] if sg else "",
                        "dest_div": sg["dest_div"] if sg else "",
                        "signed": bool(sg), "cycle": cycle_key})
    out.sort(key=lambda d: (-d["str"], d["pid"]))
    return out


def _resolve_program(progs: dict, name: str) -> str | None:
    """Forgivingly map a typed school name to a real program key in `progs`: exact, then
    case-insensitive exact, then a UNIQUE case-insensitive prefix, then a UNIQUE substring.
    So 'texas' → Texas and 'Wake' → Wake Forest, but an ambiguous stub returns None instead of
    silently dropping the pick onto the wrong club."""
    name = (name or "").strip()
    if not name:
        return None
    if name in progs:
        return name
    low = name.lower()
    exact = [s for s in progs if s.lower() == low]
    if len(exact) == 1:
        return exact[0]
    pref = [s for s in progs if s.lower().startswith(low)]
    if len(pref) == 1:
        return pref[0]
    sub = [s for s in progs if low in s.lower()]
    if len(sub) == 1:
        return sub[0]
    return None


def sign_pro(seed: int, pid: str, dest_school: str, cycle_key: str | None = None) -> dict:
    """Sign a free-agent pro to ANY program (any division). Stores the intent; the pro is
    persisted onto the roster at commit. `dest_school` empty → unsign (back to free agent).
    The school is resolved forgivingly (case/partial), so a near-miss still lands rather than
    silently doing nothing."""
    w = load_world(seed)
    if not w:
        return {"ok": False, "error": "no world"}
    from app import overrides as ov
    cycle_key = cycle_key or f"{w['year']}-preseason"
    dest_school = (dest_school or "").strip()
    if not dest_school:
        ov.pro_unsign(w["year"], cycle_key, pid)
        return {"ok": True, "pid": pid, "dest": ""}
    salt = active_salt(seed)
    from app import pros
    for gender in worldconfig.active_genders():
        pro = next((p for p in pros.generate_pros(salt, gender, cycle_key) if p.pid == pid), None)
        if pro is not None:
            progs = _flat_programs(gender)
            match = _resolve_program(progs, dest_school)
            if not match:
                return {"ok": False, "error": f"No program matches “{dest_school}”. "
                        f"Pick one from the list."}
            err = _citizenship_error(pro, match)       # service academies: US only
            if err:
                return {"ok": False, "error": err}
            prog = progs[match]
            ov.pro_set_sign(w["year"], cycle_key, gender, pid, match, prog.division)
            return {"ok": True, "pid": pid, "dest": match, "div": prog.division}
    return {"ok": False, "error": "unknown pro"}


def unsign_pro(seed: int, pid: str, cycle_key: str | None = None) -> dict:
    """Drop a pro's signing — back to an unsigned free agent."""
    from app import overrides as ov
    w = load_world(seed)
    if not w:
        return {"ok": False}
    ov.pro_unsign(w["year"], cycle_key or f"{w['year']}-preseason", pid)
    return {"ok": True, "pid": pid}


# The portal cycles a free-agent pro can be viewed/signed in this year (deterministic
# cohorts, regenerable — so an UNSIGNED pro's profile resolves without being on a roster).
def _pro_cycles(year: int) -> list[str]:
    return [f"{year}-preseason", f"{year}-fall"]


def find_pro(seed: int, pid: str):
    """Locate a free-agent pro by pid across this year's cohorts (regenerated on demand).
    Returns (Prospect, gender, cycle_key, signed_dest_or_'') or None — lets the player page
    render an unsigned pro (STR + attributes) BEFORE they're signed onto any roster."""
    from app import pros
    from app import overrides as ov
    w = load_world(seed)
    if not w:
        return None
    salt = active_salt(seed)
    for cyc in _pro_cycles(w["year"]):
        signs = ov.pro_get_signs(w["year"], cyc)
        for gender in worldconfig.active_genders():
            for p in pros.generate_pros(salt, gender, cyc):
                if p.pid == pid:
                    dest = signs.get(pid, {}).get("dest_school", "")
                    return (p, gender, cyc, dest)
    return None


def _commit_pro_signings(seed: int, cycle_key: str) -> int:
    """Persist the pros the user signed this cycle onto their clubs (world_roster + the
    world_pro ledger), displacing each club's weakest player if it's full. Idempotent per
    cycle via the ledger marker; the shared-budget deduction (`_pro_spend`) then reads it."""
    from app import pros
    from app import overrides as ov
    w = get_or_create(seed)
    signs = ov.pro_get_signs(w["year"], cycle_key)
    conn = _db()
    if conn.execute("SELECT 1 FROM world_pro WHERE world_id=? AND year=? AND cycle=? LIMIT 1",
                    (w["id"], w["year"], cycle_key)).fetchone():
        conn.close()
        return 0                                       # already committed this cycle
    if not signs:
        conn.close()
        return 0
    salt = active_salt(seed)
    window = cycle_key.split("-", 1)[1] if "-" in cycle_key else cycle_key   # 'preseason' / 'fall'
    prime(seed)
    rosters = developed_rosters(w)
    roster_rows, pro_rows, arch_rows = [], [], []
    for gender in worldconfig.active_genders():
        cohort = {p.pid: p for p in pros.generate_pros(salt, gender, cycle_key)}
        cohort_list = list(cohort.values())
        for pid, sg in signs.items():
            if sg["gender"] != gender:
                continue
            p = cohort.get(pid)
            if not p:
                continue
            d, school = sg["dest_div"], sg["dest_school"]
            roster = rosters.get((d, gender), {}).get(school)
            if roster is None:
                continue                               # program not present/active — skip
            if len(roster) >= roster_cap(d):
                weakest = min(roster, key=lambda q: q.current_overall())
                conn.execute("DELETE FROM world_roster WHERE world_id=? AND year=? AND pid=?",
                             (w["id"], w["year"], weakest.pid))
                roster.remove(weakest)
            roster.append(p)
            roster_rows.append((w["id"], w["year"], d, gender, school, p.pid,
                                json.dumps(prospect_to_dict(p))))
            pro_rows.append((w["id"], w["year"], cycle_key, gender, d, school, p.pid,
                             round(pros.pro_cost(p, cohort_list), 2)))
            # durable Portal Rankings record — a pro is an IN acquisition from the "Pros" pool
            arch_rows.append((w["id"], w["year"], window, gender, "pro", p.pid,
                              getattr(p, "name", p.pid), round(p.str_value(), 1),
                              "Pros", "PRO", school, d))
    if roster_rows:
        conn.executemany("DELETE FROM world_roster WHERE world_id=? AND year=? AND pid=?",
                         [(w["id"], w["year"], r[5]) for r in roster_rows])
        conn.executemany("INSERT INTO world_roster VALUES (?,?,?,?,?,?,?)", roster_rows)
    conn.execute("INSERT INTO world_pro VALUES (?,?,?,?,?,?,?,?)",
                 (w["id"], w["year"], cycle_key, "", "", "", "", 0.0))
    if pro_rows:
        conn.executemany("INSERT INTO world_pro VALUES (?,?,?,?,?,?,?,?)", pro_rows)
    conn.execute("DELETE FROM world_portal_move WHERE world_id=? AND year=? AND cycle=? AND kind='pro'",
                 (w["id"], w["year"], window))
    if arch_rows:
        conn.executemany("INSERT INTO world_portal_move VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", arch_rows)
    conn.commit()
    conn.close()
    _base_cache.clear(); _dev_cache.clear(); _primed.clear()
    reset_caches()
    return len(pro_rows)


# --------------------------------------------------------------------------
def preseason_portal_proposals(rosters: dict, gender: str) -> list[dict]:
    """Deterministic week-0 reshuffle for one gender (riders only; cascades are
    re-derived at resolve). Thin wrapper over the shared `_FPPlanner` discovery."""
    if not any(g == gender for (_d, g) in rosters):
        return []
    # Sources span every division (scan_rosters), but a rider may only be PLACED into an
    # ACTIVE division — never into a dormant one that the season never simulates.
    plan = _FPPlanner(rosters, {}, gender, active_divs=worldconfig.active_divisions())
    if not plan.schools:
        return []
    plan.discover(worldconfig.preseason_portal_cap())
    return plan.moves


def run_preseason_portal(seed: int = DEFAULT_SEED) -> dict:
    """Discover RIDER intents across all active universes and persist them
    ('proposed'). Cascades are NOT stored — they re-derive from these riders at
    every view/edit/commit. Idempotent: only seeds a slate that doesn't exist yet
    (so it never clobbers the user's edits or a committed run)."""
    from app import overrides as ov
    w = get_or_create(seed)
    # Pros are FREE AGENTS here — a deterministic cohort (regenerated on demand) the user signs
    # to any club through the portal; they are NOT auto-injected. Signed pros are persisted onto
    # their clubs only at commit (`_commit_pro_signings`). So nothing to seed for pros here.
    if ov.ps_get_proposals(w["year"]):                 # already seeded / committed
        return {"event": "preseason_portal_exists", "year": w["year"]}
    # Source rosters the SAME way the Bureau boards do — every division, live — so the
    # portal never comes up empty just because a division is dormant/persisted-stale.
    rosters = scan_rosters(seed)
    total = 0
    for gender in worldconfig.active_genders():
        props = preseason_portal_proposals(rosters, gender)
        riders = [{**m, "status": "proposed"} for m in props if m["cascade_from"] is None]
        ov.ps_set_proposals(w["year"], gender, riders)
        total += len(riders)
    return {"event": "preseason_portal_pending", "year": w["year"], "proposals": total}


def rescan_preseason_portal(seed: int = DEFAULT_SEED) -> dict:
    """Force a fresh scan: clear this year's stored slate and re-run discovery. Lets a
    'sticky' slate (one that was seeded/committed/dropped once and never re-scans on its
    own) be regenerated without starting a new league. Returns the seeding result."""
    from app import overrides as ov
    w = get_or_create(seed)
    ov.ps_clear_year(w["year"])
    return run_preseason_portal(seed)


def preseason_portal_debug(seed: int = DEFAULT_SEED) -> dict:
    """Why the slate is what it is: per active gender, how many lower-division starters
    are top-2 on their team, how many clear a higher division's median, and how many are
    BOTH (the riders), plus the per-division median bar. Surfaced when the slate is empty
    so an unexpected 0 is explainable rather than mysterious."""
    rosters = scan_rosters(seed)
    out: dict = {}
    for gender in worldconfig.active_genders():
        if not any(g == gender for (_d, g) in rosters):
            continue
        plan = _FPPlanner(rosters, {}, gender, active_divs=worldconfig.active_divisions())
        top2 = clears = both = pool = 0
        for s in plan.schools:
            if plan.div_of[s] == "D1":
                continue
            for p in plan.pool[s]:
                if p.walk_on or _career_transfers(p) != 0:
                    continue
                pool += 1
                val = plan._sv(p)
                is_top2 = plan.line_of(s, val) <= 2
                is_over = plan.over_div(s, val) is not None
                top2 += is_top2; clears += is_over; both += (is_top2 and is_over)
        out[gender] = {"div_level": {k: round(v, 1) for k, v in plan.div_level.items()},
                       "scanned": pool, "top2": top2, "clear_higher_div": clears,
                       "riders": both, "schools": len(plan.schools)}
    return out


def resolve_preseason_portal(seed: int = DEFAULT_SEED) -> dict:
    """Resolve the stored rider intents into the full move slate (riders + derived
    cascades) per gender, on a fresh snapshot — recomputed on every view and at
    commit so redirects / adds / drops always yield a correct, cap-safe cascade."""
    from app import overrides as ov
    w = get_or_create(seed)
    rosters = scan_rosters(seed)          # same all-division live source as seeding
    out: dict = {}
    for gender in worldconfig.active_genders():
        riders = [r for r in ov.ps_get_proposals(w["year"])
                  if r["gender"] == gender and r["cascade_from"] is None
                  and r["status"] != "rejected"]
        riders.sort(key=lambda r: (-r["str"], r["pid"]))      # best pick fits first
        plan = _FPPlanner(rosters, {}, gender, active_divs=worldconfig.active_divisions())
        plan.touched.update(r["pid"] for r in riders)   # a rider is never a cascade victim
        for r in riders:
            entry = plan.by_pid.get(r["pid"])
            if not entry:
                continue                                       # not on a roster
            src, p = entry
            plan.place(p, src, dest=r["dest_school"], gated=False)
        out[gender] = ov.dedupe_slate(plan.moves, "preseason_portal")   # see resolve_fall_portal
    return out


def _archive_portal_moves(seed: int, w: dict, gender: str, cycle: str, moves: list) -> None:
    """Write this window's committed transfer moves to the durable `world_portal_move`
    archive (riser = a rise UP, cascade = a displaced demotion DOWN). Idempotent per
    (world, year, gender, cycle) so a re-commit replaces rather than duplicates. This is
    the record the Portal Rankings board reads — it outlives the transient slate tables
    the rollover clears. (Pros live in `world_pro`, read separately.)"""
    conn = _db()
    try:
        # scope the replace to the transfer kinds only — pro archive rows (kind='pro') for the
        # same cycle are written separately by _commit_pro_signings and must not be wiped here.
        conn.execute("DELETE FROM world_portal_move WHERE world_id=? AND year=? AND gender=? "
                     "AND cycle=? AND kind!='pro'", (w["id"], w["year"], gender, cycle))
        rows = [(w["id"], w["year"], cycle, gender,
                 "riser" if m.get("cascade_from") is None else "cascade",
                 m["pid"], m.get("name", ""), float(m.get("str", 0.0)),
                 m["src_school"], m["src_div"], m["dest_school"], m["dest_div"])
                for m in moves]
        if rows:
            conn.executemany("INSERT INTO world_portal_move VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        conn.commit()
    finally:
        conn.close()


def portal_moves(seed: int, year: int, gender: str | None = None) -> list[dict]:
    """Every archived committed portal move for a year — risers (up), cascades (down), and
    pros (in from the Pros pool). Each: cycle, gender, kind, pid, name, str, src/dest school+div.
    The durable source for the Portal Rankings board (survives the rollover)."""
    w = load_world(seed)
    if not w:
        return []
    conn = _db()
    try:
        q = ("SELECT cycle,gender,kind,pid,name,str,src_school,src_div,dest_school,dest_div"
             " FROM world_portal_move WHERE world_id=? AND year=?")
        args: list = [w["id"], year]
        if gender in ("men", "women"):
            q += " AND gender=?"
            args.append(gender)
        rows = conn.execute(q, args).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


_CYCLE_ORDER = {"preseason": 0, "fall": 1}   # chronological order WITHIN a season year


def all_portal_moves(seed: int = DEFAULT_SEED,
                     gender: str | None = None) -> list[dict]:
    """EVERY archived portal move in the world's history, oldest first.

    `portal_moves` is scoped to one year because the Portal Rankings board grades one
    transfer class at a time. The Wire is the other question — where has this player
    been — so it reads the whole archive and orders it chronologically: by year, then
    preseason before fall (preseason runs at week 0, the fall portal after the ITA
    opener). A move's `src_div`/`dest_div` are the divisions AT THE TIME and are kept
    as archived; a program that has since changed division must not have its old rows
    rewritten (the JVC went D1 -> D2, and those seasons really were played in D1)."""
    w = load_world(seed)
    if not w:
        return []
    conn = _db()
    try:
        q = ("SELECT year,cycle,gender,kind,pid,name,str,"
             "src_school,src_div,dest_school,dest_div"
             " FROM world_portal_move WHERE world_id=?")
        args: list = [w["id"]]
        if gender in ("men", "women"):
            q += " AND gender=?"
            args.append(gender)
        rows = [dict(r) for r in conn.execute(q, args).fetchall()]
    finally:
        conn.close()
    rows.sort(key=lambda m: (m["year"], _CYCLE_ORDER.get(m["cycle"], 9), m["name"]))
    return rows


def portal_years(seed: int = DEFAULT_SEED) -> list[int]:
    """Years with archived portal data, newest first (for the board's year dropdown)."""
    w = load_world(seed)
    if not w:
        return []
    conn = _db()
    try:
        ys = [r[0] for r in conn.execute(
            "SELECT DISTINCT year FROM world_portal_move WHERE world_id=? ORDER BY year DESC",
            (w["id"],)).fetchall()]
    finally:
        conn.close()
    return ys


def commit_preseason_portal(seed: int = DEFAULT_SEED) -> dict:
    """Resolve the (edited) slate and relocate every mover — riders AND their cascade
    demotions — with a plain `set_move`. The whole committed slate is kept in the
    table (status='committed') so the review screen can show what happened and a
    re-open won't re-propose the same players."""
    from app import overrides as ov
    w = get_or_create(seed)
    year = w["year"]
    resolved = resolve_preseason_portal(seed)          # {gender: [moves]}
    moved = 0
    for gender, moves in resolved.items():
        rows = [{**m, "status": "committed"} for m in moves]
        ov.ps_set_proposals(year, gender, rows)        # the slate is now the committed moves
        for m in rows:
            ov.set_move(m["pid"], m["dest_school"])
            moved += 1
        _archive_portal_moves(seed, w, gender, "preseason", moves)   # durable record for Portal Rankings
    signed = _commit_pro_signings(seed, f"{year}-preseason")   # persist the free-agent pros the user signed
    reset_caches(); _primed.pop(seed, None)
    return {"event": "preseason_portal_committed", "year": year, "moved": moved, "pros": signed}


def redirect_preseason_portal_mover(seed: int, pid: str, dest_school: str) -> dict:
    """Send a proposed rider to a different destination; the cascade recomputes at
    the next resolve."""
    from app import overrides as ov
    w = get_or_create(seed)
    rosters = developed_rosters(w)
    for gender in worldconfig.active_genders():
        rider = next((r for r in ov.ps_get_proposals(w["year"])
                      if r["gender"] == gender and r["pid"] == pid
                      and r["cascade_from"] is None), None)
        if not rider:
            continue
        plan = _FPPlanner(rosters, {}, gender)
        if dest_school not in plan.div_of:
            return {"error": "unknown destination"}
        err = _citizenship_error(plan.by_pid.get(pid, (None, None))[1], dest_school)
        if err:
            return {"error": err}
        ov.ps_set_dest(w["year"], gender, pid, dest_school, plan.div_of[dest_school])
        return {"ok": True, "pid": pid, "dest": dest_school}
    return {"error": "rider not found"}


def add_preseason_portal_mover(seed: int, pid: str, dest_school: str | None = None) -> dict:
    """Add a player the sim didn't propose (your pick). With no destination the engine
    pre-fills the best fit (ungated — your call). They ride the same resolve/commit
    path, so they pick up the cascade balance like any sim mover."""
    from app import overrides as ov
    w = get_or_create(seed)
    rosters = developed_rosters(w)
    found = _fp_find(seed, w, rosters, pid)
    if not found:
        return {"error": "player not on a current roster"}
    gender, src, src_div, p, plan = found
    if dest_school in (None, "", "auto"):
        dest_school = plan.place(p, src, dest=None, gated=False)   # throwaway planner
    if not dest_school or dest_school not in plan.div_of:
        return {"error": "no destination found — pick a school"}
    err = _citizenship_error(p, dest_school)
    if err:
        return {"error": err}
    ov.ps_upsert_proposal(w["year"], gender, {
        "pid": pid, "name": getattr(p, "name", ""), "src_school": src,
        "dest_school": dest_school, "src_div": src_div, "dest_div": plan.div_of[dest_school],
        "str": round(_str_of({}, p), 1), "status": "proposed", "cascade_from": None})
    return {"ok": True, "pid": pid, "dest": dest_school, "gender": gender}


def _bake_fall_moves(seed: int, w: dict, rosters: dict) -> int:
    """Make the season's committed fall-portal moves permanent: relocate each mover
    from their source to their destination roster list (so next year's persisted
    roster has them at the new school), clear the live move override, and clear the
    year's portal slate. Runs AFTER `_record_world_history` (which needs the
    override + portal table) and BEFORE graduation/rollover (so they roll over as
    destination players, and the year-end `transfer_portal` sees their used-up
    career transfer and leaves them be)."""
    from app import overrides as ov
    rows = [r for r in ov.get_proposals(w["year"]) if r["status"] == "committed"]
    baked = 0
    for r in rows:
        src_list = rosters.get((r["src_div"], r["gender"]), {}).get(r["src_school"])
        if src_list is not None:
            moved = next((p for p in src_list if p.pid == r["pid"]), None)
            if moved is not None:
                src_list.remove(moved)
                rosters.setdefault((r["dest_div"], r["gender"]), {}) \
                       .setdefault(r["dest_school"], []).append(moved)
                baked += 1
        ov.clear_move(r["pid"])
    ov.clear_year(w["year"])
    return baked


def assign_pool_walkons(rosters: dict, signings: dict, seed: int, year: int) -> int:
    """No junior in the pool goes unsigned: every recruit left over after the season's
    signings is claimed as a walk-on by a D3/D4 program with an open roster slot
    (strongest programs get first pick of the best leftover). Auto-generation
    (refill_walkons) then covers only the seats still empty after this. D1/D2 do NOT
    claim leftover — they take only the recruits who actively signed with them."""
    placed = 0
    for gender in GENDERS:
        if not any(g == gender for (_, g) in rosters):
            continue
        signed = {p.pid for lst in signings.get(gender, {}).values() for p in lst}
        leftover = [p for p in national_class(seed, year, gender) if p.pid not in signed]
        if not leftover:
            continue
        from . import recruit_economy
        # [strength, roster, room, division, gate, us_only] open D3/D4 seats
        slots: list = []
        for (division, g), schools in rosters.items():
            if g != gender or not autogen_walkons(division):
                continue
            cap = roster_cap(division)
            progs = {p.school: p for p in load_division(division, gender).programs}
            for school, roster in schools.items():
                room = cap - len(roster)
                if room > 0:
                    prog = progs.get(school)
                    st = prog.strength if prog else 0.5
                    # D4 admits only above its academic gate, even for leftover walk-ons.
                    gate = (recruit_economy.d4_academic_min(prog, year, str(seed))
                            if division == "D4" and prog is not None else 0.0)
                    slots.append([st, roster, room, division, gate,
                                  us_only_program(school)])
        slots.sort(key=lambda x: -x[0])        # best leftover (ranked) → strongest open programs
        consumed: set = set()

        def _next_for(gate, div, us_only):
            for j, q in enumerate(leftover):
                if j in consumed:
                    continue
                if div == "D4" and int(getattr(q, "academic_rating", 79) or 79) < gate:
                    continue                   # doesn't clear this D4 program's admissions bar
                if us_only and not is_domestic_player(q):
                    continue                   # service academy: US citizens only
                return j
            return None

        progressed = True
        while progressed:                      # one recruit per open slot per pass (spreads leftover)
            progressed = False
            for slot in slots:
                if slot[2] <= 0:
                    continue
                j = _next_for(slot[4], slot[3], slot[5])
                if j is None:
                    continue
                consumed.add(j)
                fr = copy.deepcopy(leftover[j])
                fr.class_year = "Fr"; fr.committed = True; fr.walk_on = True
                slot[1].append(fr); slot[2] -= 1; placed += 1; progressed = True
    return placed


def refill_walkons(rosters: dict, year: int, seed: int) -> int:
    """Top D3/D4 rosters back up to size with AUTO-GENERATED walk-on freshmen — only
    the seats still empty after real pool recruits (signings + leftover sweep) are
    placed. D1/D2 get no walk-on DEPTH: they fill it from the recruiting pool only, so
    a D1/D2 program that doesn't sign enough simply carries fewer walk-ons.

    EVERY division, though, gets a hard floor of its LINEUP SIZE (`ncaa.
    lineup_size` — the singles card its dual format actually fields: 10 for D1/D4,
    8 for D2/D3). D1 carrying no walk-on depth is about keeping D1 rosters SMALLER
    than D2/D3/D4, so the portals can oversign and rebuild a roster quickly without
    cutting a pile of players (owner rule). It was never about letting a program fall
    below a playable lineup: under the card there is no lineup at all, the engine
    indexes every court, and it used to crash mid-bracket. The floor is enforced
    HERE, on the real roster that gets persisted and indexed, rather than by
    synthesising a phantom player at squad-build time (whose pid existed nowhere, so
    championship links 404'd). Note under the 10-singles D1 format the 6-scholarship
    core no longer covers the card, so a D1 program routinely carries floor walk-ons
    on courts 7-10 — that's the owner's depth-matters design, not a leak."""
    from . import recruit_economy
    intake = 0
    for (division, gender), schools in rosters.items():
        depth = autogen_walkons(division)          # D1/D2: no game-generated DEPTH
        cap = roster_cap(division)
        floor = lineup_size(division)
        progs = {p.school: p for p in load_division(division, gender).programs}
        for school, roster in schools.items():
            prog = progs.get(school)
            # D1/D2 top up only to the lineup floor; D3/D4 fill their whole cap.
            target = cap if depth else floor
            need = target - len(roster)
            if not prog or need <= 0:
                continue
            # D4 admits only above its academic gate — auto-gen walk-ons included, so a
            # D4 roster stays academically self-consistent.
            d4_min = (recruit_economy.d4_academic_min(prog, year, str(seed))
                      if division == "D4" else None)
            prng = random.Random(f"{seed}|{prog.key}|walkon|{year}")
            # A service academy's auto-gen depth is American too — US citizens only.
            _rw = ({"us": 1.0} if us_only_program(school)
                   else worldconfig.region_weights())
            name_fn = make_name_picker(random.Random(f"{seed}|{prog.key}|wn|{year}"),
                                       gender=_pick_gender(gender),
                                       region_weights=_rw)
            for k in range(need):
                name, country = name_fn()
                # A walk-on persona, drawn from its division x gender band
                # (ncaa.WALKON_BAND) — a known quantity below the recruited core,
                # never a phantom blue-chip.
                talent = walkon_talent(division, gender, prng)
                fr = generate_prospect(prng, name, country, gender=_pick_gender(gender),
                                       talent=talent, pid=make_pid(prog.key, "wo", year, k))
                fr.class_year = "Fr"; fr.walk_on = True
                if d4_min is not None and fr.academic_rating < d4_min:
                    fr.academic_rating = int(min(99, round(d4_min) + prng.randint(0, 7)))
                roster.append(fr)
                intake += 1
    return intake


def _normalize(rosters: dict, protect: set | None = None) -> dict:
    """Bring every roster to its division cap — by RELOCATING the surplus through
    the portal, never by deleting players. Signed recruits always join their new
    team, and a medical-redshirt returner (`protect`) is never the one moved, so
    over-cap is resolved by sending the weakest *movable* player to the best
    program (same gender) that has an open slot — dropping a level for playing time
    if their own is full. Only a player nobody has room for departs the sim.

    Keep priority (highest first): medical-redshirt returner → just-signed
    freshman → current ability. So the marginal returning walk-on makes way for a
    recruit, and the promised fifth year is the last to go — exactly the
    recruiting/redshirt contract the rest of the rollover assumes."""
    protect = protect or set()
    moved = departed = 0

    def keep_rank(p):
        rs = 2 if p.pid in protect else 0          # redshirt returner: protect hardest
        fr = 1 if p.class_year == "Fr" else 0      # this cycle's signed recruit
        return (rs, fr, p.current_overall())

    for gender in GENDERS:
        progs = _flat_programs(gender)
        pool: dict[str, list] = {}
        div_of: dict[str, str] = {}
        for (division, g), schools in rosters.items():
            if g != gender:
                continue
            for school, roster in schools.items():
                pool[school] = roster
                div_of[school] = division
        if not pool:
            continue
        prestige = {s: progs[s].prestige for s in pool if s in progs}

        def open_slot(s):
            return s in progs and len(pool[s]) < roster_cap(div_of.get(s, ""))

        # 1) trim every over-cap roster, collecting the surplus (best movers first)
        surplus: list[tuple] = []
        for school, roster in pool.items():
            cap = roster_cap(div_of.get(school, ""))
            if len(roster) <= cap:
                continue
            roster.sort(key=keep_rank, reverse=True)
            cut = roster[cap:]
            keep = roster[:cap]
            keep.sort(key=lambda p: p.current_overall(), reverse=True)
            roster[:] = keep
            for p in cut:
                surplus.append((p, div_of.get(school, "")))

        # 2) place each surplus player: best open program in their level, else one
        #    step down (depth chases a roster spot), else up; strongest pick first
        surplus.sort(key=lambda t: t[0].current_overall(), reverse=True)
        for p, src_div in surplus:
            dest = None
            blk = blocked_schools_for(p)       # service academies, for an international
            for div in (src_div, _DOWN_DIV.get(src_div), _UP_DIV.get(src_div)):
                if not div:
                    continue
                cands = [s for s in pool if div_of.get(s) == div and open_slot(s)
                         and s not in blk]
                if cands:
                    dest = max(cands, key=lambda s: prestige.get(s, 0.0))
                    break
            if dest is None:
                departed += 1                          # nobody has room — leaves the sim
                continue
            p.walk_on = True                            # joins as depth
            pool[dest].append(p)
            moved += 1

    return {"relocated": moved, "departed": departed}


def coach_carousel(rosters: dict, player_str: dict, rng: random.Random, gender: str,
                   *, year: int | None = None) -> dict:
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
        coachreg.swap_head_coaches(gender, sdiv, src, ddiv, dest,
                                   year=BASE_YEAR + year if year is not None else None)
        used.add(src); used.add(dest); moves += 1

        # Followers: src's coach is now at dest. Up to half of src's roster may
        # follow, gated to players who'd make dest's lineup (its last-starter STR,
        # sized by dest's division format).
        sr = rosters[(sdiv, gender)][src]
        dr = rosters[(ddiv, gender)][dest]
        _lu = lineup_size(ddiv)
        dstr = sorted((_str_of(player_str, p) for p in dr), reverse=True)
        floor = (dstr[_lu - 1] if len(dstr) >= _lu else (dstr[-1] if dstr else 0.0)) - 1.0
        # A coach who lands a service-academy job brings only their American players —
        # the academy can't admit an international follower.
        eligible = [p for p in sr if _str_of(player_str, p) >= floor
                    and admits_nationality(dest, p)]
        cap = min(len(sr) // 2, len(eligible))
        k = rng.randint(0, cap) if cap > 0 else 0
        for p in (rng.sample(eligible, k) if k else []):
            sr.remove(p); dr.append(p)
            followers += 1
        if k:
            sample.append((src, dest, k))
    return {"moves": moves, "followers": followers, "sample": sample[:6]}


def finalize_rollover(rosters: dict, signings: dict, player_str: dict, *,
                      seed: int, year: int, medical_redshirts: set | None = None) -> dict:
    """The post-season: graduate → coach carousel → transfer portal (per gender)
    → bring in the signed class → refill with walk-ons. Mutates `rosters`.
    `medical_redshirts` are season-ending-injury pids granted a returning RS year."""
    rng = random.Random(f"{seed}|finalize|{year}")
    grads = graduate(rosters, medical_redshirts)
    carousel = {"moves": 0, "followers": 0, "sample": []}
    for gender in GENDERS:
        if not any(g == gender for (_, g) in rosters):
            continue
        cr = coach_carousel(rosters, player_str, rng, gender, year=year)
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
    # Resolve over-cap by RELOCATING the surplus through the portal (signed recruits
    # keep their seat; a promised RS returner is never moved) — do it BEFORE the
    # walk-on fills so displaced real players claim open slots ahead of auto-gen.
    overflow = _normalize(rosters, protect=medical_redshirts)
    pooled = assign_pool_walkons(rosters, signings, seed, year)   # leftover juniors → D3/D4 walk-ons
    intake = refill_walkons(rosters, year + 1, seed)              # auto-gen only the still-empty seats
    return {"graduated": grads, "committed": committed, "walkons": intake, "pool_walkons": pooled,
            "coach_moves": carousel["moves"], "coach_followers": carousel["followers"],
            "coach_sample": carousel["sample"],
            "portal_relocated": overflow["relocated"], "portal_departed": overflow["departed"],
            **{f"portal_{k}": v for k, v in portal.items()}}


# ==========================================================================
# Cross-classification (cross-division) non-conference scheduling.
#   • Adjacent classes (D1↔D2, D2↔D3) plus elite (high-academic) D3 reaching D1.
#   • Geography-driven (same / adjacent region) and capped per team per year.
#   • The higher classification hosts.
# ==========================================================================
from .ncaa import location  # noqa: E402  (geography for cross-division pairing)


def _allowed_cross(a, b) -> bool:
    """Is a cross-class dual between programs a, b allowed? Geography (the same /
    adjacent-region pool in `cross_schedule`) plus the per-team cap already keep
    cross-class play local and rare. On top of that:
      • adjacent classes always pair (D1-D2, D2-D3, D3-D4);
      • a D2 may reach down to D4 anywhere nearby;
      • a D1 reaches down to a D3/D4 only when the smaller school is a PRESTIGE peer
        (the lifted academic programs) OR a same-region neighbor — a top-tier program
        doesn't drop two or three classes for a random small school far afield."""
    if a.division == b.division:
        return False
    ra, rb = DIV_RANK[a.division], DIV_RANK[b.division]
    if abs(ra - rb) == 1:
        return True
    hi, lo = (a, b) if ra < rb else (b, a)        # hi = higher classification
    if hi.division != "D1":                        # D2 reaching D4 — geography is enough
        return True
    return lo.prestige >= CROSS_D1_PRESTIGE or hi.region == lo.region


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
            # Nearby pool = same region + adjacent regions, restricted to OTHER
            # classifications. Weight each candidate by class proximity so adjacent
            # classes dominate and reaching two / three up (a D4 at a nearby D1) stays
            # an occasional sliver rather than the bulk — D1 is large and everywhere,
            # so unweighted picks would otherwise bury a D4 in D1 games.
            pra = DIV_RANK[p.division]
            xpool, xw = [], []
            for r in (p.region, *REGION_ADJACENT.get(p.region, ())):
                for o in by_region.get(r, ()):
                    if o.division == p.division or o.school == p.school:
                        continue
                    xpool.append(o)
                    xw.append(CROSS_GAP_DECAY ** (abs(pra - DIV_RANK[o.division]) - 1))
            tries = 0
            while count[p.school] < MAX_CROSS and tries < 40 and xpool:
                tries += 1
                o = rng.choices(xpool, weights=xw)[0]
                if count[o.school] >= MAX_CROSS:
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
        # Offseason ladder — ONE step per advance, so each is something you watch
        # happen instead of a silent stage inside the rollover click:
        #   awards (held by the web layer) → WORLD CUPS → rollover → PRO OFFSEASON
        # The cups run first because they field the year's rosters pre-graduation.
        if not cups_done(w):
            return run_world_cups(seed, w)
        return _finalize_year(seed, w)
    # Week 0, BEFORE anything college happens: Jefferson's high schools play their
    # season. Its seniors are the state's entries on this year's recruit board, so they
    # have to have finished playing before the board is read — and on a NEW SAVE that
    # means before the first college season, which is why this is not gated on year > 0
    # the way the pro rung below is.
    if w["week"] == 0 and not jhsaa_done(w):
        return run_jhsaa(seed, w)

    # Fresh year, week 0: the pro league drafts the class that just graduated. Its own
    # step, before the new college season plays a dual.
    if w["week"] == 0 and w["year"] > 0 and not pros_rolled(w):
        return run_pro_offseason(seed, w)

    # Fall transfer portal barrier: once EVERY active universe has finished its
    # ITA opener and is holding in 'fall_portal', pause the world here. First
    # encounter generates proposals; thereafter we keep holding until the user
    # commits (which releases the hold). An empty slate releases immediately.
    if sm.FALL_PORTAL_ENABLED and _all_in_fall_portal(seed, w):
        from app import overrides as ov
        existing = ov.get_proposals(w["year"])
        if not existing:
            res = run_fall_portal(seed)
            if res["proposals"] == 0:
                _release_fall_portal(seed, w)
                return {"event": "fall_portal", "year": w["year"], "proposals": 0,
                        "released": True}
            return res
        pending = [r for r in existing if r["status"] in ("proposed", "approved")]
        if pending:
            return {"event": "fall_portal_pending", "year": w["year"],
                    "proposals": len(pending)}
        _release_fall_portal(seed, w)           # safety net: nothing left pending
        return {"event": "fall_portal", "year": w["year"], "released": True}

    prime(seed)
    cross = 0
    if w["week"] == 0:                      # start of year: play the cross-division slate
        _commit_pro_signings(seed, f"{w['year']}-preseason")   # persist any free-agent pros the user signed
        cross = simulate_cross(seed)
    played = 0
    for (d, g) in _active_unis():
        sid = universe_sid(seed, w, d, g)
        # Hold any universe that's finished its ITA at the fall-portal boundary
        # (don't advance it) so they all converge there before the portal runs;
        # the barrier above fires once every active universe has arrived.
        if sm.load_season(sid)["phase"] not in ("complete", "fall_portal"):
            res = sm.advance(sid)
            played += res.get("played", 0)

    # Recruiting drip: flip a few recent commits, then sign a slice of each
    # active gender's class this week.
    conn = _db()
    signed = 0
    flips = 0
    window = _signing_window(seed, w)        # drip across the whole regular season
    # Precompute every active gender's junior circuit in parallel up front, so the
    # per-gender signing below is a cache hit instead of running men's then women's
    # circuit back to back (the dominant cost of the first advance of a world).
    prime_recruit_classes(seed, w["year"])
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
    fall_movers = ov.committed_movers(world["year"])   # split-season (two-stint) movers
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
                # A fall-portal mover already carries an ITA stint (stint 0) for
                # this year; here we append their destination stint (stint 1, the
                # regular season + postseason at the new school). Everyone else gets
                # the usual single full-season entry (stint 0).
                stint = 1 if p.pid in fall_movers else 0
                phase = "regular_post" if stint else "full"
                if any(h.get("year") == year and h.get("stint", 0) == stint
                       for h in p.history):
                    continue                      # already recorded this stint
                played_school = moves.get(p.pid, school)   # honor editor / portal moves
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
                    "stint": stint, "phase": phase,
                })


def cup_rosters(world: dict) -> dict:
    """Every REAL player in the save, for the national-team cups: the ACTIVE
    universes developed to now (the season just played), plus the DORMANT ones'
    persisted rosters. Read from `world_roster` — never `scan_rosters`, which
    re-derives dormant divisions from the generator instead of reading the players
    this save actually holds."""
    out = dict(developed_rosters(world))
    conn = _db()
    stored = _load_rosters(conn, world["id"], world["year"])      # unis=None -> every universe
    conn.close()
    for uni, schools in stored.items():
        out.setdefault(uni, schools)                             # dormant only; active stays developed
    return out


def departing_now(seed: int = DEFAULT_SEED) -> list[tuple]:
    """The cohort that will graduate at THIS year's rollover, read from the LIVE
    rosters — same predicate (`_departing`) and same row shape as the archive
    `_save_graduates` writes: (division, gender, pid, str, ovr, data).

    ‼️ This exists for ONE caller: founding a pro league. `world_graduates` is only
    written AT a rollover, so on a world that has not rolled over yet the table is
    empty and every consumer correctly reads "no graduates" — which for the GTT
    founding draft meant an inaugural league of 100% generated players standing
    beside a college world holding tens of thousands of real ones. The shortage was
    never real; the ARCHIVE just did not exist yet.

    It is deliberately NOT a fallback inside `_world_graduates`. Everywhere else, an
    empty class means the world binding is broken (see `gtt._active_world_seed`), and
    silently substituting live players there would turn a should-be-visible fault
    into plausible-looking data — the failure mode this codebase keeps relearning.

    Resolves through `load_world` and returns [] when the world is absent: it must
    never `get_or_create` a parallel universe out of a stale seed.
    """
    world = load_world(seed)
    if not world:
        return []
    rows: list[tuple] = []
    for (d, g), schools in cup_rosters(world).items():
        if not worldconfig.is_active(d, g):
            continue
        for roster in schools.values():
            for p in roster:
                if not _departing(p):
                    continue
                # No season has been played, so there are no results-based STR
                # values; `_str_of` already degrades to the player's own rating.
                rows.append((d, g, p.pid, float(_str_of({}, p)),
                             float(p.current_overall()), json.dumps(prospect_to_dict(p))))
    return rows


def advance_jhsaa_lab(seed: int) -> dict:
    """Advance a JHSAA-only lab world ONE year and simulate+archive that year's
    season — the lab equivalent of the year-rollover step, but with none of
    `_finalize_year`'s college machinery (grad, recruiting, prestige, cups,
    pro offseason). A lab world was built with `skip_college=True`, so it has
    no `world_roster` to roll over, no graduating class to bank, nothing for
    any of that to act on — this is the whole rollover a JHSAA-only world
    needs: bump the year, play the next season, done.

    Existing cohorts age up and graduate naturally: `jhsaa.build_roster` keys
    a player on (school, gender, ENTRY YEAR, seat), and `year - entry_year`
    IS their grade, so incrementing the season year alone walks a freshman to
    a sophomore, ages a senior out, and a new freshman class rolls in — the
    same mechanism a normal world uses, just without anything college
    attached to it.

    Returns the new (post-increment) world row.

    ‼️ THE ARCHIVE COMMITS BEFORE THE YEAR POINTER MOVES, not after. If
    `run_jhsaa` raises — or the process is killed — partway through a long
    simulation, persisting `year+1` first would leave that year permanently
    un-simulated: the world row would already claim it, so the NEXT advance
    would skip straight past it to `year+2`, and `jhsaa_lab`'s archived-count
    (`world["year"] + 1`) would overcount by exactly the missing season. So
    `run_jhsaa` is called against an in-memory `year+1` dict FIRST (it only
    reads `world["id"]`/`["year"]`, never the DB row's own value, so this
    needs no real world-row mutation to work) — only once that succeeds does
    the `UPDATE` make `year+1` the persisted world. A crash before that point
    leaves the world row at its old year, so the next `/jhsaa-lab/advance`
    call recomputes the SAME `new_year` and retries the missing season,
    rather than skipping it."""
    w = load_world(seed)
    if not w:
        raise ValueError(f"No lab world at seed {seed} — generate one first.")
    new_year = w["year"] + 1
    run_jhsaa(seed, {**w, "year": new_year})
    conn = _db()
    conn.execute("UPDATE world SET year=?, week=0 WHERE id=?", (new_year, w["id"]))
    conn.commit()
    conn.close()
    return load_world(seed)


def jhsaa_season_year(world: dict) -> int:
    """The calendar year of the JHSAA season for this world-year — IDENTICAL to
    `recruiting_grad_year` (BASE_YEAR + year + 1), because the season's seniors ARE
    that recruiting class. The zero-based world index is only ever the DB key."""
    return BASE_YEAR + world["year"] + 1


def jhsaa_done(world: dict) -> bool:
    """True once this world-year's JHSAA season is archived. The `world_jhsaa` rows ARE
    the marker — no separate flag to drift, same as the cups above."""
    conn = _db()
    n = conn.execute("SELECT COUNT(*) c FROM world_jhsaa WHERE world_id=? AND year=?",
                     (world["id"], world["year"])).fetchone()["c"]
    conn.close()
    return n > 0


def run_jhsaa(seed: int, world: dict) -> dict:
    """One rung of the ladder: play Jefferson's high-school season for both genders and
    archive it. Runs BEFORE the college year, so the seniors it graduates are on the
    board when recruiting opens.

    Only the summary is stored — champions, awards and district standings. The players
    themselves are deterministic from (school, gender, entry year, seat), so a career
    is rebuilt on demand rather than persisted (`jhsaa.career`)."""
    from . import jhsaa
    from . import jhsaa_individuals
    from . import jhsaa_jv_individuals as jv_indiv
    salt = active_salt(seed)          # the per-save salt recruit_class also uses
    year = world["year"]              # DB key ONLY — never a season parameter
    # THE season parameters, exactly as the recruit hand-off uses them:
    # `apply_to_class` calls `graduating_class(gender, grad_year, salt=salt)`, which
    # runs (year=grad_year, seed=0). Archiving anything else simulates a DIFFERENT
    # season — different entry years mean different students entirely — so the page
    # would show a league whose seniors are not the ones on the recruiting board.
    # Matching parameters also means the memoized season is shared: the hand-off
    # reuses this sim instead of playing a second one.
    season_year = jhsaa_season_year(world)
    conn = _db()
    champs = {}
    try:
        # Divisions are numbered STATEWIDE, girls first then boys, bottom-up by
        # classification — so the counter runs across both genders' seasons.
        division_no = 1
        # Conferences are LETTERED statewide the same way, Z backwards, letters
        # never recycled — the index runs across both genders too.
        conference_ix = 0
        # State Specials are numbered statewide the same way, starting at 1 —
        # usually the counter never moves, because the round convenes only when
        # the road left a field short.
        special_no = 1
        # Special Challenger duals are numbered statewide the same way — how
        # many there are depends on how many eligible early exits each class
        # produced, so the counter runs across both genders too.
        challenge_no = 1
        for gender in ("girls", "boys"):
            season = jhsaa.run_season(gender, season_year, seed=0, salt=salt)
            division_no = jhsaa.renumber_divisions(season, division_no)
            conference_ix = jhsaa.reletter_conferences(season, conference_ix)
            special_no = jhsaa.renumber_state_specials(season, special_no)
            challenge_no = jhsaa.renumber_special_challenges(season, challenge_no)
            summary = {
                "year": year, "season_year": season_year, "gender": gender,
                "champions": {g: season["groups"][g]["state"]["champion"]
                              for g in jhsaa.GROUPS},
                # The full awards slate (owner SOP 2027-08): `teams` is the
                # numbered All-State tiers (First..Third, plus Fourth in 7A),
                # `honorable_mention` the merit tier after them, `district_poy`
                # one per district. `all_state` stays as the FLAT list of every
                # numbered-team selection so pre-SOP readers keep working.
                "awards": {g: {"poy": season["awards"][g].get("poy"),
                               "all_state": season["awards"][g].get("all_state", []),
                               "teams": season["awards"][g].get("teams", []),
                               "honorable_mention":
                                   season["awards"][g].get("honorable_mention", []),
                               "district_poy":
                                   season["awards"][g].get("district_poy", {}),
                               # All-Region: one team per geographic region,
                               # between All-State and All-District.
                               # The FLIGHT CHECK the selector ran before
                               # finalising each singles team (owner, 2027-08 —
                               # flight weighting is structural). Archived, so a
                               # season can be audited years later without
                               # re-running a selector that may have moved on.
                               "flight_check":
                                   season["awards"][g].get("flight_check", {})}
                           for g in jhsaa.GROUPS},
                # ‼️ ALL-REGION IS GENDER-WIDE, NOT PER CLASSIFICATION (owner rule
                # 2027-08). There is no 7A All-Region team — there is a Gold Valley
                # All-Region team, drawn from every program in Gold Valley whatever
                # its enrollment. So it is archived beside `all_district` at the
                # season level, NOT inside `awards[group]`, and every reader merges
                # it in the same way. Selected per class it produced ~1,080 region
                # honours a gender on ~300 programs — every school placed somebody,
                # and it was a district by another name.
                "all_region": season.get("all_region", {}),   # {region: {tiers, honorable_mention, programs}}
                "all_region_flight_check": season.get("all_region_flight_check", {}),
                "standings": {g: season["groups"][g]["standings"] for g in jhsaa.GROUPS},
                # One dict per postseason stage, all in `run_state`'s archive shape:
                # "sectionals" / "wards" / "prestate" (Regionals+Zonals) feed the
                # RECOVERY rounds ("super_regional" / "semi_state"), which feed
                # "brackets" (the State bracket). "protected" records the Regionals
                # entry list; "district_qualifiers" the district-guarantee berths
                # (pre-2027-expansion archives carry "wildcards" instead — the
                # readers accept both). See `jhsaa_postseason_result`.
                "brackets": {g: season["groups"][g]["state"] for g in jhsaa.GROUPS},
                "sectionals": {g: season["groups"][g]["sectional"] for g in jhsaa.GROUPS},
                "wards": {g: season["groups"][g]["ward"] for g in jhsaa.GROUPS},
                "prestate": {g: season["groups"][g]["prestate"] for g in jhsaa.GROUPS},
                "super_regional": {g: season["groups"][g]["super_regional"]
                                   for g in jhsaa.GROUPS},
                "divisional": {g: season["groups"][g].get("divisional")
                                for g in jhsaa.GROUPS},
                # The CONDITIONAL last rungs — present and empty in a year that did
                # not need them (owner rule 2027-08), and the Semi-Conference
                # convenes exactly when the Conference does, because it is the round
                # that qualifies everyone but the Divisional losers FOR it. `.get`
                # because seasons archived before they existed have no key at all.
                "semi_conference": {g: season["groups"][g].get("semi_conference")
                                    for g in jhsaa.GROUPS},
                # STATE SPECIALS — the final reconciliation round (owner rule
                # 2026-08): played only when the road delivered fewer qualifiers
                # than STATE_FIELD, present and empty otherwise. `.get` for
                # seasons archived before it existed.
                "state_special": {g: season["groups"][g].get("state_special")
                                  for g in jhsaa.GROUPS},
                # THE SPECIAL CHALLENGERS — the bridge round in front of the
                # Specials (owner rule 2026-08): eligible early exits contest
                # the weakest challenger seats. Present and empty in a quiet
                # year; `.get` for seasons archived before it existed.
                "special_challenger": {g: season["groups"][g].get("special_challenger")
                                       for g in jhsaa.GROUPS},
                "conference": {g: season["groups"][g].get("conference")
                                for g in jhsaa.GROUPS},
                "semi_state": {g: season["groups"][g]["semi_state"]
                               for g in jhsaa.GROUPS},
                "protected": {g: season["groups"][g]["protected"] for g in jhsaa.GROUPS},
                "district_qualifiers": {g: season["groups"][g]["district_qualifiers"]
                                        for g in jhsaa.GROUPS},
                # The Tournament of Champions — the SIX classification champions, one
                # winner. Archived beside the brackets it is drawn from, in the same
                # shape, so it reads back through the same helpers.
                "toc": season.get("toc") or {},
                "all_district": {g: season["awards"][g].get("all_district", {})
                                 for g in jhsaa.GROUPS},
            }
            champs[gender] = summary["champions"]
            conn.execute("INSERT INTO world_jhsaa (world_id, year, gender, data)"
                         " VALUES (?,?,?,?)",
                         (world["id"], year, gender, json.dumps(summary)))
            # Match by match, so a school's season reads like a college schedule
            # without replaying it. Its own table, not a blob on the summary row:
            # ~10k duals a year per gender would make every summary read heavy.
            # ‼️ VARSITY AND JV GO IN THE SAME TABLE, separated by `level` and nothing
            # else — and BOTH now carry per-court `lines` (owner rule 2026-08: the JV
            # box score is worth its ~22 MB a season). `level` is therefore the ONLY
            # thing keeping a JV appearance out of a varsity record; it used to be
            # guaranteed by JV rows having no lines to read, and it is not any more.
            # Every reader of `lines` filters on it — see `_jh_line_records`'s callers
            # and `jhsaa_underplayed`.
            rows = [(world["id"], year, gender, t.school.name, d["opp"], int(d["home"]),
                     d["phase"], d["pf"], d["pa"], int(d["won"]), int(d["district"]),
                     json.dumps(d.get("lines", [])), d.get("level", "v"),
                     int(bool(d.get("tied"))), d.get("shape", ""), "[]")
                    for t in season["teams"].values() for d in t.schedule]
            # `played` is JV-only: a varsity row's participants are already in its
            # lines, and the career ledger's JV column folds this without having to
            # parse court detail it does not show.
            rows += [(world["id"], year, gender, t.school.name, d["opp"], int(d["home"]),
                      d["phase"], d["pf"], d["pa"], int(d["won"]), int(d["district"]),
                      json.dumps(d.get("lines", [])), d.get("level", "jv"),
                      int(bool(d.get("tied"))),
                      d.get("shape", ""), json.dumps(d.get("played", [])))
                     for t in (season.get("jv") or {}).values() for d in t.schedule]
            conn.executemany(
                "INSERT INTO world_jhsaa_dual (world_id, year, gender, school, opp,"
                " home, phase, pf, pa, won, district, lines, level, tied, shape, played)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            # THE INDIVIDUAL STATE TOURNAMENTS — one row per completed draw, in their
            # own table rather than on the summary blob above (see the schema note).
            conn.executemany(
                "INSERT INTO world_jhsaa_individual"
                " (world_id, year, gender, grp, flight, data) VALUES (?,?,?,?,?,?)",
                [(world["id"], year, gender, grp, flight, json.dumps(draw))
                 for grp, flights in (season.get("individuals") or {}).items()
                 for flight, draw in flights.items()])
            # THE JV INDIVIDUAL STATE TOURNAMENTS — the same table and the same
            # draw shape, which is the point: the champion-history and export
            # tooling reads a draw, not a varsity draw. Two rows per gender.
            #
            # ‼️ THE GROUP IS `GROUP_KEY`, NOT A CLASSIFICATION. This event is
            # CLASSLESS — one statewide champion per bracket per gender — so
            # there is no class to store, and 'ALL' collides with no
            # `jhsaa.GROUPS` entry. That is what keeps every group-scoped reader
            # (`jhsaa_individual_champions`, `jhsaa_individual_results`,
            # `jhsaa_school_individual_champions`, which all query a real class)
            # from ever serving a JV draw under a varsity heading. The one
            # reader that scans EVERY flight is `jhsaa_individual_title_repeats`
            # and it filters these out explicitly — see its own note.
            conn.executemany(
                "INSERT INTO world_jhsaa_individual"
                " (world_id, year, gender, grp, flight, data) VALUES (?,?,?,?,?,?)",
                [(world["id"], year, gender, jv_indiv.GROUP_KEY, flight,
                  json.dumps(draw))
                 for flight, draw in (season.get("jv_individuals") or {}).items()])
            # INJURIES — VARSITY only, one row per injury actually rolled
            # (`t.injury_log`, see `jhsaa.TeamSeason`). JV never carries one.
            conn.executemany(
                "INSERT INTO world_jhsaa_injury"
                " (world_id, year, gender, school, pid, name, dual_index,"
                " duals_out, season_ending) VALUES (?,?,?,?,?,?,?,?,?)",
                [(world["id"], year, gender, t.school.name, e["pid"], e["name"],
                  e["dual_index"], e["duals_out"], int(e["season_ending"]))
                 for t in season["teams"].values() for e in t.injury_log])
        # MIXED DOUBLES — run here because a mixed pair is one player from each
        # gender and `run_season` only ever sees one. It is archived under gender
        # 'mixed': it belongs to neither field, so storing it on one gender's rows
        # would make "which one?" a question, and on both would duplicate it.
        # It credits nothing to anybody (owner rule) — the archive is where a mixed
        # title lives, which is why it can run outside a season at all.
        #
        # ‼️ IT BUILDS ITS OWN ROSTERS AND IS NOT HANDED THE SEASONS ABOVE. The
        # league year begins in JULY (owner rule): summer mixed → fall boys →
        # spring girls, so this is the FIRST event of the year and its pool must be
        # cut from the preseason ability ladder, not from one moved by seasons that
        # on this calendar have not been played yet. See `run_mixed_season`.
        mixed = jhsaa_individuals.run_mixed_season(season_year, salt=salt, seed=0)
        conn.executemany(
            "INSERT INTO world_jhsaa_individual"
            " (world_id, year, gender, grp, flight, data) VALUES (?,?,?,?,?,?)",
            [(world["id"], year, "mixed", grp, "XD", json.dumps(draw))
             for grp, draw in mixed.items()])
        conn.commit()
    finally:
        conn.close()
    return {"event": "jhsaa", "year": year, "champions": champs}


# ‼️ AN ARCHIVED SEASON IS RELABELLED INTO TODAY'S NAMES ON READ (owner rule 2026-08).
# The archive stores the display name a school had when the season was written, so a
# rename orphans everything it had already won: its program page finds nothing, and
# the old name is nobody's school, so that page 404s. A 2031 state champion vanished
# from its own page exactly that way. Renaming a school is not creating a franchise.
#
# Relabelling on READ, not migrating the rows, is deliberate: the archive stays the
# record of what was written, and the next rename needs no migration at all.
#
# ‼️ IT IS KEY-DRIVEN, NOT A BLANKET STRING SWAP. Ten former school names are ALSO
# live town names — Port Veles, Ashbury, Telfair, Orellana — so replacing every string
# that matches a former name would rewrite addresses. Everything is a school name here
# EXCEPT the places and units, which is the safer way round: a shape this misses keeps
# an old name (a broken link, visible), while a blanket swap would quietly move a
# school to another town.
_NOT_A_SCHOOL = frozenset({
    "city", "locality", "town", "county", "area", "district", "districts",
    "league", "group", "classification", "unit", "units", "unit_wins", "phase",
    "region", "state", "mascot", "colors", "name_era", "season_year",
    # ‼️ PEOPLE ARE NOT SCHOOLS. Award rows carry the PLAYER under "name"/"names"
    # and the school under "school" — and Jefferson names its schools after people,
    # so an athlete who happens to share a former school's name would be silently
    # renamed to that school's current one on every read.
    "name", "names",
})

# Subtrees that contain NO school names at all, skipped whole rather than walked
# key by key. A dual's "lines" hold PLAYER lists under "home"/"away" — the same
# keys a bracket game uses for its two SCHOOLS — so the key alone cannot tell the
# two apart; the subtree can.
_NOT_A_SCHOOL_SUBTREE = frozenset({"lines"})


def _relabel(obj, key=None, _map=None):
    """Rewrite every school name in an archived structure to what that school is
    called now. Returns a new structure; the stored rows are untouched."""
    if _map is None:
        from . import jhsaa as _jh
        _map = _jh.former_names()
        if not _map:
            return obj
    if key in _NOT_A_SCHOOL_SUBTREE:
        return obj
    if isinstance(obj, str):
        return obj if key in _NOT_A_SCHOOL else _map.get(obj, obj)
    if isinstance(obj, list):
        return [_relabel(v, key, _map) for v in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            # A dict KEYED by school name (standings by district, champions by class)
            # has to move its key too, or the row is filed under a school nobody can
            # look up. Keys that are places or units are left exactly alone.
            nk = k if (key in _NOT_A_SCHOOL or not isinstance(k, str)) else _map.get(k, k)
            out[nk] = _relabel(v, k, _map)
        return out
    return obj


def get_jhsaa(world_id: int, year: int, gender: str) -> dict | None:
    """The archived JHSAA season for a world-year, or None."""
    conn = _db()
    try:
        r = conn.execute("SELECT data FROM world_jhsaa WHERE world_id=? AND year=?"
                         " AND gender=?", (world_id, year, gender)).fetchone()
    finally:
        conn.close()
    # Relabelled into today's names so a renamed program keeps every row it earned.
    return _relabel(json.loads(r["data"])) if r else None


def jhsaa_individual_draw(world_id: int, year: int, gender: str, group: str,
                          flight: str) -> dict | None:
    """ONE archived individual-tournament draw, or None.

    Deliberately one draw at a time: the page shows one flight, and a gender's
    fifty-four draws are ~1.7 MB. `gender` is 'mixed' for the summer mixed
    doubles, which belongs to neither field."""
    conn = _db()
    try:
        r = conn.execute(
            "SELECT data FROM world_jhsaa_individual WHERE world_id=? AND year=?"
            " AND gender=? AND grp=? AND flight=?",
            (world_id, year, gender, group, flight)).fetchone()
    finally:
        conn.close()
    # Relabelled into today's names, exactly like the season summary: a draw names
    # schools, and a rename must not orphan a title somebody won.
    return _relabel(json.loads(r["data"])) if r else None


def jhsaa_individual_champions(world_id: int, year: int, gender: str,
                               group: str) -> dict:
    """{flight: {champion, runner_up, entries}} for a classification.

    The runner-up rides along because the draw is already parsed to reach the
    champion — a title reads "def. X" and asking for that separately would mean
    deserialising every bracket twice.

    ‼️ It still loads each draw's JSON to reach its champion, which is the honest
    cost of keeping the champion inside the draw that determined it rather than
    denormalising it onto the row. If this ever shows up on a profile, add a
    `champion` COLUMN written at archive time — do not start storing a second
    copy of the draw."""
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT flight, data FROM world_jhsaa_individual WHERE world_id=?"
            " AND year=? AND gender=? AND grp=?",
            (world_id, year, gender, group)).fetchall()
    finally:
        conn.close()
    out = {}
    for r in rows:
        d = _relabel(json.loads(r["data"]))
        ix = d.get("champion")
        if ix is None:
            continue
        ru = d.get("runner_up")
        out[r["flight"]] = {
            "champion": d["entries"][ix],
            "runner_up": d["entries"][ru] if ru is not None else None,
            "entries": len(d.get("entries") or ()),
            "final": (d["rounds"][-1][0]["scoreline"]
                      if d.get("rounds") and d["rounds"][-1] else ""),
        }
    return out


def jhsaa_poy_repeats(world_id: int, gender: str, minimum: int = 2) -> list[dict]:
    """Players who have won a CLASSIFICATION Player of the Year more than once,
    across every archived season (owner request, 2026-08).

    The History section shows names year by year, so a multi-year run is invisible
    there — a player who won 9A POY three times reads as three unrelated rows. This
    is the only surface that can see it, because seeing it means folding over every
    season at once.

    ‼️ CLASS POY ONLY. The District POY (`awards[group]["district_poy"]`) is
    deliberately not counted: the association crowns one per league per class per
    year — hundreds a season — so aggregating it produces a longer list of more
    people rather than a harder achievement. Same reason there is no All-State roll.

    ‼️ CREDITED THROUGH `row_pids`, so a DOUBLES POY honours BOTH athletes. The award
    row is one selection describing a pairing (`jhsaa_awards._row`), and the
    section's own rule is that every "was this person honoured?" question reads
    `pids` — matching on `row["pid"]` credits half of every doubles POY and looks
    perfectly correct on the page it is on.

    ‼️ KEYED ON THE PID, NEVER THE NAME. A pid hashes (origin school, gender, entry
    year, seat), so it survives a transfer and a school rename alike — which is what
    lets one row read "Coles Creek 2028-29, Mater Dei 2030-31". Two players sharing a
    name would otherwise merge into one impossible career.

    A run is returned with the CLASSIFICATION of each award, never a single class per
    player: a 2A run and a 9A run are different achievements and the page shows both
    rather than deciding between them."""
    from . import jhsaa_awards as ja
    out: dict[str, dict] = {}
    for year in jhsaa_years(world_id, gender):
        arc = get_jhsaa(world_id, year, gender)
        if not arc:
            continue
        for grp, aw in (arc.get("awards") or {}).items():
            poy = (aw or {}).get("poy")
            pids = ja.row_pids(poy)
            if not pids:
                continue
            names = list(poy.get("names") or [poy.get("name", "")])
            for i, pid in enumerate(pids):
                nm = names[i] if i < len(names) else poy.get("name", "")
                rec = out.setdefault(pid, {"pid": pid, "name": nm, "awards": []})
                rec["name"] = nm          # the newest spelling wins; years run newest-first
                rec["awards"].append({
                    "year": year, "season_year": arc.get("season_year") or year,
                    "group": grp, "school": poy.get("school", ""),
                    "kind": poy.get("kind", ""),
                })
    rows = [r for r in out.values() if len(r["awards"]) >= minimum]
    for r in rows:
        r["awards"].sort(key=lambda a: a["year"])
        r["count"] = len(r["awards"])
        r["schools"] = list(dict.fromkeys(a["school"] for a in r["awards"]))
        r["groups"] = list(dict.fromkeys(a["group"] for a in r["awards"]))
        r["last"] = r["awards"][-1]["year"]
    rows.sort(key=lambda r: (-r["count"], -r["last"], r["name"]))
    return rows


def _jh_flight_rank() -> tuple[str, ...]:
    """How hard a flight is to win, hardest first — the tie-break on the
    repeat-champions roll: **S1, D1, S2, D2, S3, D3, XD**.

    ‼️ IT IS DERIVED FROM `jhsaa.FLIGHT_WEIGHTS`, NOT TYPED. The association already
    prices its flights for TOSS and for every award résumé — S1 1.00 · D1 1.00 ·
    S2 0.75 · D2 0.50 · S3 0.25 · D3 0.25 — and that table sorts to exactly this
    order. A first pass hand-typed a tuple built off `jhsaa_individuals.FLIGHTS`
    instead, which is S1-S3 then D1-D3 because that is how a DRAW SHEET reads, and
    got a ranking the association does not use (No. 1 doubles below No. 3 singles).
    Look the constant up before inventing an ordering.

    ‼️ AND WHY D1 SITS LEVEL WITH S1 — measured, 40 5A girls programs. A state dual
    is 1S/4D and the anti-stacking rule makes S1+D1 consume ranks #1-#3, so S1 is
    staffed at mean ability rank **1.2** and D1 at **2.4**, both only ever from the
    top three — and most classes have no No. 2 singles seat at all. Owner, 2026-08:
    "generally in Jefferson your best players are at 1st doubles as well as 1
    singles versus other places." The INDIVIDUAL event's own entry sheet is the
    other way (S2 = #2, D1 = #4+#5), which is why this looks arguable from that
    event alone; the association's weighting is the authority, and it follows the
    dual.

    Ties in the table (S1/D1 at 1.00, S3/D3 at 0.25) break SINGLES FIRST, which is
    the sequence the owner stated. `XD` carries no weight — it is not a dual flight
    — and is last: a consolation draw entered from below No. 9.

    This only ever decides which of two players with the SAME NUMBER of titles is
    listed first. Every title counts identically toward the count itself."""
    from . import jhsaa as _jh
    from . import jhsaa_individuals as ji
    return tuple(sorted(ji.FLIGHTS,
                        key=lambda f: (-_jh.FLIGHT_WEIGHTS[f], f[0] != "S", f))) + ("XD",)


def _jh_indiv_flight_order() -> tuple:
    """Every individual-tournament flight there is, in the order a page lists
    them: the six varsity flights by `_jh_flight_rank`, then mixed doubles, then
    the two JV state brackets.

    The JV brackets sit LAST because they are a different event, not a weaker
    flight — `FLIGHT_WEIGHTS` prices dual courts and has no entry for them, so
    ranking them inside that table would be inventing a weight for a court the
    association does not play. Singles before doubles, the same tie-break the
    varsity table breaks on."""
    from . import jhsaa_jv_individuals as jvi
    return _jh_flight_rank() + jvi.BRACKETS


def _jh_flight_name(flight: str) -> str:
    """How a flight is written out, across BOTH individual events. One lookup, so
    a surface showing a varsity flight and a JV bracket side by side cannot name
    one and print the other's bare key."""
    from . import jhsaa_individuals as ji
    from . import jhsaa_jv_individuals as jvi
    return ji.FLIGHT_NAMES.get(flight) or jvi.BRACKET_NAMES.get(flight, flight)


def jhsaa_individual_title_repeats(world_id: int, gender: str,
                                   minimum: int = 2) -> list[dict]:
    """Players with more than one INDIVIDUAL STATE title, across every archived
    season (owner request, 2026-08).

    ‼️ THIS IS A PERSON-LEVEL LIST, NOT A PAIRING ONE — the opposite of how the
    awards module treats doubles. A doubles TITLE credits each partner
    individually, because the same player can win with a different partner in a
    different year and those two titles are one career. Keying doubles here on the
    pair would split that career in two and count neither run. The partner rides
    along per title as context; the row and the count belong to the individual.

    ‼️ MIXED DOUBLES COUNTS HERE (owner correction, 2026-08: "if a kid wins a mixed
    doubles title it counts"). A first pass excluded it by reading across from the
    rule that it credits no AWARD — but those are different things: this roll is a
    record of state titles a person has won, and a mixed title is one of them. The
    no-credit rule is about résumés (`jhsaa_awards`), TOSS and the recruit hand-off,
    and it is untouched.
    ‼️ AND A MIXED PAIR IS ONE PLAYER FROM EACH FIELD, so only THIS gender's half of
    it may be credited on this page. The archived entry is always `[boy, girl]` —
    `jhsaa_individuals.mixed_entry` is the only thing that builds one and it pairs
    them in that order — so the side is an INDEX, not a guess. Crediting both would
    put a boy on the girls' roll, which is the one thing the `gender` column exists
    to prevent.

    ‼️ THE CHAMPION IS EXTRACTED IN SQLITE, NOT IN PYTHON. A draw is a ~30KB blob
    and this walks EVERY draw of every archived season — eleven classes × six
    flights × N years, where the individual-champions page loads one class. Parsing
    all of that on the request thread is the one-gthread hazard this section keeps
    relearning, and none of it is needed: the blob already stores `champion` as an
    INDEX into `entries`, so json1 can return just that entrant. `_relabel` then
    runs on the small dict rather than the whole draw."""
    from . import jhsaa_individuals as ji
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT year, grp, gender, flight,"
            " json_extract(data, '$.entries[' ||"
            "   json_extract(data, '$.champion') || ']') AS champ"
            " FROM world_jhsaa_individual WHERE world_id=? AND gender IN (?, 'mixed')"
            " AND json_extract(data, '$.champion') IS NOT NULL",
            (world_id, gender)).fetchall()
    finally:
        conn.close()
    order = {f: i for i, f in enumerate(_jh_flight_rank())}
    out: dict[str, dict] = {}
    for r in rows:
        # ‼️ THE FLIGHT CHECK IS WHAT KEEPS THE JV STATE TITLES OFF A VARSITY
        # CAREER ROLL, and it is load-bearing rather than defensive. The JV
        # individual tournaments archive into this same table in the same draw
        # shape (deliberately — see `run_jhsaa`), and `_jh_flight_rank` is built
        # from the VARSITY flights plus XD, so `JVS`/`JVD` are not in `order`
        # and drop out here. JV counts for nothing on a varsity surface, which
        # is the association's standing rule; a "tidy" rewrite that ranked an
        # unknown flight last instead of dropping it would quietly merge the two.
        if r["flight"] not in order or not r["champ"]:
            continue
        champ = _relabel(json.loads(r["champ"]))
        players = champ.get("players") or ()
        # The mixed pair's own gender split: [boy, girl], by construction.
        mine = (0 if gender == "boys" else 1) if r["gender"] == "mixed" else None
        for i, p in enumerate(players):
            pid = p.get("pid")
            if not pid or (mine is not None and i != mine):
                continue
            rec = out.setdefault(pid, {"pid": pid, "name": p.get("name", ""),
                                       "titles": []})
            rec["titles"].append({
                "year": r["year"], "group": r["grp"], "flight": r["flight"],
                "flight_name": ji.FLIGHT_NAMES.get(r["flight"], r["flight"]),
                "school": champ.get("school", ""),
                "grade": p.get("grade"),
                # Context, not a co-holder: the count on this row is the person's.
                "partner": next((q.get("name", "") for j, q in enumerate(players)
                                 if j != i), ""),
            })
    keep = [v for v in out.values() if len(v["titles"]) >= minimum]
    for rec in keep:
        rec["titles"].sort(key=lambda t: (t["year"], order[t["flight"]]))
        rec["count"] = len(rec["titles"])
        rec["schools"] = list(dict.fromkeys(t["school"] for t in rec["titles"]))
        rec["last"] = rec["titles"][-1]["year"]
        # The tie-break the owner asked for: by flight QUALITY, best first, compared
        # as a whole run — so two S1s outrank an S1 and an S3, which outrank two S3s.
        rec["_quality"] = sorted(order[t["flight"]] for t in rec["titles"])
    keep.sort(key=lambda r: (-r["count"], r["_quality"], -r["last"], r["name"]))
    for rec in keep:
        rec.pop("_quality")
    return keep


def jhsaa_individual_results(world_id: int, year: int, gender: str, group: str,
                             pid: str) -> list[dict]:
    """One player's individual-tournament results for ONE season — the flight they
    entered and how far they got, per draw. Empty for a season played before the
    event existed, which is honest.

    ‼️ THE `LIKE` IS A PREFILTER, NOT THE ANSWER. A season's draws for one class are
    seven ~30KB JSON blobs, and `json.loads` on all seven for every player page is
    the cost this avoids: a pid is a 16-hex string, so a blob that does not contain
    it cannot contain the player, and SQLite can decide that without parsing. The
    entry is then located properly, by walking `entries`.

    Mixed doubles is included (gender 'mixed'). It is a state title the player won
    and belongs on their page; it credits no AWARD, which is a different thing.

    ‼️ SO ARE THE JV STATE TOURNAMENTS (owner rule 2026-08): "it's still a state
    honour, so this tournament shows up on a player page no different than the
    other individual singles/doubles state tournament flights." They are archived
    CLASSLESS, under `jhsaa_jv_individuals.GROUP_KEY` rather than a
    classification, so the group filter has to admit that key as well as the
    player's own class — a page scoped to one class would otherwise silently drop
    a title the player actually won. That is the same mistake the mixed draw's
    exclusion was: answering a scoping question by losing a result.

    ‼️ IT DOES NOT FOLLOW THAT JV BELONGS ON EVERY VARSITY SURFACE. This section
    is a record of what a player did; the counters JV must never reach are the
    W-L record, the résumé the awards read, TOSS and the ladder — none of which
    is here, and all of which `jhsaa.JVTeam` keeps unreachable by construction."""
    from . import jhsaa_jv_individuals as jvi
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT gender, flight, grp, data FROM world_jhsaa_individual"
            " WHERE world_id=? AND year=? AND grp IN (?, ?)"
            " AND gender IN (?, 'mixed') AND data LIKE ?",
            (world_id, year, group, jvi.GROUP_KEY, gender,
             f"%{pid}%")).fetchall()
    finally:
        conn.close()
    from . import jhsaa_individuals as ji
    out = []
    for r in rows:
        d = _relabel(json.loads(r["data"]))
        ix = ji.entry_index_of(d, pid)
        if ix is None:                 # a LIKE hit that was not this player
            continue
        e = d["entries"][ix]
        label, tag = ji.finish_for_index(d, ix)
        tier, icon, honour = ji.finish_tier(tag)
        partner = next((p["name"] for p in e["players"] if p["pid"] != pid), "")
        out.append({"flight": r["flight"], "gender": r["gender"],
                    "flight_name": _jh_flight_name(r["flight"]),
                    "finish": label, "tag": tag, "seed": e.get("seed") or 0,
                    "partner": partner, "entries": len(d["entries"]),
                    # How loudly the page says it — see `jhsaa_individuals
                    # .FINISH_TIERS`. `honour` is empty below the top 8, which is
                    # what makes those rows read as history rather than accolade.
                    "tier": tier, "icon": icon, "honour": honour,
                    # ‼️ THE DRAW'S OWN GROUP, NOT THE PAGE'S. A JV draw is
                    # classless and carries `GROUP_KEY`; stamping the player's
                    # class on it would file a statewide title under a class it
                    # was never contested in. `jv` is the display's cue to say
                    # "Statewide" rather than print the bare key.
                    "group": r["grp"], "jv": r["flight"] in jvi.BRACKETS,
                    "champion": tag == "CHAMP"})
    order = {f: i for i, f in enumerate(_jh_indiv_flight_order())}
    out.sort(key=lambda r: order.get(r["flight"], 99))
    return out


def jhsaa_latest_season_year(world_id: int, gender: str) -> int | None:
    """The CALENDAR year of the newest archived JHSAA season, or None with no
    archive. An offseason transfer's default effective year is this + 1."""
    years = jhsaa_years(world_id, gender)
    if not years:
        return None
    arc = get_jhsaa(world_id, years[0], gender)
    return (arc or {}).get("season_year") or (BASE_YEAR + years[0] + 1)


_underplayed_cache: dict = {}


def jhsaa_underplayed(world_id: int, gender: str, salt: str = "",
                      season_year: int | None = None) -> dict:
    """The transfer-portal search: every 9th/10th grader in the newest archived
    season with under a dozen matches, best first — READ off the archive, never
    re-simulated. Match counts come from the same `world_jhsaa_dual.lines` rows
    the player card's season record reads (appearances by name within the
    school's own card); ability comes off the deterministic roster rebuild.

    Returns {"season_year", "rows"} — rows are every candidate under the CEILING
    (11 matches); the view applies the owner's actual threshold, so changing it
    on screen never re-pays the full-gender roster build. Memoised on the
    archive year plus the transfers effective BY that season (a new offseason
    move can't change last season's board, so it must not evict this)."""
    from collections import defaultdict
    from . import jhsaa as _jh
    years = jhsaa_years(world_id, gender)
    if season_year is not None:
        year = season_year - BASE_YEAR - 1      # inverse of jhsaa_season_year
        if year not in years:
            return {"season_year": None, "rows": []}
    elif not years:
        return {"season_year": None, "rows": []}
    else:
        year = years[0]
        season_year = jhsaa_latest_season_year(world_id, gender)
    # ‼️ KEY ON WHERE EACH PLAYER ACTUALLY IS THAT SEASON, not on the record's shape.
    # This read `r["to"]`/`r["year"]` — the fields a SINGLE-move record carries — so
    # once a career became a `moves` history every record collapsed to (pid, None,
    # None) and the key stopped depending on the transfers at all: adding, editing or
    # undoing a move effective during this archived season changed `build_roster` and
    # not the key, and `reset_all()` does not clear this cache, so the board went on
    # showing players at their previous schools until another season or a restart.
    #
    # `transfer_school` is also TIGHTER than listing the moves: the board depends only
    # on which school each pid plays for in `season_year`, so a move recorded for a
    # LATER season correctly leaves this key alone instead of evicting a board it
    # cannot affect. Legacy single-move records read through the same helper.
    where = tuple(sorted((pid, _jh.transfer_school(r, season_year))
                         for pid, r in _jh.transfers().items()))
    key = (world_id, gender, year, salt, where)
    got = _underplayed_cache.get(key)
    if got is not None:
        return got
    alias = _jh.former_names()
    conn = _db()
    try:
        played: dict[str, dict] = defaultdict(lambda: defaultdict(int))
        # ‼️ VARSITY ONLY. This board finds players the LEAGUE season is not dressing,
        # so that they can be moved; JV is exactly where those players already are, and
        # counting it would hide every one of them behind a full JV card. The filter is
        # load-bearing since the JV box score landed — JV rows carry lines now.
        for d in conn.execute(
                "SELECT school, home, lines FROM world_jhsaa_dual"
                " WHERE world_id=? AND year=? AND gender=?"
                " AND COALESCE(level,'v')='v'",
                (world_id, year, gender)):
            side = "home" if d["home"] else "away"
            school = alias.get(d["school"], d["school"])
            for ln in json.loads(d["lines"] or "[]"):
                for nm in ln.get(side) or ():
                    played[school][nm] += 1
    finally:
        conn.close()
    rows = []
    for school in _jh.load_schools(gender):
        counts = played.get(school.name, {})
        for i, p in enumerate(_jh.build_roster(school, season_year, salt), 1):
            if p.grade not in (9, 10):
                continue
            n = counts.get(p.name, 0)
            if n >= 12:
                continue
            rows.append({"pid": p.pid, "name": p.name, "school": school.name,
                         "group": school.group,
                         "grade": p.grade, "entry": p.entry_year, "ladder": i,
                         "ovr": round(p.current_overall(), 1),
                         "str": round(p.str_value(), 1), "matches": n})
    rows.sort(key=lambda r: -r["ovr"])
    out = {"season_year": season_year, "rows": rows}
    for k in [k for k in _underplayed_cache if k[:2] == key[:2]]:
        _underplayed_cache.pop(k, None)
    _underplayed_cache[key] = out
    return out


def jhsaa_scoreline_realism(world_id: int, year: int, gender: str) -> dict:
    """The archived season's set scores folded against the real-Oregon target
    (`jhsaa.OREGON_SET_TARGET`) — the in-game face of
    scripts/jhsaa_scoreline_benchmark.py, and deliberately a READ: it parses the
    score strings the archive already holds (the `jhsaa._games` precedent) and
    simulates nothing on the request thread.

    Varsity only (`COALESCE(level,'v')='v'` — the table is shared with JV and a
    pre-JV archive reads back NULL), one side of each dual (`home=1`). Only
    completed standard sets (6-0..6-4, 7-5, 7-6) enter the histogram, exactly
    the target's own filter — showcase-pod pro sets and anything malformed fall
    out. The three-set rate is over best-of-3 matches (>= 2 standard sets
    parsed). Split by phase family because the formats differ by design."""
    from . import jhsaa as _jh
    keys = list(_jh.OREGON_SET_TARGET)
    fams = ("regular", "postseason", "showcase")

    def fam(phase: str) -> str:
        if phase in _jh.POSTSEASON:
            return "postseason"
        if str(phase).startswith("showcase"):
            return "showcase"
        return "regular"

    conn = _db()
    try:
        rows = conn.execute(
            "SELECT phase, lines FROM world_jhsaa_dual"
            " WHERE world_id=? AND year=? AND gender=? AND home=1"
            " AND COALESCE(level,'v')='v'",
            (world_id, year, gender)).fetchall()
    finally:
        conn.close()

    counts = {f: {k: 0 for k in keys} for f in fams}
    n_sets = {f: 0 for f in fams}
    matches = {f: 0 for f in fams}
    three = {f: 0 for f in fams}
    for phase, lines_json in rows:
        f = fam(phase)
        try:
            lines = json.loads(lines_json or "[]")
        except ValueError:
            continue
        for ln in lines:
            std = 0
            for st in (ln.get("score") or "").split(","):
                bits = st.strip().split("-")
                if len(bits) != 2:
                    continue
                try:
                    a, b = int(bits[0]), int(bits[1])
                except ValueError:
                    continue
                key = f"{max(a, b)}-{min(a, b)}"
                if key in counts[f]:
                    counts[f][key] += 1
                    n_sets[f] += 1
                    std += 1
            if std >= 2:
                matches[f] += 1
                three[f] += std == 3

    def table(fs):
        total = sum(n_sets[f] for f in fs)
        m = sum(matches[f] for f in fs)
        t3 = 100 * sum(three[f] for f in fs) / m if m else 0.0
        out = []
        tv = 0.0
        for k in keys:
            sim = (100 * sum(counts[f][k] for f in fs) / total) if total else 0.0
            real = _jh.OREGON_SET_TARGET[k]
            tv += abs(sim - real)
            out.append({"key": k, "sim": sim, "real": real, "diff": sim - real})
        return {"rows": out, "sets": total, "matches": m, "three_set": t3,
                "tv": tv / 2}

    return {"overall": table(fams),
            "families": [{"key": f, "label": lbl, **table((f,))}
                         for f, lbl in (("regular", "League season"),
                                        ("postseason", "Postseason"),
                                        ("showcase", "Showcases"))],
            "real_three_set": _jh.OREGON_THREE_SET}


def jhsaa_years(world_id: int, gender: str) -> list[int]:
    """Every world-year with an archived JHSAA season, newest first."""
    conn = _db()
    try:
        rows = conn.execute("SELECT DISTINCT year FROM world_jhsaa WHERE world_id=?"
                            " AND gender=? ORDER BY year DESC",
                            (world_id, gender)).fetchall()
    finally:
        conn.close()
    return [r["year"] for r in rows]


_careerwins_cache: dict = {}
_progwins_cache: dict = {}


def jhsaa_program_wins(world_id: int, gender: str, school: str,
                       salt: str = "", limit: int = 10) -> list[dict]:
    """The one program's "Most Program Wins" top-10 — the same numbers
    `jhsaa_career_wins(...)["by_program"][school]` returns, but scoped to a
    SINGLE program's own duals instead of folding the whole gender's archive.

    ‼️ THE SCHOOL PAGE ONLY EVER NEEDS ONE PROGRAM'S ROW, and `jhsaa_career_wins`
    was written for the History boards, which genuinely need every player and
    every program at once. Calling it from the school page meant every single
    program-page view — whichever school, whichever click — paid the cost of
    tallying every archived varsity line for the WHOLE gender across EVERY
    season, just to read one program's slice back out. That scan grows with
    total schools AND total years, so it got slower every time either grew,
    and it never looked "done" from the outside — it re-pays a large share of
    that cost on every cache miss (a new season archived, a transfer-table
    edit, a different gender clicked), which reads exactly like "loading
    something every time" on a big, long-running save.

    Scoped by `world_jhsaa_dual`'s own `(world_id, year, gender, school)`
    index via `known_names` (every display name this program has ever
    carried, so a renamed program's older seasons still count) — no full-table
    scan, no player-career or transfer-merge logic (`by_program` never used
    either: it credits every court to whichever school archived it, transfer
    or not). Cached per (world, gender, school, newest year, salt, limit)."""
    from collections import defaultdict
    from . import jhsaa as _jh

    years = jhsaa_years(world_id, gender)
    if not years:
        return []
    if not salt:
        salt = active_salt(DEFAULT_SEED)
    key = (world_id, gender, school, years[0], salt, limit)
    got = _progwins_cache.get(key)
    if got is not None:
        return got

    names = _jh.known_names(school, gender)
    tal: dict = defaultdict(lambda: [0, 0, 0, 0])        # (name, year) -> [sw, sl, dw, dl]
    conn = _db()
    try:
        qmarks = ",".join("?" * len(names))
        for d in conn.execute(
                "SELECT year, home, lines FROM world_jhsaa_dual"
                f" WHERE world_id=? AND gender=? AND COALESCE(level,'v')='v'"
                f" AND school IN ({qmarks})",
                (world_id, gender, *names)):
            side = "home" if d["home"] else "away"
            for ln in json.loads(d["lines"] or "[]"):
                slot = ln.get("slot") or ""
                hw = ln.get("home_won")
                if hw is None or not slot:
                    continue
                won = bool(hw) == bool(d["home"])
                i = (0 if won else 1) if slot[0] == "S" else (2 if won else 3)
                for nm in (ln.get(side) or ()):
                    tal[(nm, d["year"])][i] += 1
    finally:
        conn.close()

    by_player: dict = defaultdict(list)
    for (name, year), t in tal.items():
        by_player[name].append((year, t))
    runs = []
    for name, items in by_player.items():
        items.sort()
        run: list[tuple] = []
        for year, t in items:
            if run and year > run[-1][0] + 1:
                runs.append(_career_run(school, name, run))
                run = []
            run.append((year, t))
        if run:
            runs.append(_career_run(school, name, run))
    out = sorted(runs, key=lambda r: (-r["w"], r["l"], r["name"]))[:limit]

    sc = next((s for s in _jh.load_schools(gender) if s.name == school), None)
    if sc is not None:
        for r in out:
            for p in _jh.build_roster(sc, r["last"], salt):
                if p.name == r["name"]:
                    r["pid"] = p.pid
                    break

    for k in [k for k in _progwins_cache if k[:3] == key[:3]]:
        _progwins_cache.pop(k, None)
    _progwins_cache[key] = out
    return out


def jhsaa_career_wins(world_id: int, gender: str, salt: str = "",
                      limit: int = 10) -> dict:
    """THE CAREER WINS BOARDS (owner request, 2026-08): the most match wins over a
    high-school career (players) and all-time (programs), folded out of the archive.

    Returns {"players": {"overall"|"singles"|"doubles": [row, ...]},   # top `limit`
             "programs": [row, ...],                                   # every program
             "years": [...]}.

    ‼️ WHAT A "WIN" IS HERE: a court won on a VARSITY dual card — the DUAL record,
    exactly what the player page's career ledger counts. JV is excluded (`level`
    filter — the section's rule for every reader of `world_jhsaa_dual`), the
    individual state tournaments and mixed doubles are excluded (their results are
    deliberately kept OUT of the career W-L; they live in their own table anyway),
    and the postseason is INCLUDED because a record is a record. A doubles win
    credits both partners (each played it); a doubles court is ONE court on the
    program's tally.

    ‼️ A CAREER IS A RUN OF CONSECUTIVE SEASONS, keyed (school, name). The archive's
    `lines` store NAMES, not pids — so identity here is the name within a school,
    split wherever the years stop being consecutive (a four-year career is
    consecutive by construction; a same-named player a generation later must not
    inherit it). Transferred players are the exception: the transfer table is the
    authority on where a pid was each season, so a mover's tallies are pulled out of
    the name-run pool and merged into ONE career with stints, the same shape the
    repeat rolls use. Two same-named players at one school in overlapping years
    would merge — accepted, the pools make that astronomically rare.

    ‼️ ONE PASS OVER THE DUAL TABLE, cached. This parses every archived varsity
    line, which is the heaviest fold in the section — it runs once per (world,
    gender, newest season, transfer version) and is served from the memo after,
    the gthread rules observed (compute local, publish, return the local).
    Schools are relabelled through `former_names` so a renamed program's career
    rows and its current page agree; the top rows resolve their PIDs by
    regenerating the roster they last played on, which is what the player links
    need and costs a handful of cached `build_roster` calls."""
    from collections import defaultdict
    from . import jhsaa as _jh
    from app import overrides as ov
    years = jhsaa_years(world_id, gender)
    if not years:
        return {"players": {"overall": [], "singles": [], "doubles": []},
                "programs": [], "years": []}
    if not salt:
        salt = active_salt(DEFAULT_SEED)
    key = (world_id, gender, years[0], salt, ov.jhsaa_transfer_version(), limit)
    got = _careerwins_cache.get(key)
    if got is not None:
        return got
    alias = _jh.former_names()

    # --- the duals: per (school, name, year) court tallies, plus program courts ---
    tal: dict = defaultdict(lambda: [0, 0, 0, 0])       # [sw, sl, dw, dl]
    prog_courts: dict = defaultdict(lambda: [0, 0, 0, 0])
    conn = _db()
    try:
        for d in conn.execute(
                "SELECT year, school, home, lines FROM world_jhsaa_dual"
                " WHERE world_id=? AND gender=? AND COALESCE(level,'v')='v'",
                (world_id, gender)):
            side = "home" if d["home"] else "away"
            school = alias.get(d["school"], d["school"])
            for ln in json.loads(d["lines"] or "[]"):
                slot = ln.get("slot") or ""
                hw = ln.get("home_won")
                if hw is None or not slot:
                    continue
                won = bool(hw) == bool(d["home"])
                i = (0 if won else 1) if slot[0] == "S" else (2 if won else 3)
                names = ln.get(side) or ()
                for nm in names:
                    tal[(school, nm, d["year"])][i] += 1
                prog_courts[school][i] += 1
    finally:
        conn.close()

    # --- the programs: dual W-L off the archived standings records (the numbers
    # the record-coverage test pins to the duals), one pass per season ---
    programs: dict = {}
    for year in years:
        arc = get_jhsaa(world_id, year, gender)
        if not arc:
            continue
        for grp, dists in (arc.get("standings") or {}).items():
            for _dname, teams in (dists or {}).items():
                for t in teams or ():
                    school = t.get("school", "")
                    r = programs.get(school)
                    if r is None:
                        r = programs[school] = {
                            "school": school, "group": grp, "seasons": 0,
                            "w": 0, "l": 0, "first": None, "last": None}
                    w, l = _wl(t.get("record"))
                    r["w"] += w
                    r["l"] += l
                    r["seasons"] += 1
                    r["group"] = grp        # the class LAST archived, like the board
                    sy = BASE_YEAR + year + 1
                    r["first"] = sy if r["first"] is None else min(r["first"], sy)
                    r["last"] = sy if r["last"] is None else max(r["last"], sy)
    for school, r in programs.items():
        c = prog_courts.get(school, [0, 0, 0, 0])
        r["s_w"], r["s_l"], r["d_w"], r["d_l"] = c
        r["pct"] = r["w"] / (r["w"] + r["l"]) if (r["w"] + r["l"]) else 0.0
    program_rows = sorted(programs.values(), key=lambda r: (-r["w"], r["school"]))

    # --- the transfers: a mover's seasons are claimed OUT of the name-run pool
    # and merged into one pid-keyed career, oldest stint first ---
    careers: list[dict] = []
    claimed: set = set()
    movers = {r["pid"]: r for r in _jh.transfer_rows()}
    for pid, rec in _jh.transfers().items():
        if rec.get("gender") != gender:
            continue
        name = (movers.get(pid) or {}).get("name", "")
        if not name:
            continue
        entry = rec.get("entry") or 0
        stints: list[tuple] = []                       # (school, season_year)
        sw = sl = dw = dl = 0
        for year in sorted(years):
            sy = BASE_YEAR + year + 1
            if not (entry <= sy <= entry + 3):
                continue
            school = alias.get(_jh.transfer_school(rec, sy), "") or ""
            school = alias.get(school, school)
            k = (school, name, year)
            if k in tal:
                claimed.add(k)
                t = tal[k]
                sw += t[0]; sl += t[1]; dw += t[2]; dl += t[3]
                stints.append((school, sy))
        if not stints:
            continue
        careers.append(_career_row(name, stints, sw, sl, dw, dl, pid=pid))

    # --- everyone else: consecutive-year runs per (school, name) ---
    by_player: dict = defaultdict(list)
    for (school, name, year), t in tal.items():
        if (school, name, year) in claimed:
            continue
        by_player[(school, name)].append((year, t))
    for (school, name), items in by_player.items():
        items.sort()
        run: list[tuple] = []
        for year, t in items:
            if run and year > run[-1][0] + 1:          # a gap ends the career
                careers.append(_career_run(school, name, run))
                run = []
            run.append((year, t))
        if run:
            careers.append(_career_run(school, name, run))

    # --- the three boards, top `limit` PLACES each (ties included, not a strict
    # slice — the tenth win count may belong to several careers, and cutting one
    # of them off mid-tie would be a wrong answer, not a shorter one). Pids are
    # only resolved for the union actually shown, which is the expensive part
    # (one cached `build_roster` call per unresolved row) — keeping `limit`
    # small is what keeps the page fast, not a display preference. ---
    def _top(rows: list[dict], k) -> list[dict]:
        rows = sorted(rows, key=k)
        if len(rows) <= limit:
            return rows
        cutoff = k(rows[limit - 1])[0]           # the Nth place's WIN count
        return [r for r in rows if k(r)[0] <= cutoff]

    boards = {
        "overall": _top(careers, lambda r: (-r["w"], r["l"], r["name"])),
        "singles": _top(careers, lambda r: (-r["s_w"], r["s_l"], r["name"])),
        "doubles": _top(careers, lambda r: (-r["d_w"], r["d_l"], r["name"])),
    }
    shown = {id(r): r for rows in boards.values() for r in rows}
    schools_by_name = {s.name: s for s in _jh.load_schools(gender)}
    for r in shown.values():
        if r.get("pid"):
            continue
        sc = schools_by_name.get(r["school"])
        if sc is None:
            continue
        for p in _jh.build_roster(sc, r["last"], salt):
            if p.name == r["name"]:
                r["pid"] = p.pid
                break

    # --- per-program top 10 (the program page's "Most Program Wins" tab):
    # wins earned AT that school, transfer or not — a mover appears on each
    # program's roll with the wins they won wearing that shirt, so the split is
    # per (school, name) runs over EVERY tally, claimed keys included.
    by_school: dict = defaultdict(list)
    for (school, name, year), t in tal.items():
        by_school[(school, name)].append((year, t))
    prog_rolls: dict = defaultdict(list)
    for (school, name), items in by_school.items():
        items.sort()
        run = []
        for year, t in items:
            if run and year > run[-1][0] + 1:
                prog_rolls[school].append(_career_run(school, name, run))
                run = []
            run.append((year, t))
        if run:
            prog_rolls[school].append(_career_run(school, name, run))
    by_program = {school: sorted(rows, key=lambda r: (-r["w"], r["l"], r["name"]))[:10]
                  for school, rows in prog_rolls.items()}

    out = {"players": boards, "programs": program_rows, "years": years,
           "by_program": by_program}
    for k in [k for k in _careerwins_cache if k[:2] == key[:2]]:
        _careerwins_cache.pop(k, None)
    _careerwins_cache[key] = out
    return out


def _career_row(name: str, stints: list[tuple], sw: int, sl: int,
                dw: int, dl: int, pid: str = "") -> dict:
    """One career row. `stints` is [(school, season_year), ...] in year order;
    consecutive same-school years collapse into one stint for display."""
    runs: list[dict] = []
    for school, sy in stints:
        if runs and runs[-1]["school"] == school:
            runs[-1]["last"] = sy
        else:
            runs.append({"school": school, "first": sy, "last": sy})
    return {"name": name, "pid": pid,
            "school": stints[-1][0], "stints": runs,
            "first": stints[0][1], "last": stints[-1][1],
            "s_w": sw, "s_l": sl, "d_w": dw, "d_l": dl,
            "w": sw + dw, "l": sl + dl}


def _career_run(school: str, name: str, run: list[tuple]) -> dict:
    """A consecutive-year run at one school, folded into a career row."""
    sw = sum(t[0] for _y, t in run); sl = sum(t[1] for _y, t in run)
    dw = sum(t[2] for _y, t in run); dl = sum(t[3] for _y, t in run)
    stints = [(school, BASE_YEAR + y + 1) for y, _t in run]
    return _career_row(name, stints, sw, sl, dw, dl)


def _schedule_rows(conn, world_id: int, year: int, gender: str, school: str) -> list[dict]:
    """One school's duals for a year, in the order they were played, on an OPEN
    connection — so a caller walking many seasons opens one, not one per year."""
    # ‼️ EVERY NAME THIS PROGRAM HAS EVER CARRIED. The archive is keyed on the display
    # name at the time the season was written, so a renamed school's older duals sit
    # under the old string. Querying the current name alone silently returns an empty
    # season for a program that played a full one.
    from . import jhsaa as _jh
    names = _jh.known_names(school, gender)
    rows = conn.execute(
        "SELECT rowid AS id, opp, home, phase, pf, pa, won, district, lines, level,"
        " tied, shape, played FROM world_jhsaa_dual"
        " WHERE world_id=? AND year=? AND gender=? AND school IN (%s) ORDER BY rowid"
        % ",".join("?" * len(names)),
        (world_id, year, gender, *names)).fetchall()
    from . import jhsaa as _jh2
    alias = _jh2.former_names()
    out = []
    for r in rows:
        d = dict(r)
        d["opp"] = alias.get(d["opp"], d["opp"])     # an opponent renamed since
        # The row is one SIDE of a dual; carrying its own school makes it
        # self-describing, so `jh_match_key` can identify the match from either
        # side without the caller threading the school through.
        d["school"] = school
        for k in ("lines", "played"):
            try:
                d[k] = json.loads(d.get(k) or "[]")
            except ValueError:
                d[k] = []
        out.append(d)
    return out


# --- the JHSAA display calendar ------------------------------------------------
# ‼️ A DUAL IS ONE EVENT WITH ONE DATE (owner rule 2027-08). Dates used to be
# derived per school from that school's POSITION in its own card, so the same
# match landed on two different days — Lake Esperanza had its Super Regional on
# May 14 and José Martí, its opponent, had the same dual on May 17. Nothing
# errored: each card was internally plausible and only reciprocity was wrong.
# The date is therefore assigned to the MATCH, once per season, and both cards
# look it up.
#
# There is still no clock inside a JHSAA season (the whole association runs in
# one rung at world week 0), so this remains PRESENTATION: nothing reads a date
# back and no simulation decision depends on one.
_JH_CAL_CACHE: dict[tuple, dict] = {}
_JH_CAL_MAX = 8

# Boys play a fall season, girls a spring one — cosmetic separation only; both
# are still simulated together in the same rung.
_JH_SEASON_OPEN = {"boys": (8, 1), "girls": (3, 1)}
# Weekday offsets from a Monday. A fictional association can play densely — the
# owner allows roughly 3-4 duals a week including Saturdays — and **never on a
# Sunday**, which is true by construction here: 6 appears in neither pattern.
# One pattern for the whole season: Mon / Wed / Fri / Sat. The postseason lands
# two or three days between stages, which is how a real state series runs and
# leaves the Road to State progression readable without stretching the calendar.
_JH_DAYS = (0, 2, 4, 5)
_JH_DAYS_POST = _JH_DAYS

# ‼️ THE SEASON MUST BE OVER BY THESE DATES (owner rule 2026-08). Boys play a fall
# season and are DONE BY THE END OF OCTOBER — early November at the absolute latest;
# girls play a spring season and are done by early June. This is not a guideline the
# calendar drifts toward, it is the window the calendar is fitted into: the pattern
# below is chosen per season so the last dual of the postseason lands inside it.
_JH_SEASON_CLOSE = {"boys": (10, 31), "girls": (6, 7)}
_JH_CLOSE_GRACE = 7          # days of slack before the hard stop (the "at the latest")

# Day patterns, loosest first, as weekday offsets from Monday. A high-school week is
# Mon/Wed/Fri/Sat; when a season has more rounds than that can hold, the extra days
# are added rather than letting the season run into December. Never a Sunday: 6 is in
# no pattern.
_JH_PATTERNS = ((0, 2, 4, 5), (0, 1, 2, 4, 5), (0, 1, 2, 3, 4, 5))


def _jh_pattern(opening: _dt.date, close: _dt.date, rounds: int) -> tuple:
    """The loosest day pattern that fits `rounds` between `opening` and `close`.

    Returns the densest one if none fits — a season that genuinely cannot be played
    in the window still has to render, and a too-long season is visible on the card
    rather than silently rescheduled into the winter."""
    weeks = max(1, ((close - opening).days + 6) // 7)
    for pat in _JH_PATTERNS:
        if weeks * len(pat) >= rounds:
            return pat
    return _JH_PATTERNS[-1]


def _jh_day(start: _dt.date, idx: int, pattern: tuple) -> _dt.date:
    wk, k = divmod(idx, len(pattern))
    return start + _dt.timedelta(weeks=wk, days=pattern[k])


def jh_match_key(row: dict) -> tuple:
    """The identity of a DUAL, the same from either side's row: LEVEL, phase, whether
    it was a league match, and the (home, away) pair in that order. A district double
    round robin meets twice with the venue reversed, so ordering the pair by venue
    keeps the two meetings distinct.

    ‼️ `level` IS LOAD-BEARING, not decoration. The same two programs meet at varsity
    and at JV, in the same phase, in the same league — so without it both duals hash to
    ONE key. `_jh_global_order` builds its edges from each school's key sequence, so a
    repeated key becomes a self-edge, its in-degree never reaches zero, and the whole
    gender's topological sort falls into its cycle fallback. Nothing raises; every
    card just quietly stops reading in play order."""
    home = bool(row.get("home"))
    a, b = (row["school"], row["opp"]) if home else (row["opp"], row["school"])
    return (row.get("level") or "v", row.get("phase") or "",
            int(bool(row.get("district"))), a, b)


def _jh_global_order(by_school: dict[str, list[tuple]],
                    seen: dict[tuple, int] | None = None) -> list[tuple]:
    """Every match of the season in one play order.

    Each school's card is already in the order it played, and those orders come
    from one simulation, so a consistent global order exists — recover it with a
    topological sort over "team X played M before N" edges rather than guessing
    from positions. Guessing is what a max-of-positions heuristic does, and it
    reorders a team's own card whenever its opponent had played a different
    number of duals by then."""
    indeg: dict[tuple, int] = {}
    nxt: dict[tuple, list[tuple]] = {}
    for keys in by_school.values():
        for k in keys:
            indeg.setdefault(k, 0)
            nxt.setdefault(k, [])
        for a, b in zip(keys, keys[1:]):
            nxt[a].append(b)
            indeg[b] = indeg.get(b, 0) + 1
    # Ties break on the order the duals were actually ARCHIVED, not alphabetically:
    # district play is generated as rounds (every team plays once per round), so the
    # natural order already groups the matches that can share a day. An alphabetical
    # tie-break scrambles that and the round packing below needs ~35% more rounds to
    # rebuild it.
    import heapq
    seen = seen or {}
    pri = lambda k: (seen.get(k, 0), k)                                 # noqa: E731
    ready = [pri(k) for k, d in indeg.items() if d == 0]
    heapq.heapify(ready)
    out = []
    while ready:
        _, k = heapq.heappop(ready)
        out.append(k)
        for m in nxt.get(k, ()):
            indeg[m] -= 1
            if indeg[m] == 0:
                heapq.heappush(ready, pri(m))
    if len(out) < len(indeg):                 # a cycle: fall back, deterministically
        out += sorted(k for k, d in indeg.items() if d > 0)
    return out


def _jh_showcase_days(slot: dict, opening: _dt.date,
                      days: tuple = _JH_DAYS) -> dict[tuple, _dt.date]:
    """{(showcase phase, round) -> date} — the mid-season showcase WEEKENDS.

    A showcase window is played as consecutive SESSIONS across the whole gender
    (`jhsaa.play_showcases` plays every event's first session before any event's
    second), so a window occupies a contiguous block of rounds and can be landed on
    the calendar as the single event it is: a 1-Day Pod's three sessions all on ONE
    Saturday, a 2-Day Tiered block's four sessions as Friday, Friday, Saturday,
    Saturday. Left to the ordinary Mon/Wed/Fri/Sat pattern they would read as three
    duals on three separate days, which is a different event with different USTA
    daily limits — the pod is scored as a pro set precisely because it is one day.

    A run is cut at the event's own session count, so two windows of the same kind
    played back to back are two weekends rather than one long one, and the weekends
    are walked forward in order so no program is shown at two showcases on one day.
    Still presentation only: nothing reads a date back."""
    from . import jhsaa as _jh
    sizes = {"showcase_pod": _jh.POD_DUALS, "showcase_tiered": _jh.TIER_DUALS}
    rounds: dict[str, set[int]] = {}
    for key, (_rk, r) in slot.items():
        # key is (level, PHASE, district, home, away) — the phase is k[1]. Read off
        # k[0] this matches the level string against showcase phase names, finds
        # nothing, and every showcase silently reverts to the ordinary weekday pattern.
        if key[1] in sizes:
            rounds.setdefault(key[1], set()).add(r)
    chunks: list[tuple[int, str, list[int]]] = []
    for phase, rs in rounds.items():
        run: list[int] = []
        for r in sorted(rs):
            if run and r == run[-1] + 1 and len(run) < sizes[phase]:
                run.append(r)
                continue
            if run:
                chunks.append((run[0], phase, run))
            run = [r]
        if run:
            chunks.append((run[0], phase, run))
    out: dict[tuple, _dt.date] = {}
    used: set[_dt.date] = set()
    for first, phase, rs in sorted(chunks):
        base = _jh_day(opening, first, days)
        sat = base + _dt.timedelta(days=(5 - base.weekday()) % 7)
        # ‼️ A WINDOW IS ANCHORED TO ITS OWN ROUND, never walked forward from the
        # previous window. This used to step every later window a week past the last
        # one — with seven windows in a season the seventh landed a month beyond the
        # rounds it was played in, so a card showed October showcases sitting between
        # September league duals and the dates ran BACKWARDS. Distinct weekends still
        # matter (nobody is at two showcases on one day), so a genuine collision is
        # nudged a week — but only ever within the block's own span, never unbounded.
        limit = _jh_day(opening, rs[-1], days) + _dt.timedelta(days=6)
        while sat in used and sat + _dt.timedelta(days=7) <= limit:
            sat += _dt.timedelta(days=7)
        used.add(sat)
        if phase == "showcase_pod":
            for r in rs:
                out[(phase, r)] = sat
        else:
            fri, cut = sat - _dt.timedelta(days=1), (len(rs) + 1) // 2
            for i, r in enumerate(rs):
                out[(phase, r)] = fri if i < cut else sat
    return out



def _jh_school_groups(world_id: int, year: int, gender: str) -> dict[str, str]:
    """{school: classification} for one archived gender-season, read off the ARCHIVE
    rather than off today's school list.

    A program's classification moves — reclassification, and a play-up changes which
    championship it entered — so the live map would put an old season's duals in the
    wrong lane. The standings are what that season was actually played in."""
    arc = get_jhsaa(world_id, year, gender) or {}
    out: dict[str, str] = {}
    for group, dists in (arc.get("standings") or {}).items():
        for teams in (dists or {}).values():
            for row in teams or ():
                nm = row.get("school") if isinstance(row, dict) else None
                if nm:
                    out[nm] = group
    return out


#: The JV season OPENS a month after varsity's (owner rule 2026-08): girls in April,
#: boys in September. It is a real scheduling reason, not a cosmetic one — varsity's
#: 5S/2D early-invitational window is played in month 1 (measured on the real 2038 save:
#: all 950 girls' and all 871 boys' early duals fall in March and August respectively),
#: and `lineup_need` is NINE there against eleven in the regular season. A JV dual
#: overlapping it would find two more players available and silently size itself off a
#: different varsity lineup. Opening in month 2 steps past the whole window.
_JH_JV_OPEN = {"boys": (9, 1), "girls": (4, 1)}

#: ‼️ AND JV MAY PLAY ON A SUNDAY. Varsity's `_JH_PATTERNS` exclude weekday 6 by
#: construction; JV is explicitly allowed it (owner rule 2026-08: "played whenever and
#: wherever… if that means the next day so be it or utilizing sundays since we don't use
#: them for varsity it doesn't matter at all"). Duals bunching is fine — the ONE
#: requirement is that a varsity dual never waits on a JV one, which is guaranteed
#: upstream by JV never entering the varsity allocator at all.
_JH_JV_DAYS = (0, 1, 2, 3, 4, 5, 6)


def _jh_jv_dates(out: dict, by_school: dict[str, list[tuple]],
                 seen: dict[tuple, int], gender: str,
                 season_year: int) -> None:
    """Date the JV season in place, on its own cursor and its own calendar.

    Deliberately much simpler than the varsity pass: JV has no postseason, so there are
    no stages to separate and no lanes to keep apart — it is one queue of duals packed
    into rounds (a round being duals with no team in common) and laid on a seven-day
    week from the JV opener. No season-close fitting either: JV cannot overrun a window
    it does not have to finish inside, and a JV dual slipping past the varsity final is
    not a fault."""
    if not by_school:
        return
    mon, day = _JH_JV_OPEN.get(gender, _JH_JV_OPEN["girls"])
    opening = _dt.date(season_year, mon, day)
    opening += _dt.timedelta(days=-opening.weekday() % 7)          # first Monday
    order = _jh_global_order(by_school, seen)
    nxt: dict[str, int] = {}
    for key in order:
        a_s, b_s = key[3], key[4]
        r = max(nxt.get(a_s, 0), nxt.get(b_s, 0))
        nxt[a_s] = nxt[b_s] = r + 1
        out[key] = _jh_day(opening, r, _JH_JV_DAYS)
    # Same monotonic guarantee the varsity card gets: a program's JV schedule reads in
    # date order, whatever dated it.
    last: dict[str, _dt.date] = {}
    for key in order:
        floor = max((last[x] for x in (key[3], key[4]) if x in last), default=None)
        if floor is not None and out[key] < floor:
            out[key] = floor
        last[key[3]] = last[key[4]] = out[key]


def jhsaa_match_dates(world_id: int, year: int, gender: str,
                      season_year: int | None) -> dict[tuple, _dt.date]:
    """{match key -> date} for one archived gender-season. One date per dual, so
    both schools' cards agree. Cached per (world, year, gender)."""
    ck = (world_id, year, gender, season_year)
    hit = _JH_CAL_CACHE.get(ck)
    if hit is not None:
        return hit
    out: dict[tuple, str] = {}
    if not season_year:
        return out
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT rowid, school, opp, home, phase, district, level"
            " FROM world_jhsaa_dual"
            " WHERE world_id=? AND year=? AND gender=? ORDER BY rowid",
            (world_id, year, gender)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    # ‼️ JV NEVER ENTERS THE VARSITY ALLOCATOR (owner rule 2026-08). The packing below
    # advances a per-school cursor on every distinct key, so a JV dual sharing a school
    # with a varsity one would take a LATER round and push the varsity season out — the
    # two seasons would serialise, the calendar would overrun its window, and every
    # individual card would still read perfectly. Only the SPAN would be wrong, which is
    # exactly how `AAR-jhsaa-postseason-calendar-lanes.md` hid for as long as it did.
    # JV is dated by `_jh_jv_dates` afterwards, off its own cursor and its own pattern.
    by_school: dict[str, list[tuple]] = {}
    seen: dict[tuple, int] = {}
    jv_by_school: dict[str, list[tuple]] = {}
    jv_seen: dict[tuple, int] = {}
    for r in rows:
        d = dict(r)
        k = jh_match_key(d)
        if (d.get("level") or "v") == "jv":
            jv_by_school.setdefault(r["school"], []).append(k)
            jv_seen.setdefault(k, r["rowid"])
        else:
            by_school.setdefault(r["school"], []).append(k)
            seen.setdefault(k, r["rowid"])
    from . import jhsaa as _jh
    rank = {p: i + 1 for i, p in enumerate(_jh.POSTSEASON)}
    # Play order first, then STAGE — a topological order alone interleaves the
    # stages across schools (one school's Sectional can sort before another's
    # last regular dual), and a stage floor that moves forward on every switch
    # then drags the regular season through the whole calendar. A team's own
    # matches already run regular -> Sectionals -> ... -> State, so a stable
    # sort by stage keeps each card in order while separating the stages.
    # ‼️ `k[1]`, not `k[0]` — `jh_match_key` puts LEVEL first now. Read off k[0] this
    # sorts every dual by the string "v", i.e. not at all, and the postseason stages
    # stop being separated from the regular season.
    order = sorted(_jh_global_order(by_school, seen),
                   key=lambda k: rank.get(k[1], 0))
    mon, day = _JH_SEASON_OPEN.get(gender, _JH_SEASON_OPEN["girls"])
    opening = _dt.date(season_year, mon, day)
    opening += _dt.timedelta(days=-opening.weekday() % 7)          # first Monday

    # Pack matches into ROUNDS: a round is a set of duals with no team in common,
    # so everything that could be played on one day is. Assigning day-by-day in
    # play order instead lets the constraint chain through opponents — A waits on
    # B, B on C — and a ~26-dual card sprawled over three months. A team's round
    # numbers are strictly increasing, so its card still reads in order.
    # ‼️ EACH CLASSIFICATION GETS ITS OWN POSTSEASON LANE (owner rule 2026-08).
    # The stage floor used to be GLOBAL: `floor_r = top_r + 1` over the whole gender,
    # so 7A's Regionals could not begin until 2A-1A's Sectionals had finished. Eight
    # classifications that never play each other were serialised into one queue, and
    # the eleven-stage ladder therefore cost eight times what any one class actually
    # plays — which is what pushed the boys' postseason into January and the girls'
    # into July.
    #
    # A class's stage now waits only on the PREVIOUS STAGE OF ITS OWN CLASS. Every
    # lane opens at the same postseason window and advances independently, so the
    # postseason lasts as long as the longest single class's ladder rather than the
    # sum of all eight.
    #
    # PRESENTATION ONLY. Match order, qualification and results are untouched: this
    # function reads the finished archive and decides nothing but what day a dual is
    # printed on.
    #
    # The REGULAR season stays on one shared calendar — invitationals and showcases
    # cross classifications, so those duals genuinely do share a queue.
    #
    # ‼️ THE TOC IS NOT A LANE. It fields the champions of every classification, so it
    # is the one postseason event with a real cross-class dependency: it waits on all
    # of them. Giving it a lane of its own (keyed on neither school's group) would let
    # it be dated before a state final it depends on.
    group_of = _jh_school_groups(world_id, year, gender)
    slot: dict[tuple, tuple] = {}
    nxt: dict[str, int] = {}
    reg_floor, reg_top = 0, -1
    lane_rank: dict[str, int] = {}
    lane_floor: dict[str, int] = {}
    lane_top: dict[str, int] = {}
    post_base: int | None = None
    for key in order:
        _lvl, phase, _dist, a_s, b_s = key
        r_rank = rank.get(phase, 0)
        if not r_rank:                                     # regular season, one queue
            r = max(reg_floor, nxt.get(a_s, 0), nxt.get(b_s, 0))
            nxt[a_s] = nxt[b_s] = r + 1
            reg_top = max(reg_top, r)
            slot[key] = (0, r)
            continue
        if post_base is None:                              # every lane opens together
            post_base = reg_top + 1
        lane = "" if phase == "toc" else (group_of.get(a_s) or group_of.get(b_s) or "")
        if lane_rank.get(lane) != r_rank:                  # this LANE's next stage
            base = (max(lane_top.values(), default=post_base - 1) if phase == "toc"
                    else lane_top.get(lane, post_base - 1))
            lane_floor[lane], lane_rank[lane] = base + 1, r_rank
        r = max(lane_floor[lane], post_base, nxt.get(a_s, 0), nxt.get(b_s, 0))
        nxt[a_s] = nxt[b_s] = r + 1
        lane_top[lane] = max(lane_top.get(lane, -1), r)
        slot[key] = (r_rank, r)

    reg_rounds = max((r for (rk, r) in slot.values() if rk == 0), default=-1) + 1
    # ‼️ ONE CONTINUOUS ROUND INDEX, AND A PATTERN CHOSEN TO FIT THE WINDOW. The
    # postseason used to restart its own count at the Monday after the regular season,
    # which inserted a break and — with the count fixed at four days a week — let the
    # season run wherever it ran. A boys' season finishing in December is wrong on its
    # face: it is a FALL sport and it is over by the end of October.
    #
    # The postseason lanes already continue the same counter, so `r` is a global index
    # for the whole season; the only choice left is how many days a week it is laid on,
    # and that is now derived from how many rounds have to fit rather than fixed.
    mon_c, day_c = _JH_SEASON_CLOSE.get(gender, _JH_SEASON_CLOSE["girls"])
    close = _dt.date(season_year, mon_c, day_c) + _dt.timedelta(days=_JH_CLOSE_GRACE)
    total = max((r for (_rk, r) in slot.values()), default=0) + 1
    days = _jh_pattern(opening, close, total)
    weekend = _jh_showcase_days(slot, opening, days)
    for key, (_r_rank, r) in slot.items():
        out[key] = weekend.get((key[1], r)) or _jh_day(opening, r, days)

    # ‼️ A CARD READS IN DATE ORDER, and that is a GUARANTEE rather than something
    # the round arithmetic happens to produce. Anything that dates a dual outside the
    # ordinary round pattern — the showcase weekends do, and a future event would —
    # can otherwise land a match before one its own team already played, which is how
    # October showcases came to sit between September league duals.
    #
    # So: walk the play order and hold each dual on or after the last date either of
    # its teams has been given. Nothing is reordered — the sequence is the archive's
    # and is not up for revision — only pushed forward to the next available slot in
    # the same pattern, which is what a real fixture list does when a date slips.
    seen: dict[str, _dt.date] = {}
    for key in order:
        # key is (level, phase, district, home, away) — the schools are the LAST TWO.
        floor = max((seen[s] for s in (key[3], key[4]) if s in seen), default=None)
        if floor is not None and out[key] < floor:
            out[key] = floor
        seen[key[3]] = seen[key[4]] = out[key]
    _jh_jv_dates(out, jv_by_school, jv_seen, gender, season_year)

    if len(_JH_CAL_CACHE) >= _JH_CAL_MAX:      # prune per season, never a global clear
        for k in list(_JH_CAL_CACHE)[:len(_JH_CAL_CACHE) - _JH_CAL_MAX + 1]:
            _JH_CAL_CACHE.pop(k, None)
    _JH_CAL_CACHE[ck] = out
    return out


def jhsaa_schedule(world_id: int, year: int, gender: str, school: str) -> list[dict]:
    """One school's season, match by match, in the order it was played."""
    conn = _db()
    try:
        return _schedule_rows(conn, world_id, year, gender, school)
    finally:
        conn.close()


def jhsaa_dual_row(dual_id: int) -> dict | None:
    """Raw read of ONE side of a JHSAA dual, by `world_jhsaa_dual` rowid — the
    Match Center's lookup key (`state.jhsaa_dual_view`). Either side's row is
    enough to render the whole dual: `lines` is the SAME shared list on both
    (`play_dual` appends it to both teams' schedule entries — see
    `state._jh_reported_lines`'s docstring), and each line's `home_won`/`home`/
    `away` keys already name the true home team regardless of which row this
    is. Only this school's own `pf`/`pa`/`home` flag differ by row, and the
    caller normalizes those against `home` to get true home/away points.

    `school`/`opp` are canonicalized (renamed programs) for DISPLAY — but the
    raw, as-archived values are kept too (`school_raw`/`opp_raw`), because a
    companion-row lookup (`jhsaa_home_row_id`) must match the string that is
    actually stored on the other row, not today's display name."""
    conn = _db()
    try:
        r = conn.execute(
            "SELECT rowid AS id, world_id, year, gender, school, opp, home, phase,"
            " pf, pa, won, district, lines, level, tied, shape, played"
            " FROM world_jhsaa_dual WHERE rowid=?", (dual_id,)).fetchone()
    finally:
        conn.close()
    if not r:
        return None
    from . import jhsaa as _jh
    d = dict(r)
    alias = _jh.former_names()
    d["school_raw"] = d["school"]
    d["opp_raw"] = d["opp"]
    d["school"] = alias.get(d["school"], d["school"])
    d["opp"] = alias.get(d["opp"], d["opp"])
    d["lines"] = json.loads(d["lines"] or "[]")
    return d


def jhsaa_home_row_id(world_id: int, year: int, gender: str, level: str,
                      school_raw: str, opp_raw: str) -> int | None:
    """The rowid of the HOME side's row for one specific dual, given the RAW
    (as-archived) names of both schools. `jhsaa_prior_meetings` only ever
    returns `home=1` rows, so excluding "the dual currently being viewed"
    from it needs that row's id — even when the page was opened from the
    AWAY school's schedule, whose own rowid is the `home=0` sibling and so
    never appears in that result set at all."""
    conn = _db()
    try:
        r = conn.execute(
            "SELECT rowid AS id FROM world_jhsaa_dual WHERE world_id=? AND year=?"
            " AND gender=? AND COALESCE(level,'v')=? AND home=1 AND school=? AND opp=?",
            (world_id, year, gender, level, school_raw, opp_raw)).fetchone()
    finally:
        conn.close()
    return r["id"] if r else None


def jhsaa_prior_meetings(world_id: int, gender: str, home: str, away: str,
                         level: str = "v", exclude_id: int | None = None) -> list[dict]:
    """The Match Center's head-to-head tab: EVERY past meeting between this
    pair, most recent first — the full series (see `matchcenter.
    summarize_series`), not a capped "recent form" list. Reads only the HOME
    side's row of each past dual (`home=1`) since the two rows of one dual
    duplicate each other from either school's perspective — without that
    filter every past meeting would double-count.

    ‼️ SCOPED TO ONE `level`. Varsity and JV share `world_jhsaa_dual`,
    distinguished only by that column (same trap as everywhere else in this
    table — see `_jh_line_records`'s docstring); without the filter a
    varsity Match Center could show JV results as head-to-head history.

    ‼️ MATCHES ON EVERY NAME EITHER PROGRAM HAS EVER CARRIED
    (`jhsaa.known_names`), not just today's — a renamed program's older
    meetings are archived under its old name, on both sides of the pairing,
    so a lookup on the current names alone silently drops them (the same
    reason `world._schedule_rows` resolves `known_names` before querying).

    `postseason` is `phase in jhsaa.POSTSEASON` (Sectional through TOC —
    everything past the league season and the mid-season showcases).

    ‼️ `label` IS A REAL CALENDAR DATE where one exists (`jhsaa_match_dates`
    — the same per-dual display calendar the school schedule page already
    reads, see `state._jh_dates`), not just a year. That function is ALREADY
    cached per `(world_id, year, gender)` (`_JH_CAL_CACHE`), so calling it
    once per meeting costs nothing extra past the first meeting of a given
    year — no second cache needed here. Falls back to the season year alone
    when a date can't be found (an archive older than the calendar system,
    or the rare row a showcase/edge case doesn't cover) — a missing date is
    a display gap, not a reason to drop the meeting."""
    from . import jhsaa as _jh
    home_names = _jh.known_names(home, gender)
    away_names = _jh.known_names(away, gender)
    alias = _jh.former_names()
    conn = _db()
    try:
        qmarks_h = ",".join("?" * len(home_names))
        qmarks_a = ",".join("?" * len(away_names))
        rows = conn.execute(
            "SELECT rowid AS id, year, school, opp, pf, pa, phase, district"
            " FROM world_jhsaa_dual"
            " WHERE world_id=? AND gender=? AND home=1 AND COALESCE(level,'v')=?"
            f" AND ((school IN ({qmarks_h}) AND opp IN ({qmarks_a}))"
            f"  OR (school IN ({qmarks_a}) AND opp IN ({qmarks_h})))"
            " ORDER BY year DESC, rowid DESC",
            (world_id, gender, level, *home_names, *away_names, *away_names, *home_names)
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        if exclude_id is not None and r["id"] == exclude_id:
            continue
        season_year = BASE_YEAR + r["year"] + 1
        cal = jhsaa_match_dates(world_id, r["year"], gender, season_year)
        # `home=1` on every fetched row, so this row's own (school, opp) IS
        # the (home, away) pair `jh_match_key` wants — no need to rebuild a
        # dict just to hand it to that function.
        day = cal.get((level, r["phase"] or "", int(bool(r["district"])), r["school"], r["opp"]))
        label = f"{day:%b} {day.day}, {season_year}" if day else str(season_year)
        out.append({"id": r["id"], "label": label,
                    "home": alias.get(r["school"], r["school"]),
                    "away": alias.get(r["opp"], r["opp"]),
                    "home_points": int(r["pf"]), "away_points": int(r["pa"]),
                    "postseason": r["phase"] in _jh.POSTSEASON})
    return out


def jhsaa_school_injuries(world_id: int, year: int, gender: str,
                          school: str) -> list[dict]:
    """One VARSITY season's injury log for one school, in the order they
    happened. JV never appears here — see `jhsaa.TeamSeason`."""
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT pid, name, dual_index, duals_out, season_ending"
            " FROM world_jhsaa_injury"
            " WHERE world_id=? AND year=? AND gender=? AND school=?"
            " ORDER BY dual_index", (world_id, year, gender, school)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# --- reading the archive back: a program's SEASON LEDGER ----------------------
# A JHSAA program's history is a ledger of SEASONS. Honours annotate a season; they are
# not the history — "was this program ever good", "when was the last title", "are they
# improving" are all questions about the season rows, and a list of All-State names
# answers none of them.
#
# Everything below is DERIVED from the accumulated archive — `world_jhsaa`'s per-school
# record/drecord/place, its state brackets and award lists, plus that school's own rows
# in `world_jhsaa_dual` — and never re-simulated. The archive is append-only (one row
# per world-year × gender), so year N's numbers cannot move when year N+1 is played;
# that is the whole persistence guarantee, and `tests/test_jhsaa_history.py` pins it.

def _finish_label(alive: int) -> str:
    """A finish, named by how many teams were still in the draw. Banded rather than
    keyed exactly, because a standalone non-power-of-two field pads with byes that
    collapse unevenly, so a "semifinal" round can legitimately hold three teams.
    Pre-state stage finishes (Sectionals/Wards/Regionals/Zonals) come off their own
    archived dicts (`jhsaa_postseason_result`), never from a team count."""
    if alive <= 0:
        return ""
    if alive == 1:
        return "Champion"
    if alive == 2:
        return "Runner-up"
    if alive <= 4:
        return "Semifinalist"
    if alive <= 8:
        return "Quarterfinalist"
    if alive <= 16:
        return "Octofinalist"
    return f"Round of {alive}"


def _round_label(alive: int) -> str:
    """The same bands, named as the ROUND rather than as one team's finish."""
    if alive <= 2:
        return "Championship"
    if alive <= 4:
        return "Semifinals"
    if alive <= 8:
        return "Quarterfinals"
    if alive <= 16:
        return "Octofinals"
    return f"Round of {alive}"


def jhsaa_state_rounds(bracket: dict) -> list[dict]:
    """An archived bracket as named rounds, each with the number of teams still
    alive going into it.

    `alive` is counted DOWN from the field — every game eliminates exactly one
    team — rather than assumed to halve, so odd shapes (old archives, standalone
    non-power-of-two fields) still read. A dict carrying its own `round_names`
    (the pre-state stages — Sectionals/Wards/Regionals/Zonals) names its rounds
    itself; otherwise the name is banded off the team count (the State bracket,
    old archives)."""
    br = bracket or {}
    alive = len(br.get("field") or ())
    names = br.get("round_names") or ()
    out = []
    for i, games in enumerate(br.get("rounds") or ()):
        name = names[i] if i < len(names) else _round_label(alive)
        out.append({"name": name, "alive": alive, "games": list(games)})
        alive -= len(games)
    return out


def jhsaa_state_result(bracket: dict, school: str) -> dict:
    """How far `school` went in one archived State bracket — pre-state stages are
    `jhsaa_postseason_result`'s job.

    `place` is the number of teams STILL ALIVE when it was eliminated — 1 champion,
    2 runner-up, 3-4 semifinalist, 9-16 octofinalist — so "reached the semis" is
    `place <= 4`, a number, never a string comparison against a label. `seed` is the
    program's position in the field that was actually drawn (post-Zonal TOSS order),
    read back off the persisted bracket rather than recomputed from a live ranking —
    the same rule that keeps the NCAA bracket's labels from drifting."""
    br = bracket or {}
    field = list(br.get("field") or ())
    out = {"made_state": False, "seed": 0, "place": 0, "finish": "", "champion": False}
    if school not in field:
        return out
    champion = br.get("champion") == school
    rounds = jhsaa_state_rounds(br)
    last = None
    for rd in rounds:
        if any(school in (gm.get("home"), gm.get("away")) for gm in rd["games"]):
            last = rd
    # The champion is read off the archive, not inferred from "won its last game" —
    # a bye means a program can sit out a round without being out of the tournament.
    place = 1 if champion else (last["alive"] if last else len(field))
    out.update(made_state=True, seed=field.index(school) + 1, place=place,
               finish=_finish_label(place), champion=champion)
    return out


def jhsaa_postseason_result(grp: dict, school: str) -> dict:
    """The furthest `school`'s postseason reached, across every archived stage of a
    group's postseason (`{"sectional", "ward", "prestate", "super_regional",
    "semi_state", "state", ...}` — the keys `run_season` writes per group). One
    call for a program page or ledger row; a State entrant takes priority, then
    the stages walk backward, RECOVERY rounds before the ladder round the school
    lost (a Regionals loser that fought through Super Regionals ended its year at
    Semi-State or State, never at "Regionals"). `finish` for a pre-state exit is
    the stage's own name — "Areas" / "Sectionals" / "Wards" / "Regionals" /
    "Zonals" / "Super Regionals" / "Semi-State" — never a team-count band.
    Old archives (16-team State, TOSS wild cards under a "wildcards" key, no
    recovery stages) fall through unchanged."""
    grp = grp or {}
    sec_field = (grp.get("sectional") or {}).get("field") or ()
    st = jhsaa_state_result(grp.get("state") or {}, school)
    if st["made_state"]:
        return {**st, "played_sectional": school in sec_field,
                "wildcard": school in (grp.get("wildcards") or ()),
                "district_qualifier": school in (grp.get("district_qualifiers") or ())}
    out = {"made_state": False, "seed": 0, "place": 0, "finish": "",
           "champion": False, "played_sectional": school in sec_field,
           "wildcard": False, "district_qualifier": False}
    # A recovery run supersedes the ladder loss that sent the school there,
    # deepest rung first — the CONFERENCE is the last one played, so a school
    # that reached it did not end its year at Sectionals.
    # STATE SPECIALS sit between the Conference and the State draw — a team whose
    # year ended there got the road's very last dual, so its finish supersedes
    # whatever rung sent it in (the recovery-supersedes rule, one round further).
    if school in ((grp.get("state_special") or {}).get("field") or ()):
        from . import jhsaa as _jh
        out["finish"] = _jh.STATE_SPECIAL_FINISH        # "Specials" (owner, 2026-08)
        return out
    # THE SPECIAL CHALLENGERS sit between the Conference and the Specials: a
    # bridge winner is in the Specials field above and never reaches here, so
    # this is exactly the set whose year ended in the bridge dual — a contested
    # challenger who lost their seat, or an eligible early exit whose one extra
    # crack fell short. Both finish at "Challengers" (owner, 2026-08),
    # superseding whatever rung sent them in — the recovery-supersedes rule.
    if school in ((grp.get("special_challenger") or {}).get("field") or ()):
        from . import jhsaa as _jh
        out["finish"] = _jh.SPECIAL_CHALLENGER_FINISH
        return out
    if school in ((grp.get("conference") or {}).get("field") or ()):
        from . import jhsaa as _jh
        out["finish"] = _jh.CONFERENCE_NAME
        return out
    # The SEMI-CONFERENCE sits between the two: a school that won it is in the
    # Conference field above and never reaches here, so this is exactly the set
    # that qualified for the last rung and lost trying.
    if school in ((grp.get("semi_conference") or {}).get("field") or ()):
        from . import jhsaa as _jh
        out["finish"] = _jh.SEMI_CONFERENCE_NAME
        return out
    if school in ((grp.get("divisional") or {}).get("field") or ()):
        from . import jhsaa as _jh
        out["finish"] = _jh.DIVISIONAL_NAME
        return out
    if school in ((grp.get("semi_state") or {}).get("field") or ()):
        out["finish"] = "Semi-State"
        return out
    if school in ((grp.get("super_regional") or {}).get("field") or ()):
        out["finish"] = "Super Regionals"
        return out
    pre = grp.get("prestate") or {}
    if school in (pre.get("field") or ()):
        # Eliminated at Regionals (round 0) or Zonals (round 1): the last round
        # the school appears in names its finish.
        names = pre.get("round_names") or ("Regionals", "Zonals")
        last = 0
        for i, games in enumerate(pre.get("rounds") or ()):
            if any(school in (gm.get("home"), gm.get("away")) for gm in games):
                last = i
        out["finish"] = names[min(last, len(names) - 1)]
        return out
    if school in ((grp.get("ward") or {}).get("field") or ()):
        out["finish"] = "Wards"
        return out
    if school in sec_field:
        # A multi-round Sectionals OPENS WITH AREAS (owner rule —
        # jhsaa.run_sectional): the last round is the one named Sectionals, so a
        # run that ended in an earlier round ended at Areas and the ledger says
        # so. The archived round_names carry the split; old archives (all rounds
        # named "Sectionals") fall through unchanged.
        sec = grp.get("sectional") or {}
        names = sec.get("round_names") or ()
        last = 0
        for i, games in enumerate(sec.get("rounds") or ()):
            if any(school in (gm.get("home"), gm.get("away")) for gm in games):
                last = i
        out["finish"] = names[last] if last < len(names) else "Sectionals"
        return out
    return out


def _toc_finish_label(alive: int) -> str:
    """A Tournament of Champions finish.

    Same arithmetic as `_finish_label` — place is teams still alive — but its own
    labels, because the events are different shapes and the shared bands lie about
    this one. `_finish_label` bands 5-8 as "Quarterfinalist"; a six-team meta-event
    has no quarterfinal, so a program that lost its opening dual would be credited
    with a round it never played.

    Now that the field runs to eleven classifications, `run_toc` plays a genuine
    Quarterfinal round (entering alive=8) ABOVE a play-in round for the bottom
    seeds (entering alive=9+, the round `_round_label` names "Octofinals") — two
    real, distinct rounds, so each gets its own band, mirroring `_round_label`'s
    own banding rather than lumping both under one generic "Opening Round"."""
    if alive <= 0:
        return ""
    if alive == 1:
        return "TOC Champion"
    if alive == 2:
        return "TOC Runner-up"
    if alive <= 4:
        return "TOC Semifinalist"
    if alive <= 8:
        return "TOC Quarterfinalist"
    if alive <= 16:
        return "TOC Octofinalist"
    return "TOC Opening Round"


def jhsaa_toc_result(toc: dict, school: str) -> dict:
    """How far `school` went in one archived Tournament of Champions.

    The TOC is archived in exactly the shape `run_state` writes, which is why this
    reuses the state draw's arithmetic wholesale rather than walking the rounds a
    second time. Only the labels are the event's own."""
    st = jhsaa_state_result(toc, school)
    return {"made_toc": st["made_state"], "toc_seed": st["seed"],
            "toc_place": st["place"], "toc_finish": _toc_finish_label(st["place"]),
            "toc_champion": st["champion"]}


def jhsaa_title_stages() -> list[tuple[str, str, str]]:
    """The ROAD's rounds, in ladder order, as `(archived round name, short column,
    full label)`.

    ‼️ THE NAMES COME FROM `jhsaa`'S OWN CONSTANTS, never typed here. A stage's
    archived `round_names` entry is what a unit win is bucketed by, so a renamed
    round (`DIVISIONAL_NAME` has moved once already) must move the column with it
    rather than silently emptying it — a title board that quietly stops counting
    Divisionals looks exactly like an association that stopped playing them."""
    import app.jhsaa as jh
    return [("Areas", "AREA", "Area titles"),
            ("Sectionals", "SECT", "Sectional titles"),
            (jh._STAGE_NAMES["ward"], "WARD", "Ward titles"),
            (jh._STAGE_NAMES["regional"], "REG", "Regional titles"),
            (jh._STAGE_NAMES["zonal"], "ZONE", "Zonal titles — an automatic State berth"),
            (jh._RECOVERY_NAMES["super_regional"], "S-REG", "Super Regional titles"),
            (jh._RECOVERY_NAMES["semi_state"], "S-ST", "Semi-State titles — a State berth"),
            (jh._RECOVERY_NAMES["divisional"], "DIV", "Divisional titles — a State berth"),
            (jh._RECOVERY_NAMES["semi_conference"], "S-CON",
             "Semi-Conference wins — a seat in the Conference, never a berth"),
            (jh._RECOVERY_NAMES["conference"], "CON", "Conference titles — a State berth"),
            (jh._RECOVERY_NAMES["special_challenger"], "CHAL",
             "Challenge wins — a contested seat in the State Specials, never a "
             "berth"),
            (jh._RECOVERY_NAMES["state_special"], "SPEC",
             "State Special wins — the reconciliation berth, played only when the "
             "road left the field short")]


#: The archive keys every unit-bearing stage is written under, in ladder order.
_JH_STAGE_KEYS = ("sectionals", "wards", "prestate", "super_regional", "semi_state",
                  "divisional", "semi_conference", "conference",
                  "special_challenger", "state_special")

#: A State finish, as a title-board column: `(key, full label)`. Keyed on the
#: `_finish_label` BAND rather than on a round index, because a field that is not a
#: power of two does not halve out of the gate — the same reason a finish is counted
#: down from teams still alive. The short keys are `state._FINISH_SHORT`'s, so the
#: board's columns and the FINISH column on the rankings page read the same.
JH_STATE_COLUMNS = (("CHAMP", "State championships"), ("F", "State finals reached"),
                    ("SF", "State semifinals reached"),
                    ("QF", "State quarterfinals reached"),
                    ("OF", "State octofinals reached"),
                    ("R1", "State first round"),
                    ("QUAL", "State qualifying round"))
_JH_STATE_COLS = tuple(k for k, _l in JH_STATE_COLUMNS)


def _jh_state_col(place: int) -> str:
    """Which State column a finish falls in. `_finish_short` (the display helper) is
    the same banding; this returns the KEY, so the two cannot drift apart."""
    if place <= 0:
        return ""
    if place == 1:
        return "CHAMP"
    if place == 2:
        return "F"
    if place <= 4:
        return "SF"
    if place <= 8:
        return "QF"
    if place <= 16:
        return "OF"
    # Both "Round of N" labels are real ROUNDS, not one: every field converges on the
    # same 24-team main draw at the Octofinals, so a team still alive above 24 went out
    # in the QUALIFIERS and one out at 24 went out in the First Round.
    return "QUAL" if place > 24 else "R1"


def jhsaa_title_board(world_id: int, gender: str) -> dict:
    """Every trophy every program has won, folded out of the archive.

    ‼️ ONE PASS PER SEASON, NOT ONE PER SCHOOL. `_season_row` answers this question
    for ONE program and reads the whole year's archive to do it, so asking it for ~860
    programs across every archived season would re-read each season ~860 times. This
    walks each season's archive ONCE and credits whoever it names — the same numbers,
    at the cost of the program-history page rather than 860 of them.

    ‼️ AND IT IS A FOLD, NOT A STORE (the rule that governs the whole section):
    the archive already determines every number here, so there is no
    `world_jhsaa_titles` table to drift from it. A season is counted by being
    archived, and a re-read of the same archive gives the same board.

    Cells are COUNTS. The road's are TITLES — units won (`unit` on the archived dual,
    bucketed by the stage's own `round_names`) — while State's are FINISHES, because
    the State event has exactly one title per class and "how often did they reach the
    semis" is the question a championship column can answer.
    """
    # ‼️ RESOLVED ONCE, not per row and not per season: `jhsaa_title_stages` reads
    # another module's constants, and the whole point of this function is that the
    # per-season work happens once.
    stages = jhsaa_title_stages()
    stage_col = {name: short for name, short, _lbl in stages}
    rows: dict = {}

    def row(school: str) -> dict:
        r = rows.get(school)
        if r is None:
            r = rows[school] = {
                "school": school, "group": "", "first": None, "last": None,
                "seasons": 0, "dist": 0, "state_apps": 0, "toc_apps": 0, "toc": 0,
                "titles": 0, "trophies": 0,
                **{c: 0 for c in _JH_STATE_COLS},
                **{s: 0 for _n, s, _l in stages}}
        return r

    years = jhsaa_years(world_id, gender)
    for year in years:
        arc = get_jhsaa(world_id, year, gender)
        if not arc:
            continue
        # --- the league season: who played, in what class, and who won it ---
        for grp, dists in (arc.get("standings") or {}).items():
            for dname, teams in (dists or {}).items():
                for t in teams or ():
                    r = row(t.get("school", ""))
                    r["seasons"] += 1
                    # `group` is the class the program last played in AS ARCHIVED —
                    # reclassification and play-up both move a program, so the class
                    # filter must read the season, never today's school list.
                    r["group"] = grp
                    r["first"] = year if r["first"] is None else min(r["first"], year)
                    r["last"] = year if r["last"] is None else max(r["last"], year)
                    if t.get("place") == 1 and dname:
                        r["dist"] += 1
        # --- the road: every unit won, bucketed by the stage that named it ---
        for key in _JH_STAGE_KEYS:
            for _grp, d in ((arc.get(key) or {}).items()):
                names = (d or {}).get("round_names") or ()
                for i, games in enumerate((d or {}).get("rounds") or ()):
                    col = stage_col.get(names[i] if i < len(names) else "")
                    if not col:
                        continue
                    for gm in games:
                        if gm.get("winner") and gm.get("unit"):
                            row(gm["winner"])[col] += 1
        # --- the State event: a finish for every entrant ---
        for _grp, br in ((arc.get("brackets") or {}).items()):
            for school in (br or {}).get("field") or ():
                st = jhsaa_state_result(br, school)
                r = row(school)
                r["state_apps"] += 1
                col = _jh_state_col(st["place"])
                if col:
                    r[col] += 1
        # --- the Tournament of Champions: its own event, so its own columns ---
        toc = arc.get("toc") or {}
        for school in toc.get("field") or ():
            r = row(school)
            r["toc_apps"] += 1
            if jhsaa_state_result(toc, school)["champion"]:
                r["toc"] += 1

    for r in rows.values():
        # Two totals, because they answer different questions: `titles` is every
        # trophy in the cabinet (league, road, State, TOC), `trophies` the ones a
        # program hangs a banner for — a State or TOC championship.
        r["titles"] = (r["dist"] + r["CHAMP"] + r["toc"]
                       + sum(r[s] for _n, s, _l in stages))
        r["trophies"] = r["CHAMP"] + r["toc"]
    return {"rows": sorted(rows.values(), key=lambda r: (-r["titles"], r["school"])),
            "years": years}


def jhsaa_group_ranking(arc: dict, group: str) -> list[dict]:
    """Every program in one classification, ordered the way the JHSAA itself orders
    them — by the TOSS Power Index the season was seeded on (`jhsaa.power_index`).

    The index is read back off the ARCHIVE, never recomputed: it is exactly the number
    at-large selection and the state seeds were drawn from, so the ranking a program
    page shows and the seed it carries into the bracket cannot disagree. Seasons
    archived before TOSS existed carry no `pi`, and fall back to the win rate and point
    differential they were actually ordered on at the time."""
    rows, rated = [], True
    for dname, teams in (((arc or {}).get("standings") or {}).get(group) or {}).items():
        for r in teams:
            w, l = _wl(r.get("record"))
            if r.get("pi") is None:
                rated = False
            rows.append({"school": r.get("school", ""), "district": dname,
                         "wins": w, "losses": l, "record": r.get("record", ""),
                         "drecord": r.get("drecord", ""), "place": r.get("place", 0),
                         "pct": w / (w + l) if (w + l) else 0.0,
                         "pi": r.get("pi"), "atr": r.get("atr"),
                         # The format-transition readout, flattened onto the row by
                         # `jhsaa._flat_format_profile` at archive time — read back, never
                         # recomputed, same as pi/atr. `None` on any season archived before
                         # this existed, exactly like `atr` before it.
                         "sc_n": r.get("sc_n") or 0, "sc_pct": r.get("sc_pct"),
                         "fmt_shift": r.get("fmt_shift"), "dbl_plus": r.get("dbl_plus"),
                         "sc_stdev": r.get("sc_stdev"),
                         # Damped, 0-centred readings — what the table shows. A season
                         # archived before these existed falls back to the raw delta,
                         # so old rows still render rather than blanking.
                         "fmt_pts": r.get("fmt_pts", r.get("fmt_shift")),
                         "dbl_pts": r.get("dbl_pts"),
                         "pf": r.get("pf") or 0.0, "pa": r.get("pa") or 0.0})
    if rated:
        rows.sort(key=lambda r: (-(r["pi"] or 0.0), r["school"]))
    else:
        rows.sort(key=lambda r: (-r["pct"], -(r["pf"] - r["pa"]), r["school"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def _wl(record: str | None) -> tuple[int, int]:
    """"25-6" -> (25, 6). Blank/malformed reads as 0-0 rather than raising: an archive
    written before a field existed must degrade, not 500 a program page."""
    w, _, l = (record or "").partition("-")
    try:
        return int(w or 0), int(l or 0)
    except ValueError:
        return 0, 0


# --- TEAM tournament honours (owner rule 2027-08) ------------------------------
# Every non-state postseason dual is a named, numbered UNIT on purpose ("Regional
# 9", "Ward 4"), and winning one is an honour the program keeps — written the
# association's way, with ROMAN numerals: "Region IX", "Ward IV" (Zonals keep
# their letters: "Zone C"). A season's unit wins all render on ONE honours line
# (state has plenty of its own); making State earns a separate line of its own.
_UNIT_HONOUR = {"Area": "Area", "Section": "Section", "Ward": "Ward",
                "Regional": "Region", "Zonal": "Zone",
                "Super Regional": "Super Region", "Semi-State": "Semi-State"}


def _roman(n: int) -> str:
    vals = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
            (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
            (5, "V"), (4, "IV"), (1, "I"))
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def _unit_honour(unit: str) -> str:
    """'Regional 9' -> 'Region IX'; 'Division 11' -> 'Division XI' (the count is
    statewide, the numeral is Roman like every other unit); 'Zonal C' -> 'Zone C'
    (letters stay letters)."""
    head, _, tail = unit.rpartition(" ")
    name = _UNIT_HONOUR.get(head, head)
    return f"{name} {_roman(int(tail))}" if tail.isdigit() else f"{name} {tail}"


def _unit_wins(arc: dict, group: str, school: str) -> list[str]:
    """The tournament units `school` won that season, in ladder order. Archives
    from before units existed carry no `unit` keys and yield nothing."""
    out = []
    for key in ("sectionals", "wards", "prestate", "super_regional",
                "semi_state", "divisional", "semi_conference", "conference",
                "special_challenger", "state_special"):
        d = (arc.get(key) or {}).get(group) or {}
        for games in d.get("rounds") or ():
            for gm in games:
                if gm.get("winner") == school and gm.get("unit"):
                    out.append(_unit_honour(gm["unit"]))
    return out


def jhsaa_jv_record(sched: list[dict]) -> tuple[int, int, int]:
    """(wins, losses, ties) over a program's JV duals, folded off the archive.

    ‼️ A FOLD, NOT A STORE — the same rule `jhsaa_school_history` runs on. The JV dual
    rows persist, so the record is DERIVED from them exactly as the varsity record is,
    and there is no second source of truth to drift. (Had the archive kept only a
    record and no duals, this would have had to become a stored column, and that was
    the strongest argument against it.)"""
    w = l = t = 0
    for d in sched:
        if (d.get("level") or "v") != "jv":
            continue
        if d.get("tied"):
            t += 1
        elif d.get("won"):
            w += 1
        else:
            l += 1
    return w, l, t


def jhsaa_jv_player_record(sched: list[dict], name: str) -> tuple[int, int, int]:
    """(wins, losses, ties) over the JV duals ONE player dressed for — the same fold as
    `jhsaa_jv_record`, narrowed by `played`.

    ‼️ A JV RECORD IS THE TEAM'S, NOT THE PLAYER'S. `played` records who dressed and
    nothing else, so a player takes the DUAL's result: there is no per-court detail to
    say whether they personally won (owner rule 2026-08 — the archive answers "did this
    kid play JV and how did that go", not "what did they go at No. 2 doubles"). Never
    present this as an individual W-L beside the varsity singles/doubles record, which
    IS per-court and means something different.

    Keyed by NAME, like every other JHSAA per-player read — a line and now a `played`
    entry both carry names rather than pids, which is why `overrides` refuses to rewrite
    a surname on an archived season.

    A season archived before `played` existed folds to (0, 0, 0) and the caller shows
    nothing, which is right: it does not know who played, and inventing a record from
    the team's would credit every JV dual to all sixteen of them."""
    w = l = t = 0
    for d in sched:
        if (d.get("level") or "v") != "jv" or name not in (d.get("played") or ()):
            continue
        if d.get("tied"):
            t += 1
        elif d.get("won"):
            w += 1
        else:
            l += 1
    return w, l, t


def _season_row(arc: dict, year: int, school: str, sched: list[dict]) -> dict | None:
    """One archived season as this program lived it. `None` if the program has no
    standings row that year (it didn't sponsor the sport, or the archive predates
    per-school records)."""
    # `group` is the classification AS THE ARCHIVE RECORDED IT that season — the one
    # thing that makes "have they moved up a class?" answerable. A school's current
    # classification is a property of the school, not of the season, so it is not
    # copied in here where it would silently rewrite history.
    row = {"year": year, "season_year": arc.get("season_year"), "group": "",
           "district": "", "record": "", "wins": 0, "losses": 0,
           "district_record": "", "dwins": 0, "dlosses": 0, "place": 0,
           "courts_won": 0, "courts_lost": 0, "pf": 0.0, "pa": 0.0,
           "state_rank": 0, "pi": None, "made_state": False, "seed": 0, "state_place": 0,
           "state_finish": "", "champion": False, "district_title": False,
           "made_toc": False, "toc_seed": 0, "toc_place": 0, "toc_finish": "",
           "toc_champion": False, "honoured": False, "unit_wins": [],
           # The JV season's record, folded off this program's JV rows. A RECORD, not a
           # rating (owner rule 2026-08): JV has no TOSS, no ranking, no seed and no
           # postseason, and it exists here because a program whose varsity is poor
           # while its JV wins is a program about to get good — a story only legible if
           # the number is on the page.
           "jv_record": "", "jv_wins": 0, "jv_losses": 0, "jv_ties": 0,
           "poy": [], "all_state": [], "all_district": [], "honors": [],
           # Team-level honours that are TEXT rather than a chip (today just a TOC
           # finish short of the title). Kept apart from `honors`, which is
           # individual awards only — the school page renders them in two tabs.
           "team_honors": []}
    for grp, dists in (arc.get("standings") or {}).items():
        for dname, rows in (dists or {}).items():
            for r in rows:
                if r.get("school") != school:
                    continue
                w, l = _wl(r.get("record"))
                dw, dl = _wl(r.get("drecord"))
                row.update(group=grp, district=dname, record=r.get("record", ""),
                           wins=w, losses=l, district_record=r.get("drecord", ""),
                           dwins=dw, dlosses=dl, place=r.get("place", 0),
                           pf=r.get("pf") or 0.0, pa=r.get("pa") or 0.0,
                           district_title=r.get("place", 0) == 1)
    if not row["group"]:
        return None
    # `jhsaa_postseason_result` walks every archived stage, so `state_finish` on the
    # ledger row names the stage a run ended at — "Areas" / "Sectionals" / "Wards"
    # / "Regionals" / "Zonals" / "Super Regionals" / "Semi-State" — instead of
    # going blank for a team that never reached the State bracket.
    g = row["group"]
    st = jhsaa_postseason_result(
        {"sectional": (arc.get("sectionals") or {}).get(g),
         "ward": (arc.get("wards") or {}).get(g),
         "prestate": (arc.get("prestate") or {}).get(g),
         "super_regional": (arc.get("super_regional") or {}).get(g),
         "semi_state": (arc.get("semi_state") or {}).get(g),
         "divisional": (arc.get("divisional") or {}).get(g),
         "semi_conference": (arc.get("semi_conference") or {}).get(g),
         "conference": (arc.get("conference") or {}).get(g),
         "special_challenger": (arc.get("special_challenger") or {}).get(g),
         "state_special": (arc.get("state_special") or {}).get(g),
         "state": (arc.get("brackets") or {}).get(g),
         "wildcards": (arc.get("wildcards") or {}).get(g),
         "district_qualifiers": (arc.get("district_qualifiers") or {}).get(g)}, school)
    row.update(made_state=st["made_state"], seed=st["seed"], state_place=st["place"],
               state_finish=st["finish"], champion=st["champion"])
    # The DISTRICT TITLE leads the units line (owner rule 2027-08: it belongs
    # "in the same line section with zone, ward, section etc."). Presence on the
    # line means WON, same as every other unit chip, and the district season
    # precedes the postseason, so it comes first. The stored district name
    # already carries the word "District" ("Marble Valley District").
    row["unit_wins"] = ([row["district"]] if row["place"] == 1 and row["district"]
                        else []) + _unit_wins(arc, g, school)
    # The Tournament of Champions is a SEPARATE event with a separate finish, not a
    # deeper run at state: only a classification champion is in it, so making it is
    # itself the honour and it has to be readable off the ledger row.
    row.update(jhsaa_toc_result(arc.get("toc") or {}, school))
    for r in jhsaa_group_ranking(arc, row["group"]):
        if r["school"] == school:
            row["state_rank"] = r["rank"]
            row["pi"] = r.get("pi")
            break
    # ‼️ THERE IS NO SEPARATE POSTSEASON RECORD (owner rule 2027-08). A program's record
    # is its record: the NCAA and the NFHS both carry the postseason inside the season
    # total, and neither publishes a regular-season record beside it as though the year
    # had two halves. `record` is archived AFTER the state tournament and the TOC are
    # played (`jhsaa.run_season`), so it already includes them; a "Post 6-1" tile next
    # to it invited exactly the double count the owner did by hand — 27-4 plus 6-1
    # reading as 33-5, when the 27-4 already contained the six. What a postseason leaves
    # behind is a FINISH, not a second record, and the finishes are `state_finish` /
    # `toc_finish` below.
    #
    # The individual courts still come off the school's own duals — the match-level
    # archive is the source for drilling into a season, exactly as it is for the
    # schedule view. Cheap: one indexed read of ~26 rows for the year.
    # ‼️ VARSITY ONLY. This used to hold because JV rows archived with `lines` EMPTY,
    # and the comment here said the filter would be needed the day per-court JV detail
    # landed. It landed (owner rule 2026-08, the JV box score) — so the filter is real
    # now, and the courts_won/courts_lost on a program's season stay the varsity ones.
    for d in sched:
        if (d.get("level") or "v") != "v":
            continue
        for ln in d.get("lines") or ():
            ours = bool(ln.get("home_won")) if d.get("home") else not ln.get("home_won")
            row["courts_won" if ours else "courts_lost"] += 1
    jw, jl, jt = jhsaa_jv_record(sched)
    row.update(jv_wins=jw, jv_losses=jl, jv_ties=jt,
               jv_record=(f"{jw}-{jl}-{jt}" if jt else f"{jw}-{jl}") if jw + jl + jt
               else "")
    # The TOC CHAMPION gets a gold chip of its own in the honours panel, exactly as the
    # state champion does — so the text line here is for the programs that MADE the
    # field without winning it. Emitting both listed the title twice, one row apart.
    # ‼️ A TOC FINISH IS A TEAM HONOUR AND GOES IN ITS OWN LIST. It used to be
    # appended to `honors` beside the individual awards, which was harmless only
    # while both were rendered as one undifferentiated panel. Now that the school
    # page separates Team trophies from Player honours, a list that mixes them
    # files "Tournament of Champions — Semifinal" under the PLAYERS and drops it
    # from the team side entirely. `honors` is individual awards, full stop.
    if row["made_toc"] and not row["toc_champion"]:
        row["team_honors"].append(
            f"Tournament of Champions — {row['toc_finish'].removeprefix('TOC ')}"
            f" (No. {row['toc_seed']} seed)")
    aw = (arc.get("awards") or {}).get(row["group"]) or {}
    poy = aw.get("poy")
    if poy and poy.get("school") == school:
        row["poy"].append(poy)
        row["honors"].append(f"{row['group']} Player of the Year — {poy['name']}")
    for dname, r in (aw.get("district_poy") or {}).items():
        if r and r.get("school") == school:
            row["honors"].append(f"{dname} Player of the Year — {r['name']}")
    # All-Region hangs off the SEASON, not the classification (owner rule 2027-08
    # — a region team is class-blind). `aw` is the fallback for seasons archived
    # while it still lived inside a class's slate.
    from .jhsaa_awards import region_rows
    for rname, tier, r in region_rows(arc.get("all_region") or aw.get("all_region")):
        if r.get("school") == school:
            row["honors"].append(
                f"All-Region {tier} ({rname}) — {r['name']}".replace("  ", " "))
    # All-State names the TIER it was won on (First/Second/Third/Fourth Team, then
    # Honorable Mention). `teams` is the SOP shape; the flat `all_state` list is
    # the fallback for seasons archived before the tiers existed.
    tiers = aw.get("teams") or []
    if tiers:
        for tier in tiers:
            for r in tier["players"]:
                if r.get("school") == school:
                    row["all_state"].append(r)
                    row["honors"].append(
                        f"All-State {tier['name']} ({row['group']}) — {r['name']}")
        for r in aw.get("honorable_mention") or ():
            if r.get("school") == school:
                row["all_state"].append(r)
                row["honors"].append(
                    f"All-State Honorable Mention ({row['group']}) — {r['name']}")
    else:
        for r in aw.get("all_state", ()):
            if r.get("school") == school:
                row["all_state"].append(r)
                row["honors"].append(f"All-State ({row['group']}) — {r['name']}")
    for dname, rs in ((arc.get("all_district") or {}).get(row["group"]) or {}).items():
        if dname != row["district"]:
            continue
        for r in rs:
            if r.get("school") == school:
                row["all_district"].append(r)
                row["honors"].append(f"All-District ({dname}) — {r['name']}")
    # ‼️ `honors` is the INDIVIDUAL awards, and the TEAM titles are rendered from
    # `champion` / `toc_champion` as banners of their own. So "did this season carry an
    # honour?" is not `bool(honors)` — a program that won its classification and the
    # Tournament of Champions without a single All-District player has an empty
    # `honors` list, and a panel selecting on that drops the season before it can draw
    # either banner. Deriving the answer here rather than in the template keeps the two
    # halves — what the panel filters on and what it renders — from disagreeing.
    # ...and the TEAM tournament honours widen it further (owner rule 2027-08):
    # a unit win or a State appearance is an honour too — only champions and TOC
    # sides earning anything "wasn't realistic".
    row["honoured"] = (bool(row["honors"]) or bool(row["team_honors"])
                       or row["champion"] or row["toc_champion"]
                       or bool(row["unit_wins"]) or row["made_state"])
    return row


def jhsaa_school_seasons(world_id: int, gender: str, school: str) -> list[dict]:
    """A program's season ledger, newest first — one row per archived world-year.

    EVERY archived year produces a row, trophy or not: a program history is how a
    program did year over year, so the losing seasons have to show. (It once returned
    only the years carrying a title or an honour, which made a school look like it had
    never played in between.)"""
    conn = _db()
    try:
        years = [r["year"] for r in conn.execute(
            "SELECT DISTINCT year FROM world_jhsaa WHERE world_id=? AND gender=?"
            " ORDER BY year DESC", (world_id, gender)).fetchall()]
        out = []
        for year in years:
            r = conn.execute("SELECT data FROM world_jhsaa WHERE world_id=? AND year=?"
                             " AND gender=?", (world_id, year, gender)).fetchone()
            if not r:
                continue
            # Relabelled, so a season this program played under an older name is
            # still ITS season — the whole point of the fix.
            row = _season_row(_relabel(json.loads(r["data"])), year, school,
                              _schedule_rows(conn, world_id, year, gender, school))
            if row:
                out.append(row)
    finally:
        conn.close()
    return out


def jh_road_ladder() -> tuple[str, ...]:
    """The road to State, shallowest rung first — the ORDER `jhsaa_season_depth`
    ranks a pre-State exit on.

    ‼️ THE NAMES COME FROM `jhsaa`'S OWN CONSTANTS, never typed here — the same rule
    `jhsaa_title_stages` runs on. A rung's archived `round_names` is what a finish is
    read off (`jhsaa_postseason_result`), and `DIVISIONAL_NAME` has moved once
    already: a typed copy would silently stop matching and every Divisionals run
    would rank as though the program had not played a postseason at all.

    It is the exact REVERSE of the walk in `jhsaa_postseason_result`, which tries the
    deepest rung first — one ladder, read from either end."""
    from . import jhsaa as _jh
    return ("Areas", "Sectionals", "Wards", "Regionals", "Zonals",
            "Super Regionals", "Semi-State", _jh.DIVISIONAL_NAME,
            _jh.SEMI_CONFERENCE_NAME, _jh.CONFERENCE_NAME,
            _jh.SPECIAL_CHALLENGER_FINISH, _jh.STATE_SPECIAL_FINISH)


def jhsaa_season_depth(row: dict) -> tuple:
    """HOW FAR a season went, as a sortable key — bigger is further.

    ‼️ A RECORD IS NOT A SEASON'S RESULT (owner rule 2026-08). "Best season" used to
    be the best win percentage, which ranked a 28-4 that lost in the Octofinals above
    a 22-7 that reached the State semifinal — and the semifinal is plainly the better
    year. So the measure is the postseason FINISH, and the record is only the
    tie-break ("if the measures are tied, then the record counts").

    The tiers are the sport's own rungs: the Tournament of Champions is above the
    State draw, the State draw is above the road to it, and inside each the deeper
    run wins. A State place is a COUNT OF TEAMS STILL ALIVE (1 = champion), so it is
    negated rather than compared to a label — the `state_place <= 4` rule, one level
    up. A road exit ranks on `jh_road_ladder`; a stage nobody has heard of ranks at
    the bottom of its tier rather than raising, because an archive written before a
    rung existed is a real thing to render."""
    if row.get("made_toc"):
        # Only a classification champion is in the field, so every TOC entrant is
        # also a State champion — the tier exists to separate the six of them.
        tier, level = 3, -(row.get("toc_place") or 99)
    elif row.get("made_state"):
        tier, level = 2, -(row.get("state_place") or 99)
    elif row.get("state_finish"):
        ladder = jh_road_ladder()
        tier = 1
        level = ladder.index(row["state_finish"]) if row["state_finish"] in ladder else -1
    else:
        tier, level = 0, 0
    w, l = row.get("wins", 0), row.get("losses", 0)
    return (tier, level, w / (w + l) if w + l else 0.0, w)


def jhsaa_program_totals(seasons: list[dict]) -> dict:
    """The career side of a program's history: what the ledger ADDS UP TO.

    Every number here is a fold over the season rows — all-time W-L is literally their
    sum — so the two halves of a program page can never disagree, and a new season
    changes the totals only by being appended."""
    played = [s for s in seasons if s["wins"] or s["losses"]]
    asc = sorted(seasons, key=lambda s: s["year"])            # oldest first, for streaks
    wins = sum(s["wins"] for s in seasons)
    losses = sum(s["losses"] for s in seasons)
    titles = [s for s in seasons if s["champion"]]
    states = [s for s in seasons if s["made_state"]]
    tocs = [s for s in seasons if s.get("made_toc")]
    toc_titles = [s for s in seasons if s.get("toc_champion")]
    streak = best_streak = 0
    for s in asc:
        streak = streak + 1 if s["made_state"] else 0
        best_streak = max(best_streak, streak)
    groups = [s["group"] for s in asc if s["group"]]
    return {
        "seasons": len(seasons), "wins": wins, "losses": losses,
        "record": f"{wins}-{losses}",
        "pct": wins / (wins + losses) if (wins + losses) else 0.0,
        # No `post_wins`/`post_losses`: a postseason record is not a thing programs
        # carry, and `wins`/`losses` above already contain those duals. See `_season_row`.
        "courts_won": sum(s["courts_won"] for s in seasons),
        "courts_lost": sum(s["courts_lost"] for s in seasons),
        "district_titles": sum(1 for s in seasons if s["district_title"]),
        "state_appearances": len(states),
        "state_quarters": sum(1 for s in seasons if s["state_place"] and s["state_place"] <= 8),
        "state_semis": sum(1 for s in seasons if s["state_place"] and s["state_place"] <= 4),
        "state_finals": sum(1 for s in seasons if s["state_place"] and s["state_place"] <= 2),
        "state_titles": len(titles),
        # The Tournament of Champions, folded the same way — appearances, how far, and
        # the last one. Only a classification champion is ever in the field, so
        # `toc_appearances` is a count of a program's very best seasons.
        "toc_appearances": len(tocs),
        "toc_semis": sum(1 for s in seasons if s.get("toc_place") and s["toc_place"] <= 4),
        "toc_finals": sum(1 for s in seasons if s.get("toc_place") and s["toc_place"] <= 2),
        "toc_titles": len(toc_titles),
        "last_toc": tocs[0] if tocs else None,                 # seasons are newest-first
        "last_toc_title": toc_titles[0] if toc_titles else None,
        "poy": sum(len(s["poy"]) for s in seasons),
        "all_state": sum(len(s["all_state"]) for s in seasons),
        "all_district": sum(len(s["all_district"]) for s in seasons),
        "last_title": titles[0] if titles else None,           # seasons are newest-first
        "last_state": states[0] if states else None,
        "state_streak": streak, "longest_state_streak": best_streak,
        # ‼️ THE BEST SEASON IS THE FURTHEST RUN, not the best record — see
        # `jhsaa_season_depth`. There is no `worst` beside it any more (owner rule
        # 2026-08: "nobody wants to see that") — a program page is a record of what a
        # program achieved, and the ledger below shows every losing season anyway.
        "best": max(played, key=jhsaa_season_depth) if played else None,
        # ROAD TO STATE titles — the units a program won on the way (Areas through
        # the Conference). `unit_wins` leads with the DISTRICT title when there is
        # one (owner rule 2027-08), and that is counted separately above, so it is
        # subtracted here rather than the list being re-derived.
        "road_titles": sum(len(s["unit_wins"]) - (1 if s["district_title"] else 0)
                           for s in seasons),
        # Classifications the program has played in, oldest first — a program that has
        # moved up or down shows more than one, which is the question the ledger exists
        # to answer ("have they changed class?").
        "classifications": list(dict.fromkeys(groups)),
    }


def jhsaa_history_rows(world_id: int, gender: str) -> dict[str, list[dict]]:
    """EVERY program's season ledger for every archived year, in ONE pass over
    the archive — the bulk counterpart of `jhsaa_school_seasons` for the research
    export. Per archived year the season blob is parsed once and the dual table
    read once (grouped by school), then `_season_row` runs per program over
    those parsed structures — never one blob parse per (school, year), which is
    what looping `jhsaa_school_seasons` over ~850 programs would cost. Rows per
    school come newest-first, matching `jhsaa_school_seasons`."""
    from collections import defaultdict
    from . import jhsaa as _jh
    _alias = _jh.former_names()
    conn = _db()
    out: dict[str, list[dict]] = {}
    try:
        years = [r["year"] for r in conn.execute(
            "SELECT DISTINCT year FROM world_jhsaa WHERE world_id=? AND gender=?"
            " ORDER BY year DESC", (world_id, gender)).fetchall()]
        for year in years:
            r = conn.execute("SELECT data FROM world_jhsaa WHERE world_id=? AND year=?"
                             " AND gender=?", (world_id, year, gender)).fetchone()
            if not r:
                continue
            arc = _relabel(json.loads(r["data"]))
            sched: dict[str, list[dict]] = defaultdict(list)
            # ‼️ `level` AND `tied` COME TOO. `_season_row` scopes its court counts to
            # varsity by `level` and folds the JV record off `level`/`tied`, so a row
            # dict missing them reads as varsity-with-no-tie: JV courts join the
            # program's varsity court totals and its JV record comes back empty. Both
            # are silent — the numbers are all plausible.
            for d in conn.execute(
                    "SELECT school, home, lines, level, tied FROM world_jhsaa_dual"
                    " WHERE world_id=? AND year=? AND gender=?",
                    (world_id, year, gender)):
                # Grouped under the CURRENT name, matching the relabelled standings —
                # otherwise a renamed program's duals never meet its own season row.
                sched[_alias.get(d["school"], d["school"])].append(
                    {"home": bool(d["home"]), "level": d["level"] or "v",
                     "tied": bool(d["tied"]),
                     "lines": json.loads(d["lines"] or "[]")})
            schools = {row["school"]
                       for dists in (arc.get("standings") or {}).values()
                       for rows_ in (dists or {}).values() for row in rows_}
            for school in schools:
                row = _season_row(arc, year, school, sched.get(school, []))
                if row:
                    out.setdefault(school, []).append(row)
    finally:
        conn.close()
    return out


def jhsaa_retired_programs(world_id: int, gender: str) -> list[dict]:
    """Every program that has archived a `gender` season and does not sponsor
    the sport today, with its LAST season — so a program's history can be
    found without guessing which classification it played in when it
    stopped (`jhsaa.former_school` needs a year to open its page on; this is
    where that year comes from, instead of hunting the state bracket to spot
    a name that vanished).

    One pass over the whole archive via `jhsaa_history_rows` — the same
    reason that function exists. Looping `jhsaa_school_seasons` per program
    would re-read every season once per program instead of once total.

    ‼️ A RENAMED SCHOOL IS STILL ACTIVE, and it is `jhsaa.former_names()`
    that has to know it — NOT a filter here. This shipped once listing
    "Bardsley County High" (now Violet City) and "Olivet Regional" (now
    Silva) as retired, because a rename applied straight to the committed
    data never reaches the git-derived half of that alias table. Excluding
    them HERE was the wrong repair: it hides the row from this page while
    leaving the underlying breakage — the pre-rename seasons still file
    under the old name, so Violet City's own page omits them from its
    ledger and career totals, and the old-name entry that would have led a
    reader there is gone too. `former_names()` now merges the live
    `source` -> `name` mapping, so those seasons are RELABELLED onto the
    active school everywhere (the ledger, the totals, the title board,
    this page) and `sponsors_sport` then excludes them for the ordinary
    reason: they are playing today."""
    from . import jhsaa as jh
    rows = jhsaa_history_rows(world_id, gender)
    out = []
    for school, seasons in rows.items():
        if not seasons or jh.sponsors_sport(school, gender):
            continue
        last = seasons[0]                      # seasons come back newest-first
        out.append({"name": school, "last_year": last["year"],
                    "last_season_year": last.get("season_year"),
                    "last_group": last.get("group"), "record": last.get("record", ""),
                    "seasons": len(seasons)})
    out.sort(key=lambda r: (-r["last_year"], r["name"]))
    return out


def jhsaa_school_history(world_id: int, gender: str, school: str) -> dict:
    """A program's whole history, as the three DISTINCT things it is:

      * `totals`      — the career: seasons played, all-time record, district titles,
                        state appearances / semifinals / finals / championships, POY
                        and All-State counts, the last title, the best and worst seasons.
      * `seasons`      — the ledger: one row per archived season, newest first.
      * `individual_champions` — every individual-flight state title a player of this
                        program has ever won, newest first — the program-history
                        counterpart of the player page's "State tournament results".

    Honours ride along on the season they were won in. They annotate the history; the
    season rows ARE the history."""
    seasons = jhsaa_school_seasons(world_id, gender, school)
    return {"totals": jhsaa_program_totals(seasons), "seasons": seasons,
            "individual_champions": jhsaa_school_individual_champions(
                world_id, gender, school, seasons)}


def jhsaa_school_individual_champions(world_id: int, gender: str, school: str,
                                      seasons: list[dict]) -> list[dict]:
    """Every individual state title a school has won — the six flights AND mixed
    doubles — newest first, the program-history counterpart of
    `jhsaa_individual_results`'s player-page section, folded across every archived
    season rather than one player's career.

    Takes `seasons` rather than re-deriving them: each row already carries the
    CLASSIFICATION the program actually played that year (`jhsaa_school_seasons`'
    own `group`), so this reads at most the one set of draws that year's program
    could possibly have won — never every classification for every year, which a
    program in one class a season could never appear in anyway.

    ‼️ MIXED DOUBLES CREDITS BOTH PROGRAMS (owner correction, 2026-08: "it should be
    crediting both the boys and girls program with the honor when it's won, just
    like the other doubles and singles brackets"). It was excluded on the grounds
    that a mixed pair is one player from each of a school's two SEPARATE teams, so a
    page scoped to one gender had "no flight-box row to hang it from" — which
    answered a LAYOUT question by dropping a title the school actually won. The
    entry's `school` is the school (one name, shared by both its teams), so the boys'
    page and the girls' page each show it, exactly as they each show their own No. 1
    doubles title. The ROW names both players, because the pair is what won it.

    That is the program-level counterpart of the rule one level down: on the career
    rolls a mixed title credits only the winner's own gender, since a career belongs
    to a person and a person has one. A PROGRAM has both teams."""
    from . import jhsaa_jv_individuals as jvi
    out = []
    for s in seasons:
        grp = s.get("group")
        if not grp:
            continue
        # The mixed draw is archived under gender 'mixed' and its group comes off the
        # school's row, which both its teams share — so this year's class is the
        # right key for it too.
        # ‼️ AND THE CLASSLESS JV STATE BRACKETS, under `GROUP_KEY`. They are a
        # state title the program won and belong here for the same reason mixed
        # doubles does — the counterpart of the player page's own section, which
        # shows them (owner rule 2026-08). The key cannot collide with a class,
        # so this reads one extra pair of rows per season and nothing else moves.
        champs = {**jhsaa_individual_champions(world_id, s["year"], gender, grp),
                  **jhsaa_individual_champions(world_id, s["year"], "mixed", grp),
                  **jhsaa_individual_champions(world_id, s["year"], gender,
                                               jvi.GROUP_KEY)}
        for flight, c in champs.items():
            champion = c.get("champion") or {}
            if champion.get("school") != school:
                continue
            out.append({
                "year": s["year"], "season_year": s.get("season_year") or s["year"],
                # A JV title was contested statewide, so it is not this
                # program's classification that year — the draw's own key is.
                "group": jvi.GROUP_KEY if flight in jvi.BRACKETS else grp,
                "flight": flight,
                "flight_name": _jh_flight_name(flight),
                "mixed": flight == "XD",
                "jv": flight in jvi.BRACKETS,
                "players": [{"pid": p.get("pid"), "name": p.get("name"),
                            "grade": p.get("grade")}
                           for p in champion.get("players") or ()],
            })
    order = {f: i for i, f in enumerate(_jh_indiv_flight_order())}
    out.sort(key=lambda r: (-r["year"], order.get(r["flight"], 99)))
    return out


def cups_done(world: dict) -> bool:
    """True once this world-year's cups are archived (the `world_cups` rows ARE the
    marker — no separate flag to drift)."""
    conn = _db()
    n = conn.execute("SELECT COUNT(*) c FROM world_cups WHERE world_id=? AND year=?",
                     (world["id"], world["year"])).fetchone()["c"]
    conn.close()
    return n > 0


def run_world_cups(seed: int = DEFAULT_SEED, world: dict | None = None) -> dict:
    """The Davis / BJK Cup step: play the cups over this year's rosters, archive
    them, and stamp champion/finalist honors. An explicit offseason step of its own
    — after the college season, before the rollover starts the next one — so seniors
    play their last cup and the result is visible before graduation moves anyone."""
    w = world or get_or_create(seed)
    prime(seed)
    conn = _db()
    try:
        out = _store_world_cups(conn, w, cup_rosters(w))
        conn.commit()
    finally:
        conn.close()
    return out


def _store_world_cups(conn, world: dict, rosters: dict) -> dict:
    """Run + persist the national-team cups (Davis / BJK) over the fully-developed
    year rosters (pre-graduation, so seniors play their cup), and stamp champion/
    finalist honors to the players' REAL pids — the title lands on the same career
    page as college and GTT honors.

    NOT wrapped in a swallow: a cup that fails used to leave the year with no cup
    row and no honors and say nothing, which is exactly the "graceful fallback hides
    wrong data" trap. Let it raise."""
    from app import national_teams as nt
    import app.honors as honors
    yr = world["year"]
    eff = year_seed(world["seed"], yr)
    conn.execute("DELETE FROM world_cups WHERE world_id=? AND year=?", (world["id"], yr))
    champions = {}
    for gender in worldconfig.active_genders():
        cup = nt.run_world_cup(gender, seed=eff, rosters=rosters)
        conn.execute("INSERT INTO world_cups VALUES (?,?,?,?)",
                     (world["id"], yr, gender, json.dumps(cup)))
        # Stamp through the CALLER's connection — a second connection here
        # deadlocks against the open rollover transaction on the shared file.
        honors.stamp(nt.honor_records(cup, year=2026 + yr, season_no=yr + 1), conn=conn)
        champions[gender] = (cup.get("champion") or {}).get("name")
    return {"event": "world_cups", "year": 2026 + yr, "champions": champions}


def latest_world_cup(seed: int, gender: str, year: int | None = None) -> dict | None:
    """A completed cup snapshot for a gender (None until one has been stored at a
    year rollover). `year` is the world-year INDEX; default = most recent."""
    w = load_world(seed)
    if not w:
        return None
    conn = _db()
    try:
        if year is None:
            r = conn.execute("SELECT data FROM world_cups WHERE world_id=? AND gender=?"
                             " ORDER BY year DESC LIMIT 1", (w["id"], gender)).fetchone()
        else:
            r = conn.execute("SELECT data FROM world_cups WHERE world_id=? AND gender=?"
                             " AND year=? LIMIT 1", (w["id"], gender, year)).fetchone()
    finally:
        conn.close()
    return json.loads(r["data"]) if r else None


def world_cup_years(seed: int) -> list[int]:
    """World-year indexes with a stored cup, newest first (the year picker)."""
    w = load_world(seed)
    if not w:
        return []
    conn = _db()
    try:
        rows = conn.execute("SELECT DISTINCT year FROM world_cups WHERE world_id=?"
                            " ORDER BY year DESC", (w["id"],)).fetchall()
    finally:
        conn.close()
    return [r["year"] for r in rows]


def player_world_cups(seed: int, pid: str) -> list[dict]:
    """A player's international record across every stored cup — one row per
    (year, event): caps + singles/doubles rubber W-L + how far the nation went.
    Feeds the International panel on the career page."""
    w = load_world(seed)
    if not w:
        return []
    conn = _db()
    try:
        rows = conn.execute("SELECT year, gender, data FROM world_cups WHERE world_id=?"
                            " ORDER BY year DESC", (w["id"],)).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        cup = json.loads(r["data"])
        rec = (cup.get("players") or {}).get(pid)
        if not rec:
            continue
        champ = cup.get("champion") or {}
        finalist = cup.get("runner_up") or {}
        finish = ("Champion" if any(p["pid"] == pid for p in champ.get("squad", []))
                  else "Finalist" if any(p["pid"] == pid for p in finalist.get("squad", []))
                  else "")
        out.append({"year": 2026 + r["year"], "event": cup["event"],
                    "country": rec["country"], "flag": flag_emoji(rec["country"]),
                    "ties": rec["ties"],
                    "singles": f"{rec['singles_w']}-{rec['singles_l']}",
                    "doubles": f"{rec['doubles_w']}-{rec['doubles_l']}",
                    "finish": finish})
    return out


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


def past_individual_champions(seed: int, division: str, gender: str) -> list[dict]:
    """Year-by-year winners of the stored NCAA individual championships for a
    universe, newest first: [{"year": calendar year, "singles": {"champion",
    "runner_up"}, "doubles": {...}}, ...]. Champion/runner-up are the flattened
    entry dicts from `championship_to_dict` (label / school / conf_abbr / pid /
    seed). Only completed, snapshotted seasons appear — the current season's draw
    joins the list at its year rollover."""
    w = load_world(seed)
    if not w:
        return []
    conn = _db()
    try:
        rows = conn.execute("SELECT year, event, data FROM world_championship WHERE world_id=?"
                            " AND division=? AND gender=? ORDER BY year DESC",
                            (w["id"], division, gender)).fetchall()
    finally:
        conn.close()
    by_year: dict[int, dict] = {}
    for r in rows:
        d = json.loads(r["data"])
        slot = by_year.setdefault(r["year"], {"year": BASE_YEAR + r["year"]})
        slot[r["event"].lower()] = {"champion": d.get("champion"),
                                    "runner_up": d.get("runner_up")}
    return [by_year[y] for y in sorted(by_year, reverse=True)]


# Dynamic prestige momentum — how fast/far a program's prestige drifts on results.
# Aggressive (owner choice): the cap allows multi-tier movement over many seasons.
PRESTIGE_MOM_CAP = 0.20      # max signed drift from base prestige (≈ 2 budget tiers)
PRESTIGE_MOM_GAIN = 0.10     # how much one season's over/under-performance nudges it
PRESTIGE_MOM_DECAY = 0.85    # regress toward base each year (mean-reversion)


def _update_prestige_momentum(seed: int, w: dict) -> None:
    """At year-end, drift each program's prestige by how it OVER/UNDER-performed its
    expectation. Expectation = its current prestige percentile in the division;
    result = its end-of-season Power-Index percentile plus a small pedigree bonus
    (NCAA field / Final Four / title). Beat your bar → climb (recruit up a tier);
    fall short → slide. Self-correcting (the bar rises with you) and capped. Per
    (school, gender). Persisted, so it compounds season to season."""
    import app.overrides as overrides
    from app.ncaa import load_division
    cur = overrides.get_prestige_momentum()
    out = dict(cur)
    for (d, g) in _active_unis():
        sid = universe_sid(seed, w, d, g)
        if sid is None:
            continue
        pi = sm.power_index(sid)
        if not pi:
            continue
        div = load_division(d, g)
        progs = [p for p in div.programs if p.school in pi]
        n = len(progs)
        if n < 2:
            continue
        by_pi = sorted(progs, key=lambda p: pi[p.school].pi, reverse=True)
        pi_pct = {p.school: 1 - i / (n - 1) for i, p in enumerate(by_pi)}
        by_pres = sorted(progs, key=lambda p: p.prestige, reverse=True)
        pres_pct = {p.school: 1 - i / (n - 1) for i, p in enumerate(by_pres)}
        champ = sm.national_champion(sid)
        ff = sm.ncaa_semifinalists(sid)
        field = sm.ncaa_participants(sid)
        ct = sm.conf_champions(sid)
        for p in progs:
            s = p.school
            bonus = 0.10 if s == champ else 0.06 if s in ff else 0.03 if s in field else 0.0
            if s in ct:
                bonus += 0.02
            result = pi_pct[s] + min(0.10, bonus)
            delta = result - pres_pct[s]                       # >0 overperformed
            m_old = cur.get((s, g), 0.0)
            m_new = PRESTIGE_MOM_DECAY * m_old + PRESTIGE_MOM_GAIN * delta
            m_new = max(-PRESTIGE_MOM_CAP, min(PRESTIGE_MOM_CAP, m_new))
            out[(s, g)] = round(m_new, 4)
    overrides.set_prestige_momentum_batch(out)


def _finalize_year(seed: int, w: dict) -> dict:
    """End-of-year: develop to a full year, then graduate / portal / intake."""
    prime(seed)
    # Results-based STR from the just-finished seasons drives the portal.
    player_str: dict = {}
    redshirts: set = set()           # season-ending injuries → medical-redshirt cohort
    for (d, g) in _active_unis():
        sid = universe_sid(seed, w, d, g)
        player_str.update(sm.season_player_str(sid))
        redshirts |= sm.season_ending_pids(sid)
    # Drift program prestige on this year's results BEFORE the rollover recruits the
    # next class, so a rising program immediately recruits up to its new tier.
    _update_prestige_momentum(seed, w)

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
    # Make this season's committed fall-portal moves permanent now that both stints
    # are on the record — relocate the movers in `rosters` and drop the overrides.
    _bake_fall_moves(seed, w, rosters)
    # season_player_str above needed the primed cache; the rollover works on
    # `rosters` (an independent copy), so free the ~170MB primed roster cache now
    # rather than holding it alongside `rosters` through the heavy rollover.
    reset_caches(); _primed.pop(seed, None)
    conn = _db()
    _save_graduates(conn, w["id"], w["year"], rosters, player_str, redshirts)
    # The Davis / BJK cups already ran, as their own step BEFORE this rollover
    # (`run_world_cups`), so the seniors about to graduate below played their last
    # cup and the result was visible before anyone moved.
    signings = _load_signings(conn, w)
    # Sign anyone still unsigned before the class arrives (decision-week gate off).
    for gender in worldconfig.active_genders():
        _sign_batch(conn, w, gender, RECRUIT_POOL, final=True)
    conn.commit()
    signings = _load_signings(conn, w)

    summary = finalize_rollover(rosters, signings, player_str, seed=seed, year=w["year"],
                                medical_redshirts=redshirts)

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
    # Pros are FREE AGENTS signed by hand through the two interactive portals (pre-season +
    # fall) — no auto year-end intake. The new season's pre-season portal is the next window.
    # The GTT off-season is NOT rolled here: it is its own visible step (`run_pro_offseason`,
    # taken at week 0 of the new year), so the pro league moving is something you watch
    # happen rather than a silent tail of the college rollover.
    summary.update(event="finalize", year=new_year, week=0)
    return summary
