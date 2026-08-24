"""
JHSAA individual state tournaments — the flighted preseason championships.

Design: `docs/DESIGN-jhsaa-individual-tournament.md`. The high-school mirror of
`app.individuals` (the NCAA singles/doubles championships), and deliberately the
same shape: entries selected off ability, a single-elimination draw over the
shared `engine.run_tournament`, and a JSON-flattenable result.

WHAT IS DIFFERENT FROM THE COLLEGE EVENT, and why:

  * **FLIGHTED.** Six draws per classification per gender — S1 S2 S3 D1 D2 D3 —
    so a program's #6 player has a title to chase, not just its best. The college
    event pools every program's top two into ONE draw; this one gives each rank
    its own.
  * **PRESEASON.** It runs BEFORE the league season, which is what makes selecting
    on ability honest rather than a violation of the association's "berths are
    earned on court" rule: there are no results yet, so ability is the only input
    there is. It is also what makes the event an INPUT — results credit
    `TeamSeason.records`, so they move `ladder_score` before the first dual and a
    deep run reorders a program's ladder for the season.
  * **NO CUT, NO QUALIFYING.** Every school enters its holder of each flight;
    the field (82-107) sits in a 128 bracket and the top seeds take byes. Talent
    is not evenly distributed geographically (owner rule), so a per-district quota
    would send the wrong players — a strong league's third-best beats a weak
    league's champion.
  * **MIXED DOUBLES is a CONSOLATION event**, one flight and one bracket, one
    entry per school drawn from BELOW #9 — the players the six-flight slate has no
    seat for. See `run_mixed`.
  * **SCORED THE WAY THE COLLEGE INDIVIDUAL CHAMPIONSHIPS ARE.** Not the league
    season's `jhsaa.MATCH_FORMAT` (a full third set) — `individuals.INDIV_FMT`,
    best-of-3 with a **10-point match tiebreak** deciding set, imported rather
    than re-declared so the two events cannot drift. See `INDIV_FORMAT`.

‼️ THE EVENT IS 3 SINGLES + 3 DOUBLES FOR EVERY CLASSIFICATION, INCLUDING 1A.
It is an individual tournament and has NOTHING to do with any dual format — the
1S/4D postseason, the 3S/4D league season and 1A's 2S/3D pilot are all irrelevant
here, and no branch in this module reads a group's dual shape. 1A crowns the same
six individual titles as 9A.

‼️ FLIGHT ENTRIES COME OFF THE ABILITY LADDER, NOT `_arrange_regular`. The league
3S/4D format is doubles-forward and allocates S1 = rank #1, the doubles pool =
ranks #2-#9, and S2/S3 = ranks #10-#11 — so "#2 singles" in a league dual is the
program's TENTH-best player. That mapping is right for a league dual and wrong
here. Preseason there are no results, no `order_of_ability` freeze (it binds from
the first POSTSEASON dual) and no lineup to protect, so entries are simply:

    S1 = #1   S2 = #2   S3 = #3   D1 = #4+#5   D2 = #6+#7   D3 = #8+#9

— nine players, and the SAME nine in every classification. That number belongs to
this event's own 3+3 shape and is not read off any dual format: 1A's road dresses
eight and the league season eleven, and neither is relevant here.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine import run_tournament, simulate_match, simulate_doubles, DoublesTeam
from engine.doubles import doubles_rating
from .individuals import INDIV_FMT

#: The college individual championships' own scoring, IMPORTED — best-of-3, no-ad,
#: set tiebreaks, 10-point match tiebreak for the deciding set. An individual
#: championship is an individual championship; there was no reason to write a
#: second constant, and a copied literal is how two events drift apart. This is
#: the one place JHSAA play differs from `jhsaa.MATCH_FORMAT`, whose third set is
#: a full set.
INDIV_FORMAT = INDIV_FMT

#: Seeds follow the USTA/ITF convention — a quarter of the draw (128 -> 32, 64 -> 16,
#: 32 -> 8). That is exactly what `engine.tournament.seed_count` already does and what
#: `run_tournament` uses by default, so nothing is passed: the default IS the rule.

#: The six flights, in card order. Deliberately the same slot names the duals use,
#: so `FLIGHT_WEIGHTS` prices them with no new entries and the awards need no
#: special case (see the design doc's "full credit" section).
SINGLES_FLIGHTS = ("S1", "S2", "S3")
DOUBLES_FLIGHTS = ("D1", "D2", "D3")
FLIGHTS = SINGLES_FLIGHTS + DOUBLES_FLIGHTS

#: Ability-ladder ranks each flight draws from (0-based) — nine players per school,
#: the SAME for every classification. NOT the league card's allocation, and not tied
#: to any dual format; see the module docstring.
FLIGHT_RANKS = {"S1": (0,), "S2": (1,), "S3": (2,),
                "D1": (3, 4), "D2": (5, 6), "D3": (7, 8)}

#: The main draw's phase. Its own phase because a phase is the archive's identity
#: for an event (the association's own rule) — and deliberately NOT a member of
#: `jhsaa.POSTSEASON`, which is what makes `_phase_weight` treat these as ordinary
#: matches rather than applying `PHASE_WEIGHT`. "Treat them like the regular
#: season" is therefore the default, with nothing to configure.
PHASE = "individual"
#: Mixed doubles is its own event, so its own phase.
MIXED_PHASE = "individual_mixed"

#: Mixed doubles draws from BELOW the nine the main event uses.
MIXED_FROM_RANK = 9


# --- finish banding ---------------------------------------------------------
#
# ‼️ THIS EVENT NEEDS ITS OWN BANDING — `state._finish_short` IS WRONG FOR A 128
# DRAW, and its own docstring explains why it cannot be reused: "every field
# converges on the same 24-team main draw at the Octofinals, so a team still alive
# above 24 went out in the QUALIFIERS… That holds at any field size, which is why
# this needs no field parameter." True for the TEAM event. False here: a 128
# individual draw has no qualifying round and no 24-team convergence, so that
# function would render "Round of 128", "Round of 64" AND "Round of 32" all as
# QUAL — a round nobody played, three distinct rounds collapsed into one label.
#
# So this is a SEPARATE function, not a field parameter bolted onto one that
# documents itself as needing none. The team path is correct and load-bearing;
# do not touch it.
#
#: alive-count -> (long label, short tag). R16 and the Octofinals are the SAME
#: round — the association already says "Octofinals", so OF is the tag and R16 is
#: only its arithmetic name. Never emit both.
FINISH_BANDS = {
    1: ("Champion", "CHAMP"),
    2: ("Runner-up", "F"),
    4: ("Semifinalist", "SF"),
    8: ("Quarterfinalist", "QF"),
    16: ("Octofinalist", "OF"),
    32: ("Round of 32", "R32"),
    64: ("Round of 64", "R64"),
    128: ("Round of 128", "R128"),
}


#: Engine round label -> the association's own. `engine.tournament` names a round
#: by its size ("Round of 16"); the JHSAA has always called that round the
#: OCTOFINALS (the team State draw's own vocabulary), so the two agree on screen.
#: Everything else the engine already names the way this association does.
ROUND_LABELS = {"Round of 16": "Octofinals"}


def round_label(rnd: str) -> str:
    """A draw round as the association writes it, for a bracket column heading."""
    return ROUND_LABELS.get(rnd, rnd)


def finish_band(alive: int) -> tuple[str, str]:
    """(label, tag) for a player still alive in a draw of `alive` — the round they
    went out in. Rounds UP to the next band, so an odd count from a partial first
    round (a 107-entry field is 107 alive, not 128) still reads as R128."""
    for n in sorted(FINISH_BANDS):
        if alive <= n:
            return FINISH_BANDS[n]
    return (f"Round of {alive}", f"R{alive}")


# --- entries ----------------------------------------------------------------

@dataclass
class Entry:
    """One entry in a flight draw — a singles player or a pair, uniformly.

    `players` is the Prospect list (one for singles, two for doubles/mixed), which
    is what lets honours credit BOTH members of a pair the way `honors.py` already
    does for the NCAA doubles title."""
    school: str
    players: list
    engine: object                  # engine Player, or DoublesTeam for a pair
    rating: float
    flight: str

    @property
    def label(self) -> str:
        if len(self.players) == 1:
            return self.players[0].name
        return " / ".join(p.name.split()[-1] for p in self.players)

    @property
    def key(self):
        # The SCHOOL is the identity: one entry per school per flight, and a pair
        # has no single pid. Unique within a draw by construction.
        return self.school

    @property
    def pids(self) -> list:
        return [p.pid for p in self.players]

    @property
    def is_doubles(self) -> bool:
        return len(self.players) > 1


@dataclass
class DrawMatch:
    rnd: str
    hi: Entry
    lo: Entry
    hi_seed: int | None
    lo_seed: int | None
    winner: Entry
    winner_is_hi: bool
    scoreline: str
    upset: bool


@dataclass
class FlightDraw:
    """One flight's completed draw."""
    gender: str
    group: str
    flight: str
    entries: list = field(default_factory=list)      # rating order, [0] = #1 seed
    n_seeds: int = 0
    rounds: list = field(default_factory=list)       # list[list[DrawMatch]]
    champion: Entry | None = None
    runner_up: Entry | None = None

    def seed_of(self, e: Entry) -> int | None:
        i = self.entries.index(e)
        return i + 1 if i < self.n_seeds else None

    def finishes(self) -> dict:
        """{school: (label, tag)} — how far every entry got. Derived from the draw
        rather than stored per entry, so it cannot disagree with the bracket."""
        out: dict = {}
        alive = len(self.entries)
        for rnd in self.rounds:
            for m in rnd:
                loser = m.lo if m.winner_is_hi else m.hi
                out[loser.key] = finish_band(alive)
            alive -= len(rnd)
        if self.champion is not None:
            out[self.champion.key] = FINISH_BANDS[1]
        return out


