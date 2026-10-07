"""The JHSAA individual state tournaments (`app/jhsaa_individuals.py`).

Data-bearing, on a real (small) classification's rosters rather than an empty
archive — the section's own rule: `tests/test_jhsaa_routes.py` renders every JHSAA
surface with nothing archived and stayed green through four faults that only exist
once there is data.
"""
import pytest

from app import jhsaa as jh
from app import jhsaa_individuals as ji


YEAR, SALT = 2039, "indiv-test"


@pytest.fixture(scope="module")
def teams():
    """One real classification's programs, rostered but with no season played —
    which is the state the tournament actually runs in (preseason)."""
    schools = [s for s in jh.load_schools("girls") if s.group == "1A"]
    return jh.district_teams(schools[:40], YEAR, SALT)


@pytest.fixture(scope="module")
def draw(teams):
    return ji.run_flight(teams, "girls", "1A", "S1", seed=11)


# --- what the event IS -------------------------------------------------------

def test_every_class_keeps_the_core_six():
    """The original No. 1-3 singles and No. 1-3 doubles championships are a FLOOR
    (owner rule 2026-10): no class loses one because its championship dual has
    fewer singles or doubles flights."""
    assert ji.SINGLES_FLIGHTS == ("S1", "S2", "S3")
    assert ji.DOUBLES_FLIGHTS == ("D1", "D2", "D3")
    for g in jh.ROAD_GROUPS:
        assert set(ji.CORE_FLIGHTS) <= set(ji.flights_for(g)), g


def test_each_class_adds_every_flight_its_state_format_contests():
    """Owner rule 2026-10: the slate is the core six plus every further flight the
    class's STATE team format plays — 110 championships a gender."""
    want = {"9A": "S1-S4 D1-D5", "8A": "S1-S4 D1-D5", "7A": "S1-S4 D1-D5",
            "Group 1": "S1-S4 D1-D5", "10B": "S1-S4 D1-D5",
            "6A": "S1-S3 D1-D4", "11B": "S1-S3 D1-D4",
            "5A": "S1-S6 D1-D5",
            "4A": "S1-S3 D1-D4", "3A": "S1-S3 D1-D4", "2A": "S1-S3 D1-D4",
            "Group 3": "S1-S3 D1-D4",
            "1A": "S1-S3 D1-D3", "Group 2": "S1-S3 D1-D3"}
    for g, spec in want.items():
        s, d = spec.split()
        ns, nd = int(s[-1]), int(d[-1])
        assert ji.flights_for(g) == (tuple(f"S{i}" for i in range(1, ns + 1))
                                     + tuple(f"D{i}" for i in range(1, nd + 1))), g
        f = jh.dual_format("state", g)
        assert ns == max(3, f.n_singles) and nd == max(3, f.n_doubles), g
    assert set(want) == set(jh.ROAD_GROUPS)
    assert sum(len(ji.flights_for(g)) for g in jh.ROAD_GROUPS) == 110
    # FLIGHTS is exactly the union — every name lookup covers every class.
    assert set(ji.FLIGHTS) == {f for g in jh.ROAD_GROUPS for f in ji.flights_for(g)}


def test_flight_positions_read_the_arranged_sheet_in_slot_order():
    """`flight_ranks` indexes the ARRANGED sheet, which is in slot order
    [S1..Sn, D1a, D1b, …] — every position used once, singles first."""
    assert ji.flight_ranks("1A") == ji.FLIGHT_RANKS
    assert ji.flight_ranks("Group 2") == ji.FLIGHT_RANKS
    r5 = ji.flight_ranks("5A")
    assert r5["S6"] == (5,) and r5["D1"] == (6, 7) and r5["D5"] == (14, 15)
    for g in jh.ROAD_GROUPS:
        pos = [i for f in ji.flights_for(g) for i in ji.flight_ranks(g)[f]]
        assert pos == list(range(ji.entry_count(g))), g


