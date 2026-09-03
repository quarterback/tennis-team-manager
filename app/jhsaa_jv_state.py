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

The road, per the spec: district qualification -> regional championship -> a state
qualifying round -> a sixteen-team State Championship.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.dual import DualFormat, simulate_dual

from . import jhsaa as jh

#: ‼️ FIVE COURTS, FIRST TO THREE, AND SEVEN PLAYERS DRESS. S1/S2/S3 + D1/D2 —
#: three singles and two doubles pairs is 3 + 4 = 7 on court. Odd by requirement
#: (see the module docstring): a drawn dual cannot advance anybody.
FORMAT = DualFormat(n_singles=3, n_doubles=2, doubles_team_point=False)

#: Players the card needs (7) and the championship roster CAP (16).
#: ‼️ 16 IS A CEILING, NOT A SQUAD SIZE: a program carries UP TO sixteen frozen-
#: eligible players and dresses seven of them, so "lineups may change between rounds
#: using only eligible championship-roster players" has somewhere to change TO. A
#: program with fewer eligible players carries fewer — it needs `LINEUP` to enter and
#: nothing more.
LINEUP = jh.jv_lineup_need(FORMAT)
ROSTER = 16

#: The phase these duals are archived under. ‼️ ITS OWN PHASE, not "regular" and not
#: the varsity postseason's — a phase is the archive's identity for an EVENT (the
#: rule the JV showcase weekend was given its own phase for). Written on JV rows, so
#: `level` still keeps every one of them out of a varsity record.
PHASE = "jv_state"

#: District berths by how many JV teams the district actually fielded (spec).
#: Read as "up to and including": 2-5 -> 1, 6-9 -> 2, 10-15 -> 3, 16+ -> 4.
DISTRICT_BERTHS = ((5, 1), (9, 2), (15, 3))
DISTRICT_BERTHS_MAX = 4

#: The association's twenty geographic areas, and the State field they play down to.
REGIONS = 20
STATE_FIELD = 16

#: How many region champions go straight to State: 12, so the other eight play in for
#: four seats (13v20, 14v19, 15v18, 16v17) and the draw is exactly sixteen.
#: ‼️ THE TWENTY REGIONS ALWAYS FILL (owner, 2026-09) — the association is ~875 boys'/
#: ~912 girls' programs on full rosters, so every area crowns a champion every season
#: and this is the only shape the event is ever played at. A smaller world (a test
#: fixture) simply crowns fewer and the fold below runs short; that case needs no
#: machinery and must not grow any.
DIRECT_SEEDS = 12

#: What the play-in round is called on a card and in the archive. ‼️ ITS OWN NAME,
#: because it is its own ROUND: twenty champions play down to sixteen, and the State
#: draw then runs 16 → 8 → 4 → 2 in full. The qualifying round never stands in for
#: the Round of 16 — a play-in winner has qualified FOR the draw, not through its
#: first round.
QUALIFYING_NAME = "State Qualifying"


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


def _dress(e: JVEntry, rng_seed: int) -> list:
    """The championship roster named for a dual, and the seven who take the court.

    Lineups may change between rounds, but only from the frozen roster, so the choice
    is made HERE and only ever over `e.players`. Named in frozen-ladder order: the
    event's own anti-sandbagging property, the same one the individual draws get from
    selecting on `ladder_score` rather than on a coach's pick.
    """
    return e.players[:LINEUP]


def play_dual(a: JVEntry, b: JVEntry, *, seed: int) -> tuple:
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
    mf = jh.match_format(PHASE)
    # ‼️ NEUTRAL SITE. A championship is not hosted by one of its entrants — the same
    # call `NEUTRAL_PHASES` makes for the varsity state event and the showcases. Pass
    # no lift rather than rolling one and discarding it.
    res = simulate_dual(jh._squad(a.jv.team, PHASE, la, FORMAT),
                        jh._squad(b.jv.team, PHASE, lb, FORMAT),
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
                      "home": [x.name for x in jh._slot_players(la, PHASE, slot, FORMAT)],
                      "away": [x.name for x in jh._slot_players(lb, PHASE, slot, FORMAT)],
                      "score": jh._score_str(ln), "home_won": bool(hw)})
    shape = f"{FORMAT.n_singles}S/{FORMAT.n_doubles}D"
    # `home` is ORIENTATION ONLY — the site is neutral, and no lift was rolled. It is
    # what `_score_str` and the archived `lines` are written from, so both rows have
    # to agree on which side is which.
    a.jv.schedule.append({"opp": b.name, "home": True, "phase": PHASE,
                          "pf": res.home_points, "pa": res.away_points,
                          "won": home_won, "tied": False, "district": False,
                          "level": jh.LEVEL_JV, "shape": shape, "lines": lines,
                          "played": [p.name for p in la]})
    b.jv.schedule.append({"opp": a.name, "home": False, "phase": PHASE,
                          "pf": res.away_points, "pa": res.home_points,
                          "won": not home_won, "tied": False, "district": False,
                          "level": jh.LEVEL_JV, "shape": shape, "lines": lines,
                          "played": [p.name for p in lb]})
    win = a if home_won else b
    return win, {"home": a.name, "away": b.name,
                 "home_points": res.home_points, "away_points": res.away_points,
                 "winner": win.name}


