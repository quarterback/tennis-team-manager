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

import bisect
import zlib
from dataclasses import dataclass

from app.development import overall_to_str

DIVISIONS = ("D1", "D2", "D3", "D4")
_scan_cache: dict = {}

# US regions for the Portal Search hometown filter — a recruiting-style 6-way cut
# (finer than the 4 Census regions where tennis density warrants it: Texas/South
# Central split out, Mountain vs West Coast split). DC files under Mid-Atlantic.
US_REGIONS: dict[str, str] = {
    # Northeast
    "ME": "Northeast", "NH": "Northeast", "VT": "Northeast", "MA": "Northeast",
    "RI": "Northeast", "CT": "Northeast", "NY": "Northeast", "NJ": "Northeast",
    "PA": "Northeast",
    # Mid-Atlantic / Upper South
    "DE": "Mid-Atlantic", "MD": "Mid-Atlantic", "DC": "Mid-Atlantic",
    "VA": "Mid-Atlantic", "WV": "Mid-Atlantic",
    # Southeast
    "NC": "Southeast", "SC": "Southeast", "GA": "Southeast", "FL": "Southeast",
    "TN": "Southeast", "KY": "Southeast", "AL": "Southeast", "MS": "Southeast",
    # South Central
    "TX": "South Central", "OK": "South Central", "AR": "South Central",
    "LA": "South Central",
    # Midwest
    "OH": "Midwest", "MI": "Midwest", "IN": "Midwest", "IL": "Midwest",
    "WI": "Midwest", "MN": "Midwest", "IA": "Midwest", "MO": "Midwest",
    "KS": "Midwest", "NE": "Midwest", "ND": "Midwest", "SD": "Midwest",
    # Mountain
    "CO": "Mountain", "UT": "Mountain", "NV": "Mountain", "AZ": "Mountain",
    "NM": "Mountain", "ID": "Mountain", "MT": "Mountain", "WY": "Mountain",
    # West Coast
    "CA": "West Coast", "OR": "West Coast", "WA": "West Coast", "AK": "West Coast",
    "HI": "West Coast",
}
US_REGION_ORDER = ["Northeast", "Mid-Atlantic", "Southeast", "South Central",
                   "Midwest", "Mountain", "West Coast"]


def home_state(r) -> str:
    """2-letter US state parsed from a domestic player's ``hometown`` ("City, ST"),
    else "" (international, or unparseable)."""
    if not getattr(r, "domestic", False):
        return ""
    ht = getattr(r, "hometown", "") or ""
    tail = ht.rsplit(",", 1)[-1].strip().upper() if "," in ht else ""
    return tail if tail in US_REGIONS else ""


def home_region(r) -> str:
    return US_REGIONS.get(home_state(r), "")


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
    cur_overall: int              # OVERALL now (static talent, 20–80)
    true_overall: int             # OVERALL ceiling (static talent, 20–80)
    ovr_upside: int               # true_overall - cur_overall (untapped talent)
    live_str: float               # results-based STR (dynamic, this season's play)
    live_rel: float               # STR reliability 0–1 (grows with matches)
    walk_on: bool
    scholarship: float
    schol_label: str
    line: int | None              # current lineup slot on their own team (1–6) or None
    team_pi_rank: int
    team_tier: str
    hometown: str = ""            # "City, ST" (domestic) / "City, NAT" (intl)
    domestic: bool = False        # US-born (hometown state parseable)
    # filled in the second pass (need global tables):
    talent_pct: float = 0.0       # global true-talent percentile (same gender, all div)
    team_level_pct: float = 0.0   # their program's level percentile
    placement_gap: float = 0.0    # talent_pct - team_level_pct (>0 = underplaced)
    deserved_school: str = ""
    deserved_division: str = ""
    deserved_pi_rank: int = 0


def _world_stamp(seed: int):
    import app.world as world
    from app import overrides as ov
    try:
        if world.exists(seed):
            w = world.load_world(seed)
            # roster_version() folds in transfers/lineups so the scan refreshes
            # the moment the fall portal commits (which changes rosters but NOT
            # the world week) — not only on a week tick.
            return (w["id"], w["year"], w["week"], ov.roster_version())
    except Exception:
        pass
    return ("noworld", 0, 0, "")