def test_the_slate_format_is_the_state_format_or_wider():
    """Arranged at the class's State format wherever the slate matches it; where
    the kept core flights outrun it (1S/4D, 2S/3D) the slate is the same mechanism
    one or two singles seats wider — never narrower."""
    for g in jh.ROAD_GROUPS:
        sf, st = ji.slate_format(g), jh.dual_format("state", g)
        assert sf.n_doubles == max(3, st.n_doubles), g
        assert sf.n_singles == max(3, st.n_singles), g
    for g in ("9A", "5A", "6A", "Group 2", "10B", "11B"):
        sf, st = ji.slate_format(g), jh.dual_format("state", g)
        assert (sf.n_singles, sf.n_doubles) == (st.n_singles, st.n_doubles), g


def test_the_flights_are_the_same_slot_names_a_dual_uses():
    """‼️ This is what makes FULL CREDIT free. `jhsaa_awards` prices a résumé row by
    its flight through `jhsaa.FLIGHT_WEIGHTS`; because the individual flights ARE
    dual slot names, an individual result is weighted by the court it was won on
    with no new entry in that table. Rename a flight and the weighting silently
    stops applying — the row would still be scored, at whatever a missing key
    gets."""
    for f in ji.FLIGHTS:
        assert f in jh.FLIGHT_WEIGHTS, f


def test_a_narrow_format_never_shrinks_the_slate(teams):
    """‼️ Owner rule: "even in 1A, it's still a 3/3 event" — and since 2026-10 the
    State format can only WIDEN a class's slate, never narrow it. 1A's 2S/3D and
    Group 2's 3S/3D keep the six-flight sheet exactly."""
    a = ji.flight_entry(teams[0], "D3")
    for group in ("1A", "Group 2"):
        assert ji.flight_ranks(group)["D3"] == (7, 8)
        assert ji.flights_for(group) == ji.CORE_FLIGHTS
    assert a is not None and len(a.players) == 2


def test_entries_are_seated_by_the_state_arrangement_not_by_rank(teams):
    """‼️ Owner rule 2026-10: the preseason ability ladder is the INPUT, and the
    seats are assigned by the same arrangement the class uses at team State. The
    entrants are exactly the top of the ladder; who plays which flight is
    `_arrange_postseason`'s decision at the slate's width — so a strong doubles
    player can be seated at D1 rather than forced into a singles flight by rank."""
    for ts in teams[:12]:
        g = ts.school.group
        n = ji.entry_count(g)
        ladder = jh._order(ts)
        want = jh._arrange_postseason(ladder[:n], ji.slate_format(g), ts.sibling_ids,
                                      ts.pair_counts, ts.culture)
        sheet = ji.arrange_sheet(ts)
        assert [p.pid for p in sheet] == [p.pid for p in want]
        assert {p.pid for p in sheet} == {p.pid for p in ladder[:n]}
        for f in ji.flights_for(g):
            got = [p.pid for p in ji.flight_entry(ts, f).players]
            assert got == [sheet[i].pid for i in ji.flight_ranks(g)[f]], f
        # S1-S3 + D1 come from the top five (the anti-stacking pool), D2 down below
        top5 = {p.pid for p in ladder[:5]}
        for f in ("S1", "S2", "S3", "D1"):
            assert {p.pid for p in ji.flight_entry(ts, f).players} <= top5, f


def test_a_5a_sheet_seats_the_top_eight_at_s1_s6_and_d1():
    """The owner's worked example: 5A takes sixteen, the top EIGHT supply S1-S6 and
    D1, and #9-#16 form D2-D5."""
    schools = [s for s in jh.load_schools("girls") if s.group == "5A"][:6]
    for ts in jh.district_teams(schools, YEAR, SALT):
        ladder = jh._order(ts)
        if len(ladder) < 16:
            continue
        sheet = ji.arrange_sheet(ts)
        top8 = {p.pid for p in ladder[:8]}
        assert {p.pid for p in sheet[:8]} == top8
        assert {p.pid for p in sheet[8:16]} == {p.pid for p in ladder[8:16]}


def test_the_nine_entrants_are_all_different_people(teams):
    """A pair is two DIFFERENT people and no player may be in two flights — unlike a
    short dual side, which wraps a player onto two lines rather than crashing."""
    for ts in teams[:12]:
        pids = [p.pid for f in ji.flights_for(ts.school.group)
                for p in ji.flight_entry(ts, f).players]
        assert len(pids) == len(set(pids)) == ji.entry_count(ts.school.group)


