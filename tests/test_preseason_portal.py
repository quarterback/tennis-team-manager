"""Pre-season portal — the week-0 misallocation reshuffle.

Shares the `_FPPlanner` cascade engine with the fall portal but runs before the
season opens, so a committed mover is a plain `set_move` relocation (no NIT stint,
no two-stint history). Here we cover the engine wrapper and the separate proposal
table; the full route/commit flow is exercised by the manual smoke.
"""
import copy
import os
import tempfile

import pytest

os.environ.setdefault("TENNIS_DB_PATH", tempfile.mktemp(suffix="-preseasonportal.db"))

from app import world, overrides as ov
from app.ncaa import load_division, build_roster, roster_cap, reset_caches


def _world4(gender="men", n=12):
    rosters = {}
    for div in ("D1", "D2", "D3", "D4"):
        prog = {p.school: p for p in load_division(div, gender).programs}
        schools = list(prog)[:n]
        rosters[(div, gender)] = {s: [copy.deepcopy(q) for q in build_roster(prog[s])]
                                  for s in schools}
    return rosters


@pytest.fixture(autouse=True)
def _clean():
    ov.clear_all(); reset_caches()
    yield
    ov.clear_all(); reset_caches()


# --- the engine (shared with the fall portal) ----------------------------

def test_preseason_proposals_match_fall_engine():
    """The pre-season wrapper is the same discovery as the fall portal's riders — at the
    same cap. (The pre-season portal defaults to a larger, UI-tunable cap since it is a
    one-time world-generation fix, not the fall portal's curated reshuffle.)"""
    import random
    from app import worldconfig
    worldconfig.set_preseason_portal_cap(world.FALL_PORTAL_MAX_RISERS)
    try:
        r1, r2 = _world4(), _world4()
        pre = world.preseason_portal_proposals(r1, "men")
        fall = world.fall_portal_proposals(r2, {}, random.Random(0), "men")
        key = lambda ms: [(m["pid"], m["src_school"], m["dest_school"]) for m in ms]
        assert key(pre) == key(fall)
    finally:
        worldconfig.set_preseason_portal_cap(worldconfig.DEFAULT_PRESEASON_PORTAL_CAP)


def test_preseason_cascade_keeps_rosters_within_cap():
    r = _world4()
    moves = world.preseason_portal_proposals(r, "men")
    # apply the slate the way commit/build_roster would
    by_pid = {p.pid: (d, s, p) for (d, g) in r if g == "men"
              for s in r[(d, "men")] for p in r[(d, "men")][s]}
    for m in moves:
        src_d, src_s, p = by_pid[m["pid"]]
        r[(src_d, "men")][src_s].remove(p)
        r[(m["dest_div"], "men")][m["dest_school"]].append(p)
    for (d, _g), schools in r.items():
        for roster in schools.values():
            assert len(roster) <= roster_cap(d)


# --- the separate proposal table -----------------------------------------

def test_ps_proposal_table_roundtrip_and_status():
    rows = [{"pid": "p1", "name": "Ace", "src_school": "A", "dest_school": "B",
             "src_div": "D3", "dest_div": "D1", "str": 55.0, "cascade_from": None},
            {"pid": "p2", "name": "Sub", "src_school": "B", "dest_school": "A",
             "src_div": "D1", "dest_div": "D3", "str": 40.0, "cascade_from": "B"}]
    ov.ps_set_proposals(5, "men", rows)
    got = ov.ps_get_proposals(5)
    assert {r["pid"] for r in got} == {"p1", "p2"}
    assert got[0]["str"] >= got[1]["str"]                 # strongest first
    assert {r["pid"]: r["name"] for r in got} == {"p1": "Ace", "p2": "Sub"}
    assert all(r["status"] == "proposed" for r in got)

    ov.ps_set_status(5, "men", "p1", "rejected")
    assert [r["pid"] for r in ov.ps_get_proposals(5, status="rejected")] == ["p1"]

    ov.ps_set_dest(5, "men", "p2", "C", "D2")
    p2 = next(r for r in ov.ps_get_proposals(5) if r["pid"] == "p2")
    assert (p2["dest_school"], p2["dest_div"]) == ("C", "D2")

    ov.ps_clear_year(5)
    assert ov.ps_get_proposals(5) == []


def test_ps_table_independent_of_fall_portal():
    """Pre-season and fall slates for the same year never collide."""
    ov.ps_set_proposals(7, "men", [{"pid": "x", "src_school": "A", "dest_school": "B",
                                    "src_div": "D4", "dest_div": "D2", "str": 50.0,
                                    "cascade_from": None}])
    ov.set_proposals(7, "men", [{"pid": "y", "src_school": "C", "dest_school": "D",
                                 "src_div": "D3", "dest_div": "D1", "str": 52.0,
                                 "cascade_from": None}])
    assert [r["pid"] for r in ov.ps_get_proposals(7)] == ["x"]
    assert [r["pid"] for r in ov.get_proposals(7)] == ["y"]
