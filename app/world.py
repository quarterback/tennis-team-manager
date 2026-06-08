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
import sqlite3
import threading
from dataclasses import asdict, fields

import app.seasonmode as sm
from .season import dual_between
from . import dbpath, worldconfig
from .dbpath import resolve_db_path
from .development import (Prospect, generate_prospect, make_pid, overall_to_str,
                          stagger_scale)
from .ncaa import (Program, load_division, build_roster, reset_caches, _roster_cache,
                   _talent_from_strength, _talent_mean, _pick_gender, region_proximity,
                   REGION_ADJACENT, ROSTER_SIZE, SCHOLARSHIP_SLOTS)
from .recruiting import (program_appeal, recruit_caliber, recruit_academic01,
                         home_region, GEO_WEIGHT, FAC_WEIGHT)
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
# Share of the national class that is international. The single knob for HOW MANY
# internationals exist — lower it for a more domestic world.
RECRUIT_INTL_SHARE = 0.32
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
  world_id INTEGER, year INTEGER, gender TEXT, school TEXT, pid TEXT, data TEXT
);
CREATE TABLE IF NOT EXISTS world_crossmatch (
  world_id INTEGER, year INTEGER, gender TEXT, home TEXT, away TEXT,
  home_div TEXT, away_div TEXT, home_pts INTEGER, away_pts INTEGER,
  winner INTEGER, lines TEXT
);
CREATE INDEX IF NOT EXISTS idx_wr ON world_roster(world_id, year);
CREATE INDEX IF NOT EXISTS idx_ws ON world_signing(world_id, year, gender);
CREATE INDEX IF NOT EXISTS idx_wx ON world_crossmatch(world_id, year, gender);
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


def get_or_create(seed: int = DEFAULT_SEED) -> dict:
    conn = _db()
    row = conn.execute("SELECT * FROM world WHERE seed=?", (seed,)).fetchone()
    if row:
        conn.close()
        return dict(row)
    cur = conn.execute("INSERT INTO world (seed, year, week) VALUES (?,0,0)", (seed,))
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
        "DELETE FROM world_roster; DELETE FROM world;"
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
    # Drop every in-memory cache so nothing stale survives the reset.
    _base_cache.clear()
    _dev_cache.clear()
    _primed.clear()
    reset_caches()
    sm._pid_idx_cache.clear()
    sm._str_cache.clear()


def start_new(seed: int = DEFAULT_SEED) -> dict:
    """Reset and create a brand-new league at preseason (week 0, nothing
    played). The onboarding 'Start new league' action."""
    reset(seed)
    return get_or_create(seed)


def current_year_seed(seed: int = DEFAULT_SEED) -> int:
    w = load_world(seed)
    return year_seed(seed, w["year"]) if w else seed


def signed_counts(seed: int = DEFAULT_SEED) -> dict:
    w = load_world(seed)
    if not w:
        return {}
    conn = _db()
    rows = conn.execute("SELECT gender, COUNT(*) c FROM world_signing WHERE world_id=? AND year=?"
                        " GROUP BY gender", (w["id"], w["year"])).fetchall()
    conn.close()
    return {r["gender"]: r["c"] for r in rows}


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


def national_class(seed: int, year: int, gender: str) -> list:
    key = (seed, year, gender)
    if key not in _class_cache:
        rng = random.Random(f"{seed}|worldrecruits|{gender}|{year}")
        klass = generate_class(rng, n=RECRUIT_POOL, grad_year=BASE_YEAR + year + 1,
                               gender=gender, talent_mean=_recruit_talent_mean(gender),
                               talent_sd=RECRUIT_TALENT_SD, intl_share=RECRUIT_INTL_SHARE,
                               intl_weights=worldconfig.region_weights())
        _class_cache[key] = rank_class(klass)
    return _class_cache[key]


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


