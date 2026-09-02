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
    # Any byes beyond the seed opponents land on random open slots.
    #
    # ‼️ BUT NEVER ON BOTH HALVES OF ONE PAIRING. A pairing with two empty slots is
    # not a bye, it is a MATCH THAT DOES NOT EXIST: whoever is drawn opposite it
    # advances twice without playing, the round after the first stops being half the
    # size of the one before it, and `state._bracket_canvas` — which links columns
    # positionally on exactly that halving — then draws the tree wrong. It bit the
    # JHSAA individual draws, where a field of 82-92 in a 128 bracket needs 36-46
    # byes against 32 seeded anchors: measured, 82-92 leaked a bye past round one in
    # most draws, while 93+ (byes <= 35) never did.
    #
    # It is ALWAYS avoidable, which is why this takes no fallback: `n` is the
    # smallest power of two >= `n_real`, so `n_real > n / 2`, so the byes needed
    # (`n - n_real`) are fewer than the `n / 2` pairings available to hold them.
    extra = need_byes - len(bye_slots)
    for _ in range(max(0, extra)):
        pick = next(i for i, s in enumerate(open_slots) if (s ^ 1) not in bye_slots)
        bye_slots.add(open_slots.pop(pick))

    # draw the unseeded entrants (ranks n_seeds..n_real-1) at random
    unseeded = list(range(n_seeds, n_real))
    rng.shuffle(unseeded)
    for slot, rank in zip(open_slots, unseeded):
        slots[slot] = rank
    return slots


def _seed_tier(num: int) -> int:
    """Which PLACEMENT TIER a 1-based seed number belongs to — [1], [2], [3-4],
    [5-8], [9-16], … — the same tiers `seeded_draw` shuffles among mirror anchors.

    Two entrants in one tier are interchangeable BY CONSTRUCTION: the draw already
    picks their anchors at random from the tier's own set, so swapping them is a
    re-draw the seeding contract permits, not a violation of it. That is what makes
    `separate_draw` able to move a seed at all."""
    if num <= 2:
        return num
    tier, lo = 3, 3
    while True:
        hi = 2 * lo - 2
        if num <= hi:
            return tier
        lo, tier = hi + 1, tier + 1


def separate_draw(slots: list, key, n_seeds: int, rng: random.Random) -> None:
    """Spread same-`key` entrants across the draw, in place.

    Two entrants sharing a key are put in opposite HALVES; three or four in
    separate QUARTERS; and so on — the block size halves each time the group
    doubles, so a group of k is spread as far as a bracket of this size allows and
    they can only meet as late as possible.

    Entries are moved by SWAPPING WITH AN ENTRANT OF THE SAME PLACEMENT TIER
    (`_seed_tier`; every unseeded entrant is one tier). That is the whole reason
    this can run after `seeded_draw` rather than inside it: a tier's anchors are
    already assigned at random within the tier, so exchanging two of its members is
    a draw this function could have produced itself. A swap that would create a new
    collision, or for which no same-tier partner exists in the target block, is
    skipped — the draw degrades to the un-separated placement for that one entrant
    rather than failing, which is the only safe behaviour when a single school
    holds more entries than the bracket has blocks.

    `key(rank) -> hashable | None` reads an entrant's group; None never separates.
    Deterministic given `rng`.
    """
    where = {rank: i for i, rank in enumerate(slots) if rank is not None}
    groups: dict = {}
    for rank in where:
        k = key(rank)
        if k is not None:
            groups.setdefault(k, []).append(rank)
    n = len(slots)
    for k, members in sorted(groups.items(), key=lambda kv: (-len(kv[1]), str(kv[0]))):
        if len(members) < 2:
            continue
        # Blocks: 2 members -> halves, 3-4 -> quarters, 5-8 -> eighths, …
        blocks = 2
        while blocks < len(members):
            blocks *= 2
        blocks = min(blocks, n)
        size = n // blocks
        members = sorted(members)                      # best seed keeps its slot
        taken: set = set()
        for rank in members:
            b = where[rank] // size
            if b not in taken:
                taken.add(b)
                continue
            # Collision: find a same-tier partner in a block nobody in this group
            # holds, whose own group is not already represented there either.
            tier = _seed_tier(rank + 1) if rank < n_seeds else -1
            cands = []
            for other, pos in where.items():
                if other == rank:
                    continue
                ob = pos // size
                if ob in taken:
                    continue
                otier = _seed_tier(other + 1) if other < n_seeds else -1
                if otier != tier:
                    continue
                ok = key(other)
                # Moving `other` into this block must not collide there either.
                if ok is not None and ok != k and any(
                        where[m] // size == where[rank] // size
                        for m in groups.get(ok, ()) if m != other):
                    continue
                cands.append((ob, other))
            if not cands:
                taken.add(b)                           # degrade, never crash
                continue
            cands.sort()
            ob, other = cands[rng.randrange(len(cands))]
            i, j = where[rank], where[other]
            slots[i], slots[j] = slots[j], slots[i]
            where[rank], where[other] = j, i
            taken.add(ob)


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
                   seeds: int | None = None,
                   separate: Callable | None = None) -> TournamentResult:
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
    # ‼️ OPT-IN, AND UNSET IT CHANGES NOTHING. `separate(entrant) -> group` spreads
    # same-group entrants across the draw (see `separate_draw`); every caller that
    # does not pass it — every varsity flight, both college championships, the
    # junior circuit — consumes the rng in exactly the same order and draws exactly
    # the bracket it drew before this existed.
    if separate is not None:
        separate_draw(slots, lambda r: separate(seeded[r]), n_seeds, rng)
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
