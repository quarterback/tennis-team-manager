"""
Web-layer state: run each division×gender season + bracket once and cache it
(a season is ~2s, far too heavy per request). Also shapes ranking rows for
the Power Index table.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from app.season import run_season
from app.bracket import select_field, run_bracket, clamp_field, FIELD_DEFAULT

DEFAULT_SEED = 2026
MY_TEAM = "Oregon"
FIELD_PRESETS = [32, 64, 76, 96]    # offered in the UI; any 16–128 works

# Division×gender universes exposed in the UI (value, division, gender, label).
UNIVERSES = [
    ("D1-men", "D1", "men", "D1 Men"),
    ("D1-women", "D1", "women", "D1 Women"),
    ("D2-men", "D2", "men", "D2 Men"),
    ("D2-women", "D2", "women", "D2 Women"),
    ("D3-men", "D3", "men", "D3 Men"),
    ("D3-women", "D3", "women", "D3 Women"),
]

# Conference → display tier (mirrors the design's P5 / MID / IVY badges).
_P5 = {"ACC", "SEC", "Big Ten", "Big 12", "Pac-12"}

_season_cache: dict = {}
_bracket_cache: dict = {}
_doubles_champ_cache: dict = {}
_singles_champ_cache: dict = {}
_portal_cache: dict = {}


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


def get_bracket(division: str, gender: str, seed: int = DEFAULT_SEED, size: int = FIELD_DEFAULT):
    """The NCAA field from the live season (conference champions get autobids once
    the conference tournaments have run). None in preseason. Cached by how far the
    season has progressed so it refreshes as results come in."""
    import app.world as world
    import app.seasonmode as sm
    size = clamp_field(size)
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    s = sm.load_season(sid)
    key = (division, gender, sid, size, s["current_week"], s["phase"])
    if key not in _bracket_cache:
        _bracket_cache[key] = sm.bracket_field(sid, size=size)
    return _bracket_cache[key]


def get_singles_championship(division: str, gender: str, seed: int = DEFAULT_SEED, size: int = 128):
    """The NCAA individual singles championship — a seed-deterministic 128-player
    draw derived from the program rosters, played AFTER the team tournament (None
    until the team bracket is complete). Cached for the year."""
    import app.world as world
    import app.seasonmode as sm
    from app.individuals import run_singles_championship, clamp_field
    size = clamp_field(size)
    eff = world.current_year_seed(seed)
    sid = sm.get_or_create(division, gender, seed=eff)
    s = sm.load_season(sid)
    if not s or s["phase"] != "complete":
        return None
    key = (division, gender, eff, size)
    if key not in _singles_champ_cache:
        _singles_champ_cache[key] = run_singles_championship(division, gender, seed=eff, size=size)
    return _singles_champ_cache[key]


def get_doubles_championship(division: str, gender: str, seed: int = DEFAULT_SEED, size: int = 64):
    """The NCAA individual doubles championship — a seed-deterministic 64-pair
    draw derived from the program rosters. It runs AFTER the team tournament, so
    it stays None until the team bracket is complete, then is cached for the
    year. Mirrors get_bracket's lazy, phase-aware shape."""
    import app.world as world
    import app.seasonmode as sm
    from app.individuals import run_doubles_championship, clamp_field
    size = clamp_field(size)
    eff = world.current_year_seed(seed)
    sid = sm.get_or_create(division, gender, seed=eff)
    s = sm.load_season(sid)
    if not s or s["phase"] != "complete":
        return None                          # unlocks once the team bracket is done
    key = (division, gender, eff, size)
    if key not in _doubles_champ_cache:
        _doubles_champ_cache[key] = run_doubles_championship(division, gender, seed=eff, size=size)
    return _doubles_champ_cache[key]


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
    _portal_cache.clear()
    _staff_cache.clear()
    awards.reset_cache()
    for c in (sm._pid_idx_cache, sm._str_cache, sm._pi_cache, sm._forced_cache, sm._prec_cache):
        c.clear()
    ncaa.reset_caches()


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
    me: bool = False

    @property
    def rank_class(self) -> str:
        return "gold" if self.rk == 1 else "bronze" if self.rk <= 3 else ""

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

    if ratings:
        rated = sorted((p for p in div.programs if p.school in ratings),
                       key=lambda p: ratings[p.school].pi, reverse=True)
        unrated = sorted((p for p in div.programs if p.school not in ratings),
                         key=_ability, reverse=True)            # not yet played
        ordered = rated + unrated
    else:
        ordered = sorted(div.programs, key=_ability, reverse=True)

    rows: list[LiveRow] = []
    for rk, p in enumerate(ordered, 1):
        r = ratings.get(p.school)
        crk, cw, cl = cr.get(p.school, (0, 0, 0))
        rows.append(LiveRow(
            rk=rk, school=p.school, conf=p.conf, conf_abbr=p.conf_abbr,
            tier=_tier(division, p.conf_abbr, p.conf), cr=crk,
            rec=r.record if r else "0-0", crec=f"{cw}-{cl}",
            pi=r.pi if r else 0.0, apr=r.apr if r else 0.0, fqi=r.fqi if r else 0.0,
            me=(p.school == MY_TEAM),
        ))
    return rows


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
    _pkey = (division, gender, sid, s["current_week"], s["phase"])
    _cached = _portal_cache.get(_pkey)
    if _cached is not None:
        return _cached
    div = load_division(division, gender)
    baseline_rows = ranking_rows(division, gender, seed)
    baseline_rank = {r.school: r.rk for r in baseline_rows}
    ratings = sm.power_index(sid)

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
            previous = baseline_rank.get(prog.school, rk)
            move = previous - rk
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
    junior_year = 2027
    juniors = recruiting_hub(rg, junior_year, seed=seed)
    top_prospects = []
    for rk, p, stat, honor in juniors["top_rows"][:6]:
        top_prospects.append({
            "rk": rk, "pid": p.pid, "name": p.name, "country": p.country,
            "secondary_country": p.secondary_country, "grad_year": p.grad_year,
            "stars": p.recruit_stars, "points": p.junior_points, "str": p.junior_str,
        })

    conn = sm._db()
    counts = conn.execute(
        "SELECT COUNT(*) total, SUM(CASE WHEN status='final' THEN 1 ELSE 0 END) final "
        "FROM duals WHERE season_id=?", (sid,)
    ).fetchone()
    conn.close()
    completed = counts["final"] or 0
    total_duals = counts["total"] or 0

    _portal_result = {
        "season": s, "phase": s["phase"], "current_week": s["current_week"],
        "total_weeks": s["total_weeks"], "programs": len(div.programs),
        "conferences": len(div.conferences), "players": len(pidx),
        "completed_duals": completed, "total_duals": total_duals,
        "live_rankings": live_rankings, "player_leaders": player_leaders,
        "standings_leaders": standings_leaders[:8], "recent": recent, "upcoming": upcoming,
        "top_prospects": top_prospects, "junior_kpis": juniors["kpis"],
        "grad_year": junior_year, "has_live_results": bool(ratings),
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
    return world.recruit_class(gender, grad_year, world.active_salt(seed))


def junior_ranking_rows(gender: str, grad_year: int, scope: str = "world",
                        nation: str = "", sort: str = "rank", desc: bool = True,
                        seed: int = DEFAULT_SEED):
    """Points-ledger junior rankings as (rank, Prospect, stat_line) rows, sortable by
    any almanac column. Scopes: 'world' (whole pool), 'us' (domestic), 'nation'."""
    from app import almanac
    klass = get_recruits(gender, grad_year, seed)
    if scope == "us":
        src = us_points_rankings(klass)[:100]
    elif scope == "nation" and nation:
        src = [p for p in points_rankings(klass) if not p.domestic and p.region == nation]
    else:
        src = points_rankings(klass)
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
            "points": p.junior_points, "singles_points": p.singles_points,
            "doubles_points": p.doubles_points, "str": p.junior_str,
            "doubles_str": p.junior_doubles_str, "events": p.tournaments_played,
            "doubles_events": p.doubles_played, "w": s["w"], "l": s["l"],
            "win_pct": round(s["pct"], 3), "titles": s["titles"], "finals": s["finals"],
            "honors": getattr(p, "junior_badges", None) or [],
        })
    return {"gender": gender, "grad_year": grad_year, "count": len(recruits), "board": rows}


