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
    size = clamp_field(size)
    key = (division, gender, seed, size)
    if key not in _bracket_cache:
        sr = get_season(division, gender, seed)
        seeded, autobids = select_field(sr.programs, sr.ratings, sr.champions, size=size)
        _bracket_cache[key] = run_bracket(seeded, autobids, seed=seed)
    return _bracket_cache[key]


def reset_all() -> None:
    """Drop every web-layer cache and the engine roster caches. Called after an
    editor override changes, so rankings / teams / season all re-derive from the
    edited rosters on the next request."""
    from app import ncaa
    _season_cache.clear()
    _bracket_cache.clear()
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


def ranking_rows(division: str, gender: str, seed: int = DEFAULT_SEED) -> list[LiveRow]:
    sr = get_season(division, gender, seed)
    # conference rank + record lookup
    conf_pos: dict[str, tuple[int, int, int]] = {}
    for conf, table in sr.standings.items():
        for i, (p, w, l) in enumerate(table, 1):
            conf_pos[p.school] = (i, w, l)
    rows: list[LiveRow] = []
    for rk, p in enumerate(sr.ranked(), 1):
        r = sr.ratings[p.school]
        cr, cw, cl = conf_pos.get(p.school, (0, 0, 0))
        rows.append(LiveRow(
            rk=rk, school=p.school, conf=p.conf, conf_abbr=p.conf_abbr,
            tier=_tier(division, p.conf_abbr, p.conf), cr=cr, rec=r.record, crec=f"{cw}-{cl}",
            pi=r.pi, apr=r.apr, fqi=r.fqi, me=(p.school == MY_TEAM),
        ))
    return rows


def dashboard_view(division: str, gender: str, seed: int = DEFAULT_SEED) -> dict:
    """Everything the landing dashboard shows for one universe, built from the
    cached ratings season + NCAA bracket (no heavy season-mode creation)."""
    from .rankings_data import crest
    sr = get_season(division, gender, seed)
    rows = ranking_rows(division, gender, seed)

    # Player STR leaders — map each rated pid back to its player + school.
    pid_to = {}
    for school, roster in sr.rosters.items():
        for pr in roster:
            pid_to[pr.pid] = (pr, school)
    leaders = []
    for pid, (s, rel) in sr.player_str.items():
        if pid in pid_to:
            pr, school = pid_to[pid]
            w, l = sr.player_record.get(pid, (0, 0))
            abbr, color = crest(school)
            leaders.append({"name": pr.name, "school": school, "abbr": abbr,
                            "color": color, "str": round(s, 1), "rel": rel,
                            "w": w, "l": l, "pid": pid})
    leaders.sort(key=lambda d: d["str"], reverse=True)

    br = get_bracket(division, gender, seed)
    top_seeds = []
    for p in br.seeds[:8]:
        r = sr.ratings[p.school]
        abbr, color = crest(p.school)
        top_seeds.append({"school": p.school, "abbr": abbr, "color": color,
                          "pi": r.pi, "rec": r.record, "autobid": p.key in br.autobids})

    top = []
    for r in rows[:10]:
        abbr, color = crest(r.school)
        top.append({"row": r, "abbr": abbr, "color": color})

    return {
        "top_programs": top,
        "leaders": leaders[:10],
        "top_seeds": top_seeds,
        "champion": br.champion.school if br.champion else None,
        "n_programs": len(rows),
        "n_conferences": len(sr.standings),
    }


def conferences_for(division: str, gender: str) -> list[str]:
    sr = get_season(division, gender)
    return ["All"] + sorted(sr.standings.keys())


# --------------------------------------------------------------------------
# Recruiting (juniors) — board + profile
# --------------------------------------------------------------------------
from app.juniors import (generate_class, national_rankings, state_rankings,
                         international_rankings, US_STATES)
from app.development import overall_to_str

_recruit_cache: dict = {}
RECRUIT_GENDERS = {"men": "male", "women": "female"}

# Recruit-pool caliber by division — the class that feeds each division is drawn
# from the SAME talent/attribute model as that division's rostered players
# (app.development.generate_prospect), just centred lower because these are
# pre-college prospects who develop once on a roster. D1 boards run hotter than
# D2/D3, exactly as the rostered-player talent does (app.ncaa._talent_from_strength).
_DIVISION_TALENT = {"D1": 48.0, "D2": 43.0, "D3": 39.0}


def get_recruits(gender: str, grad_year: int, seed: int = DEFAULT_SEED, division: str = "D1"):
    """Cached recruiting class. `gender` is "male"/"female" (juniors vocab)."""
    key = (gender, grad_year, seed, division)
    if key not in _recruit_cache:
        rng = random.Random(f"{seed}|recruits|{gender}|{grad_year}|{division}")
        klass = generate_class(rng, n=400, grad_year=grad_year, gender=gender,
                               talent_mean=_DIVISION_TALENT.get(division, 48.0))
        national_rankings(klass)        # assigns recruit_rank / tier / stars
        _recruit_cache[key] = klass
    return _recruit_cache[key]


