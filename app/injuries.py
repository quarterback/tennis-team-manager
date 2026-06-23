"""
Injuries — dice rolls on talent AND a lever that forces teams to use their depth.

DESIGN (per the owner, 2026-06): this is the ONE deliberately non-deterministic
corner of the engine. Everywhere else is seed-deterministic; injuries roll on real
entropy so the same save replays differently. "Save scumming is perfectly
acceptable" — the player is the only player, and the randomness is the point.

What an injury does:
  • A player who's hurt is filtered out of the lineup for that dual, so the coach
    has to pull up the next body — the bench/walk-on depth finally matters.
  • It's a tax on talent: your ace can sit, and a thin roster feels it.

Calibration targets (owner's spec):
  • Roll PER DUAL, for the players who actually competed that dual.
  • ~0.5 starters hurt at any given time (prevalence ≈ rate × mean-duration).
  • Injuries are COMMON but short: out for 1–6 of the team's duals.
  • 1-in-100 injuries are SEASON-ENDING — those players need a 5th-year
    "medical redshirt" to come back (handled at rollover, not here).

Prevalence math (why the numbers below): a starter draws ~`BASE_RATE` per dual;
a non-season-ending injury sits a player a uniform 1–6 duals (mean 3.5). Steady
state prevalence per starter ≈ BASE_RATE × 3.5. With BASE_RATE ≈ 0.025 that's
~0.0875, and across 6 starters ≈ 0.52 hurt at any time — the target.

Durability shifts the per-player rate a little around the base (tough, well-
conditioned players break less; high-effort grinders a touch more), but the
swing is intentionally narrow so even an iron man isn't immune.

This module owns ONLY the dice. Persistence of who's hurt and for how long lives
in the save (seasonmode's SQLite), because rosters are globally cached Prospects
shared across saves — injury state must never ride on the Prospect object.
"""
from __future__ import annotations

import random

# ---- calibration knobs -----------------------------------------------------
BASE_RATE = 0.025          # per-dual injury chance for an average-durability starter
DURABILITY_SWING = 0.6     # how much durability tilts the rate (±, around 1.0×)
SEASON_ENDING_SHARE = 0.01 # 1-in-100 injuries end the season (medical-redshirt path)
MIN_DUALS_OUT = 1          # shortest non-season-ending absence
MAX_DUALS_OUT = 6          # longest non-season-ending absence
SEASON_ENDING = -1         # sentinel return value from roll_injury
RETURN_GRACE_DUALS = 3     # after returning, a player is eased back in and can't be
                           # re-injured for this many of their team's duals — the
                           # model is injury-AWARE, so no instant re-injury chains

# A toggle so the deterministic bulk paths / tests can switch the dice off, and a
# swappable RNG so a test can pin a seed. By default we draw on real entropy.
_enabled = True
_rng: random.Random = random.SystemRandom()


def set_enabled(on: bool) -> None:
    """Globally enable/disable injury rolls (off => roll_injury always returns 0)."""
    global _enabled
    _enabled = bool(on)


def is_enabled() -> bool:
    return _enabled


def seed_for_testing(seed) -> None:
    """Pin the RNG to a deterministic stream (tests only). Pass None to restore
    real-entropy SystemRandom."""
    global _rng
    _rng = random.Random(seed) if seed is not None else random.SystemRandom()


def durability(prospect) -> float:
    """A 0..1 toughness index from a player's physical conditioning. Stamina,
    recovery, strength and flexibility keep you whole; a grinder's edge (very high
    competitiveness) costs a sliver back via overuse. Never feeds the match engine
    — only the injury rate."""
    def g(attr: str) -> float:
        try:
            return (prospect.current_grade(attr) - 20) / 60.0   # GRADE_MIN..MAX -> 0..1
        except Exception:
            return 0.5
    base = (g("stamina") + g("recovery") + g("strength") + g("flexibility")) / 4.0
    overuse = max(0.0, g("competitiveness") - 0.5) * 0.10       # grinders push through, break more
    return max(0.0, min(1.0, base - overuse))


def injury_rate(prospect) -> float:
    """Per-dual injury probability for this player. BASE_RATE scaled by durability:
    a max-durability player sits near BASE_RATE × (1 − SWING/2); a fragile one near
    × (1 + SWING/2). The swing is deliberately narrow — nobody is immune."""
    d = durability(prospect)
    return BASE_RATE * (1.0 + DURABILITY_SWING * (0.5 - d))


def roll_injury(prospect) -> int:
    """Roll once (one dual) for one player who competed.

    Returns:
      0                 — healthy, no injury this dual,
      1..MAX_DUALS_OUT  — out for that many of the team's upcoming duals,
      SEASON_ENDING(-1) — season-ending (needs a medical redshirt to return).
    """
    if not _enabled:
        return 0
    if _rng.random() >= injury_rate(prospect):
        return 0
    if _rng.random() < SEASON_ENDING_SHARE:
        return SEASON_ENDING
    return _rng.randint(MIN_DUALS_OUT, MAX_DUALS_OUT)
