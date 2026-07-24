"""
Match state + player model for the tennis engine.

Determinism contract (mirrors O27's `o27/engine`): every random draw in a
match flows through the single `random.Random` stored on `MatchState.rng`,
so seeding once produces a fully reproducible transcript + scoreline.

Player attributes are floats in [0, 1]. The engine-facing model intentionally
stays compact: rich career/recruiting attributes are translated into these
small drivers before the point engine sees a player.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, fields

# Ordered attribute list - the stable surface area the rally tables read from.
ATTRS = (
    "serve_power",      # ace / unreturnable-serve pressure
    "serve_placement",  # first-serve-in % and double-fault avoidance
    "return_game",      # neutralising the opponent's serve
    "forehand",         # rally weapon
    "backhand",         # rally weapon / liability
    "movement",         # defence, turning defence into neutral
    "stamina",          # holding level deep in matches
    "mental",           # clutch - break / set / match points
    "consistency",      # unforced-error suppression
)

CONDITION_ATTRS = (
    "indoor_comfort", "outdoor_comfort", "wind_tolerance",
    "heat_tolerance", "crowd_pressure",
)


@dataclass
class MatchContext:
    """Hardcourt match conditions.

    There are no clay/grass surfaces in this model. Context only describes the
    hardcourt environment; the default is neutral outdoor tennis so old calls to
    simulate_match/simulate_dual keep behaving nearly the same.
    """
    indoor: bool = False
    wind: float = 0.0      # 0 calm, 1 heavy wind
    heat: float = 0.0      # 0 mild, 1 oppressive heat
    crowd: float = 0.0     # 0 quiet, 1 hostile/loud

    @property
    def outdoor(self) -> bool:
        return not self.indoor


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
    indoor_comfort: float = 0.5
    outdoor_comfort: float = 0.5
    wind_tolerance: float = 0.5
    heat_tolerance: float = 0.5
    crowd_pressure: float = 0.5
    # The full 49 rich attributes as [0, 1] units (app.player_attributes.RICH_ATTRS
    # → grade_to_unit). Present for real roster players (Prospect.engine_player);
    # None for synthetic random_player()s, which fall back to the 9 drivers. The
    # point engine reads these directly so each stat carries a specific, textured
    # talent signal instead of a collapsed driver average.
    rich: dict | None = None

    @property
    def serve_skill(self) -> float:
        return 0.5 * self.serve_power + 0.5 * self.serve_placement

    @property
    def rally_skill(self) -> float:
        return (self.forehand + self.backhand + self.movement + self.consistency) / 4.0

    @property
    def overall(self) -> float:
        return sum(getattr(self, a) for a in ATTRS) / len(ATTRS)

    # --- rich-attribute role baskets (fall back to drivers when rich is absent) --
    # Each engine stat reads the specific attributes that produce it. When `rich`
    # is None the basket collapses to the matching driver, so synthetic players
    # behave exactly as before.
    def _basket(self, names: tuple[str, ...], fallback: float) -> float:
        r = self.rich
        if not r:
            return fallback
        vals = [r[n] for n in names if n in r]
        return sum(vals) / len(vals) if vals else fallback

    @property
    def ace_power_first(self) -> float:
        """Unreturnable first-serve pop + placement variety."""
        return self._basket(("first_serve_power", "serve_variety"), self.serve_power)

    @property
    def ace_power_second(self) -> float:
        return self._basket(("second_serve_quality", "serve_variety"), self.serve_power)

    @property
    def return_solidity(self) -> float:
        """How reliably the returner gets the serve back (offsets aces)."""
        return self._basket(("return_quality", "return_depth"), self.return_game)

    @property
    def first_serve_in_skill(self) -> float:
        return self._basket(("first_serve_accuracy",), self.serve_placement)

    @property
    def second_serve_in_skill(self) -> float:
        """Second-serve placement — a dumped second serve is a double fault."""
        return self._basket(("second_serve_quality", "serve_variety"), self.serve_placement)

    @property
    def serve_composure(self) -> float:
        """Nerve holding the second serve together under normal play."""
        return self._basket(("composure", "focus"), self.mental)

    @property
    def attack(self) -> float:
        """Weapons that finish points: groundstroke pop, passing, approach, vision."""
        return self._basket(
            ("forehand_power", "backhand_power", "passing_precision",
             "approach_shot", "court_vision"),
            0.5 * (self.forehand + self.backhand))

    @property
    def steadiness(self) -> float:
        """Error suppression: consistency, tolerance, discipline, patience."""
        return self._basket(
            ("groundstroke_consistency", "shot_tolerance", "discipline", "rally_patience"),
            self.consistency)

    @property
    def court_cover(self) -> float:
        """Getting to the ball — turns would-be errors back into rallies."""
        return self._basket(("footwork", "speed", "agility", "balance"), self.movement)

    @property
    def go_for_it(self) -> float:
        """Willingness to pull the trigger on a winner."""
        return self._basket(("competitiveness", "clutch"), self.mental)


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
    caller skew a whole tier / roster up or down.
    """
    def draw() -> float:
        v = rng.gauss(base, spread)
        return max(0.05, min(0.95, v))

    attrs = {a: draw() for a in ATTRS}
    attrs.update({a: draw() for a in CONDITION_ATTRS})
    return Player(name=name, country=country, **attrs)


