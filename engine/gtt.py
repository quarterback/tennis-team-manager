"""
GTT dual-match team layer — co-ed Global Team Tennis format.

A GTT dual is NINE lines, split evenly across three disciplines:
  * 3 men's singles   (MS1..MS3, best-of-3 no-ad)
  * 3 women's singles (WS1..WS3, best-of-3 no-ad)
  * 3 mixed doubles   (XD1..XD3, 8-game pro set; one man + one woman a side)

Each line is one team point. The first franchise to 5 of the 9 clinches and the
remaining lines are recorded unfinished (the `completed` flag), mirroring the
NCAA-dual abandon-after-clinch convention in `engine.dual`. A dual resolves to a
single team win/loss — GTT is scored like any other team sport, NOT with WTT
cumulative-game scoring.

Mixed doubles needs no special cross-gender model: the doubles engine
(`engine.doubles`) is attribute-driven and gender-blind, so an XD pair is just a
`DoublesTeam` of one man and one woman, and both sides are built identically.

Determinism: each constituent match draws a derived seed (`base_seed + offset`),
so the whole dual reproduces from one seed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .state import MatchContext, Player
from .format import PRESETS
from .match import simulate_match, MatchResult
from .doubles import simulate_doubles, DoublesTeam, DoublesResult

LINES_TO_CLINCH = 5    # first to 5 of the 9 available lines


@dataclass
class GTTTeam:
    """A GTT franchise: three men + three women, each ordered 1..3 by strength."""
    name: str
    men: list[Player]      # 3, ordered MS1..MS3
    women: list[Player]    # 3, ordered WS1..WS3
    # Mixed pairings as (man_idx, woman_idx) into `men`/`women`; defaults to
    # MS1+WS1, MS2+WS2, MS3+WS3.
    mixed: list[tuple[int, int]] = field(
        default_factory=lambda: [(0, 0), (1, 1), (2, 2)])


@dataclass
class GTTLine:
    slot: str                                   # "MS1".."MS3", "WS1".."WS3", "XD1".."XD3"
    home_won: bool
    result: MatchResult | DoublesResult | None  # DoublesResult on the XD lines
    completed: bool = True                       # False when abandoned after clinch


@dataclass
class GTTResult:
    home: GTTTeam
    away: GTTTeam
    home_points: int
    away_points: int
    winner: int               # 0 = home, 1 = away
    lines: list[GTTLine]


def _xd(team: GTTTeam, pair: tuple[int, int]) -> DoublesTeam:
    """Build a mixed-doubles side (one man + one woman) for a lineup pairing."""
    return DoublesTeam(players=(team.men[pair[0]], team.women[pair[1]]))


def simulate_gtt_dual(home: GTTTeam, away: GTTTeam, *, seed: int,
                      fidelity: str = "full",
                      context: MatchContext | None = None) -> GTTResult:
    context = context or MatchContext()
    lines: list[GTTLine] = []
    points = [0, 0]  # [home, away]

    singles_fmt = PRESETS["ncaa_dual"]    # best-of-3, no-ad
    mixed_fmt = PRESETS["pro_set_8"]      # 8-game pro set, like dual doubles

    def clinched() -> bool:
        return max(points) >= LINES_TO_CLINCH

    def play_singles(prefix: str, home_line, away_line, seed_base: int) -> None:
        for i in range(3):
            slot = f"{prefix}{i+1}"
            if clinched():
                lines.append(GTTLine(slot, False, None, completed=False))
                continue
            res = simulate_match(home_line[i], away_line[i], seed=seed_base + i,
                                 fmt=singles_fmt, fidelity=fidelity, context=context)
            home_won = res.winner == 0
            points[0 if home_won else 1] += 1
            lines.append(GTTLine(slot, home_won, res))

    # --- Men's singles, then women's singles ---
    play_singles("MS", home.men, away.men, seed + 100)
    play_singles("WS", home.women, away.women, seed + 200)

    # --- Mixed doubles ---
    for i in range(3):
        slot = f"XD{i+1}"
        if clinched():
            lines.append(GTTLine(slot, False, None, completed=False))
            continue
        res = simulate_doubles(_xd(home, home.mixed[i]), _xd(away, away.mixed[i]),
                               seed=seed + 300 + i, fmt=mixed_fmt,
                               fidelity=fidelity, context=context)
        home_won = res.winner == 0
        points[0 if home_won else 1] += 1
        lines.append(GTTLine(slot, home_won, res))

    winner = 0 if points[0] > points[1] else 1
    return GTTResult(home=home, away=away,
                     home_points=points[0], away_points=points[1],
                     winner=winner, lines=lines)