def scan(gender: str, seed: int | None = None) -> dict:
    """Full god-mode talent scan for one gender across every division. Returns
    ``{players, teams, by_pid, team_ladder}``, memoised per world snapshot."""
    from app.web.state import DEFAULT_SEED
    from app import worldconfig as _wc
    if seed is None:
        seed = DEFAULT_SEED
    # The fit-band reach is live-tunable, so fold it into the cache key — nudging the knob
    # must recompute the FITS column, not serve a stale scan.
    fit_up, fit_down = _wc.fit_reach_up(), _wc.fit_reach_down()
    key = (_world_stamp(seed), gender, fit_up, fit_down)
    cached = _scan_cache.get(key)
    if cached is not None:
        return cached

    from app import economy
    from app.ncaa import load_division, build_roster, lineup_size
    from app.web.state import ranking_rows

    # Load THIS world-year's live rosters into the shared cache before reading any
    # `build_roster` — the same hinge every live surface uses (state.get_season).
    # Without it the scan reads whatever rosters happen to be cached (often the
    # deterministic year-0 base), so once players develop/graduate/transfer at a
    # rollover the bureau lists stale pids and every "player" link 404s.
    import app.world as world
    import app.seasonmode as sm
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
        # Live, results-based STR for this division's season — the dynamic rating
        # that actually drives weekly lineups. Unplayed players aren't in the map;
        # they fall back to the ability prior (overall_to_str), which is also the
        # seed converge_ids blends toward, so STR == "talent so far" until results
        # accumulate. STR is the ONLY surfaced STR; OVERALL carries static talent.
        try:
            sid = sm.find_season(division, gender, seed=world.current_year_seed(seed))
            strmap = sm.season_player_str(sid) if sid else {}
        except Exception:
            strmap = {}
        for prog in div.programs:
            roster = build_roster(prog)
            if not roster:
                continue
            # The TALENT starting card (by current overall — the division's lineup
            # size, ncaa.lineup_size) feeds the program-level metric used for the
            # "deserved program" ladder — a talent comparison, so it stays on
            # OVERALL, independent of who's hot. The key stays `top6_cur` (a stored
            # name, read by the fit/underplaced boards) though the card may be 8/10.
            top6 = roster[:lineup_size(division)]
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
            prog_players: list[Intel] = []
            for p in roster:
                cur_o = p.current_overall()
                true_o = p.ceiling_overall()
                lstr, lrel = strmap.get(p.pid, (overall_to_str(cur_o), 0.0))
                schol = float(getattr(p, "scholarship", 0.0) or 0.0)
                prog_players.append(Intel(
                    pid=p.pid, name=p.name, country=getattr(p, "country", ""),
                    school=prog.school, division=division, gender=gender,
                    class_year=getattr(p, "class_year", ""),
                    hometown=getattr(p, "hometown", ""),
                    domestic=bool(getattr(p, "domestic", False)),
                    cur_overall=cur_o, true_overall=true_o, ovr_upside=true_o - cur_o,
                    live_str=round(lstr, 1), live_rel=round(lrel, 2),
                    walk_on=bool(getattr(p, "walk_on", False)),
                    scholarship=schol, schol_label=economy.fraction_label(schol),
                    line=None,
                    team_pi_rank=rk, team_tier=getattr(prog, "conf_abbr", ""),
                ))
            # The displayed singles ladder follows live STR (form) — the same signal
            # the coach AI sets lineups by — so the Lineup Lab mirrors who'd actually
            # play, not a static talent order.
            prog_players.sort(key=lambda r: r.live_str, reverse=True)
            _card = lineup_size(division)
            for i, r in enumerate(prog_players, 1):
                r.line = i if i <= _card else None
            players.extend(prog_players)

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

    # The "fits" band, by CALIBRE in grade points (team_level and true_overall are both the
    # 20–80 OVR scale): any program a talent would genuinely slot into — from a hair above their
    # level (a slight reach) down through everywhere they'd be a clear upgrade/star. Grade-based
    # so it stays tier-appropriate: a blue-chip spans the whole of D1 (top → low), NOT pushed
    # into D3/D4 where they'd just dominate; a mid talent naturally spans the D1/D2/D3 boundary.
    # We surface ONE program from that band by a STABLE per-player hash, so the column shows the
    # full spread of matching programs — any tier that fits, never the same four repeated — while
    # each player's fit stays stable. (The per-row Fit Finder link lists the full ranked set.)
    # Live-tunable band width (Analytics Bureau UI) — see worldconfig.fit_reach_up/down.
    _FIT_UP, _FIT_DOWN = fit_up, fit_down
    asc = ladder[::-1]                                   # ascending by team_level
    asc_lvls = [t["team_level"] for t in asc]
    for r in players:
        t = teams.get(r.school, {})
        r.team_level_pct = t.get("level_pct", 0.0)
        r.placement_gap = round(r.talent_pct - r.team_level_pct, 4)
        if asc:
            i0 = bisect.bisect_left(asc_lvls, r.true_overall - _FIT_DOWN)
            i1 = bisect.bisect_right(asc_lvls, r.true_overall + _FIT_UP)
            band = asc[i0:i1] or [min(ladder, key=lambda p: abs(p["team_level"] - r.true_overall))]
            d = band[zlib.crc32(r.pid.encode()) % len(band)]
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
        # match base class so medical-redshirt players (RS-Jr) still file under "Jr"
        rows = [r for r in rows
                if (r.class_year[3:] if r.class_year.startswith("RS-") else r.class_year) == class_year]
    if q:
        ql = q.strip().lower()
        rows = [r for r in rows if ql in r.name.lower() or ql in r.school.lower()]
    keys = {
        "gap": lambda r: (r.placement_gap, r.true_overall),
        "now": lambda r: (r.live_str, r.cur_overall, r.placement_gap),   # hottest now
        "talent": lambda r: (r.true_overall, r.placement_gap),
    }
    rows.sort(key=keys.get(sort, keys["gap"]), reverse=True)
    return rows


