"""
Fast game-level model - scoreline only, for bulk juniors / HS volume.

Instead of resolving every point, each game is a single Bernoulli draw on
the server's hold probability (a function of the rating gap). Sets,
tiebreaks and the match wrap that the same way the full engine does, so the
two fidelities produce comparable scorelines. No per-point stats / PBP.

Determinism: one `random.Random(seed)`.
"""
from __future__ import annotations

import math
import random

from .state import MatchContext, Player, PlayerStats
from .format import MatchFormat, DEFAULT
# Imported lazily by match.simulate_match; import the result type here.
from .match import MatchResult

TUNE = {
    # Talent: a steeper slope makes the better player hold/break more reliably
    # (rarely upset by a much weaker one) while close gaps stay near a coin-flip.
    "hold_base_logit": 0.9,
    "skill_slope": 4.5,
    "tb_slope": 3.6,
    "context_slope": 0.18,
    # Stamina: a fatigue edge that ramps up as the match gets long, so the
    # fitter player wins more of the late games. Zero early, capped after
    # ~`fatigue_full_games` total games.
    "stamina_slope": 1.2,
    "fatigue_full_games": 20.0,
    # Grit: the mental gap swings the *decisive* games (set/match points) and
    # tiebreaks — it's near-neutral on routine games, like the full engine.
    "mental_slope": 1.5,
    "tb_mental_slope": 1.2,
}


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _context_edge(server: Player, returner: Player, context: MatchContext) -> float:
    venue = (server.indoor_comfort - returner.indoor_comfort) if context.indoor else (server.outdoor_comfort - returner.outdoor_comfort)
    wind = context.wind * (server.wind_tolerance - returner.wind_tolerance)
    heat = context.heat * (server.heat_tolerance - returner.heat_tolerance)
    crowd = context.crowd * (server.crowd_pressure - returner.crowd_pressure)
    return venue + wind + heat + crowd


def _fatigue_ramp(games_elapsed: float) -> float:
    """0 early, rising to 1.0 once the match has gone ~`fatigue_full_games`."""
    return min(1.0, games_elapsed / TUNE["fatigue_full_games"])


def _game_pressure(games, tg, sets, sets_needed) -> float:
    """How decisive the upcoming game is, 0 (routine) .. 1 (match point), at
    game granularity — mirrors match.py::_point_pressure. A game is a set point
    for a side when winning it clinches the set (>= tg with a 2-game margin);
    that's a match point too when the set also wins the match."""
    pressure = 0.0
    for side in (0, 1):
        other = 1 - side
        if games[side] >= tg - 1 and games[side] - games[other] >= 1:
            p = 1.0 if sets[side] + 1 >= sets_needed else 0.7
            pressure = max(pressure, p)
    return pressure


def _hold_prob(server: Player, returner: Player, context: MatchContext,
               games_elapsed: float = 0.0, pressure: float = 0.0) -> float:
    diff = server.overall - returner.overall
    fatigue = _fatigue_ramp(games_elapsed)
    return _logistic(
        TUNE["hold_base_logit"] + TUNE["skill_slope"] * diff
        + TUNE["context_slope"] * _context_edge(server, returner, context)
        + TUNE["stamina_slope"] * (server.stamina - returner.stamina) * fatigue
        + TUNE["mental_slope"] * (server.mental - returner.mental) * pressure)


def _tb_prob(p0: Player, p1: Player, context: MatchContext,
             games_elapsed: float = 0.0) -> float:
    fatigue = _fatigue_ramp(games_elapsed)
    return _logistic(
        TUNE["tb_slope"] * (p0.overall - p1.overall)
        + TUNE["context_slope"] * _context_edge(p0, p1, context)
        + TUNE["tb_mental_slope"] * (p0.mental - p1.mental)
        + TUNE["stamina_slope"] * (p0.stamina - p1.stamina) * fatigue)


def _play_set(rng, players, server, fmt, final_tb: bool, target_games: int,
              context: MatchContext, games_elapsed: float, sets, sets_needed):
    """Returns (winner, (g0,g1), next_server). `games_elapsed` is the total games
    played in the match before this set; `sets`/`sets_needed` give match state for
    the decisive-game pressure term."""
    if final_tb:
        win = 0 if rng.random() < _tb_prob(players[0], players[1], context, games_elapsed) else 1
        return win, ((1, 0) if win == 0 else (0, 1)), 1 - server

    games = [0, 0]
    tg = target_games
    while True:
        r = players[1 - server]
        s = players[server]
        ge = games_elapsed + games[0] + games[1]
        pressure = _game_pressure(games, tg, sets, sets_needed)
        if rng.random() < _hold_prob(s, r, context, ge, pressure):
            games[server] += 1
        else:
            games[1 - server] += 1
        server = 1 - server

        if fmt.set_tiebreak and games[0] == tg and games[1] == tg:
            ge = games_elapsed + games[0] + games[1]
            win = 0 if rng.random() < _tb_prob(players[0], players[1], context, ge) else 1
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
    context: MatchContext | None = None,
) -> MatchResult:
    fmt = fmt or DEFAULT
    context = context or MatchContext()
    rng = random.Random(seed)
    players = (p0, p1)
    sets = [0, 0]
    set_scores: list[tuple[int, int]] = []
    games_won = [0, 0]
    server = first_server

    if fmt.pro_set:
        win, score, server = _play_set(rng, players, server, fmt, False, fmt.pro_set_games,
                                       context, 0.0, sets, 1)
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
            is_final and fmt.final_set_tiebreak, fmt.set_games, context,
            games_won[0] + games_won[1], sets, sets_needed,
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
