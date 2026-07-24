"""
Serve + rally probability tables - the point-resolution core.

"Talent shifts the distribution": player attributes move these tables, they
don't script outcomes. All tunables live in `TUNE` so the model can be
retuned without touching logic (mirrors `o27/config.py`). Every draw uses
`state.rng`, so a seeded match is deterministic.

`play_point(state)` resolves ONE point on the current server's serve,
records serve/rally stats on both players, appends a PBP line, and returns
`(winner_index, kind)` where kind in
{"ace", "double_fault", "winner", "forced_error", "unforced_error"}.
Game / break-point context is handled by the caller in `match.py`.
"""
from __future__ import annotations

import math

from .state import MatchState, Player

TUNE = {
    # First / second serve in-play rates (before talent adjustment).
    "first_in_base": 0.62,
    "first_in_swing": 0.10,
    # Second-serve in rate. Lower base ⇒ more double faults; the wider swing
    # rewards placement so steady servers rarely dump one.
    "second_in_base": 0.855,
    "second_in_swing": 0.10,
    # Ace rates given the serve landed in.
    "ace_first_base": 0.185,
    "ace_second_base": 0.05,
    "ace_swing": 0.24,
    # Server's edge in a neutral rally, by serve number.
    "serve_plus_first": 0.55,
    "serve_plus_second": 0.20,
    "rally_slope": 3.2,
    # Of the points won/lost in a rally, how many are decisive shots vs errors.
    # These are the *baseline* shares; the actual split flexes per point with the
    # ballstriker's weapons and (for errors) the misser's consistency, so winner
    # and unforced-error totals spread by player instead of sitting on a constant.
    "winner_share": 0.47,
    "unforced_share": 0.52,
    # How far player attributes swing the winner / error split.
    "winner_power": 0.34,     # ballstriker's groundstroke weapon → more winners
    "winner_steady": 0.34,    # steadier opponent gifts fewer cheap errors
    "unforced_steady": 0.62,  # low-consistency server sprays more unforced errors
    # Pressure / clutch.
    "clutch_logit": 1.15,
    "clutch_exp": 1.6,
    "clutch_serve": 0.07,
    # Hardcourt condition effects. Defaults are neutral; effects are intentionally
    # light so old tests and default simulations barely move.
    "wind_serve": 0.045,
    "wind_error": 0.055,
    "heat_rally": 0.075,
    "crowd_pressure": 0.10,
    "venue_serve": 0.018,
}


def _logistic(x: float, slope: float = 1.0) -> float:
    return 1.0 / (1.0 + math.exp(-slope * x))


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _venue_comfort(state: MatchState, p: Player) -> float:
    return p.indoor_comfort if state.context.indoor else p.outdoor_comfort


def _serve_condition_bonus(state: MatchState, server: Player) -> float:
    ctx = state.context
    venue = TUNE["venue_serve"] * (_venue_comfort(state, server) - 0.5) * 2
    wind = -TUNE["wind_serve"] * ctx.wind * (1.0 - server.wind_tolerance)
    heat = -0.5 * TUNE["heat_rally"] * ctx.heat * (1.0 - server.heat_tolerance)
    return venue + wind + heat


def _rally_condition_bonus(state: MatchState, server: Player, returner: Player) -> float:
    ctx = state.context
    venue = 0.10 * ((_venue_comfort(state, server) - 0.5) - (_venue_comfort(state, returner) - 0.5))
    heat = -TUNE["heat_rally"] * ctx.heat * ((1.0 - server.heat_tolerance) - (1.0 - returner.heat_tolerance))
    wind = -TUNE["wind_error"] * ctx.wind * ((1.0 - server.wind_tolerance) - (1.0 - returner.wind_tolerance))
    return venue + heat + wind


def _first_serve_in_prob(state: MatchState, server: Player) -> float:
    t = TUNE
    return _clamp01(t["first_in_base"] + t["first_in_swing"] * (server.serve_placement - 0.5) * 2
                    + _serve_condition_bonus(state, server))


def _second_serve_in_prob(state: MatchState, server: Player) -> float:
    t = TUNE
    return _clamp01(t["second_in_base"] + t["second_in_swing"] * (server.serve_placement - 0.5) * 2
                    + 0.7 * _serve_condition_bonus(state, server))


def _ace_prob(server: Player, returner: Player, first: bool) -> float:
    t = TUNE
    base = t["ace_first_base"] if first else t["ace_second_base"]
    edge = (server.serve_power - returner.return_game)
    return _clamp01(base + t["ace_swing"] * edge)


