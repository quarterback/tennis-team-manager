"""
Point -> game -> set -> match scoring for the full-fidelity engine.

Scoring rules implemented:
  - games: 0/15/30/40, deuce/advantage (or sudden-death point under no-ad)
  - sets: first to 6 games, win by 2; tiebreak (first to 7, win by 2) at 6-6
  - match: best-of-3 (or best-of-5); optional 10-point match tiebreak as the
    deciding set
  - serve alternates every game; the tiebreak consumes one serve-turn

Determinism: all draws flow through `state.rng`. `simulate_match(..., seed=N)`
with identical players + flags yields an identical transcript + scoreline.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from .state import MatchState, MatchContext, Player, PlayerStats
from .rally import play_point
from .format import MatchFormat, DEFAULT

_POINT_LABELS = {0: "0", 1: "15", 2: "30", 3: "40"}


@dataclass
class MatchResult:
    players: tuple[Player, Player]
    winner: int
    sets: list[int]
    set_scores: list[tuple[int, int]]
    games_won: tuple[int, int]
    stats: tuple[PlayerStats, PlayerStats]
    pbp: list[str]
    fidelity: str = "full"
    # Per-set game sequence recorded by the FAST model (None at full fidelity,
    # where stats are real): one dict per set, {"games": [[server, winner], ...],
    # "tb": [first_server, winner] | None, "mtb": bool}. Consumed by
    # engine.boxstats to replay the match at point level, conditioned on these
    # outcomes, so a fast-fidelity match can still carry engine-faithful stats.
    game_flow: list[dict] | None = None

    @property
    def winner_name(self) -> str:
        return self.players[self.winner].name

    @property
    def scoreline(self) -> str:
        """e.g. '6-4 3-6 7-6' from the winner's perspective."""
        w = self.winner
        parts = []
        for a, b in self.set_scores:
            hi, lo = (a, b) if w == 0 else (b, a)
            parts.append(f"{hi}-{lo}")
        return " ".join(parts)


def _point_score_str(state: MatchState) -> str:
    s, r = state.server, state.returner
    ps, pr = state.points[s], state.points[r]
    if ps >= 3 and pr >= 3:
        if ps == pr:
            return "deuce"
        return "Ad-server" if ps > pr else "Ad-returner"
    return f"{_POINT_LABELS.get(ps, '40')}-{_POINT_LABELS.get(pr, '40')}"


def _game_over(state: MatchState) -> Optional[int]:
    s, r = state.server, state.returner
    ps, pr = state.points[s], state.points[r]
    if state.fmt.no_ad:
        if ps >= 4 or pr >= 4:
            return s if ps > pr else r
        return None
    if ps >= 4 and ps - pr >= 2:
        return s
    if pr >= 4 and pr - ps >= 2:
        return r
    return None


def _point_pressure(state: MatchState) -> float:
    """How consequential the upcoming point is, 0 (routine) ... 1 (match point)."""
    ps, pr = state.points[state.server], state.points[state.returner]
    server_gp = ps >= 3 and ps > pr
    returner_gp = pr >= 3 and pr > ps
    deciding = state.fmt.no_ad and ps == 3 and pr == 3
    if not (server_gp or returner_gp or deciding):
        return 0.0
    pressure = 0.45
    sides = []
    if server_gp or deciding:
        sides.append(state.server)
    if returner_gp or deciding:
        sides.append(state.returner)
    for side in sides:
        gw, og = state.games[side] + 1, state.games[1 - side]
        if gw >= state.set_target and gw - og >= 2:
            pressure = max(pressure, 0.70)
            if state.sets[side] + 1 >= state.sets_needed:
                pressure = max(pressure, 1.0)
    return pressure


def _tb_pressure(pts: list[int], target: int, is_match: bool) -> float:
    hi, lo = max(pts), min(pts)
    if hi >= target - 1 and hi >= lo + 1:
        return 1.0 if is_match else 0.85
    return min(0.6, 0.20 + 0.40 * hi / target)


def play_game(state: MatchState) -> int:
    """Play one service game on `state.server`. Returns winner index."""
    state.points = [0, 0]
    s, r = state.server, state.returner
    while True:
        is_bp = state.points[r] >= 3 and state.points[r] > state.points[s]
        if state.fmt.no_ad and state.points[s] == 3 and state.points[r] == 3:
            is_bp = True

        state.pressure = _point_pressure(state)
        winner, kind = play_point(state)
        state.points[winner] += 1

        if is_bp:
            state.stats[s].break_points_faced += 1
            if winner == s:
                state.stats[s].break_points_saved += 1
            else:
                state.stats[r].break_points_converted += 1

        over = _game_over(state)
        if over is not None:
            return over


