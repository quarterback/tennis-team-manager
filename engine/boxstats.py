"""
Box-stat overlay — engine-faithful stats for fast-fidelity matches.

The problem this solves: college season play simulates duals with the FAST
game-level model (deliberately — its flat, upset-prone calibration is a tuned
design decision, see `fast.TUNE`), but the fast model produces no per-player
stats, so nothing like aces / double faults / winners ever existed for season
matches. Simply switching the season to the full point engine would rewrite
competitive balance (the full engine is far chalkier: at a 0.10 `overall` gap
the favorite wins ~82% of full-engine matches vs ~64% fast — measured, not
guessed), so the fast model must STAY authoritative for outcomes.

The overlay keeps both truths at once:

  1. The fast model decides every game/tiebreak exactly as before (its rng
     draw sequence is untouched) and now records WHAT happened as a
     `game_flow` — [server, winner] per game plus tiebreak [first_server,
     winner] per set.
  2. This module replays each recorded game through the REAL point engine
     (`match.play_game` / `doubles._play_game` — the same rally/serve tables,
     pressure model and all), CONDITIONED on the recorded winner by rejection
     sampling: resimulate the game until the required side wins, keep that
     attempt's stats, discard the rest.

The result: per-player stats drawn from the true engine distributions,
*exactly consistent with the persisted scoreline* (every hold, break and
tiebreak matches), deterministic given the seed, with the scoreline itself
bit-identical to what the fast model always produced.

Conditioning caveat: a game whose recorded outcome is extremely unlikely under
the point model (a break at an enormous talent gap) can exhaust `MAX_TRIES`;
the last attempt is kept, so in that vanishing case one game's stats may
disagree with the score. At realistic roster gaps the expected retry count per
game is ~1-4.

Determinism: all replay draws flow through one `random.Random(seed)` per
match, seeded independently of the outcome rng (see `stat_seed`).
"""
from __future__ import annotations

import random

from . import doubles as _dbl
from . import match as _match
from .format import MatchFormat
from .state import MatchContext, MatchState, PlayerStats

# Retry budget per conditioned game. Common case succeeds in 1-4 tries; the
# budget only matters for near-impossible recorded outcomes (see module doc).
MAX_TRIES = 2000

_SEED_SALT = 0x0B057A75  # decorrelates the stat-replay rng from the outcome rng


def stat_seed(seed: int, offset: int = 0) -> int:
    """Derive the overlay's rng seed from a match's outcome seed."""
    return ((seed + offset) ^ _SEED_SALT) & 0x7FFFFFFF


def overlay(result, *, seed: int, fmt: MatchFormat, context: MatchContext | None = None):
    """Attach point-engine stats to a fast-fidelity result, in place.

    No-op when the result carries no `game_flow` (full fidelity — stats are
    already real — or a legacy result). Returns `result` for chaining.
    `context` should be the same match conditions the outcome sim ran under.
    """
    flow = getattr(result, "game_flow", None)
    if not flow:
        return result
    context = context or MatchContext()
    if hasattr(result, "teams"):
        return _overlay_doubles(result, seed, fmt, context)
    return _overlay_singles(result, seed, fmt, context)


def _merge(dst, src) -> None:
    dst.add(src)


def _set_context(state, fmt: MatchFormat, set_flow: dict) -> None:
    """Point the live state at the next set, mirroring the bookkeeping the real
    play_set/simulate_match loop does (pressure model reads these)."""
    state.games = [0, 0]
    state.set_target = fmt.pro_set_games if fmt.pro_set else fmt.set_games
    at_decider = (state.sets[0] == state.sets_needed - 1
                  and state.sets[1] == state.sets_needed - 1)
    state.is_final_set = bool(set_flow.get("mtb")) or at_decider or state.sets_needed == 1


# --- Singles ----------------------------------------------------------------

