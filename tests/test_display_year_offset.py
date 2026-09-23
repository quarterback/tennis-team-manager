"""The display-year offset (owner request 2026-09): a JHSAA lab save integrated
into a full college save is BACKDATED — the final lab season renders as 2026-27
and the decades of high-school history read behind it, while every identity
year (pids, era gates, talent pins, archive keys) is untouched.

Pinned here:
- offset 0 (every ordinary save) is byte-identical to the old behaviour;
- the offset moves both helpers, and `world.reset()` clears it, so a fresh
  league started on the same database never inherits a backdate;
- `attach_college` builds the college rosters at the world's CURRENT year,
  sets the offset to that year, and refuses to run twice.
"""
import app.world as world
from app import worldconfig


def _clear_offset():
    worldconfig.set(world._DISPLAY_OFFSET_KEY, "")


def test_offset_zero_is_the_identity_function():
    _clear_offset()
    assert world.display_offset() == 0
    assert world.display_base_year() == world.BASE_YEAR
    assert world.display_year(2093) == 2093
    # template-filter duty: None and junk pass through, never raise
    assert world.display_year(None) is None
    assert world.display_year("—") == "—"


def test_offset_shifts_display_and_reset_clears_it():
    try:
        world.set_display_offset(66)
        assert world.display_offset() == 66
        assert world.display_base_year() == world.BASE_YEAR - 66
        # the anchor: lab season 2093 renders as the 2027 season, world year 66
        # as the 2026 college year
        assert world.display_year(2093) == 2027
        assert world.display_base_year() + 66 == 2026
    finally:
        _clear_offset()
    assert world.display_base_year() == world.BASE_YEAR


def test_attach_college_builds_at_the_current_year_and_sets_the_offset(monkeypatch):
    """Wiring test — the real build is `get_or_create`'s own year-0 path, already
    covered by every world test; here the universes are stubbed so the test pins
    the attach semantics (rows at the CURRENT year, offset set, one-time only)."""
    world.reset()
    _clear_offset()
    w = world.get_or_create_jhsaa_only(salt="attach-test")
    assert world.is_jhsaa_only()
    # walk the lab world a few years forward the cheap way (no seasons needed —
    # attach only reads the year pointer)
    conn = world._db()
    conn.execute("UPDATE world SET year=5 WHERE id=?", (w["id"],))
    conn.commit()
    conn.close()

    monkeypatch.setattr(world, "UNIVERSES", [("D1", "men")])
    monkeypatch.setattr(
        world, "_build_universe",
        lambda args: (args[2], args[3],
                      {"Testville": [{"pid": "p1", "name": "A Tester"}]}))
    out = world.attach_college()
    assert out["year"] == 5
    assert not world.is_jhsaa_only()          # rows now exist for the current year
    conn = world._db()
    rows = conn.execute("SELECT year, division, gender FROM world_roster"
                        " WHERE world_id=?", (w["id"],)).fetchall()
    conn.close()
    assert [(r["year"], r["division"], r["gender"]) for r in rows] == [(5, "D1", "men")]
    assert world.display_offset() == 5
    assert world.display_base_year() + out["year"] == world.BASE_YEAR
    # the pro rung has nothing to roll on the first advance of a merged save
    assert worldconfig.get("pros_rolled_year") == "5"
    # one-time step: a second attach must refuse rather than rebuild mid-season
    import pytest
    with pytest.raises(RuntimeError):
        world.attach_college()
    world.reset()
    assert world.display_offset() == 0        # reset clears the backdate
