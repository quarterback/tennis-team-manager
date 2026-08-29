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
    # ABILITY SHAPE, not just ability size (owner rule 2027-08). `overall` alone
    # made two players with the same mean indistinguishable — a serve-first
    # player and a counterpuncher rolled the same dice. A service game is now
    # decided by a per-SITUATION composite instead: the server's serve and
    # rally game against the returner's return and rally game, with small
    # always-on mental/stamina lanes. The lane weights are chosen so that (a)
    # two flat players reproduce the overall gap EXACTLY — the wide-gap
    # calibration above is untouched — and (b) averaged over a player's
    # serving and returning games every driver keeps ~its share of `overall`
    # (role-averaged lane weights land within ±0.02 of the uniform 1/9), so no
    # play style is systematically over- or under-priced; what changes is WHO
    # a given shape works against. A big server holds past his overall and an
    # elite returner breaks past hers — and against each other they cancel.
    # Tiebreaks add the mental deviation (big points belong to the clutch
    # player), and the DECIDING set adds the stamina deviation (the fitter
    # player grows as the match goes long); both are deviations from the
    # player's own overall, so they are zero for a flat player and zero-mean
    # over a league. The drivers are themselves rich-attribute baskets
    # (app.player_attributes.derive_drivers), so first_serve_power,
    # return_quality, composure, recovery etc. all reach the outcome — the
    # same signal chain the full engine reads, collapsed per situation
    # instead of per point.
    # Lane weights sum to 1 (flat-player equivalence); with the composite
    # mixes in `_edges` the role-averaged per-driver weights all land within
    # 0.009 of the uniform 1/9 — re-derive that check before retuning any of
    # the four, or one play style quietly becomes over- or under-priced.
    "hold_serve": 0.44,         # server's serve vs the returner's return game
    "hold_rally": 0.32,         # both players' groundstroke/movement game
    "hold_mental": 0.12,        # always-on composure lane
    "hold_stamina": 0.12,       # always-on fitness lane
    # Situational extras are DEVIATIONS from the player's own overall, priced
    # so mental/stamina end up worth roughly the same win-equity as any other
    # driver despite landing on the match's biggest moments — raise these and
    # clutch/fitness quietly become the best stats in the game.
    "edge_clutch": 0.35,        # mental deviation on tiebreak points
    "edge_stamina": 0.25,       # stamina deviation once the match goes the distance
}


# HIGH-SCHOOL SCORELINE PROFILE (owner rule 2026-08 — calibrated against five
# seasons of REAL Oregon high-school results, boys + girls, 41,932 varsity
# matches / 84,238 sets: github.com/quarterback/or-tennis-data). Real HS tennis
# is blowout-shaped — 6-0 is the single most COMMON set (26.4%), frequency falls
# monotonically toward 7-6 (3.9%), and only 13.8% of matches reach a third set —
# where the college-calibrated defaults produced the near-INVERSE (7-6 at 14.9%,
# 6-0 at 2.5%, 42.8% three-setters). And the shape is near-UNIFORM across the
# association: boys/girls, flights D1-D3 and S2/S3 all sit within ~2 points of
# each other in the real data (only No. 1 singles is more lopsided still, 33%
# 6-0 — talent concentrates at the top flight), so ONE profile serves every
# line. Two dials move, both deliberate:
#   * hold_base_logit -0.4: at HS level a BREAK is the expected outcome of a
#     game (real hold rates run 30-45%, vs ~80% ATP / ~65% WTA; the profile
#     measures ~44%). Serve stays a full SKILL lane (`hold_serve` untouched —
#     a big server still steals matches past his overall); what goes away is
#     the structural free hold that made near-equal HS sets random-walk to
#     6-6.
#   * skill_slope 6 + gap_knee 0.02: HS talent disparities are massive and
#     the college knee (0.06) sat exactly ON the median matched-line gap
#     (0.059 measured across JHSAA district play), so HALF of all real
#     mismatches were being played as "even matches" — the anti-blowout band
#     was designed too wide for this level, which is ALSO the fix for the
#     owner-reported unreal upset volume: this profile deliberately steepens
#     the match-win curve (favorite at a 0.03 gap ~76%, saturating by 0.08 —
#     vs the college curve's 52%/67%), superseding the flatter JHSAA table in
#     docs/AAR-jhsaa-upset-variance-recalibration.md for HS play.
# NO per-match "form"/hot-cold variable — considered and rejected (owner,
# 2026-08): the ratings already abstract day-to-day HS chaos, and a latent
# noise term that exists to reproduce a score distribution is the model
# compensating for a mis-set deterministic core. Fix the core instead.
# Measured with the profile on (vs real): see
# docs/AAR-jhsaa-scoreline-realism.md; re-measure with
# scripts/jhsaa_scoreline_benchmark.py before retuning anything here. The
# `d_*` keys are the doubles fast model's equivalents, scaled by the same
# ratios its college dials carry over the singles ones
# (engine.doubles.TUNE fast_* / this TUNE).
# `profile=None` (every college/cup/pro call) is BYTE-IDENTICAL to the
# pre-profile model. Pinned by tests/test_jhsaa_scorelines.py.
HS_PROFILE = {
    "hold_base_logit": -0.4,
    "skill_slope": 6.0,
    "tb_slope": 4.5,
    "gap_knee": 0.02,
    "gap_accel": 1.8,
    # doubles fast model (engine.doubles reads these; ratios mirror its
    # college dials: hold 1.05/0.9, slope 2.4/1.5, tb 1.8/1.13)
    "d_hold_logit": -0.47,
    "d_skill_slope": 9.6,
    "d_tb_slope": 7.2,
}


