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

import hashlib
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

#: How a flight is written out. The chip stays terse (S1) and the heading is the
#: sport's own phrasing — "No. 1 Singles", never "first flight" or "S1 draw"; see
#: CLAUDE.md's VOCABULARY section, which is emphatic that positions are named
#: No. 1 through No. 3.
FLIGHT_NAMES = {"S1": "No. 1 Singles", "S2": "No. 2 Singles", "S3": "No. 3 Singles",
                "D1": "No. 1 Doubles", "D2": "No. 2 Doubles", "D3": "No. 3 Doubles",
                "XD": "Mixed Doubles"}

#: ‼️ ONE DESTINATION, SEVEN VIEWS (owner, 2026-08). The event is reached from the
#: **Championship** sub-rail — beside State, Bracket and TOC — under this label.
#: The flights switch INSIDE that view, as a second sub-rail or a `<select>`;
#: what they are NOT is six items on the Championship rail, or one page with
#: every draw splayed down it. The association's own layout rule is that sibling
#: views of one thing get a switcher, and this is exactly the control a real
#: state association puts on the page ("Select a position: 1S 2S 3S …").
SUBRAIL_LABEL = "Individual State"

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


#: ‼️ A FINISH TIER IS NOT A FINISH — it is how loudly the page should say it (owner
#: layout, 2026-08). The event crowns one champion and everybody else played in it, so
#: an interface that dresses every appearance as an accolade is lying about a career:
#: "the section still matters because making Individual State is part of their record,
#: but the UI doesn't falsely turn every appearance into an accolade."
#:
#:   gold    — the state champion, and nothing else
#:   podium  — runner-up / semifinalist / quarterfinalist: a real finish, said plainly
#:   plain   — R16 and below: a neutral row, no icon and no colour. They were there.
#:
#: ‼️ EVERY TIER GETS A REAL ICON, INCLUDING THE PLAIN ONE (owner, 2026-08: "there's
#: a 1,2,3 and others in there too so you don't have to default to fake bad
#: monograms"). A drawn "R16" disc is a monogram pretending to be a badge; the
#: licensed set has a neutral mark for exactly this, and a plain row stays plain by
#: its COLOUR and layout, not by being denied an icon.
#:
#: The set splits into two families and they are not interchangeable. 1st/2nd/3rd are
#: PODIUM art — a placing. `final8` (a bracket of eight) and `4th` (a die showing
#: four) are ROUND markers — Final 8, Final 4. Semifinalist takes the podium's 3rd
#: because this association plays no third-place match, so both semifinalists ARE
#: third; `4th.png` is therefore unused and is the icon to reach for if a 3/4 playoff
#: is ever added (CHSAA plays one) or if SF is ever re-read as a round rather than a
#: placing.
#:
#: Licensed Noun Project icons live in `data/jhsaa/medals` (owner-supplied), served by
#: `server.jhsaa_medal`.
FINISH_TIERS = {
    "CHAMP": ("gold",   "noun-1st-place-medal-6892193-FFB258.png", "State champion"),
    "F":     ("podium", "noun-second-4146723-9B9B9B.png",          "Runner-up"),
    "SF":    ("podium", "noun-3rd-place-trophy-2347008-a47f00.png", "Semifinalist"),
    "QF":    ("podium", "final8.png",                              "Quarterfinalist"),
}

#: R16 and below: they played, they did not place. Tennis balls, and no honour text.
PLAIN_ICON = "tennisball.png"

#: The panel's own mark — a tennis trophy, for the section rather than a result.
SECTION_ICON = "statetrophy.png"


def finish_tier(tag: str) -> tuple[str, str, str]:
    """(tier, icon file, honour label) for a finish tag. Anything the table does not
    name is `plain` — it played, it did not place — and the empty honour is what
    keeps that row from reading as an accolade."""
    return FINISH_TIERS.get(tag, ("plain", PLAIN_ICON, ""))


