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

def test_it_is_three_singles_and_three_doubles():
    assert ji.SINGLES_FLIGHTS == ("S1", "S2", "S3")
    assert ji.DOUBLES_FLIGHTS == ("D1", "D2", "D3")
    assert len(ji.FLIGHTS) == 6


def test_the_flights_are_the_same_slot_names_a_dual_uses():
    """‼️ This is what makes FULL CREDIT free. `jhsaa_awards` prices a résumé row by
    its flight through `jhsaa.FLIGHT_WEIGHTS`; because the individual flights ARE
    dual slot names, an individual result is weighted by the court it was won on
    with no new entry in that table. Rename a flight and the weighting silently
    stops applying — the row would still be scored, at whatever a missing key
    gets."""
    for f in ji.FLIGHTS:
        assert f in jh.FLIGHT_WEIGHTS, f


def test_no_dual_format_reaches_this_module(teams):
    """‼️ Owner rule: "even in 1A, it's still a 3/3 event". 1A's postseason dresses
    EIGHT under the 2S/3D pilot and its league season eleven, and neither may change
    what this event is. Selection must be identical whichever group it is told."""
    a = ji.flight_entry(teams[0], "D3")
    for group in ("1A", "5A", "9A"):
        # `flight_entry` takes no group at all, which is the guarantee; this pins
        # that the ranks it draws are fixed rather than looked up per class.
        assert ji.FLIGHT_RANKS["D3"] == (7, 8)
    assert a is not None and len(a.players) == 2


def test_entries_come_off_the_ability_ladder_not_the_league_lineup(teams):
    """‼️ The league's 3S/4D format is doubles-forward: S1=#1, doubles=#2-#9,
    S2/S3=#10-#11. So a program's "No. 2 singles" in a league dual is its TENTH-best
    player, and entering that person in the No. 2 singles championship would be
    absurd. S2 here is rank #2 of the ability ladder."""
    ts = teams[0]
    ladder = jh._order(ts)
    assert ji.flight_entry(ts, "S1").players[0].pid == ladder[0].pid
    assert ji.flight_entry(ts, "S2").players[0].pid == ladder[1].pid
    assert ji.flight_entry(ts, "S3").players[0].pid == ladder[2].pid
    assert [p.pid for p in ji.flight_entry(ts, "D1").players] == \
           [ladder[3].pid, ladder[4].pid]


def test_the_nine_entrants_are_all_different_people(teams):
    """A pair is two DIFFERENT people and no player may be in two flights — unlike a
    short dual side, which wraps a player onto two lines rather than crashing."""
    for ts in teams[:12]:
        pids = [p.pid for f in ji.FLIGHTS for p in ji.flight_entry(ts, f).players]
        assert len(pids) == len(set(pids)) == 9


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
    """‼️ IMPORTED, not re-declared, so the two events cannot drift. Best-of-3 with a
    10-point match tiebreak deciding set — which is also why no `best_of_3_ad` preset
    exists: the constant was there all along."""
    from app.individuals import INDIV_FMT
    assert ji.INDIV_FORMAT is INDIV_FMT
    assert ji.INDIV_FORMAT.best_of == 3
    assert ji.INDIV_FORMAT.final_set_tiebreak is True
    assert ji.INDIV_FORMAT.final_set_tiebreak_target == 10


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


def test_individual_s2_s3_escape_the_LEAGUE_s2_s3_deflation():
    """‼️ AN INDIVIDUAL No. 2 SINGLES TITLE IS A REAL No. 2 SINGLES RESULT, and the
    event's own phase is the only thing that makes that true.

    `jhsaa_awards.FLIGHT_S2S3_REGULAR` deflates S2/S3 to roughly D4's weight — but
    ONLY when `phase == "regular"`, because the league's 3S/4D format puts ranks
    #10-#11 in those seats. This event's S2 and S3 are the program's genuine #2 and
    #3 off the ability ladder, so they must be priced at the table's real S2/S3.

    Written as a phase name, that is invisible: had this event been archived as
    `phase="regular"` to get "ordinary weight", every individual No. 2 singles
    champion in Jefferson would have been scored as if they were a tenth-best
    player, silently, and the résumés would still have looked fine."""
    from app import jhsaa_awards as jaw
    for slot in ("S2", "S3"):
        assert jaw._weight(slot, ji.PHASE, jh.POSTSEASON) == jh.FLIGHT_WEIGHTS[slot]
        assert jaw._weight(slot, "regular", jh.POSTSEASON) < \
               jaw._weight(slot, ji.PHASE, jh.POSTSEASON)


# --- mixed doubles -----------------------------------------------------------

def test_mixed_draws_from_below_the_nine_the_main_event_uses():
    """A CONSOLATION event (owner rule): it exists for the players the six flights
    have no seat for, so it starts at rank #9 — never the school's best two."""
    assert ji.MIXED_FROM_RANK == 9
    assert ji.MIXED_FROM_RANK == max(max(r) for r in ji.FLIGHT_RANKS.values()) + 1


def test_the_roster_floor_guarantees_a_mixed_pool():
    """‼️ If `ROSTER_FLOOR` ever drops to 9 the event silently empties. The floor is
    16 and the main draw consumes nine, so every roster carries at least seven
    below the line in each gender."""
    assert jh.ROSTER_FLOOR - ji.MIXED_FROM_RANK >= 1


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
