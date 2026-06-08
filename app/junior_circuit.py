"""
Junior circuit — the recruit-history generator.

This is NOT a second game and NOT the sprawling junior ecosystem the design doc
imagined. It is a one-shot pipeline that runs ONCE per recruiting class, *before*
recruiting opens, and freezes a believable pre-college résumé onto every recruit:

    seed STR from ability → assign tiers → play the junior calendar with the FULL
    match engine → solve results-based STR → rank → badge → freeze

so a recruit arrives in recruiting already feeling lived-in — real matches against
real rivals (scores and opponents on record), a tier, an STR that climbed or slid
with form across the year, a ranking progression, and permanent badges.

Why the full engine, why before college
----------------------------------------
The junior circuit runs once per class, not continuously, so it can afford the
*full* point-by-point match engine — the best results the engine can produce. Those
matches feed the same results-based STR rating the college game uses
(`app.str_rating.converge_ids`): STR is seeded by a player's visible ability but
then SOLVED from what they actually did on court, recency-weighted, so a winning
junior rises and a slumping one regresses. Players are dynamic, not fixed.

Closed ecosystem
----------------
Every player in every draw is a recruit the game generated — no anonymous opponents,
no synthetic filler. Future college teammates may have faced each other as juniors;
rivals carry real histories in from before college. Big fields split into parallel
sections so everyone gets matches; if only four players enter a state championship,
that is fine — consistency beats realistic draw sizes (the build spec).

Determinism: one seed threads tiering, every match, and the participation rolls, so
the same class + seed reproduce identical résumés.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass

from engine import run_tournament, simulate_match
from .str_rating import converge_ids
from .development import stagger_scale

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
# international on the ITF rhythm (the build spec's two example tables). STR is
# re-solved from the season so far at each, so it grows/regresses across the year.
US_SNAPSHOTS = [("Jan", 1), ("Apr", 4), ("Aug", 8), ("Dec", 12)]
INTL_SNAPSHOTS = [("Jan", 1), ("May", 5), ("Oct", 10), ("Dec", 12)]

_MONTH_ABBR = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

# Junior development: a recruit's CURRENT (recruiting-time) ability is the END of
# the junior climb. We replay that climb across the season — start each recruit at
# their younger self (~this many development-years back) and develop them, in
# staggered waves, back UP to current. A super-bloomer was far weaker early and
# surges up the rankings; an early bloomer was always near here and gets passed as
# peers keep climbing (the "looked great at 14, ordinary by 16" arc). The recruit
# object is never mutated — only throwaway copies develop — so the recruiting board
# stays calibrated. See docs/DEV-MODEL-tennis-adaptation.md.
JUNIOR_DEV_YEARS = 1.0

# A draw is capped at this size; bigger fields split into parallel sections (real
# junior tennis runs many L4/L5 draws at once), so every recruit gets matches.
SECTION_CAP = 32
# Probability a tier-eligible player actually enters a given event (varies résumés).
ENTER_P = 0.72
# Iterations for the results-based STR fixed point (cheaper per snapshot, full final).
_SNAP_ITERS = 6
_FINAL_ITERS = 10

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


def assign_tiers(recruits: list) -> None:
    """Sort by ability STR and stamp each recruit's competitive tier (1 = elite …
    4 = local). Tier seeds which events a player enters, so it comes first — results
    then re-sort everyone via the evolved STR."""
    ordered = sorted(recruits, key=lambda p: (-p.str_value(), p.pid))
    n = max(1, len(ordered))
    for i, p in enumerate(ordered):
        q = (i + 1) / n
        p.junior_tier = next(t for cut, t in TIER_CUTOFFS if q <= cut)


def _sections(players: list, seed_rank) -> list[list]:
    """Split a field into parallel draws of <= SECTION_CAP, spreading strength evenly
    (serpentine over the rating-sorted list) so each section has a real title race."""
    if len(players) <= SECTION_CAP:
        return [players] if players else []
    ordered = sorted(players, key=lambda p: (-seed_rank(p), p.pid))
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


def _score_str(set_scores, pi: int) -> str:
    """Set-by-set scoreline from player `pi`'s perspective, e.g. '6-4 3-6 7-5'."""
    parts = []
    for a, b in set_scores:
        hi, lo = (a, b) if pi == 0 else (b, a)
        parts.append(f"{hi}-{lo}")
    return " ".join(parts)