def signing_tracker(gender: str, seed: int = DEFAULT_SEED) -> dict:
    import app.world as world
    from .rankings_data import crest
    by_school = world.signings(seed).get(gender, {})
    classes = []
    commitments = []
    for school, recruits in by_school.items():
        stars = [getattr(p, "recruit_stars", 0) for p in recruits]
        abbr, color = crest(school)
        commits = sorted(recruits, key=lambda p: (-getattr(p, "recruit_stars", 0),
                                                  getattr(p, "recruit_rank", 1e9)))
        classes.append({
            "school": school, "abbr": abbr, "color": color, "n": len(recruits),
            "total_stars": sum(stars), "avg_stars": round(sum(stars) / len(stars), 2) if stars else 0.0,
            "five": sum(1 for x in stars if x >= 5), "four": sum(1 for x in stars if x == 4),
            "commits": commits[:5],
        })
        for p in recruits:
            commitments.append({"p": p, "school": school, "abbr": abbr, "color": color,
                                "stars": getattr(p, "recruit_stars", 0)})
    classes.sort(key=lambda c: (-c["total_stars"], -c["n"], c["school"]))
    for i, c in enumerate(classes, 1):
        c["rank"] = i
    commitments.sort(key=lambda r: (-r["stars"], getattr(r["p"], "recruit_rank", 1e9)))
    flipped_total = sum(1 for school_pl in by_school.values()
                        for p in school_pl if getattr(p, "flips", 0) > 0)
    return {"classes": classes, "commitments": commitments,
            "total_signed": sum(c["n"] for c in classes), "n_programs": len(classes),
            "n_flipped": flipped_total}


