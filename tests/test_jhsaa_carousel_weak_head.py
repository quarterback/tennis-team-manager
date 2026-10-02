"""A weak head on a bad program goes when a better assistant nearby wants the job
(owner rule 2026-10, `jhsaa_coaches._weak_head_firings`).

The standing rule judges a head against the program's OWN norm, so a program
that has always been bad keeps a bad coach for ever. This one judges the
program against its classification and the coach against the class's heads —
and never fires into a void: no willing, better assistant in the area, no
firing."""
import sqlite3
from types import SimpleNamespace

import app.jhsaa_coaches as jc


def _conn(history):
    conn = sqlite3.connect(":memory:")
    conn.executescript(jc._SCHEMA)
    conn.executemany(
        "INSERT INTO jhsaa_coach_history (world_id, year, ident, gender, slot, coach_id,"
        " school, classification, grp, wins, losses, ties, eff)"
        " VALUES (1, ?, ?, 'girls', 'head', ?, ?, '3A', '3A', ?, ?, 0, '')",
        [(y, i, c, i, w, l) for y, i, c, w, l in history])
    conn.commit()
    return conn


def _coach(cid, overall):
    return jc.Coach(coach_id=cid, name=f"Coach {cid}", grades={}, overall=overall)


def _world(weak_overall=30, asst_overall=60, asst_area="North", asst_wants=0.1,
           tenure=4):
    sy = 2100
    schools = {i: SimpleNamespace(name=i, classification="3A", area="North")
               for i in ("A", "B", "C", "D", "E", "F")}
    schools["X"] = SimpleNamespace(name="X", classification="3A", area=asst_area)
    # A is the bottom of the class for three seasons; the rest win.
    hist = []
    for y in range(sy - 3, sy):
        hist.append((y, "A", "hA", 2, 16))
        for i in ("B", "C", "D", "E", "F", "X"):
            hist.append((y, i, "h" + i, 12, 6))
    coaches = {"hA": _coach("hA", weak_overall), "aX": _coach("aX", asst_overall)}
    where = {"hA": ("A", "head", sy - tenure), "aX": ("X", "asst1", sy - 3)}
    for i in ("B", "C", "D", "E", "F", "X"):
        coaches["h" + i] = _coach("h" + i, 55)
        where["h" + i] = (i, "head", sy - 6)
    wants = {cid: (asst_wants if cid == "aX" else 0.99) for cid in where}
    return _conn(hist), sy, schools, where, coaches, wants


def _fired(**kw):
    conn, sy, schools, where, coaches, wants = _world(**kw)
    # Force the dice so the test reads the rule, not the roll.
    jc.FIRE_WEAK_CHANCE, keep = 1.0, jc.FIRE_WEAK_CHANCE
    try:
        out = jc._weak_head_firings(conn, 1, "girls", sy, schools, where, coaches,
                                    wants, set())
    finally:
        jc.FIRE_WEAK_CHANCE = keep
    return {i for i, _c, _why in out}, out


def test_a_weak_head_on_the_worst_program_goes_when_a_better_area_assistant_wants_in():
    fired, out = _fired()
    assert fired == {"A"}
    why = out[0][2]
    assert "bottom of 3A" in why and "Coach aX" in why and "wants the job" in why


def test_nobody_is_fired_into_a_void():
    assert _fired(asst_area="South")[0] == set()          # nobody nearby
    assert _fired(asst_wants=0.95)[0] == set()            # nearby, not looking
    assert _fired(asst_overall=33)[0] == set()            # nearby, no upgrade


def test_a_head_rated_like_the_class_keeps_the_job_and_a_new_hire_gets_time():
    assert _fired(weak_overall=58)[0] == set()            # bad program, not a bad coach
    assert _fired(tenure=1)[0] == set()                   # first season in the seat