def portal_search(gender: str, seed: int | None = None, division: str = "All",
                  class_year: str = "All", scope: str = "all", state: str = "All",
                  region: str = "All", sort: str = "talent", q: str = "") -> list[Intel]:
    """Searchable directory of the whole placeable universe — every rostered
    player, the pool you pull transfers from. Immersion aid for portal placement:
    filter by where a player is FROM (US state / region / domestic vs
    international) and by class, division, name; sort by talent, form, or origin.

    `gender`: 'men' | 'women' | 'all' (both, merged). Picking one halves the pool.
    `scope`: 'all' | 'us' (domestic only) | 'intl' (foreign only).
    `state`: 2-letter US code (implies domestic). `region`: a US_REGIONS bucket.
    `q` matches name, school, or hometown.
    """
    if gender == "all":
        rows = list(scan("men", seed)["players"]) + list(scan("women", seed)["players"])
    else:
        rows = list(scan(gender, seed)["players"])
    if division != "All":
        rows = [r for r in rows if r.division == division]
    if scope == "us":
        rows = [r for r in rows if r.domestic]
    elif scope == "intl":
        rows = [r for r in rows if not r.domestic]
    if state and state != "All":
        st = state.upper()
        rows = [r for r in rows if home_state(r) == st]
    if region and region != "All":
        rows = [r for r in rows if home_region(r) == region]
    if class_year != "All":
        rows = [r for r in rows
                if (r.class_year[3:] if r.class_year.startswith("RS-") else r.class_year) == class_year]
    if q:
        ql = q.strip().lower()
        rows = [r for r in rows
                if ql in r.name.lower() or ql in r.school.lower() or ql in (r.hometown or "").lower()]
    _CLASS_ORD = {"Fr": 0, "So": 1, "Jr": 2, "Sr": 3}
    keys = {
        "talent": (lambda r: (r.true_overall, r.live_str), True),
        "now": (lambda r: (r.live_str, r.cur_overall), True),
        "name": (lambda r: r.name.lower(), False),
        "state": (lambda r: (home_state(r) or "~~", r.name.lower()), False),  # US first, then A–Z
        "class": (lambda r: (_CLASS_ORD.get(
            r.class_year[3:] if r.class_year.startswith("RS-") else r.class_year, 9),
            -r.true_overall), False),
    }
    key, rev = keys.get(sort, keys["talent"])
    rows.sort(key=key, reverse=rev)
    return rows


