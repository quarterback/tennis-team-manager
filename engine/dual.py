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
from .boxstats import overlay as _overlay_stats


@dataclass
class Team:
    name: str
    # Six singles players, ordered 1..6 by strength (lineup order).
    singles: list[Player]
    # Doubles pairings as index pairs; defaults to 1/2, 3/4, 5/6.
    doubles: list[tuple[int, int]] = field(default_factory=lambda: [(0, 1), (2, 3), (4, 5)])
    # Optional SEPARATE doubles roster the pairings index into. When None (default),
    # the pairs index into `singles` (the classic "doubles is a permutation of the
    # six"). When set, doubles is its own lineup — so a doubles specialist who isn't
    # in the singles six can still play (real college tennis: a "1 doubles / 5
    # singles" player). Pairs then index into THIS list.
    doubles_players: list[Player] | None = None


@dataclass
class DualLine:
    slot: str                 # "D1".."D3", "S1".."S6"
    home_won: bool
    result: MatchResult | DoublesResult | None  # DoublesResult on the D lines
    completed: bool = True     # False when abandoned after clinch
    # Score-so-far (home-perspective set tuples) for a line abandoned mid-match.
    partial: list[tuple[int, int]] | None = None
    # 1-based ORDER OF FINISH within this line's discipline (doubles vs singles),
    # in the sequence the matches actually came off the court — the ITA box-score
    # "Order of finish: 5, 6, 2, …". None for a line abandoned after the clinch
    # (it never finished, so it carries no ordinal).
    finish: int | None = None


@dataclass
class DualResult:
    home: Team
    away: Team
    home_points: int
    away_points: int
    winner: int               # 0 = home, 1 = away
    lines: list[DualLine]
    doubles_point: int | None  # which side took the doubles point (0/1) or None if split unreached


SINGLES_COURTS = 6        # a dual fields six singles; `Team.doubles` indexes into them


def _court(team: Team, i: int) -> Player:
    """The player on singles court `i` (0-based), backstopped against a short lineup.

    The dual reads `singles[0..5]`, so — exactly like `_pair` below — a side with
    fewer than six available players used to IndexError here and take the whole page
    down mid-bracket. A short side plays its last (weakest) body on the courts it
    can't fill: the same degenerate, forfeit-like lineup `season.coach_lineup`
    already builds when injuries strip a roster, rather than a 500. The roster floor
    in `world.refill_walkons` keeps this from firing in the normal case; it still
    fires on a save that fell below six before that floor existed, since the floor
    only applies from the next rollover.
    """
    if not team.singles:
        raise ValueError(f"{team.name} has nobody to field in singles")
    return team.singles[min(i, len(team.singles) - 1)]


