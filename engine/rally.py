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
    # STYLE MATCHUPS (owner rule 2026-09) — the point engine reads the SAME
    # style plane as the fast model (engine.fast.style_edge: an antisymmetric
    # cross term on attribute-cluster deviations, faded to zero as the overall
    # gap widens). Added to the neutral-rally logit as an edge for the server,
    # so over a match it is zero-sum and the rating gap is untouched; sized on
    # its own dial because a per-POINT edge compounds ~4-6 times a game where
    # the fast model's is per game. Calibrated with
    # scripts/style_matchup_calibration.py --fidelity full.
    "style_k": 1.2,
    # NET PLAY IN SINGLES (owner rule 2026-09). A neutral rally can now go to
    # the net: each player comes forward at `approach_base` per rally, moved by
    # their approach game RELATIVE TO THEIR OWN rally level (`approach_swing` x
    # (approach_game - rally_skill) — a deviation, so a flat player approaches
    # at the base rate whatever their level and a serve-and-volleyer far more).
    # The point is then the baseline rally logit PLUS `net_slope` x (the
    # netter's net game - the passer's passing game), signed for whoever came
    # in. Zero for two flat players, so the calibrated favourite rate is
    # untouched on average; what changes is WHO wins the points that reach the
    # net. Serve-and-volley: a first serve in is followed by an approach at
    # `sv_base`, again moved by the server's approach deviation.
    "approach_base": 0.14,
    "approach_swing": 0.60,
    "sv_base": 0.05,
    "net_slope": 1.1,
    # RETURN PRICING (owner rule 2026-09). Before this the return reached a
    # singles point only through the ace offset, so a return-built player
    # (counterpuncher, return specialist) measured ~44% against the field at
    # equal grade while a serve-built one ran hot. The server's rally edge
    # after the serve lands now flexes with the serve-vs-return SHAPE: (the
    # server's serve deviation from their rally level) minus (the returner's
    # return deviation from theirs), times `serve_plus_swing`. Deviations, so
    # two flat players reproduce the calibrated curve exactly.
    "serve_plus_swing": 0.5,
    # COMPOSITIONAL STYLE TENDENCIES (owner rule 2026-09) — behaviour, read off
    # `Player.tend` (engine.state.Player.tendency). Each is a small, bounded
    # term and every one is a DEVIATION or a matchup, never a level bonus:
    #   approach  adds to the per-rally approach rate (net rusher, all-court)
    #   sv        adds to the serve-and-volley rate behind a first serve
    #   chip      adds to the RETURNER's approach rate (chip-and-charge)
    #   strike    first-strike: rally logit += strike * (own attack deviation -
    #             opponent's steadiness deviation); winners AND errors up
    #   grind     the mirror: steadiness deviation vs the opponent's attack
    #             deviation; winners and errors down (longer points)
    #   cover     retriever: court-cover deviation vs the opponent's attack
    #   slice     blunts the OPPONENT's strike term (a low ball is hard to hit
    #             through) and adds a little approach
    #   retspec   return specialist: the return side of serve_plus_swing and
    #             the ace offset both count more for this player
    #   bigserve  the ace swing counts more for this server
    #   topspin   heavy ball: pushes the opponent back — their approach rate
    #             drops — and a small grind
    "tend_strike_slope": 0.8,
    "tend_grind_slope": 0.8,
    "tend_cover_slope": 0.8,
    "tend_share": 0.10,         # end-share tilt per unit of strike (up) / grind (down)
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
    # can't return. There is deliberately NO absolute-level term here (owner rule
    # 2027-07): every division's players are the pros of their own world, so a
    # matched D4 dual reads like a matched D1 dual on the stat sheet — exactly as
    # a Challenger box score reads like an ATP one, and the difference only shows
    # when the levels MEET. The matchup gap is the whole dial: outgun your
    # opponent and your winners and their forced errors rise; get outgunned and
    # your losses tilt unforced. Do not re-add a level anchor — that was the bug
    # (players far from the old `swing_ref` posted 0-winner and 0-UE matches).
    "end_winner_base": 0.27,   # winner fraction of rally ends in a matched pairing
    "end_winner_gap": 0.45,    # your attack basket vs their defense basket
    "end_forced_base": 0.57,   # of the loser's errors: forced fraction, matched
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
    # bigserve / retspec scale each player's OWN deviation (serve above their
    # rally level, return above theirs) — never the level term, so a big
    # server below the reference is not punished for the label.
    edge = ((power - ref) + server.tendency("bigserve") * (power - server.rally_skill)
            - t["ace_return_weight"] * ((returner.return_solidity - ref)
                                        + returner.tendency("retspec")
                                        * (returner.return_solidity - returner.rally_skill)))
    return _clamp01(base + t["ace_swing"] * edge)


