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
    "first_in_base": 0.60,
    "first_in_swing": 0.10,
    # Second-serve in rate. Lower base ⇒ more double faults; the swing rewards
    # placement, `second_in_nerve` lets a composed server hold it together, and
    # `second_in_aggression` couples aces and double faults the way real tennis
    # does (pro men r≈0.93): a big serve spills more second serves too.
    "second_in_base": 0.845,
    "second_in_swing": 0.08,
    "second_in_nerve": 0.06,
    "second_in_aggression": 0.10,
    # Ace rates given the serve landed in. Calibrated to real NCAA men (~7% of
    # service points). `ace_swing` scales the serve edge; `ace_return_weight` is
    # how much the returner offsets raw serve power (<1 so a genuine cannon stays
    # an ace machine even against a good return).
    "ace_first_base": 0.085,
    "ace_second_base": 0.02,
    "ace_swing": 0.20,
    "ace_return_weight": 0.55,
    # Server's edge in a neutral rally, by serve number.
    "serve_plus_first": 0.55,
    "serve_plus_second": 0.20,
    "rally_slope": 3.2,
    # Reference talent level the winner/error/ace swings are measured against.
    # Real rosters center well above 0.5 (D1 ≈ 0.68, D2 ≈ 0.49, D3 ≈ 0.42), so the
    # swings anchor here: a player AT the reference gets the baseline rate, a
    # stronger one bends it toward winners/aces, a weaker one toward errors. This
    # is what makes the levels land right on real rosters (not just synthetic
    # base-0.5 players) AND gives sensible cross-division texture.
    "swing_ref": 0.68,
    # Point-outcome split. A rally the server wins is either a WINNER or the
    # returner's FORCED error; a rally the returner wins is either the server's
    # UNFORCED error or a returner winner. Baselines calibrated to real NCAA men
    # (~32% winners / ~41% forced / ~27% unforced — O'Shannessy). The shares flex
    # per point with talent, so totals spread by player instead of sitting flat.
    "winner_share": 0.22,     # server-won rally: winner vs returner forced error
    "unforced_share": 0.73,   # returner-won rally: server unforced error vs returner winner
    # How far player attributes swing the split. Each stat reads a small BASKET of
    # attributes, so its total carries a distinct talent fingerprint.
    "winner_power": 0.28,     # groundstroke weapons → more winners
    "winner_move": 0.14,      # court coverage manufactures put-away chances
    "winner_nerve": 0.10,     # willingness to go for the shot
    "winner_steady": 0.22,    # steadier opponent gifts fewer cheap errors
    "unforced_steady": 0.50,  # low-consistency server sprays more unforced errors
    "unforced_move": 0.18,    # a mover retrieves would-be errors back into rallies
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
    ref = t["swing_ref"]
    return _clamp01(t["first_in_base"] + t["first_in_swing"] * (server.first_serve_in_skill - ref) * 2
                    + _serve_condition_bonus(state, server))


def _second_serve_in_prob(state: MatchState, server: Player) -> float:
    t = TUNE
    ref = t["swing_ref"]
    # Serve aggression couples aces and double faults the way real tennis does
    # (pro men: r≈0.93): a big-serve player goes for more, so the same power that
    # earns aces also spills more second serves. Placement/composure pull the
    # other way, so a big AND accurate server can still keep faults down.
    return _clamp01(t["second_in_base"]
                    + t["second_in_swing"] * (server.second_serve_in_skill - ref) * 2
                    + t["second_in_nerve"] * (server.serve_composure - ref) * 2
                    - t["second_in_aggression"] * (server.ace_power_first - ref) * 2
                    + 0.7 * _serve_condition_bonus(state, server))


def _ace_prob(server: Player, returner: Player, first: bool) -> float:
    t = TUNE
    base = t["ace_first_base"] if first else t["ace_second_base"]
    # Absolute serve power drives aces; the return only partly offsets it, so a
    # true cannon reads as an ace machine regardless of who's across the net.
    ref = t["swing_ref"]
    power = server.ace_power_first if first else server.ace_power_second
    edge = (power - ref) - t["ace_return_weight"] * (returner.return_solidity - ref)
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


def _winner_share(hitter: Player, misser: Player) -> float:
    """Fraction of `hitter`-won rallies that end in a clean WINNER (vs the
    opponent's forced error). Reads a basket of the actual weapons — groundstroke
    pop, passing, approach, court vision, plus the court coverage that
    manufactures put-aways and the nerve to go for it — so a shot-maker's winner
    count reflects the whole profile, not one collapsed number. A steadier
    opponent coughs up fewer cheap errors, so more points must be earned with a
    real winner."""
    t = TUNE
    ref = t["swing_ref"]
    swing = (t["winner_power"] * (hitter.attack - ref)
             + t["winner_move"] * (hitter.court_cover - ref)
             + t["winner_nerve"] * (hitter.go_for_it - ref)
             + t["winner_steady"] * (misser.steadiness - ref))
    return _clamp01(t["winner_share"] + swing)


def _unforced_share(state: MatchState, server: Player, returner: Player) -> float:
    """Of the rallies the returner won, how many were the server's UNFORCED
    error (vs a returner winner). Steadiness leads — a disciplined, high-tolerance
    ballstriker rarely misses, a sprayer piles them up — and court coverage helps:
    a good mover turns would-be errors back into rallies. Together they make
    unforced-error totals vary by player instead of clustering on a flat rate.
    Wind adds a few more misses on top."""
    t = TUNE
    ref = t["swing_ref"]
    steady = (-t["unforced_steady"] * (server.steadiness - ref)
              - t["unforced_move"] * (server.court_cover - ref)) * 2
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
        r_stat.forced_errors += 1
        return award(s_idx, "forced_error")
    else:
        if rng.random() < _unforced_share(state, server, returner):
            s_stat.unforced_errors += 1
            return award(r_idx, "unforced_error")
        r_stat.winners += 1
        return award(r_idx, "winner")