def finish_for_index(d: dict, ix: int) -> tuple[str, str]:
    """The finish of ONE entry of an archived draw, addressed by its INDEX.

    ‼️ BY INDEX, NOT THROUGH THE `finishes` MAP, and the reason is renames. That map
    is keyed on the entry's SCHOOL — fine inside a draw, but an archived draw is
    relabelled into today's school names on read (`world._relabel`), and a lookup
    that has to agree with a relabelled key is one rename away from silently missing
    and reporting nothing. The rounds carry indices, which no rename touches.

    Same arithmetic as `FlightDraw.finishes()`: every entrant is alive until the
    round they lose in, and the band is read off how many were still standing when
    that round began."""
    alive = len(d.get("entries") or ())
    for rnd in d.get("rounds") or ():
        for m in rnd:
            if ix in (m["hi"], m["lo"]):
                won = (ix == m["hi"]) == bool(m["winner_is_hi"])
                if not won:
                    return finish_band(alive)
                break
        alive -= len(rnd)
    return FINISH_BANDS[1] if d.get("champion") == ix else finish_band(max(alive, 1))


def entry_index_of(d: dict, pid: str) -> int | None:
    """Which entry of an archived draw a player is in, or None. A pair is two people
    and either of them finds it."""
    for i, e in enumerate(d.get("entries") or ()):
        if any(p.get("pid") == pid for p in (e.get("players") or ())):
            return i
    return None


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
        """The COMPACT label, for a bracket card — surnames only for a pair, which
        is how a draw sheet prints one and what keeps a 300px card readable."""
        if len(self.players) == 1:
            return self.players[0].name
        return " / ".join(p.name.split()[-1] for p in self.players)

    @property
    def full_label(self) -> str:
        """Both people, in full. ‼️ A champion is NAMED, not abbreviated (owner,
        2026-08): the hero on a title page must read "Ava Smith / Noah Hall", never
        the draw sheet's "Smith / Hall". Anywhere the event announces a winner uses
        this; the bracket cards keep `label`."""
        return " / ".join(p.name for p in self.players)

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


def entry_sheet(teams: list) -> dict:
    """`{school: ladder}` resolved ONCE, before any flight is played.

    ‼️ THE LADDER MUST BE FROZEN BEFORE THE FIRST DRAW, and this is not a
    micro-optimisation — reading it per flight is a CORRECTNESS bug. `credit_draw`
    writes results into `ts.records`, and `_order` sorts on `ladder_score(p,
    ts.records.get(p.pid))`, so crediting S1 MOVES the ladder that S2 is then
    selected from. Measured on a real 1A boys field before this existed: **23 of 751
    players were entered in two flights** — a No. 1 who slipped to No. 2 on his own
    S1 result was entered at No. 2 singles as well, while somebody else was entered
    nowhere. Nothing raised; each draw was internally consistent.

    It is also what the event MEANS. Every flight's entry is filed at the same
    moment, in the preseason, off one order of ability — not re-derived after each
    draw as though a program could re-enter halfway through its own championships."""
    return {t.school.name: _ladder(t) for t in teams}


def flight_entry(ts, flight: str, ladder: list | None = None) -> Entry | None:
    """A program's entry in `flight`, or None if the roster cannot fill it.

    A pair is two DIFFERENT people, so unlike a dual — where a short side plays
    someone twice rather than 500-ing (`engine.dual._court`) — there is nothing to
    degrade to and the program simply does not enter. `ROSTER_FLOOR` is 16, so in
    practice this never fires; it is here so a hand-edited roster cannot crash a
    statewide draw.

    `ladder` is the program's frozen entry sheet (`entry_sheet`). It falls back to
    reading the ladder live, which is right for a single lookup but WRONG across a
    slate — see `entry_sheet`."""
    ranks = FLIGHT_RANKS[flight]
    ladder = _ladder(ts) if ladder is None else ladder
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


