"""
Seeded single-elimination dual-match bracket — the NCAA team championship.

Modeled on online March-Madness bracket simulators: teams are **seeded by
Power Index**, then each round is decided by actually **playing the dual**
(engine.simulate_dual). The match engine already carries real variance, so
higher seeds are favored but upsets happen — skill does most of the work,
but it's lossy, not deterministic. No separate coin-flip model needed.

Field selection mirrors the real format: **conference champions get
automatic bids**, the rest of the field is filled by **at-large** Power
Index order.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine import simulate_dual
from engine.format import PRESETS
from .ncaa import Program, build_squad

ROUND_NAMES = {64: "Round of 64", 32: "Round of 32", 16: "Round of 16",
               8: "Quarterfinals", 4: "Semifinals", 2: "Final"}

FIELD_DEFAULT = 64
FIELD_MIN, FIELD_MAX = 16, 128


def clamp_field(size: int) -> int:
    return max(FIELD_MIN, min(FIELD_MAX, int(size)))


def _is_pow2(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _round_name(alive: int) -> str:
    if alive in ROUND_NAMES:
        return ROUND_NAMES[alive]
    if _is_pow2(alive):
        return f"Round of {alive}"
    return "First Round"     # play-in round for a non-power-of-two field


def _seed_positions(n: int) -> list[int]:
    """Standard bracket seeding order for a power-of-two size n
    (1 plays n, 2 plays n-1, ... arranged so top seeds only meet late)."""
    order = [1, 2]
    while len(order) < n:
        m = len(order) * 2
        order = [x for s in order for x in (s, m + 1 - s)]
    return order


def play_dual(a: Program, b: Program, *, seed: int, fidelity: str = "fast") -> Program:
    """Play one dual; higher seed (a) hosts. Returns the winning Program."""
    res = simulate_dual(build_squad(a), build_squad(b), seed=seed, fidelity=fidelity)
    return a if res.winner == 0 else b


@dataclass
class Matchup:
    rnd: str
    hi_seed: int
    lo_seed: int
    hi: Program
    lo: Program
    winner_seed: int
    winner: Program
    upset: bool


@dataclass
class BracketResult:
    seeds: list[Program]                      # index 0 = #1 seed
    autobids: set[str]                        # program keys
    rounds: list[list[Matchup]] = field(default_factory=list)
    champion: Program | None = None
    runner_up: Program | None = None

    def seed_of(self, p: Program) -> int:
        return self.seeds.index(p) + 1


def select_field(programs: list[Program], ratings: dict, champions: list[Program],
                 size: int = 64) -> tuple[list[Program], set[str]]:
    """Return (seeded field of `size`, autobid keys). Champions are auto-in;
    the rest are at-large by Power Index. The full field is seeded by PI."""
    by_pi = sorted(programs, key=lambda p: ratings[p.school].pi, reverse=True)
    champ_keys = {c.key for c in champions}

    field_keys: set[str] = set()
    field_progs: list[Program] = []
    # autobids first (capped at size, best PI first)
    for p in sorted(champions, key=lambda p: ratings[p.school].pi, reverse=True):
        if len(field_progs) >= size:
            break
        field_keys.add(p.key); field_progs.append(p)
    # fill at-large by PI
    for p in by_pi:
        if len(field_progs) >= size:
            break
        if p.key not in field_keys:
            field_keys.add(p.key); field_progs.append(p)

    seeded = sorted(field_progs, key=lambda p: ratings[p.school].pi, reverse=True)
    return seeded, champ_keys


def run_bracket(seeded: list[Program], autobids: set[str], *, seed: int,
                fidelity: str = "fast", final_fidelity: str = "full") -> BracketResult:
    """Run the single-elim bracket. The Final (and Semis) use full fidelity."""
    n = 1
    while n < len(seeded):
        n *= 2
    positions = _seed_positions(n)
    # slot -> Program or None (bye). seed s (1-based) → seeded[s-1].
    slots = [seeded[s - 1] if s <= len(seeded) else None for s in positions]
    seed_of = {p.key: i + 1 for i, p in enumerate(seeded)}

    res = BracketResult(seeds=seeded, autobids=autobids)
    rng = random.Random(seed)
    while True:
        alive = sum(1 for s in slots if s is not None)
        if alive <= 1:
            break
        name = _round_name(alive)
        matchups: list[Matchup] = []
        nxt: list[Program | None] = []
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if a is None and b is None:
                nxt.append(None); continue
            if b is None:
                nxt.append(a); continue
            if a is None:
                nxt.append(b); continue
            sa, sb = seed_of[a.key], seed_of[b.key]
            hi, lo = (a, b) if sa < sb else (b, a)
            hs, ls = (sa, sb) if sa < sb else (sb, sa)
            fid = final_fidelity if alive <= 4 else fidelity
            w = play_dual(hi, lo, seed=rng.randint(1, 10**9), fidelity=fid)
            ws = seed_of[w.key]
            m = Matchup(name, hs, ls, hi, lo, ws, w, upset=(ws == ls))
            matchups.append(m)
            nxt.append(w)
        if matchups:
            res.rounds.append(matchups)
        if alive == 2:
            final = matchups[0]
            res.champion = final.winner
            res.runner_up = final.lo if final.winner is final.hi else final.hi
            break
        slots = nxt
    return res
