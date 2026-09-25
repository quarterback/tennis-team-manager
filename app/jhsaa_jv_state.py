"""The JV TEAM State Tournament — a JHSAA pilot for 2068.

One statewide bracket per gender, no classifications, ending in a single JV Team
State Champion for the boys and one for the girls.

Three mechanics carry the event, each doing real work:

  * **Seeding runs on the JV RECORD.** JV has no TOSS, no awards and no ladder
    credit — but `JVTeam` has always carried its own `wins`/`losses`/`ties` and
    `points_for`/`against`. What it has no business reading is ability, and it
    never does: see `seed_key`.
  * **Eligibility FREEZES** at the start of the JV postseason, the same device
    `TeamSeason.order_of_ability` uses for the varsity postseason, so the squad
    that qualified is the squad that plays. See `freeze_eligibility`.
  * **ONE shape for the whole event** (`FORMAT`), rather than the league's elastic
    per-dual sizing off the thinner side, so a semifinal and a final are the same
    dual and their results are comparable — which a bracket needs and a league
    schedule does not.

‼️ AND THE FIXED SHAPE HAD TO BE ODD. Three of the eight `JV_FORMATS` have an even
court count and `jv_outcome` really does return draws (~0.24% of JV duals; 2S/2D
alone is about a fifth of the league slate). A bracket cannot advance a tie and
this association has no tie-break anywhere, by design — so a five-court 3S/2D card
is not a stylistic pick, it is the shape that lets the event exist at the depth
most programs have.

The road, per the spec: district qualification -> regional championship -> State.

‼️ THE 36-TEAM FIELD (owner rule 2026-09, from `jhsaa.jv_parastate_era()`): the
twenty regional champions plus SIXTEEN AT-LARGE selections, picked on an index of
30% JV record + 70% varsity regular-season record. The at-larges play a Parastate
round (the varsity committee classes' own device) and its eight winners join the
champions in a 28-team main draw: seeds 1-4 bye, twelve preliminary duals, then
16 → QF → SF → Final. See `AT_LARGE` below. Seasons before the era keep the
twenty-team shape that follows.

‼️ WINNING YOUR REGION IS QUALIFYING. All twenty champions ARE the State field —
there is no qualifying round in front of it and nothing to survive to "reach"
State (owner, 2026-09: "the qualifiers who get in, all 20, are already at State;
there is no qualifying once into the field of 20"). Twenty in a 32-slot bracket
simply means twelve are seeded through and eight open in the Round of 20 — the
TOC's own shape, where twelve classification champions in a 16 draw open in a
Round of 12 and nobody calls that qualifying either.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine.dual import DualFormat, simulate_dual

from . import jhsaa as jh

#: ‼️ SEVEN FLIGHTS, ELEVEN PLAYERS DRESS (JHSAA rule 2096). S1-S3 + D1-D4 is
#: 3 + 8 = 11 on court — the association's universal league format, now played by the
#: JV postseason too. Odd by requirement (see the module docstring): a drawn dual
#: cannot advance anybody, and seven flights cannot draw.
#:
#: ‼️ IT WAS 3S/2D UNTIL 2096, and the reason it was is gone. Five flights was "the
#: shape that lets the event exist at the depth most programs have" — chosen when a
#: JV squad was whatever a sixteen-player roster had spare. Rosters are far deeper
#: now and the owner's save carries the players, so the event plays the league format
#: instead of a reduction of it. ‼️ DO NOT re-derive this from `ROSTER_FLOOR`: the
#: floor is a theoretical minimum the real save does not sit on, and gating the
#: format on it would hold the event at a depth nobody actually fields.
FORMAT = DualFormat(n_singles=3, n_doubles=4, doubles_team_point=False)

#: Players the card needs (7) and the championship roster CAP (16).
#: ‼️ 16 IS A CEILING, NOT A SQUAD SIZE: a program carries UP TO sixteen frozen-
#: eligible players and dresses seven of them, so "lineups may change between rounds
#: using only eligible championship-roster players" has somewhere to change TO. A
#: program with fewer eligible players carries fewer — it needs `LINEUP` to enter and
#: nothing more.
LINEUP = jh.jv_lineup_need(FORMAT)
ROSTER = 16

#: The phases these duals are archived under. ‼️ TWO, NOT ONE, AND FOR THE SECTION'S
#: OWN REASON: a phase is the archive's identity for an EVENT, and a regional
#: championship and the State draw are two rounds of the road, exactly as the varsity
#: card tells its Regionals from its State duals. Written on JV rows, so `level` still
#: keeps every one of them out of a varsity record.
#:
#: The STRUCTURE is not new — these are the association's existing rounds, and the
#: labels are the varsity ones (owner, 2026-09: "since the labels already exist it's
#: not different but labeling can be"). Only the wording says JV.
PHASE_REGION = "jv_region"
PHASE = "jv_state"

#: What each phase is called on a schedule card — the varsity vocabulary, said of JV.
PHASE_LABELS = {PHASE_REGION: "JV REGIONALS", PHASE: "JV STATE"}

#: District berths by how many JV teams the district actually fielded (spec).
#: Read as "up to and including": 2-5 -> 1, 6-9 -> 2, 10-15 -> 3, 16+ -> 4.
#: ‼️ RETIRED FROM THE TEAM EVENT IN 2096 — every JV team now enters its Region and
#: there is nothing to qualify out of a league. Kept because seasons archived before
#: the era were cut with it, and `jhsaa_jv_individuals` has its own, unrelated,
#: district qualifying that this is NOT. Measured before deleting the cap: no league
#: ever reached 16 teams, so `DISTRICT_BERTHS_MAX` never once bound.
DISTRICT_BERTHS = ((5, 1), (9, 2), (15, 3))
DISTRICT_BERTHS_MAX = 4

#: ‼️ THIRTY JV REGIONS, AND THEY ARE BUCKETS, NOT PLACES (JHSAA rule 2096). The event
#: used the association's twenty geographic areas, which are wildly uneven — 2 teams in
#: one, 22 in another in 2095 — so a Region title was worth a single win in one place
#: and five in another, and the tiny regions' qualifiers went out in the opening round
#: at State. Thirty buckets of comparable size fixes that, and comparable size is the
#: whole requirement: `assign_regions` deals a geographically-ORDERED field into thirty
#: near-equal buckets, so a bucket holds schools that are mostly near each other
#: without anybody promising it is a place. ‼️ DO NOT "fix" this by pinning buckets
#: inside the twenty areas — that is what made them uneven, and containing them forces
#: 35 buckets to hold the same ceiling.
REGIONS = 30

#: ‼️ THE STATE DRAW IS NAMED IN DEBATE PARLANCE (JHSAA rule 2096), because a
#: 120-team bracket runs out of tennis words three rounds before it runs out of
#: rounds. Debate has named draws this size for a century: an OCTAFINAL is the round
#: of sixteen, DOUBLES the round of thirty-two, TRIPLES the round of sixty-four. The
#: opening round is numbered like a prelim (R120) because it is one — eight byes and
#: fifty-six duals to get to a clean 64.
#:
#: ‼️ JV ONLY. `world._round_label` bands the VARSITY brackets and must not learn
#: these: a varsity State draw of 32 says "Round of 32", not "Doubles Octafinals".
#: These names are written onto the JV bracket as `round_names`, which
#: `world.jhsaa_state_rounds` already prefers over its own banding.
STATE_ROUND_NAMES = {2: "Final", 4: "Semifinals", 8: "Quarterfinals",
                     16: "Octafinals", 32: "Doubles Octafinals",
                     64: "Triple Octafinals"}


#: A JV State exit, named for the ROUND it happened in rather than banded off the
#: alive count. ‼️ ONLY THE ROUNDS WHOSE BAND WOULD BE WRONG OR MUTE: `world._finish_label`
#: reads 64 and 32 as "Round of 64" / "Round of 32", which are true but say nothing about
#: where in a 120-team draw that is, and it reads 16 as "Octofinalist" in the VARSITY
#: spelling. Quarterfinals, Semifinals and the Final already band correctly and are
#: deliberately absent, so every other archive stays byte-identical.
STATE_FINISH_LABELS = {"Triple Octafinals": "Triple Octafinalist",
                       "Doubles Octafinals": "Doubles Octafinalist",
                       "Octafinals": "Octafinalist"}


def state_round_names(field_n: int, rounds: list) -> list[str]:
    """Debate-parlance names for a JV State draw, one per round actually played.

    Counted DOWN from the field the way `world.jhsaa_state_rounds` counts — every dual
    eliminates exactly one team — so a draw that is not a power of two names its
    opening round for its real size (R120) and lands on the named rounds after it."""
    names, alive = [], field_n
    for games in rounds:
        names.append(STATE_ROUND_NAMES.get(alive, f"R{alive}"))
        alive -= len(games)
    return names


#: How many each Region sends to State. ‼️ A REGION CROWNS NOBODY: its draw is pure
#: qualifying, run until four remain and stopped there — no semifinal, no final, no
#: champion, no runner-up. Thirty times four is the 120-team State field.
QUALIFIERS_PER_REGION = 4

#: ‼️ NOTHING IS CALLED QUALIFYING INSIDE THIS EVENT. Winning your region IS how you
#: qualify; every one of the twenty champions is already at State. The opening round
#: is named by its field like every other round — "Round of 20", the way varsity says
#: R32/R24/R40 and the TOC says Round of 12 — and `world._round_label` bands it off
#: the alive count with nothing to configure. Passing it a NAME is what made it read
#: as a gate in front of the tournament rather than the first round of it.
#:
#: ‼️ THIS REPLACED A BESPOKE PLAY-IN. The event used to cut the field to a 12-seed
#: draw by hand, play four duals in a separate bracket, and render them in a panel of
#: their own beside the tree — a second mechanism for something the association's own
#: draw already does. Owner: "you didn't have to invent a bespoke JV format when we
#: already have lots of bracket formats that work beyond 16."
#:
#: The string survives ONLY to read archives written by that build, which stored it
#: as a round name. Nothing writes it.
LEGACY_QUALIFYING_NAME = "State Qualifying"

#: ‼️ THE 36-TEAM FIELD (owner rule 2026-09, from `jhsaa.jv_parastate_era()`):
#: the twenty regional champions PLUS sixteen at-large selections. The at-larges
#: play a PARASTATE round — the varsity committee event's own device
#: (`jhsaa.run_state_parastate`): the `2 × bids` lowest seeds paired high-low,
#: winners keep their seed — and its eight survivors join the champions in a
#: 28-team main draw. Twenty-eight in 32 slots on the TOC's strict seed lines is
#: four byes to seeds 1-4 and twelve preliminary duals (5v28 … 16v17), which is
#: the spec's shape exactly: 36 → 16 in the Parastate → 8 advance → 28 → 4 byes
#: + 12 duals → 16 → QF → SF → Final.
#:
#: ‼️ IT IS THE STATE MACHINERY, NOT A SECOND BRACKET. The archive is ONE `state`
#: dict whose first round is NAMED `jhsaa.PARASTATE_NAME` in `round_names`, which
#: is exactly what makes `state._jh_split_state` draw the Parastate as its own tree
#: (there is no bracket path from a Parastate slot to a main-draw slot),
#: `world.jhsaa_state_result` file an at-large's exit as "Parastate", and the
#: round list read it back at any size — every reader the varsity Parastate
#: already has. A champion's route is unchanged: the twenty still enter the main
#: field directly and are still seeded 1-20 on the JV record.
AT_LARGE = 16
MAIN_BYES = 4

#: ‼️ THE SELECTION INDEX — 30% JV record, 70% VARSITY record (owner rule 2026-09).
#: An at-large is a program whose JV team did not win its region, so the JV
#: record alone cannot tell the sixteen best of them apart from a soft-league
#: 12-2; the varsity side is the program's strength and weighs more. Both terms
#: are win percentages. ‼️ THE VARSITY TERM IS THE REGULAR SEASON ONLY —
#: `jhsaa._reg_season_record`, the State Specials' own rule: the varsity road
#: has been played by the time the JV postseason runs, and a deep bracket run is
#: how far the draw carried a program, not what it did across the season.
INDEX_JV_WEIGHT = 0.30
INDEX_VARSITY_WEIGHT = 0.70


def district_berths(n_teams: int) -> int:
    """How many of a district's JV teams advance. One even for a district of one —
    `_run_bracket` already returns a lone entrant as champion, and a program that
    fielded a JV team in a league where nobody else did has qualified unopposed, the
    same reading `jhsaa_jv_individuals.run_district` settled on."""
    if n_teams <= 0:
        return 0
    for upto, berths in DISTRICT_BERTHS:
        if n_teams <= upto:
            return berths
    return DISTRICT_BERTHS_MAX


@dataclass
class JVEntry:
    """A program in the JV postseason: its JV season team plus the championship
    roster frozen for the event (up to `ROSTER`). `players` is fixed at the freeze
    and every round dresses its seven from it."""
    jv: object                       # jhsaa.JVTeam
    players: list = field(default_factory=list)

    @property
    def school(self):
        return self.jv.school

    @property
    def name(self) -> str:
        return self.jv.school.name

    @property
    def region(self) -> str:
        """‼️ THE GEOGRAPHIC AREA, which is what the association's twenty regions ARE
        (spec: "use the existing 20 JHSAA regions"). NOT the varsity road's Regionals,
        which are numbered per CLASSIFICATION — this event has no classifications, so
        a per-class unit would be meaningless here."""
        return self.jv.school.area


def played_jv(jvt) -> set[str]:
    """Everyone who actually appeared in a JV dual this season.

    Spec: "players must have actually participated in JV competition during the
    season". `play_jv_dual` records the names it dressed on each schedule entry, so
    participation is already in the data and needs no new bookkeeping — which is
    just as well, since `JVTeam` deliberately has no per-player records to read.
    """
    out: set[str] = set()
    for d in jvt.schedule:
        out.update(d.get("played") or ())
    return out


def freeze_eligibility(jvt) -> list:
    """The program's championship-eligible players, FROZEN.

    Three rules, all the spec's:
      * ranked below the varsity playoff lineup on the school ladder — #12 or
        lower in every classification, and #15 or lower in 8A/9A, whose playoffs
        dress fourteen (owner rule 2070). That is `jv_postseason_cut`, derived from
        `lineup_need` and NOT a second roster split: the JV SEASON's own cut
        (`jv_pool`) is #12 everywhere and does not move. The overlap is deliberate
        and harmless — a player may dress for both playoff fields.
      * they actually played JV this season.
      * split-time players count, and fall out for free: a player who spent the year
        moving between varsity and JV is eligible if the ladder has them at #12 or
        lower AT THE FREEZE, which is the only reading a frozen order can support.

    ‼️ CALLED ONCE, at the start of the postseason. The ladder is live all season
    (`coach_eval` moves it on results), so re-reading it between rounds would let a
    program's eligible set drift mid-tournament — the same drift the varsity
    anti-stacking freeze exists to stop, arriving by a different door.
    """
    played = played_jv(jvt)
    return [p for p in jh.jv_state_pool(jvt.team) if p.name in played]


def entries(jv: dict) -> list[JVEntry]:
    """Every program that FIELDED a JV team and can still dress the state card.

    Spec: "any school that fielded a JV team may enter". A program that played no JV
    dual has not fielded one; a program that played but cannot now put seven frozen-
    eligible players on court cannot enter a five-court dual, and is dropped rather
    than degraded — the association has no short-handed dual anywhere.
    """
    out = []
    for jvt in jv.values():
        if not jvt.schedule:
            continue
        roster = freeze_eligibility(jvt)[:ROSTER]
        if len(roster) >= LINEUP:
            out.append(JVEntry(jv=jvt, players=roster))
    return out


def seed_key(e: JVEntry) -> float:
    """Seeding rating: JV win percentage, with point differential per dual breaking
    ties. Earned on court, never ability — see the module docstring."""
    n = e.jv.wins + e.jv.losses + e.jv.ties
    if not n:
        return 0.0
    diff = (e.jv.points_for - e.jv.points_against) / n
    return e.jv.win_pct + diff / 1000.0


def varsity_record(e: JVEntry) -> tuple[int, int]:
    """The program's VARSITY regular-season W-L, off the `TeamSeason` the JV team
    hangs from — `jhsaa._reg_season_record`, so the postseason never reaches the
    index."""
    return jh._reg_season_record(e.jv.team)


def selection_index(e: JVEntry) -> float:
    """`INDEX_JV_WEIGHT` × JV win% + `INDEX_VARSITY_WEIGHT` × varsity regular-season
    win%. A program with no varsity duals scores 0 on that term — a real answer,
    never a default that quietly hands it the JV share twice."""
    w, l = varsity_record(e)
    var = w / (w + l) if w + l else 0.0
    return INDEX_JV_WEIGHT * e.jv.win_pct + INDEX_VARSITY_WEIGHT * var


def select_at_large(pool: list[JVEntry], n: int = AT_LARGE) -> list[JVEntry]:
    """The at-large field, best first, from every entrant that did not win its
    region: ranked on `selection_index`, the JV seeding key breaking ties, the name
    last so the cut is reproducible. Fewer than `n` when the pool is short (a tiny
    world) — the Parastate then degrades exactly as the varsity one does."""
    ranked = sorted(pool, key=lambda e: (-selection_index(e), -seed_key(e), e.name))
    return ranked[:n]


def selection_rows(field: list[JVEntry], champions: set[str],
                   region_of: dict[str, str]) -> list[dict]:
    """The State field as an auditable table, in SEED ORDER — the committee's own
    posture (`jhsaa_committee.select` archives what it read): every team's entry
    (`champion` / `at_large`), region, JV and varsity regular-season records, the
    two percentages and the index. ‼️ THE WHOLE FIELD, not the at-larges alone: a
    later analysis of whether the index picks well needs the champions' numbers
    on the same table, and the champions' JV record is what seeded them. The
    research export flattens this to `jhsaa_jv_state.csv`."""
    out = []
    for e in field:
        vw, vl = varsity_record(e)
        out.append({"school": e.name,
                    "entry": "champion" if e.name in champions else "at_large",
                    "region": region_of.get(e.name, e.region),
                    "jv_wins": e.jv.wins, "jv_losses": e.jv.losses,
                    "jv_ties": e.jv.ties, "jv_pct": round(e.jv.win_pct, 4),
                    "v_wins": vw, "v_losses": vl,
                    "v_pct": round(vw / (vw + vl), 4) if vw + vl else 0.0,
                    "index": round(selection_index(e), 4)})
    return out


def qualifier_rows(ranked: list[JVEntry], region_of: dict[str, str]) -> list[dict]:
    """The State field as an auditable table, in SEED ORDER — `selection_rows` for the
    2096 qualifying shape (JHSAA rule 2096).

    Same columns so `jhsaa_jv_state.csv` keeps ONE schema across all three eras and an
    analysis spanning them joins on one shape. Two read differently and deliberately:
    `entry` is always `qualifier` (nobody is a champion of anything — a Region crowns
    no one), and `index` is empty (there is no selection index; nothing is picked).
    The varsity record is still carried because it is useful context, NOT because it
    selects anybody — that it used to select people, at 70% weight on a JV event, is
    the thing this rule removed."""
    out = []
    for e in ranked:
        vw, vl = varsity_record(e)
        out.append({"school": e.name, "entry": "qualifier",
                    "region": region_of.get(e.name, ""),
                    "jv_wins": e.jv.wins, "jv_losses": e.jv.losses,
                    "jv_ties": e.jv.ties, "jv_pct": round(e.jv.win_pct, 4),
                    "v_wins": vw, "v_losses": vl,
                    "v_pct": round(vw / (vw + vl), 4) if vw + vl else 0.0,
                    "index": ""})
    return out


def run_parastate(bids: list[JVEntry], *, seed: int) -> tuple[list[JVEntry], list]:
    """The Parastate round over the at-large field: pairs pinned HIGH-LOW (1v16 …
    8v9), the higher seed on the home side — orientation only, since every dual of
    this event is played at a neutral site exactly as the varsity Parastate is
    (`phase="state"` is in `NEUTRAL_PHASES`). Returns the winners IN SEED ORDER —
    winners retain their seed, the varsity rule — and the archived games. An odd
    field (a short world) advances its middle seed unplayed, `run_state_parastate`'s
    own degradation."""
    rng = random.Random(seed)
    games, alive = [], set()
    for i in range(len(bids) // 2):
        a, b = bids[i], bids[len(bids) - 1 - i]
        win, game = play_dual(a, b, seed=rng.randrange(1 << 30))
        games.append(game)
        alive.add(win.name)
    if len(bids) % 2:
        alive.add(bids[len(bids) // 2].name)
    return [e for e in bids if e.name in alive], games


def _dress(e: JVEntry, rng_seed: int) -> list:
    """The championship roster named for a dual, and the seven who take the court.

    Lineups may change between rounds, but only from the frozen roster, so the choice
    is made HERE and only ever over `e.players`. Named in frozen-ladder order: the
    event's own anti-sandbagging property, the same one the individual draws get from
    selecting on `coach_eval` rather than on a coach's pick.
    """
    return e.players[:LINEUP]


def play_dual(a: JVEntry, b: JVEntry, *, seed: int, phase: str = PHASE) -> tuple:
    """One JV state dual. Returns `(winner, loser_points_row)` — the winning entry
    and the archived game.

    ‼️ NO TIE IS POSSIBLE — five courts, first to three — which is why this can
    return a winner unconditionally where `jv_outcome` has to report draws.

    ‼️ IT RECORDS THE DUAL ON BOTH SCHEDULES, WITH ITS BOX SCORE, exactly as
    `play_jv_dual` does. `world.run_jhsaa` archives every JV schedule entry into
    `world_jhsaa_dual`, so writing the row here is the whole reason these duals reach
    a program's page at all; `level` (JV) is what keeps them out of every varsity
    record, and the phase is what tells them apart from a league dual.

    ‼️ AND IT DOES NOT TOUCH `wins`/`losses`/`points_for`. Those are the SEEDING
    basis, read by `seed_key` while the event is still being played — a region final
    that moved them would re-rank the statewide field that the play-in and the State
    draw are cut from, which is the mid-event drift `freeze_eligibility` exists to
    stop, arriving through the record instead of through the roster. The regular JV
    season is what seeds this; the postseason is what it decides.
    """
    la, lb = _dress(a, seed), _dress(b, seed)
    mf = jh.match_format(phase)
    # ‼️ NEUTRAL SITE. A championship is not hosted by one of its entrants — the same
    # call `NEUTRAL_PHASES` makes for the varsity state event and the showcases. Pass
    # no lift rather than rolling one and discarding it.
    res = simulate_dual(jh._squad(a.jv.team, phase, la, FORMAT),
                        jh._squad(b.jv.team, phase, lb, FORMAT),
                        seed=seed, play_all=False, fidelity=jh.FIDELITY,
                        dual_fmt=FORMAT, singles_fmt=mf, doubles_fmt=mf,
                        profile=jh.HS_PROFILE)
    home_won = res.home_points > res.away_points
    # ‼️ `FORMAT` MUST REACH `_slot_players` — the same override `_squad` was dressed
    # with. Without it a D-slot resolves against the varsity singles count and the box
    # score names the wrong players, raising nothing (the 1A 2S/3D pilot's own trap).
    lines = []
    for ln in res.lines:
        hw = getattr(ln, "home_won", None)
        if hw is None:
            continue
        slot = getattr(ln, "slot", "")
        lines.append({"slot": slot,
                      "home": [x.name for x in jh._slot_players(la, phase, slot, FORMAT)],
                      "away": [x.name for x in jh._slot_players(lb, phase, slot, FORMAT)],
                      "score": jh._score_str(ln), "home_won": bool(hw)})
    shape = f"{FORMAT.n_singles}S/{FORMAT.n_doubles}D"
    # `home` is ORIENTATION ONLY — the site is neutral, and no lift was rolled. It is
    # what `_score_str` and the archived `lines` are written from, so both rows have
    # to agree on which side is which.
    a.jv.schedule.append({"opp": b.name, "home": True, "phase": phase,
                          "pf": res.home_points, "pa": res.away_points,
                          "won": home_won, "tied": False, "district": False,
                          "level": jh.LEVEL_JV, "shape": shape, "lines": lines,
                          "played": [p.name for p in la]})
    b.jv.schedule.append({"opp": a.name, "home": False, "phase": phase,
                          "pf": res.away_points, "pa": res.home_points,
                          "won": not home_won, "tied": False, "district": False,
                          "level": jh.LEVEL_JV, "shape": shape, "lines": lines,
                          "played": [p.name for p in lb]})
    win = a if home_won else b
    return win, {"home": a.name, "away": b.name,
                 "home_points": res.home_points, "away_points": res.away_points,
                 "winner": win.name}


def _run_bracket(field: list[JVEntry], *, seed: int, phase: str = PHASE,
                 round_names: list[str] | None = None, stop_at: int = 1) -> tuple:
    """A seeded single-elimination draw over `field`, returning `(champion, bracket)`.

    ‼️ THE BRACKET IS THE VARSITY STATE DRAW'S ARCHIVE SHAPE — `{champion, field,
    rounds, round_names}` with the same game dicts — and that is the whole point: the
    rendering layer already turns that shape into a tree (`state._jh_bracket_cols` →
    `_bracket_canvas` → `templates/_bracket.html`), materialising byes and ordering
    cards by their real feeders. Emitting anything else would mean a fourth bracket
    implementation for an event that draws exactly like the other three.

    ‼️ STRICT SEED LINES, THE TOC'S ORDER — NOT `seeded_draw`'S TIERED ONE. Both are
    the association's; they are for different events. `jhsaa.run_state` shuffles
    within seed tiers because a classification's TOSS seeding is an ESTIMATED
    ordering, so "#5 deserves an easier path than #8" is precision the ranking cannot
    back. This event is a championship of CHAMPIONS ranked on a season's JV record,
    which is the TOC's situation exactly, and the TOC is deliberately strict
    rank-for-rank. It is also what makes the spec's own pairings true: twenty into a
    32-slot draw gives **13v20, 14v19, 15v18, 16v17** with seeds 1-12 seeded through,
    every time. Under the tiered draw those pairings came out differently every
    season (seed 9 playing in while seed 15 byed), which is defensible for a State
    draw and simply wrong here.

    The order fold is `run_toc`'s, unchanged: seed s meets seed (m+1-s), nesting so
    1 and 2 can only meet in the final.
    """
    rng = random.Random(seed)
    # ‼️ `stop_at` HALTS THE DRAW WITH THAT MANY ALIVE instead of at one, which is what
    # makes a Region a QUALIFYING draw rather than a championship (JHSAA rule 2096):
    # 32 -> 16 -> 8 -> 4 and stop, the four survivors being the qualifiers. There is no
    # champion to return, so the caller reads the survivors off the bracket instead.
    order = [1]
    while len(order) < len(field):
        m = 2 * len(order)
        order = [s for a in order for s in (a, m + 1 - a)]
    slots: list = [field[s - 1] if s <= len(field) else None for s in order]
    rounds: list = []
    while len([x for x in slots if x is not None]) > stop_at and len(slots) > 1:
        nxt, games = [], []
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if a is None or b is None:                 # a bye, drawn by the renderer
                nxt.append(a or b)
                continue
            win, game = play_dual(a, b, seed=rng.randrange(1 << 30), phase=phase)
            games.append(game)
            nxt.append(win)
        if games:
            rounds.append(games)
        slots = nxt
    alive = [x for x in slots if x is not None]
    champ = alive[0] if alive and stop_at == 1 else None
    return champ, {"champion": champ.name if champ else None,
                   "field": [e.name for e in field], "rounds": rounds,
                   "round_names": list(round_names or ()),
                   "survivors": [e.name for e in alive]}


def assign_regions(field: list[JVEntry], n: int = REGIONS) -> dict[str, str]:
    """Deal the whole field into `n` JV Regions of near-equal size -> {name: region}.

    ‼️ EVEN SIZE IS THE REQUIREMENT; GEOGRAPHY IS THE TIE-BREAK. The field is ordered
    by area, then county, then city, then name, and dealt into `n` contiguous buckets.
    Ordering first means a bucket holds schools that are mostly near each other, which
    is all the geography this event needs; dealing into equal slices means no bucket is
    a tenth the size of another, which is what the twenty areas got wrong.

    Deterministic and stateless — same field, same buckets — so a re-run reproduces the
    draw without storing the map. A bucket is named for its index, NOT for a place: it
    is not one, and naming it after the area it mostly covers would invite somebody to
    pin it there again."""
    order = sorted(field, key=lambda e: (e.jv.school.area, e.jv.school.county,
                                         e.jv.school.city, e.name))
    if not order:
        return {}
    per = len(order) / n
    return {e.name: f"JV Region {min(n, int(i // per) + 1)}"
            for i, e in enumerate(order)}


def district_qualifiers(field: list[JVEntry]) -> list[JVEntry]:
    """Each district's berths, by JV season record.

    ‼️ A DISTRICT IS `(classification, name)` — the association reuses its league
    names at every level, so keying on the name alone would merge five leagues into
    one. The same rule the archive is keyed on.

    No district TOURNAMENT is played: the spec makes the region the first
    championship, and the district's berths are earned over the season.
    """
    by_district: dict[tuple, list[JVEntry]] = {}
    for e in field:
        s = e.school
        by_district.setdefault((s.group, s.district), []).append(e)
    out = []
    for key in sorted(by_district):
        teams = sorted(by_district[key], key=lambda e: (-seed_key(e), e.name))
        out.extend(teams[:district_berths(len(teams))])
    return out


def run_qualifying(field: list[JVEntry], *, seed: int) -> tuple:
    """Every JV team enters its Region; each Region plays down to `QUALIFIERS_PER_REGION`
    and stops. Returns `(qualifiers, draws by region)` (JHSAA rule 2096).

    ‼️ NOTHING IS WON HERE. A Region has no champion, no final and no runner-up — the
    draw exists to cut a bucket of ~30 down to four, the way a Grand Slam qualifying
    draw exists to fill the last seats of a main draw. A team that reaches the last
    four has qualified; which of the four it is carries no meaning and is not played
    for.

    A short bucket behaves identically: seeded into the same slots, the byes fall to
    the top seeds, and it still stops with four alive."""
    region_of = assign_regions(field)
    by_region: dict[str, list[JVEntry]] = {}
    for e in field:
        by_region.setdefault(region_of[e.name], []).append(e)
    quals, out = [], {}
    for i, region in enumerate(sorted(by_region, key=lambda r: int(r.rsplit(" ", 1)[1]))):
        teams = sorted(by_region[region], key=lambda e: (-seed_key(e), e.name))
        _, br = _run_bracket(teams, seed=seed + 101 * i, phase=PHASE_REGION,
                             stop_at=QUALIFIERS_PER_REGION)
        by_name = {e.name: e for e in teams}
        got = [by_name[n] for n in br["survivors"]]
        out[region] = {**br, "qualifiers": [e.name for e in got]}
        quals.extend(got)
    return quals, out


def run_regionals(quals: list[JVEntry], *, seed: int) -> tuple:
    """Each region crowns one champion. Returns `(champions, brackets by region)`.

    The draw sizes itself to however many district qualifiers a region drew — it pads
    to the next power of two and byes the top seeds — so nothing here needs to know
    the number in advance.
    """
    by_region: dict[str, list[JVEntry]] = {}
    for e in quals:
        by_region.setdefault(e.region, []).append(e)
    champs, out = {}, {}
    for i, region in enumerate(sorted(by_region)):
        teams = sorted(by_region[region], key=lambda e: (-seed_key(e), e.name))
        champ, br = _run_bracket(teams, seed=seed + 101 * i, phase=PHASE_REGION)
        champs[region], out[region] = champ, br
    return champs, out


def run_jv_state(jv: dict, *, gender: str, year: int, seed: int = 0,
                 expanded: bool | None = None, qualifying: bool | None = None) -> dict:
    """The whole JV team postseason for one gender.

    Returns the archive `world.run_jhsaa` stores: the field, every region's draw,
    the at-large selection and the State bracket, each in the shape the bracket
    renderer already reads. `{}` when nothing can be staged — a world whose
    programs never played a JV season has no event, which is a real answer and not
    an error.

    `expanded` is the 36-team shape (`AT_LARGE` at-larges through a Parastate into
    a 28-team main draw); by default it is decided by the season against
    `jhsaa.jv_parastate_era()`, and a test passes it explicitly.
    """
    field = entries(jv)
    if not field:
        return {}
    if qualifying is None:
        # ‼️ AN EXPLICIT `expanded=` PINS THE OLD SHAPE. A caller naming the 20- or
        # 36-team era is asking for that era on purpose — a test, or a re-render of an
        # archive — and must not be silently upgraded to the 2096 qualifying shape by a
        # fresh save's era resolving to 0. Only an unpinned call consults the era.
        qualifying = expanded is None and year >= jh.jv_qualifying_era()
    if qualifying:
        # ‼️ THE 2096 SHAPE: no league berths, no champions, no at-larges, no committee.
        # Every JV team enters one of thirty buckets, each bucket plays down to four,
        # and those 120 are the State field — seeded straight into a 128-slot draw where
        # eight byes fall to the top seeds. The whole event is two mechanisms.
        region_of = assign_regions(field)
        quals, regions = run_qualifying(field, seed=seed + 7919 * (gender == "boys"))
        ranked = sorted(quals, key=lambda e: (-seed_key(e), e.name))
        champ, state = _run_bracket(ranked, seed=seed + 5701)
        state = {**state, "round_names": state_round_names(len(ranked), state["rounds"])}
        return {"field": [e.name for e in field],
                "qualifiers": [e.name for e in quals],
                "regions": regions,
                "region_of": {e.name: region_of[e.name] for e in quals},
                "ranked": [e.name for e in ranked],
                "selection": qualifier_rows(ranked, region_of),
                "state": state,
                "champion": champ.name if champ else ""}
    quals = district_qualifiers(field)
    champs, regions = run_regionals(quals, seed=seed + 7919 * (gender == "boys"))
    ranked = sorted(champs.values(), key=lambda e: (-seed_key(e), e.name))
    if expanded is None:
        expanded = year >= jh.jv_parastate_era()

    out = {
        "field": [e.name for e in field],
        "qualifiers": [e.name for e in quals],
        "regions": regions,
        "region_champions": {k: v.name for k, v in champs.items()},
    }
    if not expanded:
        # ‼️ ONE DRAW OVER EVERY REGION CHAMPION — all twenty ARE the field. Twenty
        # in a 32-slot bracket seeds twelve through and opens eight in the Round of
        # 20; nothing is cut beforehand, nothing is qualified into, and no second
        # bracket exists. The shape every season before `jv_parastate_era` played.
        champ, state = _run_bracket(ranked, seed=seed + 5701)
        return {**out, "ranked": [e.name for e in ranked], "state": state,
                "champion": champ.name if champ else ""}

    # ‼️ THE 36: champions seeded 1-20 on the JV record, then the sixteen at-larges
    # seeded 21-36 on the selection index — an at-large is NEVER seeded above a
    # champion, structurally (they arrive after every champion in this list), the
    # varsity Parastate's own floor. The Parastate is played over the at-larges
    # alone; its winners keep their seed and join the champions in a fresh 28-team
    # draw, where the TOC's strict seed lines give seeds 1-4 the byes.
    taken = {e.name for e in ranked}
    bids = select_at_large([e for e in field if e.name not in taken])
    winners, para = run_parastate(bids, seed=seed + 3301)
    main = ranked + winners
    champ, state = _run_bracket(main, seed=seed + 5701)
    if para:
        state = {**state,
                 "rounds": [para] + list(state["rounds"]),
                 "round_names": [jh.PARASTATE_NAME],
                 "field": [e.name for e in ranked] + [e.name for e in bids]}
    region_of = {v.name: k for k, v in champs.items()}
    return {**out,
            "ranked": list(state["field"]),
            "at_large": [e.name for e in bids],
            "selection": selection_rows(ranked + bids, set(region_of), region_of),
            "state": state,
            "champion": champ.name if champ else ""}
