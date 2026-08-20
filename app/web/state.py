"""
Web-layer state: run each division×gender season + bracket once and cache it
(a season is ~2s, far too heavy per request). Also shapes ranking rows for
the Power Index table.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass

from app.season import run_season
from app.bracket import select_field, run_bracket, clamp_field, FIELD_DEFAULT, field_for_division

DEFAULT_SEED = 2026
FIELD_PRESETS = [32, 64, 76, 96]    # offered in the UI; any 16–128 works

# Division×gender universes exposed in the UI (value, division, gender, label).
UNIVERSES = [
    ("D1-men", "D1", "men", "D1 Men"),
    ("D1-women", "D1", "women", "D1 Women"),
    ("D2-men", "D2", "men", "D2 Men"),
    ("D2-women", "D2", "women", "D2 Women"),
    ("D3-men", "D3", "men", "D3 Men"),
    ("D3-women", "D3", "women", "D3 Women"),
    ("D4-men", "D4", "men", "D4 Men"),
    ("D4-women", "D4", "women", "D4 Women"),
]

# Conference → display tier (mirrors the design's P5 / MID / IVY badges).
_P5 = {"ACC", "SEC", "Big Ten", "Big 12", "Pac-16"}

_season_cache: dict = {}
_bracket_cache: dict = {}
_doubles_champ_cache: dict = {}
_singles_champ_cache: dict = {}
_world_cup_cache: dict = {}
_portal_cache: dict = {}

# Per-key build locks for the championship draws. Playing a 128-draw singles
# (127 engine matches) or 64-draw doubles is heavy; the memo below collapses
# REPEAT views, but a BURST of first-views for the same complete season (a cold
# boot's first traffic, or a reload-mash on a slow page) can still start N
# concurrent identical builds. On the single gthread worker they all fight for
# the GIL, starve /api/health, and Fly drops the machine. A per-key lock makes
# the first request build while the rest block on the LOCK (which releases the
# GIL while waiting), so the worker stays free to answer health.
import threading as _threading
_champ_build_locks: dict = {}
_champ_build_guard = _threading.Lock()


def _champ_build_lock(key):
    with _champ_build_guard:
        lk = _champ_build_locks.get(key)
        if lk is None:
            lk = _champ_build_locks[key] = _threading.Lock()
        return lk


def get_season(division: str, gender: str, seed: int = DEFAULT_SEED):
    # When a saved world exists, every read surface reflects its CURRENT year:
    # prime the shared roster cache and key the season by the world's year seed.
    import app.world as world
    eff = seed
    if world.exists(seed):
        world.prime(seed)
        eff = world.current_year_seed(seed)
    key = (division, gender, eff)
    if key not in _season_cache:
        _season_cache[key] = run_season(division, gender, seed=eff)
    return _season_cache[key]


def get_bracket(division: str, gender: str, seed: int = DEFAULT_SEED, size: int | None = None):
    """The NCAA field from the live season (conference champions get autobids once
    the conference tournaments have run). None in preseason. Cached by how far the
    season has progressed so it refreshes as results come in."""
    import app.world as world
    import app.seasonmode as sm
    size = clamp_field(size if size is not None else field_for_division(division))
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    s = sm.load_season(sid)
    key = (division, gender, sid, size, s["current_week"], s["phase"])
    if key not in _bracket_cache:
        _bracket_cache[key] = sm.bracket_field(sid, size=size)
    return _bracket_cache[key]


def _hydrate_championship(data):
    """Rebuild a display-ready championship (objects matching the template's
    attribute contract) from a stored/serialized dict — crests resolved by school."""
    if not data:
        return None
    from types import SimpleNamespace
    from .rankings_data import crest

    def ent(d):
        if not d:
            return None
        ab, col = crest(d["school"])
        # per-player {pid, name} list; older snapshots (pre-"players") can recover
        # a singles entry from its pid/label, a doubles pair only as a whole
        players = d.get("players") or ([{"pid": d["pid"], "name": d["label"]}]
                                       if d.get("pid") else [])
        return SimpleNamespace(label=d["label"], pid=d.get("pid"), seed=d.get("seed"),
                               players=players,
                               program=SimpleNamespace(school=d["school"], abbr=ab, color=col,
                                                       conf_abbr=d.get("conf_abbr", "")))
    rounds = [[SimpleNamespace(rnd=m["rnd"], hi_seed=m["hi_seed"], lo_seed=m["lo_seed"],
                               winner_is_hi=m["winner_is_hi"], scoreline=m["scoreline"],
                               upset=m["upset"], hi=ent(m["hi"]), lo=ent(m["lo"]))
               for m in rnd] for rnd in data["rounds"]]
    return SimpleNamespace(event=data["event"], n_seeds=data["n_seeds"],
                           entries=[ent(e) for e in data["entries"]], rounds=rounds,
                           champion=ent(data["champion"]), runner_up=ent(data["runner_up"]),
                           seed_of=(lambda e: e.seed if e else None))


def _cur_cal_year(world, seed):
    return world.BASE_YEAR + (world.load_world(seed)["year"] if world.exists(seed) else 0)


def championship_years(division: str, gender: str, seed: int = DEFAULT_SEED):
    """Calendar years with a viewable individual championship (stored past years,
    plus the current season if it has concluded), newest first."""
    import app.world as world
    import app.seasonmode as sm
    years = set(world.championship_years(seed, division, gender))
    if world.exists(seed):
        s = sm.load_season(sm.get_or_create(division, gender, seed=world.current_year_seed(seed)))
        if s and s["phase"] == "complete":
            years.add(_cur_cal_year(world, seed))
    return sorted(years, reverse=True)


def past_individual_champions(division: str, gender: str, seed: int = DEFAULT_SEED) -> list[dict]:
    """Year-by-year singles/doubles champions for a universe (newest first), read
    straight from the `world_championship` snapshots — the past-winners record for
    the championship pages and the Hall of Fame."""
    import app.world as world
    return world.past_individual_champions(seed, division, gender)


def get_singles_championship(division: str, gender: str, seed: int = DEFAULT_SEED,
                             size: int = 128, year: int | None = None):
    """The NCAA individual singles championship, played AFTER the team tournament.
    Computed live while the current team season is complete; past seasons (and the
    current one after rollover) are served from the snapshot persisted at finalize.
    `year` (calendar) selects a specific past season."""
    import app.world as world
    import app.seasonmode as sm
    from app.individuals import run_singles_championship, clamp_field, championship_to_dict
    if year is not None and year != _cur_cal_year(world, seed):
        return _hydrate_championship(world.latest_championship(
            seed, division, gender, "Singles", year=year - world.BASE_YEAR))
    eff = world.current_year_seed(seed)
    sid = sm.get_or_create(division, gender, seed=eff)
    s = sm.load_season(sid)
    if s and s["phase"] == "complete":
        # Playing a 128-draw (127 engine matches) live is far too heavy to run on
        # every request — memoize the serialized result per (season, size). The
        # roster/field is frozen once the season is complete, so the draw is stable.
        # Publish to a LOCAL then return it (never `return cache[key]` — a sibling
        # thread / reset_all() can evict between store and return; read with .get()).
        csize = clamp_field(size)
        ckey = (division, gender, sid, csize)
        data = _singles_champ_cache.get(ckey)
        if data is None:
            with _champ_build_lock(("singles",) + ckey):
                data = _singles_champ_cache.get(ckey)      # re-check under the lock
                if data is None:
                    data = championship_to_dict(
                        run_singles_championship(division, gender, seed=eff, size=csize))
                    _singles_champ_cache[ckey] = data
        return _hydrate_championship(data)
    return _hydrate_championship(world.latest_championship(seed, division, gender, "Singles"))


def get_doubles_championship(division: str, gender: str, seed: int = DEFAULT_SEED,
                             size: int = 64, year: int | None = None):
    """The NCAA individual doubles championship — live while the current team season
    is complete, then served from the finalize snapshot; `year` selects a past one."""
    import app.world as world
    import app.seasonmode as sm
    from app.individuals import run_doubles_championship, clamp_field, championship_to_dict
    if year is not None and year != _cur_cal_year(world, seed):
        return _hydrate_championship(world.latest_championship(
            seed, division, gender, "Doubles", year=year - world.BASE_YEAR))
    eff = world.current_year_seed(seed)
    sid = sm.get_or_create(division, gender, seed=eff)
    s = sm.load_season(sid)
    if s and s["phase"] == "complete":
        # Same memoization as singles: a 64-draw is 63 live engine matches — cache
        # the serialized result per (season, size); publish to a local, return it.
        csize = clamp_field(size)
        ckey = (division, gender, sid, csize)
        data = _doubles_champ_cache.get(ckey)
        if data is None:
            with _champ_build_lock(("doubles",) + ckey):
                data = _doubles_champ_cache.get(ckey)      # re-check under the lock
                if data is None:
                    data = championship_to_dict(
                        run_doubles_championship(division, gender, seed=eff, size=csize))
                    _doubles_champ_cache[ckey] = data
        return _hydrate_championship(data)
    return _hydrate_championship(world.latest_championship(seed, division, gender, "Doubles"))


def get_world_cup(gender: str, seed: int = DEFAULT_SEED, year: int | None = None):
    """The national-team cup (Davis Cup for men, BJK Cup for women) — always the
    ARCHIVED edition; `year` (calendar) selects a past one. None until a world exists.

    Deliberately never computes live. The cups are their own offseason step
    (`world.run_world_cups`), which archives the result and stamps the honors; a
    second, live-computed view drew from a DIFFERENT roster set (`scan_rosters`,
    which includes dormant divisions rebuilt from the generator) than the archive
    (`developed_rosters`, active only), so the cup you looked at before finalizing
    could crown a different nation than the one that went on the record."""
    import app.world as world
    if not world.exists(seed):
        return None
    if year is not None:
        # An explicit year answers for THAT year or not at all. It used to fall
        # through to "most recent archived" when the requested year was the current
        # one, so a current year with no cup yet rendered the PRIOR year's champion
        # and draw as if they were this year's.
        return world.latest_world_cup(seed, gender, year=year - world.BASE_YEAR)
    return world.latest_world_cup(seed, gender)


def warm_championships(seed: int = DEFAULT_SEED) -> None:
    """Boot-time prewarm for the individual-championship memos: for every universe
    whose current team season is COMPLETE, build the singles + doubles draws now,
    off the request path, so the first post-restart view doesn't run a 127-match
    draw on the gunicorn worker's GIL (which starves /api/health → Fly drops the
    machine). Runs during the boot warm's health grace window, before traffic.
    Best-effort and idempotent; the per-key build lock + lazy path cover the rest."""
    import app.world as world
    import app.seasonmode as sm
    if not world.exists(seed):
        return
    for _val, division, gender, _label in UNIVERSES:
        try:
            sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
            s = sm.load_season(sid)
            if s and s["phase"] == "complete":
                get_singles_championship(division, gender, seed)
                get_doubles_championship(division, gender, seed)
        except Exception:
            pass                                  # lazy build still covers a skipped one


def reset_all() -> None:
    """Drop every web-layer cache and the engine roster caches. Called after an
    editor override changes, so rankings / teams / season all re-derive from the
    edited rosters on the next request."""
    from app import ncaa
    from . import awards
    import app.seasonmode as sm
    _season_cache.clear()
    _bracket_cache.clear()
    _doubles_champ_cache.clear()
    _singles_champ_cache.clear()
    _world_cup_cache.clear()
    _portal_cache.clear()
    _staff_cache.clear()
    _uni_staff_cache.clear()
    awards.reset_cache()
    for c in (sm._pid_idx_cache, sm._str_cache, sm._pi_cache, sm._forced_cache, sm._prec_cache,
              sm._pline_cache, sm._plrec_cache):
        c.clear()
    ncaa.reset_caches()


def reset_lineup() -> None:
    """Invalidation for a LINEUP / DOUBLES pin — scoped, because a pin only reorders
    one team's ladder. It clears the effective-roster layer (so build_roster
    re-applies the new order, cheaply, off the intact base) and the derived staff
    board, and NOTHING else: the base roster generation, the seasonmode result
    caches (a pin doesn't change past duals), and the world prime all survive. The
    pin reaches the sim via build_roster + the live read in season.coach_lineup.
    Using the full reset_all() here forced the whole world to regenerate rosters on
    the next page — the health-starving lineup-save stall. See
    docs/AAR-cache-invalidation-scope-lineup-stall.md."""
    from app import ncaa
    _staff_cache.clear()
    _uni_staff_cache.clear()
    ncaa.reset_effective()


def _tier(division: str, conf_abbr: str, conf: str) -> str:
    if division != "D1":
        return division   # D2 / D3 — flat tiers, badge shows the division
    if conf == "Ivy League" or conf_abbr == "Ivy":
        return "IVY"
    return "P5" if conf_abbr in _P5 else "MID"


@dataclass
class LiveRow:
    rk: int
    school: str
    conf: str
    conf_abbr: str
    tier: str
    cr: int
    rec: str
    crec: str
    pi: float
    apr: float
    fqi: float
    p6: float = 0.0
    points: float = 0.0
    me: bool = False
    move: int | None = 0        # poll movement: +up / -down / 0 steady / None = NEW to poll

    @property
    def rank_class(self) -> str:
        return "gold" if self.rk == 1 else "bronze" if self.rk <= 3 else ""

    @property
    def move_kind(self) -> str:
        """Poll-movement badge kind for the template: new / up / down / flat."""
        if self.move is None:
            return "new"
        return "up" if self.move > 0 else "down" if self.move < 0 else "flat"

    @property
    def confrk_class(self) -> str:
        return "lead" if self.cr == 1 else "bronze" if self.cr <= 3 else ""

    @property
    def apr_kind(self) -> str:
        return "muted" if self.apr < 0.60 else "good"

    @property
    def fqi_kind(self) -> str:
        return "muted" if self.fqi < 0.72 else "good"

    def fmt(self, v: float) -> str:
        return f"{v:.4f}"


def _ability(prog) -> float:
    """A program's preseason strength = mean of its top-6 players' overall, used
    to order surfaces before any results exist (a fresh league has no ratings)."""
    from app.ncaa import build_roster
    ovr = sorted((p.current_overall() for p in build_roster(prog)), reverse=True)[:6]
    return sum(ovr) / len(ovr) if ovr else 0.0


def _power6(prog) -> float:
    """Power 6 — roster strength from the top-6 singles players' STR: their mean,
    doubled, so it reads on an easy, spread-out scale where the strongest rosters
    clear 100. Available even preseason (STR falls back to ability before any
    results)."""
    from app.ncaa import build_roster
    s = sorted((p.str_value() for p in build_roster(prog)), reverse=True)[:6]
    return round(sum(s) / len(s) * 2, 1) if s else 0.0


def attach_power6(division: str, gender: str, table: list[dict]) -> list[dict]:
    """Enrich standings rows with each team's Power 6 (top-6 STR roster strength),
    its rank WITHIN this table, and a 0-100 bar width relative to the table's range —
    so the standings show roster strength (and where a program stacks or needs help)
    even for teams with no national ranking. Returns new row dicts; input untouched."""
    from app.ncaa import load_division
    progs = {p.school: p for p in load_division(division, gender).programs}
    rows = [dict(r, p6=(_power6(progs[r["school"]]) if r["school"] in progs else 0.0))
            for r in table]
    vals = [r["p6"] for r in rows] or [0.0]
    lo, hi = min(vals), max(vals)
    for rank, r in enumerate(sorted(rows, key=lambda r: -r["p6"]), 1):
        r["p6_rank"] = rank
    for r in rows:
        r["p6_pct"] = round(100 * (r["p6"] - lo) / (hi - lo)) if hi > lo else 100
    return rows


def ranking_rows(division: str, gender: str, seed: int = DEFAULT_SEED) -> list[LiveRow]:
    """Power Index table from the live week-by-week season. Before any results
    exist (preseason), programs are ordered by preseason ability so the page still
    renders for a freshly-started league."""
    import app.world as world
    import app.seasonmode as sm
    from app.ncaa import load_division
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    div = load_division(division, gender)
    ratings = sm.power_index(sid)
    cr = sm.conf_rank(sid)
    pts = sm.ita_team_points(sid)                              # ITA-style ranking points

    if pts:
        rated = sorted((p for p in div.programs if p.school in pts),
                       key=lambda p: pts[p.school], reverse=True)
        unrated = sorted((p for p in div.programs if p.school not in pts),
                         key=_ability, reverse=True)            # winless / not yet played → unranked
        ordered = rated + unrated
    else:
        ordered = sorted(div.programs, key=_ability, reverse=True)

    from app import worldconfig
    _prog = worldconfig.user_program()
    _my_school = (_prog["school"] if _prog and _prog["division"] == division
                  and _prog["gender"] == gender else None)
    wk_move = sm.weekly_movers(sid)          # coaches-poll week-to-week movement (top-25)
    rows: list[LiveRow] = []
    for rk, p in enumerate(ordered, 1):
        r = ratings.get(p.school)
        crk, cw, cl = cr.get(p.school, (0, 0, 0))
        # None (key present) = NEW to the poll this week; 0 = steady or outside the poll.
        move = wk_move.get(p.school, 0) if p.school in wk_move else 0
        rows.append(LiveRow(
            rk=rk, school=p.school, conf=p.conf, conf_abbr=p.conf_abbr,
            tier=_tier(division, p.conf_abbr, p.conf), cr=crk,
            rec=r.record if r else "0-0", crec=f"{cw}-{cl}",
            pi=r.pi if r else 0.0, apr=r.apr if r else 0.0, fqi=r.fqi if r else 0.0,
            p6=_power6(p), points=pts.get(p.school, 0.0), me=(p.school == _my_school),
            move=move,
        ))
    return rows


# US state → CTA geographic region for regional rankings (reuses the
# scout_intel census-division map so player-origin and team regions stay
# consistent).
def _program_regions(division: str, gender: str) -> dict:
    """{school: region-name} from each program's home state. Unknown/foreign → ''."""
    from app.ncaa import load_division, location
    from app.scout_intel import US_REGIONS
    out = {}
    for p in load_division(division, gender).programs:
        st = (getattr(p, "state", "") or location(p.school)[1] or "").upper()
        out[p.school] = US_REGIONS.get(st, "")
    return out


def regional_ranking_rows(division: str, gender: str, per_region: int = 10,
                          seed: int = DEFAULT_SEED) -> list[tuple[str, list]]:
    """CTA regional team rankings: the national board split into geographic regions
    (census divisions + Outlying), each showing its top `per_region` teams (with
    national rank + poll movement carried over), so mid-pack teams that never crack
    the national list still surface where they stack regionally. Ordered by
    scout_intel.US_REGION_ORDER; empty regions dropped."""
    from app.scout_intel import US_REGION_ORDER
    region_of = _program_regions(division, gender)
    rows = ranking_rows(division, gender, seed)
    groups: dict[str, list] = {}
    for r in rows:
        reg = region_of.get(r.school, "")
        if reg:
            groups.setdefault(reg, []).append(r)
    return [(reg, groups[reg][:per_region]) for reg in US_REGION_ORDER if groups.get(reg)]


def singles_ranking_rows(division: str, gender: str, seed: int = DEFAULT_SEED,
                         min_matches: int = 3) -> list[dict]:
    """CTA singles player ranking rows (newest-best first). Only players with at
    least `min_matches` singles are ranked."""
    import app.world as world
    import app.seasonmode as sm
    from app.ncaa import load_division
    from app.scout_intel import US_REGIONS
    from .rankings_data import crest
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    pts = sm.ita_singles_points(sid, min_matches)
    pidx = sm._pid_index(division, gender)
    recs = sm.player_records(sid)
    progs = load_division(division, gender).programs
    conf_full = {p.school: p.conf for p in progs}
    conf_abbr = {p.school: p.conf_abbr for p in progs}
    region_of = {p.school: US_REGIONS.get((p.state or "").upper(), "") for p in progs}
    rows = []
    for rk, pid in enumerate(sorted(pts, key=lambda x: pts[x], reverse=True), 1):
        info = pidx.get(pid)
        if not info:
            continue
        w, l = recs.get(pid, (0, 0))
        sch = info["school"]
        abbr, color = crest(sch)
        rows.append({"rk": rk, "pid": pid, "name": info["name"], "school": sch,
                     "conf": conf_full.get(sch, ""), "conf_abbr": conf_abbr.get(sch, ""),
                     "country": info.get("country", ""),
                     "secondary_country": info.get("secondary_country"), "class": info.get("class", ""),
                     "region": region_of.get(sch, ""),
                     "w": w, "l": l, "points": pts[pid], "abbr": abbr, "color": color})
    return rows


def doubles_ranking_rows(division: str, gender: str, seed: int = DEFAULT_SEED,
                         min_matches: int = 3) -> list[dict]:
    """CTA doubles PAIR ranking rows (newest-best first). Only pairs that have
    played together at least `min_matches` times are ranked."""
    import app.world as world
    import app.seasonmode as sm
    from app.ncaa import load_division
    from app.scout_intel import US_REGIONS
    from .rankings_data import crest
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    pts, members, wl = sm.ita_doubles_points(sid, min_matches)
    pidx = sm._pid_index(division, gender)
    progs = load_division(division, gender).programs
    conf_full = {p.school: p.conf for p in progs}
    conf_abbr = {p.school: p.conf_abbr for p in progs}
    region_of = {p.school: US_REGIONS.get((p.state or "").upper(), "") for p in progs}
    rows = []
    for rk, pr in enumerate(sorted(pts, key=lambda x: pts[x], reverse=True), 1):
        m = members.get(pr)
        i1 = pidx.get(m[0]) if m else None
        i2 = pidx.get(m[1]) if m else None
        if not i1 or not i2:
            continue
        w, l = wl.get(pr, [0, 0])
        sch = i1["school"]
        abbr, color = crest(sch)
        rows.append({"rk": rk, "p1": m[0], "p2": m[1], "n1": i1["name"], "n2": i2["name"],
                     "school": sch, "conf": conf_full.get(sch, ""), "conf_abbr": conf_abbr.get(sch, ""),
                     "c1": i1.get("country", ""), "c2": i2.get("country", ""),
                     "sc1": i1.get("secondary_country"), "sc2": i2.get("secondary_country"),
                     "region": region_of.get(sch, ""),
                     "w": w, "l": l, "points": pts[pr], "abbr": abbr, "color": color})
    return rows


def regional_player_rows(division: str, gender: str, view: str = "singles",
                         per_region: int = 10, seed: int = DEFAULT_SEED,
                         min_matches: int = 3) -> list[tuple[str, list]]:
    """CTA regional INDIVIDUAL rankings — the national singles (players) or doubles
    (pairs) board split by each program's home region (census divisions + Outlying),
    each region showing its top `per_region` entries with the national rank carried
    over. Same shape as `regional_ranking_rows` so the region-card template serves
    both. Ordered by scout_intel.US_REGION_ORDER; empty regions dropped."""
    from app.scout_intel import US_REGION_ORDER
    rows = (singles_ranking_rows if view == "singles"
            else doubles_ranking_rows)(division, gender, seed, min_matches)
    groups: dict[str, list] = {}
    for r in rows:
        if r["region"]:
            groups.setdefault(r["region"], []).append(r)
    return [(reg, groups[reg][:per_region]) for reg in US_REGION_ORDER if groups.get(reg)]


def newcomer_ranking_rows(division: str, gender: str, seed: int = DEFAULT_SEED,
                          min_matches: int = 3, limit: int = 50) -> list[dict]:
    """CTA newcomer singles rankings — the national singles board filtered to
    FRESHMEN (base class 'Fr', so a medical-redshirt RS-Fr counts), re-ranked among
    themselves with the national rank kept on the row. D1-only by owner rule (the
    real ITA runs newcomer rankings only for D1); the route enforces that scope —
    this helper just filters whatever universe it's given."""
    from app.world import _base_class
    rows = [r for r in singles_ranking_rows(division, gender, seed, min_matches)
            if _base_class(r.get("class", "") or "") == "Fr"]
    return rows[:limit]


def dashboard_view(division: str, gender: str, seed: int = DEFAULT_SEED) -> dict:
    """Everything the landing dashboard shows for one universe, built from the live
    week-by-week season. Fills in as the world advances (a freshly-started league
    shows preseason ability order, empty leaders/seeds, no champion yet)."""
    from .rankings_data import crest
    import app.world as world
    import app.seasonmode as sm
    from app.ncaa import load_division
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    div = load_division(division, gender)
    rows = ranking_rows(division, gender, seed)

    # Player STR leaders — top of the live STR board, with names from the roster
    # index and W-L from each player's match log (computed only for the top few).
    strmap = sm.season_player_str(sid)
    pidx = sm._pid_index(division, gender)
    board = sorted(((round(s, 1), rel, pid) for pid, (s, rel) in strmap.items()
                    if pid in pidx), reverse=True)[:10]
    recs = sm.player_records(sid)
    leaders = []
    for s, rel, pid in board:
        info = pidx[pid]
        w, l = recs.get(pid, (0, 0))
        abbr, color = crest(info["school"])
        leaders.append({"name": info["name"], "school": info["school"], "abbr": abbr,
                        "color": color, "str": s, "rel": rel, "w": w, "l": l,
                        "pid": pid})

    br = get_bracket(division, gender, seed)
    ratings = sm.power_index(sid)
    top_seeds = []
    if br:
        for p in br.seeds[:8]:
            r = ratings.get(p.school)
            abbr, color = crest(p.school)
            top_seeds.append({"school": p.school, "abbr": abbr, "color": color,
                              "pi": r.pi if r else 0.0, "rec": r.record if r else "0-0",
                              "autobid": p.key in br.autobids})

    s = sm.load_season(sid)
    champion = s["champion"] if s["phase"] == "complete" else None

    top = []
    for r in rows[:10]:
        abbr, color = crest(r.school)
        top.append({"row": r, "abbr": abbr, "color": color})

    return {
        "top_programs": top,
        "leaders": leaders,
        "top_seeds": top_seeds,
        "champion": champion,
        "n_programs": len(rows),
        "n_conferences": len(div.conferences),
        "n_players": len(pidx),
        "phase": s["phase"],
    }


def data_portal_view(division: str, gender: str, seed: int = DEFAULT_SEED) -> dict:
    """ATP/WTA-inspired data portal: one independent surface that wires into the
    live sim and lifts rankings, scores, stat leaders, standings, juniors, and
    recruiting from the deeper pages into a single newsroom/data hub."""
    from .rankings_data import crest
    import app.world as world
    import app.seasonmode as sm
    from app.ncaa import load_division

    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    s = sm.load_season(sid)
    conn = sm._db()
    counts = conn.execute(
        "SELECT COUNT(*) total, SUM(CASE WHEN status='final' THEN 1 ELSE 0 END) final "
        "FROM duals WHERE season_id=?", (sid,)
    ).fetchone()
    conn.close()
    completed = counts["final"] or 0
    total_duals = counts["total"] or 0
    # Include the completed-dual count in the key: during the ITA opener, week and
    # phase stay fixed across several round advances while new finals are written, so
    # without this the portal would serve pre-round results until the phase changed.
    _pkey = (division, gender, sid, s["current_week"], s["phase"], completed)
    _cached = _portal_cache.get(_pkey)
    if _cached is not None:
        return _cached
    div = load_division(division, gender)
    baseline_rows = ranking_rows(division, gender, seed)
    baseline_rank = {r.school: r.rk for r in baseline_rows}
    ratings = sm.power_index(sid)

    wk_move = sm.weekly_movers(sid)                    # week-to-week rank change
    if ratings:
        ranked_programs = sorted(
            (p for p in div.programs if p.school in ratings),
            key=lambda p: ratings[p.school].pi,
            reverse=True,
        )
        live_rankings = []
        for rk, prog in enumerate(ranked_programs[:12], 1):
            r = ratings[prog.school]
            abbr, color = crest(prog.school)
            move = wk_move.get(prog.school) or 0
            live_rankings.append({
                "rk": rk, "school": prog.school, "conf": prog.conf_abbr,
                "rec": r.record, "pi": r.pi, "apr": r.apr, "fqi": r.fqi,
                "move": move, "abbr": abbr, "color": color,
            })
    else:
        live_rankings = []
        for r in baseline_rows[:12]:
            abbr, color = crest(r.school)
            live_rankings.append({
                "rk": r.rk, "school": r.school, "conf": r.conf_abbr,
                "rec": r.rec, "pi": r.pi, "apr": r.apr, "fqi": r.fqi,
                "move": 0, "abbr": abbr, "color": color,
            })

    strmap = sm.season_player_str(sid)
    pidx = sm._pid_index(division, gender)
    recs = sm.player_records(sid)
    player_board = sorted(((round(score, 1), rel, pid) for pid, (score, rel) in strmap.items()
                           if pid in pidx), reverse=True)[:10]
    player_leaders = []
    for score, rel, pid in player_board:
        info = pidx[pid]
        w, l = recs.get(pid, (0, 0))
        abbr, color = crest(info["school"])
        player_leaders.append({
            "pid": pid, "name": info["name"], "school": info["school"],
            "class": info.get("class", ""), "country": info.get("country", ""),
            "secondary_country": info.get("secondary_country"), "w": w, "l": l,
            "str": score, "rel": rel, "abbr": abbr, "color": color,
        })

    standings_leaders = []
    for conf, table in sm.standings(sid).items():
        if not table:
            continue
        leader = table[0]
        abbr, color = crest(leader["school"])
        standings_leaders.append({"conf": conf, "abbr": abbr, "color": color, **leader})
    standings_leaders.sort(key=lambda r: (-r.get("w", 0), r.get("l", 0), r["conf"]))

    recent = []
    for d in sm.recent_duals(sid)[:10]:
        recent.append({
            "id": d["id"], "round": d["round"], "week": d["week"],
            "home": d["home"], "away": d["away"], "winner": d["winner"],
            "home_points": d["home_points"], "away_points": d["away_points"],
            "is_conf": bool(d["is_conf"]),
        })

    upcoming = []
    if s["phase"] == "regular" and s["current_week"] <= s["total_weeks"]:
        for d in sm.week_duals(sid, s["current_week"])[:10]:
            upcoming.append({
                "id": d["id"], "week": d["week"], "home": d["home"], "away": d["away"],
                "is_conf": bool(d["is_conf"]), "conf": d["conf"],
            })

    rg = RECRUIT_GENDERS.get(gender, "male")
    junior_year = world.recruiting_grad_year(seed)
    juniors = recruiting_hub(rg, junior_year, seed=seed)
    top_prospects = []
    for rk, p, stat, honor in juniors["top_rows"][:6]:
        top_prospects.append({
            "rk": rk, "pid": p.pid, "name": p.name, "country": p.country,
            "secondary_country": p.secondary_country, "grad_year": p.grad_year,
            "stars": p.recruit_stars, "points": p.junior_points, "str": p.junior_str,
        })

    # --- Bracket Watch (bubble) + opener / champion context ---
    bubble = sm.bubble_watch(sid)
    ita_champion = sm.indoor_champion(sid)
    natl_champion = sm.national_champion(sid)

    # --- Form: hot teams (active win streaks), biggest movers, upset flags ---
    hot_teams, movers = [], {"risers": [], "fallers": []}
    if ratings:
        conf_of = {p.school: p.conf_abbr for p in div.programs}
        form = sm.team_form(sid)
        for school, f in form.items():
            if f["streak"] >= 3 and school in ratings:
                ab, co = crest(school)
                hot_teams.append({"school": school, "streak": f["streak"], "last5": f["last5"],
                                  "rec": f"{f['w']}-{f['l']}", "conf": conf_of.get(school, ""),
                                  "abbr": ab, "color": co})
        hot_teams.sort(key=lambda x: -x["streak"])
        hot_teams = hot_teams[:8]
        risers, fallers = [], []
        for rk, p in enumerate(ranked_programs, 1):
            if p.school not in wk_move:                 # only currently-ranked (top-poll) teams
                continue
            m = wk_move[p.school]                       # positions gained/lost, or None = NEW
            ab, co = crest(p.school)
            entry = {"school": p.school, "rk": rk, "conf": p.conf_abbr,
                     "abbr": ab, "color": co, "move": m, "new": m is None}
            if m is None or m > 0:
                risers.append(entry)
            elif m < 0:
                fallers.append(entry)
        movers["risers"] = sorted(risers, key=lambda x: (0 if x["new"] else 1, -(x["move"] or 0)))[:6]
        movers["fallers"] = sorted(fallers, key=lambda x: x["move"])[:6]
    for d in recent:                                   # flag upsets in the score strip
        w_s = d["home"] if d["winner"] == 0 else d["away"]
        l_s = d["away"] if d["winner"] == 0 else d["home"]
        d["upset"] = bool(ratings and w_s in ratings and l_s in ratings
                          and ratings[w_s].pi + 0.03 < ratings[l_s].pi)

    # --- Conference power (average Power Index per league) ---
    from app.ncaa import conf_tier as _conf_tier
    conf_power = []
    if ratings:
        by_conf: dict = {}
        for p in div.programs:
            if p.school in ratings:
                by_conf.setdefault(p.conf_abbr, []).append(ratings[p.school].pi)
        conf_power = sorted(({"conf": c, "avg": sum(v) / len(v), "n": len(v),
                              "tier": _conf_tier(c)}
                             for c, v in by_conf.items()), key=lambda x: -x["avg"])[:8]

    # --- Program prestige board (where every program sits + YoY drift) ----------
    import app.overrides as overrides
    from app.recruit_economy import _prestige_tier
    mom = overrides.get_prestige_momentum()
    prestige_board = []
    for rk, p in enumerate(sorted(div.programs, key=lambda p: p.prestige, reverse=True), 1):
        ab, co = crest(p.school)
        m = mom.get((p.school, gender), 0.0)
        prestige_board.append({
            "rk": rk, "school": p.school, "conf": p.conf_abbr,
            "tier": _conf_tier(p.conf_abbr), "fund_tier": _prestige_tier(p.prestige),
            "base_tier": _prestige_tier(p.prestige - m),
            "prestige": round(p.prestige, 3), "base": round(p.prestige - m, 3),
            "mom": round(m, 3), "abbr": ab, "color": co,
        })
    _nz = [r for r in prestige_board if abs(r["mom"]) >= 0.005]
    prestige_risers = sorted(_nz, key=lambda r: -r["mom"])[:6]
    prestige_fallers = sorted(_nz, key=lambda r: r["mom"])[:6]

    # --- Singles + doubles win leaders ---
    def _win_leaders(rec_map):
        board = []
        for pid, (w, l) in rec_map.items():
            if pid in pidx and w + l >= 3:
                info = pidx[pid]; ab, co = crest(info["school"])
                board.append({"pid": pid, "name": info["name"], "school": info["school"],
                              "country": info.get("country", ""),
                              "secondary_country": info.get("secondary_country"),
                              "w": w, "l": l, "abbr": ab, "color": co})
        return sorted(board, key=lambda x: (-x["w"], x["l"]))[:8]

    singles_leaders = _win_leaders(recs)
    line_recs = sm.player_line_records(sid)
    doubles_map = {pid: (sum(wl[0] for wl in r["doubles"].values()),
                         sum(wl[1] for wl in r["doubles"].values()))
                   for pid, r in line_recs.items()}
    doubles_leaders = _win_leaders(doubles_map)

    _portal_result = {
        "season": s, "phase": s["phase"], "current_week": s["current_week"],
        "total_weeks": s["total_weeks"], "programs": len(div.programs),
        "conferences": len(div.conferences), "players": len(pidx),
        "completed_duals": completed, "total_duals": total_duals,
        "live_rankings": live_rankings, "player_leaders": player_leaders,
        "standings_leaders": standings_leaders[:8], "recent": recent, "upcoming": upcoming,
        "top_prospects": top_prospects, "junior_kpis": juniors["kpis"],
        "grad_year": junior_year, "has_live_results": bool(ratings) or completed > 0,
        "bubble": bubble, "ita_champion": ita_champion, "natl_champion": natl_champion,
        "hot_teams": hot_teams, "movers": movers, "conf_power": conf_power,
        "singles_leaders": singles_leaders, "doubles_leaders": doubles_leaders,
        "prestige_board": prestige_board, "prestige_risers": prestige_risers,
        "prestige_fallers": prestige_fallers,
    }
    _portal_cache[_pkey] = _portal_result
    return _portal_result


def conferences_for(division: str, gender: str) -> list[str]:
    from app.ncaa import load_division
    return ["All"] + sorted(load_division(division, gender).conferences.keys())


# --------------------------------------------------------------------------
# Recruiting (juniors) — board + profile
# --------------------------------------------------------------------------
from app.juniors import (generate_class, national_rankings, state_rankings,
                         international_rankings, US_STATES,
                         points_rankings, us_points_rankings, nation_points_top)
from app.development import overall_to_str

_recruit_cache: dict = {}
RECRUIT_GENDERS = {"men": "male", "women": "female"}

_RECRUIT_SD = 6.5
_GENDER_VOCAB = {"male": "men", "female": "women"}


RECRUIT_BOARD_N = 1000      # bounded recruiting cadre, all divisions share it


def get_recruits(gender: str, grad_year: int, seed: int = DEFAULT_SEED, division=None):
    """The ONE national recruiting class for the active league — the SAME class the
    simulation signs from and the recruit detail pages resolve against. Generation
    is owned by app.world.recruit_class, keyed by the world's salt, so there is no
    separate web-board universe and pids always match the sim. `division` is
    accepted for caller compatibility but ignored."""
    from app import world
    return world.board_class(gender, grad_year, world.active_salt(seed))


def junior_ranking_rows(gender: str, grad_year: int, scope: str = "world",
                        nation: str = "", sort: str = "rank", desc: bool = True,
                        seed: int = DEFAULT_SEED):
    """Points-ledger junior rankings as (rank, Prospect, stat_line) rows, sortable by
    any almanac column. Scopes: 'world' (everyone), 'us' (all domestic), 'intl' (all
    non-US), 'nation' (one international country)."""
    from app import almanac
    from app.juniors import intl_points_rankings
    klass = get_recruits(gender, grad_year, seed)
    if scope == "us":
        src = us_points_rankings(klass)                 # all domestic (US)
    elif scope == "intl":
        src = intl_points_rankings(klass)               # all non-US
    elif scope == "nation" and nation:
        src = [p for p in points_rankings(klass) if not p.domestic and p.region == nation]
    else:
        src = points_rankings(klass)                    # the whole pool
    stats = {p.pid: almanac.stat_line(p) for p in src}
    src = almanac.sort_recruits(src, stats, sort, desc)
    return [(i, p, stats[p.pid], almanac.honor_chip(p)) for i, p in enumerate(src, 1)]


def junior_leaders(gender: str, grad_year: int, seed: int = DEFAULT_SEED):
    """League-leader mini-boards for the rankings hub (over the whole pool)."""
    from app import almanac
    recruits = get_recruits(gender, grad_year, seed).recruits
    stats = {p.pid: almanac.stat_line(p) for p in recruits}
    return almanac.leaders(recruits, stats)


def junior_feed(gender: str, grad_year: int, seed: int = DEFAULT_SEED) -> dict:
    """The export/wiring contract: a round-trippable JSON bundle of the junior board
    (top 300 by points) — the same compute the live pages use."""
    from app import almanac
    klass = get_recruits(gender, grad_year, seed)
    recruits = points_rankings(klass)
    stats = {p.pid: almanac.stat_line(p) for p in recruits}
    rows = []
    for p in recruits[:300]:
        s = stats[p.pid]
        rows.append({
            "rank": p.points_rank, "pid": p.pid, "name": p.name, "nation": p.country,
            "domestic": p.domestic, "region": p.region, "grad_year": p.grad_year,
            "stars": getattr(p, "recruit_stars", 0), "board_rank": getattr(p, "recruit_rank", None),
            "tenniseye": getattr(p, "tenniseye_stars", 0),
            "points": p.junior_points, "singles_points": p.singles_points,
            "doubles_points": p.doubles_points, "str": p.junior_str,
            "doubles_str": p.junior_doubles_str, "events": p.tournaments_played,
            "doubles_events": p.doubles_played, "w": s["w"], "l": s["l"],
            "win_pct": round(s["pct"], 3), "titles": s["titles"], "finals": s["finals"],
            "honors": getattr(p, "junior_badges", None) or [],
        })
    return {"gender": gender, "grad_year": grad_year, "count": len(recruits), "board": rows}


# --- Class-strength scoring -------------------------------------------------
# A class is judged by its TOP 3 recruits, on two axes at once:
#   • combined STR  (how good they are — rewards depth, three studs > one + filler)
#   • average national rank (how highly regarded — sqrt-softened)
#   ClassScore = 0.1 × Σ STR(top3) × sqrt(1000 / avg rank(top3))
# The 0.1 just lands it on a ~100 scale (a strong class clears 100, e.g. 115.4).
_CLASS_SCORE_SCALE = 0.1
_RANK_SCORE_NUMERATOR = 1000.0


def _top3(recruits: list):
    """A program's three best signees by national rank (only ranked recruits)."""
    ranked = [p for p in recruits if (getattr(p, "recruit_rank", 0) or 0) > 0]
    return sorted(ranked, key=lambda p: p.recruit_rank)[:3]


def _class_score(recruits: list) -> float:
    top = _top3(recruits)
    if not top:
        return 0.0
    sum_str = sum(p.str_value() for p in top)
    avg_rank = sum(p.recruit_rank for p in top) / len(top)
    return _CLASS_SCORE_SCALE * sum_str * (_RANK_SCORE_NUMERATOR / avg_rank) ** 0.5


def _signee_outcomes(pids: list[str], seed: int = DEFAULT_SEED) -> dict:
    """How archived signees turned out, from the persisted world store:
    {pid: {status, school, division, cls, str_now}}. Status: 'Active' (on a
    current-year roster — school shows a transfer), 'Grad' (in world_graduates,
    with their final STR), 'Left' (enrolled once, no longer rostered), or None
    (never appeared on a persisted roster)."""
    import app.world as world
    w = world.load_world(seed)
    if not w or not pids:
        return {}
    latest: dict = {}
    grads: dict = {}
    conn = world._db()
    try:
        for i in range(0, len(pids), 400):          # stay under SQLite's variable cap
            chunk = pids[i:i + 400]
            marks = ",".join("?" * len(chunk))
            for r in conn.execute(
                    f"SELECT pid, year, division, school, data FROM world_roster"
                    f" WHERE world_id=? AND pid IN ({marks}) ORDER BY year",
                    [w["id"], *chunk]).fetchall():
                latest[r["pid"]] = r                # ordered by year → last write = newest
            for r in conn.execute(
                    f"SELECT pid, year, division, str FROM world_graduates"
                    f" WHERE world_id=? AND pid IN ({marks})",
                    [w["id"], *chunk]).fetchall():
                grads[r["pid"]] = r
    finally:
        conn.close()
    out: dict = {}
    for pid in pids:
        if pid in grads:
            g = grads[pid]
            out[pid] = {"status": "Grad", "school": (latest[pid]["school"] if pid in latest else ""),
                        "division": g["division"], "cls": "",
                        "str_now": round(g["str"], 1) if g["str"] else None}
            continue
        r = latest.get(pid)
        if not r:
            out[pid] = None
            continue
        p = world.prospect_from_dict(json.loads(r["data"]))
        out[pid] = {"status": "Active" if r["year"] == w["year"] else "Left",
                    "school": r["school"], "division": r["division"],
                    "cls": getattr(p, "class_year", ""),
                    "str_now": round(p.str_value(), 1)}
    return out


def signing_tracker(gender: str, division: str | None = None,
                    seed: int = DEFAULT_SEED, year: int | None = None) -> dict:
    import app.world as world
    from app.ncaa import load_division
    from .rankings_data import crest
    w = world.load_world(seed)
    cur = w["year"] if w else 0
    # Season picker: the current cycle (even before its first commit) + every
    # archived class — world_signing keeps every year (recruiting-class archive).
    years = sorted(set(world.signing_years(seed)) | {cur}, reverse=True)
    if year is None or year not in years:
        year = cur
    is_archive = year != cur
    by_school = world.signings(seed, year=year).get(gender, {})
    if division:                                    # scope to one classification (D1–D4)
        in_div = {p.school for p in load_division(division, gender).programs}
        by_school = {s: r for s, r in by_school.items() if s in in_div}
    classes = []
    commitments = []
    for school, recruits in by_school.items():
        stars = [getattr(p, "recruit_stars", 0) for p in recruits]
        abbr, color = crest(school)
        commits = sorted(recruits, key=lambda p: getattr(p, "recruit_rank", 1e9))
        classes.append({
            "school": school, "abbr": abbr, "color": color, "n": len(recruits),
            "score": round(_class_score(recruits), 1),         # the ranking metric
            "blue": sum(1 for p in recruits if getattr(p, "recruit_tier", "") == "Blue Chip"),
            "total_stars": sum(stars), "avg_stars": round(sum(stars) / len(stars), 2) if stars else 0.0,
            "five": sum(1 for x in stars if x >= 5), "four": sum(1 for x in stars if x == 4),
            "three": sum(1 for x in stars if x == 3), "two": sum(1 for x in stars if x == 2),
            "one": sum(1 for x in stars if x == 1),
            "breakdown": star_breakdown(stars),
            "commits": commits[:5],
        })
        for p in recruits:
            commitments.append({"p": p, "school": school, "abbr": abbr, "color": color,
                                "stars": getattr(p, "recruit_stars", 0)})
    classes.sort(key=lambda c: (-c["score"], -c["total_stars"], c["school"]))
    for i, c in enumerate(classes, 1):
        c["rank"] = i
    commitments.sort(key=lambda r: getattr(r["p"], "recruit_rank", 1e9))
    # Archived class: enrich every commit with how they turned out (current/last
    # team, status, STR at signing → STR now) so past classes answer "was this
    # class any good, and who panned out?".
    if is_archive:
        outcomes = _signee_outcomes([r["p"].pid for r in commitments], seed)
        for r in commitments:
            r["out"] = outcomes.get(r["p"].pid)
            r["str_sign"] = round(r["p"].str_value(), 1)
            o = r["out"]
            r["delta"] = (round(o["str_now"] - r["str_sign"], 1)
                          if o and o.get("str_now") is not None else None)
    flipped_total = sum(1 for school_pl in by_school.values()
                        for p in school_pl if getattr(p, "flips", 0) > 0)
    return {"classes": classes, "commitments": commitments,
            "total_signed": sum(c["n"] for c in classes), "n_programs": len(classes),
            "n_flipped": flipped_total,
            "year": year, "archive": is_archive,
            "class_of": world.BASE_YEAR + year + 1,
            "years": [{"val": y, "label": f"Class of {world.BASE_YEAR + y + 1}"
                       + ("" if y != cur else " (live)")} for y in years]}


def star_breakdown(stars: list[int]) -> list[dict]:
    """Per-tier signed counts, 5★ down to 1★ — the spread a class actually
    pulled in (a powerhouse skews high, a developmental program skews low)."""
    return [{"stars": s, "n": sum(1 for x in stars if x == s)} for s in (5, 4, 3, 2, 1)]


def team_recruiting_class(gender: str, school: str, seed: int = DEFAULT_SEED) -> dict:
    import app.world as world
    from .rankings_data import crest
    recruits = world.signings(seed).get(gender, {}).get(school, [])
    stars = [getattr(p, "recruit_stars", 0) for p in recruits]
    abbr, color = crest(school)
    commits = sorted(recruits, key=lambda p: getattr(p, "recruit_rank", 1e9))
    return {
        "school": school, "abbr": abbr, "color": color, "n": len(recruits),
        "score": round(_class_score(recruits), 1),              # top-3: 0.1 × ΣSTR × sqrt(1000/avgRank)
        "blue": sum(1 for p in recruits if getattr(p, "recruit_tier", "") == "Blue Chip"),
        "five": sum(1 for x in stars if x >= 5), "four": sum(1 for x in stars if x == 4),
        "three": sum(1 for x in stars if x == 3), "two": sum(1 for x in stars if x == 2),
        "one": sum(1 for x in stars if x == 1),
        "breakdown": star_breakdown(stars),
        "total_stars": sum(stars), "avg_stars": round(sum(stars) / len(stars), 2) if stars else 0.0,
        "commits": commits,
    }


# ---- The Wire (every transfer, every year) ------------------------------------
#
# Portal Rankings grades ONE transfer class: which programs got better this window.
# The Wire answers the other question — where has this player been — so it reads the
# whole `world_portal_move` archive at once and puts a career on every row. No new
# table: the archive already stores year, cycle, gender, kind, pid, name, STR and both
# school+division ends of every committed move.
#
# ⚠️ Division is ARCHIVED per move; conference is looked up LIVE, and that asymmetry is
# deliberate. `src_div`/`dest_div` are what the programs were at the time and must stay
# that way — a 2027 dual really was played in D1 even if the program sits in D2 now. A
# conference, though, is how you FIND a program ("show me everything into the SEC"), and
# you search by the league it plays in today, not the one it left. So the lookup indexes
# a school across ALL FOUR division files rather than the division the row recorded: read
# it out of `dest_div` and a realigned program (the JVC went D1 -> D2) would be looked up
# in a file it is no longer in and come back unaffiliated.
_WIRE_KINDS = {
    "riser": ("Rise", "a player moving UP — the portal's whole point"),
    "cascade": ("Depth", "displaced by an incoming riser, cascading down"),
    "pro": ("Pro", "an ex-tour player entering college through the portal"),
}
_DIV_RANK = {"D1": 0, "D2": 1, "D3": 2, "D4": 3, "PRO": -1}
_CYCLE_LABEL = {"preseason": "Preseason", "fall": "Fall"}

_wire_prog_cache: dict = {}


def _wire_programs(gender: str) -> dict:
    """school -> {div, conf, conf_name} across all four divisions, as they stand TODAY.

    Cached for the process: the division JSON is static at runtime (rebuilding it is a
    deploy), and `ncaa.load_division` parses the file and derives prestige on every call,
    which is far too heavy for a page that touches every school in a 10-year archive.
    Computed into a LOCAL and published — never read back out of the dict it just wrote
    (the gthread worker rule; see CLAUDE.md)."""
    from app.ncaa import load_division
    hit = _wire_prog_cache.get(gender)
    if hit is not None:
        return hit
    out: dict = {}
    for division in ("D1", "D2", "D3", "D4"):
        try:
            div = load_division(division, gender)
        except FileNotFoundError:
            continue
        for p in div.programs:
            out[p.school] = {"div": p.division, "conf": p.conf_abbr, "conf_name": p.conf}
    _wire_prog_cache[gender] = out
    return out


def _wire_end(school: str, div: str, progs: dict) -> dict:
    """One end of a move: the school, the division it was in AT THE TIME, and the
    conference it plays in NOW. `Pros` is the synthetic pool ex-tour players arrive
    from — not a program, so it has no conference and never gets a crest link."""
    from .rankings_data import crest
    meta = progs.get(school) or {}
    abbr, color = crest(school) if school and school != "Pros" else ("PRO", "#2f6f4f")
    return {"school": school, "div": div, "abbr": abbr, "color": color,
            "conf": meta.get("conf", ""), "conf_name": meta.get("conf_name", ""),
            "real": bool(school) and school != "Pros"}


def wire_view(seed: int = DEFAULT_SEED, gender: str = "all", division: str = "All",
              conf: str = "All", kind: str = "All", year="all", sort: str = "recent",
              q: str = "") -> dict:
    """The Wire: every archived portal move in the world's history, filterable.

    Filters match EITHER end of a move. "Show me D1" means D1 departures as well as D1
    arrivals — a wire that only matched the destination would hide exactly the story a
    coach is looking for, which is who left.

    Every row carries the player's WHOLE trajectory, and the chain is built from the
    UNFILTERED archive on purpose: narrowing to one conference must not truncate the
    career it is showing you. That is the point of the page — a player who went
    Jefferson State -> UNLV -> Pros reads as one line without opening their profile."""
    import app.world as world
    g = gender if gender in ("men", "women") else "all"
    moves = world.all_portal_moves(seed, g if g != "all" else None)
    if not moves:
        return {"rows": [], "years": [], "confs": [], "kinds": list(_WIRE_KINDS),
                "gender": g, "division": division, "conf": conf, "kind": kind,
                "year": year, "sort": sort, "q": q, "kpis": {}, "total": 0}

    progs = {gg: _wire_programs(gg) for gg in ({"men", "women"} if g == "all" else {g})}

    # --- trajectories, over the FULL archive (before any filter) ---
    chains: dict = {}
    for m in moves:                                   # already chronological
        chains.setdefault(m["pid"], []).append(m)

    def journey(pid: str) -> list[str]:
        hops = chains[pid]
        return [hops[0]["src_school"]] + [h["dest_school"] for h in hops]

    def now_at(pid: str, gender: str) -> str:
        """The division to open a player's profile in — their CURRENT program's, never
        this row's.

        `/player` resolves the live season from the universe in the URL, so an old row
        built from its own `dest_div` sends a transferred player to a universe they left.
        A 2027 D1 -> D3 row would open the D3 season for someone who has since gone back
        up, dropping them onto the persisted-player fallback with none of their current
        records, ranking or stats. Every row of a career therefore points at the same
        place: the last destination in the chain, resolved through TODAY'S division for
        that school (the same live lookup the conference column uses, so a realigned
        program still lands in the universe it actually plays in)."""
        last = chains[pid][-1]
        meta = progs.get(gender, {}).get(last["dest_school"]) or {}
        return meta.get("div") or last["dest_div"]

    # Where THIS move sits in that player's career. A chain of n moves visits n+1
    # schools, so hop i runs journey[i] -> journey[i+1]; the row lights those two so a
    # middle transfer reads as a middle transfer rather than as the whole career.
    # Counted while walking `moves` in the same chronological order the chains were
    # built in, rather than keyed on the dicts themselves.
    hop_no: dict = {}

    rows = []
    for m in moves:
        hop = hop_no.get(m["pid"], 0)
        hop_no[m["pid"]] = hop + 1
        p = progs.get(m["gender"], {})
        src = _wire_end(m["src_school"], m["src_div"], p)
        dst = _wire_end(m["dest_school"], m["dest_div"], p)
        label, why = _WIRE_KINDS.get(m["kind"], (m["kind"].title(), ""))
        d_src, d_dst = _DIV_RANK.get(m["src_div"], 9), _DIV_RANK.get(m["dest_div"], 9)
        rows.append({
            "year": m["year"], "year_label": world.BASE_YEAR + m["year"],
            "cycle": m["cycle"], "cycle_label": _CYCLE_LABEL.get(m["cycle"], m["cycle"].title()),
            "gender": m["gender"], "pid": m["pid"], "name": m["name"],
            "str": round(m["str"], 1), "kind": m["kind"], "kind_label": label, "why": why,
            # negative = moved UP a division (D2 -> D1), positive = down, 0 = lateral
            "step": d_dst - d_src,
            "src": src, "dest": dst,
            "journey": journey(m["pid"]), "hops": len(chains[m["pid"]]),
            "hop": hop, "now_div": now_at(m["pid"], m["gender"]),
        })

    # --- the dropdowns describe THIS archive, not the whole league. A conference
    # nobody has ever transferred into is noise in the filter. (Same rule as
    # scout_intel.portal_search_states.) ---
    years = sorted({r["year"] for r in rows}, reverse=True)
    confs = sorted({c for r in rows for c in (r["src"]["conf"], r["dest"]["conf"]) if c})

    try:
        yr = int(year)
    except (TypeError, ValueError):
        yr = None
    if yr is not None:
        rows = [r for r in rows if r["year"] == yr]
    if division != "All":
        rows = [r for r in rows if division in (r["src"]["div"], r["dest"]["div"])]
    if conf != "All":
        rows = [r for r in rows if conf in (r["src"]["conf"], r["dest"]["conf"])]
    if kind != "All":
        rows = [r for r in rows if r["kind"] == kind]
    if q:
        needle = q.strip().lower()
        rows = [r for r in rows if needle in r["name"].lower()
                or needle in r["src"]["school"].lower()
                or needle in r["dest"]["school"].lower()]

    order = {
        "recent": lambda r: (-r["year"], -world._CYCLE_ORDER.get(r["cycle"], 9), r["name"]),
        "oldest": lambda r: (r["year"], world._CYCLE_ORDER.get(r["cycle"], 9), r["name"]),
        "str": lambda r: (-r["str"], r["name"]),
        "name": lambda r: (r["name"], r["year"]),
        "journey": lambda r: (-r["hops"], r["name"], r["year"]),
    }
    rows.sort(key=order.get(sort, order["recent"]))

    ups = sum(1 for r in rows if r["step"] < 0)
    # Every KPI counts the ROWS ON SCREEN. `years` is the unfiltered archive because the
    # dropdown has to keep offering seasons you have filtered away — reusing it here read
    # "10 seasons archived" beside a single season's move count, which is two different
    # populations in one sentence.
    kpis = {
        "moves": len(rows), "players": len({r["pid"] for r in rows}),
        "up": ups, "down": sum(1 for r in rows if r["step"] > 0),
        "lateral": len(rows) - ups - sum(1 for r in rows if r["step"] > 0),
        "avg_str": round(sum(r["str"] for r in rows) / len(rows), 1) if rows else 0.0,
        "seasons": len({r["year"] for r in rows}),
        "multi": len({r["pid"] for r in rows if r["hops"] > 1}),
    }
    return {"rows": rows, "years": years, "confs": confs, "kinds": list(_WIRE_KINDS),
            "gender": g, "division": division, "conf": conf, "kind": kind,
            "year": year, "sort": sort, "q": q, "kpis": kpis, "total": len(rows)}


# ---- Portal Rankings (transfer-class board, On3/247 style) ---------------------
_PORTAL_SCORE_SCALE = 0.1   # top-3 STR sum × this → a readable "points" number (~15-18 strong)


def _portal_score(movers: list) -> float:
    """Score a portal class the same TOP-3 shape as recruiting, but on STR — portal movers
    carry a live STR, not a recruit rank. Σ of the three best STRs × scale."""
    top = sorted(movers, key=lambda m: m["str"], reverse=True)[:3]
    return _PORTAL_SCORE_SCALE * sum(m["str"] for m in top) if top else 0.0


def portal_class_rankings(seed: int = DEFAULT_SEED, gender: str = "all",
                          division: str = "All", year=None) -> dict:
    """Transfer-class rankings for a portal year — every program's IN class (risers + pros +
    depth it picked up) vs what it LOST, scored + ranked like recruiting classes. Filterable
    by year / gender / classification (D1–D4 or All), so a lower-division coach can see which
    D3/D4 programs actually got better in the window. Reads the durable `world_portal_move`
    archive, so past years stay available."""
    import app.world as world
    from .rankings_data import crest
    years = world.portal_years(seed)
    year_opts = [{"val": y, "label": world.BASE_YEAR + y} for y in years]
    if not years:
        return {"year": None, "year_label": None, "years": [], "classes": [], "gender": gender,
                "division": division, "kpis": {}, "n_programs": 0, "total_moves": 0}
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = None
    if year not in years:
        year = years[0]
    g = gender if gender in ("men", "women") else "all"
    moves = world.portal_moves(seed, year, g if g != "all" else None)

    prog: dict = {}

    def _p(school):
        return prog.setdefault(school, {"in": [], "out": [], "div": ""})

    for m in moves:
        pin = _p(m["dest_school"])                      # this school is the destination = a gain
        pin["in"].append(m)
        if not pin["div"]:
            pin["div"] = m["dest_div"]
        # the source lost the player (rose away, or was bumped down). Pros come from the
        # synthetic "Pros" pool — not a real program — so they never count as an OUT.
        if m["src_school"] and m["src_school"] != "Pros":
            pout = _p(m["src_school"])
            pout["out"].append(m)
            if not pout["div"]:
                pout["div"] = m["src_div"]

    classes = []
    for school, d in prog.items():
        div = d["div"]
        if division != "All" and div != division:
            continue
        ins, outs = d["in"], d["out"]
        in_str = [m["str"] for m in ins]
        out_str = [m["str"] for m in outs]
        score = _portal_score(ins)
        abbr, color = crest(school)
        classes.append({
            "school": school, "abbr": abbr, "color": color, "div": div,
            "in_n": len(ins), "in_avg": round(sum(in_str) / len(in_str), 1) if in_str else 0.0,
            "out_n": len(outs), "out_avg": round(sum(out_str) / len(out_str), 1) if out_str else 0.0,
            "risers": sum(1 for m in ins if m["kind"] == "riser"),
            "pros": sum(1 for m in ins if m["kind"] == "pro"),
            "depth": sum(1 for m in ins if m["kind"] == "cascade"),
            "score": round(score, 1),
            "net": round(score - _portal_score(outs), 1),   # improved (+) / maintained / lost (−)
            "best": sorted(ins, key=lambda m: m["str"], reverse=True)[:5],
        })
    classes.sort(key=lambda c: (-c["score"], -c["net"], c["school"]))
    for i, c in enumerate(classes, 1):
        c["rank"] = i

    # KPIs describe the board you're LOOKING at, so scope them to acquisitions that LANDED in
    # the selected classification (by dest_div). A player who came FROM a higher division still
    # counts here — they landed in this division — so a lower program signing a D1-origin player
    # shows on its own board; only pickups landing in OTHER divisions drop off.
    kpi_moves = moves if division == "All" else [m for m in moves if m["dest_div"] == division]
    all_str = [m["str"] for m in kpi_moves]
    kpis = {
        "total_moves": len(kpi_moves),
        "risers": sum(1 for m in kpi_moves if m["kind"] == "riser"),
        "pros": sum(1 for m in kpi_moves if m["kind"] == "pro"),
        "depth": sum(1 for m in kpi_moves if m["kind"] == "cascade"),
        "avg_str": round(sum(all_str) / len(all_str), 1) if all_str else 0.0,
        "programs": len(classes),
        "top_pickup": max(kpi_moves, key=lambda m: m["str"]) if kpi_moves else None,
    }
    return {"year": year, "year_label": world.BASE_YEAR + year, "years": year_opts,
            "classes": classes, "gender": g, "division": division, "kpis": kpis,
            "n_programs": len(classes), "total_moves": len(kpi_moves)}


def recruiting_hub(gender: str, grad_year: int, seed: int = DEFAULT_SEED) -> dict:
    """The Recruiting HQ landing: class KPIs + top prospects + league leaders — the
    data-portal overview that ties the dense sub-pages together."""
    from app import almanac
    klass = get_recruits(gender, grad_year, seed)
    recruits = points_rankings(klass)
    stats = {p.pid: almanac.stat_line(p) for p in recruits}
    intl = [p for p in recruits if not p.domestic]
    kpis = {
        "class_size": len(recruits),
        "intl_pct": round(100 * len(intl) / max(1, len(recruits))),
        "bluechips": sum(1 for p in recruits if getattr(p, "recruit_stars", 0) >= 5),
        "fourstar": sum(1 for p in recruits if getattr(p, "recruit_stars", 0) == 4),
        "nations": len({p.country for p in intl}),
        "states": len({p.region for p in recruits if p.domestic}),
        "top": recruits[0] if recruits else None,
    }
    top_rows = [(p.points_rank, p, stats[p.pid], almanac.honor_chip(p)) for p in recruits[:12]]
    return {"kpis": kpis, "top_rows": top_rows, "leaders": almanac.leaders(recruits, stats)}


_tour_cache: dict = {}


def _tournament_index(gender, grad_year, seed):
    key = (gender, grad_year, seed)
    if key not in _tour_cache:
        from app import almanac
        _tour_cache[key] = almanac.tournament_index(get_recruits(gender, grad_year, seed).recruits)
    return _tour_cache[key]


def junior_tournaments(gender: str, grad_year: int, tier: str = "", seed: int = DEFAULT_SEED):
    from app import almanac
    tours = list(_tournament_index(gender, grad_year, seed).values())
    if tier and tier != "All":
        tours = [t for t in tours if t["level"] == tier]
    return [{"name": t["name"], "week": t["week"], "level": t["level"],
             "champion": t["champion"], "finalist": t["finalist"],
             "n_entrants": len(t["entrants"])}
            for t in almanac.sort_tournaments(tours)]


def junior_tournament_detail(gender: str, grad_year: int, name: str, seed: int = DEFAULT_SEED):
    from app import almanac
    t = _tournament_index(gender, grad_year, seed).get(name)
    if not t:
        return None
    return {"name": t["name"], "week": t["week"], "level": t["level"],
            "champion": t["champion"], "finalist": t["finalist"],
            "n_entrants": len(t["entrants"]), "rounds": almanac.tournament_rounds(t["matches"])}


def junior_nation_boards(gender: str, grad_year: int, seed: int = DEFAULT_SEED):
    from app import almanac
    klass = get_recruits(gender, grad_year, seed)
    return [(nat, [(i, p, almanac.stat_line(p), almanac.honor_chip(p))
                   for i, p in enumerate(players, 1)])
            for nat, players in nation_points_top(klass)]


# ---- Junior Setup: in-game tuning of the junior-circuit knobs (no code editor) ----
_JR_KEYS = {"jr_season_weeks", "jr_draw_size", "jr_dev_years", "jr_doubles_weight", "jr_bands"}


def junior_setup_view() -> dict:
    from app.junior_circuit import (_jr_config, BANDS, SEASON_WEEKS, DRAW_SIZE,
                                    JUNIOR_DEV_YEARS, DOUBLES_WEIGHT)
    cur = _jr_config()
    return {
        "weeks": cur["weeks"], "draw": cur["draw"], "dev": cur["dev"],
        "doubles_weight": cur["doubles_weight"],
        "bands": [(t, round(f * 100)) for t, f in cur["bands"]],
        "defaults": {"weeks": SEASON_WEEKS, "draw": DRAW_SIZE, "dev": JUNIOR_DEV_YEARS,
                     "doubles_weight": DOUBLES_WEIGHT,
                     "bands": [(t, round(f * 100)) for t, f in BANDS]},
    }


def save_junior_setup(form) -> None:
    import json
    from app import worldconfig
    from app.junior_circuit import BANDS

    def _num(key, default):
        try:
            return float(form.get(key, default))
        except (TypeError, ValueError):
            return default

    worldconfig.set("jr_season_weeks", str(int(_num("season_weeks", 14))))
    worldconfig.set("jr_draw_size", str(int(_num("draw_size", 32))))
    worldconfig.set("jr_dev_years", str(_num("dev_years", 1.0)))
    worldconfig.set("jr_doubles_weight", str(_num("doubles_weight", 0.25)))
    base = dict(BANDS)
    bands = [[tier, max(0.0, min(1.0, _num(f"band_{tier}", base[tier] * 100) / 100.0))]
             for tier, _ in BANDS]
    worldconfig.set("jr_bands", json.dumps(bands))
    _recruit_cache.clear()
    _tour_cache.clear()


def reset_junior_setup() -> None:
    from app import worldconfig
    for k in _JR_KEYS:
        worldconfig.set(k, "")
    _recruit_cache.clear()
    _tour_cache.clear()


def get_recruit(gender: str, grad_year: int, pid: str, seed: int = DEFAULT_SEED, division=None):
    """Resolve a player for /recruit/<pid> in a strict order:
      1. persisted signed/committed/rostered data (anyone tied to a team),
      2. the canonical active-world recruit class,
    and NEVER the old DEFAULT_SEED web-board class."""
    from app import world
    p = world.find_persisted_player(pid, seed)
    if p is not None:
        # A signed player resolves out of world_signing here; stamp where they
        # signed so the profile shows "Signed with X" instead of the open board.
        smap = _signed_school_map(gender, grad_year, seed)
        p.commit_school = smap.get(pid)
        p.committed = p.commit_school is not None
        # The junior circuit now runs lazily (board_class), so a recruit signed
        # before any board view was viewed has an EMPTY junior résumé on its
        # persisted blob. For an active-class signee, re-resolve the résumé live
        # by pid — it's deterministic from the world salt, so it's the SAME data
        # the open board shows. (Junior data is a current-class board concern;
        # rostered/past players never surface it — see get_recruit callers.)
        if pid in smap:
            _overlay_junior_resume(p, gender, grad_year, seed)
        return p
    klass = get_recruits(gender, grad_year, seed)
    _apply_committed_flag(klass, gender, grad_year)
    return next((q for q in klass.recruits if q.pid == pid), None)


# Everything the junior circuit freezes onto a recruit — both the persisted
# dataclass fields (junior_str/results/badges/…) and the dynamic board fields
# (points ledger, doubles, ranks). Overlaid live onto a signed recruit whose
# persisted blob predates the circuit run. Keep in sync with junior_circuit's
# freeze step + juniors.points_rankings.
_JUNIOR_RESUME_FIELDS = (
    "junior_tier", "junior_str", "junior_str_reliability",
    "junior_results", "junior_matches", "ranking_history", "junior_badges",
    "singles_points", "doubles_points", "junior_points",
    "tournaments_played", "doubles_played",
    "junior_doubles_str", "junior_doubles_results", "junior_doubles_matches",
    "points_rank",
    "tenniseye_rank", "tenniseye_tier", "tenniseye_stars",
)


def _overlay_junior_resume(p, gender: str, grad_year: int, seed: int = DEFAULT_SEED) -> None:
    """Copy the live junior-circuit résumé from the active board class onto a
    persisted signed recruit `p` (matched by pid). Triggers the lazy circuit via
    `get_recruits` → `world.board_class`, then mirrors every junior field so the
    signee's profile is identical to the open-board view."""
    klass = get_recruits(gender, grad_year, seed)        # board_class → ensures circuit
    live = next((q for q in klass.recruits if q.pid == p.pid), None)
    if live is None:
        return
    for f in _JUNIOR_RESUME_FIELDS:
        if hasattr(live, f):
            setattr(p, f, getattr(live, f))


_REV_RECRUIT_GENDERS = {v: k for k, v in RECRUIT_GENDERS.items()}


def _signed_school_map(gender: str, grad_year: int, seed: int = DEFAULT_SEED) -> dict:
    """{pid: school} for recruits who have signed in the active class, or {} when
    `grad_year` isn't the class currently being signed. The active signing class
    is `BASE_YEAR + world.year + 1` (see world.recruiting_grad_year), NOT the bare
    world year — the previous `w["year"] != grad_year` guard compared an integer
    season index (0,1,2…) to a calendar year and so always cleared the flag."""
    import app.world as world
    w = world.load_world(seed)
    if not w or world.BASE_YEAR + w["year"] + 1 != grad_year:
        return {}
    wgender = _REV_RECRUIT_GENDERS.get(gender, gender)
    return {p.pid: school
            for school, pl in world.signings(seed).get(wgender, {}).items()
            for p in pl}


def _apply_committed_flag(klass, gender: str, grad_year: int) -> None:
    smap = _signed_school_map(gender, grad_year)
    for p in klass.recruits:
        p.commit_school = smap.get(p.pid)
        p.committed = p.commit_school is not None


def recruit_rows(gender: str, grad_year: int, scope: str = "national", state: str = "",
                 division: str = "D1", unsigned_only: bool = False):
    klass = get_recruits(gender, grad_year, division=division)
    _apply_committed_flag(klass, gender, grad_year)
    if scope == "state":
        src = state_rankings(klass, state)
    elif scope == "intl":
        src = international_rankings(klass)
    else:
        src = national_rankings(klass)
    if unsigned_only:
        src = [q for q in src if not getattr(q, "committed", False)]
    from app.juniors import recruit_grade
    n = len(klass.recruits)
    # (board_rank, Prospect, rating100, composite) — grade reflects the *national*
    # board position even on state/intl boards, exactly like a real composite.
    out = []
    for i, p in enumerate(src, 1):
        rating, comp = recruit_grade(getattr(p, "recruit_rank", i) or i, n)
        out.append((i, p, rating, comp))
    return out


SCOUT_ATTRS = [
    ("first_serve_power", "Serve Power"), ("first_serve_accuracy", "Serve Accuracy"),
    ("return_quality", "Return"), ("forehand_power", "Forehand"),
    ("backhand_power", "Backhand"), ("groundstroke_consistency", "Consistency"),
    ("net_play", "Net Play"), ("speed", "Speed"), ("stamina", "Stamina"),
    ("composure", "Composure"), ("clutch", "Clutch"),
]


def scout_bars(p):
    return [(label, p.current_grade(key)) for key, label in SCOUT_ATTRS]


def recruit_profile(p, division: str, gender: str, grad_year: int):
    rg = RECRUIT_GENDERS.get(gender, "male") if gender in RECRUIT_GENDERS else gender
    klass = get_recruits(rg, grad_year, division=division)
    if p.domestic:
        regional = state_rankings(klass, p.region)
        region_rank = next((i for i, q in enumerate(regional, 1) if q.pid == p.pid), None)
        region_label = p.region
    else:
        intl = international_rankings(klass)
        region_rank = next((i for i, q in enumerate(intl, 1) if q.pid == p.pid), None)
        region_label = "International"

    from app.recruiting import build_recruiting, schools_from_programs, academic_sat
    programs = all_gender_programs(gender)
    schools = schools_from_programs(programs)
    rec = build_recruiting(p, schools, seed_salt=f"{grad_year}")

    # Roster fit / playing time: for the schools on the board, show the program's
    # current starting-card OVRs and where this recruit projects to slot — the same
    # signal the sim's recruiting model weighs (see world._pick_school). The card is
    # the division's lineup size (D1/D4 field 10, D2/D3 eight). Only the ~handful
    # of offer schools are built (rosters are cached), so this stays cheap. The
    # `top6`/`sixth` keys are stored names the recruit page reads: the card list,
    # and the LAST STARTER's OVR (the bar a recruit must clear to start).
    from app.ncaa import build_roster, lineup_size
    prog_by_name = {pr.school: pr for pr in programs}
    recruit_ovr = p.current_overall()
    roster_fit = {}
    for o in rec.offers:
        pr = prog_by_name.get(o.school)
        if pr is None:
            continue
        _lu = lineup_size(pr.division)
        ovrs = sorted((pl.current_overall() for pl in build_roster(pr)), reverse=True)
        last = ovrs[_lu - 1] if len(ovrs) >= _lu else None
        if last is None or recruit_ovr >= last:
            slot = "Starter"
        elif len(ovrs) >= _lu + 2 and recruit_ovr >= ovrs[_lu + 1]:
            slot = "Rotation"
        else:
            slot = "Depth"
        roster_fit[o.school] = {
            "slot": slot,
            "top6": [round(x) for x in ovrs[:_lu]],
            "sixth": round(last) if last is not None else None,
            "card": _lu,
        }

    from app.junior_circuit import TIER_LABELS
    from app.juniors import grade_letter

    # Confidence in the commit favourite: a function of how far the StrikePred.
    # leader is clear of the field (HIGH / MED / LOW), mirroring a crystal ball.
    pct = rec.predicted_pct
    runner_up = rec.offers[1].strikeprediction if len(rec.offers) > 1 else 0
    lead = pct - runner_up
    if pct >= 65 or lead >= 30:
        confidence = "HIGH"
    elif pct >= 40 or lead >= 12:
        confidence = "MED"
    else:
        confidence = "LOW"

    return {
        "national_rank": p.recruit_rank,
        "region_rank": region_rank,
        "region_label": region_label,
        "points_rank": getattr(p, "points_rank", None),
        "junior_points": getattr(p, "junior_points", 0),
        "tournaments_played": getattr(p, "tournaments_played", 0),
        "junior_str": getattr(p, "junior_str", None),
        "junior_tier_label": TIER_LABELS.get(p.junior_tier, ""),
        "recruiting": rec,
        "roster_fit": roster_fit,
        "sat": academic_sat(getattr(p, "academic_rating", None)),
        "scout_bars": scout_bars(p),
        # TennisEye's results-based tier, lettered instead of starred so it's
        # never visually confusable with the board's fogged stars — same
        # TIER_CUTOFFS pyramid, just a different alphabet. See
        # docs/DESIGN-recruit-rating-clarity.md.
        "te_grade": grade_letter(getattr(p, "tenniseye_tier", "")),
        "confidence": confidence,
    }


def _acad_year(cal_year: int) -> str:
    return f"{cal_year - 1}-{cal_year % 100:02d}"


def player_career_records(division: str, gender: str, pid: str, seed: int = DEFAULT_SEED):
    """The college-tennis 'career record' boxes: per-line W-L by season for
    singles (lines 1–6) and doubles (1–3), each with Overall, Dual, and a TOTALS
    row. Built from the player's recorded per-line history plus the in-progress
    current season. (Dual == Overall here — every match in the sim is a team
    dual; the columns diverge only once individual events are tracked.)"""
    import app.world as world
    import app.seasonmode as sm

    p = world.find_persisted_player(pid, seed)
    hist = list(getattr(p, "history", []) or []) if p else []
    seasons = []
    for h in hist:
        seasons.append({
            "cal_year": world.BASE_YEAR + h["year"],
            "singles": {int(k): v for k, v in (h.get("singles_lines") or {}).items()},
            "doubles": {int(k): v for k, v in (h.get("doubles_lines") or {}).items()},
        })
    wld = world.load_world(seed)
    cur = wld["year"] if wld else 0
    if not any(h.get("year") == cur for h in hist):
        sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
        lr = sm.player_line_records(sid).get(pid)
        if lr:
            seasons.append({"cal_year": world.BASE_YEAR + cur,
                            "singles": lr["singles"], "doubles": lr["doubles"]})
    seasons.sort(key=lambda s: s["cal_year"])

    def _box(kind: str, n_lines: int):
        rows, totals, tov = [], {i: [0, 0] for i in range(1, n_lines + 1)}, [0, 0]
        for s in seasons:
            lines, ov = s[kind], [0, 0]
            cells = {}
            for i in range(1, n_lines + 1):
                wl = lines.get(i)
                cells[i] = (f"{wl[0]}-{wl[1]}" if wl else "–")
                if wl:
                    ov[0] += wl[0]; ov[1] += wl[1]
                    totals[i][0] += wl[0]; totals[i][1] += wl[1]
            tov[0] += ov[0]; tov[1] += ov[1]
            rows.append({"year": _acad_year(s["cal_year"]), "cells": cells,
                         "overall": f"{ov[0]}-{ov[1]}", "dual": f"{ov[0]}-{ov[1]}"})
        tcells = {i: (f"{totals[i][0]}-{totals[i][1]}" if (totals[i][0] or totals[i][1]) else "–")
                  for i in range(1, n_lines + 1)}
        return {"n_lines": n_lines, "rows": rows, "lines": list(range(1, n_lines + 1)),
                "tcells": tcells, "toverall": f"{tov[0]}-{tov[1]}", "tdual": f"{tov[0]}-{tov[1]}",
                "any": bool(rows)}

    # Card width = the player's division's dual shape, widened to any line they
    # actually played (career history can span formats — pre-change seasons and
    # cross-division transfers both live in the same table).
    from app.ncaa import dual_format
    f = dual_format(division)
    n_s = max([f.n_singles] + [max(s["singles"], default=0) for s in seasons])
    n_d = max([f.n_doubles] + [max(s["doubles"], default=0) for s in seasons])
    return {"singles": _box("singles", n_s), "doubles": _box("doubles", n_d)}


def _round_phase(round_: str, conf: str):
    """(group_title, phase_label) for a dual round."""
    if round_ == "CT":
        return (f"{conf} Tournament", "Conference Tournament")
    if round_ == "NCAA":
        return (conf or "NCAA", "NCAA Championship")     # conf holds the round name
    return ("Regular Season", "Regular Season")


_CT_ROUND_NAMES = {0: "Final", 1: "Semifinals", 2: "Quarterfinals",
                   3: "Round of 16", 4: "Round of 32", 5: "Round of 64"}


def _ct_round_name(round_no: int, total_rounds: int) -> str:
    """Name a conference-tournament round from the END — the last round is the
    Final — so it reads correctly for any bracket size (Final, Semifinals,
    Quarterfinals, …) regardless of how many teams the conference seeded."""
    back = max(0, (total_rounds or round_no) - round_no)
    return _CT_ROUND_NAMES.get(back, f"Round {round_no}")


def results_by_week(division: str, gender: str, week=None, seed: int = DEFAULT_SEED):
    """Week-by-week results browser: for the selected week, the duals played
    (regular slate + conference-tournament rounds + NCAA rounds), grouped and
    labelled, each with its score and winner. Also returns the weeks that have
    results so the page can offer a selector."""
    import app.world as world
    import app.seasonmode as sm
    from .rankings_data import crest
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    rows = sm.all_results(sid)
    if not rows:
        return {"weeks": [], "week": None, "groups": [], "phase_label": None}

    order = {"REG": 0, "CT": 1, "NCAA": 2}
    by_week: dict = {}
    ct_rounds: dict = {}                 # conf -> its CT's final round_no (rounds total)
    for r in rows:
        by_week.setdefault(r["week"], []).append(r)
        if r["round"] == "CT":
            ct_rounds[r["conf"]] = max(ct_rounds.get(r["conf"], 0), r["round_no"] or 0)
    weeks = []
    for wk in sorted(by_week):
        top = max(by_week[wk], key=lambda r: order.get(r["round"], 0))
        weeks.append({"week": wk, "phase": _round_phase(top["round"], top["conf"])[1]})

    sel = int(week) if week is not None else weeks[-1]["week"]
    if sel not in by_week:
        sel = weeks[-1]["week"]

    groups_map: dict = {}
    for r in by_week[sel]:
        title, phase = _round_phase(r["round"], r["conf"])
        g = groups_map.setdefault((order.get(r["round"], 0), title),
                                  {"title": title, "phase": phase, "round_label": None,
                                   "duals": []})
        # Conference tournaments label by ROUND (Semifinals, Final, …) instead of a
        # bare dual count — one bracket round is played per week.
        if r["round"] == "CT":
            g["round_label"] = _ct_round_name(r["round_no"] or 0, ct_rounds.get(r["conf"], 0))
        hp, ap = r["home_points"], r["away_points"]
        ha, hc = crest(r["home"])
        aa, ac = crest(r["away"])
        g["duals"].append({
            "home": r["home"], "away": r["away"], "home_abbr": ha, "home_color": hc,
            "away_abbr": aa, "away_color": ac, "hp": hp, "ap": ap,
            "home_won": r["winner"] == 0,
            "score": f"{max(hp, ap)}-{min(hp, ap)}" if hp is not None else "",
        })
    groups = [groups_map[k] for k in sorted(groups_map)]
    sel_phase = next((w["phase"] for w in weeks if w["week"] == sel), None)
    return {"weeks": weeks, "week": sel, "groups": groups, "phase_label": sel_phase}


def transfer_portal_view(division: str, gender: str, seed: int = DEFAULT_SEED, year=None):
    """Every transfer in this universe — where each player started and where they
    went — reconstructed from career history (a school change between seasons is a
    transfer). Newest off-season first. `year` (calendar) filters to one off-season;
    the full set of years is returned for the picker."""
    import app.world as world
    from .rankings_data import crest
    w = world.load_world(seed)
    if not w:
        return {"transfers": [], "n": 0, "current_year": None, "years": [], "year": year}
    rosters = world._base_rosters(w).get((division, gender), {})
    cur_cal = world.BASE_YEAR + w["year"]
    events = []
    for school, roster in rosters.items():
        for p in roster:
            hist = sorted((getattr(p, "history", []) or []),
                          key=lambda h: (h.get("year", 0), h.get("stint", 0)))
            seq = [(world.BASE_YEAR + h["year"], h.get("school")) for h in hist]
            seq.append((cur_cal, school))               # current spot closes the timeline
            for i in range(1, len(seq)):
                (_py, ps), (cy, cs) = seq[i - 1], seq[i]
                if ps and cs and ps != cs:
                    fa, fc = crest(ps)
                    ta, tc = crest(cs)
                    events.append({
                        "pid": p.pid, "name": p.name, "country": getattr(p, "country", ""),
                        "year": cy, "from": ps, "to": cs, "from_abbr": fa, "from_color": fc,
                        "to_abbr": ta, "to_color": tc, "str": round(p.str_value(), 1),
                        "class": getattr(p, "class_year", ""),
                    })
    events.sort(key=lambda e: (e["year"], -e["str"], e["name"]), reverse=True)
    years = sorted({e["year"] for e in events}, reverse=True)
    if year is not None:
        events = [e for e in events if e["year"] == year]
    return {"transfers": events, "n": len(events), "current_year": cur_cal,
            "years": years, "year": year}


def _portal_q_filter(rows: list, q: str) -> list:
    """Case-insensitive slate filter: keep rows whose player name, source school or
    destination school contains `q` — so a big slate can be scanned/edited without
    paging through it."""
    needle = (q or "").strip().lower()
    if not needle:
        return rows
    return [r for r in rows
            if needle in (r.get("name") or "").lower()
            or needle in (r.get("src_school") or "").lower()
            or needle in (r.get("dest_school") or "").lower()]


def fall_portal_view(seed: int = DEFAULT_SEED, page: int = 1,
                     per_page: int | None = None, q: str = "") -> dict:
    """The fall-portal slate for the review screen: each kept rider plus the player
    they'd push down the ladder, freshly RESOLVED so the cascade reflects any
    redirects/adds the user has made. Riders carry an editable destination.
    Paginated (the slate can run to hundreds of rows across both genders);
    `per_page` overrides the default page size and `q` filters by player/school."""
    import app.world as world
    from app import overrides as ov
    from .pagination import paginate
    from .rankings_data import crest
    w = world.load_world(seed)
    if not w:
        return {"year": None, "proposals": [], "n": 0, "riders": 0, "committed": 0,
                "destinations": [], "page": 1, "pages": 1, "q": "",
                "pager": paginate([], 1, PRESEASON_PORTAL_PER_PAGE)}
    committed = [r for r in ov.get_proposals(w["year"], status="committed")]
    resolved = world.resolve_fall_portal(seed)        # {gender: [moves]} (riders + cascades)
    recs, lines = world._ita_lookup(seed, w)
    out = []
    for gender, moves in resolved.items():
        for m in moves:
            p = world.find_persisted_player(m["pid"], seed)
            fa, fc = crest(m["src_school"])
            ta, tc = crest(m["dest_school"])
            sd = (m["src_div"], gender)
            ww, ll = recs.get(sd, {}).get(m["pid"], (0, 0))
            out.append({
                **m, "gender": gender,
                "name": getattr(p, "name", m["pid"]),
                "class": getattr(p, "class_year", ""),
                "country": getattr(p, "country", ""),
                "from_abbr": fa, "from_color": fc, "to_abbr": ta, "to_color": tc,
                "is_riser": m["cascade_from"] is None,
                "ita_w": ww, "ita_l": ll, "ita_line": lines.get(sd, {}).get(m["pid"]),
            })
    out.sort(key=lambda r: (0 if r["is_riser"] else 1, -r["str"], r["pid"]))
    # Free-agent pros for the FALL cycle — same manual model as the pre-season portal.
    cyc = f"{w['year']}-fall"
    committed_pros = world.list_pros(seed, cyc)
    _pro_src = committed_pros if committed_pros else world.pro_cohort(seed, cyc)
    pros_in = []
    for pr in _pro_src:
        ta, tc = crest(pr["dest_school"]) if pr.get("dest_school") else ("", "")
        pros_in.append({**pr, "to_abbr": ta, "to_color": tc})
    # Paginate the full combined slate (both genders shown together); riders/n stay
    # totals over the whole slate, proposals is just the current page.
    shown = _portal_q_filter(out, q)
    pg = paginate(shown, page, per_page or PRESEASON_PORTAL_PER_PAGE)
    return {"year": world.BASE_YEAR + w["year"], "raw_year": w["year"],
            "proposals": pg.items, "n": len(out), "q": (q or "").strip(),
            "riders": sum(1 for r in out if r["is_riser"]),
            "committed": len(committed), "pros": pros_in,
            "pros_committed": bool(committed_pros),
            "page": pg.page, "pages": pg.pages, "pager": pg,
            "destinations": world.fall_portal_destinations(seed)}


def recruit_economy_view() -> dict:
    """Live reference for the scholarship-BUDGET economy: recruit cost by star, the
    budget floor to attract each tier, and the per-program budget bands by conference
    tier. Read straight off `recruit_economy` so the page never drifts from the sim."""
    from app import recruit_economy as re
    from app.recruiting import academic_sat
    off = re._GRADE_OFFSET
    tiers = [{"name": n, "stars": st, "cost": c, "free": c == 0.0,
              "men_grade": round(g + off.get("men", 0.0), 1),
              "women_grade": round(g + off.get("women", 0.0), 1),
              "floor": re._TIER_FLOOR.get(n)}
             for (n, st, c, g) in re.TIERS]
    # what core each band can realistically build (from the design comments)
    _core = {"top": "≈3 blue chips — only the blue-bloods stack them",
             "major": "a 5★/4★ core, the odd blue-chip reach",
             "mid": "4★/3★ core", "low": "3★ core, thin (the D1 floor)"}
    d1 = [{"tier": t, "label": lbl, "lo": re._D1_TIER_BANDS[t][0],
           "hi": re._D1_TIER_BANDS[t][1], "core": _core[t]}
          for t, lbl in (("top", "Blue Blood (top)"), ("major", "High-major (major)"),
                         ("mid", "Mid-major (mid)"), ("low", "Low-major (low)"))]
    from app import pros as _pros
    import app.worldconfig as _wc
    return {
        "tiers": tiers,
        "d1_bands": d1,
        "d2_band": re._D2_BAND,
        "d4_band": re._D4_BAND,
        "d4_gate_lo": academic_sat(round(re.D4_MIN_FLOOR)),
        "d4_gate_hi": academic_sat(round(re.D4_MIN_CEIL)),
        "d3d4_band": re._D3D4_BAND,
        "elite_d2_prestige": re._ELITE_D2_PRESTIGE,
        "d3_top_n": len(re._d3_top_keys("men")),  # max(30, 5% of D3)
        "elite_academics": re._ELITE_D3D4_ACADEMICS,
        "roster_caps": {"D1": "12 (8 core + 4 walk-on)", "D2": "10 (6 + 4)",
                        "D4": "16 (6 funded + walk-ons)", "D3": "16 (3 + 13)"},
        "pros": {"per_cycle": _wc.pros_per_cycle(),
                 "attr_lo": int(_pros.PRO_ATTR[0]), "attr_hi": int(_pros.PRO_ATTR[1]),
                 "cost_lo": _pros.PRO_COST_LO, "cost_hi": _pros.PRO_COST_HI},
    }


PRESEASON_PORTAL_PER_PAGE = 50


def _paginate_portal(rows: list, gender: str, page: int, per_page: int) -> dict:
    """Gender filter + pagination shared by the committed and live portal views. Returns
    the page slice plus the meta the template needs (counts per gender, page nav)."""
    counts = {"all": len(rows), "men": sum(1 for r in rows if r.get("gender") == "men"),
              "women": sum(1 for r in rows if r.get("gender") == "women")}
    g = gender if gender in ("men", "women") else "all"
    filtered = rows if g == "all" else [r for r in rows if r.get("gender") == g]
    total = len(filtered)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    from .pagination import Page
    return {"page_rows": filtered[start:start + per_page], "gender": g,
            "gender_counts": counts, "page": page, "pages": pages,
            "per_page": per_page, "total_filtered": total,
            # A Page for the shared numbered pager (_pager.html) — items unused here,
            # it only needs the counts to render the window + prev/next.
            "pager": Page([], page, per_page, total)}


def preseason_portal_view(seed: int = DEFAULT_SEED, gender: str = "all",
                          page: int = 1, per_page: int | None = None,
                          q: str = "") -> dict:
    """The pre-season-portal slate for the week-0 review screen: each kept rider plus
    the player they'd push down the ladder, freshly RESOLVED so the cascade reflects
    any redirects / adds. Riders carry an editable destination. Once committed, the
    rows come back with status='committed' so the screen shows what was applied.
    Gender-filtered + paginated (the slate can run to hundreds of rows); `per_page`
    overrides the default page size and `q` filters by player/school."""
    import app.world as world
    import app.worldconfig as worldconfig
    from app import overrides as ov
    from .rankings_data import crest
    per_page = per_page or PRESEASON_PORTAL_PER_PAGE
    cap = worldconfig.preseason_portal_cap()
    pros_cycle = worldconfig.pros_per_cycle()
    w = world.load_world(seed)
    if not w:
        return {"year": None, "proposals": [], "n": 0, "riders": 0, "committed": 0,
                "destinations": [], "is_preseason": False, "cap": cap, "pros_cycle": pros_cycle,
                "pros": [], "gender": "all", "gender_counts": {"all": 0, "men": 0, "women": 0},
                "q": "", "page": 1, "pages": 1,
                "pager": _paginate_portal([], "all", 1, per_page)["pager"]}
    committed = ov.ps_get_proposals(w["year"], status="committed")
    # Pros are FREE AGENTS out of the synthetic "Pros" pool — pre-commit show the whole cohort
    # (each with an editable, initially-blank destination the user signs to any club); once the
    # slate commits, show the signed pros as persisted. Both carry the green badge + real STR/cost.
    _g = gender if gender in ("men", "women") else "all"
    _pro_src = world.list_pros if committed else world.pro_cohort
    pros_in = []
    for pr in _pro_src(seed, f"{w['year']}-preseason"):
        if _g != "all" and pr["gender"] != _g:
            continue
        ta, tc = crest(pr["dest_school"]) if pr.get("dest_school") else ("", "")
        pros_in.append({**pr, "to_abbr": ta, "to_color": tc})
    if committed:
        # Already applied — show the committed slate as-is (no re-resolve).
        out = []
        for m in committed:
            fa, fc = crest(m["src_school"])
            ta, tc = crest(m["dest_school"])
            p = world.find_persisted_player(m["pid"], seed)
            out.append({
                **m, "name": m.get("name") or getattr(p, "name", m["pid"]),
                "class": getattr(p, "class_year", ""), "country": getattr(p, "country", ""),
                "from_abbr": fa, "from_color": fc, "to_abbr": ta, "to_color": tc,
                "is_riser": m["cascade_from"] is None})
        out.sort(key=lambda r: (0 if r["is_riser"] else 1, -r["str"], r["pid"]))
        pg = _paginate_portal(_portal_q_filter(out, q), gender, page, per_page)
        return {"year": world.BASE_YEAR + w["year"], "raw_year": w["year"],
                "proposals": pg["page_rows"], "n": len(out), "q": (q or "").strip(),
                "riders": sum(1 for r in out if r["is_riser"]),
                "committed": len(committed), "done": True, "cap": cap, "pros_cycle": pros_cycle,
                "is_preseason": w["week"] == 0, "pros": pros_in,
                "gender": pg["gender"], "gender_counts": pg["gender_counts"],
                "page": pg["page"], "pages": pg["pages"], "pager": pg["pager"],
                "destinations": world.fall_portal_destinations(seed)}
    resolved = world.resolve_preseason_portal(seed)   # {gender: [moves]} (riders + cascades)
    out = []
    for g, moves in resolved.items():
        for m in moves:
            p = world.find_persisted_player(m["pid"], seed)
            fa, fc = crest(m["src_school"])
            ta, tc = crest(m["dest_school"])
            out.append({
                **m, "gender": g,
                "name": getattr(p, "name", m.get("name") or m["pid"]),
                "class": getattr(p, "class_year", ""),
                "country": getattr(p, "country", ""),
                "from_abbr": fa, "from_color": fc, "to_abbr": ta, "to_color": tc,
                "is_riser": m["cascade_from"] is None,
            })
    out.sort(key=lambda r: (0 if r["is_riser"] else 1, -r["str"], r["pid"]))
    # When the slate is empty, surface WHY (scan counts + the per-division bar) so an
    # unexpected 0 is explainable and the user can force a re-scan.
    debug = world.preseason_portal_debug(seed) if not out else None
    pg = _paginate_portal(_portal_q_filter(out, q), gender, page, per_page)
    return {"year": world.BASE_YEAR + w["year"], "raw_year": w["year"],
            "proposals": pg["page_rows"], "n": len(out), "q": (q or "").strip(),
            "riders": sum(1 for r in out if r["is_riser"]),
            "committed": 0, "done": False, "cap": cap, "pros_cycle": pros_cycle,
            "is_preseason": w["week"] == 0, "debug": debug, "pros": pros_in,
            "gender": pg["gender"], "gender_counts": pg["gender_counts"],
            "page": pg["page"], "pages": pg["pages"], "pager": pg["pager"],
            "destinations": world.fall_portal_destinations(seed)}


def ncaa_bracket_years(division: str, gender: str, seed: int = DEFAULT_SEED):
    """Calendar years (newest first) that have a stored NCAA bracket for this
    universe — every past world-year whose season reached the bracket. Drives the
    season picker on the bracket page; the brackets survive the rollover under
    each year's seed."""
    import app.world as world
    import app.seasonmode as sm
    if not world.exists(seed):
        return []
    cur = world.load_world(seed)["year"]
    years = []
    for idx in range(cur + 1):
        sid = sm.find_season(division, gender, seed=world.year_seed(seed, idx))
        if sid is None:
            continue
        ph = (sm.load_season(sid) or {}).get("phase")
        if ph in ("selection", "ncaa", "complete"):
            years.append(world.BASE_YEAR + idx)
    return sorted(years, reverse=True)


def ncaa_bracket_view(division: str, gender: str, seed: int = DEFAULT_SEED, year: int | None = None):
    """The ACTUAL played NCAA team bracket reconstructed from results — rounds of
    real matchups with the winner and dual score. None until the tournament has
    begun. (The /bracket page is a projection; this is what the league played.)

    `year` (calendar) selects a PAST world-year's stored bracket; default is the
    current season. Past brackets reconstruct exactly from that season's saved
    duals (seeds included, since the field is seeded from those same results)."""
    import app.world as world
    import app.seasonmode as sm
    from app import regions as _regions
    from .rankings_data import crest

    def _region_map(seeded):
        """({school: cosmetic region name}, [4 names]) for a regional field — 96
        teams (D1) or 64 (D2/D3/D4), both split into four S-curve regions."""
        if len(seeded) not in (64, 96):
            return {}, []
        names = _regions.region_names(sm.load_season(sid)["seed"])
        idx = _regions.region_index_of([p.school for p in seeded])
        return {sch: names[r] for sch, r in idx.items()}, names

    def _group_by_region(entries, region_names):
        """Four {name, teams} groups in MAIN_DRAW_ORDER (adjacent groups meet in
        the national semifinals). Entries arrive in overall-seed order, so each
        group lists its region seeds 1..N top to bottom."""
        by_rgn = {nm: [] for nm in region_names}
        for e in entries:
            by_rgn[e["region"]].append(e)
        return [{"name": region_names[r], "teams": by_rgn[region_names[r]]}
                for r in _regions.MAIN_DRAW_ORDER]
    if year is not None:
        idx = year - world.BASE_YEAR
        sid = sm.find_season(division, gender, seed=world.year_seed(seed, idx))
        if sid is None:
            return None
    else:
        sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    # Scheduled duals included: the round currently on the board is the answer to
    # "who do they play if they win", so an unplayed cell belongs on the bracket.
    rows = sm.ncaa_duals(sid)
    if not rows:
        # Bracket reveal: the field is locked but no NCAA match has been played.
        phase = sm.load_season(sid).get("phase")
        if phase in ("selection", "ncaa"):
            seeded, autobids, out_board, _r = sm.ncaa_field(sid)
            region_of, region_names = _region_map(seeded)
            field = []
            for i, p in enumerate(seeded, 1):
                ab, col = crest(p.school)
                # Regional fields carry the REGION seed (the S-curve seed line:
                # 1–24 in a 96 field, 1–16 in a 64) — the overall committee rank
                # is only the input to the split, not the displayed seed.
                rseed = (i - 1) // 4 + 1 if region_names else i
                field.append({"seed": rseed, "school": p.school, "abbr": ab, "color": col,
                              "conf": getattr(p, "conf_abbr", ""),
                              "aq": p.key in autobids, "region": region_of.get(p.school)})
            field_regions = _group_by_region(field, region_names) if region_names else []
            snubs = []
            for o in out_board:
                ab, col = crest(o["school"])
                snubs.append({**o, "abbr": ab, "color": col})
            return {"reveal": True, "field": field, "field_regions": field_regions,
                    "size": len(field),
                    "n_aq": len(autobids), "out_board": snubs, "regions": region_names,
                    "rounds": [], "champion": None, "complete": False}
        return None
    # Seed / conference / bid context — the field is locked for the whole
    # postseason, so the same seeding the bracket was drawn from labels every team
    # (so you can see who the seeds were and trace a seed's path round to round).
    seed_map, conf_map, aq_set = {}, {}, set()
    region_of, region_names = {}, []
    top_seeds, seed_regions = [], []
    try:
        seeded, autobids, _out, _r = sm.ncaa_field(sid)
        region_of, region_names = _region_map(seeded)
        for i, p in enumerate(seeded, 1):
            # Region seed (S-curve line) on regional fields; overall rank otherwise.
            seed_map[p.school] = (i - 1) // 4 + 1 if region_names else i
            conf_map[p.school] = getattr(p, "conf_abbr", "")
            if p.key in autobids:
                aq_set.add(p.school)
            if i <= 16:
                ab, col = crest(p.school)
                top_seeds.append({"seed": seed_map[p.school], "school": p.school,
                                  "abbr": ab, "color": col,
                                  "conf": getattr(p, "conf_abbr", ""), "aq": p.key in autobids,
                                  "region": region_of.get(p.school)})
        if region_names:
            seed_regions = _group_by_region(top_seeds, region_names)
    except Exception:
        pass

    def _team(school, abbr, color, won):
        return {"school": school, "abbr": abbr, "color": color, "won": won,
                "seed": seed_map.get(school), "conf": conf_map.get(school, ""),
                "aq": school in aq_set, "region": region_of.get(school)}

    by_round: dict = {}
    for r in rows:
        by_round.setdefault(r["round_no"], []).append(r)
    # Region display order: the same order the main draw is laid out in, so reading
    # the four groups top to bottom follows the halves into the national semifinals.
    draw_order = [region_names[r] for r in _regions.MAIN_DRAW_ORDER] if region_names else []
    rounds = []
    for rno in sorted(by_round):
        matchups = []
        for r in sorted(by_round[rno], key=lambda x: x["bpos"]):
            hp, ap = r["home_points"], r["away_points"]
            played = r["winner"] is not None
            home_won = played and r["winner"] == 0
            ha, hc = crest(r["home"]); aa, ac = crest(r["away"])
            home = _team(r["home"], ha, hc, home_won)
            away = _team(r["away"], aa, ac, played and not home_won)
            matchups.append({
                "home": home, "away": away, "played": played, "bpos": r["bpos"],
                "id": r["id"],
                # A dual belongs to a region until the regions meet: every round
                # through the regional final is inside one, the national semifinals
                # and final are not (both sides carry different region labels).
                "region": home["region"] if home["region"] == away["region"] else None,
                "home_won": home_won,
                "winner": (r["home"] if home_won else r["away"]) if played else None,
                "score": f"{max(hp, ap)}-{min(hp, ap)}" if played and hp is not None else "",
            })
        # A round goes NATIONAL once the regions meet — the semifinals and the final.
        # Every earlier round sits inside one region, and belongs to its tree.
        rounds.append({"name": by_round[rno][0]["conf"], "matchups": matchups,
                       "national": not (draw_order and all(m["region"] for m in matchups))})
    champion = None
    if rounds and len(rounds[-1]["matchups"]) == 1 and rounds[-1]["matchups"][0]["played"]:
        m = rounds[-1]["matchups"][0]
        win = m["home"] if m["home_won"] else m["away"]
        champion = {"school": win["school"], "abbr": win["abbr"], "color": win["color"],
                    "seed": win["seed"]}
    ladders = _region_ladders(rounds, draw_order)
    return {"rounds": rounds, "champion": champion, "top_seeds": top_seeds,
            "seed_regions": seed_regions,
            "region_size": max(seed_map.values(), default=0) if region_names else 0,
            "ladders": ladders,
            "national": _bracket_canvas([r for r in rounds if r["national"]]) if ladders else None,
            "regions": region_names, "complete": champion is not None}


CARD_H = 62           # matchup card height (two team rows)
CARD_W = 216          # matchup card width
GUTTER = 52           # horizontal space between a column and the next — the elbow gutter
LEAF_GAP = 16         # vertical gap between two adjacent first-round cards
PAD_Y = 8


def _bracket_canvas(cols: list, *, card_w: int = CARD_W, card_h: int = CARD_H,
                    gutter: int = GUTTER, leaf_gap: int = LEAF_GAP) -> dict | None:
    """Lay a list of rounds out as an ELIMINATION TREE on one coordinate canvas.

    Positions come from the tree, not from document flow: the widest full round is
    the leaf row (evenly spaced), and every later matchup is centred on the average
    of the two feeders it receives — so a card always sits between the two cards
    that can send it a team. A play-in column (same width as the round it feeds,
    one source per destination) is laid out level with its destination.

    Returns the canvas the template renders: card boxes with x/y, column headers,
    and the SVG elbow paths (source right edge → mid-gutter → target y → target
    left edge) that make the parent-child relationship visible. Cards and paths
    share this one coordinate system, so nothing can drift out of alignment.

    The geometry is overridable so a SMALL tree can use smaller cards (the Preseason
    NIT lays sixteen four-team Kickoff sites side by side); the defaults are the
    NCAA bracket's. Everything scales off these four numbers, so a caller never has
    to touch CSS to change the size — which would break the shared coordinates."""
    cols = [c for c in cols if c["matchups"]]
    if not cols:
        return None
    widest = max(len(c["matchups"]) for c in cols)
    base = max(i for i, c in enumerate(cols) if len(c["matchups"]) == widest)
    stride = card_h + leaf_gap
    centres: list[list[float]] = [[] for _ in cols]
    centres[base] = [PAD_Y + i * stride + card_h / 2 for i in range(widest)]
    for i in range(base + 1, len(cols)):                       # rightwards: average the feeders
        prev, cur = centres[i - 1], cols[i]["matchups"]
        centres[i] = [(prev[2 * k] + prev[2 * k + 1]) / 2 if 2 * k + 1 < len(prev)
                      else prev[min(2 * k, len(prev) - 1)] for k in range(len(cur))]
    for i in range(base - 1, -1, -1):                          # leftwards: play-in sits level
        nxt = centres[i + 1]
        centres[i] = [nxt[k] if k < len(nxt) else PAD_Y + k * stride + card_h / 2
                      for k in range(len(cols[i]["matchups"]))]

    cards, columns, links = [], [], []
    for i, col in enumerate(cols):
        x = i * (card_w + gutter)
        columns.append({"name": col["name"], "x": x, "n": len(col["matchups"]),
                        "playin": i < base})
        for k, m in enumerate(col["matchups"]):
            cards.append({**m, "x": x, "y": centres[i][k] - card_h / 2,
                          "round": col["name"], "col": i, "slot": k, "playin": i < base})
        if i == 0:
            continue
        prev_col, prev_c = cols[i - 1]["matchups"], centres[i - 1]
        px = (i - 1) * (card_w + gutter) + card_w
        mid = px + gutter / 2
        # One source per destination (a play-in feeding its slot) or two (the
        # normal halving); either way the destination is fixed by the tree.
        pairs = ([(k, [k]) for k in range(len(col["matchups"]))]
                 if len(prev_col) == len(col["matchups"])
                 else [(k, [2 * k, 2 * k + 1]) for k in range(len(col["matchups"]))])
        for k, sources in pairs:
            for s in sources:
                if s >= len(prev_col):
                    continue
                src, dst = prev_col[s], col["matchups"][k]
                y0, y1 = prev_c[s], centres[i][k]
                links.append({
                    "d": f"M {px} {y0:.1f} H {mid} V {y1:.1f} H {x}",
                    # A path is live once the feeder has produced a winner that is
                    # standing in the destination card.
                    "won": bool(src["winner"]) and src["winner"] in
                           (dst["home"]["school"], dst["away"]["school"]),
                    "school": src["winner"] or "",
                })
    height = max((c["y"] + card_h for c in cards), default=0) + PAD_Y
    return {"cards": cards, "columns": columns, "links": links,
            "width": len(cols) * (card_w + gutter) - gutter,
            "height": height, "card_w": card_w, "card_h": card_h}


def _region_ladders(rounds: list, draw_order: list) -> list:
    """The played bracket as FOUR REGION LADDERS — a real bracket tree per region:
    `[{name, rounds: [{name, matchups}, …]}]`, each round half the size of the one
    before it, matchups ordered so match `i` of a round feeds match `i // 2` of the
    next. Rendered as columns that halve, that reads as an actual bracket: you can
    see who a winner meets next instead of hunting two columns over.

    The one hop that ISN'T positional is the 96-field opening round into the Round
    of 64 — the bracketer swaps which play-in winner faces which bye to dodge a
    rematch — so that column is reordered by the game its winner actually fed."""
    if not draw_order:
        return []
    ladders = []
    for name in draw_order:
        cols = []
        for rnd in rounds:
            got = [m for m in rnd["matchups"] if m["region"] == name]
            if got:
                cols.append({"name": rnd["name"], "matchups": got})
        if not cols:
            continue
        # Opening round (same width as the round it feeds) → align by who fed whom.
        if len(cols) > 1 and len(cols[0]["matchups"]) == len(cols[1]["matchups"]):
            feeds = {}
            for i, m in enumerate(cols[1]["matchups"]):
                feeds.setdefault(m["home"]["school"], i)
                feeds.setdefault(m["away"]["school"], i)
            cols[0]["matchups"].sort(
                key=lambda m: feeds.get(m["winner"], len(feeds) + m["bpos"]))
        final = cols[-1]["matchups"][0] if len(cols[-1]["matchups"]) == 1 else None
        ladders.append({"name": name, "rounds": cols, "canvas": _bracket_canvas(cols),
                        "champion": (final["home"] if final["home_won"] else final["away"])
                        if final and final["played"] else None})
    return ladders


# --------------------------------------------------------------------------
# Preseason NIT (the ITA opener) — the SAME elimination tree as the NCAAs
# --------------------------------------------------------------------------
# The NIT has exactly the NCAA bracket's shape, one tier down: a four-team Kickoff
# site is a region (a little ladder that sends one team on), and the National Team
# Indoor is the main draw those ladders feed — so it renders through the same
# server-positioned `_bracket_canvas`, the same cards and the same SVG elbows.
#
# Seeds are read back off the DRAW THAT WAS PERSISTED, never re-derived from a live
# ranking: a site's two openers are 1v4 / 2v3 by construction, and the Indoor's
# round-1 slots are the standard seed positions. That's the same rule that keeps the
# NCAA bracket's labels from drifting (docs/AAR-ncaa-bracket-region-drift.md) — the
# ITA seeding input (`_ita_ranking`) is a live Power Index that keeps moving all
# season, so reading it again would relabel a bracket that was drawn in week 1.

NIT_SITE_CARD_W = 232     # a four-team site is a small tree — two sites sit side by side
NIT_SITE_GUTTER = 44      # (2 × card + gutter = the `.brk-grid` column min-width)


def _nit_tbd_match(bpos: int = 0) -> dict:
    """A placeholder card for a round that hasn't been drawn yet. The draw only
    writes a round once its feeders have played, so without these the bracket would
    stop dead at the round on the board — you could never see the shape of the tree
    you're playing into. Carries the same keys as a real matchup so the canvas
    positions it identically; `tbd` tells the template to render it empty."""
    blank = {"school": "", "abbr": "", "color": "", "won": False, "seed": None,
             "conf": "", "aq": False, "tbd": True}
    return {"home": dict(blank), "away": dict(blank), "played": False, "bpos": bpos,
            "id": None, "region": None, "home_won": False, "winner": None,
            "score": "", "tbd": True}


def _nit_pad(cols: list, namer) -> list:
    """Extend a partly-drawn ladder with the rounds it still has to play, as TBD
    cards, so the whole tree is visible from the moment the draw is made."""
    out = list(cols)
    while out and len(out[-1]["matchups"]) > 1:
        alive = len(out[-1]["matchups"])         # feeders → teams alive in the next round
        out.append({"name": namer(alive),
                    "matchups": [_nit_tbd_match(k) for k in range(alive // 2)]})
    return out


def ita_bracket_years(division: str, gender: str, seed: int = DEFAULT_SEED) -> list[int]:
    """Calendar years (newest first) whose Preseason NIT has been drawn — the season
    picker on the NIT page. Past openers reconstruct exactly from that season's saved
    duals, seeds included (the draw itself carries the seeding)."""
    import app.world as world
    import app.seasonmode as sm
    if not world.exists(seed):
        return []
    cur = world.load_world(seed)["year"]
    years = []
    for idx in range(cur + 1):
        sid = sm.find_season(division, gender, seed=world.year_seed(seed, idx))
        if sid is None:
            continue
        if sm.ita_view(sid):
            years.append(world.BASE_YEAR + idx)
    return sorted(years, reverse=True)


def ita_bracket_view(division: str, gender: str, seed: int = DEFAULT_SEED,
                     year: int | None = None):
    """The Preseason NIT as a real bracket: the Kickoff Weekend sites as four-team
    ladders and the National Team Indoor as the draw they feed, both laid out on the
    NCAA bracket's coordinate canvas. None before the opener is drawn.

    `year` (calendar) selects a past world-year's opener; default is this season."""
    import app.world as world
    import app.seasonmode as sm
    from app import ita as ita_fmt
    from app.bracket import _seed_positions
    from app.ncaa import load_division
    from .rankings_data import crest

    if year is not None:
        sid = sm.find_season(division, gender, seed=world.year_seed(seed, year - world.BASE_YEAR))
        if sid is None:
            return None
    else:
        sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    view = sm.ita_view(sid)
    if not view:
        return None
    conf_of = {p.school: p.conf_abbr for p in load_division(division, gender).programs}

    def _team(school, won, seeds):
        ab, col = crest(school)
        return {"school": school, "abbr": ab, "color": col, "won": won,
                "seed": seeds.get(school), "conf": conf_of.get(school, ""),
                "aq": False, "tbd": False}

    def _match(r, seeds):
        hp, ap = r["home_points"], r["away_points"]
        played = r["winner"] is not None
        home_won = played and r["winner"] == 0
        return {"home": _team(r["home"], home_won, seeds),
                "away": _team(r["away"], played and not home_won, seeds),
                "played": played, "bpos": r["bpos"], "id": r["id"], "region": None,
                "home_won": home_won, "tbd": False,
                "winner": (r["home"] if home_won else r["away"]) if played else None,
                "score": f"{max(hp, ap)}-{min(hp, ap)}" if played and hp is not None else ""}

    # --- Kickoff sites: a four-team ladder each, seeded 1–4 by the draw ----------
    sites = []
    for site in view["sites"]:
        semis = sorted(site["semis"], key=lambda r: r["bpos"])
        # `ita.site_pairs` draws (1 v 4) then (2 v 3), in bpos order — so the pairing
        # IS the seed line. Read it straight off rather than re-ranking.
        seeds = {}
        for i, r in enumerate(semis):
            seeds.setdefault(r["home"], 1 + i)
            seeds.setdefault(r["away"], 4 - i)
        cols = [{"name": "Site Semifinals", "matchups": [_match(r, seeds) for r in semis]}]
        if site["final"]:
            cols.append({"name": "Site Final", "matchups": [_match(site["final"], seeds)]})
        final = site["final"]
        champ = None
        if final and final["winner"] is not None:
            champ = _team(final["home"] if final["winner"] == 0 else final["away"], True, seeds)
        sites.append({
            "name": site["label"], "host": semis[0]["home"] if semis else "",
            "champion": champ,
            "teams": [_team(s, False, seeds) for s in sorted(seeds, key=seeds.get)],
            "canvas": _bracket_canvas(_nit_pad(cols, lambda _alive: "Site Final"),
                                      card_w=NIT_SITE_CARD_W, gutter=NIT_SITE_GUTTER),
        })

    # --- The Indoor: one seeded single-elim, the NCAA main draw in miniature -----
    size = ita_fmt.indoor_size(division)
    rounds = view["indoor"]
    iseeds: dict = {}
    if rounds:
        r1 = sorted(rounds[0]["duals"], key=lambda r: r["bpos"])
        pos = _seed_positions(2 * len(r1))       # slot i of the round-1 order holds seed pos[i]
        for k, r in enumerate(r1):
            iseeds.setdefault(r["home"], pos[2 * k])
            iseeds.setdefault(r["away"], pos[2 * k + 1])
    icols = [{"name": rnd["name"],
              "matchups": [_match(r, iseeds) for r in sorted(rnd["duals"], key=lambda x: x["bpos"])]}
             for rnd in rounds]
    if not icols:
        # Drawn Kickoff, no Indoor yet: show the empty draw the sites are playing for.
        icols = [{"name": sm._round_name(size),
                  "matchups": [_nit_tbd_match(k) for k in range(size // 2)]}]
    indoor = _bracket_canvas(_nit_pad(icols, sm._round_name))

    champion = None
    if view["indoor_champion"]:
        champion = _team(view["indoor_champion"], True, iseeds)
    field = [_team(s, False, iseeds) for s in sorted(iseeds, key=iseeds.get)]
    return {"phase": view["phase"], "champion": champion, "sites": sites,
            "indoor": indoor, "indoor_field": field, "indoor_size": size,
            "runs_kickoff": ita_fmt.runs_kickoff(division),
            "complete": champion is not None}


def teams_by_conference(division: str, gender: str, conf_filter: str = "All"):
    from .rankings_data import crest
    rows = ranking_rows(division, gender)
    groups: dict[str, list] = {}
    for r in rows:
        if conf_filter != "All" and r.conf != conf_filter:
            continue
        abbr, color = crest(r.school)
        groups.setdefault(r.conf, []).append(
            {"school": r.school, "abbr": abbr, "color": color, "pi": r.pi,
             "rec": r.rec, "tier": r.tier})
    return sorted(groups.items())


_staff_cache: dict = {}


def coaching_staff(division: str, gender: str, school: str):
    from app import coachgen
    import app.coachreg as coachreg
    import app.world as world
    # Key the cache by the coach-registry generation (and the world salt/year), so a
    # world reset / New League — which wipes the registry — invalidates stale staff
    # rather than serving coach ids the registry no longer knows.
    w = world.load_world()
    yr = w["year"] if w else 0
    salt = (w.get("salt") or "") if w else ""
    key = (coachreg.generation(), salt, division, gender, school, yr)
    if key in _staff_cache:
        return _staff_cache[key]
    staff = []
    for role in ("head", "assoc", "asst"):
        r = coachgen.ensure(division, gender, school, role)
        if r is None:                       # retired/empty seat — show it as vacant
            staff.append({"coach_id": None, "name": "Vacant", "vacant": True,
                          "title": coachgen.ROLE_TITLES[role], "role": role,
                          "archetype": "", "tenure": 0, "dev": 0, "rec": 0, "tac": 0})
            continue
        staff.append({"coach_id": r["coach_id"], "name": r["name"], "vacant": False,
                      "title": coachgen.ROLE_TITLES[role], "role": role,
                      "archetype": r["archetype"], "tenure": r["tenure"],
                      "dev": r["dev"], "rec": r["rec"], "tac": r["tac"]})
    _staff_cache[key] = staff
    return staff


def head_coach(division: str, gender: str, school: str) -> dict | None:
    for s in coaching_staff(division, gender, school):
        if s["role"] == "head":
            return s if s.get("coach_id") else None    # None when the seat is vacant
    return None


_STAFF_DIVS = ("D1", "D2", "D3", "D4")
_uni_staff_cache: dict = {}


def coach_overall(dev: int, rec: int, tac: int) -> int:
    """A single 20–80 'current ability' for a coach — the mean of the three
    surfaced pillars (development / recruiting / tactics). Simple and legible; the
    per-pillar columns show the actual profile."""
    return round((dev + rec + tac) / 3.0)


def _universe_staff(division: str, gender: str) -> list[dict]:
    """Every coach seat in one division×gender as flat rows, built with the
    division loaded ONCE (skips the per-seat load_division that dominates a full
    enumeration). Cached per world snapshot / registry generation."""
    from app import coachgen
    import app.coachreg as coachreg
    import app.world as world
    from app.ncaa import load_division
    w = world.load_world()
    yr = w["year"] if w else 0
    salt = (w.get("salt") or "") if w else ""
    key = (coachreg.generation(), salt, division, gender, yr)
    cached = _uni_staff_cache.get(key)
    if cached is not None:
        return cached
    try:
        div = load_division(division, gender)
    except FileNotFoundError:
        _uni_staff_cache[key] = []
        return []
    rows: list[dict] = []
    for prog in div.programs:
        for role in ("head", "assoc", "asst"):
            r = coachgen.ensure(division, gender, prog.school, role, prog=prog)
            if r is None:                       # vacant seat — skip in the search pool
                continue
            dev, rec, tac = r["dev"], r["rec"], r["tac"]
            rows.append({
                "coach_id": r["coach_id"], "name": r["name"], "school": prog.school,
                "division": division, "gender": gender, "role": role,
                "title": coachgen.ROLE_TITLES[role], "archetype": r["archetype"],
                "home_country": r.get("home_country", ""), "tenure": r["tenure"],
                "dev": dev, "rec": rec, "tac": tac, "overall": coach_overall(dev, rec, tac),
            })
    _uni_staff_cache[key] = rows
    return rows


def staff_search(gender: str = "men", division: str = "All", role: str = "both",
                 sort: str = "overall", q: str = "") -> dict:
    """Football-Manager-style staff search across the world's coaching seats.
    `role`: 'head' | 'assistant' (assoc + asst) | 'both'. Sort by overall or any
    pillar (dev/rec/tac) or tenure. `q` matches name / school / country / archetype.

    Returns {rows, hc_bar} where hc_bar is the median HEAD-coach overall in scope —
    an assistant at/above it is flagged 'hc_ready' (ready to run a program), which
    is the whole point: spot assistants primed for a head job.
    """
    divisions = _STAFF_DIVS if division == "All" else (division,)
    genders = ("men", "women") if gender == "all" else (gender,)
    pool: list[dict] = []
    for d in divisions:
        for g in genders:
            pool.extend(_universe_staff(d, g))

    # Head-coach benchmark from the FULL in-scope head pool (before the role filter),
    # so "ready" means "as good as the median sitting head coach at this level".
    head_ovr = sorted(r["overall"] for r in pool if r["role"] == "head")
    hc_bar = head_ovr[len(head_ovr) // 2] if head_ovr else 0

    if role == "head":
        rows = [r for r in pool if r["role"] == "head"]
    elif role == "assistant":
        rows = [r for r in pool if r["role"] in ("assoc", "asst")]
    else:
        rows = list(pool)
    if q:
        ql = q.strip().lower()
        rows = [r for r in rows if ql in r["name"].lower() or ql in r["school"].lower()
                or ql in (r["home_country"] or "").lower() or ql in (r["archetype"] or "").lower()]
    for r in rows:
        r["hc_ready"] = r["role"] in ("assoc", "asst") and r["overall"] >= hc_bar

    keys = {
        "overall": lambda r: (r["overall"], r["dev"] + r["rec"] + r["tac"]),
        "dev": lambda r: r["dev"], "rec": lambda r: r["rec"], "tac": lambda r: r["tac"],
        "tenure": lambda r: r["tenure"],
        "name": lambda r: r["name"].lower(),
    }
    rev = sort != "name"
    rows.sort(key=keys.get(sort, keys["overall"]), reverse=rev)
    return {"rows": rows, "hc_bar": hc_bar}


def get_coach(coach_id: str) -> dict | None:
    import app.coachreg as coachreg
    c = coachreg.get(coach_id)
    if not c or not c.get("school"):
        return c
    c["role_label"] = {"head": "Head Coach", "assoc": "Associate Head Coach",
                       "asst": "Assistant Coach"}.get(c.get("role"), "Coach")
    rec = team_results(c["division"], c["gender"], c["school"])
    c["team_w"], c["team_l"] = rec["wins"], rec["losses"]
    return c


def editor_roster(division: str, gender: str, school: str):
    from app import ncaa, overrides as ov
    from .rankings_data import crest
    div = ncaa.load_division(division, gender)
    prog = div.by_school(school)
    if prog is None:
        return None, None
    roster = ncaa.build_roster(prog)
    base_pids = {pr.pid for pr in ncaa._base_roster(prog)}
    rows = []
    for i, pr in enumerate(roster, 1):
        rows.append({
            "pid": pr.pid, "name": pr.name,
            "class_year": getattr(pr, "class_year", ""),
            "overall": round(pr.current_overall(), 1),
            "str": round(pr.str_value(), 1),
            "line": i if i <= ncaa.lineup_size(division) else None,
            "walk_on": getattr(pr, "walk_on", False),
            "moved_in": pr.pid not in base_pids,
            "hometown": getattr(pr, "hometown", ""),
        })
    abbr, color = crest(school)
    return rows, {"school": school, "abbr": abbr, "color": color}


def all_programs_grouped(gender=None):
    """Programs grouped by universe (label, [schools]) for the editor MOVE picker.

    Pass `gender` ("men"/"women") to restrict to that gender only — a women's
    player must never be movable onto a men's roster, and vice versa. The result
    still spans every division of that gender (cross-division moves are intended),
    so a women's editor sees "D1 Women / D2 Women / …", never any men's program.
    """
    from app import ncaa
    out = []
    for val, division, g, label in UNIVERSES:
        if gender and g != gender:
            continue
        try:
            div = ncaa.load_division(division, g)
        except FileNotFoundError:
            continue
        out.append((label, sorted(p.school for p in div.programs)))
    return out


def all_programs_by_universe():
    """Every program grouped by universe, keeping division + gender — so a coach
    can be moved to ANY program in ANY division/gender. Each entry:
    (division, gender, label, [schools])."""
    from app import ncaa
    out = []
    for _val, division, gender, label in UNIVERSES:
        try:
            div = ncaa.load_division(division, gender)
        except FileNotFoundError:
            continue
        out.append((division, gender, label, sorted(p.school for p in div.programs)))
    return out


def coach_move_tree():
    """Nested {gender: [{div, conf, schools:[...]}, ...]} powering the coach-move
    cascade — pick Gender → Conference → an alphabetical school list, instead of
    one dropdown of every program in the world. Ordered by division then
    conference; schools sorted within a conference."""
    out: dict[str, list] = {"men": [], "women": []}
    for _val, division, gender, _label in UNIVERSES:
        try:
            groups = conference_schools(division, gender)   # [(conf, [schools sorted])]
        except FileNotFoundError:
            continue
        for conf, schools in groups:
            out.setdefault(gender, []).append(
                {"div": division, "conf": conf, "schools": schools})
    return out


def active_overrides():
    from app import ncaa, overrides as ov
    moves = []
    for pid, dest in sorted(ov.get_moves().items(), key=lambda kv: kv[1]):
        pr = ncaa.player_by_pid(pid)
        moves.append({"pid": pid, "name": pr.name if pr else pid,
                      "str": round(pr.str_value(), 1) if pr else "—", "dest": dest})
    lineups = [{"school": s, "n": len(pids)} for s, pids in sorted(ov.get_lineups().items())]
    doubles = [{"school": s, "n": len(pids) // 2} for s, pids in sorted(ov.get_doubles().items())]
    prestige = [{"school": s, "value": round(v * 100)}
                for s, v in sorted(ov.get_prestige().items())]
    academics = [{"school": s, "value": round(v * 100)}
                 for s, v in sorted(ov.get_academics().items())]
    conf_prestige = [{"conf": c, "value": round(v * 100)}
                     for c, v in sorted(ov.get_conf_prestige().items())]
    conf_academics = [{"conf": c, "value": round(v * 100)}
                      for c, v in sorted(ov.get_conf_academics().items())]
    return {"moves": moves, "lineups": lineups, "doubles": doubles, "prestige": prestige,
            "academics": academics, "conf_prestige": conf_prestige,
            "conf_academics": conf_academics,
            "any": bool(moves or lineups or doubles or prestige or academics
                        or conf_prestige or conf_academics)}


def team_results(division: str, gender: str, school: str, seed: int = DEFAULT_SEED):
    from .rankings_data import crest
    import app.world as world
    import app.seasonmode as sm
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    out = []
    wins = losses = 0
    for d in sm.team_schedule(sid, school):
        if d["status"] != "final":
            continue
        is_home = d["home"] == school
        opp = d["away"] if is_home else d["home"]
        won = (d["winner"] == 0) if is_home else (d["winner"] == 1)
        mine = d["home_points"] if is_home else d["away_points"]
        theirs = d["away_points"] if is_home else d["home_points"]
        wins += won
        losses += not won
        abbr, color = crest(opp)
        out.append({"id": d["id"], "opp": opp, "abbr": abbr, "color": color,
                    "home": is_home, "won": won, "mine": mine, "theirs": theirs,
                    "conf": bool(d["is_conf"]), "round": d["round"],
                    "postseason": d["round"] in ("CT", "NCAA")})
    return {"results": out, "wins": wins, "losses": losses}


def program_history(division: str, gender: str, school: str, seed: int = DEFAULT_SEED) -> dict:
    """A program's season-by-season history (newest first) and aggregated program
    honors, across every world-year of this universe that has results."""
    import app.world as world
    import app.seasonmode as sm
    w = world.load_world(seed)
    base = w["seed"] if w else seed
    cur_year = w["year"] if w else 0
    seasons = []
    for y in range(cur_year + 1):
        ysid = sm.find_season(division, gender, seed=world.year_seed(base, y))
        if ysid is None:
            continue
        row = sm.season_program_result(ysid, school)
        if not row:
            continue
        row["year"] = 2026 + y
        row["season_no"] = y + 1
        seasons.append(row)
    seasons.reverse()                                  # newest first

    def years(pred):
        return [s["year"] for s in seasons if pred(s)]

    honors = {
        "national_titles": years(lambda s: s["national_champ"]),
        "regional_titles": years(lambda s: s.get("regional_champ")),
        "indoor_titles": years(lambda s: s["indoor_champ"]),
        "reg_conf_titles": years(lambda s: s["reg_conf_champ"]),
        "ct_titles": years(lambda s: s["ct_champ"]),
        "ncaa_appearances": [{"year": s["year"], "round": s["ncaa"]} for s in seasons if s["ncaa"]],
        "ita_appearances": [{"year": s["year"], "round": s["ita"]} for s in seasons if s["ita"]],
    }
    honors["division"] = division
    honors["any"] = any(honors[k] for k in honors if k != "division")
    return {"seasons": seasons, "honors": honors}


def player_career(division: str, gender: str, pid: str, seed: int = DEFAULT_SEED):
    import app.world as world
    import app.seasonmode as sm
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    yr = world.load_world(seed)["year"] if world.exists(seed) else 0

    log = sm.player_log(sid, pid)
    w = sum(1 for m in log if m["won"])
    l = len(log) - w
    groups = [{"year": 2026 + yr, "season_no": yr + 1, "log": log, "w": w, "l": l}] if log else []
    return groups, (w, l)


def _pos_label(line) -> str:
    """Lineup slot shown as stored (e.g. 'S2' / 'D1'); blank -> em dash."""
    return str(line) if line else "—"


def player_career_table(division: str, gender: str, pid: str, seed: int = DEFAULT_SEED):
    """Season-by-season college career, newest first: the team played for that
    year (transfers visible), class, primary singles line, record, STR, and that
    season's accomplishments. Past seasons come from the player's recorded
    history (stamped at each year's end); the in-progress current season is added
    live so the card is current before the year closes."""
    import app.world as world
    import app.seasonmode as sm
    import app.honors as honors
    from .rankings_data import crest

    p = world.find_persisted_player(pid, seed)
    hist = list(getattr(p, "history", []) or []) if p else []
    hbyyear = {g["year"]: [a["label"] for a in g["awards"]]
               for g in honors.career_by_year(pid, "player")}

    rows = []
    for h in hist:
        cal = world.BASE_YEAR + h["year"]
        rows.append({
            "cal_year": cal, "season_no": h.get("season_no", h["year"] + 1),
            "school": h["school"], "division": h.get("division", division),
            "class": h.get("class", ""), "line": h.get("line"),
            "w": h.get("w", 0), "l": h.get("l", 0), "str": h.get("str"),
            "accolades": hbyyear.get(cal, []), "live": False,
            "stint": h.get("stint", 0), "phase": h.get("phase", "full"),
        })

    # In-progress current season. A fall-portal mover already has their ITA stint
    # (stint 0) recorded for this year; we still want the live destination stint
    # (stint 1) shown, so the guard keys on the destination stint, not the year.
    wld = world.load_world(seed)
    cur = wld["year"] if wld else 0
    if not any(h.get("year") == cur and h.get("stint", 0) == 1 for h in hist):
        sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
        info = sm.player_info(sid, pid)
        if info:
            w_, l_ = sm.player_records(sid).get(pid, (0, 0))
            strv = sm.season_player_str(sid).get(pid, (None, 0.0))[0]
            cal = world.BASE_YEAR + cur
            rows.append({
                "cal_year": cal, "season_no": cur + 1, "school": info["school"],
                "division": division, "class": info.get("class", ""),
                "line": sm.player_primary_lines(sid).get(pid),
                "w": w_, "l": l_, "str": round(strv, 1) if strv else None,
                "accolades": hbyyear.get(cal, []), "live": True,
                "stint": 1, "phase": "regular_post",
            })
            # If they've MOVED this season (current school != where they started) and
            # it isn't already shown as a fall-portal two-stint, surface the origin
            # school so the transfer is visible now — not just after the year closes.
            already_split = any(h.get("year") == cur and h.get("stint", 0) == 0 for h in hist)
            origin_school, origin_div = world.persisted_team(pid, seed)
            if origin_school and origin_school != info["school"] and not already_split:
                rows.append({
                    "cal_year": cal, "season_no": cur + 1, "school": origin_school,
                    "division": origin_div or division, "class": info.get("class", ""),
                    "line": None, "w": None, "l": None, "str": None,
                    "accolades": [], "live": False, "stint": 0, "phase": "transfer_out",
                    "transferred": True,
                })

    # Newest first, and within a split season the CURRENT school (higher stint) on
    # top with the school they came from below — a transfer reads top-to-bottom.
    rows.sort(key=lambda r: (-r["cal_year"], -r.get("stint", 0)))
    # Final CTA rankings earned each year (stamped when that season's conference
    # tournaments ended) — "#12" singles, "D#5" doubles. The current season fills
    # in the moment its final board is stamped.
    from app import rankings_archive
    finals: dict[int, list[str]] = {}
    for fr in rankings_archive.player_final_ranks(pid):
        tag = f"#{fr['rk']}" if fr["board"] == "singles" else f"D#{fr['rk']}"
        finals.setdefault(fr["year"], []).append(tag)
    for r in rows:
        r["abbr"], r["color"] = crest(r["school"])
        r["pos"] = _pos_label(r["line"])
        r["cta"] = " · ".join(finals.get(r["cal_year"], []))
    return rows


def player_ranks(division: str, gender: str, pid: str, seed: int = DEFAULT_SEED) -> dict | None:
    """The player's STR (results-based, fluctuating) with national / conference /
    team ranks — the at-a-glance header (like the recruiting sites' NATL/POS/ST
    boxes). Ranked on STR, the performance metric. Players with no results yet sit
    at their ability prior (the seed converge_ids blends toward), so early-season
    ranks ≈ talent and shift as matches accrue."""
    import app.seasonmode as sm
    import app.world as world
    from app.ncaa import load_division, build_roster
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    strmap = sm.season_player_str(sid)
    progs = load_division(division, gender).programs
    entries = []                                          # (pid, str, school, conf, conf_abbr)
    for p in progs:
        for pr in build_roster(p):
            s = strmap.get(pr.pid, (pr.str_value(), 0.0))[0]
            entries.append((pr.pid, s, p.school, p.conf, p.conf_abbr))
    if not any(e[0] == pid for e in entries):
        return None
    entries.sort(key=lambda e: (-e[1], e[0]))
    def rank_in(subset):
        return (next(i for i, e in enumerate(subset) if e[0] == pid) + 1, len(subset))
    me = next(e for e in entries if e[0] == pid)
    natl_rk, natl_n = rank_in(entries)
    conf_rk, conf_n = rank_in([e for e in entries if e[3] == me[3]])
    team_rk, team_n = rank_in([e for e in entries if e[2] == me[2]])
    return {"str": round(me[1], 1), "division": division,
            "natl": natl_rk, "natl_total": natl_n,
            "conf": conf_rk, "conf_total": conf_n, "conf_name": me[3], "conf_abbr": me[4],
            "team": team_rk, "team_total": team_n}


def player_journey(division: str, gender: str, pid: str, seed: int = DEFAULT_SEED) -> list[dict]:
    """The player's path (newest first), badged like a recruiting-site 'Journey':
    the current school (CURRENT), every prior program (TRANSFER), and their high
    school (HIGH SCHOOL, carrying the recruit stars). Built from the career table so
    a mid-season move — editor or portal — shows up immediately, not just at year-end.
    Collapses consecutive same-school years into one stop."""
    import app.world as world
    import app.seasonmode as sm
    from .rankings_data import crest
    rows = player_career_table(division, gender, pid, seed)
    chrono = sorted(rows, key=lambda r: (r["cal_year"], r.get("stint", 0)))   # oldest first
    stops: list[dict] = []
    for r in chrono:
        sch = r["school"]
        if stops and stops[-1]["school"] == sch:
            stops[-1]["end"] = r["cal_year"]
        else:
            stops.append({"school": sch, "division": r.get("division", division),
                          "start": r["cal_year"], "end": r["cal_year"]})
    out = []
    for i, st in enumerate(stops):
        abbr, color = crest(st["school"])
        yrs = (str(st["start"]) if st["start"] == st["end"]
               else f"{st['start']}–{st['end']}")
        out.append({"school": st["school"], "division": st["division"],
                    "badge": "current" if i == len(stops) - 1 else "transfer",
                    "years": yrs, "abbr": abbr, "color": color})
    out.reverse()                                        # newest (current) first
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    info = sm.player_info(sid, pid)
    if info and (info.get("high_school") or info.get("hometown")):
        # A Jefferson player came through the JHSAA, so their high-school stop carries
        # the real thing: classification, district, individual record and any honours.
        jh = info.get("jhsaa") or {}
        stop = {"school": info.get("high_school") or "High school",
                "division": jh.get("group", ""), "badge": "high_school",
                "years": info.get("hometown", ""), "abbr": "HS", "color": "#888",
                "stars": info.get("recruit_stars", 0), "tier": info.get("recruit_tier", "")}
        if jh:
            stop["hs_record"] = jh.get("record", "")
            stop["hs_ladder"] = jh.get("ladder", 0)
            stop["hs_district"] = jh.get("district", "")
            stop["hs_honors"] = jh.get("honors", [])
            stop["hs_champion"] = jh.get("state_champion", False)
        out.append(stop)
    return out


def search_players(query: str, seed: int = DEFAULT_SEED, limit: int = 80) -> dict:
    """Name search across the active universes: rostered college players (link to
    their profile) and the current recruiting class (link to the recruit page).
    Matches a case-insensitive substring; reuses the cached pid index, so it's
    cheap once rosters are primed."""
    import app.seasonmode as sm
    import app.world as world
    from app import worldconfig
    q = (query or "").strip().lower()
    if len(q) < 2:
        return {"query": query, "players": [], "recruits": [], "n": 0, "short": True}

    players, seen = [], set()
    for val, division, gender, label in UNIVERSES:
        if not worldconfig.is_active(division, gender):
            continue
        for pid, info in sm._pid_index(division, gender).items():
            if pid in seen or q not in info["name"].lower():
                continue
            seen.add(pid)
            players.append({"pid": pid, "name": info["name"], "school": info["school"],
                            "division": division, "u": val, "label": label,
                            "class": info.get("class", ""), "country": info.get("country", "")})
    players.sort(key=lambda r: r["name"])

    recruits = []
    grad_year = world.recruiting_grad_year(seed) if world.exists(seed) else None
    if grad_year:
        for gender in worldconfig.active_genders():
            rg = RECRUIT_GENDERS.get(gender, gender)
            for p in get_recruits(rg, grad_year, seed).recruits:
                if q in p.name.lower():
                    recruits.append({"pid": p.pid, "name": p.name, "country": p.country,
                                     "hometown": getattr(p, "hometown", ""),
                                     "stars": getattr(p, "recruit_stars", 0),
                                     "tier": getattr(p, "recruit_tier", ""),
                                     "grad_year": grad_year, "u": "D1-" + gender})
        recruits.sort(key=lambda r: (-r["stars"], r["name"]))

    players = players[:limit]
    recruits = recruits[:limit]
    return {"query": query, "players": players, "recruits": recruits,
            "n": len(players) + len(recruits), "short": False}


def world_hub(seed: int = DEFAULT_SEED):
    import app.world as world
    import app.seasonmode as sm
    from app import worldconfig
    w = world.get_or_create(seed)
    world.prime(seed)
    # Only the universes the player actually runs count toward the world's phase
    # and completion. Dormant universes (e.g. the men's side of a women-only save)
    # are frozen at week 1 in 'regular' — counting them would peg the stage stepper
    # to "Regular season" forever and never let the world read complete.
    active_unis = [(val, division, gender, label)
                   for (val, division, gender, label) in UNIVERSES
                   if worldconfig.is_active(division, gender)]
    divisions = []
    progress = set()
    for val, division, gender, label in active_unis:
        sid = world.universe_sid(seed, w, division, gender)
        s = sm.load_season(sid)
        champ = s["champion"] if s["phase"] == "complete" else None
        progress.add(sm.season_progress(sid))
        divisions.append({
            "u": val, "label": label, "phase": s["phase"],
            "week": s["current_week"], "total": s["total_weeks"],
            "top": sm.national_top(sid, 4), "champion": champ,
        })
    # Every universe runs on the one world clock. More than one position here means
    # the save desynced (something stepped a universe on its own), which makes the
    # rankings compare fields that have played different numbers of duals.
    in_sync = len(progress) <= 1
    signed = world.signed_counts(seed)
    year = world.BASE_YEAR + w["year"]
    complete = bool(divisions) and all(d["phase"] == "complete" for d in divisions)

    import app.honors as honors
    # Awards are "done" once every ACTIVE universe's honors are stamped (never wait
    # on a dormant universe, whose honors are never stamped).
    awards_done = complete and all(honors.has_season(year, d, g)
                                   for (_v, d, g, _l) in active_unis)
    # Offseason runs as separate, visible steps: awards → world cups → rollover →
    # pro offseason. Each is one advance click, so nothing important happens inside
    # another step's click.
    _ORDER = ["ita", "fall_portal", "regular", "conf_tournaments", "selection", "ncaa",
              "awards", "world_cups", "offseason"]
    _PH = {"ita_kickoff": -2, "ita_indoor": -1, "fall_portal": -0.5, "regular": 0,
           "conf_tournaments": 1, "selection": 2, "ncaa": 3, "complete": 4}
    pros_pending = (w["week"] == 0 and w["year"] > 0 and not world.pros_rolled(w))
    if not complete:
        raw = min((d["phase"] for d in divisions), key=lambda p: _PH[p])
        stage = ("ita" if raw in ("ita_kickoff", "ita_indoor") else raw)
        if pros_pending:
            stage = "pro_offseason"
    elif not awards_done:
        stage = "awards"
    elif not world.cups_done(w):
        stage = "world_cups"
    else:
        stage = "offseason"
    if stage == "fall_portal":
        primary = {"endpoint": "fall_portal", "icon": "fa-solid fa-arrows-rotate", "label": "Review fall portal →", "link": True}
    elif stage == "selection":
        primary = {"endpoint": "world_advance", "label": "Reveal complete — start NCAAs →"}
    elif stage in ("ita", "regular", "conf_tournaments", "ncaa"):
        if w["week"] == 0 and stage in ("ita", "regular"):
            primary = {"endpoint": "preseason_view", "icon": "fa-solid fa-gear", "label": "Preseason setup →", "link": True}
        else:
            primary = {"endpoint": "world_advance",
                       "label": ("Run Preseason NIT →" if stage == "ita"
                                 else "Advance week →" if stage == "regular"
                                 else "Advance postseason →")}
    elif stage == "awards":
        primary = {"endpoint": "world_awards", "icon": "fa-solid fa-medal", "label": "Run awards →"}
    elif stage == "world_cups":
        primary = {"endpoint": "world_advance", "icon": "fa-solid fa-earth-americas",
                   "label": "Run Davis / BJK Cup →"}
    elif stage == "pro_offseason":
        primary = {"endpoint": "world_advance", "icon": "fa-solid fa-trophy",
                   "label": "Run pro league offseason →"}
    else:
        primary = {"endpoint": "world_advance", "label": f"Begin {year + 1} season →"}
    _LABELS = {"ita": "Preseason NIT", "fall_portal": "Fall portal", "regular": "Regular season",
               "conf_tournaments": "Conf tournaments", "selection": "Bracket Reveal",
               "ncaa": "NCAA championship", "awards": "Awards", "world_cups": "World Cups",
               "offseason": "Offseason"}
    # pro_offseason sits at week 0 of the NEW year — past the stepper's season arc,
    # so it shows as the (already-rolled-over) Offseason step still finishing up.
    ci = _ORDER.index("offseason" if stage == "pro_offseason" else stage)
    stages = [{"key": k, "label": _LABELS[k], "done": i < ci, "current": i == ci}
              for i, k in enumerate(_ORDER)]

    return {
        "year": year, "season_no": w["year"] + 1,
        "week": w["week"], "divisions": divisions, "signed": signed,
        "signed_total": sum(signed.values()), "in_sync": in_sync,
        "complete": complete, "awards_done": awards_done,
        "stage": stage, "primary": primary, "stages": stages,
    }


def preseason_view(seed: int = DEFAULT_SEED) -> dict:
    import app.world as world
    from app import worldconfig
    w = world.get_or_create(seed)
    year = world.BASE_YEAR + w["year"]
    active = [lbl for (_v, d, g, lbl) in UNIVERSES if worldconfig.is_active(d, g)]
    dormant = [lbl for (_v, d, g, lbl) in UNIVERSES if not worldconfig.is_active(d, g)]
    steps = [
        {"icon": "fa-solid fa-arrows-rotate", "title": "Pre-season portal",
         "auto": "The sim flags talent that generated into the wrong division.",
         "desc": "Move studs stuck in D3/D4 (and any other misallocated player) up to "
                 "a fitting program before the season opens. Cascades re-balance rosters.",
         "label": "Open pre-season portal →", "endpoint": "preseason_portal", "args": {}},
        {"icon": "fa-solid fa-graduation-cap", "title": "Recruiting",
         "auto": "Your class signs automatically, a slice each week.",
         "desc": "Open the board to track the pool and steer your targets.",
         "label": "Open recruiting →", "endpoint": "recruiting", "args": {}},
        {"icon": "fa-solid fa-calendar-days", "title": "Schedule",
         "auto": "Every team's non-conference + conference slate is already set.",
         "desc": "Review your slate, or edit a team's schedule in the editor.",
         "label": "View schedule →", "endpoint": "season_schedule", "args": {}},
        {"icon": "fa-solid fa-table-tennis-paddle-ball", "title": "Lineups",
         "auto": "Ladders auto-shuffle by player strength.",
         "desc": "Reorder any ladder in the editor to override the auto order.",
         "label": "Open editor →", "endpoint": "editor", "args": {}},
    ]
    return {"year": year, "active": active, "dormant": dormant, "steps": steps,
            "is_preseason": w["week"] == 0}


def my_program_view(seed: int = DEFAULT_SEED) -> dict | None:
    """The coached program's clubhouse: identity, record, lineup, incoming class,
    scholarships and schedule — scoped to worldconfig.user_program(). None in
    spectator mode (no team chosen) or if the saved program no longer exists."""
    from app import worldconfig, overrides as ov
    import app.world as world
    import app.seasonmode as sm
    from app.ncaa import (load_division, build_roster,
                          lineup_size as _lineup_size, dual_format as _dual_format)
    prog = worldconfig.user_program()
    if not prog:
        return None
    division, gender, school = prog["division"], prog["gender"], prog["school"]
    p = load_division(division, gender).by_school(school)
    if not p:
        return None
    w = world.get_or_create(seed)
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    roster = team_roster(division, gender, school)
    # team_roster re-sorts by ability, which would hide a hand-set lineup. Order the
    # rows by build_roster (which honors the lineup pin) so the displayed ladder is
    # exactly what the team fields, and renumber the singles lines to match.
    order = {pr.pid: i for i, pr in enumerate(build_roster(p))}
    roster.sort(key=lambda r: order.get(r["p"].pid, len(order)))
    for i, r in enumerate(roster, 1):
        r["line"] = i if i <= 6 else None
    lineup_pinned = school in ov.get_lineups()
    doubles_pin = ov.get_doubles().get(school) or []
    rec = team_results(division, gender, school, seed)
    sched = sm.team_schedule(sid, school)
    nxt = next((d for d in sched if d["status"] != "final"), None)
    if nxt:
        opp = nxt["away"] if nxt["home"] == school else nxt["home"]
        nxt = {"week": nxt["week"], "opp": opp, "home": nxt["home"] == school,
               "round": nxt["round"], "conf": bool(nxt["is_conf"])}
    return {
        "division": division, "gender": gender, "school": school,
        "u": f"{division}-{gender}",
        "conf": p.conf, "conf_abbr": p.conf_abbr,
        "prestige": round(getattr(p, "prestige", 0.0) * 100),
        "year": world.BASE_YEAR + w["year"], "week": w["week"],
        "is_preseason": w["week"] == 0,
        "season_complete": sm.load_season(sid).get("phase") == "complete",
        "wins": rec["wins"], "losses": rec["losses"], "results": rec["results"][-5:],
        "roster": roster,
        "starters": [r for r in roster if r["line"]],
        "bench": [r for r in roster if not r["line"]],
        "lineup_pinned": lineup_pinned,
        "doubles_pinned": bool(doubles_pin),
        "doubles_pin": doubles_pin,
        # The division's dual shape, so the lineup/doubles editors render the right
        # number of slots (D1/D4 field 10 singles; D1 fields 5 doubles pairs).
        "n_lineup": _lineup_size(division),
        "n_doubles": _dual_format(division).n_doubles,
        "budget": team_budget(division, gender, school),
        "incoming": team_recruiting_class(gender, school, seed),
        "next": nxt,
        "remaining_duals": sum(1 for d in sched if d["status"] != "final"),
    }


def my_schedule_plan(seed: int = DEFAULT_SEED) -> dict | None:
    """Preseason non-conference planner for the coached program: its editable
    non-conf duals + the pool of eligible opponents. None in spectator mode."""
    from app import worldconfig
    import app.world as world
    import app.seasonmode as sm
    from .rankings_data import crest
    prog = worldconfig.user_program()
    if not prog:
        return None
    division, gender, school = prog["division"], prog["gender"], prog["school"]
    w = world.get_or_create(seed)
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    duals = sm.nonconf_duals(sid, school)
    for d in duals:
        d["abbr"], d["color"] = crest(d["opponent"])
    return {
        "school": school, "division": division, "gender": gender,
        "u": f"{division}-{gender}", "is_preseason": w["week"] == 0,
        "duals": duals,
        "eligible": sm.eligible_nonconf_opponents(sid, division, gender, school),
    }


def _class_grade(avg_stars: float, n: int) -> str:
    if not n:
        return "—"
    return ("A" if avg_stars >= 3.8 else "B" if avg_stars >= 3.0
            else "C" if avg_stars >= 2.2 else "D" if avg_stars >= 1.2 else "F")


def my_season_report(seed: int = DEFAULT_SEED) -> dict | None:
    """End-of-season report card for the coached program. Expectation = preseason
    prestige rank; result = Power-Index rank + a postseason pedigree bonus (same
    over/under-performance the prestige-momentum rollover uses). Read-only; reads
    the live season, never writes momentum. None in spectator mode."""
    from app import worldconfig
    import app.world as world
    import app.seasonmode as sm
    from app.ncaa import load_division
    prog = worldconfig.user_program()
    if not prog:
        return None
    division, gender, school = prog["division"], prog["gender"], prog["school"]
    w = world.get_or_create(seed)
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    div = load_division(division, gender)
    if not div.by_school(school):
        return None
    pi = sm.power_index(sid)
    rec = team_results(division, gender, school, seed)
    played = rec["wins"] + rec["losses"]
    base = {"school": school, "u": f"{division}-{gender}", "conf": div.by_school(school).conf,
            "year": world.BASE_YEAR + w["year"]}
    progs = [p for p in div.programs if p.school in pi]
    if played == 0 or len(progs) < 2:
        return {**base, "started": False}

    npres = len(div.programs)
    by_pres = sorted(div.programs, key=lambda p: p.prestige, reverse=True)
    pres_rank = next(i for i, p in enumerate(by_pres, 1) if p.school == school)
    by_pi = sorted(progs, key=lambda p: pi[p.school].pi, reverse=True)
    pi_rank = next(i for i, p in enumerate(by_pi, 1) if p.school == school)
    n = len(progs)
    pres_pct = 1 - (pres_rank - 1) / (npres - 1) if npres > 1 else 0.5
    pi_pct = 1 - (pi_rank - 1) / (n - 1)

    champ = sm.national_champion(sid)
    ff = sm.ncaa_semifinalists(sid)
    field = sm.ncaa_participants(sid)
    ct = sm.conf_champions(sid)
    bonus = (0.10 if school == champ else 0.06 if school in ff
             else 0.03 if school in field else 0.0) + (0.02 if school in ct else 0.0)
    delta = (pi_pct + min(0.10, bonus)) - pres_pct
    verdict = "overachieved" if delta > 0.12 else "underachieved" if delta < -0.12 else "met"
    post = ("National champion" if school == champ else "NCAA Final Four" if school in ff
            else "Made the NCAA field" if school in field else "Missed the NCAA field")

    cr = sm.conf_rank(sid).get(school)                 # (rank, w, l) or None
    cls = team_recruiting_class(gender, school, seed)
    pirank = {p.school: i for i, p in enumerate(by_pi, 1)}
    notable = sorted(
        ({"opp": d["opp"], "rank": pirank[d["opp"]], "mine": d["mine"],
          "theirs": d["theirs"], "home": d["home"]}
         for d in rec["results"] if d["won"] and pirank.get(d["opp"], 1e9) < pi_rank),
        key=lambda x: x["rank"])[:4]

    season = sm.load_season(sid)
    return {
        **base, "started": True, "complete": season.get("phase") == "complete",
        "wins": rec["wins"], "losses": rec["losses"],
        "pres_rank": pres_rank, "pi_rank": pi_rank, "field": n, "field_pres": npres,
        "verdict": verdict, "delta": round(delta, 3),
        "conf_rank": cr[0] if cr else None, "conf_w": cr[1] if cr else None,
        "conf_l": cr[2] if cr else None, "ct_champ": school in ct, "post": post,
        "class_score": cls["score"], "class_grade": _class_grade(cls["avg_stars"], cls["n"]),
        "class_n": cls["n"], "class_avg": cls["avg_stars"], "notable": notable,
    }


def _prestige_tier_label(p: float) -> str:
    return ("Blue blood" if p >= 0.78 else "Powerhouse" if p >= 0.62
            else "Established" if p >= 0.45 else "Up-and-comer" if p >= 0.30 else "Rebuild")


def _programs_for_gender(gender: str):
    from app.ncaa import load_division
    out = []
    for d in ("D1", "D2", "D3", "D4"):
        try:
            div = load_division(d, gender)
        except FileNotFoundError:
            continue
        out += [(d, p) for p in div.programs]
    return out


def job_offers(seed: int = DEFAULT_SEED) -> dict | None:
    """Prestige-gated coaching offers for the human coach. Opt-in UPWARD mobility
    only — there is no firing. Offers open once the season is complete; a strong
    season (overperforming expectation) widens the reach to better programs. The
    slate is deterministic per (seed, year, school). None in spectator mode."""
    from app import worldconfig
    import app.world as world
    import app.seasonmode as sm
    import random
    from app.ncaa import load_division
    prog = worldconfig.user_program()
    if not prog:
        return None
    division, gender, school = prog["division"], prog["gender"], prog["school"]
    w = world.get_or_create(seed)
    cur = load_division(division, gender).by_school(school)
    if not cur:
        return None
    cur_prestige = getattr(cur, "prestige", 0.5)
    rep = my_season_report(seed)
    complete = bool(rep and rep.get("complete"))
    delta = rep.get("delta", 0.0) if (rep and rep.get("started")) else 0.0
    head = {"school": school, "division": division, "gender": gender,
            "u": f"{division}-{gender}", "conf": cur.conf,
            "prestige": round(cur_prestige * 100),
            "tier": _prestige_tier_label(cur_prestige),
            "career": worldconfig.get_coach_career(),
            "verdict": rep.get("verdict") if rep else None}
    if not complete:
        return {**head, "available": False, "offers": [],
                "note": "Job offers open once your season is complete."}
    # A good season widens the reach upward; offers are always at least lateral-plus.
    band_lo = cur_prestige + 0.02
    band_hi = cur_prestige + 0.06 + max(0.0, delta) * 0.6
    pool = [(d, p) for (d, p) in _programs_for_gender(gender)
            if p.school != school and band_lo <= getattr(p, "prestige", 0.0) <= band_hi]
    rng = random.Random(f"{seed}|offers|{w['year']}|{school}")
    rng.shuffle(pool)                                    # break prestige ties stably per save
    pool.sort(key=lambda dp: getattr(dp[1], "prestige", 0.0), reverse=True)
    offers = [{"school": p.school, "division": d, "conf": p.conf,
               "prestige": round(getattr(p, "prestige", 0.0) * 100),
               "tier": _prestige_tier_label(getattr(p, "prestige", 0.0))}
              for d, p in pool[:4]]
    return {**head, "available": True, "offers": offers,
            "note": None if offers else "No better jobs opened up this year — keep building."}


def all_gender_programs(gender: str):
    from app import ncaa
    progs = []
    for division in ("D1", "D2", "D3", "D4"):
        try:
            progs.extend(ncaa.load_division(division, gender).programs)
        except FileNotFoundError:
            continue
    return progs


def conference_schools(division: str, gender: str):
    from app import ncaa
    div = ncaa.load_division(division, gender)
    return sorted((conf, sorted(p.school for p in members))
                  for conf, members in div.conferences.items())


def team_conference(division: str, gender: str, school: str) -> str:
    from app import ncaa
    prog = ncaa.load_division(division, gender).by_school(school)
    return prog.conf if prog else ""


def injury_rows(division: str, gender: str, school: str | None = None,
                conf_filter: str = "All", active_only: bool = False) -> list[dict]:
    """The current season's injury log as display rows. For a single program pass
    `school`; for the league-wide list omit it and optionally filter by conference.
    `active_only` keeps just the currently-hurt (out / season-ending). Each row
    carries the player/team, the injury length, status, and crest bits."""
    import app.seasonmode as sm
    from app import world as wd, ncaa
    from .rankings_data import crest
    sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
    conf_of = {p.school: p.conf for p in ncaa.load_division(division, gender).programs}
    out = []
    for e in sm.injury_log(sid, school):
        if active_only and not e["active"]:
            continue
        c = conf_of.get(e["school"], "")
        if conf_filter and conf_filter != "All" and c != conf_filter:
            continue
        abbr, color = crest(e["school"])
        out.append({**e, "conf": c, "abbr": abbr, "color": color})
    return out


def conference_ratings(division: str, gender: str, conf: str):
    """Current prestige + academic priors (0–100) for a conference, flagged when
    overridden. Returns None for 'All' or an unknown conference."""
    from app import ncaa, overrides as ov
    members = ncaa.load_division(division, gender).conferences.get(conf, [])
    if not members:
        return None
    abbr = members[0].conf_abbr
    cp, ca = ov.get_conf_prestige(), ov.get_conf_academics()
    return {
        "conf": conf,
        "prestige": round(cp.get(conf, ncaa.conf_prestige(abbr, division)) * 100),
        "academics": round(ca.get(conf, ncaa._academic_prior(abbr, division)) * 100),
        "prestige_overridden": conf in cp,
        "academics_overridden": conf in ca,
        "n": len(members),
    }


def team_roster(division: str, gender: str, school: str):
    from app import economy
    import app.world as world
    import app.seasonmode as sm
    from app.ncaa import build_roster, load_division
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed())
    prog = load_division(division, gender).by_school(school)
    roster = build_roster(prog) if prog else []
    strmap = sm.season_player_str(sid)
    recs = sm.player_records(sid)
    injured = {e["pid"]: e for e in sm.injury_log(sid, school) if e["active"]}
    rows = []
    for p in sorted(roster, key=lambda q: q.current_overall(), reverse=True):
        s, rel = strmap.get(p.pid, (p.str_value(), 0.0))
        w, l = recs.get(p.pid, (0, 0))
        rows.append({"p": p, "str": round(s, 1), "rel": rel, "w": w, "l": l,
                     "injury": injured.get(p.pid),
                     "schol": economy.fraction_label(getattr(p, "scholarship", 0.0))})
    from app.ncaa import lineup_size
    _lu = lineup_size(division)
    for i, r in enumerate(rows, 1):
        r["line"] = i if i <= _lu else None     # the division's singles card starts
    return rows


def team_budget(division: str, gender: str, school: str) -> dict:
    from app import economy
    from app.ncaa import build_roster, load_division
    prog = load_division(division, gender).by_school(school)
    roster = build_roster(prog) if prog else []
    return economy.budget_summary(roster, division, gender)


# ---------------------------------------------------------------------------
# JHSAA — Jefferson's high-school association
# ---------------------------------------------------------------------------
# Another layer of the same sports world, so it is shaped like the college one:
# a program has a page, a district is its conference, a classification is the scope
# you browse in, and the state tournament is the postseason everything points at.
#
# EVERY view here READS the archive `world.run_jhsaa` wrote — a season is ~5,100 duals
# per gender and must never be replayed on a request thread. The only thing rebuilt
# live is a ROSTER, which is deterministic from (school, gender, entry year, seat) and
# costs twelve prospect builds; that is also what lets an archived season show the
# players who actually played it.

import datetime as _dt


def _jh_g(gender: str) -> str:
    return "girls" if gender in ("women", "female", "girls") else "boys"


def _jh_schools(gender: str) -> dict:
    import app.jhsaa as jh
    return {s.name: s for s in jh.load_schools(gender)}


def _jh_deco(schools: dict, name: str, size: int = 34) -> dict:
    """A school as it appears anywhere it is referenced: mark, where it is, what
    class it plays in. Every JHSAA surface renders a school through this, so a school
    looks the same on the hub, in a bracket and in a district table."""
    import app.jhsaa as jh
    s = schools.get(name)
    if s is None:
        return {"name": name, "mark": "", "city": "", "county": "", "district": "",
                "group": "", "classification": "", "mascot": "", "found": False}
    return {"name": name, "mark": jh.mark(s, size), "city": s.city, "county": s.county,
            "district": s.district, "group": s.group, "classification": s.classification,
            "mascot": s.mascot, "enrollment": s.enrollment, "private": s.private,
            "found": True}


def _jh_dates(sched: list[dict], season_year: int | None,
              cal: dict | None = None) -> list[str]:
    """A DISPLAY calendar for one season's card.

    ‼️ THE DATE BELONGS TO THE MATCH, NOT THE CARD (owner rule 2027-08). This
    used to derive a date from each dual's POSITION in the school's own
    schedule, so the same dual showed two different days on the two schools'
    pages — Lake Esperanza's Super Regional read May 14 and its opponent José
    Martí's read May 17. Each card was internally plausible; only reciprocity
    was wrong, which is why it survived. `world.jhsaa_match_dates` now assigns
    one date per DUAL for the whole gender-season and both cards look it up.

    Still presentation only: there is no clock inside a JHSAA season, nothing
    reads a date back, and no simulation decision depends on one. The fallback
    below keeps a card readable when the calendar cannot be built (an archive
    with no dual rows)."""
    import app.world as world
    if not season_year:
        return ["" for _ in sched]
    cal = cal or {}
    out = []
    for d in sched:
        day = cal.get(world.jh_match_key(d))
        out.append(f"{day:%b} {day.day}" if day else "")
    return out

def _jh_reported_lines(d: dict) -> list[dict]:
    """A dual's lines with every set score WINNER-FIRST — how tennis is actually reported.

    A tennis score is written from the winner's side, always: "6-4, 3-6, 7-5" belongs to
    whoever won the match, and the loser's name appears beside it rather than the loser's
    games. It is NOT a per-viewer perspective, which is the mistake this replaces — an
    earlier pass flipped the numbers for the away team's card, which fixed the visible
    symptom (a pair shown winning with 3-6, 3-6 beside them) by inventing a second wrong
    convention: the home team's card then read the loser's games first on every line the
    away side won.

    The engine already had this right: `MatchResult.scoreline` is documented "from the
    winner's perspective", and the college league stores THAT and un-flips it with
    `home_won` when it needs directional games (`gtt_seasonmode._parse_games`). The JHSAA
    reimplemented the string instead of using it, and reimplemented it home-first.

    ⚠️ The STORED JHSAA string stays home-first, and that divergence is now deliberate
    rather than accidental: seasons are ALREADY ARCHIVED that way, and re-reading them
    under a new convention would silently misreport every line the away side won — the
    same bug, moved into the past where it cannot be seen. `jhsaa._games` also wants the
    directional split for oGS. So storage keeps the record and the report is normalised
    here. Which side is being viewed decides the name order and the d./l. marker; it never
    decides the numbers."""
    out = []
    for ln in d.get("lines") or ():
        if ln.get("home_won"):
            out.append(ln)                       # home won: home-first IS winner-first
            continue
        sets = [x.strip() for x in (ln.get("score") or "").split(",") if x.strip()]
        flipped = []
        for st in sets:
            a, _, b = st.partition("-")
            flipped.append(f"{b}-{a}" if b else st)
        out.append({**ln, "score": ", ".join(flipped)})
    return out


def _jh_line_records(sched: list[dict]) -> dict:
    """Every player's singles and doubles record for a season, off the match-level archive.

    Keyed by NAME because that is what a line carries. A season's individual records
    therefore come from the same duals the team record does — a senior shown at 27-4
    and the school's season are the one simulated season, never two computations."""
    rec: dict = {}
    for d in sched:
        side = "home" if d.get("home") else "away"
        for ln in d.get("lines") or ():
            we_won = bool(ln.get("home_won")) if d.get("home") else not ln.get("home_won")
            kind = "s" if (ln.get("slot") or "").startswith("S") else "d"
            for nm in ln.get(side) or ():
                r = rec.setdefault(nm, {"s": [0, 0], "d": [0, 0]})
                r[kind][0 if we_won else 1] += 1
    return rec


def _jh_slot_records(sched: list[dict]) -> dict:
    """Every player's W-L broken out by the actual FLIGHT they played (S1-S5,
    D1-D4 — the union of both league formats, `EARLY_FORMAT_PHASE`'s 5S/2D and the
    regular season's 3S/4D), off the same match-level archive `_jh_line_records`
    reads. This is the college career-record box's per-line breakdown, ported to
    high school — mirrors `player_career_records`'s `_box`."""
    rec: dict = {}
    for d in sched:
        side = "home" if d.get("home") else "away"
        for ln in d.get("lines") or ():
            slot = ln.get("slot") or ""
            if not slot:
                continue
            we_won = bool(ln.get("home_won")) if d.get("home") else not ln.get("home_won")
            for nm in ln.get(side) or ():
                r = rec.setdefault(nm, {})
                wl = r.setdefault(slot, [0, 0])
                wl[0 if we_won else 1] += 1
    return rec


def _jh_flight_box(seasons: list[dict]) -> dict:
    """The player-card flight box: singles S1-S5, doubles D1-D4, one row per season
    plus a TOTALS row — same shape as `player_career_records`'s `_box`, so the
    template can share the `.rc-recbox` markup."""
    def _box(kind: str, slots: list[str]):
        rows, totals = [], {s: [0, 0] for s in slots}
        tov = [0, 0]
        for s in seasons:
            cells, ov = {}, [0, 0]
            for slot in slots:
                wl = (s["slots"] or {}).get(slot)
                cells[slot] = (f"{wl[0]}-{wl[1]}" if wl else "–")
                if wl:
                    ov[0] += wl[0]; ov[1] += wl[1]
                    totals[slot][0] += wl[0]; totals[slot][1] += wl[1]
            tov[0] += ov[0]; tov[1] += ov[1]
            rows.append({"year": s["season_year"], "cells": cells,
                        "overall": f"{ov[0]}-{ov[1]}"})
        tcells = {s: (f"{totals[s][0]}-{totals[s][1]}" if (totals[s][0] or totals[s][1]) else "–")
                  for s in slots}
        return {"slots": slots, "rows": rows, "tcells": tcells,
                "toverall": f"{tov[0]}-{tov[1]}", "any": bool(rows)}
    singles = [f"S{i}" for i in range(1, 6)]
    doubles = [f"D{i}" for i in range(1, 5)]
    return {"singles": _box("singles", singles), "doubles": _box("doubles", doubles)}


def _jh_seeds(bracket: dict) -> dict:
    return {nm: i + 1 for i, nm in enumerate((bracket or {}).get("field") or ())}


def _jh_score(gm: dict) -> str:
    """A state game's score, WINNER-FIRST — the contract `_bracket.html` renders under.

    `brk_row` picks its half of the string by which side WON, so a home-first score is
    swapped on every card the away team won. It looks right on the cards the home team
    won, which is exactly why it survived a design pass and a merge: half the bracket
    was correct, and the wrong half read as a plausible upset."""
    hp, ap = int(gm.get("home_points", 0)), int(gm.get("away_points", 0))
    return f"{max(hp, ap)}-{min(hp, ap)}"


def _jh_brk_team(name: str, won: bool, seeds: dict, schools: dict) -> dict:
    """One side of a bracket card, in the shape `_bracket.html` already renders."""
    return {"school": name, "abbr": "", "color": "var(--gray-400)", "won": won,
            "seed": seeds.get(name, ""), "conf": (schools.get(name).district
                                                  if schools.get(name) else ""),
            "aq": False, "tbd": False, "mark": _jh_deco(schools, name, 18)["mark"]}


def _jh_bye_card(name: str, seeds: dict, schools: dict) -> dict:
    """A team advancing WITHOUT playing, as a card of its own.

    `_bracket_canvas` connects a column to the one before it positionally: same width
    means one feeder each, anything else means the standard halving (`2k`, `2k+1`). A
    JHSAA draw pads to the next power of two and the byes collapse unevenly, so a
    24-team field plays rounds of 12 → 6 → 3 → 1 → 1 — and at 3 → 1 the halving rule
    links only the first two winners. The THIRD winner byes straight into the final, so
    its route through the tree was simply missing.

    Making the bye an explicit card restores it without touching the shared geometry:
    the column becomes 3 → 2 → 1, which is exactly what the halving rule already draws
    correctly. The empty side renders as BYE rather than TBD — the slot is not
    undecided, there is genuinely no opponent."""
    return {"home": _jh_brk_team(name, True, seeds, schools),
            "away": {"school": "", "abbr": "", "color": "", "won": False, "seed": None,
                     "conf": "", "aq": False, "tbd": True, "label": "BYE"},
            "played": False, "id": None, "tbd": False, "region": None, "bpos": 0,
            "home_won": True, "winner": name, "score": "", "bye": True}


def jhsaa_toc_view(seed: int, gender: str, year: int | None = None) -> dict:
    """The Tournament of Champions bracket — its own event, not a classification's.

    One champion per classification, seeded on the TOSS Power Index rather than on
    classification, so a 4A champion that rated above the 6A one is the higher seed.
    That is the whole reason the event is worth playing, and it is why the seeds are
    read off the archive rather than reconstructed from the group order.

    Renders on the SAME tree as every other bracket in the app — which means handing
    the template a `_bracket_canvas` result, not the raw columns. `brk_canvas` reads
    `cv.width` / `cv.columns` / `cv.cards` / `cv.links`; give it a plain list and Jinja
    resolves every one of them to Undefined, so the page draws a zero-size canvas with
    no cards and no elbows and says nothing about it. That is what shipped: a toolbar,
    a champion and a field list above an empty box."""
    import app.jhsaa as jh
    import app.world as world
    w = world.get_or_create(seed)
    g = _jh_g(gender)
    years = world.jhsaa_years(w["id"], g)
    yr = (years[0] if years else w["year"]) if year is None else year
    arc = world.get_jhsaa(w["id"], yr, g)
    scope = _jh_scope(g, jh.GROUPS[0], list(jh.GROUPS), yr, years, None, None)
    if not arc or not (arc.get("toc") or {}).get("rounds"):
        return {"ready": False, "gender": g, "year": yr, "years": years, "scope": scope}
    toc = arc["toc"]
    schools = _jh_schools(g)
    champ_of = {br.get("champion"): grp
                for grp, br in (arc.get("brackets") or {}).items() if br.get("champion")}
    seeds = toc.get("seeds") or {n: i + 1 for i, n in enumerate(toc.get("field") or ())}
    return {
        "ready": True, "gender": g, "year": yr, "years": years, "scope": scope,
        "season_year": arc.get("season_year"),
        "field": [{**_jh_deco(schools, n, 26), "seed": seeds.get(n, i + 1),
                   "group": champ_of.get(n, "")}
                  for i, n in enumerate(toc.get("field") or ())],
        "field_n": len(toc.get("field") or ()),
        # Every round, decorated the way the state bracket's are, so the page can show
        # the draw round by round like every other bracket in the app instead of only
        # naming the winner.
        "rounds": [{**rd, "games": [
            {**gm, "home_deco": _jh_deco(schools, gm["home"], 20),
             "away_deco": _jh_deco(schools, gm["away"], 20),
             "home_seed": seeds.get(gm["home"], 0), "away_seed": seeds.get(gm["away"], 0),
             "home_group": champ_of.get(gm["home"], ""),
             "away_group": champ_of.get(gm["away"], ""),
             "win_points": max(gm["home_points"], gm["away_points"]),
             "lose_points": min(gm["home_points"], gm["away_points"])}
            for gm in rd["games"]]} for rd in world.jhsaa_state_rounds(toc)],
        # A six-team tree is a third the width of a 32-team state draw, so it gets the
        # roomier cards the Preseason NIT's small sites use rather than the NCAA
        # defaults — the geometry is a parameter precisely so this never becomes CSS.
        "canvas": _bracket_canvas(_jh_bracket_cols(toc, schools),
                                  card_w=232, card_h=60, gutter=56, leaf_gap=18),
        **_jh_final_four(toc, schools),
        "champion_group": champ_of.get(toc.get("champion"), ""),
    }


def _jh_split_state(br: dict) -> tuple[dict, dict | None]:
    """An archived State bracket split at the qualifying boundary, for rendering.

    An EXPANDED field's preliminary rounds (`round_names` — the Qualifiers Round
    and the First Round) are a qualifying event feeding a FRESH seeded draw, so
    there is NO bracket path from a Qualies slot to a main-draw slot — exactly as
    a tour event's qualifying feeds its main draw. One positional tree over all
    the rounds would therefore invent links (`_bracket_canvas` connects columns
    by the 2k/2k+1 halving), so the page draws TWO canvases. The split dicts are
    render-shapes only — the archive keeps the one bracket:
      * main: the post-prelim rounds, `field` = the teams alive going into them
        (the double-bye champions + the qualifying survivors), so
        `jhsaa_state_rounds` counts down and derives byes from the right number;
      * qualifying: the prelim rounds over the teams that actually played them.
    Both carry `seed_map` — the TOURNAMENT's own seeds off the full field — so a
    #23 seed that qualifies keeps its 23 chip in the main draw. A 24-team class
    or an old archive returns `(br, None)` untouched."""
    names = br.get("round_names") or ()
    rounds = br.get("rounds") or ()
    if not names or len(rounds) <= len(names):
        return br, None
    k = len(names)
    seed_map = _jh_seeds(br)
    pre, main = list(rounds[:k]), list(rounds[k:])
    qual_field = [t for gm in pre[0] for t in (gm["home"], gm["away"])]
    survivors = [gm["winner"] for gm in pre[-1]]
    champs = [t for t in (br.get("field") or ()) if t not in set(qual_field)]
    qual = {"field": qual_field, "rounds": pre, "round_names": list(names),
            "seed_map": seed_map}
    return ({**br, "rounds": main, "round_names": [],
             "field": champs + survivors, "seed_map": seed_map}, qual)


def _jh_bracket_cols(bracket: dict, schools: dict, keep: int = 0) -> list:
    """The state tournament as bracket COLUMNS for the shared canvas.

    Byes are materialised as pass-through cards (`_jh_bye_card`) so every team's route
    through the tree is drawn. Which teams byed is DERIVED from the archive rather than
    assumed: a team alive going into a round that does not appear in any of that
    round's games advanced without playing.

    The cards are then ORDERED BY THEIR REAL FEEDERS, which is what makes the shared
    canvas correct. `_bracket_canvas` links positionally — cards `2k` and `2k+1` feed
    card `k` — and the archive gives no such order: the draw seeds byes onto the top
    seeds' anchors, so they sit INTERLEAVED through the opening round, not conveniently
    at its end. Walking back from the final and placing each card next to its sibling
    (the previous column's card whose winner is standing in this one) makes the
    positional rule true by construction, for any draw shape.

    `keep` trims to the last N rounds — the hub shows the business end of the draw and
    links to the full tree, rather than putting a 32-card ladder above the standings."""
    import app.world as world
    # A split render-shape (`_jh_split_state`) carries the tournament's own seeds;
    # the archived bracket derives them from its field order as always.
    seeds = (bracket or {}).get("seed_map") or _jh_seeds(bracket)
    rounds = world.jhsaa_state_rounds(bracket)
    alive = list((bracket or {}).get("field") or ())
    cols = []
    for rd in rounds:
        ms = []
        playing = set()
        for gm in rd["games"]:
            hw = gm.get("winner") == gm.get("home")
            playing.update((gm.get("home"), gm.get("away")))
            ms.append({"home": _jh_brk_team(gm.get("home", ""), hw, seeds, schools),
                       "away": _jh_brk_team(gm.get("away", ""), not hw, seeds, schools),
                       "played": True, "id": None, "tbd": False, "region": None,
                       "bpos": 0, "home_won": hw, "winner": gm.get("winner"),
                       # WINNER-FIRST: `brk_row` picks its half of this string by which
                       # side won, not by which side is home (see _bracket.html).
                       "score": _jh_score(gm)})
        byes = [t for t in alive if t not in playing]
        ms.extend(_jh_bye_card(t, seeds, schools) for t in byes)
        alive = [gm.get("winner") for gm in rd["games"]] + byes
        cols.append({"name": rd["name"], "matchups": ms})
    _order_by_feeders(cols)
    return cols[-keep:] if keep else cols


def _order_by_feeders(cols: list) -> list:
    """Reorder each column so card `2k` and card `2k+1` are the two that feed card `k`.

    `_bracket_canvas` reads the parent-child relationship off POSITION, so the caller
    owes it a positionally-correct list. Walking right to left, each card in column `i`
    claims the cards in column `i-1` whose winners are standing in it; anything
    unclaimed keeps its relative order at the end (a defensive tail — with a complete
    archive there is nothing left over)."""
    for i in range(len(cols) - 1, 0, -1):
        prev = cols[i - 1]["matchups"]
        by_winner = {}
        for m in prev:
            if m.get("winner"):
                by_winner.setdefault(m["winner"], m)
        ordered, claimed = [], set()
        for m in cols[i]["matchups"]:
            for side in ("home", "away"):
                f = by_winner.get(m[side].get("school"))
                if f is not None and id(f) not in claimed:
                    ordered.append(f)
                    claimed.add(id(f))
        ordered += [m for m in prev if id(m) not in claimed]
        cols[i - 1]["matchups"] = ordered
    return cols


def _jh_final_four(bracket: dict, schools: dict) -> dict:
    """Champion, runner-up and the beaten semifinalists of an archived draw — the
    result, as a result reads, rather than as the last two rows of a list of games."""
    import app.world as world
    rounds = world.jhsaa_state_rounds(bracket)
    out = {"champion": None, "runner_up": None, "semifinalists": [], "final": None}
    if not rounds:
        return out
    final = rounds[-1]["games"][-1] if rounds[-1]["games"] else None
    if final:
        win, lose = final["winner"], (final["away"] if final["winner"] == final["home"]
                                      else final["home"])
        out["champion"] = _jh_deco(schools, win, 64)
        out["runner_up"] = _jh_deco(schools, lose, 30)
        # `win_points`/`lose_points` because the summary reads "N-M · final · def.
        # <runner-up>": a home-first pair prints the LOSER's number first whenever the
        # away side won the final, which is the same bug as the bracket card in the one
        # place it is stated in words. `score` stays for the shared card macro.
        wp, lp = max(final["home_points"], final["away_points"]), \
            min(final["home_points"], final["away_points"])
        out["final"] = {**final, "score": _jh_score(final),
                        "win_points": int(wp), "lose_points": int(lp)}
    if len(rounds) > 1:
        for gm in rounds[-2]["games"]:
            beaten = gm["away"] if gm["winner"] == gm["home"] else gm["home"]
            out["semifinalists"].append(_jh_deco(schools, beaten, 24))
    return out


def _jh_scope(gender: str, group: str, groups: list, year: int, years: list,
              season_year: int | None, arc: dict | None = None) -> dict:
    """The persistent scope the whole section is browsed in: gender, classification,
    season. Every JHSAA page carries the same one so a class stays selected as you move
    state → classification → district → school → player and back.

    `season_years` labels each world-year with its calendar year — the season a world
    index stands for is `jhsaa_season_year`, and a page must never print the bare index
    (a program history reading "Year 0, Year 1, Year 2" is what made the old one
    unreadable)."""
    import app.world as world
    return {"gender": gender, "group": group, "groups": groups, "year": year,
            "years": years,
            # `pin` is the year a link must CARRY to keep the reader where they are.
            # Browsing the latest season it is None, so URLs stay clean and follow the
            # world forward as it advances; browsing an ARCHIVED season it is that year,
            # so drilling into a program shows the roster, schedule, record and finish
            # of the season on screen instead of silently falling back to the newest.
            "pin": year if (years and year != years[0]) else None,
            "season_year": season_year or (world.BASE_YEAR + (year or 0) + 1),
            "season_years": {y: world.BASE_YEAR + y + 1 for y in years}}


#: A State FINISH, abbreviated for a dense table (owner's set, 2026-08):
#: CHAMP · F · SF · QF · OF · R1 · QUAL. The full label always rides along as a title.
_FINISH_SHORT = {"Champion": "CHAMP", "Runner-up": "F",
                 "Semifinalist": "SF", "Quarterfinalist": "QF",
                 "Octofinalist": "OF"}


def _finish_short(label: str) -> str:
    """`label` for a narrow column. Always render the full text as a title beside it.

    The two "Round of N" labels are different ROUNDS: every field converges on the
    same 24-team main draw at the Octofinals, so a team still alive above 24 went out
    in the QUALIFIERS and one out at 24 went out in the First Round. That holds at any
    field size, which is why this needs no field parameter."""
    if not label:
        return ""
    if label in _FINISH_SHORT:
        return _FINISH_SHORT[label]
    if label.startswith("Round of "):
        n = label[9:].strip()
        return "QUAL" if (n.isdigit() and int(n) > 24) else "R1"
    return label


def jhsaa_scope_view(seed: int, gender: str, group: str | None = None,
                     year: int | None = None) -> dict:
    """Just the section scope — for a JHSAA page that edits SETTINGS rather than
    reading a season, so it needs the header's gender/class/season rail and nothing
    archived. Costs one cheap year lookup instead of a whole hub view."""
    import app.jhsaa as jh
    import app.world as world
    w = world.get_or_create(seed)
    g = _jh_g(gender)
    years = world.jhsaa_years(w["id"], g)
    yr = (years[0] if years else w["year"]) if year is None else year
    grp = group if group in jh.GROUPS else jh.GROUPS[0]
    return {"gender": g, "group": grp, "groups": list(jh.GROUPS), "year": yr,
            "years": years,
            "scope": _jh_scope(g, grp, list(jh.GROUPS), yr, years, None, None)}


def jhsaa_view(seed: int, gender: str, group: str | None = None,
               year: int | None = None) -> dict:
    """The JHSAA hub — the state high-school home, organised around the season being
    played rather than around the trophies it handed out.

    The dominant object is the selected classification's STATE TOURNAMENT; the awards
    are compact panels beside it; standings, districts and the program ranking sit
    below. Empty (`{"ready": False}`) until the rung has run for that year."""
    import app.jhsaa as jh
    import app.world as world          # local, matching the rest of this module
    w = world.get_or_create(seed)
    g = _jh_g(gender)
    years = world.jhsaa_years(w["id"], g)
    yr = (years[0] if years else w["year"]) if year is None else year
    arc = world.get_jhsaa(w["id"], yr, g)
    if not arc:
        return {"ready": False, "gender": g, "year": yr, "groups": list(jh.GROUPS),
                "group": group if group in jh.GROUPS else jh.GROUPS[0],
                "years": years,
                "scope": _jh_scope(g, group if group in jh.GROUPS else jh.GROUPS[0],
                                   list(jh.GROUPS), yr, years, None, None)}
    grp = group if group in jh.GROUPS else jh.GROUPS[0]
    schools = _jh_schools(g)
    br = (arc.get("brackets") or {}).get(grp) or {}
    ranking = world.jhsaa_group_ranking(arc, grp)
    seeds = _jh_seeds(br)

    # The hub carries a district INDEX, not nine stacked standings tables. Full
    # standings for ~110 schools is the longest thing on the page and none of it is
    # what the hub is for; it lives one click away on the district's own page, where
    # it sits behind a tab beside the head-to-head grid.
    districts = []
    for d, rows in sorted(((arc.get("standings") or {}).get(grp) or {}).items()):
        table = [{**_jh_deco(schools, r["school"], 26), "record": r.get("record", ""),
                  "drecord": r.get("drecord", ""), "place": r.get("place", 0),
                  "pf": r.get("pf") or 0.0, "pa": r.get("pa") or 0.0,
                  "seed": seeds.get(r["school"], 0)} for r in rows]
        if not table:
            continue
        districts.append({"district": d, "members": len(table),
                          "champion": table[0],
                          "qualifiers": [r for r in table if r["seed"]],
                          "runner_up": table[1] if len(table) > 1 else None})

    rank_by = {r["school"]: r["rank"] for r in ranking}
    return {
        "ready": True, "gender": g, "year": yr, "years": years,
        "season_year": arc.get("season_year", world.jhsaa_season_year(w)),
        "group": grp, "groups": list(jh.GROUPS),
        "scope": _jh_scope(g, grp, list(jh.GROUPS), yr, years,
                           arc.get("season_year"), arc),
        # --- the state tournament, the page's dominant object ---
        "state": {**_jh_final_four(br, schools),
                  "field": br.get("field", []), "field_n": len(br.get("field") or ()),
                  "rounds": [{**rd, "games": [
                      {**gm, "home_deco": _jh_deco(schools, gm["home"], 20),
                       "away_deco": _jh_deco(schools, gm["away"], 20),
                       "home_seed": seeds.get(gm["home"], 0),
                       "away_seed": seeds.get(gm["away"], 0)}
                      for gm in rd["games"]]}
                      for rd in world.jhsaa_state_rounds(br)],
                  "canvas": _bracket_canvas(_jh_bracket_cols(br, schools, keep=3),
                                            card_w=196, card_h=54, gutter=40,
                                            leaf_gap=12)},
        # --- awards, as short scannable panels beside it ---
        "poy": (arc.get("awards", {}).get(grp) or {}).get("poy"),
        "all_state": (arc.get("awards", {}).get(grp) or {}).get("all_state", []),
        "all_district": (arc.get("all_district", {}) or {}).get(grp, {}),
        "top": [{**_jh_deco(schools, r["school"], 24), **r} for r in ranking[:12]],
        "districts": districts,
        "rank_by": rank_by,
        "champions": {gp: _jh_deco(schools, nm, 22)
                      for gp, nm in (arc.get("champions") or {}).items() if nm},
    }


def jhsaa_rankings_view(seed: int, gender: str, group: str | None = None,
                        year: int | None = None, sort: str | None = None,
                        dir: str = "desc") -> dict:
    """The whole classification, ranked — the association's own order, top to bottom.

    `jhsaa_group_ranking` already returns EVERY program in the class; the hub simply
    showed the first twelve of it beside the bracket, which is the right length for a
    rail panel and the wrong one for the question "where does my 3-19 program actually
    sit?". Same computation, no cut, on a page of its own — the college league's
    rankings surface, and the one oregontennis.org publishes.

    The index is read back off the archive, never recomputed, so this ranking and the
    seeds drawn from it cannot disagree (`world.jhsaa_group_ranking`)."""
    import app.jhsaa as jh
    import app.world as world
    w = world.get_or_create(seed)
    g = _jh_g(gender)
    years = world.jhsaa_years(w["id"], g)
    yr = (years[0] if years else w["year"]) if year is None else year
    arc = world.get_jhsaa(w["id"], yr, g)
    grp = group if group in jh.GROUPS else jh.GROUPS[0]
    scope = _jh_scope(g, grp, list(jh.GROUPS), yr, years,
                      (arc or {}).get("season_year"), arc)
    if not arc:
        return {"ready": False, "gender": g, "year": yr, "years": years,
                "group": grp, "groups": list(jh.GROUPS), "scope": scope}
    schools = _jh_schools(g)
    br = (arc.get("brackets") or {}).get(grp) or {}
    seeds = _jh_seeds(br)
    toc_field = set((arc.get("toc") or {}).get("field") or ())
    rows = world.jhsaa_group_ranking(arc, grp)
    new_rows = []
    for r in rows:
        result = world.jhsaa_state_result(br, r["school"])
        new_rows.append({**_jh_deco(schools, r["school"], 24), **r,
                         # Suffix dropped for the table, full name on hover and in
                         # the link: the column is narrow and the names run long.
                         "district_short": jh.district_short(r.get("district", "")),
                         "seed": seeds.get(r["school"], 0),
                         "state_finish": result["finish"],
                         # Abbreviated for the table; the full label rides along as a
                         # title so nothing is lost.
                         "state_finish_short": _finish_short(result["finish"]),
                         # Sort key only — negated `place` (1 = champion) so this
                         # column's click-sort shares the generic "desc = best first"
                         # convention every other numeric column uses, without
                         # displaying a negative number anywhere (the template still
                         # renders `state_finish`, the label).
                         "state_finish_rank": -result["place"] if result["place"] else None,
                         "toc": r["school"] in toc_field})
    rows = new_rows
    # ‼️ DISPLAY ORDER ONLY. `r["rank"]` is the archived TOSS position — it is what
    # seeded the postseason, and it never moves, whatever the table is sorted by. A
    # click-sort just reorders the ROWS the page draws; sorting by "Doubles Shift" and
    # seeing #1 sit fourth in the list is correct, not a bug — that program is still
    # TOSS's #1, it just isn't the biggest doubles-shift story this year. Missing
    # values (no showcase duals, a season archived before ATR/format data existed)
    # sort LAST regardless of direction, so an empty column never reads as a zero.
    SORTABLE = {"rank": "rank", "school": "school", "district": "district",
               "record": "pct", "place": "place", "pf": "pf", "pa": "pa",
               "pi": "pi", "atr": "atr", "seed": "seed",
               "state_finish": "state_finish_rank",
               "sc_n": "sc_n", "fmt_pts": "fmt_pts", "dbl_pts": "dbl_pts"}
    key = SORTABLE.get(sort)
    if key:
        # "empty" isn't always `None` — an unqualified team's seed is 0 and a team
        # that missed State has no `state_finish_rank` (place 0), neither of which
        # should sort as though it beat every real value on an ascending click.
        def _empty(r):
            v = r.get(key)
            return v is None or (key == "seed" and not v)
        present = [r for r in rows if not _empty(r)]
        missing = [r for r in rows if _empty(r)]
        present.sort(key=lambda r: r[key], reverse=(dir != "asc"))
        rows = present + missing
    return {
        "ready": True, "gender": g, "year": yr, "years": years,
        "group": grp, "groups": list(jh.GROUPS), "scope": scope,
        "season_year": arc.get("season_year", world.jhsaa_season_year(w)),
        # `rated` says whether the order is the archived TOSS index or the pre-TOSS
        # win-rate fallback, so the page can label the column it is actually sorting on
        # instead of printing a blank where a number belongs.
        "rated": all(r.get("pi") is not None for r in rows) if rows else False,
        "qualified": sum(1 for r in rows if seeds.get(r["school"])),
        "sort": sort or "", "dir": dir,
        "rows": rows,
    }


def jhsaa_honors_view(seed: int, gender: str, group: str | None = None,
                      year: int | None = None) -> dict:
    """The classification's postseason AWARDS, on a page of their own.

    Player of the Year, the numbered All-State teams and Honorable Mention, then
    every district's All-District team and District Player of the Year — the
    whole slate `jhsaa_awards.season_awards` selected, read straight back off the
    archive so a past season shows exactly what it awarded at the time.

    It used to be scattered: POY and a six-name All-State list sat in a rail
    panel on the hub, and All-District only ever appeared one school at a time on
    program pages. There was nowhere to see who the association actually
    honoured, and nothing to page back through year over year."""
    import app.jhsaa as jh
    import app.jhsaa_awards as jaw
    import app.world as world
    w = world.get_or_create(seed)
    g = _jh_g(gender)
    years = world.jhsaa_years(w["id"], g)
    yr = (years[0] if years else w["year"]) if year is None else year
    arc = world.get_jhsaa(w["id"], yr, g) or {}
    grp = group if group in jh.GROUPS else jh.GROUPS[0]
    scope = _jh_scope(g, grp, list(jh.GROUPS), yr, years,
                      arc.get("season_year"), arc)
    schools = _jh_schools(g)
    aw = (arc.get("awards") or {}).get(grp) or {}
    ad = (arc.get("all_district") or {}).get(grp) or {}

    def deco(r):
        # ‼️ Take the CREST ONLY, never the whole deco. `_jh_deco` describes a
        # SCHOOL and its dict is keyed `name` — splatting it over an award row
        # overwrote every selection's player name with the school's, so the
        # All-State teams rendered as a list of schools. Every other caller
        # splats a deco over a row that IS a school, where `name` colliding is
        # correct; this is the one place the row is a PERSON.
        return {**r, "mark": _jh_deco(schools, r.get("school", ""), 20)["mark"]}

    # Pre-SOP seasons archived a flat six-name `all_state` and no tiers; show it
    # as a single unnamed team rather than an empty page.
    tiers = aw.get("teams") or ([{"name": "All-State", "players": aw["all_state"]}]
                                if aw.get("all_state") else [])
    return {
        "ready": bool(arc), "gender": g, "year": yr, "years": years,
        "group": grp, "groups": list(jh.GROUPS), "scope": scope,
        "season_year": arc.get("season_year", world.jhsaa_season_year(w)),
        # Sizes come off the awards module so the page cannot state a shape the
        # selector does not use.
        "team_singles": jaw.TEAM_SINGLES, "team_doubles": jaw.TEAM_DOUBLES,
        "ar_tier2_min": jaw.AR_TIER2_MIN_PROGRAMS,
        "ar_hm_min": jaw.AR_HM_MIN_PROGRAMS,
        # The FLIGHT CHECK is archived with the awards, never recomputed — it is
        # the record of what the selector produced, so re-deriving it from a
        # later code version would be a second source of truth for a decision
        # the season already made.
        # The state/district halves are the class's own; the REGION half hangs off
        # the season, because All-Region is class-blind.
        "flight_check": {**(aw.get("flight_check") or {}),
                         **({"region": arc["all_region_flight_check"]}
                            if arc.get("all_region_flight_check") else {})},
        "poy": deco(aw["poy"]) if aw.get("poy") else None,
        "teams": [{"name": t["name"], "players": [deco(r) for r in t["players"]]}
                  for t in tiers],
        "honorable_mention": [deco(r) for r in aw.get("honorable_mention") or ()],
        # ‼️ ONE TEAM PER REGION, ACROSS EVERY CLASSIFICATION (owner rule
        # 2027-08) — there is no 7A All-Region team, there is a Gold Valley
        # All-Region team. So it is read off the SEASON and is the same whichever
        # classification is on screen; `aw` is the fallback for seasons archived
        # while it still lived inside a class's slate.
        # A region's value is a LIST OF TIERS — one unnumbered team in a small
        # region, First and Second where the region is big enough to warrant it
        # (`jaw.AR_TIER2_MIN_PROGRAMS`).
        # A region carries its TIERS (one unnumbered team in a small region, a
        # First and a Second where it is big enough — `jaw.AR_TIER2_MIN_PROGRAMS`)
        # and, in the one region big enough to warrant it, an Honorable Mention.
        "regions": sorted(
            ({"region": rn, "programs": reg.get("programs") or 0,
              "tiers": [{"name": t.get("name") or "",
                         "players": [deco(r) for r in t["players"]]}
                        for t in reg["tiers"]],
              "honorable_mention": [deco(r) for r in reg.get("honorable_mention") or ()],
              "n": sum(1 for _ in jaw.region_rows({rn: reg}))}
             for rn, reg in (arc.get("all_region")
                             or aw.get("all_region") or {}).items()),
            key=lambda x: x["region"]),
        "districts": sorted(
            ({"district": d,
              "poy": deco((aw.get("district_poy") or {}).get(d))
                     if (aw.get("district_poy") or {}).get(d) else None,
              "players": [deco(r) for r in rows]}
             for d, rows in ad.items()), key=lambda x: x["district"]),
    }


def jhsaa_bracket_view(seed: int, gender: str, group: str | None = None,
                       year: int | None = None) -> dict:
    """The full state draw on its own surface — the same server-positioned tree the
    NCAA bracket and the Preseason NIT use (`_bracket_canvas` + `templates/_bracket.html`),
    never a third bracket implementation."""
    import app.jhsaa as jh
    import app.world as world
    w = world.get_or_create(seed)
    g = _jh_g(gender)
    years = world.jhsaa_years(w["id"], g)
    yr = (years[0] if years else w["year"]) if year is None else year
    arc = world.get_jhsaa(w["id"], yr, g)
    grp = group if group in jh.GROUPS else jh.GROUPS[0]
    if not arc:
        return {"ready": False, "gender": g, "year": yr, "group": grp,
                "groups": list(jh.GROUPS), "years": years,
                "scope": _jh_scope(g, grp, list(jh.GROUPS), yr, years, None, None)}
    schools = _jh_schools(g)
    br = (arc.get("brackets") or {}).get(grp) or {}
    seeds = _jh_seeds(br)
    main_br, qual_br = _jh_split_state(br)

    def _deco_rounds(d, sseeds):
        return [{**rd, "games": [
            {**gm, "home_deco": _jh_deco(schools, gm["home"], 20),
             "away_deco": _jh_deco(schools, gm["away"], 20),
             "home_seed": sseeds.get(gm["home"], 0),
             "away_seed": sseeds.get(gm["away"], 0)}
            for gm in rd["games"]]} for rd in world.jhsaa_state_rounds(d)]

    # Road to State: one collapsed fold per pre-state stage, Zonals first (closest
    # to State) down to Sectionals. These duals are visible NOWHERE else — the
    # bracket tree only draws the 16-team State field — while the State bracket's
    # own results are exactly what the tree already shows, so this section carries
    # the pre-state stages instead of repeating them. Seeds come off each stage's
    # OWN field (a team's Sectional, Ward and Regionals seeds are three different
    # numbers). Empty on archives from before the ladder existed.
    stages = []
    # The RECOVERY rounds sit closest to State, so their folds come first
    # (the list is reverse-chronological: the stage that fed State on top).
    for key in ("conference", "semi_conference", "divisional", "semi_state",
                "super_regional"):
        d = (arc.get(key) or {}).get(grp) or {}
        if d.get("rounds") and d["rounds"][0]:
            # Recovery rounds are BYELESS BY CONSTRUCTION — each pairs its entire
            # field — so this is empty on every season played since, and kept only
            # because archives from the old cut-shaped rounds still carry byes and
            # a path that showed none was how a lucky loser looked like it jumped
            # from a Regional loss straight into State. A footnote on the stage,
            # not the schedule, and no counters (owner rule 2027-08).
            sseeds = _jh_seeds(d)
            played = {nm for rd in d["rounds"] for gm in rd
                      for nm in (gm["home"], gm["away"])}
            byes = [{"name": nm} for nm in (d.get("field") or ())
                    if nm not in played]
            for rd in _deco_rounds(d, sseeds):
                stages.append({"name": rd["name"], "rounds": [rd], "byes": byes})
    pre = (arc.get("prestate") or {}).get(grp) or {}
    if pre.get("rounds"):
        for rd in reversed(_deco_rounds(pre, _jh_seeds(pre))):
            stages.append({"name": rd["name"], "rounds": [rd]})
    ward = (arc.get("wards") or {}).get(grp) or {}
    if ward.get("rounds"):
        stages.append({"name": "Wards", "rounds": _deco_rounds(ward, _jh_seeds(ward))})
    sec = (arc.get("sectionals") or {}).get(grp) or {}
    if sec.get("rounds"):
        # Sectionals and Areas are separate folds — the last archived round is the
        # one named Sectionals, anything before it is Areas (`jhsaa.run_sectional`).
        deco = _deco_rounds(sec, _jh_seeds(sec))
        stages.append({"name": "Sectionals", "rounds": deco[-1:]})
        if len(deco) > 1:
            stages.append({"name": "Areas", "rounds": deco[:-1]})
    return {
        "ready": True, "gender": g, "year": yr, "years": years, "group": grp,
        "groups": list(jh.GROUPS),
        "season_year": arc.get("season_year", world.jhsaa_season_year(w)),
        "scope": _jh_scope(g, grp, list(jh.GROUPS), yr, years, arc.get("season_year"), arc),
        **_jh_final_four(br, schools),
        "field": [{**_jh_deco(schools, nm, 22), "seed": seeds[nm]}
                  for nm in (br.get("field") or ())],
        "field_n": len(br.get("field") or ()),
        # An expanded field renders as TWO trees — the main draw and the
        # qualifying that fed it — because a fresh draw sits between them and a
        # single positional tree would invent links (see `_jh_split_state`).
        "canvas": _bracket_canvas(_jh_bracket_cols(main_br, schools),
                                  card_w=206, card_h=56, gutter=44, leaf_gap=12),
        "qual_canvas": (_bracket_canvas(_jh_bracket_cols(qual_br, schools),
                                        card_w=206, card_h=56, gutter=44,
                                        leaf_gap=12) if qual_br else None),
        "rounds": _deco_rounds(br, seeds),
        "stages": stages,
    }


def jhsaa_school_view(seed: int, gender: str, school: str,
                      year: int | None = None) -> dict:
    """One JHSAA program, as a PROGRAM page: who they are, how this season went, the
    card match by match, the roster that played it, and the season ledger underneath.

    `year` selects an archived season; without it you get the latest one. Either way
    the roster is rebuilt for THAT season's year, so an archived page shows the team
    that actually played it rather than today's."""
    import app.jhsaa as jh
    import app.jhsaa_awards as jaw
    import app.world as world
    w = world.get_or_create(seed)
    g = _jh_g(gender)
    sc = next((s for s in jh.load_schools(g) if s.name == school), None)
    if sc is None:
        return {"found": False, "school": school, "gender": g}
    years = world.jhsaa_years(w["id"], g)
    yr = (years[0] if years else w["year"]) if year is None else year
    arc = world.get_jhsaa(w["id"], yr, g)
    salt = world.active_salt(seed)
    schools = _jh_schools(g)
    hist = world.jhsaa_school_history(w["id"], g, school)
    season = next((s for s in hist["seasons"] if s["year"] == yr), None)
    # The season's own year drives the roster identity — the grad year the hand-off
    # uses, never the world index. See world.run_jhsaa.
    season_year = ((arc or {}).get("season_year")
                   or (season or {}).get("season_year") or world.jhsaa_season_year(w))
    sched = world.jhsaa_schedule(w["id"], yr, g, school)
    dates = _jh_dates(sched, season_year,
                      world.jhsaa_match_dates(w["id"], yr, g, season_year))
    lines = _jh_line_records(sched)
    roster = jh.build_roster(sc, season_year, salt)
    br = (arc or {}).get("brackets", {}).get(sc.group) or {}
    seeds = _jh_seeds(br)
    # Every stage is its own draw with its own seed order — a team's Sectional seed,
    # Ward seed, Regionals seed, State seed and TOC seed are five different numbers —
    # so each dual's opponent seed comes off the field of the stage it was played in.
    toc_seeds = _jh_seeds((arc or {}).get("toc") or {})
    sec_arc = (arc or {}).get("sectionals", {}).get(sc.group) or {}
    sec_seeds = _jh_seeds(sec_arc)
    ward_seeds = _jh_seeds((arc or {}).get("wards", {}).get(sc.group) or {})
    pre_seeds = _jh_seeds((arc or {}).get("prestate", {}).get(sc.group) or {})
    sr_seeds = _jh_seeds((arc or {}).get("super_regional", {}).get(sc.group) or {})
    ss_seeds = _jh_seeds((arc or {}).get("semi_state", {}).get(sc.group) or {})
    dv_seeds = _jh_seeds((arc or {}).get("divisional", {}).get(sc.group) or {})
    sc_seeds = _jh_seeds((arc or {}).get("semi_conference", {}).get(sc.group) or {})
    cf_seeds = _jh_seeds((arc or {}).get("conference", {}).get(sc.group) or {})
    # A non-district dual is an INVITATIONAL (owner rule 2027-08) — that is what the
    # association calls the duals a program arranges outside its league, and the card
    # should say what they are rather than what they are not. "Non-district" is still
    # the right word for the SCHEDULING rule (the allowance, the matcher, the district
    # guardrail); it was only ever wrong as a label on a match.
    _KIND = {"showcase_pod": "SHOWCASE", "showcase_tiered": "SHOWCASE",
             "toc": "TOC", "state": "STATE", "conference": "CONFERENCE",
             "semi_conference": "SEMI-CONFERENCE",
             "divisional": "DIVISIONAL", "semi_state": "SEMI-STATE",
             "super_regional": "SUPER REGIONAL", "zonal": "ZONAL",
             "regional": "REGIONAL", "ward": "WARD", "sectional": "SECTIONAL"}
    # The sectional PHASE holds every cut round, but a multi-round Sectionals
    # OPENS WITH AREAS (owner rule — jhsaa.run_sectional): only the last round is
    # the one named Sectionals. The archive's round_names carry the split, so an
    # Area dual is recognised by its pairing sitting in an "Areas" round — never
    # by position in the schedule. Old archives (round_names all "Sectionals")
    # have no Areas rounds and keep the SECTIONAL tag everywhere.
    sec_names = sec_arc.get("round_names") or ()
    area_pairs = {frozenset((gm.get("home"), gm.get("away")))
                  for i, games in enumerate(sec_arc.get("rounds") or ())
                  if i < len(sec_names) and sec_names[i] == "Areas"
                  for gm in games}

    def _kind(d):
        k = _KIND.get(d["phase"], "DIST" if d["district"] else "INVITE")
        if k == "SECTIONAL" and frozenset((school, d["opp"])) in area_pairs:
            k = "AREA"
        return k
    kinds = [_kind(d) for d in sched]
    # A showcase dual names its event beside the tag, the way a State dual names its
    # bracket round — the two showcases are a different length, a different scoring
    # format and a different weekend, and the phase is what tells them apart.
    # The State/TOC bracket ROUND a dual belongs to, so the card can say "R32"
    # or "SF" beside the STATE tag rather than tagging five different rounds
    # identically. Read off the archived bracket (one appearance per round), not
    # inferred from the schedule's position.
    _SHORT = {"Championship": "Final", "Semifinals": "SF", "Quarterfinals": "QF",
              "Octofinals": "Octas", "Qualifiers Round": "Qualies",
              "First Round": "R1"}

    def _round_of(bracket):
        out = {}
        for rd in world.jhsaa_state_rounds(bracket or {}):
            nm = _SHORT.get(rd["name"]) or (f"R{rd['alive']}" if rd["name"].startswith("Round of")
                                            else rd["name"])
            for gm in rd["games"]:
                if school in (gm.get("home"), gm.get("away")):
                    other = gm["away"] if gm["home"] == school else gm["home"]
                    out[other] = nm
        return out
    state_round = _round_of(br)
    toc_round = _round_of((arc or {}).get("toc") or {})

    _SEEDS = {"TOC": toc_seeds, "STATE": seeds, "CONFERENCE": cf_seeds,
              "SEMI-CONFERENCE": sc_seeds,
              "DIVISIONAL": dv_seeds,
              "SEMI-STATE": ss_seeds,
              "SUPER REGIONAL": sr_seeds, "ZONAL": pre_seeds,
              "REGIONAL": pre_seeds, "WARD": ward_seeds, "SECTIONAL": sec_seeds,
              "AREA": sec_seeds}

    awards = ((arc or {}).get("awards") or {}).get(sc.group) or {}
    honor_pids = {}
    # ‼️ A DOUBLES AWARD ROW HONOURS TWO ATHLETES (owner, 2027-08) — doubles
    # honours go to PAIRINGS. `jaw.row_pids` is the one place that knows how many
    # people a row names; matching on `row["pid"]` badged half of every pairing
    # and silently left the partner's roster line blank.
    def badge(row, label):
        if row and row.get("school") == school:
            for p in jaw.row_pids(row):
                honor_pids.setdefault(p, []).append(label)

    badge(awards.get("poy"), f"{sc.group} Player of the Year")
    for r in awards.get("all_state", ()):
        badge(r, "All-State")
    for _rn, tier, r in jaw.region_rows((arc or {}).get("all_region")
                                        or awards.get("all_region")):
        badge(r, f"All-Region {tier}".strip())
    for dname, rs in (((arc or {}).get("all_district") or {}).get(sc.group) or {}).items():
        for r in rs:
            badge(r, "All-District")

    return {
        "found": True, "school": school, "gender": g, "year": yr, "years": years,
        "season_year": season_year, "is_current": bool(years) and yr == years[0],
        "scope": _jh_scope(g, sc.group, list(jh.GROUPS), yr, years, season_year, arc),
        # --- identity ---
        "mark": jh.mark(sc, 76), "city": sc.city, "county": sc.county, "area": sc.area,
        "locality": sc.locality,
        "classification": sc.classification, "group": sc.group, "district": sc.district,
        "mascot": sc.mascot, "enrollment": sc.enrollment, "private": sc.private,
        "colors": sc.colors,
        # --- this season ---
        "season": season,
        "record": (season or {}).get("record") or "0-0",
        "district_record": (season or {}).get("district_record") or "0-0",
        "place": (season or {}).get("place", 0),
        "state_rank": (season or {}).get("state_rank", 0),
        "state_seed": seeds.get(school, 0),
        "state_finish": (season or {}).get("state_finish", ""),
        "made_toc": (season or {}).get("made_toc", False),
        "toc_seed": (season or {}).get("toc_seed", 0),
        "toc_finish": (season or {}).get("toc_finish", ""),
        "schedule": [{**d, "date": dates[i], "lines": _jh_reported_lines(d),
                      "kind": k, "opp_deco": _jh_deco(schools, d["opp"], 22),
                      "opp_seed": _SEEDS.get(k, {}).get(d["opp"], 0),
                      # ‼️ ONLY a BRACKET ROUND earns the second chip (owner, 2026-08).
                      # It carried the showcase KIND (Pod/Tiered) and the early
                      # window's 5S/2D shape too, and both restated what the reader
                      # already knew from the primary tag and the season: "I know what
                      # an invite and a showcase are, and I know all programs' early
                      # season games use 5/2". A chip that repeats its own row is noise.
                      # R32 / QF / SF stay, because which round a State dual was cannot
                      # be read off the row.
                      "round": (state_round if k == "STATE" else
                                toc_round if k == "TOC" else {}).get(d["opp"], "")}
                     for i, (d, k) in enumerate(zip(sched, kinds))],
        "roster": [{"pid": p.pid, "name": p.name, "grade": p.grade,
                    "ovr": round(p.current_overall(), 1),
                    # Talent/potential visibility (owner request) — the ceiling and
                    # star rating were already computed by `Prospect` (the same
                    # methods the college recruit board reads), just never surfaced
                    # here. Pure display: no new simulation.
                    "ceiling": round(p.ceiling_overall(), 1),
                    "stars": p.star_rating(),
                    "str": p.str_value(),
                    "singles": "{}-{}".format(*lines.get(p.name, {}).get("s", (0, 0))),
                    "doubles": "{}-{}".format(*lines.get(p.name, {}).get("d", (0, 0))),
                    "honors": honor_pids.get(p.pid, [])}
                   for p in roster],
        "honors": (season or {}).get("honors", []),
        "history": hist,
    }


def jhsaa_district_view(seed: int, gender: str, group: str, district: str,
                        year: int | None = None) -> dict:
    """A district — high school's conference. Member schools with their standing, the
    league's own results, its champion, its All-District team, and the way through to
    every program in it.

    A district is identified by (CLASSIFICATION, name) and never by name alone: the
    JHSAA reuses its geographic district names at every level, so "Halbrook Basin
    District" is five different leagues in five different classes. The archive is keyed
    `standings[group][district]` for exactly that reason — key it the same way here or
    a 7A page quietly serves the 3A-1A league of the same name."""
    import app.jhsaa as jh
    import app.world as world
    w = world.get_or_create(seed)
    g = _jh_g(gender)
    grp = group
    members = [s for s in jh.load_schools(g)
               if s.district == district and s.group == grp]
    if not members:
        return {"found": False, "district": district, "group": grp, "gender": g}
    years = world.jhsaa_years(w["id"], g)
    yr = (years[0] if years else w["year"]) if year is None else year
    arc = world.get_jhsaa(w["id"], yr, g)
    schools = _jh_schools(g)
    br = ((arc or {}).get("brackets") or {}).get(grp) or {}
    seeds = _jh_seeds(br)
    rows = (((arc or {}).get("standings") or {}).get(grp) or {}).get(district) or []
    ranking = {r["school"]: r["rank"] for r in world.jhsaa_group_ranking(arc or {}, grp)}
    names = {s.name for s in members}

    standings = [{**_jh_deco(schools, r["school"], 26), "record": r.get("record", ""),
                  "drecord": r.get("drecord", ""), "place": r.get("place", 0),
                  "pf": r.get("pf") or 0.0, "pa": r.get("pa") or 0.0,
                  "rank": ranking.get(r["school"], 0), "seed": seeds.get(r["school"], 0),
                  "state_finish": world.jhsaa_state_result(br, r["school"])["finish"]}
                 for r in rows]
    # League results: read each member's card once and keep the duals played INSIDE the
    # district, de-duplicated by taking only the home side's copy of each meeting.
    results = []
    for s in members:
        for i, d in enumerate(world.jhsaa_schedule(w["id"], yr, g, s.name)):
            if d.get("district") and d.get("home") and d["opp"] in names:
                results.append({"home": s.name, "away": d["opp"], "pf": d["pf"],
                                "pa": d["pa"], "won": d["won"],
                                "home_deco": _jh_deco(schools, s.name, 20),
                                "away_deco": _jh_deco(schools, d["opp"], 20),
                                "order": i})
    results.sort(key=lambda r: (r["order"], r["home"]))
    # A 12-team double round-robin is 132 duals — as a flat list that is the longest,
    # least readable thing on the page. The league's shape is a HEAD-TO-HEAD GRID:
    # every team against every other, the season series in the cell. Columns are the
    # standings positions, so the header stays narrow however long the names are.
    series: dict = {}
    for r in results:
        a, b = r["home"], r["away"]
        series.setdefault((a, b), [0, 0])[0 if r["won"] else 1] += 1
        series.setdefault((b, a), [0, 0])[1 if r["won"] else 0] += 1
    order = [r["name"] for r in standings]
    grid = []
    for row in standings:
        cells = []
        for i, opp in enumerate(order, 1):
            w, l = series.get((row["name"], opp), (0, 0))
            cells.append({"pos": i, "opp": opp, "self": opp == row["name"],
                          "record": f"{w}-{l}" if (w or l) else "",
                          "swept": bool(w and not l), "lost": bool(l and not w)})
        grid.append({"team": row, "cells": cells})
    return {
        "found": True, "district": district, "gender": g, "group": grp, "year": yr,
        "years": years, "season_year": (arc or {}).get("season_year"),
        "scope": _jh_scope(g, grp, list(jh.GROUPS), yr, years,
                           (arc or {}).get("season_year"), arc),
        "ready": bool(arc), "standings": standings,
        "champion": standings[0] if standings else None,
        "results": results, "grid": grid,
        "all_district": (((arc or {}).get("all_district") or {}).get(grp) or {}).get(district, []),
        "members": [_jh_deco(schools, s.name, 26) for s in sorted(members, key=lambda s: s.name)],
        "qualifiers": [r for r in standings if r["seed"]],
        "peers": sorted({s.district for s in jh.load_schools(g) if s.group == grp}),
    }


def jhsaa_districts_view(seed: int, gender: str, group: str | None = None,
                         year: int | None = None) -> dict:
    """Every district in one classification — the way into the league layer, so high
    school has the browse structure the college side gets from its conferences."""
    import app.jhsaa as jh
    import app.world as world
    w = world.get_or_create(seed)
    g = _jh_g(gender)
    grp = group if group in jh.GROUPS else jh.GROUPS[0]
    years = world.jhsaa_years(w["id"], g)
    yr = (years[0] if years else w["year"]) if year is None else year
    arc = world.get_jhsaa(w["id"], yr, g)
    schools = _jh_schools(g)
    br = ((arc or {}).get("brackets") or {}).get(grp) or {}
    seeds = _jh_seeds(br)
    rows = []
    for dname, members in sorted(jh.districts(g, grp).items()):
        table = (((arc or {}).get("standings") or {}).get(grp) or {}).get(dname) or []
        champ = table[0] if table else None
        rows.append({
            "district": dname, "members": len(members),
            "champion": _jh_deco(schools, champ["school"], 24) if champ else None,
            "record": (champ or {}).get("record", ""),
            "drecord": (champ or {}).get("drecord", ""),
            "qualifiers": [{**_jh_deco(schools, r["school"], 20), "seed": seeds[r["school"]]}
                           for r in table if r["school"] in seeds],
        })
    return {"ready": bool(arc), "gender": g, "group": grp, "groups": list(jh.GROUPS),
            "year": yr, "years": years,
            "season_year": (arc or {}).get("season_year", world.jhsaa_season_year(w)),
            "scope": _jh_scope(g, grp, list(jh.GROUPS), yr, years,
                               (arc or {}).get("season_year")),
            "districts": rows}


def jhsaa_player_view(seed: int, gender: str, school: str, pid: str) -> dict:
    """One high-school player's whole career at a program: four seasons, what they
    did in each, and the honours that came with them.

    Resolved by PID, not by name — a pid is stable across all four years (it keys on
    the year the player entered and their seat), so it survives two players sharing a
    name and it matches the award rows straight off. Careers are rebuilt rather than
    stored, which is why an archived season can show the team that played it."""
    import app.jhsaa as jh
    import app.world as world
    w = world.get_or_create(seed)
    g = _jh_g(gender)
    sc = next((s for s in jh.load_schools(g) if s.name == school), None)
    if sc is None:
        return {"found": False, "school": school, "gender": g}
    salt = world.active_salt(seed)
    years = world.jhsaa_years(w["id"], g)
    # The school's ledger is read ONCE and indexed by year. Reading it inside the loop
    # made the page quadratic in seasons — every year re-walking every year's archive.
    team_by_year = {r["year"]: r
                    for r in world.jhsaa_school_seasons(w["id"], g, school)}
    seasons, player = [], None
    for yr in years:
        arc = world.get_jhsaa(w["id"], yr, g)
        if not arc:
            continue
        season_year = arc.get("season_year") or world.jhsaa_season_year(w)
        roster = jh.build_roster(sc, season_year, salt)
        hit = next((p for p in roster if p.pid == pid), None)
        if hit is None:
            continue                       # not enrolled that year (pre-9th, or graduated)
        player = player or hit
        sched = world.jhsaa_schedule(w["id"], yr, g, school)
        rec = _jh_line_records(sched).get(hit.name, {"s": [0, 0], "d": [0, 0]})
        slots = _jh_slot_records(sched).get(hit.name, {})
        aw = (arc.get("awards") or {}).get(sc.group) or {}
        # Both `all_district` and `all_region` live on the SEASON rather than in a
        # class's slate — the district because it is keyed (class, name), the
        # region because it is class-blind — so both are merged in here.
        honors = jh.honors_for(pid, {
            **aw,
            "all_district": (arc.get("all_district") or {}).get(sc.group, {}),
            "all_region": arc.get("all_region") or aw.get("all_region") or {},
        }, sc.group)
        team = team_by_year.get(yr)
        w_, l_ = rec["s"][0] + rec["d"][0], rec["s"][1] + rec["d"][1]
        seasons.append({
            "year": yr, "season_year": season_year, "grade": hit.grade,
            "class": {9: "Freshman", 10: "Sophomore", 11: "Junior", 12: "Senior"}
                     .get(hit.grade, str(hit.grade)),
            "ladder": next((i for i, p in enumerate(roster, 1) if p.pid == pid), 0),
            "ovr": round(hit.current_overall(), 1), "str": hit.str_value(),
            "singles": "{}-{}".format(*rec["s"]), "doubles": "{}-{}".format(*rec["d"]),
            "record": f"{w_}-{l_}", "wins": w_, "losses": l_,
            "honors": honors, "team": team, "slots": slots,
        })
    if player is None:
        return {"found": False, "school": school, "gender": g, "pid": pid}
    seasons.sort(key=lambda s: -s["year"])
    # Flight box wants OLDEST-first rows (freshman year on top, like the college
    # career-record box), so it's built before `seasons` above sorts newest-first
    # for the ledger table.
    flights = _jh_flight_box(sorted(seasons, key=lambda s: s["year"]))
    wins = sum(s["wins"] for s in seasons)
    losses = sum(s["losses"] for s in seasons)
    return {
        "found": True, "school": school, "gender": g, "pid": pid, "name": player.name,
        "hometown": player.hometown, "grade": player.grade,
        "ovr": round(player.current_overall(), 1),
        "ceiling": round(player.ceiling_overall(), 1),
        "stars": player.star_rating(),
        "mark": jh.mark(sc, 44), "group": sc.group, "district": sc.district,
        "classification": sc.classification, "city": sc.city,
        "locality": sc.locality,
        "scope": _jh_scope(g, sc.group, list(jh.GROUPS),
                           years[0] if years else 0, years, None, None),
        "seasons": seasons, "record": f"{wins}-{losses}", "wins": wins, "losses": losses,
        "honors": [h for s in seasons for h in s["honors"]], "flights": flights,
        # For the transfer form — the identity a `set_jhsaa_transfer` row is keyed on.
        "entry_year": player.entry_year,
        "transfer": jh.transfer_for(pid),
        # The grad year is what the college recruit board keys a Jefferson signee on,
        # so it is the hand-off between this career and the rest of the game.
        "grad_year": (seasons[0]["season_year"] + (12 - seasons[0]["grade"])
                      if seasons else None),
    }


def jhsaa_players_search(seed: int, gender: str, group: str = "All", district: str = "All",
                         grade: str = "All", sort: str = "ceiling", q: str = "") -> dict:
    """A searchable directory of the WHOLE JHSAA player pool — the high-school
    counterpart of `scout_intel.portal_search`. Reads the live current-season roster
    for every program (via `jh.build_roster`, the same call every roster page already
    makes — no resimulation, no new archive), so it's cheap and always in sync with
    the season on the field.

    `gender`: 'boys' | 'girls' | 'all'. `group`/`district` filter by classification/
    league; `grade` filters by class year; `q` matches name, school, or hometown.
    Sort by ceiling (potential), current OVR, stars, or name."""
    import app.jhsaa as jh
    rows = _jhsaa_all_players(seed, gender)

    if group != "All":
        rows = [r for r in rows if r["group"] == group]
    # Districts offered in the filter are scoped to the classification picked (a
    # district is (classification, name), same rule as everywhere else in JHSAA),
    # captured BEFORE the district filter itself narrows `rows` further.
    districts = ["All"] + sorted({r["district"] for r in rows})
    if district != "All":
        rows = [r for r in rows if r["district"] == district]
    if grade != "All":
        rows = [r for r in rows if str(r["grade"]) == str(grade)]
    if q:
        ql = q.strip().lower()
        rows = [r for r in rows if ql in r["name"].lower() or ql in r["school"].lower()
                or ql in (r["hometown"] or "").lower()]

    keys = {
        "ceiling": (lambda r: (r["ceiling"], r["ovr"]), True),
        "ovr": (lambda r: (r["ovr"], r["ceiling"]), True),
        "stars": (lambda r: (r["stars"], r["ovr"]), True),
        "name": (lambda r: r["name"].lower(), False),
        "school": (lambda r: (r["school"].lower(), r["name"].lower()), False),
    }
    key, rev = keys.get(sort, keys["ceiling"])
    rows.sort(key=key, reverse=rev)

    return {
        "gender": gender, "rows": rows, "total": len(rows),
        "groups": ["All"] + list(jh.GROUPS),
        "districts": districts,
        "grades": ["All", "9", "10", "11", "12"],
        "group": group, "district": district, "grade": grade, "sort": sort, "q": q,
    }


# A player is genuinely mismatched (JHSAA's version of the college "buried"
# board) when their ceiling clears their own classification's typical level by
# this much, and clears a floor so a raw 1A pool full of low numbers doesn't
# flag its own top player as a mismatch against nobody.
MISAPPLIED_MIN_GAP = 10.0
MISAPPLIED_MIN_CEILING = 55.0


# ‼️ P1 — the association-wide player CENSUS is cached, per gender, keyed on
# everything that can change it (CLAUDE.md's module-global-cache rules: compute
# into a local, publish, never `cache[key]` after a possible evict). Building it
# is CPU-bound and real (14.6k Boys players / 7.6s, 31.1k Both / 15.9s measured on
# a scratch world) — without a cache, the players directory, mismatch board and
# lineup lab each rebuild the WHOLE gender's rosters on every request, including
# every pagination click and filter change.
#
# Keyed per SINGLE gender ('boys'/'girls'), never 'all' — 'all' concatenates the
# two cached lists instead of building a third combined entry, so switching the
# gender filter back and forth never doubles the cache's memory or duplicates a
# build already paid for.
_JH_CENSUS_CACHE: dict[tuple, list[dict]] = {}


def _jhsaa_census_key(seed: int, g: str) -> tuple:
    """Resolved ONCE per call (never inside a per-school/per-player loop — the
    `jhsaa_playup_version()` fingerprint-in-a-loop trap this codebase already hit
    once). Everything that can change a roster's shape: the world's identity/year/
    salt (a new world or a year rollover ages every player), plus the three
    override tables `jh.build_roster` reads through (`jh.load_schools` bakes
    archetype/play-up into `School`, and a JHSAA transfer moves a player)."""
    import app.overrides as ov
    import app.world as world
    w = world.get_or_create(seed)
    salt = world.active_salt(seed)
    return (seed, g, w["id"], w["year"], salt,
            ov.jhsaa_archetype_version(), ov.jhsaa_playup_version(),
            ov.jhsaa_transfer_version())


def _jhsaa_build_census(seed: int, g: str) -> list[dict]:
    """The actual roster-build loop for one gender — only ever called on a cache
    miss."""
    import app.jhsaa as jh
    import app.world as world
    w = world.get_or_create(seed)
    salt = world.active_salt(seed)
    season_year = world.jhsaa_season_year(w)
    rows = []
    for sc in jh.load_schools(g):
        for p in jh.build_roster(sc, season_year, salt):
            rows.append({
                "pid": p.pid, "name": p.name, "grade": p.grade,
                "gender": g, "school": sc.name, "group": sc.group,
                "district": sc.district, "classification": sc.classification,
                "hometown": p.hometown,
                "ovr": round(p.current_overall(), 1),
                "ceiling": round(p.ceiling_overall(), 1),
                "stars": p.star_rating(),
            })
    return rows


def _jhsaa_census_for(seed: int, g: str) -> list[dict]:
    """The cached census for one gender ('boys'|'girls') — compute-then-publish,
    read with `.get()`, never `key in cache` + `cache[key]` (a sibling request can
    evict between the two)."""
    key = _jhsaa_census_key(seed, g)
    cached = _JH_CENSUS_CACHE.get(key)
    if cached is not None:
        return cached
    built = _jhsaa_build_census(seed, g)
    _JH_CENSUS_CACHE[key] = built
    return built


def _jhsaa_all_players(seed: int, gender: str) -> list[dict]:
    """Every rostered JHSAA player for `gender` ('boys'|'girls'|'all'), current
    season. Shared building block for the players directory, the talent-mismatch
    board and the lineup lab — one cached census per gender, no resimulation, same
    shape every time. Returns a fresh list (never the cached list object itself),
    so callers are free to sort/filter without mutating the cache."""
    genders = ("boys", "girls") if gender == "all" else (_jh_g(gender),)
    rows: list[dict] = []
    for g in genders:
        rows.extend(_jhsaa_census_for(seed, g))
    return rows


def jhsaa_misapplied_players(seed: int, gender: str, group: str = "All",
                             sort: str = "gap") -> dict:
    """Talent mismatches — the JHSAA analogue of the college Underplaced board (a
    D1-caliber player stuck in D3). JHSAA classifications ARE a real ladder here,
    same as `_TALENT`'s own division-shaped design (9A the deepest/strongest down
    to 1A) — `jh.GROUPS` is already ordered best to worst — so this reads exactly
    like the college check: is this player's CEILING better than a level they are
    NOT currently playing at? Comparing a player only to their own classification's
    average (the first cut of this) just finds "best fish in a small pond" and
    missed the actual college analogy; the real signal is clearing a BETTER
    classification's bar, the same way a college riser must clear a higher
    division's median (`world.div_level`) to be flagged.

    `sort`: 'gap' (most mismatched — biggest jump above where they'd fit), 'ceiling'
    (highest ceiling), 'now' (highest current OVR — who's already dominating below
    their level)."""
    import app.jhsaa as jh
    rows = _jhsaa_all_players(seed, gender)

    group_ceilings: dict[str, list[float]] = {}
    for r in rows:
        group_ceilings.setdefault(r["group"], []).append(r["ceiling"])
    group_avg = {g: sum(v) / len(v) for g, v in group_ceilings.items()}
    # jh.GROUPS is 9A..1A, best to worst — the same order the college division
    # ladder ranks D1..D4 on.
    order = [g for g in jh.GROUPS if g in group_avg]

    flagged = []
    for r in rows:
        own_idx = order.index(r["group"]) if r["group"] in order else len(order)
        # Best (lowest-index / toughest) classification this player's ceiling
        # clears by the gap threshold — never their own or a WORSE one, since
        # that isn't a mismatch, it's just being good at your own level.
        best_fit = None
        for g in order[:own_idx]:
            if r["ceiling"] - group_avg[g] >= MISAPPLIED_MIN_GAP:
                best_fit = g
                break
        if best_fit is None or r["ceiling"] < MISAPPLIED_MIN_CEILING:
            continue
        r = {**r, "fits_in": best_fit,
             "fit_avg": round(group_avg[best_fit], 1),
             "gap": round(r["ceiling"] - group_avg[best_fit], 1)}
        flagged.append(r)

    if group != "All":
        flagged = [r for r in flagged if r["group"] == group]

    keys = {
        "gap": (lambda r: (r["gap"], r["ceiling"]), True),
        "ceiling": (lambda r: (r["ceiling"], r["gap"]), True),
        "now": (lambda r: (r["ovr"], r["gap"]), True),
    }
    key, rev = keys.get(sort, keys["gap"])
    flagged.sort(key=key, reverse=rev)

    return {"gender": gender, "rows": flagged, "total": len(flagged),
            "groups": ["All"] + list(jh.GROUPS), "group": group, "sort": sort}


def jhsaa_lineup_lab(seed: int, gender: str, target_group: str = "5A",
                     pool: str = "mismatched", n_squads: int = 3) -> dict:
    """The scouting-department view for JHSAA — deal mismatched talent into whole
    9-player rosters for a target classification and rank each hypothetical squad
    against that classification's REAL programs, by average current OVR of their
    own dressed nine.

    `pool`: 'mismatched' (Talent-Mismatch qualifiers only) or 'any' (every player,
    best ceiling first — useful once the mismatch pool runs dry for a class).
    Squads are non-overlapping, dealt best-first. 9 is the association's own
    dressed-lineup size (3 singles + 4 doubles pairs)."""
    import app.jhsaa as jh
    SQUAD_SIZE = 9
    genders = ("boys", "girls") if gender == "all" else (_jh_g(gender),)

    if pool == "mismatched":
        cands = []
        for g in genders:
            cands.extend(jhsaa_misapplied_players(seed, g)["rows"])
    else:
        cands = _jhsaa_all_players(seed, gender)
        for r in cands:
            r.setdefault("gap", 0.0)
    cands.sort(key=lambda r: (r["ceiling"], r["ovr"]), reverse=True)

    # The target classification's real programs, by average current OVR of their
    # own top nine — the same lens a squad is judged against. Reuses the cached
    # census (grouped by school) instead of re-calling `jh.build_roster`, which
    # would otherwise redo the whole gender's roster build a second time in the
    # same request.
    by_school: dict[str, list[float]] = {}
    for g in genders:
        for r in _jhsaa_census_for(seed, g):
            if r["group"] == target_group:
                by_school.setdefault(r["school"], []).append(r["ovr"])
    div_levels = []
    for ovrs in by_school.values():
        top = sorted(ovrs, reverse=True)[:SQUAD_SIZE]
        if top:
            div_levels.append(sum(top) / len(top))
    div_levels.sort(reverse=True)
    n_div = len(div_levels)

    squads = []
    for k in range(max(1, n_squads)):
        block = cands[k * SQUAD_SIZE:(k + 1) * SQUAD_SIZE]
        if len(block) < SQUAD_SIZE:
            break
        avg_ovr = sum(r["ovr"] for r in block) / SQUAD_SIZE
        avg_ceiling = sum(r["ceiling"] for r in block) / SQUAD_SIZE
        rank = sum(1 for lvl in div_levels if lvl > avg_ovr) + 1
        squads.append({
            "players": block, "avg_ovr": round(avg_ovr, 1),
            "avg_ceiling": round(avg_ceiling, 1),
            "rank": rank, "n_div": n_div,
        })

    return {"gender": gender, "target_group": target_group, "pool": pool,
            "squads": squads, "groups": list(jh.GROUPS), "n_div": n_div}


def jhsaa_past_winners(seed: int, gender: str) -> dict:
    """Champions and Players of the Year for every archived JHSAA year — the
    high-school analogue of the college past-winners boards."""
    import app.jhsaa as jh
    import app.world as world
    w = world.get_or_create(seed)
    g = _jh_g(gender)
    schools = _jh_schools(g)
    years = []
    for year in world.jhsaa_years(w["id"], g):
        arc = world.get_jhsaa(w["id"], year, g)
        if arc:
            years.append({"year": year, "season_year": arc.get("season_year"),
                          "champions": {gp: _jh_deco(schools, nm, 20)
                                        for gp, nm in (arc.get("champions") or {}).items()
                                        if nm},
                          "poy": {grp: (aw.get("poy") or {})
                                  for grp, aw in (arc.get("awards") or {}).items()}})
    return {"gender": g, "groups": list(jh.GROUPS), "years": years,
            "scope": _jh_scope(g, jh.GROUPS[0], list(jh.GROUPS),
                               years[0]["year"] if years else 0,
                               [y["year"] for y in years], None, None)}