def portal_search_states(gender: str, seed: int | None = None) -> list[str]:
    """US states actually present in this world's rosters, in region order then
    alphabetical — so the dropdown only offers states you'd find someone from."""
    genders = ("men", "women") if gender == "all" else (gender,)
    present = {home_state(r) for g in genders for r in scan(g, seed)["players"]}
    present.discard("")
    return sorted(present, key=lambda s: (US_REGION_ORDER.index(US_REGIONS[s]), s))


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
                weakest_funded_true=wk.true_overall, weakest_funded_schol=wk.schol_label,
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


_DIVRANK = {"D1": 0, "D2": 1, "D3": 2, "D4": 3}


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
    team_level_ovr: int           # program's top-6 talent average (OVERALL, 20–80)
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
            tier=t["tier"], team_level_ovr=round(t["team_level"]),
            slot=slot, slot_label=_slot_label(slot), aid_label=aid,
            move_up=t["level_pct"] > here_level)))
    out.sort(key=lambda x: x[0], reverse=True)
    return p, [ft for _, ft in out[:limit]]


_IMPACT_SLOT = {"first": 1, "top3": 3}   # how high a fit must project to show;
# the third tier ("top6", the legacy name the UI keeps) means "would crack the
# lineup" and resolves to the user's division card size at query time.


def targets_for_my_program(seed: int | None = None, div_filter: str = "All",
                           sort: str = "fit", upgrades_only: bool = False,
                           impact: str = "top3") -> dict | None:
    """The INVERSE of the Fit Finder, scoped to the ONE program the user coaches
    (`worldconfig.user_program`): every player in the world who would crack YOUR lineup —
    a starter or upgrade on your roster — ranked by how much they'd help. `impact` trims to the
    meaningful ones (a Top-3 starter by default, since with compressed talent almost anyone
    clears a weak No. 6). Returns None if no program has been picked yet."""
    from app import worldconfig
    from app.ncaa import lineup_size
    from app.web.rankings_data import crest
    up = worldconfig.user_program()
    if not up:
        return None
    gender, my_school, my_div = up["gender"], up["school"], up["division"]
    data = scan(gender, seed)
    mine = sorted((r for r in data["players"] if r.school == my_school),
                  key=lambda r: r.cur_overall, reverse=True)
    my_top6 = mine[:lineup_size(my_div)]                # my current singles ladder (by ability)
    my_cur = [r.cur_overall for r in my_top6]
    n_start = len(my_top6)
    my_abbr, my_color = crest(my_school)

    slot_cap = (lineup_size(my_div) if impact == "top6"
                else _IMPACT_SLOT.get(impact, 3))
    targets = []
    for r in data["players"]:
        if r.school == my_school:
            continue
        slot = 1 + sum(1 for cs in my_cur if cs > r.cur_overall)
        if slot > slot_cap:                             # not a high-enough fit for this impact tier
            continue
        bumps = my_top6[slot - 1] if slot - 1 < n_start else None   # who they'd leapfrog (None = open slot)
        is_upgrade = bumps is not None
        if upgrades_only and not is_upgrade:
            continue
        if div_filter != "All" and r.division != div_filter:
            continue
        dr = _DIVRANK[r.division] - _DIVRANK[my_div]
        ab, co = crest(r.school)
        targets.append({
            "pid": r.pid, "name": r.name, "country": r.country,
            "secondary_country": getattr(r, "secondary_country", ""), "gender": gender,
            "school": r.school, "division": r.division, "abbr": ab, "color": co,
            "line": r.line, "cur_overall": r.cur_overall, "true_overall": r.true_overall,
            "live_str": r.live_str, "walk_on": r.walk_on,
            "slot": slot, "slot_label": _slot_label(slot),
            "is_upgrade": is_upgrade,
            "upgrade_over": bumps.name if bumps else "(open lineup slot)",
            "upgrade_over_ovr": bumps.cur_overall if bumps else 0,
            "from": "up" if dr < 0 else ("down" if dr > 0 else "lateral"),
        })

    keys = {
        "fit": lambda t: (t["slot"], -t["true_overall"], -t["live_str"]),
        "talent": lambda t: (-t["true_overall"], t["slot"]),
        "str": lambda t: (-t["live_str"], t["slot"]),
    }
    reverse = False
    targets.sort(key=keys.get(sort, keys["fit"]), reverse=reverse)

    return {
        "program": {"school": my_school, "division": my_div, "gender": gender,
                    "abbr": my_abbr, "color": my_color},
        "my_top6": [{"name": r.name, "ovr": r.cur_overall, "str": r.live_str} for r in my_top6],
        "targets": targets, "n": len(targets),
        "n_instant1": sum(1 for t in targets if t["slot"] == 1),
        "n_upgrade": sum(1 for t in targets if t["is_upgrade"]),
        "sort": sort, "div_filter": div_filter, "upgrades_only": upgrades_only,
        "impact": impact,
    }


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


