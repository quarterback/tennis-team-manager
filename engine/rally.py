"""
Serve + rally probability tables — the point-resolution core.

"Talent shifts the distribution": player attributes move these tables, they
don't script outcomes. All tunables live in `TUNE` so the model can be
retuned without touching logic (mirrors `o27/config.py`). Every draw uses
`state.rng`, so a seeded match is deterministic.

`play_point(state)` resolves ONE point on the current server's serve,
records serve/rally stats on both players, appends a PBP line, and returns
`(winner_index, kind)` where kind ∈
{"ace", "double_fault", "winner", "forced_error", "unforced_error"}.
Game / break-point context is handled by the caller in `match.py`.
"""
from __future__ import annotations

import math

from .state import MatchState, Player

TUNE = {
    # First / second serve in-play rates (before talent adjustment).
    "first_in_base": 0.62,
    "first_in_swing": 0.10,     # ± from serve_placement
    "second_in_base": 0.90,
    "second_in_swing": 0.08,
    # Ace rates given the serve landed in.
    "ace_first_base": 0.16,
    "ace_second_base": 0.04,
    "ace_swing": 0.18,          # scaled by (server.serve_power - returner.return_game)
    # Server's edge in a neutral rally, by serve number.
    "serve_plus_first": 0.55,   # logistic bias toward server after a first serve
    "serve_plus_second": 0.20,
    "rally_slope": 3.2,         # how sharply rally_skill diff tilts the rally
    # Of the points won/lost in a rally, how many are "decisive" shots vs errors.
    "winner_share": 0.42,       # fraction of won rally points credited as winners
    "unforced_share": 0.55,     # fraction of lost rally points that are unforced
    # --- Pressure / clutch (pazzah-style, adapted) ---
    # On big points (break/set/match points, late tiebreaks) the clutch gap
    # (server.mental - returner.mental) swings the point. Non-linear in pressure
    # so routine points are barely affected and championship points swing hard.
    "clutch_logit": 1.15,       # rally win-prob logit swing at full pressure × full mental gap
    "clutch_exp": 1.6,          # >1 ⇒ pressure bites mostly on the biggest points
    "clutch_serve": 0.07,       # 2nd-serve-in swing (the non-clutch server double-faults under pressure)
}


def _logistic(x: float, slope: float = 1.0) -> float:
    return 1.0 / (1.0 + math.exp(-slope * x))


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _first_serve_in_prob(server: Player) -> float:
    t = TUNE
    return _clamp01(t["first_in_base"] + t["first_in_swing"] * (server.serve_placement - 0.5) * 2)


def _second_serve_in_prob(server: Player) -> float:
    t = TUNE
    return _clamp01(t["second_in_base"] + t["second_in_swing"] * (server.serve_placement - 0.5) * 2)


def _ace_prob(server: Player, returner: Player, first: bool) -> float:
    t = TUNE
    base = t["ace_first_base"] if first else t["ace_second_base"]
    edge = (server.serve_power - returner.return_game)
    return _clamp01(base + t["ace_swing"] * edge)


def _server_rally_win_prob(server: Player, returner: Player, first: bool,
                           bonus: float = 0.0) -> float:
    """Probability the server wins a rally that reached neutral play.
    `bonus` is an additive logit term (clutch swing on big points)."""
    t = TUNE
    serve_plus = t["serve_plus_first"] if first else t["serve_plus_second"]
    diff = (server.rally_skill - returner.rally_skill)
    # serve_plus is an additive logit bump for holding serve.
    return _logistic(t["rally_slope"] * diff + serve_plus + bonus)


def _clutch(state: MatchState, server: Player, returner: Player) -> float:
    """Signed clutch term in [-1, 1]-ish: positive favours the server.
    Non-linear in the point's pressure; scaled by the mental-toughness gap."""
    pressure = getattr(state, "pressure", 0.0)
    if pressure <= 0.0:
        return 0.0
    return (pressure ** TUNE["clutch_exp"]) * (server.mental - returner.mental)


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
    if rng.random() < _first_serve_in_prob(server):
        s_stat.first_serves_in += 1
        first = True
    else:
        # Fault — go to second serve. Under pressure the less-clutch server
        # double-faults more (clutch term lowers the second-serve-in rate).
        s_stat.second_serve_points += 1
        second_in = _clamp01(_second_serve_in_prob(server) + TUNE["clutch_serve"] * clutch)
        if rng.random() >= second_in:
            s_stat.double_faults += 1
            return award(r_idx, "double_fault")
        first = False

    # --- Ace check ---
    if rng.random() < _ace_prob(server, returner, first):
        s_stat.aces += 1
        s_stat.winners += 1
        return award(s_idx, "ace")

    # --- Rally (clutch swings the big points) ---
    if rng.random() < _server_rally_win_prob(server, returner, first,
                                             bonus=TUNE["clutch_logit"] * clutch):
        # Server wins the rally.
        if rng.random() < TUNE["winner_share"]:
            s_stat.winners += 1
            return award(s_idx, "winner")
        r_stat.unforced_errors += 1
        return award(s_idx, "forced_error")
    else:
        # Returner wins the rally.
        if rng.random() < TUNE["unforced_share"]:
            s_stat.unforced_errors += 1
            return award(r_idx, "unforced_error")
        r_stat.winners += 1
        return award(r_idx, "winner")
