"""
Junior circuit — the recruit-history generator.

This is NOT a second game and NOT the sprawling junior ecosystem the design doc
imagined. It is a one-shot pipeline that runs ONCE per recruiting class, *before*
recruiting opens, and freezes a believable pre-college résumé onto every recruit:

    generate class → assign tiers → run the junior calendar → rank → badge → freeze

so a recruit arrives in recruiting already feeling lived-in — tournament results,
a ranking that climbed across the year, and permanent achievement badges.

Closed ecosystem
----------------
Every player in every draw is a recruit the game generated. There are no anonymous
opponents and no synthetic filler. Future college teammates may have faced each
other as juniors; rivals carry histories in from before college. If only four
players enter a state championship, that is fine — consistency beats realistic
draw sizes (see the build spec).

The circuit reuses the engine's individual-tournament framework
(`engine.run_tournament`), which only runs once per class here but is reusable for
NCAA Singles/Doubles and conference individual titles later.

Determinism: a single seed threads the tier draw, every tournament, and the (small)
participation rolls, so the same class + seed reproduce identical résumés.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from engine import run_tournament

# --------------------------------------------------------------------------
# Tournament calendar — the schedule IS the tier system. A player reveals their
# level by the events they enter, so no separate classification engine is needed.
# (name, level, month). Levels rank by prestige: Major > Premier > National >
# Development > State.
# --------------------------------------------------------------------------
CALENDAR: list[tuple[str, str, int]] = [
    # Junior Major Series — the junior equivalent of the four Grand Slams.
    ("Junior Chinese Open", "Major", 1),
    ("Junior Casablanca Open", "Major", 4),
    ("Junior São Paulo Open", "Major", 7),
    ("Junior Mexican Open", "Major", 9),
    # Premier International — ITF J500-class; not majors but nearly as prestigious.
    ("Easter Bowl", "Premier", 4),
    ("Bonfiglio Cup", "Premier", 5),
    ("Osaka Cup", "Premier", 7),
    ("Kalamazoo Championships", "Premier", 8),
    ("Orange Bowl", "Premier", 12),
    # National Circuit — the strongest domestic events.
    ("Winter Nationals", "National", 2),
    ("Spring Nationals", "National", 4),
    ("National Championships", "National", 6),
    ("Summer Nationals", "National", 8),
    ("L1 Circuit", "National", 10),
    # Development Circuit — where the bulk of recruits spend their careers.
    ("L2", "Development", 3),
    ("L3", "Development", 5),
    ("L4", "Development", 9),
    ("L5", "Development", 11),
    # State Circuit — important, but the bottom of the competitive ladder.
    ("State Championships", "State", 7),
]
_EVENT_LEVEL = {name: level for name, level, _ in CALENDAR}
_EVENT_MONTH = {name: month for name, level, month in CALENDAR}

# Which events each STR-driven tier typically enters. Tier 1 rarely touches state
# championships; most college recruits live in Tier 3.
TIER_EVENTS: dict[int, list[str]] = {
    1: ["Junior Chinese Open", "Junior Casablanca Open", "Junior São Paulo Open",
        "Junior Mexican Open", "Easter Bowl", "Bonfiglio Cup", "Osaka Cup",
        "Kalamazoo Championships", "Orange Bowl"],
    2: ["Winter Nationals", "Spring Nationals", "National Championships",
        "Summer Nationals", "L1 Circuit", "L2"],
    3: ["L2", "L3", "L4", "State Championships"],
    4: ["State Championships", "L4", "L5"],
}

# Tier cutoffs as a cumulative fraction of the STR-sorted class. A thin international
# elite on top, a national-elite band, a thick regional body, then a local tail.
TIER_CUTOFFS = [(0.05, 1), (0.25, 2), (0.65, 3), (1.01, 4)]
TIER_LABELS = {1: "International Elite", 2: "National Elite",
               3: "Regional / State Elite", 4: "Local Competitive"}

# Snapshot dates the ranking history reports at — domestic on the US junior rhythm,
# international on the ITF rhythm (the build spec's two example tables).
US_SNAPSHOTS = [("Jan", 1), ("Apr", 4), ("Aug", 8), ("Dec", 12)]
INTL_SNAPSHOTS = [("Jan", 1), ("May", 5), ("Oct", 10), ("Dec", 12)]

_MONTH_ABBR = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

# A draw is capped at this size; bigger fields split into parallel sections (real
# junior tennis runs many L4/L5 draws at once), so every recruit gets matches.
SECTION_CAP = 32
# Probability a tier-eligible player actually enters a given event (varies résumés).
ENTER_P = 0.72

# Ranking points: prestige base × how far you went, plus a small participation point.
_LEVEL_BASE = {"Major": 1000, "Premier": 600, "National": 300,
               "Development": 120, "State": 80}
_FINISH_FACTOR = {"Champion": 1.0, "Finalist": 0.62, "Semifinalist": 0.38,
                  "Quarterfinalist": 0.22, "R16": 0.13, "R32": 0.08,
                  "R64": 0.05, "R128": 0.03}

# Badge ladders: (rank threshold, label). Awarded if the BEST rank ever reached is
# at or below the threshold — badges are permanent milestones, so a recruit who
# touched National Top 10 keeps it even if they slide.
US_NATIONAL_BADGES = [(300, "National Top 300 Junior"), (100, "National Top 100 Junior"),
                      (50, "National Top 50 Junior"), (25, "National Top 25 Junior"),
                      (10, "National Top 10 Junior"), (1, "National No. 1 Junior")]
US_STATE_BADGES = [(25, "State Top 25 Junior"), (10, "State Top 10 Junior"),
                   (5, "State Top 5 Junior"), (1, "State No. 1 Junior")]
INTL_GLOBAL_BADGES = [(250, "Global Top 250 Junior"), (100, "Global Top 100 Junior"),
                      (50, "Global Top 50 Junior"), (25, "Global Top 25 Junior"),
                      (10, "Global Top 10 Junior"), (1, "World No. 1 Junior")]
INTL_NATION_BADGES = [(10, "Nation Top 10 Junior"), (5, "Nation Top 5 Junior"),
                      (1, "Nation No. 1 Junior")]


@dataclass
class _Entry:
    """One recruit's accumulated junior results, keyed for ranking math."""
    results: list                      # [(month, tournament, level, finish_label)]

    def points_through(self, month: int) -> float:
        return sum(_result_points(level, finish)
                   for (m, _t, level, finish) in self.results if m <= month)


