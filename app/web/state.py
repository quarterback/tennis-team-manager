"""
Web-layer state: run each division×gender season + bracket once and cache it
(a season is ~2s, far too heavy per request). Also shapes ranking rows for
the Power Index table.
"""
from __future__ import annotations

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
        return SimpleNamespace(label=d["label"], pid=d.get("pid"), seed=d.get("seed"),
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
    s = sm.load_season(sm.get_or_create(division, gender, seed=eff))
    if s and s["phase"] == "complete":
        ch = run_singles_championship(division, gender, seed=eff, size=clamp_field(size))
        return _hydrate_championship(championship_to_dict(ch))
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
    s = sm.load_season(sm.get_or_create(division, gender, seed=eff))
    if s and s["phase"] == "complete":
        ch = run_doubles_championship(division, gender, seed=eff, size=clamp_field(size))
        return _hydrate_championship(championship_to_dict(ch))
    return _hydrate_championship(world.latest_championship(seed, division, gender, "Doubles"))


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
    for c in (sm._pid_idx_cache, sm._str_cache, sm._pi_cache, sm._forced_cache, sm._prec_cache,
              sm._pline_cache, sm._plrec_cache):
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
    p6: float = 0.0
    points: float = 0.0
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


def _power6(prog) -> float:
    """Power 6 — roster strength from the top-6 singles players' STR: their mean,
    doubled, so it reads on an easy, spread-out scale where the strongest rosters
    clear 100. Available even preseason (STR falls back to ability before any
    results)."""
    from app.ncaa import build_roster
    s = sorted((p.str_value() for p in build_roster(prog)), reverse=True)[:6]
    return round(sum(s) / len(s) * 2, 1) if s else 0.0


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
    rows: list[LiveRow] = []
    for rk, p in enumerate(ordered, 1):
        r = ratings.get(p.school)
        crk, cw, cl = cr.get(p.school, (0, 0, 0))
        rows.append(LiveRow(
            rk=rk, school=p.school, conf=p.conf, conf_abbr=p.conf_abbr,
            tier=_tier(division, p.conf_abbr, p.conf), cr=crk,
            rec=r.record if r else "0-0", crec=f"{cw}-{cl}",
            pi=r.pi if r else 0.0, apr=r.apr if r else 0.0, fqi=r.fqi if r else 0.0,
            p6=_power6(p), points=pts.get(p.school, 0.0), me=(p.school == _my_school),
        ))
    return rows


def singles_ranking_rows(division: str, gender: str, seed: int = DEFAULT_SEED) -> list[dict]:
    """ITA-style singles player ranking rows (newest-best first)."""
    import app.world as world
    import app.seasonmode as sm
    from app.ncaa import load_division
    from .rankings_data import crest
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    pts = sm.ita_singles_points(sid)
    pidx = sm._pid_index(division, gender)
    recs = sm.player_records(sid)
    progs = load_division(division, gender).programs
    conf_full = {p.school: p.conf for p in progs}
    conf_abbr = {p.school: p.conf_abbr for p in progs}
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
                     "w": w, "l": l, "points": pts[pid], "abbr": abbr, "color": color})
    return rows


def doubles_ranking_rows(division: str, gender: str, seed: int = DEFAULT_SEED) -> list[dict]:
    """ITA-style doubles PAIR ranking rows (newest-best first)."""
    import app.world as world
    import app.seasonmode as sm
    from app.ncaa import load_division
    from .rankings_data import crest
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    pts, members, wl = sm.ita_doubles_points(sid)
    pidx = sm._pid_index(division, gender)
    progs = load_division(division, gender).programs
    conf_full = {p.school: p.conf for p in progs}
    conf_abbr = {p.school: p.conf_abbr for p in progs}
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
                     "w": w, "l": l, "points": pts[pr], "abbr": abbr, "color": color})
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


def signing_tracker(gender: str, division: str | None = None,
                    seed: int = DEFAULT_SEED) -> dict:
    import app.world as world
    from app.ncaa import load_division
    from .rankings_data import crest
    by_school = world.signings(seed).get(gender, {})
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
    flipped_total = sum(1 for school_pl in by_school.values()
                        for p in school_pl if getattr(p, "flips", 0) > 0)
    return {"classes": classes, "commitments": commitments,
            "total_signed": sum(c["n"] for c in classes), "n_programs": len(classes),
            "n_flipped": flipped_total}


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

    from app.recruiting import build_recruiting, schools_from_programs
    schools = schools_from_programs(all_gender_programs(gender))
    rec = build_recruiting(p, schools, seed_salt=f"{grad_year}")

    from app.junior_circuit import TIER_LABELS
    from app.juniors import recruit_grade
    class_size = len(klass.recruits)
    rating, composite = recruit_grade(p.recruit_rank or 1, class_size)

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
        # OVR grades (20–80), NOT ability-derived STR — STR is match-based only.
        "service": round(p.scouting_report("service")),
        "dept": round(p.scouting_report("dept")),
        "projection": round(p.project(4)),
        "recruiting": rec,
        "scout_bars": scout_bars(p),
        "rating": rating,
        "composite": composite,
        "class_size": class_size,
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

    return {"singles": _box("singles", 6), "doubles": _box("doubles", 3)}


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