def _conditioned_game(state: MatchState, server: int, want: int, play) -> None:
    """Replay one game/tiebreak until `want` wins it (rejection sampling),
    then fold the winning attempt's stats into the match totals."""
    totals = state.stats
    trial = (PlayerStats(), PlayerStats())
    for _ in range(MAX_TRIES):
        trial = (PlayerStats(), PlayerStats())
        state.stats = trial
        state.server = server
        if play() == want:
            break
    state.stats = totals
    _merge(totals[0], trial[0])
    _merge(totals[1], trial[1])


def _overlay_singles(result, seed: int, fmt: MatchFormat, context: MatchContext):
    p0, p1 = result.players
    state = MatchState(players=(p0, p1), rng=random.Random(stat_seed(seed)), fmt=fmt,
                       context=context)
    state.sets_needed = 1 if fmt.pro_set else fmt.best_of // 2 + 1

    for set_flow in result.game_flow:
        _set_context(state, fmt, set_flow)
        if set_flow.get("mtb"):
            first_server, win = set_flow["tb"]
            _conditioned_game(
                state, first_server, win,
                lambda: _match.play_tiebreak(state, target=fmt.final_set_tiebreak_target))
            state.sets[win] += 1
            continue
        for srv, gwin in set_flow["games"]:
            _conditioned_game(state, srv, gwin, lambda: _match.play_game(state))
            state.games[gwin] += 1
        tb = set_flow.get("tb")
        if tb:
            first_server, win = tb
            _conditioned_game(
                state, first_server, win,
                lambda: _match.play_tiebreak(state, target=fmt.set_tiebreak_target))
            state.games[win] += 1
            set_winner = win
        else:
            set_winner = 0 if state.games[0] > state.games[1] else 1
        state.sets[set_winner] += 1

    result.stats = state.stats
    return result


# --- Doubles ----------------------------------------------------------------

def _fresh_dstats() -> dict:
    return {(s, p): PlayerStats() for s in (0, 1) for p in (0, 1)}


def _conditioned_dgame(state: "_dbl._DState", server: int, want: int, play) -> None:
    """Doubles twin of `_conditioned_game`: also restores the serve-rotation
    counters each rejected attempt (the point model advances them), keeping the
    rotation of the winning attempt so partners alternate correctly."""
    totals = state.stats
    base_srv = list(state.srv_count)
    trial = _fresh_dstats()
    for _ in range(MAX_TRIES):
        trial = _fresh_dstats()
        state.stats = trial
        state.srv_count = list(base_srv)
        state.server = server
        if play() == want:
            break
    state.stats = totals
    for key, stat in totals.items():
        _merge(stat, trial[key])


def _overlay_doubles(result, seed: int, fmt: MatchFormat, context: MatchContext):
    state = _dbl._DState(teams=result.teams, rng=random.Random(stat_seed(seed)), fmt=fmt,
                         context=context)
    state.sets_needed = 1 if fmt.pro_set else fmt.best_of // 2 + 1
    _dbl._seed_orders(state)

    for set_flow in result.game_flow:
        _set_context(state, fmt, set_flow)
        if set_flow.get("mtb"):
            first_server, win = set_flow["tb"]
            _conditioned_dgame(
                state, first_server, win,
                lambda: _dbl._play_tiebreak(state, target=fmt.final_set_tiebreak_target))
            state.sets[win] += 1
            continue
        for srv, gwin in set_flow["games"]:
            _conditioned_dgame(state, srv, gwin, lambda: _dbl._play_game(state))
            state.games[gwin] += 1
        tb = set_flow.get("tb")
        if tb:
            first_server, win = tb
            _conditioned_dgame(
                state, first_server, win,
                lambda: _dbl._play_tiebreak(state, target=fmt.set_tiebreak_target))
            state.games[win] += 1
            set_winner = win
        else:
            set_winner = 0 if state.games[0] > state.games[1] else 1
        state.sets[set_winner] += 1

    result.stats = (state.stats[(0, 0)], state.stats[(0, 1)],
                    state.stats[(1, 0)], state.stats[(1, 1)])
    return result
