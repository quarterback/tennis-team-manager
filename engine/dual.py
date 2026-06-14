"""
Dual-match team layer (NCAA format).

Order of play:
  1. Doubles - 3 matches (8-game pro set each); winning 2 of 3 = ONE team point.
  2. Singles - all 6 courts play AT THE SAME TIME (best-of-3, no-ad); each is one
     team point. First team to 4 of the 7 available points clinches.

Because the six singles run concurrently, they finish in an order set by how
long each takes - a 6-0 6-1 rout ends well before a 7-6 6-7 7-6 grind - NOT by
court number. Points accrue as matches finish; the moment a side reaches 4 the
matches still in progress are abandoned at their CURRENT (partial) score. So a
clinched dual leaves a varied set of unfinished courts, each with the score it
had reached - not a blank "did not play".

`completed=False` flags an abandoned line; `partial` carries its score-so-far
(home-perspective set tuples) so a stats layer can still exclude it from records
while the UI shows where it stood.

Determinism: each constituent match gets a derived seed `base_seed + offset`,
and finish order is a deterministic function of match length, so the whole dual
is reproducible from one seed.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .state import MatchContext, Player
from .format import PRESETS
from .match import simulate_match, MatchResult
from .doubles import simulate_doubles, DoublesTeam, DoublesResult


@dataclass
class Team:
    name: str
    # Six singles players, ordered 1..6 by strength (lineup order).
    singles: list[Player]
    # Doubles pairings as index pairs into `singles`; defaults to 1/2, 3/4, 5/6.
    doubles: list[tuple[int, int]] = field(default_factory=lambda: [(0, 1), (2, 3), (4, 5)])


@dataclass
class DualLine:
    slot: str                 # "D1".."D3", "S1".."S6"
    home_won: bool
    result: MatchResult | DoublesResult | None  # DoublesResult on the D lines
    completed: bool = True     # False when abandoned after clinch
    # Score-so-far (home-perspective set tuples) for a line abandoned mid-match.
    partial: list[tuple[int, int]] | None = None


@dataclass
class DualResult:
    home: Team
    away: Team
    home_points: int
    away_points: int
    winner: int               # 0 = home, 1 = away
    lines: list[DualLine]
    doubles_point: int | None  # which side took the doubles point (0/1) or None if split unreached


def _pair(team: Team, pair: tuple[int, int]) -> DoublesTeam:
    """Build the two-player doubles side for a lineup pairing."""
    return DoublesTeam(players=(team.singles[pair[0]], team.singles[pair[1]]))


def _match_length(res: MatchResult) -> int:
    """Total games in a singles match — the proxy for how long it took to play."""
    return sum(a + b for a, b in res.set_scores)


def _partial_score(set_scores: list[tuple[int, int]], elapsed: float,
                   total: float) -> list[tuple[int, int]]:
    """The score a match had reached when play was stopped at `elapsed` of its
    `total` running length: completed sets verbatim, then the in-progress set
    split proportionally to its eventual score. Home-perspective tuples."""
    total_games = sum(a + b for a, b in set_scores)
    if total <= 0 or total_games == 0:
        return [(0, 0)]
    played = int(round(max(0.0, min(1.0, elapsed / total)) * total_games))
    out: list[tuple[int, int]] = []
    acc = 0
    for a, b in set_scores:
        sg = a + b
        if acc + sg <= played:                      # whole set was finished
            out.append((a, b)); acc += sg
            continue
        rem = played - acc                           # mid-set when the dual clinched
        if rem > 0:
            pa = int(round(rem * a / sg)) if sg else 0
            out.append((pa, rem - pa))
        break
    return out or [(0, 0)]


def simulate_dual(home: Team, away: Team, *, seed: int, fidelity: str = "full",
                  context: MatchContext | None = None,
                  priority_finish: set[int] | None = None) -> DualResult:
    """Simulate an NCAA dual. `priority_finish` lists singles court indices (0-5)
    that should finish among the first matches off the court — used by season mode
    so a guaranteed-appearance player's line actually completes regardless of how
    long it ran. The first three singles to finish always complete (a 4-point
    clinch needs more than doubles + two singles), so a small priority set is a
    hard guarantee."""
    context = context or MatchContext()
    priority_finish = priority_finish or set()
    lines: list[DualLine] = []
    points = [0, 0]  # [home, away]

    # --- Doubles: 3 pro-set matches, 2 of 3 -> 1 team point ---
    # Each line is a real two-on-two match (engine.doubles), not an averaged pair.
    doubles_pro = PRESETS["pro_set_8"]
    d_wins = [0, 0]
    for i in range(3):
        res = simulate_doubles(_pair(home, home.doubles[i]), _pair(away, away.doubles[i]),
                               seed=seed + 10 + i, fmt=doubles_pro,
                               fidelity=fidelity, context=context)
        home_won = res.winner == 0
        d_wins[0 if home_won else 1] += 1
        lines.append(DualLine(slot=f"D{i+1}", home_won=home_won, result=res))
    doubles_point = 0 if d_wins[0] >= 2 else 1
    points[doubles_point] += 1

    # --- Singles: all six play concurrently; resolve in finish order ---
    singles_fmt = PRESETS["ncaa_dual"]
    clinch = 4
    results: dict[int, MatchResult] = {}
    length: dict[int, float] = {}
    for i in range(6):
        res = simulate_match(home.singles[i], away.singles[i],
                             seed=seed + 100 + i, fmt=singles_fmt,
                             fidelity=fidelity, context=context)
        results[i] = res
        # Running length = games played + a tiny seeded jitter so equal-length
        # matches still settle into a stable, varied order.
        jit = random.Random((seed + 100 + i) ^ 0xD0A1).uniform(-0.4, 0.4)
        length[i] = _match_length(res) + jit
    # Priority courts come off first; the rest finish shortest-match-first.
    finish_order = sorted(range(6), key=lambda i: (i not in priority_finish, length[i], i))

    by_slot: dict[int, DualLine] = {}
    clinch_at: float | None = None
    for i in finish_order:
        if max(points) >= clinch:                    # dual already decided — abandon in progress
            res = results[i]
            by_slot[i] = DualLine(
                slot=f"S{i+1}", home_won=(res.winner == 0), result=res, completed=False,
                partial=_partial_score(res.set_scores, clinch_at, length[i]))
            continue
        res = results[i]
        home_won = res.winner == 0
        points[0 if home_won else 1] += 1
        by_slot[i] = DualLine(slot=f"S{i+1}", home_won=home_won, result=res)
        if max(points) >= clinch and clinch_at is None:
            clinch_at = length[i]
    for i in range(6):                               # display in court order S1..S6
        lines.append(by_slot[i])

    winner = 0 if points[0] > points[1] else 1
    return DualResult(
        home=home, away=away,
        home_points=points[0], away_points=points[1],
        winner=winner, lines=lines, doubles_point=doubles_point,
    )