# ---------------------------------------------------------------------------
# Per-player accumulated stats
# ---------------------------------------------------------------------------

@dataclass
class PlayerStats:
    # Serving
    first_serves_in: int = 0
    first_serve_points: int = 0
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
    forced_errors: int = 0
    # Totals
    points_won: int = 0

    @property
    def first_serve_pct(self) -> float:
        return self.first_serves_in / self.first_serve_points if self.first_serve_points else 0.0

    @property
    def serve_points_won_pct(self) -> float:
        return self.serve_points_won / self.serve_points_total if self.serve_points_total else 0.0

    @property
    def has_data(self) -> bool:
        """True once any point has been recorded — distinguishes real stats from
        the empty placeholder the fast (scoreline-only) model returns."""
        return bool(self.serve_points_total or self.return_points_total)

    def add(self, other: "PlayerStats") -> None:
        """Accumulate another stat line into this one (all fields are counters)."""
        for f in fields(PlayerStats):
            setattr(self, f.name, getattr(self, f.name) + getattr(other, f.name))

    def to_dict(self) -> dict:
        """Compact JSON form for persistence (e.g. inside a dual's lines_json).
        Short keys keep thousands of persisted duals small; the mapping is the
        module-level `STAT_KEYS` (short -> field name)."""
        return {k: getattr(self, f) for k, f in STAT_KEYS}

    @classmethod
    def from_dict(cls, d: dict) -> "PlayerStats":
        return cls(**{f: int(d.get(k, 0) or 0) for k, f in STAT_KEYS})


# Persisted short key -> PlayerStats field. The one place the wire format lives.
STAT_KEYS: tuple[tuple[str, str], ...] = (
    ("ace", "aces"), ("df", "double_faults"),
    ("fsi", "first_serves_in"), ("fsp", "first_serve_points"),
    ("ssp", "second_serve_points"),
    ("svw", "serve_points_won"), ("svt", "serve_points_total"),
    ("rtw", "return_points_won"), ("rtt", "return_points_total"),
    ("bpf", "break_points_faced"), ("bps", "break_points_saved"),
    ("bpc", "break_points_converted"),
    ("win", "winners"), ("ue", "unforced_errors"), ("fe", "forced_errors"),
    ("pts", "points_won"),
)


@dataclass
class MatchState:
    players: tuple[Player, Player]
    rng: random.Random
    fmt: "object" = None              # engine.format.MatchFormat (rule toggles)
    context: MatchContext = field(default_factory=MatchContext)

    # situational context for the pressure/clutch model (set by match.py)
    pressure: float = 0.0             # 0 (routine) ... 1 (match point)
    set_target: int = 6              # games to win the current set
    sets_needed: int = 2             # sets to win the match
    is_final_set: bool = False

    # live score
    server: int = 0                   # index of current server
    points: list[int] = field(default_factory=lambda: [0, 0])
    games: list[int] = field(default_factory=lambda: [0, 0])
    sets: list[int] = field(default_factory=lambda: [0, 0])
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