def test_nobody_is_entered_in_two_flights_once_results_are_credited(teams):
    """‼️ THE REGRESSION THAT THE TEST ABOVE CANNOT SEE, because it selects from a
    FRESH TeamSeason and the fault only exists once a draw has been credited.

    `credit_draw` writes into `ts.records`; `_order` sorts on `ladder_score(p,
    ts.records.get(p.pid))`. So crediting S1 MOVES the ladder that S2 is then
    selected from, and a No. 1 who slipped to No. 2 on his own S1 result was entered
    at No. 2 singles as well while somebody else was entered nowhere. Measured on a
    real 1A boys field: 23 of 751 players in two flights, nothing raised, every draw
    internally consistent. `entry_sheet` freezes the order before the first draw.

    ‼️ Counting SEATS does not catch it — a program still fills nine (1+1+1+2+2+2)
    when one person holds two of them. Count DISTINCT PIDS."""
    by_group = {"1A": {"all": teams}}
    res = ji.run_preseason(by_group, "girls", YEAR, seed=1)
    per_school = {}
    for flight, draw in res["1A"].items():
        for e in draw["entries"]:
            per_school.setdefault(e["school"], []).extend(
                p["pid"] for p in e["players"])
    assert per_school, "no draws were produced"
    for school, pids in per_school.items():
        assert len(pids) == 9, (school, len(pids))
        assert len(set(pids)) == 9, (school, "a player entered in two flights")


# --- the draw ----------------------------------------------------------------

def test_the_field_is_open_every_program_enters(teams, draw):
    """No district quota (owner rule). Every program with a full ladder is in."""
    assert len(draw.entries) == len(teams)


def test_seeds_are_a_quarter_of_the_bracket(draw):
    """The tennis convention `engine.tournament.seed_count` already implements —
    128 -> 32, 64 -> 16. Not re-derived here."""
    from engine.tournament import seed_count
    assert draw.n_seeds == seed_count(len(draw.entries))


def test_the_draw_is_deterministic(teams):
    a = ji.run_flight(teams, "girls", "1A", "S2", seed=5)
    b = ji.run_flight(teams, "girls", "1A", "S2", seed=5)
    assert a.champion.key == b.champion.key
    assert [m.scoreline for r in a.rounds for m in r] == \
           [m.scoreline for r in b.rounds for m in r]


def test_every_entrant_gets_exactly_one_finish(draw):
    fin = draw.finishes()
    assert len(fin) == len(draw.entries)
    assert fin[draw.champion.key] == ("Champion", "CHAMP")
    assert fin[draw.runner_up.key] == ("Runner-up", "F")


def test_the_draw_eliminates_exactly_one_player_a_match(draw):
    played = sum(len(r) for r in draw.rounds)
    assert played == len(draw.entries) - 1


# --- finish banding ----------------------------------------------------------

def test_the_bands_name_every_round_of_a_128_draw():
    """‼️ `state._finish_short` would render R128, R64 AND R32 all as QUAL — its own
    docstring explains why it needs no field parameter, and that reasoning holds only
    for the TEAM event, whose fields all converge on a 24-team main draw. This event
    has no qualifying and no convergence, so it bands for itself."""
    assert [ji.finish_band(n)[1] for n in (1, 2, 4, 8, 16, 32, 64, 128)] == \
        ["CHAMP", "F", "SF", "QF", "OF", "R32", "R64", "R128"]


def test_an_odd_alive_count_rounds_up_to_its_round():
    """A 107-entry field is 107 alive in the opening round, not 128."""
    assert ji.finish_band(107)[1] == "R128"
    assert ji.finish_band(93)[1] == "R128"
    assert ji.finish_band(5)[1] == "QF"


def test_the_round_of_16_is_called_the_octofinals():
    """The association's own word — the team State draw already uses it."""
    assert ji.round_label("Round of 16") == "Octofinals"
    assert ji.round_label("Quarterfinals") == "Quarterfinals"


# --- scoring -----------------------------------------------------------------

