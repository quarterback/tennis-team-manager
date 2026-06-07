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

from engine import simulate_dual
from .ncaa import Program, Division, load_division, build_squad
from .rating import compute_ratings, RatingLine
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

    def ranked(self) -> list[Program]:
        return sorted(self.programs, key=lambda p: self.ratings[p.school].pi, reverse=True)


def _dual_record(a: Program, b: Program, *, seed: int, conf: bool) -> dict:
    res = simulate_dual(build_squad(a), build_squad(b), seed=seed, fidelity="fast")
    lines = []
    for ln in res.lines:
        if not ln.completed:
            lines.append({"slot": ln.slot, "completed": False})
            continue
        gw = ln.result.games_won
        lines.append({"slot": ln.slot, "completed": True, "home_won": ln.home_won,
                      "home_games": gw[0], "away_games": gw[1]})
    return {
        "home": a.school, "away": b.school, "conf": conf,
        "home_won": res.winner == 0,
        "home_points": res.home_points, "away_points": res.away_points,
        "lines": lines,
    }


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


def run_season(division: str = "D1", gender: str = "men", *, seed: int = 2026) -> SeasonResult:
    div = load_division(division, gender)
    rng = random.Random(seed)

    games = _schedule(div, rng)
    duals = [_dual_record(a, b, seed=rng.randint(1, 10**9), conf=c) for (a, b, c) in games]

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

    return SeasonResult(division, gender, seed, div.programs, ratings,
                        standings, champions, duals)
