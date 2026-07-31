"""
NCAA Individual Championships — the post-team-tournament singles & doubles draws.

The individual mirror of `app.bracket` (the NCAA *team* championship): the best
individual players (singles, 128 draw) and pairs (doubles, 64 draw) in a
division×gender, seeded by an ability rating and decided round by round by
actually playing the match in the engine — `engine.simulate_match` for singles,
the four-player `engine.simulate_doubles` for doubles — over the shared
single-elimination framework (`engine.run_tournament`).

Both events run AFTER the team tournament and, like the team bracket's
projection, are **derived, seed-deterministic** computations off the program
rosters: no new persisted phase or table, and the same seed reproduces the same
draw and champions exactly. Every division×gender has its own — D1/D2/D3 × men
and women — selected from that universe's own programs.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine import (run_tournament, simulate_match, simulate_doubles,
                    DoublesTeam, doubles_rating)
from engine.format import MatchFormat
from .ncaa import Program, squad_and_ladder, load_division

SINGLES_FIELD = 128              # 128 players, the NCAA singles draw
DOUBLES_FIELD = 64               # 64 pairs (128 players), the NCAA doubles draw
SINGLES_PER_PROGRAM = 2          # a program can qualify up to its top 2 singles
FIELD_MIN, FIELD_MAX = 8, 128

# NCAA individual scoring (singles and doubles): best-of-3, no-ad, set tiebreaks,
# with a 10-point match tiebreak as the deciding set.
INDIV_FMT = MatchFormat(best_of=3, no_ad=True, set_tiebreak=True,
                        final_set_tiebreak=True, final_set_tiebreak_target=10)


def _last(name: str) -> str:
    return name.split()[-1] if name else name


def clamp_field(size: int) -> int:
    return max(FIELD_MIN, min(FIELD_MAX, int(size)))


# --- Entries ---------------------------------------------------------------

@dataclass
class SinglesEntry:
    """One player in the singles draw."""
    program: Program
    player: object               # Prospect (name / pid for display + linking)
    engine: object               # engine.Player that actually plays
    rating: float                # seeding signal (ability overall)

    @property
    def label(self) -> str:
        return self.player.name

    @property
    def pid(self) -> str:
        return self.player.pid

    @property
    def key(self):
        return self.player.pid

    @property
    def players(self) -> list:
        return [self.player]


@dataclass
class DoublesEntry:
    """One pair in the doubles draw: a program's two best players."""
    program: Program
    p0: object
    p1: object
    team: DoublesTeam            # the engine pair that actually plays
    rating: float                # seeding signal (doubles_rating)

    @property
    def label(self) -> str:
        return f"{_last(self.p0.name)} / {_last(self.p1.name)}"

    @property
    def key(self):
        return self.program.key

    @property
    def players(self) -> list:
        return [self.p0, self.p1]


# --- Shared draw result shapes (used by both events) -----------------------

@dataclass
class DrawMatch:
    rnd: str
    hi: object                   # SinglesEntry | DoublesEntry (better-rated side)
    lo: object
    hi_seed: int | None          # seed number, or None if that side was unseeded
    lo_seed: int | None
    winner: object
    winner_is_hi: bool
    scoreline: str               # from the winner's perspective
    upset: bool


@dataclass
class Championship:
    event: str                   # "Singles" | "Doubles"
    entries: list                # rating order, [0] = #1 seed
    n_seeds: int = 0             # only the top n_seeds carry a seed number
    rounds: list[list[DrawMatch]] = field(default_factory=list)
    champion: object | None = None
    runner_up: object | None = None

    def seed_of(self, e) -> int | None:
        """Seed number (1-based) for an entry, or None if it was unseeded."""
        rank = self.entries.index(e)
        return rank + 1 if rank < self.n_seeds else None


# Backwards-compatible alias (the doubles championship shipped first).
DoublesChampionship = Championship


def championship_to_dict(ch: Championship) -> dict:
    """Flatten a Championship to a JSON-safe dict for persistence — school / conf /
    label / seed per entry plus the round results. Rehydrated for display so the
    completed championship survives the year rollover (the live objects carry
    engine players that can't and needn't be stored)."""
    def ed(e):
        if e is None:
            return None
        return {"label": e.label, "school": e.program.school,
                "conf_abbr": getattr(e.program, "conf_abbr", ""),
                "pid": getattr(e, "pid", None), "seed": ch.seed_of(e),
                # every player on the entry (two for a doubles pair) so titles can
                # be credited per player (honors chips) and linked per player
                "players": [{"pid": p.pid, "name": p.name} for p in e.players]}
    return {
        "event": ch.event, "n_seeds": ch.n_seeds,
        "entries": [ed(e) for e in ch.entries],
        "champion": ed(ch.champion), "runner_up": ed(ch.runner_up),
        "rounds": [[{"rnd": m.rnd, "hi_seed": m.hi_seed, "lo_seed": m.lo_seed,
                     "winner_is_hi": m.winner_is_hi, "scoreline": m.scoreline,
                     "upset": m.upset, "hi": ed(m.hi), "lo": ed(m.lo)} for m in rnd]
                   for rnd in ch.rounds],
    }