def _server_rally_win_prob(server: Player, returner: Player, first: bool,
                           bonus: float = 0.0) -> float:
    """Probability the server wins a rally that reached neutral play.
    `bonus` is an additive logit term (clutch/context swing on big points).
    """
    t = TUNE
    serve_plus = t["serve_plus_first"] if first else t["serve_plus_second"]
    diff = (server.rally_skill - returner.rally_skill)
    return _logistic(t["rally_slope"] * diff + serve_plus + bonus)


def _offense(p: Player) -> float:
    """Groundstroke weapon — the two wings that finish points."""
    return 0.5 * (p.forehand + p.backhand)


def _winner_share(hitter: Player, misser: Player) -> float:
    """Fraction of `hitter`-won rallies that end in a clean WINNER (vs the
    opponent's forced error). Big ballstrikers finish more points outright; a
    steadier opponent coughs up fewer cheap errors, so more points have to be
    earned with a real winner."""
    t = TUNE
    swing = (t["winner_power"] * (_offense(hitter) - 0.5)
             + t["winner_steady"] * (misser.consistency - 0.5))
    return _clamp01(t["winner_share"] + swing)


def _unforced_share(state: MatchState, server: Player, returner: Player) -> float:
    """Of the rallies the returner won, how many were the server's UNFORCED
    error (vs a returner winner). Consistency is the driver: a low-consistency
    server sprays, a metronome rarely misses — this is what makes unforced-error
    totals vary across players instead of clustering on a flat rate. Wind adds a
    few more misses on top."""
    t = TUNE
    steady = -t["unforced_steady"] * (server.consistency - 0.5) * 2
    wind = t["wind_error"] * state.context.wind * (1.0 - server.wind_tolerance)
    return _clamp01(t["unforced_share"] + steady + wind)


def _clutch(state: MatchState, server: Player, returner: Player) -> float:
    """Signed clutch term in [-1, 1]-ish: positive favours the server.
    Non-linear in pressure; scaled by mental gap and crowd comfort.
    """
    pressure = getattr(state, "pressure", 0.0)
    if pressure <= 0.0:
        return 0.0
    crowd = state.context.crowd * TUNE["crowd_pressure"] * (server.crowd_pressure - returner.crowd_pressure)
    return (pressure ** TUNE["clutch_exp"]) * ((server.mental - returner.mental) + crowd)


def play_point(state: MatchState) -> tuple[int, str]:
    s_idx = state.server
    r_idx = state.returner
    server = state.players[s_idx]
    returner = state.players[r_idx]
    s_stat = state.stats[s_idx]
    r_stat = state.stats[r_idx]

    s_stat.serve_points_total += 1
    r_stat.return_points_total += 1

    def award(winner: int, kind: str) -> tuple[int, str]:
        state.stats[winner].points_won += 1
        if winner == s_idx:
            s_stat.serve_points_won += 1
        else:
            r_stat.return_points_won += 1
        return winner, kind

    rng = state.rng
    clutch = _clutch(state, server, returner)

    # --- First serve ---
    s_stat.first_serve_points += 1
    if rng.random() < _first_serve_in_prob(state, server):
        s_stat.first_serves_in += 1
        first = True
    else:
        # Fault - go to second serve. Under pressure the less-clutch server
        # double-faults more (clutch term lowers the second-serve-in rate).
        s_stat.second_serve_points += 1
        second_in = _clamp01(_second_serve_in_prob(state, server) + TUNE["clutch_serve"] * clutch)
        if rng.random() >= second_in:
            s_stat.double_faults += 1
            return award(r_idx, "double_fault")
        first = False

    # --- Ace check ---
    if rng.random() < _ace_prob(server, returner, first):
        s_stat.aces += 1
        s_stat.winners += 1
        return award(s_idx, "ace")

    # --- Rally (clutch + hardcourt context swing the big points) ---
    ctx_bonus = _rally_condition_bonus(state, server, returner)
    if rng.random() < _server_rally_win_prob(server, returner, first,
                                             bonus=TUNE["clutch_logit"] * clutch + ctx_bonus):
        if rng.random() < _winner_share(server, returner):
            s_stat.winners += 1
            return award(s_idx, "winner")
        r_stat.unforced_errors += 1
        return award(s_idx, "forced_error")
    else:
        if rng.random() < _unforced_share(state, server, returner):
            s_stat.unforced_errors += 1
            return award(r_idx, "unforced_error")
        r_stat.winners += 1
        return award(r_idx, "winner")
