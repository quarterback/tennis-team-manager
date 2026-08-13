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
    # Talent vs talent. A single skill signal — the gap in `overall`, the bounded
    # average of a player's whole attribute table (each of the 9 drivers is itself
    # an average of rich attributes, so serve, grit, stamina, consistency, etc.
    # all feed in here) — drives every game; randomness is only the residual.
    # Deliberately FLAT: talent tells, but college tennis is upset-prone, so the
    # gap bites gently and results — not ratings — decide most matches. Emergent
    # over a full D1 season (favorite = higher-talent player), by UTR gap:
    # 1-1.5 ~63%, 1.5-2 ~69%, 2-3 ~77%, 3+ ~87%; overall favorite rate ~65%. The
    # dense, realistic talent distribution (top players bunched within a margin of
    # error) is what keeps same-level matches competitive — not match-time dials.
    "hold_base_logit": 0.9,     # server's natural hold advantage
    "skill_slope": 1.5,         # how hard the overall gap bites, per game
    "tb_slope": 1.13,           # tiebreaks a touch more volatile than a set
    "context_slope": 0.18,      # venue / wind / heat / crowd comfort
    # HINGED gap response (owner rule 2027-08 — JHSAA upset recalibration). A
    # single logistic slope cannot keep near-equals a coin flip AND make a huge
    # underdog rare — the 2026 flattening (2.2 -> 1.5) accepted that trade for
    # college, where the talent band is dense and big gaps are rare. High school
    # (and juniors) routinely play across gaps 3-5x the college spread, and there
    # the flat slope let a materially weaker team win far too often — measured on
    # the JHSAA postseason (1S/4D): 12.7% upsets at a 0.10-0.15 overall gap, with
    # 4-1 / 5-0 underdog wins, and back-to-back bracket runs by bottom-quartile
    # teams. So the gap the model plays on is hinged: below `gap_knee` (a margin
    # of error — ~3.6 OVR points, ~1 UTR) NOTHING changes and near-equal matches
    # stay as upset-prone as ever; beyond it every extra point of real gap counts
    # (1 + gap_accel) times, so upset odds fall away sharply as the mismatch
    # grows and a huge underdog's win is rare, usually narrow, and compounding
    # rounds of it vanishingly so. One transform, shared by hold, tiebreak and
    # the doubles fast model (engine.doubles), so all three curves steepen
    # together. Calibrated with scripts/jhsaa_upset_calibration.py; see
    # docs/AAR-jhsaa-upset-variance-recalibration.md before retuning.
    # Measured on the JHSAA state format (underdog dual-win % by per-line-avg
    # gap, before -> after): 0.05-0.075 28% -> 18%, 0.075-0.10 20% -> 8%,
    # 0.10-0.15 13% -> 4.6% (upset wins almost all 3-2), 0.15-0.20 5% -> 0.3%,
    # 0.20+ 1% -> <0.15%; the 0-0.05 bands keep 30-40%. 1.8 is the gentlest
    # accel that reaches that shape — sweep 1.6/1.8/2.2 moved the big-gap rows
    # by under half a point, so resist "just a bit more".
    "gap_knee": 0.06,           # overall-units of gap that stay "even match"
    "gap_accel": 1.8,           # extra bite per unit of gap beyond the knee
}


def effective_gap(gap: float) -> float:
    """The gap the fast models PLAY ON: real gap below the knee, accelerated
    beyond it. Sign-symmetric and continuous; identity for |gap| <= knee."""
    knee = TUNE["gap_knee"]
    extra = abs(gap) - knee
    if extra <= 0:
        return gap
    return gap + (extra if gap > 0 else -extra) * TUNE["gap_accel"]


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _context_edge(server: Player, returner: Player, context: MatchContext) -> float:
    venue = (server.indoor_comfort - returner.indoor_comfort) if context.indoor else (server.outdoor_comfort - returner.outdoor_comfort)
    wind = context.wind * (server.wind_tolerance - returner.wind_tolerance)
    heat = context.heat * (server.heat_tolerance - returner.heat_tolerance)
    crowd = context.crowd * (server.crowd_pressure - returner.crowd_pressure)
    return venue + wind + heat + crowd


def _hold_prob(server: Player, returner: Player, context: MatchContext) -> float:
    return _logistic(
        TUNE["hold_base_logit"]
        + TUNE["skill_slope"] * effective_gap(server.overall - returner.overall)
        + TUNE["context_slope"] * _context_edge(server, returner, context))


def _tb_prob(p0: Player, p1: Player, context: MatchContext) -> float:
    return _logistic(
        TUNE["tb_slope"] * effective_gap(p0.overall - p1.overall)
        + TUNE["context_slope"] * _context_edge(p0, p1, context))


def _play_set(rng, players, server, fmt, final_tb: bool, target_games: int, context: MatchContext):
    """Returns (winner, (g0,g1), next_server, flow).

    `flow` records what happened, game by game — [server, winner] pairs plus
    tiebreak [first_server, winner] — WITHOUT consuming any extra rng draws, so
    scorelines are bit-identical to the pre-recording model. engine.boxstats
    replays this flow at point level to attach real stats to a fast match."""
    if final_tb:
        win = 0 if rng.random() < _tb_prob(players[0], players[1], context) else 1
        flow = {"games": [], "tb": [server, win], "mtb": True}
        return win, ((1, 0) if win == 0 else (0, 1)), 1 - server, flow

    games = [0, 0]
    flow_games: list[list[int]] = []
    tg = target_games
    while True:
        r = players[1 - server]
        s = players[server]
        if rng.random() < _hold_prob(s, r, context):
            games[server] += 1
            flow_games.append([server, server])
        else:
            games[1 - server] += 1
            flow_games.append([server, 1 - server])
        server = 1 - server

        if fmt.set_tiebreak and games[0] == tg and games[1] == tg:
            win = 0 if rng.random() < _tb_prob(players[0], players[1], context) else 1
            games[win] += 1
            flow = {"games": flow_games, "tb": [server, win], "mtb": False}
            return win, (games[0], games[1]), 1 - server, flow
        if games[0] >= tg and games[0] - games[1] >= 2:
            return 0, (games[0], games[1]), server, {"games": flow_games, "tb": None, "mtb": False}
        if games[1] >= tg and games[1] - games[0] >= 2:
            return 1, (games[0], games[1]), server, {"games": flow_games, "tb": None, "mtb": False}


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

    flows: list[dict] = []

    if fmt.pro_set:
        win, score, server, flow = _play_set(rng, players, server, fmt, False, fmt.pro_set_games, context)
        sets[win] += 1
        set_scores.append(score)
        flows.append(flow)
        games_won = [score[0], score[1]]
        overall = 0 if sets[0] > sets[1] else 1
        return MatchResult(
            players=players, winner=overall, sets=sets, set_scores=set_scores,
            games_won=(games_won[0], games_won[1]),
            stats=(PlayerStats(), PlayerStats()), pbp=[], fidelity="fast",
            game_flow=flows,
        )

    sets_needed = fmt.best_of // 2 + 1
    while max(sets) < sets_needed:
        is_final = sets[0] == sets_needed - 1 and sets[1] == sets_needed - 1
        win, score, server, flow = _play_set(
            rng, players, server, fmt,
            is_final and fmt.final_set_tiebreak, fmt.set_games, context,
        )
        sets[win] += 1
        set_scores.append(score)
        flows.append(flow)
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
        game_flow=flows,
    )
