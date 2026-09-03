"""The JV TEAM State Tournament — a JHSAA pilot for 2068.

One statewide bracket per gender, no classifications, ending in a single JV Team
State Champion for the boys and one for the girls.

‼️ THIS REVERSES A STANDING "NO JV TEAM PLAYOFFS" RULE, and it is worth recording
what the three objections were and how the spec answers each, because they were
real and none of them was hand-waved:

  * *"a bracket needs a ranking to seed it and JV has none by design."* JV has no
    TOSS, no awards and no ladder credit — but `JVTeam` has always carried its own
    `wins`/`losses`/`ties` and `points_for`/`against`. A JV RECORD exists; what
    does not exist is an opponent-strength rating. Every seeding here runs on the
    record, which is earned on court, and never on ability.
  * *"a JV team is a ladder slice, so the squad that qualified need not be the
    squad that plays."* Answered by FREEZING eligibility at the start of the JV
    postseason, the same device `TeamSeason.order_of_ability` uses for the varsity
    postseason. See `freeze_eligibility`.
  * *"the elastic format means a semifinal and a final could be different shapes."*
    Answered by fixing ONE shape for the whole event (`FORMAT`) instead of sizing
    it per dual off the thinner side. That is also what makes the event's results
    comparable across rounds, which a bracket needs and a league card does not.

‼️ AND THE FIXED SHAPE HAD TO BE ODD. Three of the eight `JV_FORMATS` have an even
court count and `jv_outcome` really does return draws (~0.24% of JV duals; 2S/2D
alone is about a fifth of the league slate). A bracket cannot advance a tie and
this association has no tie-break anywhere, by design — so a five-court 3S/2D card
is not a stylistic pick, it is the shape that lets the event exist at the depth
most programs have.

The road, per the spec: district qualification -> regional championship -> a state
qualifying round -> a sixteen-team State Championship.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.dual import DualFormat, simulate_dual
from engine.tournament import run_tournament

from . import jhsaa as jh

#: ‼️ FIVE COURTS, FIRST TO THREE, AND SEVEN PLAYERS DRESS. S1/S2/S3 + D1/D2 —
#: three singles and two doubles pairs is 3 + 4 = 7 on court. Odd by requirement
#: (see the module docstring): a drawn dual cannot advance anybody.
FORMAT = DualFormat(n_singles=3, n_doubles=2, doubles_team_point=False)

#: Players the card needs (7) and players NAMED for each dual (8). The extra name is
#: the spec's: "lineups may change between rounds using only eligible
#: championship-roster players", so a program carries one more than it plays.
LINEUP = jh.jv_lineup_need(FORMAT)
ROSTER = 8

#: The phase these duals are archived under. ‼️ ITS OWN PHASE, not "regular" and not
#: the varsity postseason's — a phase is the archive's identity for an EVENT (the
#: rule the JV showcase weekend was given its own phase for). Written on JV rows, so
#: `level` still keeps every one of them out of a varsity record.
PHASE = "jv_state"

#: District berths by how many JV teams the district actually fielded (spec).
#: Read as "up to and including": 2-5 -> 1, 6-9 -> 2, 10-15 -> 3, 16+ -> 4.
DISTRICT_BERTHS = ((5, 1), (9, 2), (15, 3))
DISTRICT_BERTHS_MAX = 4

#: Regional champions ranked statewide; the top this many go straight to State and
#: the rest play in. 12 direct + 4 play-in winners = a 16 field, from 20 regions.
DIRECT_SEEDS = 12
STATE_FIELD = 16


def district_berths(n_teams: int) -> int:
    """How many of a district's JV teams advance. One even for a district of one —
    `run_tournament` already returns a lone entrant as champion, and a program that
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
    """A program in the JV postseason: its JV season team plus the roster frozen for
    the event. `players` is fixed at the freeze and every round dresses from it."""
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
      * ranked #12 or lower on the school ladder — which is exactly `jv_pool`, the
        one ladder cut below `lineup_need("regular")`. No second roster split is
        invented here; there has never been one and there must not start being one.
      * they actually played JV this season.
      * split-time players count, and fall out for free: a player who spent the year
        moving between varsity and JV is eligible if the ladder has them at #12 or
        lower AT THE FREEZE, which is the only reading a frozen order can support.

    ‼️ CALLED ONCE, at the start of the postseason. The ladder is live all season
    (`ladder_score` moves it on results), so re-reading it between rounds would let a
    program's eligible set drift mid-tournament — the same drift the varsity
    anti-stacking freeze exists to stop, arriving by a different door.
    """
    played = played_jv(jvt)
    return [p for p in jh.jv_pool(jvt.team) if p.name in played]


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
        roster = freeze_eligibility(jvt)
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


def _dress(e: JVEntry, rng_seed: int) -> list:
    """The eight named for a dual, and the seven who take the court.

    Lineups may change between rounds, but only from the frozen roster, so the choice
    is made HERE and only ever over `e.players`. Named in frozen-ladder order: the
    event's own anti-sandbagging property, the same one the individual draws get from
    selecting on `ladder_score` rather than on a coach's pick.
    """
    named = e.players[:ROSTER]
    return named[:LINEUP]


def play_dual(a: JVEntry, b: JVEntry, *, seed: int) -> int:
    """One JV state dual. Returns 0 if `a` won, 1 if `b` did.

    ‼️ NO TIE IS POSSIBLE — five courts, first to three. That is the whole reason
    `FORMAT` is odd, and it is why this can return a winner unconditionally where
    `jv_outcome` has to report draws.
    """
    la, lb = _dress(a, seed), _dress(b, seed)
    mf = jh.match_format(PHASE)
    # ‼️ NEUTRAL SITE. A championship is not hosted by one of its entrants — the same
    # call `NEUTRAL_PHASES` makes for the varsity state event and the showcases. Pass
    # no lift rather than rolling one and discarding it.
    res = simulate_dual(jh._squad(a.jv.team, PHASE, la, FORMAT),
                        jh._squad(b.jv.team, PHASE, lb, FORMAT),
                        seed=seed, play_all=False, fidelity=jh.FIDELITY,
                        dual_fmt=FORMAT, singles_fmt=mf, doubles_fmt=mf,
                        profile=jh.HS_PROFILE)
    return 0 if res.home_points > res.away_points else 1


def _play(a: JVEntry, b: JVEntry, *, seed: int):
    """`run_tournament`'s contract: return the WINNING ENTRANT."""
    return a if play_dual(a, b, seed=seed) == 0 else b


