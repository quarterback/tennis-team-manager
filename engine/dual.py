"""
Dual-match team layer (NCAA format).

Order of play:
  1. Doubles - 3 matches (8-game pro set each); winning 2 of 3 = ONE team point.
  2. Singles - 6 matches (best-of-3, no-ad); each is one team point.
  First team to 4 of the 7 available points clinches.

`abandoned_after_clinch`: once a side reaches 4, remaining singles are
recorded as not-completed (the real-college convention) rather than played
out - flagged so a stats layer can exclude them.

Determinism: each constituent match gets a derived seed `base_seed + offset`,
so the whole dual is reproducible from one seed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .state import MatchContext, Player, ATTRS, CONDITION_ATTRS
from .format import PRESETS
from .match import simulate_match, MatchResult


@dataclass
class Team:
    name: str
    # Six singles players, ordered 1..6 by strength (lineup order).
    singles: list[Player]
    # Doubles pairings as index pairs into `singles`; defaults to 1/2, 3/4, 5/6.
    doubles: list[tuple[int, int]] = field(default_factory=lambda: [(0, 1), (2, 3), (4, 5)])


@dataclass
class DualLine:
    slot: str                 # "D1".."D3", "S1".."S6"
    home_won: bool
    result: MatchResult | None
    completed: bool = True     # False when abandoned after clinch


@dataclass
class DualResult:
    home: Team
    away: Team
    home_points: int
    away_points: int
    winner: int               # 0 = home, 1 = away
    lines: list[DualLine]
    doubles_point: int | None  # which side took the doubles point (0/1) or None if split unreached


def _pair_player(team: Team, pair: tuple[int, int]) -> Player:
    """Collapse a doubles pair into one synthetic Player (attribute means) so
    the existing singles engine can resolve the doubles pro set. A real
    doubles model (serve+volley, net play) is a later build.
    """
    a, b = team.singles[pair[0]], team.singles[pair[1]]
    attrs = {at: (getattr(a, at) + getattr(b, at)) / 2.0 for at in ATTRS + CONDITION_ATTRS}
    return Player(name=f"{a.name} / {b.name}", country=a.country, **attrs)


def simulate_dual(home: Team, away: Team, *, seed: int, fidelity: str = "full",
                  context: MatchContext | None = None) -> DualResult:
    context = context or MatchContext()
    lines: list[DualLine] = []
    points = [0, 0]  # [home, away]

    # --- Doubles: 3 pro-set matches, 2 of 3 -> 1 team point ---
    doubles_pro = PRESETS["pro_set_8"]
    d_wins = [0, 0]
    for i in range(3):
        hp = _pair_player(home, home.doubles[i])
        ap = _pair_player(away, away.doubles[i])
        res = simulate_match(hp, ap, seed=seed + 10 + i, fmt=doubles_pro,
                             fidelity=fidelity, context=context)
        home_won = res.winner == 0
        d_wins[0 if home_won else 1] += 1
        lines.append(DualLine(slot=f"D{i+1}", home_won=home_won, result=res))
    doubles_point = 0 if d_wins[0] >= 2 else 1
    points[doubles_point] += 1

    # --- Singles: 6 matches, clinch at 4 ---
    singles_fmt = PRESETS["ncaa_dual"]
    clinch = 4
    for i in range(6):
        if max(points) >= clinch:
            lines.append(DualLine(slot=f"S{i+1}", home_won=False, result=None, completed=False))
            continue
        res = simulate_match(
            home.singles[i], away.singles[i],
            seed=seed + 100 + i, fmt=singles_fmt, fidelity=fidelity, context=context,
        )
        home_won = res.winner == 0
        points[0 if home_won else 1] += 1
        lines.append(DualLine(slot=f"S{i+1}", home_won=home_won, result=res))

    winner = 0 if points[0] > points[1] else 1
    return DualResult(
        home=home, away=away,
        home_points=points[0], away_points=points[1],
        winner=winner, lines=lines, doubles_point=doubles_point,
    )