def test_it_plays_the_college_individual_championships_format():
    """‼️ IMPORTED, not re-declared, so the two events cannot drift — which is also
    why no `best_of_3_ad` preset exists: the constant was there all along.

    Best-of-3, no-ad, and a FULL third set (owner rule 2026-08 — it was a 10-point
    match tiebreak, changed at BOTH levels, which is why the import survived the
    change untouched)."""
    from app.individuals import INDIV_FMT
    assert ji.INDIV_FORMAT is INDIV_FMT
    assert ji.INDIV_FORMAT.best_of == 3
    assert ji.INDIV_FORMAT.no_ad is True
    assert ji.INDIV_FORMAT.final_set_tiebreak is False
    assert ji.INDIV_FORMAT.set_tiebreak is True          # ...but 6-6 is a tiebreak


def test_every_jhsaa_match_is_now_scored_the_same_way():
    """The individual event used to be the ONE place JHSAA scoring differed from
    the league season. It no longer is: a full third set makes them agree field
    for field. Pinned because it is a property worth losing loudly."""
    from app.jhsaa import MATCH_FORMAT
    assert ji.INDIV_FORMAT.to_dict() == MATCH_FORMAT.to_dict()


def test_no_ad_preset_was_not_added_to_the_engine():
    from engine.format import PRESETS
    assert "best_of_3_ad" not in PRESETS


# --- credit ------------------------------------------------------------------

def test_full_credit_lands_on_records_and_the_award_resume(teams, draw):
    """Owner rule: treat them like the regular season. Both halves must land — the
    W-L that moves `ladder_score`, and the match log the awards read."""
    fresh = jh.district_teams([t.school for t in teams], YEAR, SALT + "-credit")
    by_school = {t.school.name: t for t in fresh}
    d = ji.run_flight(fresh, "girls", "1A", "S1", seed=11)
    n = ji.credit_draw(d, by_school)
    assert n == 2 * sum(len(r) for r in d.rounds)          # singles: 2 a match
    champ = by_school[d.champion.school]
    pid = d.champion.players[0].pid
    w, l = champ.records[pid]
    assert l == 0 and w == sum(1 for r in d.rounds for m in r
                               if d.champion.key in (m.hi.key, m.lo.key))
    rows = champ.matches[pid]
    assert {r[0] for r in rows} == {"S1"}                  # the flight is the slot
    assert {r[2] for r in rows} == {ji.PHASE}
    assert all(r[3] for r in rows)                         # opponent pids recorded


def test_a_doubles_pair_credits_both_partners(teams):
    fresh = jh.district_teams([t.school for t in teams], YEAR, SALT + "-pair")
    by_school = {t.school.name: t for t in fresh}
    d = ji.run_flight(fresh, "girls", "1A", "D1", seed=3)
    n = ji.credit_draw(d, by_school)
    assert n == 4 * sum(len(r) for r in d.rounds)          # doubles: 4 a match
    ts = by_school[d.champion.school]
    a, b = (p.pid for p in d.champion.players)
    assert ts.records[a] == ts.records[b]
    # `partner` is what `jhsaa_awards._pairs` keys a partnership on.
    assert {r[4] for r in ts.matches[a]} == {b}
    assert {r[4] for r in ts.matches[b]} == {a}


def test_the_phase_is_not_postseason_so_awards_price_it_as_ordinary():
    """‼️ "Treat them like the regular season" is the DEFAULT with nothing to
    configure — `_weight` multiplies by PHASE_WEIGHT only inside POSTSEASON, and
    the individual phase is deliberately outside it."""
    from app import jhsaa_awards as jaw
    assert ji.PHASE not in jh.POSTSEASON
    assert jaw._weight("S1", ji.PHASE, jh.POSTSEASON) == \
           jaw._weight("S1", "regular", jh.POSTSEASON) == jh.FLIGHT_WEIGHTS["S1"]


