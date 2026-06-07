"""
Match state + player model for the tennis engine.

Determinism contract (mirrors O27's `o27/engine`): every random draw in a
match flows through the single `random.Random` stored on `MatchState.rng`,
so seeding once produces a fully reproducible transcript + scoreline.

Player attributes are floats in [0, 1] — "talent shifts the distribution"
(the same idiom as `o27/engine/prob.py`): higher ratings move the serve /
rally probability tables in the player's favour, they don't hard-script
outcomes.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

# Ordered attribute list — the surface area the rally tables read from.
ATTRS = (
    "serve_power",      # ace / unreturnable-serve pressure
    "serve_placement",  # first-serve-in % and double-fault avoidance
    "return_game",      # neutralising the opponent's serve
    "forehand",         # rally weapon
    "backhand",         # rally weapon / liability
    "movement",         # defence, turning defence into neutral
    "stamina",          # holding level deep in matches (hook; used by fatigue)
    "mental",           # clutch — break / set / match points
    "consistency",      # unforced-error suppression
)


@dataclass
class Player:
    name: str
    country: str = ""
    serve_power: float = 0.5
    serve_placement: float = 0.5
    return_game: float = 0.5
    forehand: float = 0.5
    backhand: float = 0.5
    movement: float = 0.5
    stamina: float = 0.5
    mental: float = 0.5
    consistency: float = 0.5

    @property
    def serve_skill(self) -> float:
        return 0.5 * self.serve_power + 0.5 * self.serve_placement

    @property
    def rally_skill(self) -> float:
        return (self.forehand + self.backhand + self.movement + self.consistency) / 4.0

    @property
    def overall(self) -> float:
        return sum(getattr(self, a) for a in ATTRS) / len(ATTRS)


def random_player(
    rng: random.Random,
    name: str,
    country: str = "",
    *,
    base: float = 0.5,
    spread: float = 0.18,
) -> Player:
    """Generate a player whose attributes cluster around `base` with a
    per-attribute Gaussian spread, clamped to [0.05, 0.95]. `base` lets a
    caller skew a whole tier / roster up or down."""
    def draw() -> float:
        v = rng.gauss(base, spread)
        return max(0.05, min(0.95, v))

    return Player(name=name, country=country, **{a: draw() for a in ATTRS})


# ---------------------------------------------------------------------------
# Per-player accumulated stats
# ---------------------------------------------------------------------------

@dataclass
class PlayerStats:
    # Serving
    first_serves_in: int = 0
    first_serve_points: int = 0      # first-serve attempts (points where this player served)
    second_serve_points: int = 0
    aces: int = 0
    double_faults: int = 0
    serve_points_won: int = 0
    serve_points_total: int = 0
    # Returning
    return_points_won: int = 0
    return_points_total: int = 0
    # Break points (as the server facing them)
    break_points_faced: int = 0
    break_points_saved: int = 0
    # Break points (as the returner)
    break_points_converted: int = 0
    # Rally shape
    winners: int = 0
    unforced_errors: int = 0
    # Totals
    points_won: int = 0

    @property
    def first_serve_pct(self) -> float:
        return self.first_serves_in / self.first_serve_points if self.first_serve_points else 0.0

    @property
    def serve_points_won_pct(self) -> float:
        return self.serve_points_won / self.serve_points_total if self.serve_points_total else 0.0


@dataclass
class MatchState:
    players: tuple[Player, Player]
    rng: random.Random
    fmt: "object" = None              # engine.format.MatchFormat (rule toggles)

    # live score
    server: int = 0                   # index of current server
    points: list[int] = field(default_factory=lambda: [0, 0])    # within current game
    games: list[int] = field(default_factory=lambda: [0, 0])     # within current set
    sets: list[int] = field(default_factory=lambda: [0, 0])      # sets won
    set_scores: list[tuple[int, int]] = field(default_factory=list)

    stats: tuple[PlayerStats, PlayerStats] = field(
        default_factory=lambda: (PlayerStats(), PlayerStats())
    )
    pbp: list[str] = field(default_factory=list)

    @property
    def returner(self) -> int:
        return 1 - self.server

    def log(self, line: str) -> None:
        self.pbp.append(line)