def _sign_batch(conn, world: dict, gender: str, quota: int) -> int:
    """Sign up to `quota` more recruits this tick. Each unsigned recruit (best
    first) commits to the open program with the highest prestige+academics
    appeal that still has a projected seat."""
    wid = world["id"]
    rows = conn.execute("SELECT pid, school FROM world_signing WHERE world_id=? AND year=? AND gender=?",
                        (wid, world["year"], gender)).fetchall()
    signed = {r["pid"] for r in rows}
    taken: dict[str, int] = {}
    for r in rows:
        taken[r["school"]] = taken.get(r["school"], 0) + 1

    progs = _flat_programs(gender)
    traits = {s: (p.prestige, p.academics, p.region, p.division, p.facilities)
              for s, p in progs.items()}
    cap = _openings(_base_rosters(world), gender)
    avail = {s: cap.get(s, 0) - taken.get(s, 0) for s in progs}
    # Candidate indexing: each recruit only weighs programs near their athletic
    # level (a prestige window) plus the always-tempting top-academic set — so a
    # commit is O(window) not O(all ~1,000 programs).
    by_pres = sorted(progs, key=lambda s: traits[s][0])
    pres_arr = [traits[s][0] for s in by_pres]
    academic_top = sorted(progs, key=lambda s: -traits[s][1])[:40]
    # Home-region programs of EVERY division — so a strong "homecooking" recruit
    # can choose a near-home smaller school over a higher-prestige one out of
    # range (the realistic path by which real talent falls to a lower classification).
    by_region: dict[str, list] = {}
    for s in progs:
        by_region.setdefault(traits[s][2], []).append(s)

    klass = national_class(world["seed"], world["year"], gender)
    new = []
    signed_n = 0
    for p in klass:
        if signed_n >= quota:
            break
        if p.pid in signed:
            continue
        cal, ac = recruit_caliber(p), recruit_academic01(p)
        hr = home_region(p)
        hc = float(getattr(p, "homecooking", 0.0))
        intl = not getattr(p, "domestic", False)
        lo = bisect.bisect_left(pres_arr, cal - 0.30)
        hi = bisect.bisect_left(pres_arr, cal + 0.30)
        cands = set(by_pres[lo:hi]) | set(academic_top)
        if hc > 0.0 and not intl:                       # homebodies also weigh home
            cands |= set(by_region.get(hr, ()))
        best, best_score = None, -1.0
        jit = random.Random(f"{p.pid}|sign").uniform(-0.04, 0.04)
        for s in cands:
            if avail.get(s, 0) <= 0:
                continue
            pres, acad, reg, div, fac = traits[s]
            athletic = 0.6 * (1.0 - abs(pres - cal)) + 0.4 * pres * cal
            geo = hc * region_proximity(hr, reg)        # one-way; intl hc=0 → no geo
            score = (max(0.0, athletic) * (1.0 + 0.9 * acad * ac)
                     * (1.0 + GEO_WEIGHT * geo) * (1.0 + FAC_WEIGHT * fac) * (1 + jit))
            if intl:                                     # internationals route by tier
                score *= INTL_TIER_PULL[_intl_tier(div, acad)]
            if score > best_score:
                best, best_score = s, score
        if best is None:                              # no seats in range — widen once
            best = next((s for s in by_pres if avail.get(s, 0) > 0), None)
            if best is None:
                break
        avail[best] -= 1
        signed.add(p.pid)
        new.append((wid, world["year"], gender, best, p.pid, json.dumps(prospect_to_dict(p))))
        signed_n += 1
    if new:
        conn.executemany("INSERT INTO world_signing VALUES (?,?,?,?,?,?)", new)
    return signed_n


def _load_signings(conn, world: dict) -> dict[str, dict[str, list]]:
    """{gender: {school: [Prospect, ...]}} for the class that's signed so far."""
    rows = conn.execute("SELECT gender, school, data FROM world_signing"
                        " WHERE world_id=? AND year=?", (world["id"], world["year"])).fetchall()
    out: dict = {}
    for r in rows:
        out.setdefault(r["gender"], {}).setdefault(r["school"], []).append(
            prospect_from_dict(json.loads(r["data"])))
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

    # Recruiting drip: sign a slice of each active gender's class this week.
    conn = _db()
    signed = 0
    for gender in worldconfig.active_genders():
        quota = max(1, sum(_openings(_base_rosters(w), gender).values()) // SIGNING_WEEKS)
        signed += _sign_batch(conn, w, gender, quota)
    conn.execute("UPDATE world SET week=? WHERE id=?", (w["week"] + 1, w["id"]))
    conn.commit()
    conn.close()
    _primed.pop(seed, None)               # week advanced → re-prime (more dev) next access
    return {"event": "week", "year": w["year"], "week": w["week"] + 1,
            "played": played, "signed": signed, "cross": cross,
            "complete": _all_complete(seed, get_or_create(seed))}


def _finalize_year(seed: int, w: dict) -> dict:
    """End-of-year: develop to a full year, then graduate / portal / intake."""
    prime(seed)
    # Results-based STR from the just-finished seasons drives the portal.
    player_str: dict = {}
    for (d, g) in _active_unis():
        player_str.update(sm.season_player_str(universe_sid(seed, w, d, g)))

    rosters = developed_rosters(w)        # full-year developed copy
    # season_player_str above needed the primed cache; the rollover works on
    # `rosters` (an independent copy), so free the ~170MB primed roster cache now
    # rather than holding it alongside `rosters` through the heavy rollover.
    reset_caches(); _primed.pop(seed, None)
    conn = _db()
    signings = _load_signings(conn, w)
    # Sign anyone still unsigned before the class arrives.
    for gender in worldconfig.active_genders():
        _sign_batch(conn, w, gender, RECRUIT_POOL)
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
