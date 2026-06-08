"""
Seeded single-elimination INDIVIDUAL tournament — the reusable draw framework.

`app.bracket` brackets whole *teams* (duals, seeded by Power Index); this brackets
individual *players*. Entrants are seeded by a rating key, byes go to the top seeds,
and every match is decided by actually **playing it** — the caller supplies a `play`
callback (default: `engine.simulate_fast` between two `Player`s), so higher seeds are
favored but upsets happen for free off the engine's own variance.

What it returns is the raw material a résumé needs: the champion, the runner-up, and
**every entrant's finishing round** (Champion / Finalist / Semifinalist /
Quarterfinalist / R16 / R32 / …). That makes it reusable beyond the junior circuit —
NCAA Singles/Doubles Championships, conference individual titles, future pro circuits
all want the same "draw → advancement → finish" shape.

Determinism: one `random.Random(seed)` drives every match seed, and seeding ties are
broken by entry index, so the same entrants + seed reproduce the same draw exactly.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

# Round labels keyed by how many players ENTER that round (always a power of two
# once the field is padded with byes).
_ROUND_NAMES = {2: "Final", 4: "Semifinals", 8: "Quarterfinals"}
# A player's finishing line, keyed by the size of the round they lost in.
_FINISH_NAMES = {2: "Finalist", 4: "Semifinalist", 8: "Quarterfinalist"}


def round_name(size: int) -> str:
    return _ROUND_NAMES.get(size, f"Round of {size}")


def finish_label(size: int, champion: bool = False) -> str:
    """Label for a player who lost in a round of `size` (champion overrides)."""
    if champion:
        return "Champion"
    return _FINISH_NAMES.get(size, f"R{size}")


def _seed_order(n: int) -> list[int]:
    """Standard bracket seeding order for a power-of-two size n (1 meets n, 2 meets
    n-1, …) so the top seeds can only collide in the late rounds."""
    order = [1, 2]
    while len(order) < n:
        m = len(order) * 2
        order = [x for s in order for x in (s, m + 1 - s)]
    return order


@dataclass
class TourMatch:
    rnd: str            # round label, e.g. "Quarterfinals"
    size: int           # players entering this round (power of two)
    hi: int             # better seed (lower seeded index)
    lo: int             # worse seed
    winner: int         # seeded index of the winner
    upset: bool         # lower seed won


@dataclass
class TournamentResult:
    entrants: list                                   # seeded order; index 0 = top seed
    rounds: list[list[TourMatch]] = field(default_factory=list)
    champion_idx: int | None = None
    runner_up_idx: int | None = None
    # seeded index -> size of the round in which they were eliminated. The champion
    # is absent (never eliminated); look them up via `champion_idx`.
    elim_size: dict[int, int] = field(default_factory=dict)

    @property
    def champion(self):
        return self.entrants[self.champion_idx] if self.champion_idx is not None else None

    @property
    def runner_up(self):
        return self.entrants[self.runner_up_idx] if self.runner_up_idx is not None else None

    def finish_of(self, idx: int) -> str | None:
        """Finishing label for the entrant at seeded index `idx`."""
        if idx == self.champion_idx:
            return "Champion"
        size = self.elim_size.get(idx)
        return None if size is None else finish_label(size)


def _default_play(a, b, *, seed: int):
    """Play `a` vs `b` with the fast game-level model; `a`/`b` are engine.Players."""
    from .fast import simulate_fast
    res = simulate_fast(a, b, seed=seed)
    return a if res.winner == 0 else b


def run_tournament(entrants: list, *, seed: int,
                   play: Callable | None = None,
                   key: Callable | None = None) -> TournamentResult:
    """Run a seeded single-elimination draw over `entrants`.

    `key(entrant) -> float` is the seeding rating (higher seeds first); ties break on
    entry index for determinism. If omitted, `entrants` are taken as already seeded.
    `play(a, b, seed=...) -> winner` decides each match (default: `simulate_fast`).
    """
    play = play or _default_play
    n_real = len(entrants)
    if n_real == 0:
        return TournamentResult(entrants=[])
    if key is not None:
        order = sorted(range(n_real), key=lambda i: (-key(entrants[i]), i))
        seeded = [entrants[i] for i in order]
    else:
        seeded = list(entrants)
    res = TournamentResult(entrants=seeded)
    if n_real == 1:
        res.champion_idx = 0
        return res

    n = 1
    while n < n_real:
        n *= 2
    positions = _seed_order(n)
    # Slots hold the seeded index (0-based) or None for a bye.
    slots: list[int | None] = [(s - 1) if s <= n_real else None for s in positions]

    rng = random.Random(seed)
    size = n
    while size > 1:
        nxt: list[int | None] = []
        matches: list[TourMatch] = []
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if a is None and b is None:
                nxt.append(None)
                continue
            if b is None:
                nxt.append(a)
                continue
            if a is None:
                nxt.append(b)
                continue
            hi, lo = (a, b) if a < b else (b, a)
            w_ent = play(seeded[hi], seeded[lo], seed=rng.randint(1, 10 ** 9))
            w = hi if w_ent is seeded[hi] else lo
            loser = lo if w == hi else hi
            res.elim_size[loser] = size
            matches.append(TourMatch(round_name(size), size, hi, lo, w, upset=(w == lo)))
            nxt.append(w)
        if matches:
            res.rounds.append(matches)
        if size == 2 and matches:
            final = matches[-1]
            res.champion_idx = final.winner
            res.runner_up_idx = final.lo if final.winner == final.hi else final.hi
        slots = nxt
        size //= 2
    # A field padded entirely with byes around a single real entrant never plays a
    # match; fall back to the lone survivor as champion.
    if res.champion_idx is None:
        survivors = [s for s in slots if s is not None]
        if survivors:
            res.champion_idx = survivors[0]
    return res