def _assemble(event: str, result, played: dict) -> Championship:
    """Walk a run_tournament result into a Championship, looking each match's
    scoreline up in `played` (keyed by the frozenset of the two entry keys)."""
    ch = Championship(event=event, entries=result.entrants, n_seeds=result.n_seeds)
    for rnd in result.rounds:
        matches: list[DrawMatch] = []
        for m in rnd:
            hi, lo = result.entrants[m.hi], result.entrants[m.lo]
            res = played[frozenset((hi.key, lo.key))]
            matches.append(DrawMatch(
                rnd=m.rnd, hi=hi, lo=lo,
                hi_seed=result.seed_no(m.hi), lo_seed=result.seed_no(m.lo),
                winner=result.entrants[m.winner], winner_is_hi=(m.winner == m.hi),
                scoreline=res.scoreline, upset=m.upset))
        ch.rounds.append(matches)
    if result.champion_idx is not None:
        ch.champion = result.entrants[result.champion_idx]
    if result.runner_up_idx is not None:
        ch.runner_up = result.entrants[result.runner_up_idx]
    return ch


# --- Singles ---------------------------------------------------------------

def _program_singles(prog: Program, k: int = SINGLES_PER_PROGRAM) -> list[SinglesEntry]:
    """A program's top `k` singles players (the top of its ladder)."""
    team, ladder = squad_and_ladder(prog)
    out = []
    for i in range(min(k, len(ladder))):
        out.append(SinglesEntry(program=prog, player=ladder[i],
                                engine=team.singles[i], rating=team.singles[i].overall))
    return out


def select_singles_field(programs: list[Program], size: int = SINGLES_FIELD) -> list[SinglesEntry]:
    """The seeded singles field: every program's top players pooled, the strongest
    `size` by ability, ordered as seeds (ties break on school then name)."""
    pool: list[SinglesEntry] = []
    for p in programs:
        pool.extend(_program_singles(p))
    pool.sort(key=lambda e: (-e.rating, e.program.school, e.player.name))
    return pool[:max(2, min(size, len(pool)))]


def run_singles_championship(division: str, gender: str, *, seed: int,
                             size: int = SINGLES_FIELD) -> Championship:
    """Select, seed and play the individual singles championship. Deterministic:
    the same (division, gender, seed, size) reproduces the whole draw."""
    div = load_division(division, gender)
    entries = select_singles_field(div.programs, clamp_field(size))
    rng = random.Random(seed)
    played: dict = {}

    def play(ea: SinglesEntry, eb: SinglesEntry, *, seed: int) -> SinglesEntry:
        res = simulate_match(ea.engine, eb.engine, seed=seed, fmt=INDIV_FMT)
        played[frozenset((ea.key, eb.key))] = res
        return ea if res.winner == 0 else eb

    result = run_tournament(entries, seed=rng.randint(1, 10 ** 9), play=play,
                            key=lambda e: e.rating)
    return _assemble("Singles", result, played)


# --- Doubles ---------------------------------------------------------------

def _program_pair(prog: Program) -> DoublesEntry | None:
    """A program's #1 doubles pair — its two strongest players by the singles
    ladder, which is exactly how the top doubles team is built in a dual. None for a
    program that can't field two players: a pair is two DIFFERENT people, so unlike
    a dual (where a short side plays someone twice rather than 500-ing, see
    `engine.dual._court`) there's nothing to degrade to — it just doesn't enter."""
    team, ladder = squad_and_ladder(prog)
    if len(ladder) < 2:
        return None
    a, b = team.singles[0], team.singles[1]
    pair = DoublesTeam(players=(a, b), name=f"{ladder[0].name} / {ladder[1].name}")
    return DoublesEntry(program=prog, p0=ladder[0], p1=ladder[1], team=pair,
                        rating=doubles_rating(a, b))


def select_doubles_field(programs: list[Program], size: int = DOUBLES_FIELD) -> list[DoublesEntry]:
    """The seeded doubles field: each program's #1 pair, the strongest `size` by
    doubles rating, ordered as seeds (ties break on school name)."""
    entries = [e for e in (_program_pair(p) for p in programs) if e is not None]
    entries.sort(key=lambda e: (-e.rating, e.program.school))
    return entries[:max(2, min(size, len(entries)))]


def run_doubles_championship(division: str, gender: str, *, seed: int,
                             size: int = DOUBLES_FIELD) -> Championship:
    """Select, seed and play the individual doubles championship. Deterministic:
    the same (division, gender, seed, size) reproduces the whole draw."""
    div = load_division(division, gender)
    entries = select_doubles_field(div.programs, clamp_field(size))
    rng = random.Random(seed)
    played: dict = {}

    def play(ea: DoublesEntry, eb: DoublesEntry, *, seed: int) -> DoublesEntry:
        res = simulate_doubles(ea.team, eb.team, seed=seed, fmt=INDIV_FMT)
        played[frozenset((ea.key, eb.key))] = res
        return ea if res.winner == 0 else eb

    result = run_tournament(entries, seed=rng.randint(1, 10 ** 9), play=play,
                            key=lambda e: e.rating)
    return _assemble("Doubles", result, played)