def effective_gap(gap: float, knee: float | None = None,
                  accel: float | None = None) -> float:
    """The gap the fast models PLAY ON: real gap below the knee, accelerated
    beyond it. Sign-symmetric and continuous; identity for |gap| <= knee.
    `knee`/`accel` default to TUNE's (the college calibration); a profile
    passes its own."""
    knee = TUNE["gap_knee"] if knee is None else knee
    accel = TUNE["gap_accel"] if accel is None else accel
    extra = abs(gap) - knee
    if extra <= 0:
        return gap
    return gap + (extra if gap > 0 else -extra) * accel


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _context_edge(server: Player, returner: Player, context: MatchContext) -> float:
    venue = (server.indoor_comfort - returner.indoor_comfort) if context.indoor else (server.outdoor_comfort - returner.outdoor_comfort)
    wind = context.wind * (server.wind_tolerance - returner.wind_tolerance)
    heat = context.heat * (server.heat_tolerance - returner.heat_tolerance)
    crowd = context.crowd * (server.crowd_pressure - returner.crowd_pressure)
    return venue + wind + heat + crowd


def _edges(p: Player) -> dict:
    """A player's situational profile, computed once per match. `serve`, `ret`
    and `rally` are role composites; `m_dev`/`s_dev` are zero-mean deviations
    from the player's own overall (exactly zero for a flat player, so the
    pre-shape calibration is reproduced)."""
    o = p.overall
    return {
        "serve": 0.5 * p.serve_power + 0.5 * p.serve_placement,
        "ret": 0.5 * p.return_game + 0.25 * p.movement + 0.25 * p.consistency,
        "rally": 0.35 * p.forehand + 0.35 * p.backhand
                 + 0.15 * p.movement + 0.15 * p.consistency,
        "mental": p.mental,
        "stamina": p.stamina,
        "overall": o,
        "m_dev": p.mental - o,
        "s_dev": p.stamina - o,
    }


def _hold_prob(server: Player, returner: Player, context: MatchContext,
               es: dict, er: dict, decider: bool, tune: dict = TUNE) -> float:
    """One service game, decided by the situational composite: the server's
    serve against the returner's return game, both players' rally games, and
    the always-on mental/stamina lanes (`es`/`er` are the two players' profile
    dicts, server's first). Two flat players reproduce the overall gap
    exactly. In the deciding set the stamina deviation joins in."""
    gap = (tune["hold_serve"] * (es["serve"] - er["ret"])
           + tune["hold_rally"] * (es["rally"] - er["rally"])
           + tune["hold_mental"] * (es["mental"] - er["mental"])
           + tune["hold_stamina"] * (es["stamina"] - er["stamina"]))
    if decider:
        gap += tune["edge_stamina"] * (es["s_dev"] - er["s_dev"])
    return _logistic(
        tune["hold_base_logit"]
        + tune["skill_slope"] * effective_gap(gap, tune["gap_knee"],
                                              tune["gap_accel"])
        + tune["context_slope"] * _context_edge(server, returner, context))


def _tb_prob(p0: Player, p1: Player, context: MatchContext,
             e0: dict, e1: dict, decider: bool, tune: dict = TUNE) -> float:
    """A tiebreak is big points: the mental deviation counts beyond the talent
    gap, and in a deciding set so does the stamina deviation. Reads `overall`
    off the edge dicts (identical to the players' own except under the HS
    profile, where each carries its side's per-match form)."""
    gap = (e0["overall"] - e1["overall"]
           + tune["edge_clutch"] * (e0["m_dev"] - e1["m_dev"]))
    if decider:
        gap += tune["edge_stamina"] * (e0["s_dev"] - e1["s_dev"])
    return _logistic(
        tune["tb_slope"] * effective_gap(gap, tune["gap_knee"],
                                         tune["gap_accel"])
        + tune["context_slope"] * _context_edge(p0, p1, context))


