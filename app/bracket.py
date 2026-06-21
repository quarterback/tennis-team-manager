"""
Seeded single-elimination dual-match bracket — the NCAA team championship.

Modeled on online March-Madness bracket simulators: teams are **seeded by
seed score** (Power Index + a power-conference preference, see ``seed_score``),
then each round is decided by actually **playing the dual** (engine.simulate_dual).
The match engine already carries real variance, so higher seeds are favored but
upsets happen — skill does most of the work, but it's lossy, not deterministic.
No separate coin-flip model needed.

Field selection mirrors the real format: **conference champions get
automatic bids**, the rest of the field is filled **at-large by seed score**.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine import simulate_dual
from engine.format import PRESETS
from engine.tournament import seed_count, seeded_draw
from .ncaa import Program, build_squad

ROUND_NAMES = {64: "Round of 64", 32: "Round of 32", 16: "Round of 16",
               8: "Quarterfinals", 4: "Semifinals", 2: "Final"}

FIELD_DEFAULT = 64
FIELD_MIN, FIELD_MAX = 16, 128

# Power-conference seeding preference. A purely results-based Power Index overrates
# teams that pile up wins against a weak conference schedule — so a mid-major can
# land a top seed and then lose its first match to a power-conference team it was
# seeded above. Real selection committees correct for this: they reward teams from
# deeper leagues (whose week-to-week schedule is far tougher) rather than seeding on
# results alone. So the NCAA field is selected and seeded by a *seed score* — the
# Power Index plus a conference-prestige preference. It's a balance, not a takeover:
# a genuinely dominant mid-major still earns a high seed, and automatic-qualifier
# status never substitutes for it (an at-large team can out-seed an AQ). The Power
# Index rankings themselves stay untouched — this tilt lives only at bracket time.
CONF_SEED_PREF = 0.30     # weight on conference prestige (0 = seed on the Power Index alone)
CONF_SEED_PIVOT = 0.55    # neutral prestige; only centers the score (order depends on the weight)


def seed_score(p: Program, ratings: dict) -> float:
    """Power Index plus the power-conference preference — the value the NCAA field is
    selected and seeded by (see ``CONF_SEED_PREF``)."""
    from .ncaa import conf_prestige
    return ratings[p.school].pi + CONF_SEED_PREF * (conf_prestige(p.conf_abbr) - CONF_SEED_PIVOT)


def field_for_division(division: str) -> int:
    """National-tournament field size by division. D1 here is a ~390-team
    division across 34 automatic-bid leagues, so a 64 field is too small (the
    autobids alone nearly fill it); D1 uses a 96 field. D2/D3 keep 64."""
    return 96 if division == "D1" else FIELD_DEFAULT



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
    hi: Program                               # better-rated side
    lo: Program
    hi_seed: int | None                       # seed number, or None if unseeded
    lo_seed: int | None
    winner: Program
    winner_is_hi: bool
    upset: bool


@dataclass
class BracketResult:
    seeds: list[Program]                      # rating order; index 0 = #1 seed
    autobids: set[str]                        # program keys
    n_seeds: int = 0                          # only the top n_seeds carry a seed no.
    rounds: list[list[Matchup]] = field(default_factory=list)
    champion: Program | None = None
    runner_up: Program | None = None

    def seed_of(self, p: Program) -> int | None:
        """Seed number (1-based), or None if the program was unseeded in the draw."""
        rank = self.seeds.index(p)
        return rank + 1 if rank < self.n_seeds else None


def select_field(programs: list[Program], ratings: dict, champions: list[Program],
                 size: int = 64, score: dict | None = None) -> tuple[list[Program], set[str]]:
    """Return (seeded field of `size`, autobid keys). Champions are auto-in; the rest
    are at-large by seed value, and the full field is seeded by it. ``score`` is an
    explicit {school: seed value} map (the ITA team-ranking points); without it the
    field falls back to ``seed_score`` (Power Index + power-conference preference)."""
    def sc(p: Program) -> float:
        return score.get(p.school, 0.0) if score is not None else seed_score(p, ratings)
    by_score = sorted(programs, key=sc, reverse=True)
    champ_keys = {c.key for c in champions}

    field_keys: set[str] = set()
    field_progs: list[Program] = []
    # autobids first (capped at size, best seed value first)
    for p in sorted(champions, key=sc, reverse=True):
        if len(field_progs) >= size:
            break
        field_keys.add(p.key); field_progs.append(p)
    # fill at-large by seed value
    for p in by_score:
        if len(field_progs) >= size:
            break
        if p.key not in field_keys:
            field_keys.add(p.key); field_progs.append(p)

    seeded = sorted(field_progs, key=sc, reverse=True)
    return seeded, champ_keys


def run_bracket(seeded: list[Program], autobids: set[str], *, seed: int,
                fidelity: str = "fast", final_fidelity: str = "full") -> BracketResult:
    """Run the single-elim bracket. The Final (and Semis) use full fidelity."""
    n = 1
    while n < len(seeded):
        n *= 2
    n_seeds = seed_count(len(seeded))
    rank_of = {p.key: i for i, p in enumerate(seeded)}      # 0-based rating rank
    rng = random.Random(seed)
    # Tennis-style draw: top n_seeds protected, everyone else drawn in at random
    # (consumes the rng first, ahead of the match seeds).
    ranks = seeded_draw(len(seeded), n, n_seeds, rng)
    slots = [seeded[r] if r is not None else None for r in ranks]

    def seed_no(rank: int) -> int | None:
        return rank + 1 if rank < n_seeds else None

    res = BracketResult(seeds=seeded, autobids=autobids, n_seeds=n_seeds)
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
            ra, rb = rank_of[a.key], rank_of[b.key]
            hi, lo = (a, b) if ra < rb else (b, a)
            hr, lr = (ra, rb) if ra < rb else (rb, ra)
            fid = final_fidelity if alive <= 4 else fidelity
            w = play_dual(hi, lo, seed=rng.randint(1, 10**9), fidelity=fid)
            m = Matchup(name, hi, lo, seed_no(hr), seed_no(lr), w,
                        winner_is_hi=(w is hi), upset=(w is lo))
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
