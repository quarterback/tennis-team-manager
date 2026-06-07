"""Per-nation tennis talent-generation metrics (static JSON store).

Ported from o27 baseball's nation_talent model, trimmed to the static read
path the tennis sim needs (no live season-to-season drift / DB store). Two
0-100 ratings per nation drive how players from that nation generate:

  investment  -> the ELITE SPIKE: chance a generated player is a blue-chip.
  grassroots  -> the AVERAGE LIFT: a talent-grade shift applied to every
                 player from that nation.

Nations absent from ``data/names/nation_talent.json`` default to a neutral
50/50 -- tour-average with full variance -- which is exactly the
"talent can still emerge anywhere" floor the world model wants: a small
non-major nation still rolls the occasional gem.

Public API
----------
  ratings(cc) -> (investment, grassroots)
  all_ratings() -> {cc: (investment, grassroots)}
  elite_probability(cc) -> float
  talent_shift(cc) -> int          # additive grade shift, 0 for neutral
  roll_elite(cc, rng) -> bool
  describe(cc) -> dict             # display bundle for a nation
  ELITE_HEADLINE / ELITE_SUPPORT  # grade bands used when an elite roll hits
"""
from __future__ import annotations

import json
import os

_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "names", "nation_talent.json")

NEUTRAL = 50

# Elite spike: probability a generated player is a blue-chip, as a function
# of the (investment-weighted) talent index. 1/1000 floor, 1/100 ceiling.
ELITE_MIN_P = 0.001     # 1 in 1000 — the weakest programmes
ELITE_MAX_P = 0.010     # 1 in 100  — never higher, by design

# Average lift: a talent-grade shift of (index-50) * LIFT_K, clamped to ±LIFT_CAP.
LIFT_K   = 0.16         # ≈ ±8 grade points across the 0-100 range
LIFT_CAP = 8

# When the elite roll hits, marquee grades are floored into these bands so the
# player reads as genuinely blue-chip at seed time. The seed ceiling is still
# the normal grade max; Elite+ growth stays earned via development.
ELITE_HEADLINE = (74, 80)   # primary ceiling band
ELITE_SUPPORT  = (68, 80)   # supporting ceiling band

_cache: dict[str, tuple[int, int]] | None = None


def _load() -> dict[str, tuple[int, int]]:
    global _cache
    if _cache is None:
        try:
            with open(_DATA_PATH, encoding="utf-8") as fh:
                raw = json.load(fh).get("ratings", {}) or {}
        except (OSError, ValueError):
            raw = {}
        out: dict[str, tuple[int, int]] = {}
        for cc, row in raw.items():
            out[cc.upper()] = (int(row.get("investment", NEUTRAL)),
                               int(row.get("grassroots", NEUTRAL)))
        _cache = out
    return _cache


def reset_cache() -> None:
    """Drop the cached ratings (call after editing the JSON)."""
    global _cache
    _cache = None


def ratings(country_code: str) -> tuple[int, int]:
    """(investment, grassroots) for a country, defaulting to neutral 50/50."""
    return _load().get((country_code or "").upper(), (NEUTRAL, NEUTRAL))


def all_ratings() -> dict[str, tuple[int, int]]:
    """Ratings for every nation currently on record."""
    return dict(_load())


def _elite_index(country_code: str) -> float:
    inv, grass = ratings(country_code)
    return 0.7 * inv + 0.3 * grass


def _lift_index(country_code: str) -> float:
    inv, grass = ratings(country_code)
    return 0.4 * inv + 0.6 * grass


def elite_probability(country_code: str) -> float:
    """Chance a single generated player from this nation is a blue-chip."""
    idx = _elite_index(country_code)
    p = ELITE_MIN_P + (idx / 100.0) * (ELITE_MAX_P - ELITE_MIN_P)
    return max(ELITE_MIN_P, min(ELITE_MAX_P, p))


def talent_shift(country_code: str) -> int:
    """Additive talent-grade shift applied to a nation's players. 0 for a
    neutral (50/50) nation, so non-major markets are never penalised."""
    shift = round((_lift_index(country_code) - NEUTRAL) * LIFT_K)
    return max(-LIFT_CAP, min(LIFT_CAP, shift))


def roll_elite(country_code: str, rng) -> bool:
    """True if a freshly generated player from this nation rolls blue-chip."""
    return rng.random() < elite_probability(country_code)


def describe(country_code: str) -> dict:
    """Display bundle for a nation: ratings + derived generation effects."""
    inv, grass = ratings(country_code)
    p = elite_probability(country_code)
    return {
        "country_code": (country_code or "").upper(),
        "investment":   inv,
        "grassroots":   grass,
        "elite_one_in": int(round(1.0 / p)) if p > 0 else 0,
        "talent_shift": talent_shift(country_code),
    }