def select_field(teams: list, flight: str, sheet: dict | None = None) -> list:
    """Every program's entry in `flight`, seed-ordered.

    ‼️ NO CUT AND NO DISTRICT QUOTA (owner rule). Talent is not evenly distributed
    geographically, so "top N per league" sends the wrong players — a strong
    league's third-best beats a weak league's champion. The whole field enters and
    `run_tournament` sizes the bracket, byes to the top seeds. Ties break on school
    name so the order is reproducible rather than dict-ordered."""
    out = [e for e in (flight_entry(t, flight,
                                    (sheet or {}).get(t.school.name))
                       for t in teams) if e is not None]
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
               seed: int, sheet: dict | None = None) -> FlightDraw | None:
    """Select, seed and play one flight's draw. Deterministic: the same
    (teams, gender, group, flight, seed) reproduces the whole bracket.

    Pass `sheet` (from `entry_sheet`) whenever more than one flight is being played
    off these teams — see `entry_sheet` for why leaving it out is a correctness bug
    rather than a slower path."""
    entries = select_field(teams, flight, sheet)
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


def _draw_seed(base: int, *parts: str) -> int:
    """A stable per-draw seed.

    ‼️ NEVER `hash()`. Python salts `hash()` of a str per PROCESS, so a seed built
    that way reproduces a draw only within one interpreter — and this draw is
    ARCHIVED, which means "the same season" has to mean the same thing across
    restarts, not merely inside the run that wrote it. (`run_season`'s own
    `hash(group) % 9973` is an older wart with the same shape; it is not copied
    here and should not be copied anywhere else.)"""
    h = hashlib.blake2s("|".join(("jh-indiv", *parts)).encode(), digest_size=4)
    return (base + int(h.hexdigest(), 16)) % (2 ** 31)


def run_preseason(by_group: dict, gender: str, year: int, *,
                  seed: int = 0) -> dict:
    """Every classification's six flight draws, played and CREDITED, returned
    archive-flattened as `{group: {flight: dict}}`.

    ‼️ IT RUNS BEFORE THE LEAGUE SEASON, WHICH IS WHAT MAKES IT HONEST. Selecting
    entries off ability would be a plain violation of the association's "berths
    are earned on court" rule at any other point in the year. Preseason there are
    no results to earn anything on — `ts.records` is empty, so `_order` IS ability
    order — and the event is therefore an INPUT to the season rather than a
    summary of it: `credit_draw` writes into the same `records` that
    `ladder_score` reads, so a deep run in August moves a player up the ladder
    before the first league dual.

    `by_group` is `run_season`'s own `{group: {district: [TeamSeason]}}`; a flight
    draw is statewide within a classification, so the districts are flattened."""
    out: dict = {}
    for group, districts in by_group.items():
        teams = [t for ts in districts.values() for t in ts]
        by_school = {t.school.name: t for t in teams}
        # ‼️ ONE ENTRY SHEET FOR ALL SIX FLIGHTS, resolved before a ball is struck.
        # Re-reading the ladder per flight lets `credit_draw` reorder it mid-slate
        # and enters somebody twice — see `entry_sheet`.
        sheet = entry_sheet(teams)
        drawn = {}
        for flight in FLIGHTS:
            d = run_flight(teams, gender, group, flight, sheet=sheet,
                           seed=_draw_seed(seed, gender, str(year), group, flight))
            if d is None:                   # fewer than two entries — no event
                continue
            credit_draw(d, by_school)
            drawn[flight] = draw_to_dict(d)
        if drawn:
            out[group] = drawn
    return out


# --- crediting the season ---------------------------------------------------