def test_individual_s2_s3_are_priced_at_the_table_and_so_is_the_league_now():
    """An individual No. 2 singles title is a real No. 2 singles result and is
    priced at the table's S2. Under the 2027-08 doubles-forward league seating the
    awards deflated a REGULAR-season S2/S3 (ranks #10-#11 sat there) and this
    event's own phase was what kept it clear of that; since the league seats
    #1-#3 at S1-S3 (owner rule 2026-09) the deflation is retired and the two
    phases price S2/S3 identically. Both halves pinned: the override is empty, and
    a regular-season S2 is no longer scored as a tenth-best player."""
    from app import jhsaa_awards as jaw
    assert jaw.FLIGHT_S2S3_REGULAR == {}
    for slot in ("S2", "S3"):
        assert jaw._weight(slot, ji.PHASE, jh.POSTSEASON) == jh.FLIGHT_WEIGHTS[slot]
        assert jaw._weight(slot, "regular", jh.POSTSEASON) == \
               jaw._weight(slot, ji.PHASE, jh.POSTSEASON)


# --- mixed doubles -----------------------------------------------------------

def test_mixed_draws_from_below_the_nine_the_main_event_uses():
    """A CONSOLATION event (owner rule): it exists for the players the main slate
    has no seat for, so it starts directly below the class's entries — #9 on the
    six-flight sheet, #16 in 5A — never the school's best two."""
    assert ji.MIXED_FROM_RANK == 9
    assert ji.MIXED_FROM_RANK == max(max(r) for r in ji.FLIGHT_RANKS.values()) + 1
    for g in jh.ROAD_GROUPS:
        assert ji.mixed_from_rank(g) == max(
            max(r) for r in ji.flight_ranks(g).values()) + 1, g


def test_the_roster_floor_guarantees_a_mixed_pool():
    """‼️ If `ROSTER_FLOOR` ever drops to the widest slate's entry count the event
    silently empties for that class. 5A enters sixteen; the floor is 20."""
    for g in jh.ROAD_GROUPS:
        assert jh.ROSTER_FLOOR - ji.mixed_from_rank(g) >= 1, g


def test_mixed_is_one_bracket_not_a_flighted_ladder():
    """Owner rule: one flight, one bracket, one entry per school."""
    assert "XD" not in ji.FLIGHTS
    assert ji.MIXED_PHASE != ji.PHASE


# --- persistence -------------------------------------------------------------

def test_a_match_stores_indices_not_copies_of_its_entrants(draw):
    """‼️ The first version wrote the full entrant dict on BOTH sides of every match,
    so a 128 draw carried each entrant up to eight times over — 3.5 MB a gender
    against 1.7 indexed. `entries` is the entrant list and a draw is a graph over
    it, which is how the engine's own TourneyMatch already models it."""
    d = ji.draw_to_dict(draw)
    for rnd in d["rounds"]:
        for m in rnd:
            assert isinstance(m["hi"], int) and isinstance(m["lo"], int)
            assert 0 <= m["hi"] < len(d["entries"])
    assert isinstance(d["champion"], int)
    assert d["entries"][d["champion"]]["label"] == draw.champion.label


def test_the_flattened_draw_is_json_round_trippable(draw):
    import json
    d = ji.draw_to_dict(draw)
    assert json.loads(json.dumps(d)) == d


def test_every_entry_carries_pids_so_a_page_can_link_a_player(draw):
    """By PID, never by name — a pid keys on (school, gender, entry year, seat), so
    it is stable across all four years and matches the award rows."""
    d = ji.draw_to_dict(draw)
    for e in d["entries"]:
        assert e["players"] and all(p["pid"] for p in e["players"])


def test_the_draw_seed_is_stable_across_processes():
    """‼️ NEVER `hash()` — Python salts str hashes per process and these draws are
    ARCHIVED, so the same season has to mean the same thing after a restart."""
    import subprocess
    import sys
    code = ("import sys; sys.path.insert(0, '.');"
            " from app.jhsaa_individuals import _draw_seed;"
            " print(_draw_seed(0, 'girls', '2039', '5A', 'S1'))")
    out = [subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, env={"PYTHONHASHSEED": s, "PATH": "/usr/bin:/bin",
                                          "TENNIS_DB_PATH": "/tmp/_seedchk.db"}).stdout
           for s in ("1", "2")]
    assert out[0].strip() and out[0] == out[1]