@dataclass
class _Circuit:
    """Mutable scratch state threaded through the season build."""
    grad_year: int
    engine_players: dict          # pid -> engine.Player (built once, reused)
    finishes: dict                # pid -> [(month, name, level, finish_label)]
    matches: dict                 # pid -> [{date, tournament, round, opponent, score, won}]
    corpus: dict                  # pid -> [(month, opp_pid, my_games, opp_games)] chronological


def _run_event(c: _Circuit, name: str, level: str, month: int, field: list,
               rng: random.Random) -> None:
    """Play one event (possibly several parallel sections) with the FULL engine and
    record finishes, per-match lore (opponent + score), and the STR corpus."""
    date = f"{_MONTH_ABBR[month]} {c.grad_year}"
    for section in _sections(field, lambda p: p.str_value()):
        if len(section) < 2:
            continue
        played: dict = {}   # frozenset(pid pair) -> MatchResult

        def play(a, b, *, seed):
            res = simulate_match(c.engine_players[a.pid], c.engine_players[b.pid], seed=seed)
            played[frozenset((a.pid, b.pid))] = res
            return a if res.winner == 0 else b

        result = run_tournament(section, seed=rng.randint(1, 10 ** 9),
                                play=play, key=lambda p: p.str_value())

        for idx, p in enumerate(result.entrants):
            finish = result.finish_of(idx)
            if finish is not None:
                c.finishes.setdefault(p.pid, []).append((month, name, level, finish))

        # Walk the bracket in round order (chronological within the event). The
        # framework always calls play(seeded[hi], seeded[lo]), so hi is side 0.
        for rnd in result.rounds:
            for m in rnd:
                hp, lp = result.entrants[m.hi], result.entrants[m.lo]
                res = played[frozenset((hp.pid, lp.pid))]
                hg, lg = res.games_won            # (side0=hi, side1=lo)
                for player, opp, pi, mg, og in (
                        (hp, lp, 0, hg, lg), (lp, hp, 1, lg, hg)):
                    c.matches.setdefault(player.pid, []).append({
                        "date": date, "tournament": name, "round": m.rnd,
                        "opponent": opp.name, "score": _score_str(res.set_scores, pi),
                        "won": (res.winner == pi)})
                    c.corpus.setdefault(player.pid, []).append((month, opp.pid, mg, og))


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


def _solve_str(recruits: list, corpus: dict, priors: dict, month: int,
               iterations: int) -> dict[str, float]:
    """Results-based STR for the whole class through `month` — the closed ecosystem
    solved to a fixed point. Recruits with no matches yet sit at their ability prior,
    so everyone is rankable from the first snapshot."""
    by_player = {p.pid: [] for p in recruits}
    for pid, entries in corpus.items():
        by_player[pid] = [(opp, mg, og) for (m, opp, mg, og) in entries if m <= month]
    solved = converge_ids(by_player, priors=priors, iterations=iterations)
    return {pid: priors.get(pid, 44.0) for pid in by_player} | {
        pid: v[0] for pid, v in solved.items()}


