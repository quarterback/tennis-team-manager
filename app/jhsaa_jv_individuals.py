"""
The JV Individual State Tournaments — two statewide draws per gender.

A VARIANT of `app.jhsaa_individuals`, not a second engine. Selection, the draw,
the match, the finish banding and the archive shape are all that module's (which
is itself the high-school mirror of the college championships in
`app.individuals` — `INDIV_FORMAT` is imported down that chain, never
re-declared, so all three events are scored the same way and cannot drift).
What is new here is exactly three things: who is eligible, a district
qualifying path, and the pigtail pre-round an oversized field needs.

WHAT IS DIFFERENT FROM THE VARSITY INDIVIDUAL EVENT, and why:

  * **CLASSLESS.** Every other JHSAA championship is crowned per classification;
    this one is not. All four draws — Singles and Doubles × boys and girls — are
    one statewide field, so there is exactly ONE JV Singles State Champion and
    ONE JV Doubles State Champion per gender. That is why the archive's group
    key is `GROUP_KEY` rather than a class: there is no class to store.
  * **SENIORS ONLY, AND JV ONLY.** A 12th-grader who is not in the varsity
    eleven. Both halves come off `jhsaa.jv_pool` — the ONE ladder, cut below
    `lineup_need("regular")` — so this invents no roster split of its own and a
    player who played his way onto varsity is, correctly, not JV any more.
  * **QUALIFIED, NOT OPEN.** The varsity flights take every school's holder with
    no cut (talent is not evenly distributed geographically, so a quota would
    send the wrong players). Here the field is small by construction — one
    entry per school, seniors only — so the association can afford to make it
    earned: **win your district**. One champion per district per bracket, no
    at-large, no wild card, no recovery ladder. A district with no eligible
    entrant produces no champion, and the field size therefore moves year to
    year by design.
  * **A 96 MAIN DRAW WITH PIGTAILS.** The field is ~90-100 (one per district,
    ~10 leagues × 9 classes), so it sits either side of the cap. Under 96 it is
    an ordinary seeded draw with byes; over it, the surplus plays in. See
    `_pigtails`.

‼️ IT CREDITS NOTHING, AND IT CANNOT. `JVTeam` has no `records` and no
`matches` by construction (see `jhsaa.JVTeam`), which is the association's
standing guarantee that a JV result never reaches a varsity counter, an award
résumé, TOSS or the ladder. This event holds to that: nothing here writes to a
`TeamSeason`, so it is read-only over the season it runs inside and cannot move
a varsity outcome. It is the same posture `run_mixed` takes, for the same
reason — the archive is where the title lives.

‼️ A DISTRICT TITLE HERE IS AN INDIVIDUAL HONOUR, NOT A ROAD UNIT (owner,
2026-08). The road units — Areas, Sectionals, Wards, Regionals, Zonals and the
recovery rounds — are TEAM units the title board counts. A District JV Singles
or Doubles champion is a player's and their school's individual honour, so it is
recorded on the ENTRY (`Entry.district`, archived with the state field) and
NOTHING is added to `jhsaa_title_stages` or the road ladder.
"""
from __future__ import annotations

import random

from engine import run_tournament, simulate_match, simulate_doubles, DoublesTeam
from engine.doubles import doubles_rating
from .jhsaa_individuals import (INDIV_FORMAT, DrawMatch, Entry, FlightDraw,
                                _assemble, _draw_seed, draw_to_dict)

#: The two brackets. Terse keys, because they are archived as the `flight` column
#: beside the varsity S1-D3 — the same slot the association's own vocabulary
#: names a position with.
SINGLES = "JVS"
DOUBLES = "JVD"
BRACKETS = (SINGLES, DOUBLES)

#: How a bracket is written out. The association names positions No. 1 through
#: No. 3 and this event has only one of each, so no number appears.
BRACKET_NAMES = {SINGLES: "JV Singles", DOUBLES: "JV Doubles"}

#: ‼️ THE DISTRICT QUALIFIERS ARE THEIR OWN EVENT KEY, and that is what keeps
#: them out of every reader that counts a STATE title. They are archived in the
#: same table and the same draw shape as the state draws — the qualifying round
#: of a tournament is a real bracket with real results, and it is what a district
#: page is asked for — but a district championship is not a state championship,
#: and `world_jhsaa_individual` is keyed on `flight`. Given the SAME key as the
#: state draw, ninety-five district champions a bracket would have counted as
#: state champions on the career repeat roll, which reads every flight it knows.
#:
#: So the flight IS the distinction, exactly as a PHASE is the archive's identity
#: for an event everywhere else in this association: a reader that does not know
#: `DJVS`/`DJVD` drops them by construction rather than by remembering to filter.
DISTRICT_SINGLES = "DJVS"
DISTRICT_DOUBLES = "DJVD"
DISTRICT_BRACKETS = (DISTRICT_SINGLES, DISTRICT_DOUBLES)

#: state bracket -> its district qualifier's key, and back.
DISTRICT_OF = {SINGLES: DISTRICT_SINGLES, DOUBLES: DISTRICT_DOUBLES}
STATE_OF = {v: k for k, v in DISTRICT_OF.items()}

DISTRICT_NAMES = {DISTRICT_SINGLES: "District JV Singles",
                  DISTRICT_DOUBLES: "District JV Doubles"}

#: Its own phase, because a phase is the archive's identity for an EVENT — the
#: rule the JV season itself had to learn when its showcase was indistinguishable
#: from an invitational. Deliberately NOT in `jhsaa.POSTSEASON`: membership of
#: that set drives the dual shape, the Order of Ability freeze, the TOSS
#: exclusion and the calendar lane, none of which an individual JV draw has.
PHASE = "jv_individual"

#: The archive's group key. The event is CLASSLESS, so there is no classification
#: to store and a real one must never be invented — 'ALL' is a value no
#: `jhsaa.GROUPS` entry can collide with, which is what keeps the group-scoped
#: readers (`jhsaa_individual_champions`, `jhsaa_individual_results`) from ever
#: serving a JV draw under a class heading.
GROUP_KEY = "ALL"

#: Twelfth grade. `jhsaa` keys graduation off exactly this comparison.
SENIOR_GRADE = 12

#: Who may enter, PER BRACKET (owner rule 2026-08). Singles is the seniors' event.
#: Doubles takes **juniors and seniors**, and the reason is arithmetic rather than
#: sentiment: a pair needs three eligible players deep (the school's JV No. 1
#: plays singles, the next two pair), and a JV pool is the roster below the
#: varsity eleven — measured across three classifications, ~72% of programs have a
#: JV senior at all and only ~14% have three, so a seniors-only doubles bracket
#: left most of the association unable to enter and some districts with no
#: champion to send. Eleventh grade opens it without touching the singles rule.
ELIGIBLE_GRADES = {SINGLES: (SENIOR_GRADE,), DOUBLES: (11, SENIOR_GRADE)}

#: The main draw. Not a bracket SIZE — `run_tournament` pads to the next power of
#: two (96 -> 128) and byes the top seeds, exactly as the varsity 128 draw does
#: with its 82-107 field. It is the cap on how many entrants reach that draw;
#: everyone beyond it plays in. See `_pigtails`.
MAIN_DRAW = 96

#: How many players an entry is. `jhsaa_individuals` states this as fixed RANKS
#: because all six of its flights draw from one pool; here the two brackets have
#: DIFFERENT pools (see `ELIGIBLE_GRADES`), so the rule is stated as a size and
#: `school_entry` takes the top of each bracket's own pool.
ENTRY_SIZE = {SINGLES: 1, DOUBLES: 2}


# --- eligibility ------------------------------------------------------------

def jv_ladder(ts) -> list:
    """A program's JV players, in ladder order.

    ‼️ IT IS `jhsaa.jv_pool` AND NOTHING ELSE — the one ladder cut below
    `lineup_need("regular")`, which is the association's only definition of a JV
    player and the one the whole JV season staffs from. No second roster split is
    invented here, so a player who played his way onto varsity is correctly no
    longer JV.

    The ORDER is what makes "JV No. 1" mean something: it is `ladder_score` —
    ability moved by results — so a school's entry is its ESTABLISHED position,
    not a coach's pick. That is the same anti-sandbagging property the varsity
    individual event gets from selecting off `_order`.
    """
    from .jhsaa import jv_pool
    return jv_pool(ts)


def jv_eligible(ts, bracket: str, ladder: list | None = None) -> list:
    """The JV players a school may enter in `bracket`, in ladder order — seniors
    for singles, juniors and seniors for doubles (`ELIGIBLE_GRADES`)."""
    grades = ELIGIBLE_GRADES[bracket]
    pool = jv_ladder(ts) if ladder is None else ladder
    return [p for p in pool if p.grade in grades]


def jv_seniors(ts, ladder: list | None = None) -> list:
    """The singles bracket's pool: a program's JV twelfth-graders, in ladder
    order. `grade == 12` is the same comparison the graduation hand-off makes."""
    return jv_eligible(ts, SINGLES, ladder)


def entry_sheet(teams: list) -> dict:
    """`{school: JV ladder}`, resolved ONCE before any draw is played.

    The varsity event freezes its sheet because `credit_draw` moves the ladder
    that the next flight is selected from, and re-reading it entered 23 players
    in two flights. Nothing here credits anything, so this cannot happen — but
    the sheet is frozen anyway, and for a reason of its own: a school's singles
    entry and doubles pair must come off ONE reading of that school's ladder, and
    the two brackets are played one after the other over the same teams.
    """
    return {t.school.name: jv_ladder(t) for t in teams}


def school_entry(ts, bracket: str, *, district: str = "",
                 ladder: list | None = None) -> Entry | None:
    """A school's entry in `bracket`, or None if too few of its JV are eligible.

    A school with nobody eligible simply enters nobody that year (owner rule) —
    which is also true of a school one player short in the doubles bracket, since
    a pair is two DIFFERENT people and there is nothing to degrade to.

    ‼️ THE SINGLES ENTRANT IS HELD OUT OF THE PAIR. The two brackets are one
    event, so a school fields three different people exactly as the varsity
    flights do — its JV No. 1 in singles, then the best two of what is left. Now
    that the pools differ (doubles reaches down a grade) that has to be said
    rather than fall out of disjoint rank tuples: a senior JV No. 1 is at the top
    of BOTH pools and would otherwise enter twice.
    """
    pool = jv_ladder(ts) if ladder is None else ladder
    singles = jv_eligible(ts, SINGLES, pool)
    held = {singles[0].pid} if singles else set()
    picks = [p for p in jv_eligible(ts, bracket, pool)
             if bracket == SINGLES or p.pid not in held][:ENTRY_SIZE[bracket]]
    if len(picks) < ENTRY_SIZE[bracket]:
        return None
    if len(picks) == 1:
        eng = picks[0].engine_player()
        return Entry(school=ts.school.name, players=picks, engine=eng,
                     rating=eng.overall, flight=bracket, district=district)
    a, b = (p.engine_player() for p in picks)
    pair = DoublesTeam(players=(a, b), name=f"{picks[0].name} / {picks[1].name}")
    return Entry(school=ts.school.name, players=picks, engine=pair,
                 rating=doubles_rating(a, b), flight=bracket, district=district)


def district_label(group: str, district: str) -> str:
    """A district's FULL identity, written out.

    ‼️ `(CLASSIFICATION, name)`, never the bare name. The JHSAA reuses its
    district names at every level — "Halbrook Basin District" is five different
    leagues — and this string is what a classless state draw carries to say where
    an entry qualified, so the class cannot be dropped from it.
    """
    return f"{group} {district}"


def district_field(teams: list, bracket: str, *, group: str, district: str,
                   sheet: dict | None = None) -> list:
    """Every eligible school's entry in one district, seed-ordered.

    Ties break on school name, so the order is reproducible rather than
    dict-ordered — `select_field`'s rule, for the same reason.
    """
    label = district_label(group, district)
    out = [e for e in (school_entry(t, bracket, district=label,
                                    ladder=(sheet or {}).get(t.school.name))
                       for t in teams) if e is not None]
    out.sort(key=lambda e: (-e.rating, e.school))
    return out


# --- playing a draw ---------------------------------------------------------

def _play(played: dict):
    """The `run_tournament` callback, recording each result for `_assemble`.

    Singles and doubles differ only in which simulator runs; both take
    `INDIV_FORMAT` — the college championships' own best-of-3, no-ad, full third
    set — so a pigtail, a district qualifier and a state final are all scored
    identically, and none of them hardcodes a set or tiebreak rule.
    """
    def play(ea: Entry, eb: Entry, *, seed: int):
        sim = simulate_doubles if ea.is_doubles else simulate_match
        res = sim(ea.engine, eb.engine, seed=seed, fmt=INDIV_FORMAT)
        played[frozenset((ea.key, eb.key))] = res
        return ea if res.winner == 0 else eb
    return play


def run_district(teams: list, bracket: str, *, gender: str, group: str,
                 district: str, seed: int,
                 sheet: dict | None = None) -> FlightDraw | None:
    """One district's JV senior qualifier, or None if nobody is eligible.

    The whole qualifying path, and it is `run_tournament` doing the work: a
    district is a small field, so a mini-draw over it needs nothing the state
    draw does not already use.

    ‼️ ONE ELIGIBLE SCHOOL IS A CHAMPION, NOT AN EMPTY DRAW. `run_tournament`
    already returns a lone entrant as champion with no rounds, which is what a
    district with one entry means: they qualify unopposed. That is why the guard
    below is `not entries` and not `len(entries) < 2` — the varsity `run_flight`
    uses the latter because a one-entry flight there would crown a state champion
    who never played, and here it only fills a district seat.
    """
    entries = district_field(teams, bracket, group=group, district=district,
                             sheet=sheet)
    if not entries:
        return None
    rng = random.Random(seed)
    played: dict = {}
    result = run_tournament(entries, seed=rng.randint(1, 10 ** 9),
                            play=_play(played), key=lambda e: e.rating)
    return _assemble(gender, district_label(group, district), bracket,
                     result, played)


def district_qualifiers(by_group: dict, bracket: str, *, gender: str,
                        year: int, seed: int,
                        sheet: dict | None = None) -> list:
    """Every district's qualifier for `bracket`, in order — the whole qualifying
    round, as played.

    ‼️ IT RETURNS THE DRAWS, NOT JUST THE CHAMPIONS. The first version plucked
    `d.champion` off each and dropped the draw on the floor, which threw away the
    only record of how ninety-five brackets were actually won — a district
    championship is a real title with a real final, and a district page is asked
    for exactly that. Keeping them is ~2.8 KB a draw, ~1 MB a season across both
    brackets and both genders, measured, against the 1.7 MB a gender the varsity
    draws already cost. Nothing justified discarding them.

    `by_group` is `run_season`'s own `{group: {district: [TeamSeason]}}`, walked
    in sorted order so the field is assembled identically on every run.
    """
    out = []
    for group, dists in sorted(by_group.items()):
        for district, teams in sorted(dists.items()):
            d = run_district(teams, bracket, gender=gender, group=group,
                             district=district, sheet=sheet,
                             seed=_draw_seed(seed, "jv", str(year), gender,
                                             bracket, group, district))
            if d is not None:
                out.append(d)
    return out


def champions_of(draws: list) -> list:
    """The state field: the champion of every district draw that crowned one.

    FLATTENED across classifications — the state draw is classless, so a 1A
    champion and a 9A champion enter it on the same terms."""
    return [d.champion for d in draws if d.champion is not None]


# --- the pigtail pre-round --------------------------------------------------

#: The pre-round's own label. It is a round of the draw and archives as one, so
#: it is named the way `engine.tournament` names the rest ("Round of 32",
#: "Quarterfinals") rather than tagged onto the front of the first main round.
PIGTAIL_ROUND = "Play-in"


def _prelim_layers(n_field: int) -> list[int]:
    """The field size each preliminary round reduces to, in order.

    ‼️ LAYERS, NOT CHAINS, AND THAT IS A CORRECTNESS RULE RATHER THAN A STYLE
    ONE. The first version hung extra play-in matches off a seed LINE once the
    field passed 192 — a chain of three entrants on one line, both its matches
    stored in the same round. `jhsaa_individuals.finish_for_index` reads a
    finish by scanning each round for the entrant and STOPPING at the first
    match it finds them in, which is sound only if nobody appears twice in one
    round; a chained entrant who won and then lost was read as still alive, and
    could be reported champion on their own player page. Storing each layer as
    its own round makes "at most once per round" true by construction instead of
    asking every reader to allow for it.

    The rule (owner, 2026-08): keep building pre-rounds until the field is
    `MAIN_DRAW`, and a round may not more than halve the field — so each layer
    lands on the smallest 96·2^k that one round can reach.

        97-192   -> one layer      193-384  -> two
        385-768  -> three          769-1536 -> four

    Worked, at the owner's own examples. **200**: round 1 eliminates 8 (the
    bottom 16 seeds pair off; the other 184 bye through the layer) leaving 192,
    round 2 plays 96 to leave 96. **250**: 58 matches, then 96. **384**: 192
    matches, then 96.
    """
    out: list[int] = []
    cur = n_field
    while cur > MAIN_DRAW:
        nxt = MAIN_DRAW
        # A single elimination round cannot more than halve a field.
        while nxt < (cur + 1) // 2:
            nxt *= 2
        out.append(nxt)
        cur = nxt
    return out


def _prelim_pairs(field: list, target: int) -> tuple[list, list]:
    """ONE preliminary layer over a seed-ordered `field`, as
    `(entrants who bye through it, [(line, entrant, entrant), …])`.

    Only the bottom of the field plays: reducing to `target` needs
    `len(field) - target` matches, so exactly twice that many entrants — the
    lowest seeds — pair off and everyone above them byes through untouched. The
    pairing mirrors that pool, strongest against weakest, which makes every line
    the same combined seed so no top seed draws a systematically softer one.

    Lines are numbered from 1 in order, which is the "assigned to seeds 1, 2,
    3 …" rule; a layer never needs more lines than the layer it feeds, so
    nothing wraps.

    At 100 entrants that is the four pairings the spec names — (93, 100),
    (94, 99), (95, 98), (96, 97) — and at 97, the single (96, 97).
    """
    m = len(field) - target
    if m <= 0:
        return list(field), []
    cut = len(field) - 2 * m
    direct, pool = list(field[:cut]), list(field[cut:])
    pairs = [(i + 1, pool[i], pool[len(pool) - 1 - i]) for i in range(m)]
    return direct, pairs


# --- the state draw ---------------------------------------------------------