def get_recruit(gender: str, grad_year: int, pid: str, seed: int = DEFAULT_SEED, division: str = "D1"):
    return next((p for p in get_recruits(gender, grad_year, seed, division).recruits
                 if p.pid == pid), None)


def recruit_rows(gender: str, grad_year: int, scope: str = "national", state: str = "",
                 division: str = "D1"):
    klass = get_recruits(gender, grad_year, division=division)
    if scope == "state":
        src = state_rankings(klass, state)
    elif scope == "intl":
        src = international_rankings(klass)
    else:
        src = national_rankings(klass)
    return list(enumerate(src, 1))      # (board_rank, Prospect)


# Marquee attributes surfaced on the recruit/player scouting card (key, label),
# mirroring viperball's ~dozen-bar ATTRIBUTES block.
SCOUT_ATTRS = [
    ("first_serve_power", "Serve Power"), ("first_serve_accuracy", "Serve Accuracy"),
    ("return_quality", "Return"), ("forehand_power", "Forehand"),
    ("backhand_power", "Backhand"), ("groundstroke_consistency", "Consistency"),
    ("net_play", "Net Play"), ("speed", "Speed"), ("stamina", "Stamina"),
    ("composure", "Composure"), ("clutch", "Clutch"),
]


def scout_bars(p):
    """Visible per-attribute grades (20-80) for the scouting-bar block."""
    return [(label, p.current_grade(key)) for key, label in SCOUT_ATTRS]


def recruit_profile(p, division: str, gender: str, grad_year: int):
    """Build the profile view: rankings, scouting reads, and the College List /
    Dreamsheet / Timeline recruiting board.

    The College List is drawn from the LIVE programs of this division×gender —
    the same generated teams shown on the Rankings/Teams pages — so a recruit's
    offers come from real programs at their level, not a static seed list."""
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
    # One national pool: every gender-matched program across ALL divisions, so a
    # recruit's board can mix a low-major D1, an Ivy and a NESCAC school — the
    # appeal model (prestige + academics) decides the order.
    schools = schools_from_programs(all_gender_programs(gender))
    rec = build_recruiting(p, schools, seed_salt=f"{grad_year}")

    return {
        "national_rank": p.recruit_rank,
        "region_rank": region_rank,
        "region_label": region_label,
        "service": overall_to_str(p.scouting_report("service")),   # two independent ceiling reads
        "dept": overall_to_str(p.scouting_report("dept")),
        "projection": overall_to_str(p.project(4)),
        "recruiting": rec,
        "scout_bars": scout_bars(p),
    }


def teams_by_conference(division: str, gender: str, conf_filter: str = "All"):
    """[(conference, [ {school, abbr, color, pi, rec, tier} ... ]) ...] for the
    Teams index — teams grouped by conference, ranked within each by Power Index."""
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


ARCHETYPE_LABELS = {
    "coaching_lifer": "Coaching Lifer",
    "former_pro": "Former Pro",
    "recruiting_closer": "Recruiting Closer",
    "development_guru": "Development Guru",
    "tactician": "Tactician",
}


def _coach(school: str, gender: str, role: str, base: float):
    """A deterministic coach (real name) for a program, seeded by role."""
    import random
    from generators import make_name_picker, region_preset
    from app.coaches import generate_coach
    name_fn = make_name_picker(random.Random(f"coachname|{role}|{school}|{gender}"),
                               gender="mixed", region_weights=region_preset("global"))
    nm, _ = name_fn()
    return generate_coach(random.Random(f"coach|{role}|{school}|{gender}"), nm,
                          school=school, base=base)


def head_coach(school: str, division: str = "D1", gender: str = "men"):
    """A deterministic head coach (real name) for a program."""
    return _coach(school, gender, "head", base=54.0)


def coaching_staff(division: str, gender: str, school: str):
    """Head coach + associate + assistant, with display labels + a stable tenure.
    Stronger programs (higher conference prestige) skew to higher-rated staff."""
    import random
    from app import ncaa
    div = ncaa.load_division(division, gender)
    prog = div.by_school(school)
    base = 50.0 + (12.0 * prog.strength if prog else 0.0)
    rng = random.Random(f"tenure|{school}|{gender}")
    staff = []
    for role, title, bump in (("head", "Head Coach", 4.0),
                              ("assoc", "Associate Head Coach", -2.0),
                              ("asst", "Assistant Coach", -6.0)):
        c = _coach(school, gender, role, base=max(28.0, base + bump))
        staff.append({
            "coach": c, "title": title,
            "archetype": ARCHETYPE_LABELS.get(c.archetype, c.archetype.replace("_", " ").title()),
            "tenure": rng.randint(1, 14) if role == "head" else rng.randint(1, 8),
            "dev": round(c.development_score), "rec": round(c.recruiting_score),
            "tac": round(c.tactical_score),
        })
    return staff


