"""
Seeded single-elimination INDIVIDUAL tournament — the reusable draw framework.

`app.bracket` brackets whole *teams* (duals, seeded by Power Index); this brackets
individual *players*. Entrants are rating-ordered by a key, the draw is seeded the
tennis way — only the top quarter (128→32, 64→16, …) are protected, everyone else
is drawn in at random — byes go to the top seeds, and every match is decided by
actually **playing it** (the caller supplies a `play` callback, default
`engine.simulate_fast`), so higher seeds are favored but upsets happen for free off
the engine's own variance.

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


def seed_count(field: int) -> int:
    """How many entrants are SEEDED in a draw of `field`, per the tennis
    convention: a quarter of the (power-of-two) draw. 128→32, 64→16, 32→8,
    16→4, 8→2. The rest of the field is drawn in unseeded."""
    n = 1
    while n < field:
        n *= 2
    return max(2, n // 4)


def seeded_draw(n_real: int, n: int, n_seeds: int, rng: random.Random) -> list[int | None]:
    """Make the draw: return slots[i] = entrant rank (0-based, 0 = top seed) or
    None (a bye). Only the top `n_seeds` are placed at protected anchors — seeds
    1 and 2 fixed at the ends, every deeper seed tier shuffled among its mirror
    anchors — byes go to the top seeds, and all unseeded entrants are drawn at
    random into the open slots. Same rng + inputs ⇒ same draw."""
    positions = _seed_order(n)                 # positions[slot] = canonical seed no.
    slot_of = {positions[i]: i for i in range(n)}
    slots: list[int | None] = [None] * n

    # Place the seeds tier by tier. Tiers: [1], [2], [3,4], [5..8], [9..16], …;
    # 1 and 2 are anchored, deeper tiers are randomized among their mirror slots.
    n_seeds = min(n_seeds, n_real)
    tier_lo = 1
    while tier_lo <= n_seeds:
        # Tiers: [1], [2], [3,4], [5..8], [9..16], … — seeds 1 and 2 are anchored,
        # each deeper tier doubles and is shuffled among its mirror anchors.
        tier_hi = tier_lo if tier_lo <= 2 else min(2 * tier_lo - 2, n_seeds)
        nums = list(range(tier_lo, tier_hi + 1))
        anchors = [slot_of[s] for s in nums]
        rng.shuffle(anchors)
        for num, pos in zip(nums, anchors):
            slots[pos] = num - 1               # entrant rank
        tier_lo = 2 if tier_lo == 1 else tier_hi + 1

    # Byes go to the top seeds' first-round opponents, in seed order.
    need_byes = n - n_real
    bye_slots: set[int] = set()
    for rank in range(min(n_seeds, n_real)):
        if len(bye_slots) >= need_byes:
            break
        opp = slot_of[rank + 1] ^ 1             # the seed's pair partner slot
        if slots[opp] is None:
            bye_slots.add(opp)

    open_slots = [i for i in range(n) if slots[i] is None and i not in bye_slots]
    rng.shuffle(open_slots)
    # any byes beyond the seed opponents land on random open slots
    extra = need_byes - len(bye_slots)
    for _ in range(max(0, extra)):
        bye_slots.add(open_slots.pop())

    # draw the unseeded entrants (ranks n_seeds..n_real-1) at random
    unseeded = list(range(n_seeds, n_real))
    rng.shuffle(unseeded)
    for slot, rank in zip(open_slots, unseeded):
        slots[slot] = rank
    return slots


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
    entrants: list                                   # rating order; index 0 = #1 seed
    rounds: list[list[TourMatch]] = field(default_factory=list)
    champion_idx: int | None = None
    runner_up_idx: int | None = None
    # seeded index -> size of the round in which they were eliminated. The champion
    # is absent (never eliminated); look them up via `champion_idx`.
    elim_size: dict[int, int] = field(default_factory=dict)
    n_seeds: int = 0                                 # how many entrants were seeded

    def seed_no(self, idx: int) -> int | None:
        """The displayed seed number for entrant `idx` (1-based), or None if the
        entrant was unseeded (drawn in)."""
        return idx + 1 if idx < self.n_seeds else None

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
                   key: Callable | None = None,
                   seeds: int | None = None) -> TournamentResult:
    """Run a single-elimination draw over `entrants` with tennis-style seeding.

    `key(entrant) -> float` is the seeding rating (higher first); ties break on entry
    index for determinism. If omitted, `entrants` are taken as already rating-ordered.
    Only the top `seeds` entrants are protected in the draw (default: a quarter of the
    bracket — 128→32, 64→16, …); everyone else is drawn in at random. `play(a, b,
    seed=...) -> winner` decides each match (default: `simulate_fast`).
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
    n_seeds = min(seed_count(n_real) if seeds is None else seeds, n_real)
    res = TournamentResult(entrants=seeded, n_seeds=n_seeds)
    if n_real == 1:
        res.champion_idx = 0
        return res

    n = 1
    while n < n_real:
        n *= 2
    rng = random.Random(seed)
    # The draw (seed placement + random unseeded fill) consumes the rng first, so
    # it is part of the same deterministic stream as the match seeds below.
    slots: list[int | None] = seeded_draw(n_real, n, n_seeds, rng)
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