def team_recruiting_class(gender: str, school: str, seed: int = DEFAULT_SEED) -> dict:
    import app.world as world
    from .rankings_data import crest
    recruits = world.signings(seed).get(gender, {}).get(school, [])
    stars = [getattr(p, "recruit_stars", 0) for p in recruits]
    abbr, color = crest(school)
    commits = sorted(recruits, key=lambda p: (-getattr(p, "recruit_stars", 0),
                                              getattr(p, "recruit_rank", 1e9)))
    return {
        "school": school, "abbr": abbr, "color": color, "n": len(recruits),
        "five": sum(1 for x in stars if x >= 5), "four": sum(1 for x in stars if x == 4),
        "three": sum(1 for x in stars if x == 3),
        "total_stars": sum(stars), "avg_stars": round(sum(stars) / len(stars), 2) if stars else 0.0,
        "commits": commits,
    }


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
        return p
    klass = get_recruits(gender, grad_year, seed)
    _apply_committed_flag(klass, gender, grad_year)
    return next((q for q in klass.recruits if q.pid == pid), None)


_REV_RECRUIT_GENDERS = {v: k for k, v in RECRUIT_GENDERS.items()}


def _apply_committed_flag(klass, gender: str, grad_year: int) -> None:
    import app.world as world
    w = world.load_world()
    if not w or w["year"] != grad_year:
        for p in klass.recruits:
            p.committed = False
            p.commit_school = None
        return
    wgender = _REV_RECRUIT_GENDERS.get(gender, gender)
    pid_to_school = {p.pid: school
                     for school, pl in world.signings().get(wgender, {}).items()
                     for p in pl}
    for p in klass.recruits:
        p.commit_school = pid_to_school.get(p.pid)
        p.committed = p.commit_school is not None