def editor_roster(division: str, gender: str, school: str):
    """Effective (post-override) roster rows for the editor — what the lineup
    looks like *after* moves + ordering are applied."""
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
    """[(universe_label, [school,...])] across every division×gender — the move
    destination picker (optgroups)."""
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
    """Human-readable summary of current editor overrides for the panel."""
    from app import ncaa, overrides as ov
    moves = []
    for pid, dest in sorted(ov.get_moves().items(), key=lambda kv: kv[1]):
        pr = ncaa.player_by_pid(pid)
        moves.append({"pid": pid, "name": pr.name if pr else pid,
                      "str": round(pr.str_value(), 1) if pr else "—", "dest": dest})
    lineups = [{"school": s, "n": len(pids)} for s, pids in sorted(ov.get_lineups().items())]
    return {"moves": moves, "lineups": lineups, "any": bool(moves or lineups)}


def team_results(division: str, gender: str, school: str, seed: int = DEFAULT_SEED):
    """A school's dual results **as actually played** in the week-by-week season
    (season mode): opponent, home/away, W/L, team score, and the season-mode dual
    id so each result links to its box score. Only completed duals appear, so the
    team page fills in as the world advances rather than showing a finished
    season at week 1."""
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
    """A player's singles results grouped by season-year, newest first — built
    from the **persisted week-by-week season** (season mode), so the card only
    shows matches actually played as the world advances (not a pre-simulated
    baseline). Returns (groups, (career_w, career_l)); each group is
    {year, season_no, log, w, l}.

    Today there is one live season-year (the world's current year); the by-year
    structure is ready for persisted multi-season history."""
    import app.world as world
    import app.seasonmode as sm
    sid = sm.get_or_create(division, gender, seed=world.current_year_seed(seed))
    yr = world.load_world(seed)["year"] if world.exists(seed) else 0

    log = sm.player_log(sid, pid)
    w = sum(1 for m in log if m["won"])
    l = len(log) - w
    groups = [{"year": 2026 + yr, "season_no": yr + 1, "log": log, "w": w, "l": l}] if log else []
    return groups, (w, l)


def season_match_view(division: str, gender: str, idx: int, seed: int = DEFAULT_SEED):
    """Box-score view of the idx-th dual in the cached season — shaped exactly
    like seasonmode.dual_detail so the shared box-score template renders both."""
    sr = get_season(division, gender, seed)
    if idx < 0 or idx >= len(sr.duals):
        return None
    d = sr.duals[idx]
    return {"home": d["home"], "away": d["away"], "round": "REG",
            "conf": d["conf"], "home_points": d["home_points"],
            "away_points": d["away_points"], "winner": 0 if d["home_won"] else 1,
            "lines": d["lines"]}


def world_hub(seed: int = DEFAULT_SEED):
    """Overview for the unified-world hub: the shared clock, plus each division's
    season phase, live top teams, champion, and the signing class so far."""
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
    return {
        "year": world.BASE_YEAR + w["year"], "season_no": w["year"] + 1,
        "week": w["week"], "divisions": divisions, "signed": signed,
        "signed_total": sum(signed.values()),
        "complete": all(d["phase"] == "complete" for d in divisions),
    }


def all_gender_programs(gender: str):
    """Every program for one gender across D1+D2+D3 — the national recruiting
    pool (a recruit can choose any division)."""
    from app import ncaa
    progs = []
    for division in ("D1", "D2", "D3"):
        try:
            progs.extend(ncaa.load_division(division, gender).programs)
        except FileNotFoundError:
            continue
    return progs


def conference_schools(division: str, gender: str):
    """[(conference, [school, ...]), ...] — drives the schedule page's
    conference→team drill-down dropdowns."""
    from app import ncaa
    div = ncaa.load_division(division, gender)
    return sorted((conf, sorted(p.school for p in members))
                  for conf, members in div.conferences.items())


def team_conference(division: str, gender: str, school: str) -> str:
    from app import ncaa
    prog = ncaa.load_division(division, gender).by_school(school)
    return prog.conf if prog else ""


def team_roster(division: str, gender: str, school: str):
    """Roster rows for a Team page: (player, line, live STR, reliability, W-L)."""
    from app import economy
    sr = get_season(division, gender)
    roster = sr.rosters.get(school, [])
    rows = []
    for p in sorted(roster, key=lambda q: q.current_overall(), reverse=True):
        s, rel = sr.player_str.get(p.pid, (p.str_value(), 0.0))
        w, l = sr.player_record.get(p.pid, (0, 0))
        rows.append({"p": p, "str": round(s, 1), "rel": rel, "w": w, "l": l,
                     "schol": economy.fraction_label(getattr(p, "scholarship", 0.0))})
    for i, r in enumerate(rows, 1):
        r["line"] = i if i <= 6 else None       # top 6 are the singles lineup
    return rows


def team_budget(division: str, gender: str, school: str) -> dict:
    """Scholarship-equivalency ledger for a program's team page."""
    from app import economy
    sr = get_season(division, gender)
    roster = sr.rosters.get(school, [])
    return economy.budget_summary(roster, division, gender)
