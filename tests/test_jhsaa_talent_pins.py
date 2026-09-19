"""THE TALENT PIN (owner rule 2026-09): a player already archived on a roster
keeps the ceiling they were generated with, whatever the program tier says
later. Tier edits reach NEW ENTRANTS ONLY.

Why: a JHSAA player is rebuilt from a recipe on every build, and the recipe's
inputs (tier, tier table, seed file, archetype) can move for an enrolled cohort
— a seed-file revert re-tiered ~94% of programs between 2088 and 2089, same pid,
same name, a different ceiling, seniors included. `world_jhsaa_talent` records
the ceiling at archive time and `_gen_seat` reads it before the tier.
"""
from types import SimpleNamespace

import pytest

from app import jhsaa
from app import overrides as ov
from app import world as wd
from app import worldconfig as wc


@pytest.fixture(autouse=True)
def _world():
    """A world row (so pins scope to something), the tier era at 0 so every
    cohort draws from its tier, a clean override layer, an empty pin table."""
    ov.init_schema()
    conn = wd._db()
    conn.execute("DELETE FROM world_jhsaa_talent")
    conn.execute("DELETE FROM world_jhsaa")
    if conn.execute("SELECT 1 FROM world LIMIT 1").fetchone() is None:
        conn.execute("INSERT INTO world (seed, year, week, salt) VALUES (?,0,0,?)",
                     (wd.DEFAULT_SEED, "pin-salt"))
    conn.commit()
    wid = conn.execute("SELECT id FROM world ORDER BY id ASC LIMIT 1").fetchone()[0]
    prev = wc.get("jhsaa_band_era")
    wc.set("jhsaa_band_era", "0")
    for n in list(ov.get_jhsaa_bands()):
        ov.clear_jhsaa_band(n)
    jhsaa.reset_schools()
    yield wid
    for n in list(ov.get_jhsaa_bands()):
        ov.clear_jhsaa_band(n)
    wc.set("jhsaa_band_era", prev if prev is not None else "")
    conn = wd._db()
    conn.execute("DELETE FROM world_jhsaa_talent")
    conn.execute("DELETE FROM world_jhsaa")
    conn.commit()
    jhsaa.reset_schools()


def _school():
    live = set(jhsaa.upstarts(2030, "")) | set(jhsaa._arch_seed())
    return next(s for s in jhsaa.load_schools("boys") if s.name not in live)


def _set(school, tier):
    ov.set_jhsaa_band(school.ident, tier)
    jhsaa.reset_schools()


def _ceilings(roster):
    return {p.pid: round(p.ceiling_overall(), 6) for p in roster}


def test_a_tier_edit_never_moves_a_player_already_archived(_world):
    wid = _world
    s = _school()
    _set(s, "average")
    r30 = jhsaa.build_roster(s, 2030)
    assert all(p.jhsaa.get("talent") is not None and p.jhsaa.get("tier") == "average"
               for p in r30), "every generated seat carries what the pin records"
    # The INTENDED 2031: the same program, the same tier, one year on. (A
    # ceiling can legitimately rise with grade — the POT-never-below-OVR lift —
    # so the invariant is same-year equality, never cross-year.)
    intended = _ceilings(jhsaa.build_roster(s, 2031))
    returning = {p.pid for p in r30} & set(intended)
    assert returning, "grades 9-11 of 2030 are 10-12 of 2031"

    # Control: with NO pin, moving the tier rewrites the enrolled cohorts in
    # place — the fault this table exists to make impossible.
    _set(s, "very_strong")
    moved = _ceilings(jhsaa.build_roster(s, 2031))
    assert any(moved[pid] != intended[pid] for pid in returning), \
        "the control must bite: unpinned, the tier edit re-tiers returning players"

    # Pin the 2030 roster (what `run_jhsaa` does at archive time), then rebuild
    # 2031 under the new tier.
    conn = wd._db()
    n = jhsaa.record_talents(conn, wid, 0, "boys", [r30])
    conn.commit()
    assert n == len(r30)
    jhsaa.reset_schools()
    r31 = jhsaa.build_roster(s, 2031)
    after = _ceilings(r31)
    for pid in returning:
        assert after[pid] == intended[pid], "a returning player keeps the ceiling they played at"
    by = {p.pid: p for p in r31}
    assert all(by[pid].jhsaa["tier"] == "pinned" for pid in returning)
    # ...and the NEW entrants draw from the tier of the day: identical to the
    # unpinned build under "very_strong" (pinning changes nothing for them).
    fresh = [pid for pid in after if pid not in returning]
    assert fresh, "2031 has a freshman class"
    for pid in fresh:
        assert after[pid] == moved[pid]
        assert by[pid].jhsaa["tier"] == "very_strong"
    # The pin is FIRST-VALUE-WINS: recording 2031 under the new tier keeps the
    # 2030 values for the returning players, and a third tier moves nobody
    # already recorded.
    jhsaa.record_talents(conn, wid, 1, "boys", [r31])
    conn.commit()
    jhsaa.reset_schools()
    _set(s, "abysmal")
    third = _ceilings(jhsaa.build_roster(s, 2031))
    assert third == after


def test_an_unpinned_save_builds_exactly_as_before(_world):
    """No rows for a program → the recipe alone, to the bit (every existing
    byte-identity test in the section keeps holding)."""
    s = _school()
    _set(s, "solid")
    a = jhsaa.build_roster(s, 2030)
    assert jhsaa.pinned_talents("boys", s.ident) == {}
    b = jhsaa.build_roster(s, 2030)
    assert _ceilings(a) == _ceilings(b)
    assert all(p.jhsaa.get("tier") == "solid" for p in a)


def test_the_backfill_pins_the_season_already_played_once(_world):
    """A save from before the pin: the newest archived season's rosters are
    pinned as the recipe builds them today, once, and only when the archive
    row for that index exists."""
    wid = _world
    s = _school()
    _set(s, "good")
    conn = wd._db()
    # No archive at index 0 → nothing to backfill.
    assert jhsaa.backfill_talent_pins(conn, wid, 0, 2030, "") == 0
    conn.execute("INSERT INTO world_jhsaa (world_id, year, gender, data) VALUES (?,?,?,?)",
                 (wid, 0, "boys", "{}"))
    conn.commit()
    n = jhsaa.backfill_talent_pins(conn, wid, 0, 2030, "")
    conn.commit()
    assert n > 0
    pins = jhsaa.pinned_talents("boys", s.ident)
    r30 = jhsaa.build_roster(s, 2030)
    assert set(pins) >= {p.pid for p in r30}
    # Idempotent: a second call finds rows and does nothing.
    assert jhsaa.backfill_talent_pins(conn, wid, 0, 2030, "") == 0
    # And the pins hold against a tier edit afterwards (same-year comparison).
    intended = _ceilings(jhsaa.build_roster(s, 2031))
    _set(s, "abysmal")
    after = _ceilings(jhsaa.build_roster(s, 2031))
    for pid in pins:
        if pid in after:
            assert after[pid] == intended[pid]
