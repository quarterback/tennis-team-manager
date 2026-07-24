"""
Full two-on-two DOUBLES engine — a genuine four-player point model.

Singles collapses a point into server-vs-returner; doubles does not. A doubles
point is decided by four players and the geometry between them: the server, the
server's partner poaching at the net, the returner trying to dip the ball at the
incomer's feet, and the returner's partner guarding the other half. This module
models that point for real rather than averaging a pair into one synthetic
singles player (the old `engine.dual._pair_player` trick).

What makes doubles its OWN skill (so a player's doubles level ≠ their singles
level, and specialists surface):

  * serve + placement matter more — a big serve sets up the partner's poach;
  * net play dominates — volleys, reflexes and positioning (`movement`,
    `forehand`, `mental`) win the quick exchanges that decide most points;
  * the return must clear the net man, so `return_game` is pressured by the
    opposing poacher, not just the server;
  * long-rally baseline traits (`backhand`, `stamina`, `consistency`) matter
    less than they do in singles.

Mechanics modelled:
  * service rotation — the four players serve in a fixed order; within a team
    the two partners alternate service games;
  * receiving formation — each player owns one court (deuce / ad) for the match
    and returns every point struck to that court;
  * the point in stages — serve in/ace/double-fault → return (under poach
    pressure) → net exchange (both teams' net presence, plus the serving team's
    serve+1 edge), with clutch swinging the big points on the mental gap.

Scoring (games / sets / tiebreaks / pro set) reuses the SAME `MatchFormat`
rules as singles, so a doubles match serialises and renders like any other.

Determinism: every draw flows through one `random.Random(seed)`; identical
teams + seed reproduce the transcript and scoreline exactly.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional

from .state import Player, PlayerStats, MatchContext
from .format import MatchFormat, DEFAULT
from .rally import (
    _first_serve_in_prob, _second_serve_in_prob, _ace_prob,
    _rally_condition_bonus, _logistic, _clamp01, TUNE as RALLY_TUNE,
)

# Tunables for the doubles point model — talent shifts these distributions, it
# does not script outcomes. Kept in one table so the model retunes without
# touching logic (mirrors `rally.TUNE`).
TUNE = {
    # Aces are rarer than singles (a returner stands in, the net man crowds), so
    # the shared singles ace model (rally._ace_prob — same bases/swing, and it now
    # reads the rich serve/return attributes) is scaled DOWN by this factor. One
    # source of truth for ace calibration; doubles just damps it.
    "ace_scale": 0.60,
    # Return must clear the net man. Most returns come back (high base); the
    # talent term and the poacher's pressure swing it, with an easier-return
    # bump on second serves. Calibrated so ~82% of returns are in play at parity.
    "return_base": 1.5,
    "return_slope": 1.05,
    "poach_pressure": 0.45,
    "second_serve_return": 0.55,
    # A return can be an outright winner past the net man (pass / lob), rare.
    "ret_winner_base": -2.4,
    "ret_winner_slope": 1.0,
    # The net exchange once the return is in play: how hard the net-presence gap
    # bites, and the serving team's structural serve+1 / first-volley edge.
    "net_slope": 1.05,
    "serve_plus": 0.33,
    # Of points the serving team wins at net, how many are the partner's poach.
    "poach_share": 0.40,
    # Volley exchanges end in clean winners more often than baseline rallies.
    # The split flexes with talent (like singles, anchored on rally swing_ref): a
    # bigger weapon / net game finishes more outright, and a steadier losing pair
    # coughs up fewer cheap errors so more points must be earned.
    "winner_share": 0.58,
    "winner_power": 0.30,     # groundstroke weapon of the finisher
    "winner_net": 0.34,       # net game of the finisher
    "winner_steady": 0.30,    # steadier losers gift fewer errors
    # Pressure / clutch on break / set / match points (mental gap).
    "clutch_logit": 1.0,
    "clutch_exp": 1.6,
    # Fast (bulk) model: team-doubles-rating hold curve.
    "fast_hold_logit": 1.05,
    "fast_skill_slope": 2.4,
    "fast_tb_slope": 1.8,
}


# --- Doubles skill ratings -------------------------------------------------
# Each maps a player's talent onto the role they play in a doubles point. These
# read the RICH attributes directly — net_play, volley_touch, poaching, overhead,
# doubles_chemistry are the specifically-doubles attributes that never touch a
# singles point — and fall back to the 9 drivers for synthetic random_player()s
# (which carry no rich table), so existing tests are unchanged. Each basket is
# centered like the driver form it replaces, so the fast-model / seeding
# calibration (fast_skill_slope) is preserved on average while gaining texture.

def _rich(p: Player, weights: dict, fallback: float) -> float:
    r = p.rich
    if not r:
        return fallback
    tot = sum(w for n, w in weights.items() if n in r)
    if tot <= 0:
        return fallback
    return sum(r[n] * w for n, w in weights.items() if n in r) / tot


def serve_rating(p: Player) -> float:
    return _rich(p, {"first_serve_power": 0.40, "first_serve_accuracy": 0.25,
                     "second_serve_quality": 0.20, "serve_variety": 0.15},
                 0.62 * p.serve_power + 0.38 * p.serve_placement)


def return_rating(p: Player) -> float:
    return _rich(p, {"return_quality": 0.35, "return_depth": 0.20,
                     "return_aggression": 0.15, "passing_precision": 0.15,
                     "groundstroke_consistency": 0.15},
                 0.70 * p.return_game + 0.30 * p.consistency)


def net_rating(p: Player) -> float:
    """Volleys, reflexes, positioning — the engine of doubles."""
    return _rich(p, {"net_play": 0.34, "volley_touch": 0.24, "overhead": 0.12,
                     "agility": 0.16, "composure": 0.14},
                 0.45 * p.movement + 0.30 * p.forehand + 0.25 * p.mental)


def poach_rating(p: Player) -> float:
    """Reading the return and crossing to put it away."""
    return _rich(p, {"poaching": 0.38, "speed": 0.20, "agility": 0.15,
                     "court_vision": 0.15, "doubles_chemistry": 0.12},
                 0.55 * p.movement + 0.25 * p.mental + 0.20 * p.serve_placement)


def _net_winner_share(hitter: Player, loser_a: Player, loser_b: Player) -> float:
    """Fraction of net-exchange points the winning side ends with a clean WINNER
    (vs the losing pair's error). Flexes with the finisher's weapon + net game
    and the losers' steadiness — so doubles winner/error totals track talent
    instead of a flat rate, the same way singles do."""
    t = TUNE
    ref = RALLY_TUNE["swing_ref"]
    steady = 0.5 * (loser_a.steadiness + loser_b.steadiness)
    swing = (t["winner_power"] * (hitter.attack - ref)
             + t["winner_net"] * (net_rating(hitter) - ref)
             + t["winner_steady"] * (steady - ref))
    return _clamp01(t["winner_share"] + swing)


def doubles_rating(a: Player, b: Player) -> float:
    """A pair's overall doubles strength in [0, 1] — the seeding / fast-model
    signal. Weighted toward serve and net play, so a serve+volley pair rates
    above its singles level and a pair of baseline grinders below."""
    def idx(p: Player) -> float:
        return (0.30 * serve_rating(p) + 0.40 * net_rating(p)
                + 0.20 * return_rating(p) + 0.10 * poach_rating(p))
    return (idx(a) + idx(b)) / 2.0


@dataclass
class DoublesTeam:
    """Two players a side. `name` defaults to "A / B"."""
    players: tuple[Player, Player]
    name: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = f"{self.players[0].name} / {self.players[1].name}"

    @property
    def rating(self) -> float:
        return doubles_rating(self.players[0], self.players[1])


@dataclass
class DoublesResult:
    teams: tuple[DoublesTeam, DoublesTeam]
    winner: int                          # 0 or 1
    sets: list[int]
    set_scores: list[tuple[int, int]]
    games_won: tuple[int, int]
    # Per-player stats, ordered [t0 p0, t0 p1, t1 p0, t1 p1].
    stats: tuple[PlayerStats, PlayerStats, PlayerStats, PlayerStats]
    pbp: list[str]
    fidelity: str = "full"
    # Per-set game sequence recorded by the FAST model (None at full fidelity):
    # same shape as MatchResult.game_flow, sides 0/1 are the two teams. Lets
    # engine.boxstats replay a fast doubles match at point level for real stats.
    game_flow: list[dict] | None = None

    @property
    def players(self):
        """Alias for `teams` so a DoublesResult duck-types as a singles
        MatchResult (both expose `.players[i].name`) wherever a dual line is
        rendered or persisted uniformly across singles and doubles."""
        return self.teams

    @property
    def winner_name(self) -> str:
        return self.teams[self.winner].name

    @property
    def scoreline(self) -> str:
        """e.g. '6-4 3-6 7-6' from the winning team's perspective."""
        parts = []
        for a, b in self.set_scores:
            hi, lo = (a, b) if self.winner == 0 else (b, a)
            parts.append(f"{hi}-{lo}")
        return " ".join(parts)


@dataclass
class _DState:
    """Live doubles match state — sides are indexed 0/1, like singles, but each
    side fields two players and the per-point identities rotate underneath."""
    teams: tuple[DoublesTeam, DoublesTeam]
    rng: random.Random
    fmt: MatchFormat
    context: MatchContext
    server: int = 0                       # serving SIDE this game
    pressure: float = 0.0
    set_target: int = 6
    sets_needed: int = 2
    is_final_set: bool = False
    points: list[int] = field(default_factory=lambda: [0, 0])
    games: list[int] = field(default_factory=lambda: [0, 0])
    sets: list[int] = field(default_factory=lambda: [0, 0])
    set_scores: list[tuple[int, int]] = field(default_factory=list)
    # serve_order[side] = [p, q]: that side's two partners serve in this order.
    serve_order: list[list[int]] = field(default_factory=lambda: [[0, 1], [0, 1]])
    # recv_order[side] = [deuce_player, ad_player]: who returns each court.
    recv_order: list[list[int]] = field(default_factory=lambda: [[0, 1], [0, 1]])
    srv_count: list[int] = field(default_factory=lambda: [0, 0])  # service games taken
    # Stats keyed (side, slot); flattened to a 4-tuple at the end.
    stats: dict = field(default_factory=lambda: {(s, p): PlayerStats()
                                                 for s in (0, 1) for p in (0, 1)})
    pbp: list[str] = field(default_factory=list)

    @property
    def returner(self) -> int:
        return 1 - self.server

    def log(self, line: str) -> None:
        self.pbp.append(line)


# --- Point resolution ------------------------------------------------------

def _net_presence(state: _DState, side: int, net_slot: int, back_slot: int) -> float:
    """A side's effective net strength on a point: the net partner does most of
    the volleying, the back player covers transition / lobs."""
    net_p = state.teams[side].players[net_slot]
    back_p = state.teams[side].players[back_slot]
    return 0.74 * net_rating(net_p) + 0.26 * (0.6 * back_p.movement + 0.4 * back_p.mental)


def _team_mental(state: _DState, side: int) -> float:
    a, b = state.teams[side].players
    return (a.mental + b.mental) / 2.0


def _clutch(state: _DState) -> float:
    """Signed clutch term; positive favours the serving team. Non-linear in
    pressure, scaled by the team mental gap and crowd comfort."""
    pressure = state.pressure
    if pressure <= 0.0:
        return 0.0
    s, r = state.server, state.returner
    crowd = state.context.crowd * 0.10 * (_team_mental(state, s) - _team_mental(state, r))
    return (pressure ** TUNE["clutch_exp"]) * ((_team_mental(state, s) - _team_mental(state, r)) + crowd)


def _play_point(state: _DState) -> tuple[int, str]:
    """Resolve one doubles point on the serving side. Returns (winning_side,
    kind). Mirrors the four-stage geometry: serve → ace/DF → return-under-poach
    → net exchange."""
    t = TUNE
    s_side, r_side = state.server, state.returner
    court = sum(state.points) % 2                     # 0 deuce, 1 ad

    srv_slot = state.serve_order[s_side][state.srv_count[s_side] % 2]
    snet_slot = 1 - srv_slot                          # server's partner is at net
    ret_slot = state.recv_order[r_side][court]
    rnet_slot = 1 - ret_slot                          # returner's partner is at net

    server = state.teams[s_side].players[srv_slot]
    snet = state.teams[s_side].players[snet_slot]
    returner = state.teams[r_side].players[ret_slot]

    s_stat = state.stats[(s_side, srv_slot)]
    snet_stat = state.stats[(s_side, snet_slot)]
    r_stat = state.stats[(r_side, ret_slot)]

    s_stat.serve_points_total += 1
    r_stat.return_points_total += 1
    clutch = _clutch(state)

    def award(side: int, winner_stat: PlayerStats | None, kind: str,
              error_stat: PlayerStats | None = None, forced: bool = False) -> tuple[int, str]:
        if winner_stat is not None and kind in ("ace", "winner"):
            winner_stat.winners += 1
        if error_stat is not None:
            if forced:
                error_stat.forced_errors += 1
            else:
                error_stat.unforced_errors += 1
        if side == s_side:
            s_stat.serve_points_won += 1
        else:
            r_stat.return_points_won += 1
        # credit the point to every player on the winning side
        for slot in (0, 1):
            state.stats[(side, slot)].points_won += 1
        return side, kind

    rng = state.rng

    # --- Serve: first, then second, then double fault ---
    s_stat.first_serve_points += 1
    if rng.random() < _first_serve_in_prob(state, server):
        s_stat.first_serves_in += 1
        first = True
    else:
        s_stat.second_serve_points += 1
        second_in = _clamp01(_second_serve_in_prob(state, server) + 0.07 * clutch)
        if rng.random() >= second_in:
            s_stat.double_faults += 1
            return award(r_side, None, "double_fault")
        first = False

    # --- Ace / unreturnable serve (rarer in doubles) ---
    # Route through the shared singles ace model (reads rich serve/return
    # attributes), damped for the crowded doubles net.
    ace_p = _clamp01(t["ace_scale"] * _ace_prob(server, returner, first))
    if rng.random() < ace_p:
        s_stat.aces += 1
        return award(s_side, s_stat, "ace")

    # --- Return under poach pressure ---
    return_logit = (t["return_base"]
                    + t["return_slope"] * (return_rating(returner) - serve_rating(server))
                    - t["poach_pressure"] * (poach_rating(snet) - 0.5) * 2.0)
    if not first:
        return_logit += t["second_serve_return"]
    if rng.random() >= _logistic(return_logit):
        # Return missed or floated up — the net man (or server) puts it away.
        # The serve/poach pressure forced it, so it is a FORCED error, not a gift.
        if rng.random() < TUNE["poach_share"]:
            return award(s_side, snet_stat, "winner")     # poach putaway
        return award(s_side, None, "winner", error_stat=r_stat, forced=True)

    # --- Return in play: a chance it's an outright pass / lob winner ---
    ret_win_logit = t["ret_winner_base"] + t["ret_winner_slope"] * (return_rating(returner) - net_rating(snet))
    if rng.random() < _logistic(ret_win_logit):
        return award(r_side, r_stat, "winner")

    # --- Net exchange: both teams' net presence + serving team's serve+1 edge ---
    edge = (t["net_slope"] * (_net_presence(state, s_side, snet_slot, srv_slot)
                              - _net_presence(state, r_side, rnet_slot, ret_slot))
            + t["serve_plus"]
            + t["clutch_logit"] * clutch
            + _rally_condition_bonus(state, server, returner))
    if rng.random() < _logistic(edge):
        win_side, win_slot = s_side, (snet_slot if rng.random() < t["poach_share"] else srv_slot)
        loser = r_side
    else:
        win_side, win_slot = r_side, (rnet_slot if rng.random() < 0.5 else ret_slot)
        loser = s_side
    win_stat = state.stats[(win_side, win_slot)]
    la, lb = state.teams[loser].players
    if rng.random() < _net_winner_share(state.teams[win_side].players[win_slot], la, lb):
        return award(win_side, win_stat, "winner")
    # error by the losing side — the less-steady partner is likelier to have missed
    p_first = _clamp01(0.5 + 0.5 * (lb.steadiness - la.steadiness))
    err_slot = 0 if rng.random() < p_first else 1
    err_stat = state.stats[(loser, err_slot)]
    return award(win_side, None, "winner", error_stat=err_stat)


# --- Game / set / match scoring (same rules as singles) --------------------

def _game_over(state: _DState) -> Optional[int]:
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


def _point_pressure(state: _DState) -> float:
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


def _play_game(state: _DState) -> int:
    state.points = [0, 0]
    s, r = state.server, state.returner
    while True:
        is_bp = state.points[r] >= 3 and state.points[r] > state.points[s]
        if state.fmt.no_ad and state.points[s] == 3 and state.points[r] == 3:
            is_bp = True
        state.pressure = _point_pressure(state)
        # the serving player faces the break point in the stat ledger
        srv_slot = state.serve_order[s][state.srv_count[s] % 2]
        winner, _ = _play_point(state)
        state.points[winner] += 1
        if is_bp:
            state.stats[(s, srv_slot)].break_points_faced += 1
            if winner == s:
                state.stats[(s, srv_slot)].break_points_saved += 1
            else:
                # credit the conversion to the returner who struck the point
                court = (sum(state.points) - 1) % 2
                state.stats[(r, state.recv_order[r][court])].break_points_converted += 1
        over = _game_over(state)
        if over is not None:
            state.srv_count[s] += 1
            return over


def _tb_pressure(pts: list[int], target: int, is_match: bool) -> float:
    hi, lo = max(pts), min(pts)
    if hi >= target - 1 and hi >= lo + 1:
        return 1.0 if is_match else 0.85
    return min(0.6, 0.20 + 0.40 * hi / target)


def _play_tiebreak(state: _DState, target: int = 7) -> int:
    pts = [0, 0]
    first_server = state.server
    served = 0
    is_match_tb = state.is_final_set or (max(state.sets) >= state.sets_needed - 1)
    while True:
        state.points = list(pts)                       # expose to court/pressure calc
        state.pressure = _tb_pressure(pts, target, is_match_tb)
        winner, _ = _play_point(state)
        pts[winner] += 1
        served += 1
        if served == 1 or (served - 1) % 2 == 0:
            # service passes to the other side; that side advances its rotation
            state.srv_count[state.server] += 1
            state.server = 1 - state.server
        if (pts[0] >= target or pts[1] >= target) and abs(pts[0] - pts[1]) >= 2:
            win = 0 if pts[0] > pts[1] else 1
            state._tb_points = (pts[0], pts[1])         # type: ignore[attr-defined]
            state.server = first_server
            return win


def _play_set(state: _DState, is_final: bool,
              target_games: Optional[int] = None) -> tuple[int, tuple[int, int]]:
    fmt = state.fmt
    state.games = [0, 0]
    state.is_final_set = is_final or state.sets_needed == 1
    state.set_target = target_games if target_games is not None else fmt.set_games

    if is_final and fmt.final_set_tiebreak:
        win = _play_tiebreak(state, target=fmt.final_set_tiebreak_target)
        state.server = 1 - state.server
        return win, ((1, 0) if win == 0 else (0, 1))

    tg = target_games if target_games is not None else fmt.set_games
    tb_at = fmt.set_tiebreak_at if fmt.set_tiebreak_at is not None else tg
    while True:
        g_winner = _play_game(state)
        state.games[g_winner] += 1
        state.server = 1 - state.server
        g0, g1 = state.games
        if fmt.set_tiebreak and g0 == tb_at and g1 == tb_at:
            tb_winner = _play_tiebreak(state, target=fmt.set_tiebreak_target)
            state.games[tb_winner] += 1
            state.server = 1 - state.server
            return tb_winner, (state.games[0], state.games[1])
        if g0 >= tg and g0 - g1 >= 2:
            return 0, (g0, g1)
        if g1 >= tg and g1 - g0 >= 2:
            return 1, (g0, g1)


def _seed_orders(state: _DState) -> None:
    """Stronger server serves first; stronger returner takes the ad court (where
    the bigger points are played). Deterministic, no rng."""
    for side in (0, 1):
        a, b = state.teams[side].players
        if serve_rating(b) > serve_rating(a):
            state.serve_order[side] = [1, 0]
        # ad court (index 1) to the better returner
        if return_rating(b) > return_rating(a):
            state.recv_order[side] = [0, 1]   # b (slot 1) on ad
        else:
            state.recv_order[side] = [1, 0]   # a (slot 0) on ad


def _result(state: _DState, teams, fidelity: str,
            game_flow: list[dict] | None = None) -> DoublesResult:
    overall = 0 if state.sets[0] > state.sets[1] else 1
    games = [0, 0]
    for a, b in state.set_scores:
        games[0] += a
        games[1] += b
    stats = (state.stats[(0, 0)], state.stats[(0, 1)],
             state.stats[(1, 0)], state.stats[(1, 1)])
    return DoublesResult(
        teams=teams, winner=overall, sets=list(state.sets),
        set_scores=list(state.set_scores), games_won=(games[0], games[1]),
        stats=stats, pbp=state.pbp, fidelity=fidelity, game_flow=game_flow,
    )


# --- Fast (bulk) model -----------------------------------------------------

def _fast_hold(state: _DState) -> float:
    s, r = state.server, state.returner
    gap = state.teams[s].rating - state.teams[r].rating
    return _logistic(TUNE["fast_hold_logit"] + TUNE["fast_skill_slope"] * gap)


def _fast_tb(state: _DState, s0: int = 0) -> int:
    gap = state.teams[0].rating - state.teams[1].rating
    return 0 if state.rng.random() < _logistic(TUNE["fast_tb_slope"] * gap) else 1


def _simulate_fast(state: _DState) -> DoublesResult:
    fmt = state.fmt
    rng = state.rng
    flows: list[dict] = []

    def play_set(target_games: int, final_tb: bool) -> tuple[int, tuple[int, int]]:
        # Records the game-by-game flow ([server, winner] pairs + tiebreak
        # [first_server, winner]) without extra rng draws — same contract as
        # engine.fast._play_set, consumed by engine.boxstats.
        if final_tb:
            win = _fast_tb(state)
            flows.append({"games": [], "tb": [state.server, win], "mtb": True})
            return win, ((1, 0) if win == 0 else (0, 1))
        games = [0, 0]
        flow_games: list[list[int]] = []
        while True:
            srv = state.server
            if rng.random() < _fast_hold(state):
                games[state.server] += 1
                flow_games.append([srv, srv])
            else:
                games[state.returner] += 1
                flow_games.append([srv, 1 - srv])
            state.server = 1 - state.server
            if fmt.set_tiebreak and games[0] == target_games and games[1] == target_games:
                win = _fast_tb(state)
                games[win] += 1
                flows.append({"games": flow_games, "tb": [state.server, win], "mtb": False})
                return win, (games[0], games[1])
            if games[0] >= target_games and games[0] - games[1] >= 2:
                flows.append({"games": flow_games, "tb": None, "mtb": False})
                return 0, (games[0], games[1])
            if games[1] >= target_games and games[1] - games[0] >= 2:
                flows.append({"games": flow_games, "tb": None, "mtb": False})
                return 1, (games[0], games[1])

    if fmt.pro_set:
        win, score = play_set(fmt.pro_set_games, False)
        state.sets[win] += 1
        state.set_scores.append(score)
        return _result(state, state.teams, "fast", game_flow=flows)

    while max(state.sets) < state.sets_needed:
        is_final = (state.sets[0] == state.sets_needed - 1
                    and state.sets[1] == state.sets_needed - 1)
        win, score = play_set(fmt.set_games, is_final and fmt.final_set_tiebreak)
        state.sets[win] += 1
        state.set_scores.append(score)
    return _result(state, state.teams, "fast", game_flow=flows)


# --- Public entry point ----------------------------------------------------

def simulate_doubles(
    team0: DoublesTeam | tuple[Player, Player],
    team1: DoublesTeam | tuple[Player, Player],
    *,
    seed: int,
    fmt: Optional[MatchFormat] = None,
    first_server: int = 0,
    fidelity: str = "full",
    context: Optional[MatchContext] = None,
) -> DoublesResult:
    """Simulate a doubles match between two pairs.

    Pass `DoublesTeam`s or bare `(Player, Player)` tuples. `fidelity="fast"`
    routes to the team-rating hold model (scoreline only) for bulk simulation;
    `"full"` plays every point through the four-player model with stats + PBP.
    """
    fmt = fmt or DEFAULT
    context = context or MatchContext()
    t0 = team0 if isinstance(team0, DoublesTeam) else DoublesTeam(players=tuple(team0))
    t1 = team1 if isinstance(team1, DoublesTeam) else DoublesTeam(players=tuple(team1))
    state = _DState(teams=(t0, t1), rng=random.Random(seed), fmt=fmt,
                    context=context, server=first_server)
    state.sets_needed = 1 if fmt.pro_set else fmt.best_of // 2 + 1

    if fidelity == "fast":
        return _simulate_fast(state)

    _seed_orders(state)
    if fmt.pro_set:
        win, score = _play_set(state, is_final=False, target_games=fmt.pro_set_games)
        state.sets[win] += 1
        state.set_scores.append(score)
        state.log(f"Pro set: {score[0]}-{score[1]}")
    else:
        while max(state.sets) < state.sets_needed:
            is_final = (state.sets[0] == state.sets_needed - 1
                        and state.sets[1] == state.sets_needed - 1)
            win, score = _play_set(state, is_final)
            state.sets[win] += 1
            state.set_scores.append(score)
            state.log(f"Set {len(state.set_scores)}: {score[0]}-{score[1]}")
    return _result(state, state.teams, "full")
