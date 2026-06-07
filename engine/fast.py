"""
Fast game-level model — scoreline only, for bulk juniors / HS volume.

Instead of resolving every point, each game is a single Bernoulli draw on
the server's hold probability (a function of the rating gap). Sets,
tiebreaks and the match wrap that the same way the full engine does, so the
two fidelities produce comparable scorelines. No per-point stats / PBP.

Determinism: one `random.Random(seed)`.
"""
from __future__ import annotations

import math
import random

from .state import Player, PlayerStats
from .format import MatchFormat, DEFAULT
# Imported lazily by match.simulate_match; import the result type here.
from .match import MatchResult

TUNE = {
    "hold_base_logit": 0.9,   # baseline server advantage (≈0.71 hold at parity)
    "skill_slope": 3.0,       # how hard the overall-rating gap tilts holds
    "tb_slope": 2.5,          # tiebreak coin-flip sensitivity to the gap
}


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _hold_prob(server: Player, returner: Player) -> float:
    diff = server.overall - returner.overall
    return _logistic(TUNE["hold_base_logit"] + TUNE["skill_slope"] * diff)


def _tb_prob(p0: Player, p1: Player) -> float:
    return _logistic(TUNE["tb_slope"] * (p0.overall - p1.overall))


def _play_set(rng, players, server, fmt, final_tb: bool, target_games: int):
    """Returns (winner, (g0,g1), next_server)."""
    if final_tb:
        win = 0 if rng.random() < _tb_prob(players[0], players[1]) else 1
        return win, ((1, 0) if win == 0 else (0, 1)), 1 - server

    games = [0, 0]
    tg = target_games
    while True:
        r = players[1 - server]
        s = players[server]
        if rng.random() < _hold_prob(s, r):
            games[server] += 1
        else:
            games[1 - server] += 1
        server = 1 - server

        if fmt.set_tiebreak and games[0] == tg and games[1] == tg:
            win = 0 if rng.random() < _tb_prob(players[0], players[1]) else 1
            games[win] += 1
            return win, (games[0], games[1]), 1 - server
        if games[0] >= tg and games[0] - games[1] >= 2:
            return 0, (games[0], games[1]), server
        if games[1] >= tg and games[1] - games[0] >= 2:
            return 1, (games[0], games[1]), server


def simulate_fast(
    p0: Player,
    p1: Player,
    *,
    seed: int,
    fmt: MatchFormat = None,
    first_server: int = 0,
) -> MatchResult:
    fmt = fmt or DEFAULT
    rng = random.Random(seed)
    players = (p0, p1)
    sets = [0, 0]
    set_scores: list[tuple[int, int]] = []
    games_won = [0, 0]
    server = first_server

    if fmt.pro_set:
        win, score, server = _play_set(rng, players, server, fmt, False, fmt.pro_set_games)
        sets[win] += 1
        set_scores.append(score)
        games_won = [score[0], score[1]]
        overall = 0 if sets[0] > sets[1] else 1
        return MatchResult(
            players=players, winner=overall, sets=sets, set_scores=set_scores,
            games_won=(games_won[0], games_won[1]),
            stats=(PlayerStats(), PlayerStats()), pbp=[], fidelity="fast",
        )

    sets_needed = fmt.best_of // 2 + 1
    while max(sets) < sets_needed:
        is_final = sets[0] == sets_needed - 1 and sets[1] == sets_needed - 1
        win, score, server = _play_set(
            rng, players, server, fmt,
            is_final and fmt.final_set_tiebreak, fmt.set_games,
        )
        sets[win] += 1
        set_scores.append(score)
        games_won[0] += score[0]
        games_won[1] += score[1]

    overall = 0 if sets[0] > sets[1] else 1
    return MatchResult(
        players=players,
        winner=overall,
        sets=sets,
        set_scores=set_scores,
        games_won=(games_won[0], games_won[1]),
        stats=(PlayerStats(), PlayerStats()),
        pbp=[],
        fidelity="fast",
    )
