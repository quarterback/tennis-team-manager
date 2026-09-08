"""A JHSAA-only save opened through the ORDINARY college launch must fail LOUDLY.

‼️ THE COLD-START LOADER CAN WAIT FOR SOMETHING THAT NEVER HAPPENS. A JHSAA-only
world (`get_or_create_jhsaa_only`, `skip_college=True`) writes no `world_roster`
rows at all, so `is_primed()`'s `bool(_roster_cache)` term stays False even after
a fully successful `prime()`. `/api/ready` answered off `is_primed()` alone, so it
returned `{"ready": false}` for as long as the process lived: the loader polled
every 1.5s forever, `_prime_world` served that loader from `before_request` on
EVERY route, and no page — not the JHSAA hub, not a program page — ever rendered.

A spinner is indistinguishable from a slow warm, which is what made this read as
"the sim is hanging" rather than "you opened the wrong database", and why it cost
an owner an evening on top of a lost season.

Both surfaces already had an escape hatch, but both keyed it on the
`JHSAA_LAB_MODE` ENVIRONMENT FLAG when the real condition is a property of the
WORLD. Open the very same database without the flag and the guard evaporated.
These tests pin the world-shaped condition, in both directions.
"""
import os
import sqlite3

import pytest


@pytest.fixture
def save(monkeypatch):
    """A clean world in the suite's own database.

    ‼️ Do NOT try to move the save with `TENNIS_DB_PATH` here: `world.WORLD_DB`
    resolves at IMPORT time, so a monkeypatched path leaves every write going to
    the suite's original file while the test believes it is isolated — which is
    exactly how one test's stub roster row leaked forward and made the next test
    see a college save. Wipe the world instead, before and after.
    """
    from app import world as wd
    from app.dbpath import resolve_db_path

    monkeypatch.setenv("PTC_NO_BOOT_WARM", "1")
    monkeypatch.delenv("JHSAA_LAB_MODE", raising=False)

    def _clear():
        wd.reset()
        wd.reset_caches()
        wd._primed.clear()
        wd._base_cache.clear()
        wd._dev_cache.clear()

    _clear()
    yield resolve_db_path()
    _clear()


def _client():
    from app.web.server import create_app
    return create_app().test_client()


def _kind(response) -> str:
    body = response.get_data(as_text=True)
    if "wrong database" in body:
        return "diagnostic"
    if "Warming up the league" in body:
        return "loader"
    return "content"


def test_a_jhsaa_only_world_is_recognised_by_its_shape_not_a_flag(save):
    from app import world as wd

    wd.get_or_create_jhsaa_only()
    assert wd.is_jhsaa_only() is True
    # The trap this whole module exists for: a SUCCESSFUL prime leaves the
    # college cache empty, so "is it warm yet?" is permanently False.
    wd.prime()
    assert wd.is_primed() is False


def test_a_world_with_college_rosters_is_not_jhsaa_only(save):
    """The probe must not mistake an ordinary college save for a lab world —
    that would serve the diagnostic to a player whose league is merely cold."""
    from app import world as wd

    w = wd.get_or_create_jhsaa_only()
    conn = wd._db()
    conn.execute("INSERT INTO world_roster (world_id, year, division, gender,"
                 " school, data) VALUES (?,?,?,?,?,?)",
                 (w["id"], w["year"], "D1", "men", "Anywhere", "[]"))
    conn.commit()
    conn.close()
    assert wd.is_jhsaa_only() is False


def test_ready_never_polls_forever_on_a_jhsaa_only_save(save):
    """The bug, at its source: this answered False for the life of the process."""
    from app import world as wd

    wd.get_or_create_jhsaa_only()
    assert _client().get("/api/ready").get_json() == {"ready": True}