def _server_rally_win_prob(server: Player, returner: Player, first: bool,
                           bonus: float = 0.0, net: float = 0.0) -> float:
    """Probability the server wins a rally that reached neutral play.
    `bonus` is an additive logit term (clutch/context swing on big points);
    `net` is the signed net-exchange term (`_net_term`) when the rally went
    to the net, zero for a baseline rally.
    """
    t = TUNE
    serve_plus = t["serve_plus_first"] if first else t["serve_plus_second"]
    diff = (server.rally_skill - returner.rally_skill)
    style = _style_edge(server, returner, t["style_k"])
    # serve-vs-return shape on the serve+1 edge (deviations, see TUNE)
    shape = t["serve_plus_swing"] * (
        (server.serve_skill - server.rally_skill)
        - (returner.return_game - returner.rally_skill) * (1.0 + returner.tendency("retspec")))
    return _logistic(t["rally_slope"] * diff + serve_plus + bonus + style + net + shape
                     + _tendency_terms(server, returner))


def _tendency_terms(a: Player, b: Player) -> float:
    """The behavioural matchup terms, as a logit edge for `a` over `b` —
    strike / grind / cover, each `a`'s own tendency against `b`'s shape and
    `b`'s tendency against `a`'s, all on attribute DEVIATIONS from the
    player's rally level (a flat player contributes nothing and a level gap
    never leaks in). `slice` blunts the opponent's strike."""
    t = TUNE
    out = 0.0
    for me, you, sign in ((a, b, 1.0), (b, a, -1.0)):
        # ‼️ OPPONENT terms only. `me`'s own attack/steadiness deviation is
        # already priced (it IS the shape the shifts bought); multiplying the
        # tendency by it made every trait a strength bonus against a balanced
        # field (first_strike measured 56.7%). What a tendency changes is how
        # the player fares against a PARTICULAR opponent: an attacker profits
        # against an unsteady one and pays against a wall; a grinder or a
        # retriever profits against an erratic hitter and pays against a clean
        # one. Zero-mean over a field by construction.
        y_atk = you.attack - you.rally_skill
        y_std = you.steadiness - you.rally_skill
        strike = me.tendency("strike") * (1.0 - min(0.6, you.tendency("slice")))
        out += sign * (-t["tend_strike_slope"] * strike * y_std
                       - t["tend_grind_slope"] * (me.tendency("grind") + 0.3 * me.tendency("topspin")) * y_atk
                       - t["tend_cover_slope"] * me.tendency("cover") * y_atk)
    return out


def _approach_prob(p: Player, base: float) -> float:
    """How often `p` comes forward in a neutral rally — the base rate moved by
    their approach game relative to their own rally level."""
    return _clamp01(base + TUNE["approach_swing"] * (p.approach_game - p.rally_skill))


def _net_term(netter: Player, passer: Player) -> float:
    """The net exchange, as a logit edge for the NETTER: their net game
    against the passer's passing game — each as a DEVIATION from that
    player's own rally level. The level gap already rides on `rally_slope`;
    read raw, the net term was a second copy of it and lifted the favourite's
    win rate ~4 points across the 3-12 OVR bands (measured). As deviations,
    two flat players cancel exactly and only SHAPE decides who wins the
    points that reach the net."""
    return TUNE["net_slope"] * ((netter.net_game - netter.rally_skill)
                                - (passer.passing_game - passer.rally_skill))


