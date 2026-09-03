"""The transfer ledger at scale (owner report 2026-09).

A 40-season save holds 11,000+ recorded moves, and the transfers page took
"forever": it regenerated every mover ever recorded to print a name, rendered
them all, and kicked off two full-gender roster builds underneath itself — while
every roster build walked the whole ledger asking each of 11,000 records whether
it lands here this year. A move stops mattering when the player graduates, so:

  * `enrolled_transfers` is the slice of the ledger a season can see;
  * `jhsaa_transfer_version()` is a one-row stamp kept by schema triggers;
  * the ledger's names come off the name draw alone (`_seat_name`);
  * the batch pid index is patched across edits, never rebuilt whole.
"""
import json
import sqlite3

import pytest

from app import jhsaa as jh
from app import overrides as ov
from app.dbpath import resolve_db_path


def _wipe():
    for pid in list(ov.get_jhsaa_transfers()):
        ov.clear_jhsaa_transfer(pid)
    jh._transfer_cache.clear()
    jh._pid_idx_cache.clear()


@pytest.fixture
def mover():
    schools = jh.load_schools("girls")
    a, b, c = schools[0], schools[1], schools[2]
    p = next(q for q in jh.build_roster(a, 2027, "") if q.grade == 9)
    seat = jh.resolve_seat(a, p.entry_year, p.pid)
    assert seat is not None
    _wipe()
    yield {"a": a, "b": b, "c": c, "p": p, "seat": seat}
    _wipe()


def _move(m, to, year):
    ov.set_jhsaa_transfer(m["p"].pid, m["a"].name, "girls", m["p"].entry_year,
                          m["seat"], to.name, year)


def test_version_is_a_stamp_that_every_write_path_bumps(mover):
    """Set, clear AND a direct INSERT (a script, a repair) all move the version —
    the triggers live in the schema, not in the helpers."""
    v0 = ov.jhsaa_transfer_version()
    assert ov.jhsaa_transfer_version() == v0            # stable between writes
    _move(mover, mover["b"], 2028)
    v1 = ov.jhsaa_transfer_version()
    assert v1 != v0
    conn = sqlite3.connect(resolve_db_path())
    conn.execute("INSERT OR REPLACE INTO roster_overrides (kind,key,value)"
                 " VALUES ('jhsaa_transfer',?,?)",
                 ("jh_direct_row", json.dumps({"from": mover["a"].name, "gender": "girls",
                                              "entry": 2027, "seat": 0,
                                              "to": mover["b"].name, "year": 2028})))
    conn.commit(); conn.close()
    v2 = ov.jhsaa_transfer_version()
    assert v2 != v1
    ov.clear_jhsaa_transfer("jh_direct_row")
    assert ov.jhsaa_transfer_version() != v2
    # and the stamp row itself never reads back as a transfer
    assert "stamp" not in ov.get_jhsaa_transfers()


def test_enrolled_slice_drops_graduated_movers(mover):
    """A 2027 freshman is enrolled 2027-2030 and nowhere after."""
    _move(mover, mover["b"], 2028)
    pid = mover["p"].pid
    for year in (2027, 2028, 2030):
        active, _inbound = jh.enrolled_transfers(year)
        assert pid in active, year
    for year in (2026, 2031, 2040):
        active, inbound = jh.enrolled_transfers(year)
        assert pid not in active, year
        assert not any(pid == q for lst in inbound.values() for q, _ in lst)
    # inbound is keyed on where they ARE that season, only once away from home
    _active, inbound = jh.enrolled_transfers(2027)
    assert ("girls", mover["b"].name) not in inbound
    _active, inbound = jh.enrolled_transfers(2029)
    assert [q for q, _ in inbound[("girls", mover["b"].name)]] == [pid]


def test_roster_membership_is_unchanged_by_the_slice(mover):
    """The slice must answer exactly what the full walk answered: away from the
    origin from the effective year, on the destination, back home on a return."""
    _move(mover, mover["b"], 2028)
    _move(mover, mover["a"], 2030)
    pid = mover["p"].pid

    def holding(year):
        return [s.name for s in (mover["a"], mover["b"])
                if any(q.pid == pid for q in jh.build_roster(s, year, ""))]
    assert holding(2027) == [mover["a"].name]
    assert holding(2028) == [mover["b"].name]
    assert holding(2029) == [mover["b"].name]
    assert holding(2030) == [mover["a"].name]
    assert holding(2031) == []                                # graduated


def test_seat_name_is_the_roster_name(mover):
    """The ledger's cheap name draw and the roster's full generation share one
    draw, so they can never disagree about who a seat is."""
    a = mover["a"]
    for p in jh.build_roster(a, 2027, "")[:6]:
        seat = jh.resolve_seat(a, p.entry_year, p.pid)
        assert jh._seat_name(a, p.entry_year, seat, "") == p.name


def test_ledger_names_resolve_only_for_the_rows_asked(mover):
    _move(mover, mover["b"], 2028)
    _move(mover, mover["c"], 2029)
    ledger = jh.transfer_ledger()
    assert [r["name"] for r in ledger] == ["", ""]
    assert [(r["from"], r["to"], r["step"]) for r in sorted(ledger, key=lambda r: r["year"])] == [
        (mover["a"].name, mover["b"].name, 1), (mover["b"].name, mover["c"].name, 2)]
    rows = jh.resolve_transfer_names([r for r in ledger if r["year"] == 2029], "")
    assert rows[0]["name"] == mover["p"].name
    # the whole-ledger convenience still reads the same
    assert {r["name"] for r in jh.transfer_rows("")} == {mover["p"].name}


def test_pid_index_is_patched_across_edits_not_rebuilt(mover, monkeypatch):
    """After a move, only the schools the record names are rebuilt — and the
    patched index equals a cold build."""
    pid = mover["p"].pid
    cold = jh.roster_pid_index("girls", 2028, "")
    assert cold[pid][0] == mover["a"].name
    built = []
    real = jh.build_roster
    monkeypatch.setattr(jh, "build_roster",
                        lambda s, y, salt="": (built.append(s.name), real(s, y, salt))[1])
    _move(mover, mover["b"], 2028)
    patched = jh.roster_pid_index("girls", 2028, "")
    assert set(built) == {mover["a"].name, mover["b"].name}
    assert patched[pid][0] == mover["b"].name
    jh._pid_idx_cache.clear()
    assert jh.roster_pid_index("girls", 2028, "") == patched