def _result_points(level: str, finish: str) -> float:
    return _LEVEL_BASE.get(level, 80) * _FINISH_FACTOR.get(finish, 0.02) + 8.0


def assign_tiers(recruits: list) -> None:
    """Sort by STR and stamp each recruit's competitive tier (1 = elite … 4 = local).
    Tier drives which events a player enters, so it has to come first."""
    ordered = sorted(recruits, key=lambda p: (-p.str_value(), p.pid))
    n = max(1, len(ordered))
    for i, p in enumerate(ordered):
        q = (i + 1) / n
        p.junior_tier = next(t for cut, t in TIER_CUTOFFS if q <= cut)


def _sections(players: list, rng: random.Random) -> list[list]:
    """Split a field into parallel draws of <= SECTION_CAP, spreading strength evenly
    (serpentine over the STR-sorted list) so each section has a real title race."""
    if len(players) <= SECTION_CAP:
        return [players] if players else []
    ordered = sorted(players, key=lambda p: (-p.str_value(), p.pid))
    n_sec = (len(ordered) + SECTION_CAP - 1) // SECTION_CAP
    buckets: list[list] = [[] for _ in range(n_sec)]
    forward = True
    for i in range(0, len(ordered), n_sec):
        chunk = ordered[i:i + n_sec]
        idxs = range(n_sec) if forward else range(n_sec - 1, -1, -1)
        for player, b in zip(chunk, idxs):
            buckets[b].append(player)
        forward = not forward
    return [b for b in buckets if b]


def _play_juniors(a, b, *, seed: int):
    """Decide one junior match between two recruits with the fast engine model."""
    from engine import simulate_fast
    res = simulate_fast(a.engine_player(), b.engine_player(), seed=seed)
    return a if res.winner == 0 else b


def _run_event(name: str, level: str, month: int, field: list,
               rng: random.Random, log: dict) -> None:
    """Run one event (possibly several parallel sections) and record each entrant's
    finish into `log` (pid -> _Entry)."""
    for section in _sections(field, rng):
        if len(section) < 2:
            continue
        result = run_tournament(section, seed=rng.randint(1, 10 ** 9),
                                play=_play_juniors, key=lambda p: p.str_value())
        for idx, p in enumerate(result.entrants):
            finish = result.finish_of(idx)
            if finish is None:
                continue
            log.setdefault(p.pid, _Entry(results=[])).results.append(
                (month, name, level, finish))


def _eligible_field(recruits: list, event: str, rng: random.Random) -> list:
    """Recruits who enter `event`: tier-eligible, rolled in, and — for the US-only
    State Championships — domestic (it groups by state below)."""
    out = []
    for p in recruits:
        if event not in TIER_EVENTS.get(p.junior_tier, []):
            continue
        if event == "State Championships" and not p.domestic:
            continue
        if rng.random() < ENTER_P:
            out.append(p)
    return out


def _rank_within(players: list, log: dict, month: int) -> dict[str, int]:
    """1-based ranking of `players` by points through `month` (STR breaks ties)."""
    ordered = sorted(
        players,
        key=lambda p: (-(log[p.pid].points_through(month) if p.pid in log else 0.0),
                       -p.str_value(), p.pid))
    return {p.pid: i for i, p in enumerate(ordered, 1)}