# ---- Lineup Lab: every team's singles ladder by conference ------------------

def conference_list(division: str, gender: str, seed: int | None = None) -> list[str]:
    """Conference abbreviations in a division, with team counts, for the selector."""
    from app.ncaa import load_division
    div = load_division(division, gender)
    counts: dict[str, int] = {}
    for p in div.programs:
        counts[p.conf_abbr] = counts.get(p.conf_abbr, 0) + 1
    return sorted(counts)


def conference_lineups(division: str, gender: str, conf: str, seed: int | None = None,
                       highlight: str | None = None) -> list[dict]:
    """Every team in a conference with its top-6 singles ladder — the data behind
    the lineup-comparison plot and the per-team depth table. The ladder follows
    live, results-based STR (form), the same order the coach AI plays. Each player
    carries both `str` (results STR) and `ovr` (static OVERALL talent) so the view
    can toggle lens; team aggregates are provided in both. Each team:
    {school, lineup:[{line,name,pid,str,ovr,class,walk_on}], avg/top/low (STR) +
    avg_ovr/top_ovr/low_ovr}."""
    from app.ncaa import lineup_size
    data = scan(gender, seed)
    n_card = lineup_size(division)
    teams: dict[str, dict] = {}
    for r in data["players"]:
        if r.division != division or r.team_tier != conf or r.line is None:
            continue
        teams.setdefault(r.school, {})[r.line] = r
    rows = []
    for school, slots in teams.items():
        lineup = [{"line": ln, "name": r.name, "pid": r.pid,
                   "str": r.live_str, "ovr": r.cur_overall,
                   "class": r.class_year, "walk_on": r.walk_on}
                  for ln in range(1, n_card + 1) if (r := slots.get(ln))]
        strs = [x["str"] for x in lineup]
        ovrs = [x["ovr"] for x in lineup]
        rows.append({
            "school": school, "lineup": lineup,
            "avg": round(sum(strs) / len(strs), 1) if strs else 0.0,
            "top": max(strs) if strs else 0.0,
            "low": min(strs) if strs else 0.0,
            "avg_ovr": round(sum(ovrs) / len(ovrs)) if ovrs else 0,
            "top_ovr": max(ovrs) if ovrs else 0,
            "low_ovr": min(ovrs) if ovrs else 0,
            "highlight": school == highlight,
        })
    rows.sort(key=lambda t: t["avg"], reverse=True)
    for i, t in enumerate(rows, 1):
        t["rank"] = i
    return rows


# ---- Team Scanner: every program in one cross-division board ----------------

_TEAM_SORTS = {
    # metric key -> row key(s); every sort tiebreaks on the talent ladder so
    # equal-metric teams keep a stable, meaningful order.
    "card_str":   lambda t: (t["card_str"], -t["level_rank"]),
    "card_ovr":   lambda t: (t["card_ovr"], -t["level_rank"]),
    "roster_ovr": lambda t: (t["roster_ovr"], -t["level_rank"]),
    "ceiling":    lambda t: (t["ceiling"], -t["level_rank"]),
    "upside":     lambda t: (t["upside"], t["ceiling"]),
    "buried":     lambda t: (t["n_buried"], t["ceiling"]),
    "best":       lambda t: (t["best_ovr"], -t["level_rank"]),
}


