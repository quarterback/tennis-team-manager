"""Analytics Bureau — the god-mode player-intelligence platform.

An ADDITIVE read/analytics layer over the existing world. It reads the engine's
*hidden truth* — every player's true talent ceiling (``ceiling_overall``), with
ZERO scouting fog — and cross-references it against where each player actually
sits: their program's level, their lineup slot, and their scholarship status.

Nothing here simulates or mutates anything. It answers three questions the
public recruiting board can't, because the board only sees noisy visible
ability:

  1. UNDERPLACED TALENT — who is buried at a program well below their true
     ceiling (a D3 stud who should be playing D1; a low-major's hidden gem).
  2. SCHOLARSHIP WATCH — walk-ons whose true talent out-strips funded
     teammates: aid the program is misallocating.
  3. FIT FINDER — for any player, the programs where their talent would
     actually be deployed (instant No. 1 / top-3 starter / rotation), weighed
     by program level and remaining scholarship room.

Talent is the absolute 20–80 ceiling grade, so it is directly comparable across
D1/D2/D3 — that's what makes "stuck at the wrong level" computable. The whole
scan is memoised per world snapshot (id, year, week, gender) the way the roster
caches are, so the pages stay snappy over ~11k players a gender.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.development import overall_to_str

DIVISIONS = ("D1", "D2", "D3")
_scan_cache: dict = {}


def _caliber(overall: float) -> float:
    return max(0.0, min(1.0, (overall - 20) / 60.0))


def _pct(rank: int, n: int) -> float:
    """Top-is-1.0 percentile for a 1-based rank within n items."""
    if n <= 1:
        return 1.0
    return 1.0 - (rank - 1) / (n - 1)


@dataclass
class Intel:
    pid: str
    name: str
    country: str
    school: str
    division: str
    gender: str
    class_year: str
    cur_overall: int
    true_overall: int
    cur_str: float
    true_str: float
    upside: float                 # true_str - cur_str (untapped growth)
    walk_on: bool
    scholarship: float
    schol_label: str
    line: int | None              # current lineup slot on their own team (1–6) or None
    team_pi_rank: int
    team_tier: str
    # filled in the second pass (need global tables):
    talent_pct: float = 0.0       # global true-talent percentile (same gender, all div)
    team_level_pct: float = 0.0   # their program's level percentile
    placement_gap: float = 0.0    # talent_pct - team_level_pct (>0 = underplaced)
    deserved_school: str = ""
    deserved_division: str = ""
    deserved_pi_rank: int = 0


def _world_stamp(seed: int):
    import app.world as world
    try:
        if world.exists(seed):
            w = world.load_world(seed)
            return (w["id"], w["year"], w["week"])
    except Exception:
        pass
    return ("noworld", 0, 0)


def scan(gender: str, seed: int | None = None) -> dict:
    """Full god-mode talent scan for one gender across every division. Returns
    ``{players, teams, by_pid, team_ladder}``, memoised per world snapshot."""
    from app.web.state import DEFAULT_SEED
    if seed is None:
        seed = DEFAULT_SEED
    key = (_world_stamp(seed), gender)
    cached = _scan_cache.get(key)
    if cached is not None:
        return cached

    from app import economy
    from app.ncaa import load_division, build_roster
    from app.web.state import ranking_rows

    # Load THIS world-year's live rosters into the shared cache before reading any
    # `build_roster` — the same hinge every live surface uses (state.get_season).
    # Without it the scan reads whatever rosters happen to be cached (often the
    # deterministic year-0 base), so once players develop/graduate/transfer at a
    # rollover the bureau lists stale pids and every "player" link 404s.
    import app.world as world
    if world.exists(seed):
        world.prime(seed)

    players: list[Intel] = []
    teams: dict[str, dict] = {}

    for division in DIVISIONS:
        try:
            div = load_division(division, gender)
        except FileNotFoundError:
            continue
        pi_rank = {r.school: r.rk for r in ranking_rows(division, gender, seed)}
        n_teams_div = len(div.programs)
        offers_aid = economy.offers_aid(division, gender)
        for prog in div.programs:
            roster = build_roster(prog)
            if not roster:
                continue
            # roster is current-ability ordered; the top 6 are the singles ladder.
            top6 = roster[:6]
            team_level = sum(p.ceiling_overall() for p in top6) / len(top6)
            top6_cur = sorted((p.current_overall() for p in top6), reverse=True)
            budget = economy.budget_summary(roster, division, gender)
            rk = pi_rank.get(prog.school, n_teams_div)
            teams[prog.school] = {
                "school": prog.school, "division": division, "gender": gender,
                "pi_rank": rk, "n_teams": n_teams_div, "tier": getattr(prog, "conf_abbr", ""),
                "team_level": team_level, "top6_cur": top6_cur,
                "aid_remaining": budget["remaining"], "offers_aid": offers_aid,
                "n_core": sum(1 for p in roster if not getattr(p, "walk_on", False)),
            }
            for i, p in enumerate(roster, 1):
                cur_o = p.current_overall()
                true_o = p.ceiling_overall()
                cur_s = overall_to_str(cur_o)
                true_s = overall_to_str(true_o)
                schol = float(getattr(p, "scholarship", 0.0) or 0.0)
                players.append(Intel(
                    pid=p.pid, name=p.name, country=getattr(p, "country", ""),
                    school=prog.school, division=division, gender=gender,
                    class_year=getattr(p, "class_year", ""),
                    cur_overall=cur_o, true_overall=true_o,
                    cur_str=round(cur_s, 1), true_str=round(true_s, 1),
                    upside=round(true_s - cur_s, 1),
                    walk_on=bool(getattr(p, "walk_on", False)),
                    scholarship=schol, schol_label=economy.fraction_label(schol),
                    line=(i if i <= 6 else None),
                    team_pi_rank=rk, team_tier=getattr(prog, "conf_abbr", ""),
                ))

    # ---- global tables (absolute ceiling → comparable across divisions) ----
    players.sort(key=lambda r: r.true_overall, reverse=True)
    n_players = len(players)
    for i, r in enumerate(players, 1):
        r.talent_pct = _pct(i, n_players)

    # program ladder by true team level, all divisions blended into one ladder
    ladder = sorted(teams.values(), key=lambda t: t["team_level"], reverse=True)
    n_t = len(ladder)
    for i, t in enumerate(ladder, 1):
        t["level_pct"] = _pct(i, n_t)
        t["level_rank"] = i

    for r in players:
        t = teams.get(r.school, {})
        r.team_level_pct = t.get("level_pct", 0.0)
        r.placement_gap = round(r.talent_pct - r.team_level_pct, 4)
        # The program a talent of this calibre "deserves": the team sitting at
        # the same percentile on the program ladder.
        idx = min(n_t - 1, max(0, round((1 - r.talent_pct) * (n_t - 1)))) if n_t else 0
        if ladder:
            d = ladder[idx]
            r.deserved_school = d["school"]
            r.deserved_division = d["division"]
            r.deserved_pi_rank = d["pi_rank"]

    by_pid = {r.pid: r for r in players}
    out = {"players": players, "teams": teams, "by_pid": by_pid, "team_ladder": ladder}
    _scan_cache[key] = out
    return out


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

UNDERPLACED_MIN_GAP = 0.18        # placement gap below this is just normal spread
UNDERPLACED_MIN_TRUE = 46         # ignore genuinely low-ceiling players (3★+ talent)


def underplaced_board(gender: str, seed: int | None = None, division: str = "All",
                      class_year: str = "All", sort: str = "gap", q: str = "") -> list[Intel]:
    """Players whose true talent sits above their program's level — the buried
    studs and arbitrage targets. `sort` picks the lens: 'gap' (most underplaced),
    'now' (best RIGHT NOW — who you'd want to move today), or 'talent' (highest
    ceiling). `q` filters by player or school name."""
    rows = [r for r in scan(gender, seed)["players"]
            if r.placement_gap >= UNDERPLACED_MIN_GAP and r.true_overall >= UNDERPLACED_MIN_TRUE]
    if division != "All":
        rows = [r for r in rows if r.division == division]
    if class_year != "All":
        rows = [r for r in rows if r.class_year == class_year]
    if q:
        ql = q.strip().lower()
        rows = [r for r in rows if ql in r.name.lower() or ql in r.school.lower()]
    keys = {
        "gap": lambda r: (r.placement_gap, r.true_overall),
        "now": lambda r: (r.cur_overall, r.cur_str, r.placement_gap),   # good today
        "talent": lambda r: (r.true_overall, r.placement_gap),
    }
    rows.sort(key=keys.get(sort, keys["gap"]), reverse=True)
    return rows


@dataclass
class AidFlag:
    player: Intel
    outranks: int                 # # of funded teammates this walk-on out-talents
    weakest_funded: str           # name of the weakest scholarship player they'd displace
    weakest_funded_true: float
    weakest_funded_schol: str
    recommended: str              # scholarship fraction label they merit


def scholarship_watch(gender: str, seed: int | None = None,
                      division: str = "All") -> list[AidFlag]:
    """Walk-ons whose TRUE ceiling out-strips funded teammates — aid the program
    is misallocating. D3 (no athletic aid) is excluded by definition."""
    from app import economy
    data = scan(gender, seed)
    teams = data["teams"]
    by_school: dict[str, list[Intel]] = {}
    for r in data["players"]:
        by_school.setdefault(r.school, []).append(r)

    flags: list[AidFlag] = []
    for school, roster in by_school.items():
        t = teams.get(school, {})
        if not t.get("offers_aid"):
            continue
        if division != "All" and t["division"] != division:
            continue
        funded = sorted((r for r in roster if not r.walk_on and r.scholarship > 0),
                        key=lambda r: r.true_overall)
        if not funded:
            continue
        for w in roster:
            if not w.walk_on:
                continue
            weaker = [f for f in funded if f.true_overall < w.true_overall]
            if not weaker:
                continue
            wk = weaker[0]      # weakest funded player this walk-on beats
            rec = economy.fraction_label(
                economy.offered_fraction(w.division, gender, _caliber(w.true_overall)))
            flags.append(AidFlag(
                player=w, outranks=len(weaker), weakest_funded=wk.name,
                weakest_funded_true=wk.true_str, weakest_funded_schol=wk.schol_label,
                recommended=rec))
    flags.sort(key=lambda f: (f.outranks, f.player.true_overall), reverse=True)
    return flags


@dataclass
class PlayWatch:
    player: Intel
    best_school: str
    best_division: str
    best_slot: int
    best_slot_label: str
    move_dir: str                 # 'up' / 'lateral' / 'down' vs their current division


_DIVRANK = {"D1": 0, "D2": 1, "D3": 2}


def playing_time_watch(gender: str, seed: int | None = None,
                       division: str = "All") -> list[PlayWatch]:
    """Walk-ons (no athletic aid) at D1/D2 who AREN'T in their own lineup, and the
    best program — any division, in or out of their own — where their CURRENT
    ability would make them a starter. Playing somewhere beats sitting anywhere."""
    data = scan(gender, seed)
    ladder = data["team_ladder"]
    out: list[PlayWatch] = []
    for p in data["players"]:
        if not p.walk_on or p.division not in ("D1", "D2"):
            continue                                   # a kid sitting at D1 or D2
        if division != "All" and p.division != division:
            continue
        if p.line is not None and p.line <= 6:
            continue                                   # already a starter — not stuck
        best = None
        for t in ladder:
            if t["school"] == p.school:
                continue
            slot = 1 + sum(1 for cs in t["top6_cur"] if cs > p.cur_overall)
            if slot > 6:                               # wouldn't crack that lineup either
                continue
            # prefer: starts highest, then closest to (or above) their level
            score = (7 - slot) + t["level_pct"] - _DIVRANK[t["division"]] * 0.4
            if best is None or score > best[0]:
                best = (score, t, slot)
        if best is None:
            continue
        _s, t, slot = best
        dr = _DIVRANK[t["division"]] - _DIVRANK[p.division]
        out.append(PlayWatch(player=p, best_school=t["school"], best_division=t["division"],
                             best_slot=slot, best_slot_label=_slot_label(slot),
                             move_dir=("up" if dr < 0 else "down" if dr > 0 else "lateral")))
    out.sort(key=lambda f: (f.player.cur_overall, f.best_slot == 1), reverse=True)
    return out


@dataclass
class FitTarget:
    school: str
    division: str
    pi_rank: int
    tier: str
    team_level_str: float
    slot: int                     # projected lineup slot by CURRENT ability
    slot_label: str
    aid_label: str
    move_up: bool                 # higher program level than their current team


def _slot_label(slot: int) -> str:
    if slot == 1:
        return "Instant No. 1"
    if slot <= 3:
        return f"Top-{slot} starter"
    if slot <= 6:
        return f"No. {slot} starter"
    return "Rotation / depth"


def fit_targets(gender: str, pid: str, seed: int | None = None,
                limit: int = 14) -> tuple[Intel | None, list[FitTarget]]:
    """Where this player's talent would actually be deployed. Scores every
    program by the lineup slot they'd claim NOW (current ability) plus program
    level and scholarship room — surfacing the best landing spots."""
    from app import economy
    data = scan(gender, seed)
    p = data["by_pid"].get(pid)
    if p is None:
        return None, []
    here = data["teams"].get(p.school, {})
    here_level = here.get("level_pct", 0.0)
    out: list[FitTarget] = []
    for t in data["team_ladder"]:
        if t["school"] == p.school:
            continue
        slot = 1 + sum(1 for cs in t["top6_cur"] if cs > p.cur_overall)
        if slot > 6:                       # wouldn't crack the lineup — not "useful"
            continue
        aid = economy.fraction_label(
            economy.offered_fraction(t["division"], gender, _caliber(p.true_overall))
        ) if t["offers_aid"] else "—"
        # prefer: starts high (low slot) + strong program + moving up a level
        score = t["level_pct"] + (7 - slot) * 0.04 + (0.05 if t["level_pct"] > here_level else 0)
        out.append((score, FitTarget(
            school=t["school"], division=t["division"], pi_rank=t["pi_rank"],
            tier=t["tier"], team_level_str=round(overall_to_str(t["team_level"]), 1),
            slot=slot, slot_label=_slot_label(slot), aid_label=aid,
            move_up=t["level_pct"] > here_level)))
    out.sort(key=lambda x: x[0], reverse=True)
    return p, [ft for _, ft in out[:limit]]


def overview(gender: str, seed: int | None = None) -> dict:
    """Bureau landing KPIs + the headline finds."""
    data = scan(gender, seed)
    under = underplaced_board(gender, seed)
    aid = scholarship_watch(gender, seed)
    return {
        "n_players": len(data["players"]),
        "n_teams": len(data["teams"]),
        "n_underplaced": len(under),
        "n_aid_flags": len(aid),
        "top_underplaced": under[:8],
        "top_aid": aid[:8],
    }
