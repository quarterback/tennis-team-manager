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
    # Server's edge in a neutral rally, by serve number, and how hard the rally-
    # skill gap bites. These are the OUTCOME competitiveness dials now that the full
    # point engine decides matches (not the fast model): calibrated so the favorite
    # wins ~77% overall on real D1 rosters — close matchups near a coin-flip, real
    # talent gaps decisive but never certain (0-0.5 UTR ~53%, 1-1.5 ~73%, 2-3 ~90%,
    # 3+ ~96%). Dense talent (tight roster spread) keeps most duals competitive; the
    # rally slope is what turns a real gap into an edge without predetermining it.
    "serve_plus_first": 0.36,
    "serve_plus_second": 0.10,
    "rally_slope": 0.9,
    # Reference talent level the winner/error/ace swings are measured against.
    # Real rosters center well above 0.5 (D1 ≈ 0.68, D2 ≈ 0.49, D3 ≈ 0.42), so the
    # swings anchor here: a player AT the reference gets the baseline rate, a
    # stronger one bends it toward winners/aces, a weaker one toward errors. This
    # is what makes the levels land right on real rosters (not just synthetic
    # base-0.5 players) AND gives sensible cross-division texture.
    "swing_ref": 0.68,
    # Point-ending attribution (owner research 2027-07 — O'Shannessy/Brain Game
    # Tennis, Ultimate Tennis Statistics, Tennis View). Every rally end is a
    # THREE-WAY split: the point-winner's clean WINNER, or the loser's FORCED
    # error, or the loser's UNFORCED error — on BOTH sides symmetrically (a
    # returner can dump an easy ball while losing the point on serve too; the old
    # model only ever charged UEs to the server and FEs to the returner).
    #
    # A winner is RELATIVE TO THE OPPONENT: a shot the player across the net
    # can't return. Matched weak players therefore produce near-normal winner
    # counts — their tennis is uglier, not winner-less — so the split is anchored
    # on the MATCHUP GAP (your weapons vs their defense), with only a small
    # absolute-level drift (real mix: ~32/41/27 pro men, 29/37/34 pro women,
    # "slightly lower at collegiate levels" — the mix compresses a few points as
    # level drops, it never collapses). The gap term is what pays for aggression:
    # outgun your opponent and your winners and their forced errors rise; get
    # outgunned and your losses tilt unforced.
    "end_winner_base": 0.27,   # winner fraction of rally ends, matched at swing_ref
    "end_winner_level": 0.08,  # small absolute drift: lower-level → slightly fewer winners
    "end_winner_gap": 0.45,    # your attack basket vs their defense basket
    "end_forced_base": 0.57,   # of the loser's errors: forced fraction, matched at ref
    "end_forced_level": 0.24,  # lower-level errors tilt unforced (sloppier misses)
    "end_forced_gap": 0.35,    # a bigger gap makes the loser's misses FORCED
    # Attribution floor: the shares are clamped into [floor, 1-floor]. They only
    # LABEL a point already won — never decide one — so this is box-score texture:
    # nobody plays a whole match with zero winners or zero unforced errors.
    "share_floor": 0.06,
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


def _end_shares(state: MatchState, hitter: Player, misser: Player) -> tuple[float, float]:
    """How a rally that `hitter` just WON gets labeled, as two clamped fractions:
    (winner_frac, forced_frac) — the chance the point ends on the hitter's clean
    WINNER, else the misser's error, which is FORCED with `forced_frac` and
    UNFORCED otherwise. Symmetric: called for whichever side won the rally.

    Anchored on the MATCHUP, not the level: `gap` is the hitter's attacking
    basket vs the misser's defensive basket, so a 35-STR player beating up on a
    30 hits real winner counts and a matched pair of weak players still splits
    points like tennis players do (their mix drifts only `end_*_level` softer).
    Wind tilts the misser's errors unforced."""
    t = TUNE
    atk = 0.55 * hitter.attack + 0.25 * hitter.court_cover + 0.20 * hitter.go_for_it
    dfn = 0.60 * misser.steadiness + 0.40 * misser.court_cover
    gap = atk - dfn
    lvl = (atk + dfn) / 2.0 - t["swing_ref"]
    wind = t["wind_error"] * state.context.wind * (1.0 - misser.wind_tolerance)
    f = t["share_floor"]

    def clamp(x: float) -> float:
        return max(f, min(1.0 - f, x))
    winner_frac = clamp(t["end_winner_base"] + t["end_winner_gap"] * gap
                        + t["end_winner_level"] * lvl)
    forced_frac = clamp(t["end_forced_base"] + t["end_forced_gap"] * gap
                        + t["end_forced_level"] * lvl - wind)
    return winner_frac, forced_frac


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
    # One draw labels the end (winner / forced / unforced) whichever side won —
    # the SAME single rng.random() the old two-way split consumed, so the stream,
    # and with it every outcome, is bit-identical to before this model existed.
    if rng.random() < _server_rally_win_prob(server, returner, first,
                                             bonus=TUNE["clutch_logit"] * clutch + ctx_bonus):
        w_frac, f_frac = _end_shares(state, server, returner)
        roll = rng.random()
        if roll < w_frac:
            s_stat.winners += 1
            return award(s_idx, "winner")
        if roll < w_frac + (1.0 - w_frac) * f_frac:
            r_stat.forced_errors += 1
            return award(s_idx, "forced_error")
        r_stat.unforced_errors += 1
        return award(s_idx, "unforced_error")
    else:
        w_frac, f_frac = _end_shares(state, returner, server)
        roll = rng.random()
        if roll < w_frac:
            r_stat.winners += 1
            return award(r_idx, "winner")
        if roll < w_frac + (1.0 - w_frac) * f_frac:
            s_stat.forced_errors += 1
            return award(r_idx, "forced_error")
        s_stat.unforced_errors += 1
        return award(r_idx, "unforced_error")