def team_board(gender: str, seed: int | None = None, division: str = "All",
               conf: str = "All", sort: str = "card_ovr", direction: str = "desc",
               q: str = "") -> list[dict]:
    """Every program in one scannable board, across ALL divisions — the team-level
    lens the player boards don't give. Per team, both rating systems side by side:

      card_str   — avg live results STR of the actual starters (the division's
                   full singles card, not a hardcoded 6)
      card_ovr   — avg CURRENT ability (OVERALL, 20–80) of the talent top card:
                   the honest "how good are they right now", immune to the
                   freshman/new-player STR lag
      roster_ovr — avg current OVERALL of the whole roster (depth included)
      ceiling    — avg true ceiling of the top card (program's talent level, the
                   same number the cross-division ladder ranks on)
      upside     — ceiling − card_ovr: how much the current core has left to grow
      n_buried   — how many rostered players qualify for the Underplaced board

    `direction` flips the sort ('asc' surfaces the weakest — the god-mode "which
    team do I want to build up" cut). `q` filters by school or conference."""
    data = scan(gender, seed)
    by_school: dict[str, list[Intel]] = {}
    for r in data["players"]:
        by_school.setdefault(r.school, []).append(r)

    rows: list[dict] = []
    for t in data["team_ladder"]:
        roster = by_school.get(t["school"], [])
        starters = [r.live_str for r in roster if r.line is not None]
        card_ovrs = t["top6_cur"]            # current OVERALL of the talent top card
        all_ovrs = [r.cur_overall for r in roster]
        card_ovr = sum(card_ovrs) / len(card_ovrs) if card_ovrs else 0.0
        n_buried = sum(1 for r in roster
                       if r.placement_gap >= UNDERPLACED_MIN_GAP
                       and r.true_overall >= UNDERPLACED_MIN_TRUE)
        rows.append({
            "school": t["school"], "division": t["division"], "gender": gender,
            "conf": t["tier"], "pi_rank": t["pi_rank"], "n_teams": t["n_teams"],
            "level_rank": t["level_rank"], "n_roster": len(roster),
            "card_str": round(sum(starters) / len(starters), 1) if starters else 0.0,
            "card_ovr": round(card_ovr, 1),
            "roster_ovr": round(sum(all_ovrs) / len(all_ovrs), 1) if all_ovrs else 0.0,
            "ceiling": round(t["team_level"], 1),
            "upside": round(t["team_level"] - card_ovr, 1),
            "best_ovr": max(all_ovrs) if all_ovrs else 0,
            "n_buried": n_buried,
        })

    if division != "All":
        rows = [t for t in rows if t["division"] == division]
    if conf != "All":
        rows = [t for t in rows if t["conf"] == conf]
    if q:
        ql = q.strip().lower()
        rows = [t for t in rows if ql in t["school"].lower() or ql in t["conf"].lower()]
    rows.sort(key=_TEAM_SORTS.get(sort, _TEAM_SORTS["card_ovr"]),
              reverse=(direction != "asc"))
    for i, t in enumerate(rows, 1):
        t["rank"] = i
    return rows


def team_board_conferences(gender: str, division: str, seed: int | None = None) -> list[str]:
    """Conference abbreviations present on the board for a division filter (empty
    for "All" — a conference only means something inside its division)."""
    if division == "All":
        return []
    return sorted({t["tier"] for t in scan(gender, seed)["team_ladder"]
                   if t["division"] == division})


def team_rosters(gender: str, schools: list[str], seed: int | None = None) -> dict[str, list[dict]]:
    """Full rosters for the given schools, in TALENT order (current OVERALL — the
    reliable lens; live STR only reflects who they happened to play) — the
    expandable per-team view under each Team Scanner row. Each player keeps their
    `line` (the STR-based slot the coach AI actually plays), so a high-OVR player
    with a low/no line reads instantly as buried."""
    data = scan(gender, seed)
    want = set(schools)
    out: dict[str, list[dict]] = {s: [] for s in schools}
    for r in data["players"]:
        if r.school not in want:
            continue
        out[r.school].append(r)
    for s, roster in out.items():
        roster.sort(key=lambda r: (-r.cur_overall, -r.true_overall, r.name))
        out[s] = [{
            "pid": r.pid, "name": r.name, "country": r.country,
            "class_year": r.class_year, "line": r.line,
            "live_str": r.live_str, "cur_overall": r.cur_overall,
            "true_overall": r.true_overall, "ovr_upside": r.ovr_upside,
            "walk_on": r.walk_on, "schol_label": r.schol_label,
            "buried": (r.placement_gap >= UNDERPLACED_MIN_GAP
                       and r.true_overall >= UNDERPLACED_MIN_TRUE),
        } for r in roster]
    return out


# ---- Lineup Architect: assemble whole squads from underutilized talent ------