def fall_portal_view(seed: int = DEFAULT_SEED) -> dict:
    """The fall-portal slate for the review screen: each kept rider plus the player
    they'd push down the ladder, freshly RESOLVED so the cascade reflects any
    redirects/adds the user has made. Riders carry an editable destination."""
    import app.world as world
    from app import overrides as ov
    from .rankings_data import crest
    w = world.load_world(seed)
    if not w:
        return {"year": None, "proposals": [], "n": 0, "riders": 0, "committed": 0,
                "destinations": []}
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
    return {"year": world.BASE_YEAR + w["year"], "raw_year": w["year"],
            "proposals": out, "n": len(out),
            "riders": sum(1 for r in out if r["is_riser"]),
            "committed": len(committed),
            "destinations": world.fall_portal_destinations(seed)}


def preseason_portal_view(seed: int = DEFAULT_SEED) -> dict:
    """The pre-season-portal slate for the week-0 review screen: each kept rider plus
    the player they'd push down the ladder, freshly RESOLVED so the cascade reflects
    any redirects / adds. Riders carry an editable destination. Once committed, the
    rows come back with status='committed' so the screen shows what was applied."""
    import app.world as world
    from app import overrides as ov
    from .rankings_data import crest
    w = world.load_world(seed)
    if not w:
        return {"year": None, "proposals": [], "n": 0, "riders": 0, "committed": 0,
                "destinations": [], "is_preseason": False}
    committed = ov.ps_get_proposals(w["year"], status="committed")
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
        return {"year": world.BASE_YEAR + w["year"], "raw_year": w["year"],
                "proposals": out, "n": len(out),
                "riders": sum(1 for r in out if r["is_riser"]),
                "committed": len(committed), "done": True,
                "is_preseason": w["week"] == 0,
                "destinations": world.fall_portal_destinations(seed)}
    resolved = world.resolve_preseason_portal(seed)   # {gender: [moves]} (riders + cascades)
    out = []
    for gender, moves in resolved.items():
        for m in moves:
            p = world.find_persisted_player(m["pid"], seed)
            fa, fc = crest(m["src_school"])
            ta, tc = crest(m["dest_school"])
            out.append({
                **m, "gender": gender,
                "name": getattr(p, "name", m.get("name") or m["pid"]),
                "class": getattr(p, "class_year", ""),
                "country": getattr(p, "country", ""),
                "from_abbr": fa, "from_color": fc, "to_abbr": ta, "to_color": tc,
                "is_riser": m["cascade_from"] is None,
            })
    out.sort(key=lambda r: (0 if r["is_riser"] else 1, -r["str"], r["pid"]))
    return {"year": world.BASE_YEAR + w["year"], "raw_year": w["year"],
            "proposals": out, "n": len(out),
            "riders": sum(1 for r in out if r["is_riser"]),
            "committed": 0, "done": False,
            "is_preseason": w["week"] == 0,
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
    if year is not None:
        idx = year - world.BASE_YEAR
        sid = sm.find_season(division, gender, seed=world.year_seed(seed, idx))
        if sid is None:
            return None
    else:
        sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    rows = [r for r in sm.all_results(sid) if r["round"] == "NCAA"]
    if not rows:
        # Bracket reveal: the field is locked but no NCAA match has been played.
        phase = sm.load_season(sid).get("phase")
        if phase in ("selection", "ncaa"):
            seeded, autobids, out_board, _r = sm.ncaa_field(sid)
            region_of, region_names = _region_map(seeded)
            field = []
            for i, p in enumerate(seeded, 1):
                ab, col = crest(p.school)
                field.append({"seed": i, "school": p.school, "abbr": ab, "color": col,
                              "conf": getattr(p, "conf_abbr", ""),
                              "aq": p.key in autobids, "region": region_of.get(p.school)})
            snubs = []
            for o in out_board:
                ab, col = crest(o["school"])
                snubs.append({**o, "abbr": ab, "color": col})
            return {"reveal": True, "field": field, "size": len(field),
                    "n_aq": len(autobids), "out_board": snubs, "regions": region_names,
                    "rounds": [], "champion": None, "complete": False}
        return None
    # Seed / conference / bid context — the field is locked for the whole
    # postseason, so the same seeding the bracket was drawn from labels every team
    # (so you can see who the seeds were and trace a seed's path round to round).
    seed_map, conf_map, aq_set = {}, {}, set()
    region_of, region_names = {}, []
    top_seeds = []
    try:
        seeded, autobids, _out, _r = sm.ncaa_field(sid)
        region_of, region_names = _region_map(seeded)
        for i, p in enumerate(seeded, 1):
            seed_map[p.school] = i
            conf_map[p.school] = getattr(p, "conf_abbr", "")
            if p.key in autobids:
                aq_set.add(p.school)
            if i <= 16:
                ab, col = crest(p.school)
                top_seeds.append({"seed": i, "school": p.school, "abbr": ab, "color": col,
                                  "conf": getattr(p, "conf_abbr", ""), "aq": p.key in autobids,
                                  "region": region_of.get(p.school)})
    except Exception:
        pass

    def _team(school, abbr, color, won):
        return {"school": school, "abbr": abbr, "color": color, "won": won,
                "seed": seed_map.get(school), "conf": conf_map.get(school, ""),
                "aq": school in aq_set, "region": region_of.get(school)}

    by_round: dict = {}
    for r in rows:
        by_round.setdefault(r["round_no"], []).append(r)
    rounds = []
    for rno in sorted(by_round):
        matchups = []
        for r in sorted(by_round[rno], key=lambda x: x["bpos"]):
            hp, ap = r["home_points"], r["away_points"]
            home_won = r["winner"] == 0
            ha, hc = crest(r["home"]); aa, ac = crest(r["away"])
            matchups.append({
                "home": _team(r["home"], ha, hc, home_won),
                "away": _team(r["away"], aa, ac, not home_won),
                "home_won": home_won, "winner": r["home"] if home_won else r["away"],
                "score": f"{max(hp, ap)}-{min(hp, ap)}" if hp is not None else "",
            })
        rounds.append({"name": by_round[rno][0]["conf"], "matchups": matchups})
    champion = None
    if rounds and len(rounds[-1]["matchups"]) == 1:
        m = rounds[-1]["matchups"][0]
        win = m["home"] if m["home_won"] else m["away"]
        champion = {"school": win["school"], "abbr": win["abbr"], "color": win["color"],
                    "seed": win["seed"]}
    return {"rounds": rounds, "champion": champion, "top_seeds": top_seeds,
            "regions": region_names, "complete": champion is not None}


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
                "division": division, "class": info.get("class_year", ""),
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
                    "division": origin_div or division, "class": info.get("class_year", ""),
                    "line": None, "w": None, "l": None, "str": None,
                    "accolades": [], "live": False, "stint": 0, "phase": "transfer_out",
                    "transferred": True,
                })

    # Newest first, and within a split season the CURRENT school (higher stint) on
    # top with the school they came from below — a transfer reads top-to-bottom.
    rows.sort(key=lambda r: (-r["cal_year"], -r.get("stint", 0)))
    for r in rows:
        r["abbr"], r["color"] = crest(r["school"])
        r["pos"] = _pos_label(r["line"])
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
        out.append({"school": info.get("high_school") or "High school",
                    "division": "", "badge": "high_school",
                    "years": info.get("hometown", ""), "abbr": "HS", "color": "#888",
                    "stars": info.get("recruit_stars", 0), "tier": info.get("recruit_tier", "")})
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
    for val, division, gender, label in active_unis:
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
    complete = bool(divisions) and all(d["phase"] == "complete" for d in divisions)

    import app.honors as honors
    # Awards are "done" once every ACTIVE universe's honors are stamped (never wait
    # on a dormant universe, whose honors are never stamped).
    awards_done = complete and all(honors.has_season(year, d, g)
                                   for (_v, d, g, _l) in active_unis)
    _ORDER = ["ita", "fall_portal", "regular", "conf_tournaments", "selection", "ncaa",
              "awards", "offseason"]
    _PH = {"ita_kickoff": -2, "ita_indoor": -1, "fall_portal": -0.5, "regular": 0,
           "conf_tournaments": 1, "selection": 2, "ncaa": 3, "complete": 4}
    if not complete:
        raw = min((d["phase"] for d in divisions), key=lambda p: _PH[p])
        stage = ("ita" if raw in ("ita_kickoff", "ita_indoor") else raw)
    else:
        stage = "offseason" if awards_done else "awards"
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
    else:
        primary = {"endpoint": "world_advance", "label": f"Begin {year + 1} season →"}
    _LABELS = {"ita": "Preseason NIT", "fall_portal": "Fall portal", "regular": "Regular season",
               "conf_tournaments": "Conf tournaments", "selection": "Bracket Reveal",
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
    from app.ncaa import load_division, build_roster
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
    for i, r in enumerate(rows, 1):
        r["line"] = i if i <= 6 else None       # top 6 are the singles lineup
    return rows


def team_budget(division: str, gender: str, school: str) -> dict:
    from app import economy
    from app.ncaa import build_roster, load_division
    prog = load_division(division, gender).by_school(school)
    roster = build_roster(prog) if prog else []
    return economy.budget_summary(roster, division, gender)