def recruit_rows(gender: str, grad_year: int, scope: str = "national", state: str = "",
                 division: str = "D1"):
    klass = get_recruits(gender, grad_year, division=division)
    _apply_committed_flag(klass, gender, grad_year)
    if scope == "state":
        src = state_rankings(klass, state)
    elif scope == "intl":
        src = international_rankings(klass)
    else:
        src = national_rankings(klass)
    return list(enumerate(src, 1))      # (board_rank, Prospect)


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

    from app.recruiting import build_recruiting, schools_from_programs
    schools = schools_from_programs(all_gender_programs(gender))
    rec = build_recruiting(p, schools, seed_salt=f"{grad_year}")

    from app.junior_circuit import TIER_LABELS
    return {
        "national_rank": p.recruit_rank,
        "region_rank": region_rank,
        "region_label": region_label,
        "points_rank": getattr(p, "points_rank", None),
        "junior_points": getattr(p, "junior_points", 0),
        "tournaments_played": getattr(p, "tournaments_played", 0),
        "junior_str": getattr(p, "junior_str", None),
        "junior_tier_label": TIER_LABELS.get(p.junior_tier, ""),
        "service": overall_to_str(p.scouting_report("service")),
        "dept": overall_to_str(p.scouting_report("dept")),
        "projection": overall_to_str(p.project(4)),
        "recruiting": rec,
        "scout_bars": scout_bars(p),
    }


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
    import app.world as world
    yr = world.load_world()["year"] if world.exists() else 0
    key = (division, gender, school, yr)
    if key in _staff_cache:
        return _staff_cache[key]
    staff = []
    for role in ("head", "assoc", "asst"):
        r = coachgen.ensure(division, gender, school, role)
        staff.append({"coach_id": r["coach_id"], "name": r["name"],
                      "title": coachgen.ROLE_TITLES[role], "role": role,
                      "archetype": r["archetype"], "tenure": r["tenure"],
                      "dev": r["dev"], "rec": r["rec"], "tac": r["tac"]})
    _staff_cache[key] = staff
    return staff


def head_coach(division: str, gender: str, school: str) -> dict | None:
    for s in coaching_staff(division, gender, school):
        if s["role"] == "head":
            return s
    return None


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
            "line": i if i <= 6 else None,
            "walk_on": getattr(pr, "walk_on", False),
            "moved_in": pr.pid not in base_pids,
            "hometown": getattr(pr, "hometown", ""),
        })
    abbr, color = crest(school)
    return rows, {"school": school, "abbr": abbr, "color": color}


def all_programs_grouped():
    from app import ncaa
    out = []
    for val, division, gender, label in UNIVERSES:
        try:
            div = ncaa.load_division(division, gender)
        except FileNotFoundError:
            continue
        out.append((label, sorted(p.school for p in div.programs)))
    return out


def active_overrides():
    from app import ncaa, overrides as ov
    moves = []
    for pid, dest in sorted(ov.get_moves().items(), key=lambda kv: kv[1]):
        pr = ncaa.player_by_pid(pid)
        moves.append({"pid": pid, "name": pr.name if pr else pid,
                      "str": round(pr.str_value(), 1) if pr else "—", "dest": dest})
    lineups = [{"school": s, "n": len(pids)} for s, pids in sorted(ov.get_lineups().items())]
    prestige = [{"school": s, "value": round(v * 100)}
                for s, v in sorted(ov.get_prestige().items())]
    academics = [{"school": s, "value": round(v * 100)}
                 for s, v in sorted(ov.get_academics().items())]
    conf_prestige = [{"conf": c, "value": round(v * 100)}
                     for c, v in sorted(ov.get_conf_prestige().items())]
    conf_academics = [{"conf": c, "value": round(v * 100)}
                      for c, v in sorted(ov.get_conf_academics().items())]
    return {"moves": moves, "lineups": lineups, "prestige": prestige,
            "academics": academics, "conf_prestige": conf_prestige,
            "conf_academics": conf_academics,
            "any": bool(moves or lineups or prestige or academics
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
                    "conf": bool(d["is_conf"])})
    return {"results": out, "wins": wins, "losses": losses}


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