def lineup_architect(gender: str, target_division: str = "D2", seed: int | None = None,
                     pool: str = "buried", min_ovr: int = 0, max_ovr: int = 80,
                     min_str: float = 0.0, max_str: float = 99.0,
                     n_squads: int = 3) -> dict:
    """The scouting-department view: instead of surfacing buried players one at a
    time, deal them into whole singles cards for a target division and rank each
    squad against that division's real teams (by current-OVR card average).

    `pool`: 'buried' (Underplaced-board qualifiers), 'below' (anyone rostered in
    a division below the target), 'any'. OVR and STR gates are BANDS (min AND
    max), so mid/low tiers are searchable on their own — a max keeps the elite
    out of the pool instead of best-first always skimming the top. Squads are
    non-overlapping, dealt best-first within the band."""
    from app.ncaa import lineup_size
    data = scan(gender, seed)
    card = lineup_size(target_division)
    tgt_rank = _DIVRANK[target_division]

    cands = []
    for r in data["players"]:
        if pool == "buried":
            if not (r.placement_gap >= UNDERPLACED_MIN_GAP
                    and r.true_overall >= UNDERPLACED_MIN_TRUE):
                continue
        elif pool == "below":
            if _DIVRANK[r.division] <= tgt_rank:
                continue
        if not (min_ovr <= r.cur_overall <= max_ovr):
            continue
        if not (min_str <= r.live_str <= max_str):
            continue
        cands.append(r)
    cands.sort(key=lambda r: (r.cur_overall, r.true_overall), reverse=True)

    # The target division's real cards by the same metric (current OVR of the
    # talent card), so "would rank #N of M" is apples to apples.
    div_lvls = sorted((sum(t["top6_cur"]) / len(t["top6_cur"])
                       for t in data["team_ladder"]
                       if t["division"] == target_division and t["top6_cur"]),
                      reverse=True)
    n_div = len(div_lvls)

    squads = []
    for k in range(max(1, n_squads)):
        block = cands[k * card:(k + 1) * card]
        if len(block) < card:
            break
        avg_ovr = sum(r.cur_overall for r in block) / card
        squads.append({
            "players": [{
                "slot": i, "pid": r.pid, "name": r.name, "country": r.country,
                "school": r.school, "division": r.division, "gender": r.gender,
                "class_year": r.class_year, "line": r.line,
                "cur_overall": r.cur_overall, "true_overall": r.true_overall,
                "live_str": r.live_str,
            } for i, r in enumerate(block, 1)],
            "avg_ovr": round(avg_ovr, 1),
            "avg_ceil": round(sum(r.true_overall for r in block) / card, 1),
            "avg_str": round(sum(r.live_str for r in block) / card, 1),
            "rank": 1 + sum(1 for lv in div_lvls if lv > avg_ovr),
            "n_div": n_div,
        })
    return {
        "squads": squads, "pool_size": len(cands), "card": card, "n_div": n_div,
        "div_top": round(div_lvls[0], 1) if div_lvls else 0.0,
        "div_median": round(div_lvls[n_div // 2], 1) if div_lvls else 0.0,
        "leftover": max(0, len(cands) - len(squads) * card),
    }


def conference_strength(division: str, gender: str, seed: int | None = None) -> list[dict]:
    """Relative league strength across a division: every conference ranked by the
    average STR of its starters (lineup positions 1–6), with its strongest starter,
    team count, and the curated conference tier/prestige for context."""
    from app.ncaa import conf_tier, conf_prestige
    data = scan(gender, seed)
    confs: dict[str, dict] = {}
    for r in data["players"]:
        if r.division != division or r.line is None:
            continue
        d = confs.setdefault(r.team_tier, {"strs": [], "ovrs": [], "teams": set()})
        d["strs"].append(r.live_str)
        d["ovrs"].append(r.cur_overall)
        d["teams"].add(r.school)
    rows = []
    for conf, d in confs.items():
        strs, ovrs = d["strs"], d["ovrs"]
        rows.append({
            "conf": conf, "n_teams": len(d["teams"]),
            "avg_str": round(sum(strs) / len(strs), 1) if strs else 0.0,
            "top_str": round(max(strs), 1) if strs else 0.0,
            "avg_ovr": round(sum(ovrs) / len(ovrs)) if ovrs else 0,
            "top_ovr": max(ovrs) if ovrs else 0,
            "tier": conf_tier(conf), "prestige": round(conf_prestige(conf), 2),
        })
    rows.sort(key=lambda r: r["avg_str"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows
