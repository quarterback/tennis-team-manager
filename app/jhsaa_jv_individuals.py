"""
The JV Individual State Tournaments — two statewide draws per gender.

A VARIANT of `app.jhsaa_individuals`, not a second engine. Selection, the draw,
the match, the finish banding and the archive shape are all that module's (which
is itself the high-school mirror of the college championships in
`app.individuals` — `INDIV_FORMAT` is imported down that chain, never
re-declared, so all three events are scored the same way and cannot drift).
What is new here is exactly three things: who is eligible, the qualifying
pathway into a full 128 draw, and the defending champion's autobid.

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
  * **A FULL 128 DRAW, BUILT FROM THREE SOURCES** (owner rule 2026-09, the
    association having judged the event a success). Jefferson has ~95 districts
    and a 128 draw needs more entrants than that, so the field is the Grand Slam
    shape: district champions, ONE defending-champion autobid, and Regional
    Qualifying winners drawn from every district's RUNNER-UP. See `run_jv_state`.

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
from engine.tournament import seed_count
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

#: ‼️ A FULL 128 DRAW (owner rule 2026-09, the association having judged the event
#: a success). Not a cap on a smaller field any more — an EXACT size the three entry
#: sources are built to fill: district champions, one defending-champion autobid,
#: and Regional Qualifying winners. See `run_jv_state`.
STATE_FIELD = 128

#: Berths the defending champion's PROGRAM receives on top of its district entry.
#: One, and it belongs to the school rather than to the player who won it — a JV
#: roster turns over every year, so a bid held by a person would lapse the moment
#: they graduated, which for a seniors-only bracket is always.
TOC_AUTOBIDS = 1

#: The qualifying draws' own archive keys — a third event key beside the state and
#: district ones, for the reason the district ones exist: `world_jhsaa_individual`
#: is keyed on `flight`, and a qualifying round is neither a state title nor a
#: district title. A reader that does not know these drops them by construction.
QUAL_SINGLES = "QJVS"
QUAL_DOUBLES = "QJVD"
QUAL_BRACKETS = (QUAL_SINGLES, QUAL_DOUBLES)
QUAL_OF = {SINGLES: QUAL_SINGLES, DOUBLES: QUAL_DOUBLES}
QUAL_NAMES = {QUAL_SINGLES: "JV Singles Qualifying",
              QUAL_DOUBLES: "JV Doubles Qualifying"}

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
                 ladder: list | None = None,
                 exclude: frozenset = frozenset()) -> Entry | None:
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

    `exclude` drops players who already hold a seat in this event's field, so the
    caller can ask for the school's best REMAINING entry. That is what the
    defending champion's autobid needs: the bid is a SECOND entry, and if the
    school's best player is already in through the district then the best
    ELIGIBLE entry for the bid is the next one down — otherwise the bid would
    duplicate a player who cannot occupy two seats, and quietly go unused in
    exactly the year the program earned it.
    """
    pool = jv_ladder(ts) if ladder is None else ladder
    singles = jv_eligible(ts, SINGLES, pool)
    held = {singles[0].pid} if singles else set()
    picks = [p for p in jv_eligible(ts, bracket, pool)
             if (bracket == SINGLES or p.pid not in held)
             and p.pid not in exclude][:ENTRY_SIZE[bracket]]
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
# --- REGIONAL QUALIFYING (owner spec 2026-09) --------------------------------
#
# The association expanded the event to a full 128 draw, and a 128 draw needs more
# entrants than Jefferson has districts. So the field is built from THREE sources,
# the shape of a Grand Slam:
#
#     district champions  +  1 defending-champion autobid  +  qualifiers  =  128
#
# Every district also sends its RUNNER-UP to Regional Qualifying, and that pool plays
# down to exactly the number of seats the first two sources leave open.
QUALIFYING_ROUND = "Qualifying"
FINAL_QUALIFYING_ROUND = "Final Qualifying"


def qualifying_spots(n_champions: int, autobids: int = 0) -> int:
    """Seats left in the State draw for qualifiers: `STATE_FIELD` minus the direct
    entries. Never negative — an association that ever grows past 128 districts has
    outgrown this shape, and `run_jv_state` says so loudly rather than quietly
    playing a qualifying tournament for no seats."""
    return max(0, STATE_FIELD - n_champions - autobids)