def _style_edge(a: Player, b: Player, k: float) -> float:
    """`a`'s style-plane edge over `b` (engine.fast.style_edge), on this
    module's dial. Imported lazily: engine.fast imports engine.match."""
    if not k:
        return 0.0
    from .fast import style_vector, style_edge
    xa, ya = style_vector(a)
    xb, yb = style_vector(b)
    return style_edge(xa, ya, xb, yb, a.overall - b.overall,
                      {"style_k": k, "style_fade": _STYLE_FADE})


_STYLE_FADE = 0.15      # mirrors engine.fast.TUNE["style_fade"]; pinned by a test

#: The tendency keys engine.rally reads off Player.tend (a test pins that the
#: generator emits no other).
TENDENCY_KEYS = ("approach", "sv", "chip", "strike", "grind", "cover", "slice",
                 "retspec", "bigserve", "topspin")


def _end_shares(state: MatchState, hitter: Player, misser: Player) -> tuple[float, float]:
    """How a rally that `hitter` just WON gets labeled, as two clamped fractions:
    (winner_frac, forced_frac) — the chance the point ends on the hitter's clean
    WINNER, else the misser's error, which is FORCED with `forced_frac` and
    UNFORCED otherwise. Symmetric: called for whichever side won the rally.

    Anchored on the MATCHUP only, never the level (owner rule 2027-07): `gap` is
    the hitter's attacking basket vs the misser's defensive basket, so a 35-STR
    player beating up on a 30 hits real winner counts, and a matched pair of weak
    players splits points exactly like a matched pair of stars — every level is
    the pros of its own world. Wind tilts the misser's errors unforced."""
    t = TUNE
    atk = 0.55 * hitter.attack + 0.25 * hitter.court_cover + 0.20 * hitter.go_for_it
    dfn = 0.60 * misser.steadiness + 0.40 * misser.court_cover
    gap = atk - dfn
    wind = t["wind_error"] * state.context.wind * (1.0 - misser.wind_tolerance)
    f = t["share_floor"]

    def clamp(x: float) -> float:
        return max(f, min(1.0 - f, x))
    # first-strikers end points on winners and errors, grinders on neither —
    # a tilt on how a won point is LABELLED (points already decided above).
    tilt = t["tend_share"] * (hitter.tendency("strike") - hitter.tendency("grind")
                              - 0.5 * hitter.tendency("cover"))
    winner_frac = clamp(t["end_winner_base"] + t["end_winner_gap"] * gap + tilt)
    forced_frac = clamp(t["end_forced_base"] + t["end_forced_gap"] * gap - wind
                        + t["tend_share"] * (misser.tendency("grind") - misser.tendency("strike")))
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
    # --- Who comes to the net, if anyone (owner rule 2026-09) ---
    # One draw: the server's approach band first (serve-and-volley behind a
    # first serve, an approach off the ground otherwise), then the returner's.
    t = TUNE
    sv = (t["sv_base"] + server.tendency("sv")) if first else 0.0
    p_s = _approach_prob(server, t["approach_base"] + sv + server.tendency("approach")
                         - returner.tendency("topspin") * 0.05)
    p_r = _approach_prob(returner, t["approach_base"] + returner.tendency("approach")
                         + returner.tendency("chip") - server.tendency("topspin") * 0.05)
    roll = rng.random()
    net = 0.0
    if roll < p_s:
        net = _net_term(server, returner)
        s_stat.net_points += 1
        netter = s_idx
    elif roll < p_s + p_r:
        net = -_net_term(returner, server)
        r_stat.net_points += 1
        netter = r_idx
    else:
        netter = None
    # One draw labels the end (winner / forced / unforced) whichever side won.
    if rng.random() < _server_rally_win_prob(server, returner, first,
                                             bonus=TUNE["clutch_logit"] * clutch + ctx_bonus,
                                             net=net):
        if netter == s_idx:
            s_stat.net_points_won += 1
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
        if netter == r_idx:
            r_stat.net_points_won += 1
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