def play_tiebreak(state: MatchState, target: int = 7) -> int:
    """Play a tiebreak to `target` (win by 2)."""
    pts = [0, 0]
    first_server = state.server
    served = 0
    is_match_tb = state.is_final_set or (max(state.sets) >= state.sets_needed - 1)
    while True:
        state.pressure = _tb_pressure(pts, target, is_match_tb)
        winner, kind = play_point(state)
        pts[winner] += 1
        served += 1
        if served == 1 or (served - 1) % 2 == 0:
            state.server = 1 - state.server
        if (pts[0] >= target or pts[1] >= target) and abs(pts[0] - pts[1]) >= 2:
            win = 0 if pts[0] > pts[1] else 1
            state._tb_points = (pts[0], pts[1])  # type: ignore[attr-defined]
            state.server = first_server
            return win


def play_set(
    state: MatchState,
    is_final: bool,
    target_games: Optional[int] = None,
) -> tuple[int, tuple[int, int], tuple[int, int]]:
    """Play one set. Returns (winner, game_score, games_won_pair)."""
    fmt = state.fmt
    state.games = [0, 0]
    state.is_final_set = is_final or state.sets_needed == 1
    state.set_target = target_games if target_games is not None else fmt.set_games

    if is_final and fmt.final_set_tiebreak:
        win = play_tiebreak(state, target=fmt.final_set_tiebreak_target)
        state.server = 1 - state.server
        pts = getattr(state, "_tb_points", (fmt.final_set_tiebreak_target, 0))
        gw = (1, 0) if win == 0 else (0, 1)
        return win, pts, gw

    tg = target_games if target_games is not None else fmt.set_games
    tb_at = fmt.set_tiebreak_at if fmt.set_tiebreak_at is not None else tg
    while True:
        g_winner = play_game(state)
        state.games[g_winner] += 1
        state.server = 1 - state.server

        g0, g1 = state.games
        if fmt.set_tiebreak and g0 == tb_at and g1 == tb_at:
            tb_winner = play_tiebreak(state, target=fmt.set_tiebreak_target)
            state.games[tb_winner] += 1
            state.server = 1 - state.server
            return tb_winner, (state.games[0], state.games[1]), (state.games[0], state.games[1])
        if g0 >= tg and g0 - g1 >= 2:
            return 0, (g0, g1), (g0, g1)
        if g1 >= tg and g1 - g0 >= 2:
            return 1, (g0, g1), (g0, g1)


def simulate_match(
    p0: Player,
    p1: Player,
    *,
    seed: int,
    fmt: Optional[MatchFormat] = None,
    first_server: int = 0,
    fidelity: str = "full",
    context: Optional[MatchContext] = None,
) -> MatchResult:
    """Simulate a singles match under `fmt`.

    `fidelity="fast"` routes to the game-level hold model. `context` is optional
    hardcourt weather/venue context; omitted means neutral outdoor conditions.
    """
    fmt = fmt or DEFAULT
    context = context or MatchContext()
    if fidelity == "fast":
        from .fast import simulate_fast
        return simulate_fast(p0, p1, seed=seed, fmt=fmt, first_server=first_server, context=context)

    state = MatchState(players=(p0, p1), rng=random.Random(seed), fmt=fmt,
                       server=first_server, context=context)
    state.sets_needed = 1 if fmt.pro_set else fmt.best_of // 2 + 1
    games_won = [0, 0]

    if fmt.pro_set:
        winner, score, gw = play_set(state, is_final=False, target_games=fmt.pro_set_games)
        state.sets[winner] += 1
        state.set_scores.append(score)
        games_won = [gw[0], gw[1]]
        state.log(f"Pro set: {score[0]}-{score[1]}")
    else:
        sets_needed = fmt.best_of // 2 + 1
        while max(state.sets) < sets_needed:
            is_final = state.sets[0] == sets_needed - 1 and state.sets[1] == sets_needed - 1
            winner, score, gw = play_set(state, is_final)
            state.sets[winner] += 1
            state.set_scores.append(score)
            games_won[0] += gw[0]
            games_won[1] += gw[1]
            state.log(f"Set {len(state.set_scores)}: {score[0]}-{score[1]}")

    overall = 0 if state.sets[0] > state.sets[1] else 1
    return MatchResult(
        players=(p0, p1),
        winner=overall,
        sets=list(state.sets),
        set_scores=list(state.set_scores),
        games_won=(games_won[0], games_won[1]),
        stats=state.stats,
        pbp=state.pbp,
        fidelity="full",
    )