def _badges_for(best: int | None, ladder) -> list[str]:
    """All milestone labels a best-ever rank of `best` clears, highest first."""
    if best is None:
        return []
    return [label for thresh, label in reversed(ladder) if best <= thresh]


def run_junior_circuit(klass, *, seed: int = 0) -> None:
    """Run the whole junior circuit over `klass` and freeze the résumé onto every
    recruit. Idempotent: a class is only processed once."""
    if getattr(klass, "circuit_done", False):
        return
    recruits = klass.recruits
    grad_year = klass.grad_year
    rng = random.Random(f"{seed}|junior-circuit|{klass.gender}|{grad_year}")

    assign_tiers(recruits)

    # ---- play the calendar (chronologically) into a per-recruit result log ----
    log: dict[str, _Entry] = {}
    for name, level, month in sorted(CALENDAR, key=lambda e: e[2]):
        if name == "State Championships":
            # Closed ecosystem, grouped by home state: each state's draw is its own
            # field, however small.
            by_state: dict[str, list] = {}
            for p in _eligible_field(recruits, name, rng):
                by_state.setdefault(p.region, []).append(p)
            for state in sorted(by_state):
                _run_event(name, level, month, by_state[state], rng, log)
        else:
            _run_event(name, level, month, _eligible_field(recruits, name, rng), rng, log)

    # ---- coverage: a recruit with no results enters one fallback home event so
    # every profile reads lived-in (the spec's whole point) ----
    fallback_event = {1: "Easter Bowl", 2: "L1 Circuit", 3: "State Championships",
                      4: "State Championships"}
    extra: dict[str, list] = {}
    for p in recruits:
        if p.pid in log:
            continue
        ev = fallback_event.get(p.junior_tier, "L5")
        if ev == "State Championships" and not p.domestic:
            ev = "L4"
        extra.setdefault(ev, []).append(p)
    for ev, players in extra.items():
        _run_event(ev, _EVENT_LEVEL[ev], _EVENT_MONTH[ev], players, rng, log)

    # ---- rankings + badges, split US (national/state) vs intl (global/nation) ----
    domestic = [p for p in recruits if p.domestic]
    intl = [p for p in recruits if not p.domestic]
    state_pools: dict[str, list] = {}
    for p in domestic:
        state_pools.setdefault(p.region, []).append(p)
    nation_pools: dict[str, list] = {}
    for p in intl:
        nation_pools.setdefault(p.region, []).append(p)

    _rank_and_freeze(domestic, log, US_SNAPSHOTS, grad_year, state_pools,
                     "National", "State", US_NATIONAL_BADGES, US_STATE_BADGES)
    _rank_and_freeze(intl, log, INTL_SNAPSHOTS, grad_year, nation_pools,
                     "Global", "Nation", INTL_GLOBAL_BADGES, INTL_NATION_BADGES)

    # ---- freeze the result lists (chronological, scores/opponents intentionally
    # absent — only participation + finish) ----
    for p in recruits:
        entry = log.get(p.pid)
        rows = sorted(entry.results, key=lambda r: r[0]) if entry else []
        p.junior_results = [
            {"date": f"{_MONTH_ABBR[m]} {grad_year}", "tournament": t,
             "level": level, "result": finish}
            for (m, t, level, finish) in rows]

    klass.circuit_done = True


def _rank_and_freeze(players, log, snapshots, grad_year, sub_pools,
                     primary_label, secondary_label, primary_ladder, secondary_ladder):
    """Compute the ranking-history progression + best-rank badges for one population
    (domestic or international) and freeze it onto each recruit."""
    best_primary: dict[str, int] = {}
    best_secondary: dict[str, int] = {}
    history: dict[str, list] = {p.pid: [] for p in players}

    for label, month in snapshots:
        primary_rank = _rank_within(players, log, month)
        sub_ranks: dict[str, dict[str, int]] = {}
        for key, pool in sub_pools.items():
            sub_ranks[key] = _rank_within(pool, log, month)
        for p in players:
            pr = primary_rank[p.pid]
            sr = sub_ranks.get(p.region, {}).get(p.pid)
            history[p.pid].append({
                "date": f"{label} {grad_year}",
                "primary_label": primary_label, "primary": pr,
                "secondary_label": secondary_label, "secondary": sr,
            })
            best_primary[p.pid] = min(best_primary.get(p.pid, pr), pr)
            if sr is not None:
                best_secondary[p.pid] = min(best_secondary.get(p.pid, sr), sr)

    for p in players:
        p.ranking_history = history[p.pid]
        badges = _badges_for(best_primary.get(p.pid), primary_ladder)
        badges += _badges_for(best_secondary.get(p.pid), secondary_ladder)
        p.junior_badges = badges