def credit_draw(draw: FlightDraw, teams: dict) -> int:
    """Credit every match of a completed flight draw to the players who played
    it. Returns the number of appearances credited (two a match).

    ‼️ FULL CREDIT, AND IT COST NO NEW CODE PATH (owner rule): a state individual
    match counts exactly the way a league dual's court does — the same `records`
    W-L that moves `ladder_score`, and the same `matches` résumé row the awards
    read. Three existing decisions are what make that free rather than a special
    case:

      * **The flight names ARE the dual slot names.** `FLIGHT_WEIGHTS` already
        prices S1 above S3 and D1 above D3, so an individual result is weighted
        by the court it was won on with no new entry in that table.
      * **`PHASE` is deliberately NOT in `jhsaa.POSTSEASON`**, so
        `jhsaa_awards._phase_weight` prices these at 1.0 — an ordinary match, not
        a postseason one. "Treat them like the regular season" is the default
        with nothing to configure. (It is still its OWN phase, because a phase is
        the archive's identity for an event — that is what lets a card tag these
        and what keeps them out of `rating_duals`.)
      * **A pair is credited to BOTH members** with `partner` set, which is what
        `jhsaa_awards._pairs` keys a partnership on. A doubles title is a
        partnership's résumé, exactly as it is in a dual.

    ‼️ IT DOES NOT GO THROUGH `jhsaa._credit`. That resolves WHO played by
    slotting a lineup through `_slot_players`, because a dual only records the
    lineup; here the Entry already names the two people, so re-deriving them
    from a lineup would be inventing a lineup to read it back."""
    n = 0
    for rnd in draw.rounds:
        for m in rnd:
            win, lose = (m.hi, m.lo) if m.winner_is_hi else (m.lo, m.hi)
            for side, other, won in ((win, lose, True), (lose, win, False)):
                ts = teams.get(side.school)
                if ts is None:              # a school with no TeamSeason this year
                    continue
                opps = tuple(other.pids)
                for p in side.players:
                    rec = ts.records.setdefault(p.pid, [0, 0])
                    rec[0 if won else 1] += 1
                    ts.by_pid.setdefault(p.pid, p)
                    partner = next((q.pid for q in side.players
                                    if q.pid != p.pid), "")
                    ts.matches.setdefault(p.pid, []).append(
                        (draw.flight, won, PHASE, opps, partner, other.school))
                    n += 1
    return n


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
    association's programs.

    ‼️ IT CREDITS NOTHING — never pass this draw to `credit_draw` (owner rule:
    "mixed doubles gets no credit for anything for awards"). It is also the one
    event played in the SUMMER, after the season it sits beside has finished, so
    there is no open `records`/`matches` for it to land in even if something
    tried. The archive is where a mixed title lives, and the honours page reads
    it from there."""
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


def run_mixed_season(year: int, *, salt: str = "", seed: int = 0) -> dict:
    """The whole association's mixed doubles, one draw per classification,
    archive-flattened as `{group: dict}`.

    ‼️ THE LEAGUE YEAR BEGINS IN JULY (owner rule 2026-08), and that fixes both the
    timing and the rosters. One league year is **summer mixed → fall boys → spring
    girls**, so mixed is the FIRST event of the year, not the last: June's seniors
    have already graduated and it is the RISING squads who take the court. A
    reviewer read the summer date the other way — as a last hurrah for departing
    seniors — which would have needed the previous year's rosters and a
    gender-specific credit policy. It needs neither.

    ‼️ SO IT BUILDS ITS OWN TEAMS, and does NOT take `run_season`'s. Handing it
    `season["teams"]` gave it TeamSeasons whose `records` were full of a season
    that, on this calendar, HAS NOT BEEN PLAYED YET — `_ladder` reads `records`
    through `ladder_score`, so the pool below #9 was cut from a finished ladder for
    an event that opens the year. Fresh `district_teams` have no results, so
    `_order` is ability order, exactly as it is for the six flights.

    ‼️ It still cannot live in `run_season`: that takes ONE gender and a mixed pair
    is one player from each. It runs at the world rung, where `renumber_divisions`
    and `reletter_conferences` also run, for the same reason.

    ‼️ Nothing here credits anything. See `run_mixed`."""
    from .jhsaa import district_teams, load_schools
    # ‼️ THE GROUP IS TAKEN FROM THE BOYS' SCHOOL ROW, which is only correct because
    # a school's two teams always play in the same one — a league belongs to the
    # SCHOOL and is drawn once per classification over every sponsor, so both gender
    # fields read it (CLAUDE.md, league identity). Verified on the real 2041
    # association: 786 schools sponsor both and ZERO have their two teams in
    # different groups. It is an unstated dependency rather than a guarantee, so it
    # is stated here — if a play-up ever moved one gender's team alone, a school
    # would enter the mixed draw of the boys' class with a girl from another.
    boys = {s.name: s for s in load_schools("boys")}
    girls = {s.name: s for s in load_schools("girls")}
    groups: dict = {}
    for name, s in boys.items():
        if name in girls:
            groups.setdefault(s.group, []).append(name)
    out: dict = {}
    for group, names in sorted(groups.items()):
        bt = {t.school.name: t
              for t in district_teams([boys[n] for n in names], year, salt)}
        gt = {t.school.name: t
              for t in district_teams([girls[n] for n in names], year, salt)}
        d = run_mixed(bt, gt, group,
                      seed=_draw_seed(seed, "mixed", str(year), group))
        if d is not None:
            out[group] = draw_to_dict(d)
    return out


# --- persistence ------------------------------------------------------------

def draw_to_dict(d: FlightDraw) -> dict:
    """Flatten a FlightDraw for the archive. The live objects carry engine players
    that cannot and need not be stored; everything a page needs to render the
    bracket, credit an honour or link a player is kept.

    ‼️ A MATCH STORES INDICES INTO `entries`, NEVER COPIES OF THEM. The first
    version wrote the full entrant dict — school, label, seed and both players'
    pid and name — on BOTH sides of every match, so a 128 draw carried each
    entrant up to eight times over and a gender's slate came to **3.5 MB**
    against 1.0 MB indexed. `entries` is already the entrant list and a draw is
    a graph over it; the engine's own `TourneyMatch` indexes it exactly this way.
    A reader resolves with `entries[m["hi"]]`, and `seed` lives on the entry
    because it is a property of the entrant, not of a match it appears in.

    `finishes` is likewise keyed on the entry's `school` — the entry key — so it
    stays a small map rather than a per-round annotation."""
    def ed(e: Entry) -> dict:
        # BOTH labels are stored. `full_label` is derivable from `players`, and it is
        # kept anyway so every surface that announces a champion joins the names the
        # same way rather than each one re-deriving it — the same reason `played`
        # sits beside `lines` on a JV dual.
        # ‼️ GRADE IS ARCHIVED WITH THE ENTRY. An individual result is written NAME,
        # GRADE, SCHOOL (owner, 2026-08 — the OSAA's convention), and the grade is a
        # property of the player IN THAT SEASON: deriving it on read would mean
        # rebuilding a roster for a year that may be a decade old, to recover
        # something the draw already knew. Archives written before this read back
        # with no grade and simply omit it.
        return {"school": e.school, "label": e.label,
                "full_label": e.full_label, "seed": d.seed_of(e),
                "players": [{"pid": p.pid, "name": p.name, "grade": p.grade}
                            for p in e.players]}
    ix = {e.key: i for i, e in enumerate(d.entries)}
    fin = d.finishes()
    return {
        "gender": d.gender, "group": d.group, "flight": d.flight,
        "n_seeds": d.n_seeds,
        "entries": [ed(e) for e in d.entries],
        "champion": ix.get(d.champion.key) if d.champion else None,
        "runner_up": ix.get(d.runner_up.key) if d.runner_up else None,
        "finishes": {k: {"label": v[0], "tag": v[1]} for k, v in fin.items()},
        "rounds": [[{"rnd": m.rnd, "hi": ix[m.hi.key], "lo": ix[m.lo.key],
                     "winner_is_hi": m.winner_is_hi, "scoreline": m.scoreline,
                     "upset": m.upset}
                    for m in rnd] for rnd in d.rounds],
    }
