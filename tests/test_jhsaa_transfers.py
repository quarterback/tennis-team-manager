"""Offseason transfers — a career can hold several moves.

It held exactly ONE. A second move meant cancelling the first, and because the
player card DERIVES which school each season belonged to from this record, the
seasons actually played at the forgotten school were re-attributed to the origin
and their results read 0-0 — while the archived duals still named the right school,
so two surfaces disagreed with nothing erroring. The college side has always written
a history row per player per season; this is the same idea in the shape high school
needs, since a move only ever happens between seasons.
"""
import pytest

from app import jhsaa as jh
from app import overrides as ov


@pytest.fixture
def mover():
    """A real ninth-grader with a resolvable seat — the transfer store keys on a pid
    that is a one-way hash of (origin, gender, entry year, seat), so this has to be
    somebody `build_roster` really produces."""
    schools = jh.load_schools("girls")
    a, b, c = schools[0], schools[1], schools[2]
    p = next(q for q in jh.build_roster(a, 2027, "") if q.grade == 9)
    seat = jh.resolve_seat(a, p.entry_year, p.pid)
    assert seat is not None
    for pid in list(ov.get_jhsaa_transfers()):
        ov.clear_jhsaa_transfer(pid)
    jh._transfer_cache.clear()
    yield {"a": a, "b": b, "c": c, "p": p, "seat": seat}
    for pid in list(ov.get_jhsaa_transfers()):
        ov.clear_jhsaa_transfer(pid)
    jh._transfer_cache.clear()


def _move(m, to, year):
    ov.set_jhsaa_transfer(m["p"].pid, m["a"].name, "girls", m["p"].entry_year,
                          m["seat"], to.name, year)
    jh._transfer_cache.clear()


def _rosters_holding(m, year):
    return [s.name for s in (m["a"], m["b"], m["c"])
            if any(q.pid == m["p"].pid for q in jh.build_roster(s, year, ""))]


def test_a_second_move_does_not_erase_the_first(mover):
    """‼️ THE REPORTED GAP. Recording another move must ADD to the history, so the
    seasons already played keep the school they were played at."""
    _move(mover, mover["b"], 2028)
    _move(mover, mover["c"], 2029)
    moves = jh.transfer_moves(jh.transfer_for(mover["p"].pid))
    assert [(x["to"], x["year"]) for x in moves] == [
        (mover["b"].name, 2028), (mover["c"].name, 2029)]
    assert _rosters_holding(mover, 2028) == [mover["b"].name]
    assert _rosters_holding(mover, 2029) == [mover["c"].name]


def test_a_player_can_move_back_to_the_school_they_left(mover):
    """‼️ AND THE ORIGIN'S OWN SEAT LOOP GENERATES THEM AGAIN. `build_roster` skips a
    player who is elsewhere and pulls in whoever has moved here — so a return would be
    produced twice unless the inbound pull refuses anyone whose origin IS this school.
    A phantom team-mate reads as a roster quirk, never as a bug."""
    _move(mover, mover["b"], 2028)
    _move(mover, mover["a"], 2029)
    assert _rosters_holding(mover, 2028) == [mover["b"].name]
    assert _rosters_holding(mover, 2029) == [mover["a"].name]


@pytest.mark.parametrize("year", [2027, 2028, 2029, 2030])
def test_a_player_is_on_exactly_one_roster_every_season(mover, year):
    """The invariant the whole feature rests on, checked across a career that leaves,
    moves again, and comes home."""
    _move(mover, mover["b"], 2028)
    _move(mover, mover["c"], 2029)
    _move(mover, mover["a"], 2030)
    assert len(_rosters_holding(mover, year)) == 1, year


def test_undoing_one_move_leaves_the_others_standing(mover):
    _move(mover, mover["b"], 2028)
    _move(mover, mover["c"], 2029)
    ov.clear_jhsaa_transfer(mover["p"].pid, 2029)
    jh._transfer_cache.clear()
    moves = jh.transfer_moves(jh.transfer_for(mover["p"].pid))
    assert [x["year"] for x in moves] == [2028]
    assert _rosters_holding(mover, 2029) == [mover["b"].name]


def test_undoing_the_last_move_deletes_the_record(mover):
    """A record with no moves is not a player who transferred nowhere."""
    _move(mover, mover["b"], 2028)
    ov.clear_jhsaa_transfer(mover["p"].pid, 2028)
    jh._transfer_cache.clear()
    assert jh.transfer_for(mover["p"].pid) is None
    assert _rosters_holding(mover, 2029) == [mover["a"].name]


def test_re_recording_the_same_year_edits_that_move(mover):
    """Two destinations for one season is one decision changed, not two moves."""
    _move(mover, mover["b"], 2028)
    _move(mover, mover["c"], 2028)
    moves = jh.transfer_moves(jh.transfer_for(mover["p"].pid))
    assert [(x["to"], x["year"]) for x in moves] == [(mover["c"].name, 2028)]


def test_a_record_written_before_moves_existed_still_reads(mover):
    """Legacy rows carry a single `to`/`year`; read back as a one-move history rather
    than migrated — the section's own idiom."""
    import json, sqlite3
    from app.dbpath import resolve_db_path
    conn = sqlite3.connect(resolve_db_path())
    conn.execute("INSERT OR REPLACE INTO roster_overrides (kind,key,value)"
                 " VALUES ('jhsaa_transfer',?,?)",
                 (mover["p"].pid, json.dumps(
                     {"from": mover["a"].name, "gender": "girls",
                      "entry": mover["p"].entry_year, "seat": mover["seat"],
                      "to": mover["b"].name, "year": 2028})))
    conn.commit(); conn.close()
    jh._transfer_cache.clear()
    assert [(x["to"], x["year"]) for x in
            jh.transfer_moves(jh.transfer_for(mover["p"].pid))] == [(mover["b"].name, 2028)]
    assert _rosters_holding(mover, 2029) == [mover["b"].name]
    # and appending to a legacy record keeps the move it already had
    _move(mover, mover["c"], 2030)
    assert [x["year"] for x in
            jh.transfer_moves(jh.transfer_for(mover["p"].pid))] == [2028, 2030]


def test_the_ledger_is_one_row_per_move(mover):
    """‼️ `from` ON A ROW IS WHERE THEY WERE BEFORE THAT MOVE, not the career origin —
    otherwise every later hop reads as starting from the first school, and a move home
    reads as a move from itself."""
    _move(mover, mover["b"], 2028)
    _move(mover, mover["c"], 2029)
    _move(mover, mover["a"], 2030)
    rows = [r for r in jh.transfer_rows() if r["pid"] == mover["p"].pid]
    assert len(rows) == 3
    by_year = {r["year"]: r for r in rows}
    assert by_year[2028]["from"] == mover["a"].name
    assert by_year[2029]["from"] == mover["b"].name
    assert by_year[2030]["from"] == mover["c"].name
    assert by_year[2030]["to"] == mover["a"].name
    assert {r["steps"] for r in rows} == {3}