def district_qualifiers(field: list[JVEntry]) -> list[JVEntry]:
    """Each district's berths, by JV season record.

    ‼️ A DISTRICT IS `(classification, name)` — the association reuses its league
    names at every level, so keying on the name alone would merge five leagues into
    one. The same rule the archive is keyed on.

    No district TOURNAMENT is played: the spec makes the region the first
    championship, and the district's berths are earned over the season. That also
    keeps the pilot's dual count down, which matters when this runs for every
    program in the association.
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


def run_regionals(quals: list[JVEntry], *, seed: int) -> dict:
    """Each of the twenty regions crowns one champion.

    The bracket size adjusts to however many qualifiers a region drew — that is
    `run_tournament`'s ordinary behaviour, which pads to the next power of two and
    byes the top seeds, so nothing here needs to know the number in advance.
    """
    by_region: dict[str, list[JVEntry]] = {}
    for e in quals:
        by_region.setdefault(e.region, []).append(e)
    out = {}
    for i, region in enumerate(sorted(by_region)):
        teams = sorted(by_region[region], key=lambda e: (-seed_key(e), e.name))
        out[region] = run_tournament(teams, seed=seed + 101 * i,
                                     play=_play, key=seed_key)
    return out


def qualifying_pairs(ranked: list[JVEntry]) -> list[tuple[JVEntry, JVEntry]]:
    """The play-in: 13v20, 14v19, 15v18, 16v17 (spec).

    Written as a fold of the ranking rather than four typed pairs, so a future change
    to `DIRECT_SEEDS` or the number of regions reshapes it instead of silently
    pairing the wrong seeds.
    """
    rest = ranked[DIRECT_SEEDS:]
    return [(rest[i], rest[len(rest) - 1 - i]) for i in range(len(rest) // 2)]


def run_jv_state(jv: dict, *, gender: str, year: int, seed: int = 0) -> dict:
    """The whole JV team postseason for one gender.

    Returns the archive: the field, each region's draw, the play-in, and the State
    bracket. `None` when nothing can be staged — a world whose programs never played
    a JV season has no event, which is a real answer and not an error.
    """
    field = entries(jv)
    if not field:
        return {}
    quals = district_qualifiers(field)
    regions = run_regionals(quals, seed=seed + 7919 * (gender == "boys"))

    champs = [r.entrants[r.champion_idx] for r in regions.values()
              if r.champion_idx is not None]
    ranked = sorted(champs, key=lambda e: (-seed_key(e), e.name))

    playin = []
    for i, (hi, lo) in enumerate(qualifying_pairs(ranked)):
        w = _play(hi, lo, seed=seed + 3301 + i)
        playin.append({"hi": hi.name, "lo": lo.name, "winner": w.name})
    winners = [e for e in ranked if e.name in {p["winner"] for p in playin}]

    draw_field = ranked[:DIRECT_SEEDS] + winners
    state = run_tournament(draw_field[:STATE_FIELD], seed=seed + 5701,
                           play=_play, key=seed_key)
    champ = (state.entrants[state.champion_idx].name
             if state.champion_idx is not None else "")
    return {
        "field": [e.name for e in field],
        "qualifiers": [e.name for e in quals],
        "regions": {k: [e.name for e in v.entrants] for k, v in regions.items()},
        "region_champions": {k: (v.entrants[v.champion_idx].name
                                 if v.champion_idx is not None else "")
                             for k, v in regions.items()},
        "ranked": [e.name for e in ranked],
        "play_in": playin,
        "state_field": [e.name for e in draw_field[:STATE_FIELD]],
        "champion": champ,
    }