def test_every_route_explains_the_wrong_launch_instead_of_spinning(save):
    from app import world as wd

    wd.get_or_create_jhsaa_only()
    client = _client()
    for url in ("/jhsaa", "/dashboard", "/"):
        r = client.get(url)
        assert _kind(r) == "diagnostic", f"{url} served {_kind(r)}"
        assert r.status_code == 503, url
        body = r.get_data(as_text=True)
        # It must name the launcher and the actual file, or it is just a
        # prettier dead end than the spinner was.
        assert "scripts/jhsaa_lab_server.sh" in body
        assert save in body


def test_lab_mode_still_serves_the_very_same_world(save, monkeypatch):
    """The flag is no longer the CONDITION, but it must still be honoured: the
    lab launcher opens exactly this shape of world and has to render it."""
    from app import world as wd

    wd.get_or_create_jhsaa_only()
    monkeypatch.setenv("JHSAA_LAB_MODE", "1")
    # The suite's DB is not the canonical lab file, and the canonical-database
    # invariant refuses a non-canonical path in lab mode — which is the point of
    # that guard. This is the developer/test path it deliberately leaves open.
    monkeypatch.setenv("JHSAA_LAB_DEV_OVERRIDE", "1")
    client = _client()
    assert client.get("/api/ready").get_json() == {"ready": True}
    r = client.get("/jhsaa")
    assert r.status_code == 200 and _kind(r) == "content"


def test_health_stays_instant_and_never_touches_the_world(save):
    """`_prime_world` exempts health; the new branch must not have changed that
    (a health check that pays for a DB probe is how the 503 recycle loop began)."""
    from app import world as wd

    wd.get_or_create_jhsaa_only()
    r = _client().get("/api/health")
    assert r.status_code == 200 and r.get_json() == {"status": "ok"}


def test_the_boot_line_names_the_season_the_world_actually_plays(save, caplog):
    """‼️ THE ONE LINE THIS REPO SAYS TO READ FIRST WHEN A SAVE LOOKS WRONG, so
    it is the last place an off-by-one belongs. It printed `2026 + year` for
    every world, but a JHSAA season is `BASE_YEAR + year + 1` (the season's
    seniors ARE that recruiting class) — so a lab save at world year 49
    announced "season 2075" while its archive, its pages and its research
    export all said 2076. The diagnostic for "am I in the right universe?" was
    itself the evidence of a discrepancy that does not exist.
    """
    import logging

    from app import world as wd

    wd.get_or_create_jhsaa_only()
    w = wd.load_world(wd.DEFAULT_SEED)
    conn = wd._db()
    try:
        conn.execute("UPDATE world SET year=49 WHERE id=?", (w["id"],))
        conn.commit()
    finally:
        conn.close()
    assert wd.is_jhsaa_only() is True

    with caplog.at_level(logging.WARNING, logger="baseline.server"):
        _client()
    line = next(r.getMessage() for r in caplog.records
                if r.getMessage().startswith("save"))
    w = wd.load_world(wd.DEFAULT_SEED)
    assert f"JHSAA season {wd.jhsaa_season_year(w)}" in line, line
    assert "season 2075" not in line, line          # the college formula
    assert "world year 49" in line, line            # the DB key still shown


def test_the_boot_line_keeps_the_college_year_on_a_college_save(save, caplog):
    """The fix is a fork, not a replacement: an ordinary college world still
    announces `2026 + year`. Its JHSAA rung runs a year ahead of that by
    design, and naming THAT year here would move the error rather than fix it.
    """
    import logging

    from app import world as wd

    w = wd.get_or_create(wd.DEFAULT_SEED)
    conn = wd._db()
    try:
        conn.execute("UPDATE world SET year=49 WHERE id=?", (w["id"],))
        conn.execute(
            "INSERT INTO world_roster (world_id, year, division, gender, school, data)"
            " VALUES (?,?,?,?,?,?)", (w["id"], 49, "D1", "men", "Stub", "[]"))
        conn.commit()
    finally:
        conn.close()
    assert wd.is_jhsaa_only() is False

    with caplog.at_level(logging.WARNING, logger="baseline.server"):
        _client()
    line = next(r.getMessage() for r in caplog.records
                if r.getMessage().startswith("save"))
    assert "season 2075" in line and "JHSAA" not in line, line