def _mtb_score(win: int, r: float, p: float, target: int) -> tuple[int, int]:
    """A MATCH TIEBREAK's score for the fast model — `10-6`, not `1-0`.

    ‼️ THE FAST MODEL DECIDES A TIEBREAK WITH ONE COIN FLIP AND NEVER PLAYS THE
    POINTS, so there is no real 10-8 to report and this returned the SET score
    `(1, 0)` instead. "1-0 doesn't tell me anything" (owner, 2026-08) — and it is
    also inconsistent, because the FULL model plays the points and prints `10-8`,
    so the same fixture read differently depending on fidelity. It is live in the
    Davis/BJK cups, which run a 10-point decider at fast fidelity.

    ‼️ IT CONSUMES NO EXTRA RNG DRAW, and that is the load-bearing constraint: the
    margin is read out of the draw ALREADY TAKEN. `r` is that draw and `p` the win
    probability, so how far `r` landed from the threshold is exactly how comfortable
    the win was — a dominant tiebreak and a squeaker are already distinguished by
    the number in hand. Drawing again would shift every subsequent scoreline in
    fast mode and break `engine.boxstats`, which replays this flow point by point
    on the promise that the flow costs nothing.

    The loser's score is therefore a function of that distance: level with the
    threshold gives a two-point squeaker, the far end a runaway."""
    edge = abs(r - p) / max(p, 1.0 - p, 1e-9)          # 0 = squeaker, 1 = runaway
    lo = int(round((1.0 - min(edge, 1.0)) * (target - 2)))
    lo = max(0, min(target - 2, lo))
    return (target, lo) if win == 0 else (lo, target)


def _play_set(rng, players, server, fmt, final_tb: bool, target_games: int,
              context: MatchContext, edges, decider: bool = False,
              tune: dict = TUNE):
    """Returns (winner, (g0,g1), next_server, flow).

    `edges` is the pair of per-player shape dicts (`_edges`), computed once per
    match; `decider` marks the match-deciding set, where the stamina gap counts.

    `flow` records what happened, game by game — [server, winner] pairs plus
    tiebreak [first_server, winner] — WITHOUT consuming any extra rng draws, so
    scorelines are bit-identical to the pre-recording model. engine.boxstats
    replays this flow at point level to attach real stats to a fast match."""
    if final_tb:
        p = _tb_prob(players[0], players[1], context, edges[0], edges[1],
                     decider, tune)
        r = rng.random()
        win = 0 if r < p else 1
        flow = {"games": [], "tb": [server, win], "mtb": True}
        return (win, _mtb_score(win, r, p, fmt.final_set_tiebreak_target),
                1 - server, flow)

    games = [0, 0]
    flow_games: list[list[int]] = []
    tg = target_games
    while True:
        r = players[1 - server]
        s = players[server]
        if rng.random() < _hold_prob(s, r, context, edges[server],
                                     edges[1 - server], decider, tune):
            games[server] += 1
            flow_games.append([server, server])
        else:
            games[1 - server] += 1
            flow_games.append([server, 1 - server])
        server = 1 - server

        if fmt.set_tiebreak and games[0] == tg and games[1] == tg:
            win = 0 if rng.random() < _tb_prob(players[0], players[1], context,
                                               edges[0], edges[1], decider,
                                               tune) else 1
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
    profile: dict | None = None,
) -> MatchResult:
    """`profile` overlays TUNE for this match (e.g. `HS_PROFILE`). None — every
    college/cup/pro call — is byte-identical to the pre-profile model: the same
    dials, and no extra rng draw."""
    fmt = fmt or DEFAULT
    context = context or MatchContext()
    rng = random.Random(seed)
    players = (p0, p1)
    sets = [0, 0]
    set_scores: list[tuple[int, int]] = []
    games_won = [0, 0]
    server = first_server

    flows: list[dict] = []

    tune = TUNE if profile is None else {**TUNE, **profile}
    edges = (_edges(p0), _edges(p1))

    if fmt.pro_set:
        win, score, server, flow = _play_set(rng, players, server, fmt, False,
                                             fmt.pro_set_games, context, edges,
                                             tune=tune)
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
            edges, decider=is_final, tune=tune,
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
