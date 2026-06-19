"""The Analytics Bureau must read the SAME live rosters every other surface does.

Regression: `scout_intel.scan` read `build_roster` without first priming the world,
so once a season rolled over (players develop, graduate, transfer) the bureau kept
listing the deterministic *base* roster — stale pids for players who no longer sit
where the link claims. Every "player" link off the Underplaced Talent board then
404'd, because the player route resolves the pid against the LIVE season roster.

The guard plays one universe through a full year (so the live roster diverges from
the base one), then — from a cold cache, the worst case a fresh web worker hits —
asserts every pid the bureau surfaces resolves to a real player.
"""
import pytest

import app.world as world
import app.worldconfig as wc
import app.seasonmode as sm
import app.scout_intel as si
from app.ncaa import reset_caches
from app.web.server import create_app


@pytest.fixture
def rolled_over_women_world():
    create_app()                               # bootstrap schemas
    if world.exists():
        world.reset()
    # One active universe keeps the rollover cheap; the scan still sweeps all
    # divisions for the gender, so the bug surfaces on the active one.
    wc.set_active(["D1"], ["women"])
    try:
        world.get_or_create()
        guard = 0
        while guard < 120:
            ev = world.advance_week()
            guard += 1
            if ev.get("event") == "finalize":     # rolled into the next year
                break
        assert world.load_world()["year"] >= 1, "world did not roll over"
        yield
    finally:
        wc.set_active(["D1", "D2", "D3"], ["men", "women"])   # restore default
        if world.exists():
            world.reset()


def test_bureau_player_links_resolve_after_rollover(rolled_over_women_world):
    world.active_salt()                          # every request publishes the salt
    sid = sm.get_or_create("D1", "women", seed=world.current_year_seed())

    # Recreate the production cache state that broke the links: an earlier surface
    # (dashboard/teams) primed the world, so the player route's pid index already
    # holds the LIVE roster — then a week-advance cleared the roster cache. A web
    # worker now hits the bureau with `_roster_cache` empty but a live pid index
    # still resolving clicks. If `scan` doesn't re-prime, it reads the stale base
    # roster and every link it emits points at a player the route can't find.
    world.prime()
    live_pids = set(sm._pid_index("D1", "women"))   # built + cached against live rosters
    reset_caches()                                  # week-advance clears the roster cache
    world._primed.clear()
    si._scan_cache.clear()

    players = si.scan("women")["players"]
    d1 = [r for r in players if r.division == "D1"]
    assert d1, "expected D1 women on the talent scan"

    # Every pid the bureau links to must resolve through the live player route.
    unresolved = [r.pid for r in d1 if sm.player_info(sid, r.pid) is None]
    assert not unresolved, (
        f"{len(unresolved)}/{len(d1)} bureau player links 404 — the scan is reading "
        f"stale (base) rosters instead of the live season")
    # And the bureau must agree with the live roster it links into.
    assert {r.pid for r in d1} <= live_pids