# --- selection --------------------------------------------------------------

def _ladder(ts) -> list:
    """A program's ability ladder. Preseason `_order` has no results to read, so
    this IS ability order — which is the whole reason selecting on it is honest
    here (see the module docstring)."""
    from .jhsaa import _order
    return _order(ts)


def flight_entry(ts, flight: str) -> Entry | None:
    """A program's entry in `flight`, or None if the roster cannot fill it.

    A pair is two DIFFERENT people, so unlike a dual — where a short side plays
    someone twice rather than 500-ing (`engine.dual._court`) — there is nothing to
    degrade to and the program simply does not enter. `ROSTER_FLOOR` is 16, so in
    practice this never fires; it is here so a hand-edited roster cannot crash a
    statewide draw."""
    ranks = FLIGHT_RANKS[flight]
    ladder = _ladder(ts)
    if len(ladder) <= max(ranks):
        return None
    picks = [ladder[i] for i in ranks]
    if len(picks) == 1:
        eng = picks[0].engine_player()
        return Entry(school=ts.school.name, players=picks, engine=eng,
                     rating=eng.overall, flight=flight)
    a, b = (p.engine_player() for p in picks)
    pair = DoublesTeam(players=(a, b), name=f"{picks[0].name} / {picks[1].name}")
    return Entry(school=ts.school.name, players=picks, engine=pair,
                 rating=doubles_rating(a, b), flight=flight)