def run_state(champions: list, bracket: str, *, gender: str,
              seed: int) -> FlightDraw | None:
    """One classless state draw over the district champions.

    The field is seeded on the same rating the varsity individual event seeds on
    — a player's overall, a pair's `doubles_rating` — since every entrant here
    arrived the same way and there is nothing else to separate them by.

    ‼️ HOW MANY ARE SEEDED IS THE USTA CONVENTION AND IS NOT SET HERE: a quarter
    of the padded draw, so 128 seeds 32, 64 seeds 16 and 32 seeds 8. That is
    exactly `engine.tournament.seed_count`, which `run_tournament` applies by
    default — nothing is passed to `seeds=`, so the default IS the rule and this
    event cannot drift from the varsity flights or the college championships,
    which get it the same way. A ~96 field pads to 128 and therefore seeds 32.
    """
    if len(champions) < 2:
        return None
    by_rating = lambda e: (-e.rating, e.school)          # noqa: E731
    cur = sorted(champions, key=by_rating)
    rng = random.Random(seed)
    played: dict = {}
    play = _play(played)
    pre_rounds: list = []
    eliminated: list = []
    # ‼️ ONE STORED ROUND PER LAYER — see `_prelim_layers`. Each layer eliminates
    # every one of its players exactly once, so nobody can appear twice in a
    # round and `finish_for_index`'s scan (which stops at the first match it
    # finds an entrant in) reads the right finish for all of them.
    for target in _prelim_layers(len(cur)):
        direct, pairs = _prelim_pairs(cur, target)
        matches, survivors = [], []
        for line, a, b in pairs:
            hi, lo = (a, b) if by_rating(a) <= by_rating(b) else (b, a)
            win = play(hi, lo, seed=rng.randint(1, 10 ** 9))
            matches.append(DrawMatch(
                rnd=PIGTAIL_ROUND, hi=hi, lo=lo, hi_seed=None, lo_seed=None,
                winner=win, winner_is_hi=(win is hi),
                scoreline=played[frozenset((hi.key, lo.key))].scoreline,
                upset=(win is lo), seed_line=line))
            survivors.append(win)
            eliminated.append(lo if win is hi else hi)
        pre_rounds.append(matches)
        cur = sorted(direct + survivors, key=by_rating)
    result = run_tournament(cur, seed=rng.randint(1, 10 ** 9),
                            play=play, key=lambda e: e.rating)
    d = _assemble(gender, GROUP_KEY, bracket, result, played)
    if pre_rounds:
        # ‼️ THE ELIMINATED PLAY-IN LOSERS ARE APPENDED, NOT MERGED IN RATING
        # ORDER. `_assemble` set `entries` to the main draw's seed order and
        # every archived match indexes into it, so inserting anybody would move
        # an index the rounds already point at. Appending keeps every main-draw
        # index exactly where `run_tournament` put it, leaves the losers below
        # `n_seeds` (so `seed_of` correctly reports them unseeded), and makes
        # `len(entries)` the true field — which is what `finishes()` counts down
        # from, so a play-in loser bands as the round they actually went out in.
        d.entries = list(d.entries) + eliminated
        for rnd in reversed(pre_rounds):
            d.rounds.insert(0, rnd)
    return d


def run_jv_state(by_group: dict, gender: str, year: int, *,
                 seed: int = 0) -> dict:
    """Both of a gender's JV state tournaments AND their qualifying rounds,
    archive-flattened as `{"state": {bracket: dict}, "districts": {bracket:
    {district identity: dict}}}`.

    The district draws are keyed by their FULL identity (`district_label` —
    `(classification, name)`, never the bare name, since the JHSAA reuses its
    district names at every level), which is also the key they are archived
    under.

    ‼️ IT READS THE SEASON AND WRITES NOTHING TO IT. `jv_pool` reads `_order`, so
    this must run after the varsity regular season for the ladder to mean
    anything — but it credits nobody, mutates no `TeamSeason`, and takes its
    randomness from its own `Random`, so no varsity result, seeding or
    development outcome can move because this event exists.
    """
    teams = [t for dists in by_group.values() for ts in dists.values()
             for t in ts]
    sheet = entry_sheet(teams)
    state: dict = {}
    districts: dict = {}
    for bracket in BRACKETS:
        quals = district_qualifiers(by_group, bracket, gender=gender, year=year,
                                    seed=seed, sheet=sheet)
        districts[bracket] = {d.group: draw_to_dict(d) for d in quals}
        d = run_state(champions_of(quals), bracket, gender=gender,
                      seed=_draw_seed(seed, "jv-state", str(year), gender,
                                      bracket))
        if d is not None:
            state[bracket] = draw_to_dict(d)
    return {"state": state, "districts": districts}
