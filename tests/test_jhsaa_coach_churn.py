"""Turnover pressure, mobility and the promotion signal in the coaching carousel
(owner rule 2026-10). Pure folds and in-memory reads — no season is played."""
import json
import sqlite3
from types import SimpleNamespace

import app.jhsaa_coaches as jc


def test_a_programs_churn_point_is_stable_inside_its_tier_band_and_scaled_by_archetype():
    lo, hi = jc.CHURN_TIER_BAND["poor"]
    p = jc.program_churn("Harrow", "poor", "", "salt")
    assert lo <= p <= hi
    assert p == jc.program_churn("Harrow", "poor", "", "salt")      # one draw, stable
    assert p != jc.program_churn("Harrow", "elite", "", "salt")     # moves with the tier
    assert jc.program_churn("Harrow", "poor", "neglect", "salt") == min(
        jc.CHURN_MAX, p * jc.CHURN_ARCHETYPE["neglect"])
    assert jc.program_churn("Harrow", "poor", "blue_blood", "salt") < p
    # Strong programs are stable, weak ones a wide band whose top is a revolving door.
    assert jc.CHURN_TIER_BAND["dynasty"][1] < jc.CHURN_TIER_BAND["abysmal"][0]
    assert jc.CHURN_TIER_BAND["abysmal"][1] >= 0.4


def test_tenure_and_age_reduce_mobility_but_never_block_it():
    assert jc._mobility(45, 3) == 1.0
    assert jc._mobility(45, 14) == 0.5
    assert jc._mobility(63, 14) == 0.25
    assert jc._mobility(63, 2) == 0.5
    assert jc._mobility(59, 9) == 1.0          # never 50 as the age threshold
    assert all(jc._mobility(a, t) > 0 for a in (40, 60, 75) for t in (0, 10, 30))


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(jc._SCHEMA)
    conn.execute("CREATE TABLE world_jhsaa_season_row (world_id INTEGER, year INTEGER,"
                 " gender TEXT, school TEXT, v INTEGER, data TEXT)")
    conn.execute("CREATE TABLE jhsaa_coach_award (world_id INTEGER, year INTEGER, gender TEXT,"
                 " level TEXT, grp TEXT, district TEXT, rank INTEGER, school TEXT, ident TEXT,"
                 " coach_id TEXT, coach_name TEXT, score REAL, detail TEXT)")
    return conn


def test_the_promotion_signal_reads_a_state_title_a_coy_and_a_top_record():
    conn = _conn()
    schools = {i: SimpleNamespace(name=i, classification="2A", area="N", enrollment=300)
               for i in ("Champ", "Final", "Plain", "Coy", "Record")}
    heads = {i: "h" + i for i in schools}
    conn.executemany("INSERT INTO world_jhsaa_season_row VALUES (1, 70, 'girls', ?, 5, ?)", [
        ("Champ", json.dumps({"champion": True, "state_finish": "Champion", "season_year": 2101})),
        ("Final", json.dumps({"champion": False, "state_finish": "Finalist"})),
        ("Plain", json.dumps({"champion": False, "state_finish": ""})),
    ])
    conn.execute("INSERT INTO jhsaa_coach_award (world_id, year, gender, level, rank, coach_id)"
                 " VALUES (1, 2100, 'girls', 'state', 1, 'hCoy')")
    conn.execute("INSERT INTO jhsaa_coach_award (world_id, year, gender, level, rank, coach_id)"
                 " VALUES (1, 2090, 'girls', 'state', 1, 'hPlain')")      # outside the window
    recent = {"Record": 0.9, "Champ": 0.8, "Final": 0.6, "Plain": 0.3, "Coy": 0.5}
    sig = jc._promotion_signal(conn, 1, "girls", 2101, schools, heads, recent)
    assert sig["hChamp"][0] == jc.PROMO_TITLE       # the top quarter of five is ONE: Record
    assert "State champion 2101" in sig["hChamp"][1]
    assert sig["hFinal"] == (jc.PROMO_FINAL, "State finalist")
    assert sig["hCoy"] == (jc.PROMO_COY_STATE, "State COY 2100")
    assert "hPlain" not in sig
    assert sig["hRecord"][0] == jc.PROMO_RECORD and "top of 2A" in sig["hRecord"][1]
    # The signal is a HEAD-job edge; it names facts (a title, an award), never a reason to leave.
    for _edge, note in sig.values():
        assert "left" not in note.lower()


def test_a_leave_line_empties_the_seat_and_is_a_departure_for_the_commit_rules():
    assert "leave" in jc.DEPARTURES
    # A vetoed leave keeps its seat exactly as a vetoed retirement does: the same
    # tuple the commit reads for both.
    assert set(jc.DEPARTURES) >= {"retire", "fire"}
