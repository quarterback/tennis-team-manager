"""
STR rating engine — the results-based, recency-weighted rating.

This is the "real" STR: not a readout of a player's hidden ability, but a number
computed from what they've actually done on court. Its behavior (per the user
spec + calibration brief):

  • Opponent-relative: each match yields a *match rating* anchored on the
    opponent's STR. Win/lose decisively shifts you above/below them.
  • Credit for competing well against good players, and a real boost for
    BEATING better players (you can rise on a strong loss; you rise a lot on an
    upset win).
  • "What have you done for me lately, Eddie?" — recent matches are weighted far
    more than old ones (exponential recency decay over a rolling window), so an
    inactive or slumping player's STR DECAYS and can go DOWN even though their
    underlying ability never regresses.
  • Reliability grows with (effective) match count; thin records blend toward a
    prior (e.g. the ability-derived seed) so a 2-match STR isn't taken at face.

STR depends on opponents' STRs, so a full corpus is solved by `converge_ids()`
(iterate to a fixed point). UTR-style. STR is shown on a distinctive 31–57 band.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# STR is on this game's distinctive 31–57 band (not raw UTR 1–17). The
# calibration is UTR-native (1.0-pt logistic, ±2.00 exclusion); 1.0 UTR pt ≈ 1.68
# STR, so the UTR constants below are scaled into STR units.
STR_MIN, STR_MAX = 31.0, 57.0
_STR_PER_UTR = (STR_MAX - STR_MIN) / 15.5          # ≈ 1.677
DEFAULT_STR = 44.0                                 # mid-band prior
SLOPE = 0.62 / _STR_PER_UTR                        # games-share logistic, per STR point
WINDOW = 30            # only the last ~30 matches count (UTR's rolling window)
HALF_LIFE = 12.0       # matches; weight halves every ~12 matches back ("lately")
RELIABILITY_K = 6.0    # ~5 matches ⇒ reliable (UTR's own benchmark)
MAX_DIFF = 2.0 * _STR_PER_UTR                      # ±2.00 UTR exclusion, in STR units (≈3.35)


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def expected_games_share(my_str: float, opp_str: float) -> float:
    """Expected share of games you take vs an opponent (logistic in STR diff)."""
    return 1.0 / (1.0 + math.exp(-SLOPE * (my_str - opp_str)))


def match_rating(opp_str: float, games_won: int, games_lost: int) -> float:
    """The STR this performance implies: invert the games-share curve. Anchored
    on the opponent — take more games than expected vs a strong opponent and you
    rate well above them; get bageled by a weak one and you rate below."""
    total = games_won + games_lost
    if total <= 0:
        return opp_str
    share = _clamp(games_won / total, 0.05, 0.95)
    return _clamp(opp_str + math.log(share / (1 - share)) / SLOPE, STR_MIN, STR_MAX)


@dataclass
class Match:
    opp_str: float
    games_won: int
    games_lost: int
    opp_reliability: float = 1.0   # results vs a thinly-rated opponent count less
    # order is recency: matches are passed oldest → newest


def player_str(matches: list[Match], prior: float | None = None) -> tuple[float, float]:
    """Return (STR, reliability) from a player's matches (oldest → newest).

    Only the last WINDOW matches count; each is recency-decayed and weighted by
    the opponent's rating reliability. Thin records blend toward `prior`."""
    if not matches:
        return (_clamp(prior, STR_MIN, STR_MAX) if prior is not None else DEFAULT_STR), 0.0
    window = matches[-WINDOW:]
    n = len(window)
    wsum = rsum = 0.0
    for i, m in enumerate(window):
        age = (n - 1) - i                       # newest → age 0
        w = (0.5 ** (age / HALF_LIFE)) * (0.4 + 0.6 * m.opp_reliability)
        wsum += w
        rsum += w * match_rating(m.opp_str, m.games_won, m.games_lost)
    if wsum <= 0:
        return (_clamp(prior, STR_MIN, STR_MAX) if prior is not None else DEFAULT_STR), 0.0
    raw = rsum / wsum
    reliability = min(1.0, wsum / RELIABILITY_K)
    if prior is not None:
        raw = reliability * raw + (1 - reliability) * prior
    return _clamp(raw, STR_MIN, STR_MAX), reliability


def converge_ids(matches_by_player: dict[str, list[tuple[str, int, int]]],
                 priors: dict[str, float] | None = None,
                 iterations: int = 8,
                 max_diff: float = MAX_DIFF) -> dict[str, tuple[float, float]]:
    """Solve a whole population's STR to a fixed point (UTR-style).

    matches_by_player: player id → list of (opponent_id, games_won, games_lost),
    oldest → newest. Each pass resolves opponents' STR + reliability from the
    previous pass; matches with a current STR gap > `max_diff` are excluded,
    and each result is weighted by the opponent's reliability. Returns
    id → (STR, reliability).

    `max_diff` defaults to UTR's 2.00 blowout-gap rule, which assumes a large
    population where close-rated opponents exist (college). A small closed pool
    — e.g. a pro league whose best player out-rates everyone by more than the
    gap — passes a wider window so outliers' results still count."""
    priors = priors or {}
    cur = {pid: (_clamp(priors.get(pid, DEFAULT_STR), STR_MIN, STR_MAX), 0.0) for pid in matches_by_player}
    for _ in range(iterations):
        nxt: dict[str, tuple[float, float]] = {}
        for pid, ms in matches_by_player.items():
            my = cur[pid][0]
            resolved = []
            for (opp, gw, gl) in ms:
                opp_str, opp_rel = cur.get(opp, (DEFAULT_STR, 0.0))
                if abs(my - opp_str) > max_diff:      # blowout-gap matches don't count
                    continue
                resolved.append(Match(opp_str, gw, gl, opp_reliability=opp_rel))
            nxt[pid] = player_str(resolved, prior=priors.get(pid))
        cur = nxt
    return cur