def select_field(teams: list, flight: str) -> list:
    """Every program's entry in `flight`, seed-ordered.

    ‼️ NO CUT AND NO DISTRICT QUOTA (owner rule). Talent is not evenly distributed
    geographically, so "top N per league" sends the wrong players — a strong
    league's third-best beats a weak league's champion. The whole field enters and
    `run_tournament` sizes the bracket, byes to the top seeds. Ties break on school
    name so the order is reproducible rather than dict-ordered."""
    out = [e for e in (flight_entry(t, flight) for t in teams) if e is not None]
    out.sort(key=lambda e: (-e.rating, e.school))
    return out


# --- running a draw ---------------------------------------------------------

def _assemble(gender, group, flight, result, played) -> FlightDraw:
    d = FlightDraw(gender=gender, group=group, flight=flight,
                   entries=result.entrants, n_seeds=result.n_seeds)
    for rnd in result.rounds:
        matches = []
        for m in rnd:
            hi, lo = result.entrants[m.hi], result.entrants[m.lo]
            res = played[frozenset((hi.key, lo.key))]
            matches.append(DrawMatch(
                rnd=m.rnd, hi=hi, lo=lo,
                hi_seed=result.seed_no(m.hi), lo_seed=result.seed_no(m.lo),
                winner=result.entrants[m.winner], winner_is_hi=(m.winner == m.hi),
                scoreline=res.scoreline, upset=m.upset))
        d.rounds.append(matches)
    if result.champion_idx is not None:
        d.champion = result.entrants[result.champion_idx]
    if result.runner_up_idx is not None:
        d.runner_up = result.entrants[result.runner_up_idx]
    return d