def _pair(team: Team, pair: tuple[int, int]) -> DoublesTeam:
    """Build the two-player doubles side for a lineup pairing. The pair indexes into
    the team's separate `doubles_players` roster when set, else into `singles`."""
    pool = team.doubles_players if team.doubles_players is not None else team.singles
    if not pool:
        raise ValueError(f"{team.name} has nobody to field in doubles")
    # NEVER IndexError on a short pool. `Team.doubles` defaults to [(0,1),(2,3),(4,5)],
    # so a side with fewer than six available players used to blow up here and take
    # the whole page with it — reachable both from roster thinning over seasons and
    # from injuries cutting a six-man roster down. A degenerate side plays whoever it
    # has rather than 500-ing; the roster floor in `world.refill_walkons` keeps this
    # from firing in the normal case. Indices WRAP here (not clamp as in `_court`)
    # because a pair needs two DIFFERENT players.
    n = len(pool)
    i, j = pair[0] % n, pair[1] % n
    if n > 1 and i == j:
        j = (j + 1) % n
    return DoublesTeam(players=(pool[i], pool[j]))


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
                  priority_finish: set[int] | None = None,
                  box_stats: bool = False, play_all: bool = False) -> DualResult:
    """Simulate an NCAA dual. `priority_finish` lists singles court indices (0-5)
    that should finish among the first matches off the court — used by season mode
    so a guaranteed-appearance player's line actually completes regardless of how
    long it ran. The first three singles to finish always complete (a 4-point
    clinch needs more than doubles + two singles), so a small priority set is a
    hard guarantee.

    `box_stats=True` attaches engine-faithful per-player stats to every COMPLETED
    line of a fast-fidelity dual (engine.boxstats conditioned replay — the fast
    model still decides every outcome; scorelines are unchanged). Abandoned lines
    stay stat-less: they're excluded from records and the stats layer alike. At
    full fidelity stats already exist and this flag is a no-op.

    `play_all=True` is the ITA Division III "play-play" format: every singles
    match is played to completion instead of abandoning the rest once a side
    reaches the 4-point clinch. It never changes the WINNER (the 4th point locks
    the dual; with only 7 points on offer the loser cannot pass 3) — it only fills
    in the final margin and gives every player a completed match on record. The
    matches are already simulated either way, so this just stops discarding them."""
    context = context or MatchContext()
    priority_finish = priority_finish or set()
    lines: list[DualLine] = []
    points = [0, 0]  # [home, away]

    # --- Doubles: 3 pro-set matches, 2 of 3 -> 1 team point ---
    # Each line is a real two-on-two match (engine.doubles), not an averaged pair.
    doubles_pro = PRESETS["pro_set_8"]
    d_wins = [0, 0]
    d_res: dict[int, DoublesResult] = {}
    d_len: dict[int, int] = {}
    for i in range(3):
        res = simulate_doubles(_pair(home, home.doubles[i]), _pair(away, away.doubles[i]),
                               seed=seed + 10 + i, fmt=doubles_pro,
                               fidelity=fidelity, context=context)
        if box_stats:
            _overlay_stats(res, seed=seed + 10 + i, fmt=doubles_pro, context=context)
        d_wins[0 if res.winner == 0 else 1] += 1
        d_res[i] = res
        d_len[i] = sum(a + b for a, b in res.set_scores)   # games played = length proxy
    # All three doubles play out in this sim, but they still finish in an order set
    # by how long each pro set ran (shortest first; court index breaks a tie).
    d_finish = {i: pos for pos, i in enumerate(sorted(range(3), key=lambda i: (d_len[i], i)), 1)}
    for i in range(3):
        lines.append(DualLine(slot=f"D{i+1}", home_won=d_res[i].winner == 0,
                              result=d_res[i], finish=d_finish[i]))
    doubles_point = 0 if d_wins[0] >= 2 else 1
    points[doubles_point] += 1

    # --- Singles: all six play concurrently; resolve in finish order ---
    singles_fmt = PRESETS["ncaa_dual"]
    clinch = 4
    results: dict[int, MatchResult] = {}
    length: dict[int, float] = {}
    for i in range(SINGLES_COURTS):
        res = simulate_match(_court(home, i), _court(away, i),
                             seed=seed + 100 + i, fmt=singles_fmt,
                             fidelity=fidelity, context=context)
        results[i] = res
        # Running length = games played + a tiny seeded jitter so equal-length
        # matches still settle into a stable, varied order.
        jit = random.Random((seed + 100 + i) ^ 0xD0A1).uniform(-0.4, 0.4)
        length[i] = _match_length(res) + jit
    # Priority courts come off first; the rest finish shortest-match-first.
    finish_order = sorted(range(SINGLES_COURTS),
                          key=lambda i: (i not in priority_finish, length[i], i))

    by_slot: dict[int, DualLine] = {}
    clinch_at: float | None = None
    s_finish = 0                                      # running order-of-finish counter
    for i in finish_order:
        if not play_all and max(points) >= clinch:   # dual decided — abandon in progress
            res = results[i]
            by_slot[i] = DualLine(
                slot=f"S{i+1}", home_won=(res.winner == 0), result=res, completed=False,
                partial=_partial_score(res.set_scores, clinch_at, length[i]))
            continue
        res = results[i]
        if box_stats:
            _overlay_stats(res, seed=seed + 100 + i, fmt=singles_fmt, context=context)
        home_won = res.winner == 0
        points[0 if home_won else 1] += 1
        s_finish += 1
        by_slot[i] = DualLine(slot=f"S{i+1}", home_won=home_won, result=res, finish=s_finish)
        if max(points) >= clinch and clinch_at is None:
            clinch_at = length[i]
    for i in range(SINGLES_COURTS):                  # display in court order S1..S6
        lines.append(by_slot[i])

    winner = 0 if points[0] > points[1] else 1
    return DualResult(
        home=home, away=away,
        home_points=points[0], away_points=points[1],
        winner=winner, lines=lines, doubles_point=doubles_point,
    )