def _rank_within(players: list, strs: dict[str, float]) -> dict[str, int]:
    """1-based ranking of `players` by results-based STR (pid breaks ties)."""
    ordered = sorted(players, key=lambda p: (-strs.get(p.pid, 0.0), p.pid))
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
    rng = random.Random(f"{seed}|junior-circuit|{klass.gender}|{klass.grad_year}")

    # Throwaway "junior selves": start each recruit at their younger self and develop
    # back up to current across the season. The recruit object itself is untouched,
    # so the recruiting board keeps the calibrated recruiting-time ability while the
    # junior matches/STR reflect the climb.
    selves = {p.pid: copy.deepcopy(p) for p in recruits}
    for p in recruits:
        selves[p.pid].regress_to_younger(JUNIOR_DEV_YEARS)
    # The younger ability is the PRIOR the results-based rating regresses toward, so
    # thin early-season records sit low and rise with results — the arc shows.
    priors = {p.pid: selves[p.pid].str_value() for p in recruits}
    assign_tiers(recruits)        # schedule by recruiting-time (current) ability

    c = _Circuit(grad_year=klass.grad_year,
                 engine_players={pid: s.engine_player() for pid, s in selves.items()},
                 finishes={}, matches={}, corpus={})

    # ---- play the calendar chronologically with the full match engine, pulsing a
    # staggered slice of development before each month so players climb in waves ----
    months = sorted({m for _, _, m in CALENDAR})
    events_by_month: dict[int, list] = {}
    for nm, lv, m in CALENDAR:
        events_by_month.setdefault(m, []).append((nm, lv))

    for mi, month in enumerate(months):
        for p in recruits:
            sc = stagger_scale(p.pid, mi, len(months), total=JUNIOR_DEV_YEARS)
            if sc:
                selves[p.pid].develop(sc)
                c.engine_players[p.pid] = selves[p.pid].engine_player()
        for (name, level) in events_by_month[month]:
            if name == "State Championships":
                by_state: dict[str, list] = {}
                for p in _eligible_field(recruits, name, rng):
                    by_state.setdefault(p.region, []).append(p)
                for state in sorted(by_state):
                    _run_event(c, name, level, month, by_state[state], rng)
            else:
                _run_event(c, name, level, month, _eligible_field(recruits, name, rng), rng)

    # ---- coverage: a recruit with no matches enters one fallback home event so
    # every profile reads lived-in (the spec's whole point) ----
    fallback = {1: "Easter Bowl", 2: "L1 Circuit", 3: "State Championships",
                4: "State Championships"}
    extra: dict[str, list] = {}
    for p in recruits:
        if p.pid in c.matches:
            continue
        ev = fallback.get(p.junior_tier, "L5")
        if ev == "State Championships" and not p.domestic:
            ev = "L4"
        extra.setdefault(ev, []).append(p)
    for ev, players in extra.items():
        _run_event(c, ev, _EVENT_LEVEL[ev], _EVENT_MONTH[ev], players, rng)

    # ---- rankings + badges from the EVOLVING results-based STR, split US
    # (national/state) vs intl (global/nation) ----
    domestic = [p for p in recruits if p.domestic]
    intl = [p for p in recruits if not p.domestic]
    state_pools: dict[str, list] = {}
    for p in domestic:
        state_pools.setdefault(p.region, []).append(p)
    nation_pools: dict[str, list] = {}
    for p in intl:
        nation_pools.setdefault(p.region, []).append(p)

    _rank_and_freeze(recruits, domestic, c, priors, US_SNAPSHOTS, state_pools,
                     "National", "State", US_NATIONAL_BADGES, US_STATE_BADGES)
    _rank_and_freeze(recruits, intl, c, priors, INTL_SNAPSHOTS, nation_pools,
                     "Global", "Nation", INTL_GLOBAL_BADGES, INTL_NATION_BADGES)

    # ---- freeze the evolved STR + the résumé (finishes + per-match lore) ----
    final = converge_ids(
        {p.pid: [(o, mg, og) for (_m, o, mg, og) in c.corpus.get(p.pid, [])]
         for p in recruits},
        priors=priors, iterations=_FINAL_ITERS)
    for p in recruits:
        s, rel = final.get(p.pid, (priors[p.pid], 0.0))
        p.junior_str = round(s, 2)
        p.junior_str_reliability = round(rel, 3)
        rows = sorted(c.finishes.get(p.pid, []), key=lambda r: r[0])
        p.junior_results = [
            {"date": f"{_MONTH_ABBR[m]} {klass.grad_year}", "tournament": t,
             "level": level, "result": finish}
            for (m, t, level, finish) in rows]
        p.junior_matches = list(c.matches.get(p.pid, []))

    klass.circuit_done = True


def _rank_and_freeze(all_recruits, players, c, priors, snapshots, sub_pools,
                     primary_label, secondary_label, primary_ladder, secondary_ladder):
    """Compute the ranking-history progression (results-based STR re-solved at each
    snapshot) + best-rank badges for one population, and freeze it onto each recruit."""
    best_primary: dict[str, int] = {}
    best_secondary: dict[str, int] = {}
    history: dict[str, list] = {p.pid: [] for p in players}

    for label, month in snapshots:
        strs = _solve_str(all_recruits, c.corpus, priors, month, _SNAP_ITERS)
        primary_rank = _rank_within(players, strs)
        sub_ranks = {k: _rank_within(pool, strs) for k, pool in sub_pools.items()}
        for p in players:
            pr = primary_rank[p.pid]
            sr = sub_ranks.get(p.region, {}).get(p.pid)
            history[p.pid].append({
                "date": f"{label} {c.grad_year}",
                "primary_label": primary_label, "primary": pr,
                "secondary_label": secondary_label, "secondary": sr,
                "str": round(strs.get(p.pid, 0.0), 1),
            })
            best_primary[p.pid] = min(best_primary.get(p.pid, pr), pr)
            if sr is not None:
                best_secondary[p.pid] = min(best_secondary.get(p.pid, sr), sr)

    for p in players:
        p.ranking_history = history[p.pid]
        p.junior_badges = (_badges_for(best_primary.get(p.pid), primary_ladder)
                           + _badges_for(best_secondary.get(p.pid), secondary_ladder))