def world_hub(seed: int = DEFAULT_SEED):
    import app.world as world
    import app.seasonmode as sm
    w = world.get_or_create(seed)
    world.prime(seed)
    divisions = []
    for val, division, gender, label in UNIVERSES:
        sid = world.universe_sid(seed, w, division, gender)
        s = sm.load_season(sid)
        champ = s["champion"] if s["phase"] == "complete" else None
        divisions.append({
            "u": val, "label": label, "phase": s["phase"],
            "week": s["current_week"], "total": s["total_weeks"],
            "top": sm.national_top(sid, 4), "champion": champ,
        })
    signed = world.signed_counts(seed)
    year = world.BASE_YEAR + w["year"]
    complete = all(d["phase"] == "complete" for d in divisions)

    import app.honors as honors
    awards_done = complete and honors.has_season(year, "D1", "men")
    _ORDER = ["regular", "conf_tournaments", "ncaa", "awards", "offseason"]
    _PH = {"regular": 0, "conf_tournaments": 1, "ncaa": 2, "complete": 3}
    if not complete:
        stage = min((d["phase"] for d in divisions), key=lambda p: _PH[p])
    else:
        stage = "offseason" if awards_done else "awards"
    if stage in ("regular", "conf_tournaments", "ncaa"):
        if w["week"] == 0 and stage == "regular":
            primary = {"endpoint": "preseason_view", "label": "⚙ Preseason setup →", "link": True}
        else:
            primary = {"endpoint": "world_advance",
                       "label": "Advance week →" if stage == "regular" else "Advance postseason →"}
    elif stage == "awards":
        primary = {"endpoint": "world_awards", "label": "🏅 Run awards →"}
    else:
        primary = {"endpoint": "world_advance", "label": f"Begin {year + 1} season →"}
    _LABELS = {"regular": "Regular season", "conf_tournaments": "Conf tournaments",
               "ncaa": "NCAA championship", "awards": "Awards", "offseason": "Offseason"}
    ci = _ORDER.index(stage)
    stages = [{"key": k, "label": _LABELS[k], "done": i < ci, "current": i == ci}
              for i, k in enumerate(_ORDER)]

    return {
        "year": year, "season_no": w["year"] + 1,
        "week": w["week"], "divisions": divisions, "signed": signed,
        "signed_total": sum(signed.values()),
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
        {"icon": "🎓", "title": "Recruiting",
         "auto": "Your class signs automatically, a slice each week.",
         "desc": "Open the board to track the pool and steer your targets.",
         "label": "Open recruiting →", "endpoint": "recruiting", "args": {}},
        {"icon": "📅", "title": "Schedule",
         "auto": "Every team's non-conference + conference slate is already set.",
         "desc": "Review your slate, or edit a team's schedule in the editor.",
         "label": "View schedule →", "endpoint": "season_schedule", "args": {"school": MY_TEAM}},
        {"icon": "🎾", "title": "Lineups",
         "auto": "Ladders auto-shuffle by player strength.",
         "desc": "Reorder any ladder in the editor to override the auto order.",
         "label": "Open editor →", "endpoint": "editor", "args": {}},
    ]
    return {"year": year, "active": active, "dormant": dormant, "steps": steps,
            "is_preseason": w["week"] == 0}


def all_gender_programs(gender: str):
    from app import ncaa
    progs = []
    for division in ("D1", "D2", "D3"):
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
        "prestige": round(cp.get(conf, ncaa.CONF_PRESTIGE.get(abbr, 0.50)) * 100),
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
    rows = []
    for p in sorted(roster, key=lambda q: q.current_overall(), reverse=True):
        s, rel = strmap.get(p.pid, (p.str_value(), 0.0))
        w, l = recs.get(p.pid, (0, 0))
        rows.append({"p": p, "str": round(s, 1), "rel": rel, "w": w, "l": l,
                     "schol": economy.fraction_label(getattr(p, "scholarship", 0.0))})
    for i, r in enumerate(rows, 1):
        r["line"] = i if i <= 6 else None       # top 6 are the singles lineup
    return rows


def team_budget(division: str, gender: str, school: str) -> dict:
    from app import economy
    from app.ncaa import build_roster, load_division
    prog = load_division(division, gender).by_school(school)
    roster = build_roster(prog) if prog else []
    return economy.budget_summary(roster, division, gender)
