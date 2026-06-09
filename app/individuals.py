"""
NCAA Individual Doubles Championship — the post-team-tournament 64-pair draw.

The mirror of `app.bracket` (the NCAA *team* championship), but for individual
doubles **pairs**: each program enters its #1 pair (its two strongest players),
the field is seeded by the pair's doubles rating (engine.doubles.doubles_rating),
and every round is decided by playing a real two-on-two match (engine.doubles)
via the shared single-elimination framework (engine.run_tournament).

It runs AFTER the team tournament, and like the team bracket's projection view
it is a **derived, seed-deterministic** computation off the program rosters —
so it needs no new persisted phase or table: the same seed reproduces the same
draw and the same champion exactly.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine import run_tournament, simulate_doubles, DoublesTeam, doubles_rating
from engine.format import MatchFormat
from .ncaa import Program, squad_and_ladder, load_division

DOUBLES_FIELD = 64               # 64 pairs = 128 players, the NCAA doubles draw
FIELD_MIN, FIELD_MAX = 8, 128

# NCAA individual doubles scoring: best-of-3, no-ad, set tiebreaks, with a
# 10-point match tiebreak as the deciding set.
DOUBLES_FMT = MatchFormat(best_of=3, no_ad=True, set_tiebreak=True,
                          final_set_tiebreak=True, final_set_tiebreak_target=10)


def _last(name: str) -> str:
    return name.split()[-1] if name else name


@dataclass
class DoublesEntry:
    """One pair in the draw: a program's two best players."""
    program: Program
    p0: object                   # Prospect (name / pid for display + linking)
    p1: object
    team: DoublesTeam            # the engine pair that actually plays
    rating: float                # seeding signal (doubles_rating)

    @property
    def label(self) -> str:
        return f"{_last(self.p0.name)} / {_last(self.p1.name)}"


@dataclass
class DoublesMatch:
    rnd: str
    hi_seed: int
    lo_seed: int
    hi: DoublesEntry
    lo: DoublesEntry
    winner_seed: int
    winner: DoublesEntry
    scoreline: str               # from the winning pair's perspective
    upset: bool


@dataclass
class DoublesChampionship:
    entries: list[DoublesEntry]                       # seeded order, [0] = #1 seed
    rounds: list[list[DoublesMatch]] = field(default_factory=list)
    champion: DoublesEntry | None = None
    runner_up: DoublesEntry | None = None

    def seed_of(self, e: DoublesEntry) -> int:
        return self.entries.index(e) + 1


def _program_pair(prog: Program) -> DoublesEntry:
    """A program's #1 doubles pair — its two strongest players by the singles
    ladder, which is exactly how the top doubles team is built in a dual."""
    team, ladder = squad_and_ladder(prog)
    a, b = team.singles[0], team.singles[1]
    pair = DoublesTeam(players=(a, b), name=f"{ladder[0].name} / {ladder[1].name}")
    return DoublesEntry(program=prog, p0=ladder[0], p1=ladder[1], team=pair,
                        rating=doubles_rating(a, b))


def clamp_field(size: int) -> int:
    return max(FIELD_MIN, min(FIELD_MAX, int(size)))


def select_doubles_field(programs: list[Program], size: int = DOUBLES_FIELD) -> list[DoublesEntry]:
    """The seeded field: each program's #1 pair, the strongest `size` by doubles
    rating, ordered as seeds (ties break on school name for determinism)."""
    entries = [_program_pair(p) for p in programs]
    entries.sort(key=lambda e: (-e.rating, e.program.school))
    return entries[:max(2, min(size, len(entries)))]


def run_doubles_championship(division: str, gender: str, *, seed: int,
                             size: int = DOUBLES_FIELD) -> DoublesChampionship:
    """Select, seed and play the individual doubles championship. Deterministic:
    the same (division, gender, seed, size) reproduces the whole draw."""
    div = load_division(division, gender)
    entries = select_doubles_field(div.programs, clamp_field(size))
    rng = random.Random(seed)
    played: dict = {}

    def pkey(e: DoublesEntry) -> str:
        return e.program.key

    def play(ea: DoublesEntry, eb: DoublesEntry, *, seed: int) -> DoublesEntry:
        res = simulate_doubles(ea.team, eb.team, seed=seed, fmt=DOUBLES_FMT)
        played[frozenset((pkey(ea), pkey(eb)))] = res
        return ea if res.winner == 0 else eb

    result = run_tournament(entries, seed=rng.randint(1, 10 ** 9), play=play,
                            key=lambda e: e.rating)

    champ = DoublesChampionship(entries=result.entrants)
    for rnd in result.rounds:
        matches: list[DoublesMatch] = []
        for m in rnd:
            hi, lo = result.entrants[m.hi], result.entrants[m.lo]
            res = played[frozenset((pkey(hi), pkey(lo)))]
            matches.append(DoublesMatch(
                rnd=m.rnd, hi_seed=m.hi + 1, lo_seed=m.lo + 1, hi=hi, lo=lo,
                winner_seed=m.winner + 1, winner=result.entrants[m.winner],
                scoreline=res.scoreline, upset=m.upset))
        champ.rounds.append(matches)
    if result.champion_idx is not None:
        champ.champion = result.entrants[result.champion_idx]
    if result.runner_up_idx is not None:
        champ.runner_up = result.entrants[result.runner_up_idx]
    return champ
