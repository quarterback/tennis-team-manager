"""
Season simulation for one division × gender universe.

Flow (P4/P5):
  1. Build a schedule — conference round-robin + a few non-conference duals
     (the non-conf links give RPI/APR a real strength-of-schedule graph).
  2. Simulate every dual (fast model) → dual records.
  3. Conference standings from conference duals.
  4. Compute the Power Index (APR + FQI + oGS) over the regular season.
  5. Conference tournaments (seeded by conf record, tiebreak PI) → champions
     = automatic NCAA bids.

The result feeds the rankings page and the NCAA bracket (app/bracket.py).
Seed-deterministic: same (division, gender, seed) ⇒ same season.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine import simulate_dual, Team
from .ncaa import Program, Division, load_division, build_squad, build_roster
from .rating import compute_ratings, RatingLine
from .str_rating import converge_ids
from .bracket import play_dual, _seed_positions

NONCONF_PER_TEAM = 3
NATIONAL_FIELD = 64


@dataclass
class SeasonResult:
    division: str
    gender: str
    seed: int
    programs: list[Program]
    ratings: dict[str, RatingLine]
    standings: dict[str, list[tuple]]          # conf -> [(Program, w, l), ...]
    champions: list[Program]
    duals: list[dict]
    rosters: dict = field(default_factory=dict)        # school -> list[Prospect] (full roster)
    player_str: dict = field(default_factory=dict)     # pid -> (STR, reliability)
    player_record: dict = field(default_factory=dict)  # pid -> (singles wins, losses)

    def ranked(self) -> list[Program]:
        return sorted(self.programs, key=lambda p: self.ratings[p.school].pi, reverse=True)


def _dual_record(a: Program, b: Program, sa: Team, sb: Team,
                 la: list, lb: list, *, seed: int, conf: bool) -> dict:
    """Simulate a dual between prebuilt squads `sa`/`sb`. `la`/`lb` are the top-6
    Prospect ladders (la[i] ↔ sa.singles[i]) so singles lines carry player ids."""
    res = simulate_dual(sa, sb, seed=seed, fidelity="fast")
    lines = []
    for ln in res.lines:
        if not ln.completed:
            lines.append({"slot": ln.slot, "completed": False})
            continue
        gw = ln.result.games_won
        rec = {"slot": ln.slot, "completed": True, "home_won": ln.home_won,
               "home_games": gw[0], "away_games": gw[1]}
        if ln.slot.startswith("S"):              # singles only — STR is singles-based
            i = int(ln.slot[1:]) - 1
            if 0 <= i < len(la) and i < len(lb):
                rec["home_pid"], rec["away_pid"] = la[i].pid, lb[i].pid
        lines.append(rec)
    return {
        "home": a.school, "away": b.school, "conf": conf,
        "home_won": res.winner == 0,
        "home_points": res.home_points, "away_points": res.away_points,
        "lines": lines,
    }


def _build_corpus(duals: list[dict]) -> dict[str, list[tuple]]:
    """Per-player singles match corpus: pid -> [(opp_pid, games_won, games_lost), ...]."""
    corpus: dict[str, list[tuple]] = {}
    for d in duals:
        for ln in d["lines"]:
            if not ln.get("completed") or "home_pid" not in ln:
                continue
            hp, ap = ln["home_pid"], ln["away_pid"]
            hg, ag = ln["home_games"], ln["away_games"]
            corpus.setdefault(hp, []).append((ap, hg, ag))
            corpus.setdefault(ap, []).append((hp, ag, hg))
    return corpus


def _schedule(div: Division, rng: random.Random) -> list[tuple[Program, Program, bool]]:
    games: list[tuple[Program, Program, bool]] = []
    # conference round robin
    for members in div.conferences.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                games.append((members[i], members[j], True))
    # non-conference: connect the SoS graph
    progs = div.programs
    for p in progs:
        for _ in range(NONCONF_PER_TEAM):
            q = rng.choice(progs)
            if q.conf != p.conf and q is not p:
                games.append((p, q, False))
    return games


def _conf_tournament(members: list[Program], standings_order: list[Program],
                     rng: random.Random) -> Program:
    """Single-elim conference tournament; champion earns the autobid."""
    seeded = standings_order[:min(8, len(members))]
    if len(seeded) == 1:
        return seeded[0]
    n = 1
    while n < len(seeded):
        n *= 2
    positions = _seed_positions(n)
    slots = [seeded[s - 1] if s <= len(seeded) else None for s in positions]
    while len([s for s in slots if s]) > 1:
        nxt = []
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if not a or not b:
                nxt.append(a or b); continue
            nxt.append(play_dual(a, b, seed=rng.randint(1, 10**9), fidelity="fast"))
        slots = nxt
    return next(s for s in slots if s)


def run_season(division: str = "D1", gender: str = "men", *, seed: int = 2026,
               rosters: dict | None = None) -> SeasonResult:
    div = load_division(division, gender)
    rng = random.Random(seed)

    # Persistent rosters of Prospects (the League passes its own; otherwise build).
    if rosters is None:
        rosters = {p.school: build_roster(p) for p in div.programs}
    ladders = {s: sorted(r, key=lambda pr: pr.current_overall(), reverse=True)[:6]
               for s, r in rosters.items()}
    squads = {s: Team(name=s, singles=[pr.engine_player() for pr in ladders[s]])
              for s in rosters}

    games = _schedule(div, rng)
    duals = [_dual_record(a, b, squads[a.school], squads[b.school],
                          ladders[a.school], ladders[b.school],
                          seed=rng.randint(1, 10**9), conf=c) for (a, b, c) in games]

    ratings = compute_ratings(duals)

    # conference standings (conference duals only)
    conf_wl: dict[str, dict[str, list[int]]] = {}
    for d in duals:
        if not d["conf"]:
            continue
        for t in (d["home"], d["away"]):
            conf_wl.setdefault(t, [0, 0])
        if d["home_won"]:
            conf_wl[d["home"]][0] += 1; conf_wl[d["away"]][1] += 1
        else:
            conf_wl[d["away"]][0] += 1; conf_wl[d["home"]][1] += 1

    standings: dict[str, list[tuple]] = {}
    champions: list[Program] = []
    for conf, members in div.conferences.items():
        def keyf(p: Program):
            w, l = conf_wl.get(p.school, [0, 0])
            n = w + l
            return (w / n if n else 0.0, ratings[p.school].pi)
        order = sorted(members, key=keyf, reverse=True)
        standings[conf] = [(p, *conf_wl.get(p.school, [0, 0])) for p in order]
        if members:
            champions.append(_conf_tournament(members, order, rng))

    # Live STR from results: per-player singles corpus → convergence, seeded by
    # each player's ability-derived STR (results take over as reliability rises).
    corpus = _build_corpus(duals)
    priors = {pr.pid: pr.str_value() for s in rosters for pr in ladders[s]}
    player_str = converge_ids(corpus, priors=priors)
    player_record = {pid: (sum(1 for (_, gw, gl) in ms if gw > gl),
                           sum(1 for (_, gw, gl) in ms if gw <= gl))
                     for pid, ms in corpus.items()}

    return SeasonResult(division, gender, seed, div.programs, ratings,
                        standings, champions, duals,
                        rosters=rosters, player_str=player_str, player_record=player_record)