def qualifying_rounds(n_entries: int, spots: int) -> list[int]:
    """Matches per qualifying round, reducing `n_entries` to exactly `spots`.

    ‼️ THE SHAPE IS THE SPEC'S, NOT THE OBVIOUS ONE. A generic play-down would
    halve the field each round; qualifying instead aims straight at a FINAL ROUND OF
    `2 × spots`, so the last round is complete — every match in it produces one
    qualifier, which is what "win your last one and you are in" means at a slam.
    Everything before it is an opening round with a lot of byes.

    So the opening round plays `Q - 2S` matches and byes the rest, leaving `2S`; the
    final round plays `S`. The owner's own worked examples, reproduced exactly:

        Q=95, S=32 -> [31, 32]   62 play, 33 bye, 64 remain, 32 qualify
        Q=94, S=33 -> [28, 33]   56 play, 38 bye, 66 remain, 33 qualify
        Q=96, S=31 -> [34, 31]   68 play, 28 bye, 62 remain, 31 qualify

    Below `2S` runners-up the opening round is unnecessary and the final round
    carries byes instead (a real qualifying draw does the same when it is short of
    entries). Above `4S` a round cannot pair everyone it would need to, so another
    round is added — the loop handles it rather than a special case.
    """
    out: list[int] = []
    cur = n_entries
    while cur > spots > 0:
        target = 2 * spots if cur > 2 * spots else spots
        m = min(cur - target, cur // 2)
        if m <= 0:
            break
        out.append(m)
        cur -= m
    return out


def _round_pairs(field: list, target: int) -> tuple[list, list]:
    """ONE round over a seed-ordered `field`, as `(entrants who bye, [(line, a,
    b)])`.

    Only the BOTTOM of the field plays: reducing to `target` needs
    `len(field) - target` matches, so exactly twice that many entrants — the
    lowest seeds — pair off and everyone above them byes through. That is what
    "seed the draw and assign the byes on the ranking" means, and it is the rule
    for every play-down in this module.

    The pairing MIRRORS that pool, strongest against weakest, so every match in
    the round carries the same combined seed and no top seed draws a
    systematically softer one. Lines are numbered from 1 in order.
    """
    m = len(field) - target
    if m <= 0:
        return list(field), []
    cut = len(field) - 2 * m
    direct, pool = list(field[:cut]), list(field[cut:])
    pairs = [(i + 1, pool[i], pool[len(pool) - 1 - i]) for i in range(m)]
    return direct, pairs


def _play_down(field: list, targets: list, played: dict, rng: random.Random,
               names: list) -> tuple[list, list]:
    """Play a seeded field down through successive rounds. Returns
    `(survivors, [DrawMatch rounds])`.

    Each round pairs the BOTTOM of the field and byes the top (`_round_pairs`),
    which is what "seed the draw and assign the byes on the ranking" means — the
    same helper, and the same mirror pairing, every play-down here uses."""
    play = _play(played)
    rounds = []
    cur = list(field)
    for i, m in enumerate(targets):
        direct, pairs = _round_pairs(cur, len(cur) - m)
        matches, survivors = [], []
        for line, a, b in pairs:
            hi, lo = (a, b) if (-a.rating, a.school) <= (-b.rating, b.school) else (b, a)
            win = play(hi, lo, seed=rng.randint(1, 10 ** 9))
            matches.append(DrawMatch(
                rnd=names[min(i, len(names) - 1)], hi=hi, lo=lo,
                hi_seed=None, lo_seed=None, winner=win,
                winner_is_hi=(win is hi),
                scoreline=played[frozenset((hi.key, lo.key))].scoreline,
                upset=(win is lo), seed_line=line))
            survivors.append(win)
        rounds.append(matches)
        cur = sorted(direct + survivors, key=lambda e: (-e.rating, e.school))
    return cur, rounds


def run_qualifying(runners_up: list, bracket: str, *, gender: str, spots: int,
                   seed: int) -> tuple[list, FlightDraw | None]:
    """Regional Qualifying: every district runner-up, played down to `spots`.

    Returns `(qualifiers, draw)` — the draw is archived in its own right, because a
    qualifying tournament is a tournament: it has its own seeds, its own rounds and
    its own losers, and a player who came within one match of the State draw has a
    result worth keeping.
    """
    if spots <= 0 or len(runners_up) < 2:
        return list(runners_up[:max(0, spots)]), None
    field = sorted(runners_up, key=lambda e: (-e.rating, e.school))
    rounds = qualifying_rounds(len(field), spots)
    rng = random.Random(seed)
    played: dict = {}
    # The LAST round is the final qualifying round; everything before it is the
    # opening. Named so the archive can say which is which.
    names = ([QUALIFYING_ROUND] * (len(rounds) - 1)) + [FINAL_QUALIFYING_ROUND] \
        if rounds else []
    survivors, played_rounds = _play_down(field, rounds, played, rng, names or
                                          [QUALIFYING_ROUND])
    d = FlightDraw(gender=gender, group=GROUP_KEY, flight=QUAL_OF[bracket],
                   entries=list(field), n_seeds=seed_count(len(field)))
    d.rounds = played_rounds
    return survivors, d


# --- the state draw ---------------------------------------------------------

def runners_up_of(draws: list) -> list:
    """Every district's RUNNER-UP — the Regional Qualifying field.

    A district that crowned a champion unopposed has no runner-up and sends
    nobody, which is why this is not simply "the field minus the champions"."""
    return [d.runner_up for d in draws if d.runner_up is not None]


def defending_program(gender: str, bracket: str, season_year: int) -> str:
    """The school holding this event's autobid — the program that won LAST
    season's JV state title in this bracket, or "" when there is no prior season.

    ‼️ THE BID BELONGS TO THE PROGRAM, NOT THE PLAYER, and for this event that is
    forced rather than stylistic: singles is seniors-only, so the champion has
    graduated by the time the bid would be used. The school spends it on its best
    eligible entry, which is what `school_entry` already returns.

    ‼️ IT READS THE ARCHIVE, which is the only place a previous season exists —
    a season is memoised but not retained, and re-simulating last year to learn
    one name would cost a full association pass. Same idiom as
    `jhsaa.school_exposure`: resolve the db path, resolve THE world (the oldest
    row — one real world per save), read, and cache. Absent archive reads as no
    autobid, which is what a world's first JV season must see.
    """
    from .jhsaa import _expo_world_id
    from .dbpath import resolve_db_path
    db = resolve_db_path()
    key = (db, gender, bracket, season_year)
    got = _defend_cache.get(key)
    if got is not None:
        return got
    out = ""
    wid = _expo_world_id(db)
    if wid is not None:
        import json
        import sqlite3
        try:
            conn = sqlite3.connect(db)
            try:
                # `json_extract` for the champion alone — a draw is a ~30KB blob
                # and this wants one school name out of it. The archive stores
                # `champion` as an INDEX into `entries`, so json1 reaches it
                # directly; the whole-blob parse is the one-gthread hazard this
                # section keeps relearning.
                # ‼️ THE NEWEST ARCHIVED DRAW IS LAST SEASON'S, and that is the
                # whole lookup — no season-year arithmetic. This runs while the
                # current season is being played, so nothing for it is archived
                # yet; the latest row for this gender and bracket is therefore the
                # one that just finished. Matching on a computed season year
                # instead would have to reconcile the archive's WORLD-year key
                # with `run_season`'s season year, which are different numbers.
                r = conn.execute(
                    "SELECT json_extract(data, '$.entries[' ||"
                    "  json_extract(data, '$.champion') || '].school') AS s"
                    " FROM world_jhsaa_individual WHERE world_id=? AND gender=?"
                    "  AND grp=? AND flight=?"
                    "  AND json_extract(data, '$.champion') IS NOT NULL"
                    " ORDER BY year DESC LIMIT 1",
                    (wid, gender, GROUP_KEY, bracket)).fetchone()
                out = (r[0] or "") if r else ""
            finally:
                conn.close()
        except sqlite3.Error:
            out = ""
    _defend_cache[key] = out
    return out


_defend_cache: dict = {}


def autobid_entry(school: str, bracket: str, teams: dict,
                  sheet: dict | None = None,
                  taken: frozenset = frozenset()) -> Entry | None:
    """The defending program's autobid entry — its best eligible entry in this
    bracket, which is the SAME selection every other school makes.

    ‼️ A SECOND ENTRY FROM ONE SCHOOL, DELIBERATELY. The program keeps its normal
    district pathway, so a defending champion can hold two seats in the draw: for
    singles two players from one school, for doubles two pairs. That is the point
    of the bid, and it is why the state draw separates same-school entries (see
    `run_state`). Returns None if the school no longer fields an eligible entry,
    which a JV roster can easily fail to do a year later.
    """
    ts = teams.get(school)
    if ts is None:
        return None
    return school_entry(ts, bracket, district=AUTOBID_DISTRICT,
                        ladder=(sheet or {}).get(school), exclude=taken)


#: ‼️ THE AUTOBID IS ADMINISTERED AS A DISTRICT OF ONE (owner rule 2026-09): the
#: defending champion's entry "won a district event by themselves rather than being
#: granted auto access". So the bid is not a separate kind of berth at all — it is a
#: one-entry district that its only entrant wins unopposed, which is a path
#: `run_district` already has (`run_tournament` returns a lone entrant as champion
#: with no rounds, the same as a real district where only one school could field
#: anybody).
#:
#: That is worth more than a label: the entry becomes a district CHAMPION like every
#: other direct entrant, so it needs no special case in the field arithmetic, no
#: second branch in the archive, and no reader anywhere has to know it exists. The
#: seat it consumes is counted by `champions_of` for free.
AUTOBID_DISTRICT = "TOC"


def run_state(field: list, bracket: str, *, gender: str,
              seed: int) -> FlightDraw | None:
    """The 128-entry State draw, over a field already assembled from its three
    sources (`run_jv_state`).

    ‼️ HOW MANY ARE SEEDED IS THE USTA CONVENTION AND IS NOT SET HERE: a quarter
    of the padded draw, so 128 seeds 32. That is exactly
    `engine.tournament.seed_count`, which `run_tournament` applies by default —
    nothing is passed to `seeds=`, so the default IS the rule and this event
    cannot drift from the varsity flights or the college championships.

    ‼️ SAME-SCHOOL ENTRIES ARE SEPARATED (owner rule 2026-09). A school can now
    hold more than one seat — the defending champion's autobid sits beside its
    district entry, and a school can also put a district champion and a qualifier
    in the same draw — so two of them meeting in the first round would waste the
    bid the association just awarded. Two entries go to opposite HALVES, three or
    four to separate QUARTERS, spread as far as the bracket allows. It is done by
    swapping same-tier entrants after the seeded placement (`separate_draw`), so
    the seeding contract is untouched: a tier's anchors are assigned at random
    within the tier already, and exchanging two of its members is a draw the same
    code could have produced.
    """
    if len(field) < 2:
        return None
    rng = random.Random(seed)
    played: dict = {}
    result = run_tournament(sorted(field, key=lambda e: (-e.rating, e.school)),
                            seed=rng.randint(1, 10 ** 9),
                            play=_play(played), key=lambda e: e.rating,
                            separate=lambda e: e.school)
    return _assemble(gender, GROUP_KEY, bracket, result, played)


def run_jv_state(by_group: dict, gender: str, year: int, *, seed: int = 0,
                 season_year: int | None = None) -> dict:
    """A gender's whole JV individual postseason, archive-flattened as
    `{"state": …, "districts": …, "qualifying": …}`.

    ‼️ THE 128 FIELD IS BUILT FROM THREE SOURCES (owner rule 2026-09), and the
    arithmetic closes by construction rather than by hoping:

        district champions  +  TOC autobid  +  Regional Qualifying winners  =  128

    Every district champion enters directly and every district RUNNER-UP enters
    Regional Qualifying, which plays down to exactly the seats the first two
    sources leave open (`qualifying_spots`). With Jefferson's 95 districts that
    is 95 + 1 = 96 direct and 32 through qualifying.

    ‼️ THE COUNT IS TAKEN PER EVENT AND PER SEASON, never assumed. A district that
    fielded nobody crowns no champion, and one that crowned a champion unopposed
    sends no runner-up, so both numbers move year to year and between singles and
    doubles — the qualifying shape is derived from what was actually played.
    """
    teams = [t for dists in by_group.values() for ts in dists.values()
             for t in ts]
    by_school = {t.school.name: t for t in teams}
    sheet = entry_sheet(teams)
    sy = year if season_year is None else season_year
    state: dict = {}
    districts: dict = {}
    qualifying: dict = {}
    for bracket in BRACKETS:
        quals = district_qualifiers(by_group, bracket, gender=gender, year=year,
                                    seed=seed, sheet=sheet)
        districts[bracket] = {d.group: draw_to_dict(d) for d in quals}
        champs = champions_of(quals)
        # THE AUTOBID, placed before the qualifying arithmetic — it consumes a
        # seat, so the number of qualifying spots depends on whether it exists.
        holder = defending_program(gender, bracket, sy)
        # ‼️ THE BID IS A SECOND ENTRY, so it is drawn from what the school has
        # LEFT. Its best player is usually the one who won its district, and one
        # person cannot hold two seats — asked for the best entry outright the
        # bid would duplicate them and go unused in exactly the year the program
        # earned it. Excluding whoever already holds a seat is what makes the
        # owner's "two players from the same school" true.
        held = frozenset(p for c in champs if c.school == holder for p in c.pids)
        auto = (autobid_entry(holder, bracket, by_school, sheet, held)
                if holder else None)
        if auto is not None:
            # Played as its own district (of one), so it archives beside the
            # other districts and enters State as an ordinary champion.
            ad = FlightDraw(gender=gender, group=AUTOBID_DISTRICT,
                            flight=bracket, entries=[auto], n_seeds=1)
            ad.champion = auto
            quals = quals + [ad]
            districts[bracket][AUTOBID_DISTRICT] = draw_to_dict(ad)
            champs = champions_of(quals)
        direct = champs
        spots = qualifying_spots(len(champs))
        winners, qdraw = run_qualifying(runners_up_of(quals), bracket,
                                        gender=gender, spots=spots,
                                        seed=_draw_seed(seed, "jv-qual",
                                                        str(year), gender,
                                                        bracket))
        if qdraw is not None:
            qualifying[bracket] = draw_to_dict(qdraw)
        d = run_state(direct + winners, bracket, gender=gender,
                      seed=_draw_seed(seed, "jv-state", str(year), gender,
                                      bracket))
        if d is not None:
            state[bracket] = draw_to_dict(d)
    return {"state": state, "districts": districts, "qualifying": qualifying}