def _run_bracket(field: list[JVEntry], *, seed: int,
                 round_names: list[str] | None = None) -> tuple:
    """A seeded single-elimination draw over `field`, returning `(champion, bracket)`.

    ‼️ THE BRACKET IS THE VARSITY STATE DRAW'S ARCHIVE SHAPE — `{champion, field,
    rounds, round_names}` with the same game dicts — and that is the whole point: the
    rendering layer already turns that shape into a tree (`state._jh_bracket_cols` →
    `_bracket_canvas` → `templates/_bracket.html`), materialising byes and ordering
    cards by their real feeders. Emitting anything else would mean a fourth bracket
    implementation for an event that draws exactly like the other three.

    Seeded through `engine.tournament.seeded_draw`, so entrants land on the standard
    anchors, the top seeds take any byes, and the draw is then FIXED — no reseeding
    between rounds, the association's rule for every draw it runs.
    """
    import random
    from engine.tournament import seeded_draw
    rng = random.Random(seed)
    size = 1
    while size < len(field):
        size *= 2
    slots: list = [None if r is None else field[r]
                   for r in seeded_draw(len(field), size, len(field), rng)]
    rounds: list = []
    while len(slots) > 1:
        nxt, games = [], []
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if a is None or b is None:                 # a bye, drawn by the renderer
                nxt.append(a or b)
                continue
            win, game = play_dual(a, b, seed=rng.randrange(1 << 30))
            games.append(game)
            nxt.append(win)
        if games:
            rounds.append(games)
        slots = nxt
    champ = slots[0] if slots else None
    return champ, {"champion": champ.name if champ else None,
                   "field": [e.name for e in field], "rounds": rounds,
                   "round_names": list(round_names or ())}


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


def run_regionals(quals: list[JVEntry], *, seed: int) -> tuple:
    """Each region crowns one champion. Returns `(champions, brackets by region)`.

    The draw sizes itself to however many qualifiers a region drew — `seeded_draw`
    pads to the next power of two and byes the top seeds — so nothing here needs to
    know the number in advance.
    """
    by_region: dict[str, list[JVEntry]] = {}
    for e in quals:
        by_region.setdefault(e.region, []).append(e)
    champs, out = {}, {}
    for i, region in enumerate(sorted(by_region)):
        teams = sorted(by_region[region], key=lambda e: (-seed_key(e), e.name))
        champ, br = _run_bracket(teams, seed=seed + 101 * i)
        champs[region], out[region] = champ, br
    return champs, out


def qualifying_pairs(ranked: list[JVEntry]) -> list[tuple[JVEntry, JVEntry]]:
    """The play-in: 13v20, 14v19, 15v18, 16v17 (spec).

    ‼️ A REAL SAVE FILLS ALL TWENTY REGIONS — the association is ~875 boys'/~912
    girls' programs on full rosters, so this is exactly four pairs and the State field
    is exactly sixteen. It is folded off the ranking rather than typed as four seeds
    so that a thin test season (or a change to `DIRECT_SEEDS`) still produces a legal
    draw instead of pairing the wrong seeds — that graceful case is a property of the
    fold, never a design target.
    """
    rest = ranked[DIRECT_SEEDS:]
    return [(rest[i], rest[len(rest) - 1 - i]) for i in range(len(rest) // 2)]


def run_jv_state(jv: dict, *, gender: str, year: int, seed: int = 0) -> dict:
    """The whole JV team postseason for one gender.

    Returns the archive `world.run_jhsaa` stores: the field, every region's draw, the
    play-in and the State bracket, each in the shape the bracket renderer already
    reads. `{}` when nothing can be staged — a world whose programs never played a JV
    season has no event, which is a real answer and not an error.
    """
    field = entries(jv)
    if not field:
        return {}
    quals = district_qualifiers(field)
    champs, regions = run_regionals(quals, seed=seed + 7919 * (gender == "boys"))
    ranked = sorted(champs.values(), key=lambda e: (-seed_key(e), e.name))

    # THE STATE QUALIFYING ROUND — one round, archived as a bracket of its own so it
    # renders beside the others rather than as a hand-built list. It is NOT a column
    # of the State tree: eight teams playing into four seats do not halve into a
    # sixteen-team draw, and `_bracket_canvas` links columns positionally.
    playin_field = [e for pair in qualifying_pairs(ranked) for e in pair]
    playin, winners = {}, []
    if playin_field:
        games = []
        for i, (hi, lo) in enumerate(qualifying_pairs(ranked)):
            win, game = play_dual(hi, lo, seed=seed + 3301 + i)
            games.append(game)
            winners.append(win)
        playin = {"champion": None, "field": [e.name for e in playin_field],
                  "rounds": [games], "round_names": [QUALIFYING_NAME]}

    # Seed order is preserved: a play-in winner enters at its own statewide rank, not
    # at the bottom of the field it just came through.
    # ‼️ BY IDENTITY. `JVEntry` is an ordinary dataclass, so `__eq__` is field-wise and
    # `__hash__` is None — a set of entries raises TypeError. It raised only once a
    # season crowned MORE than `DIRECT_SEEDS` regions, i.e. only when a play-in was
    # actually played, which a small fixture never reaches and the real association
    # reaches every year.
    qualified = {id(e) for e in winners}
    draw_field = (list(ranked[:DIRECT_SEEDS])
                  + [e for e in ranked[DIRECT_SEEDS:] if id(e) in qualified])[:STATE_FIELD]
    champ, state = _run_bracket(draw_field, seed=seed + 5701)
    return {
        "field": [e.name for e in field],
        "qualifiers": [e.name for e in quals],
        "regions": regions,
        "region_champions": {k: v.name for k, v in champs.items()},
        "ranked": [e.name for e in ranked],
        "play_in": playin,
        "state": state,
        "champion": champ.name if champ else "",
    }