def run_flight(teams: list, gender: str, group: str, flight: str, *,
               seed: int) -> FlightDraw | None:
    """Select, seed and play one flight's draw. Deterministic: the same
    (teams, gender, group, flight, seed) reproduces the whole bracket."""
    entries = select_field(teams, flight)
    if len(entries) < 2:
        return None
    rng = random.Random(seed)
    played: dict = {}

    def play(ea: Entry, eb: Entry, *, seed: int):
        if ea.is_doubles:
            res = simulate_doubles(ea.engine, eb.engine, seed=seed, fmt=INDIV_FORMAT)
        else:
            res = simulate_match(ea.engine, eb.engine, seed=seed, fmt=INDIV_FORMAT)
        played[frozenset((ea.key, eb.key))] = res
        return ea if res.winner == 0 else eb

    result = run_tournament(entries, seed=rng.randint(1, 10 ** 9), play=play,
                            key=lambda e: e.rating)
    return _assemble(gender, group, flight, result, played)


# --- mixed doubles ----------------------------------------------------------

def mixed_entry(boys_ts, girls_ts) -> Entry | None:
    """A school's ONE mixed pair — its best boy and best girl from BELOW #9.

    ‼️ THE POOL IS BELOW #9, BY DESIGN. This is a CONSOLATION event (owner rule):
    it exists for the players the six-flight main draw has no seat for, not as a
    marquee event pairing the two best players in the school. `ROSTER_FLOOR` is 16
    and the main draw consumes nine, so every roster carries at least 16 − 9 = 7
    below the line in each gender — measured median 8, never fewer than 7. The
    guard below therefore never fires in practice; it exists so a hand-edited
    roster cannot crash the draw.

    ‼️ AND THE FLOOR IS WHY THIS WORKS AT ALL. If `ROSTER_FLOOR` ever drops to 9 or
    below there is no pool and the event silently empties, so the relationship is
    asserted at import (see `jhsaa`'s own `ROSTER_FLOOR` assertion idiom)."""
    b, g = _ladder(boys_ts), _ladder(girls_ts)
    if len(b) <= MIXED_FROM_RANK or len(g) <= MIXED_FROM_RANK:
        return None
    boy, girl = b[MIXED_FROM_RANK], g[MIXED_FROM_RANK]
    eb, eg = boy.engine_player(), girl.engine_player()
    pair = DoublesTeam(players=(eb, eg), name=f"{boy.name} / {girl.name}")
    return Entry(school=boys_ts.school.name, players=[boy, girl], engine=pair,
                 rating=doubles_rating(eb, eg), flight="XD")


def run_mixed(boys_by_school: dict, girls_by_school: dict, group: str, *,
              seed: int) -> FlightDraw | None:
    """The mixed doubles consolation draw for one classification.

    ONE flight, ONE bracket, one entry per school (owner rule) — not a flighted
    ladder. Only schools sponsoring BOTH genders can enter, which is 786 of the
    association's programs."""
    entries = []
    for name in sorted(set(boys_by_school) & set(girls_by_school)):
        e = mixed_entry(boys_by_school[name], girls_by_school[name])
        if e is not None:
            entries.append(e)
    if len(entries) < 2:
        return None
    entries.sort(key=lambda e: (-e.rating, e.school))
    rng = random.Random(seed)
    played: dict = {}

    def play(ea: Entry, eb: Entry, *, seed: int):
        res = simulate_doubles(ea.engine, eb.engine, seed=seed, fmt=INDIV_FORMAT)
        played[frozenset((ea.key, eb.key))] = res
        return ea if res.winner == 0 else eb

    result = run_tournament(entries, seed=rng.randint(1, 10 ** 9), play=play,
                            key=lambda e: e.rating)
    return _assemble("mixed", group, "XD", result, played)


# --- persistence ------------------------------------------------------------

def draw_to_dict(d: FlightDraw) -> dict:
    """Flatten a FlightDraw for the archive. The live objects carry engine players
    that cannot and need not be stored; everything a page needs to render the
    bracket, credit an honour or link a player is kept."""
    def ed(e: Entry | None):
        if e is None:
            return None
        return {"school": e.school, "label": e.label, "seed": d.seed_of(e),
                "players": [{"pid": p.pid, "name": p.name} for p in e.players]}
    fin = d.finishes()
    return {
        "gender": d.gender, "group": d.group, "flight": d.flight,
        "n_seeds": d.n_seeds,
        "entries": [ed(e) for e in d.entries],
        "champion": ed(d.champion), "runner_up": ed(d.runner_up),
        "finishes": {k: {"label": v[0], "tag": v[1]} for k, v in fin.items()},
        "rounds": [[{"rnd": m.rnd, "hi_seed": m.hi_seed, "lo_seed": m.lo_seed,
                     "winner_is_hi": m.winner_is_hi, "scoreline": m.scoreline,
                     "upset": m.upset, "hi": ed(m.hi), "lo": ed(m.lo)}
                    for m in rnd] for rnd in d.rounds],
    }
