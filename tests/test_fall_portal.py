"""Fall transfer portal — the post-ITA talent reshuffle.

Covers the pure cascade engine (`world.fall_portal_proposals`), the two-stint
career-history bookkeeping, and the proposal persistence table. The full
barrier/commit DB flow (advance_week → run → commit → release) is exercised by
the manual smoke in the PR; here we keep to fast, deterministic units.
"""
import copy
import os
import random
import tempfile

import pytest

# Point the override / proposal store at a throwaway DB before importing anything.
os.environ.setdefault("TENNIS_DB_PATH", tempfile.mktemp(suffix="-fallportal.db"))

from app import world, overrides as ov
from app.ncaa import load_division, build_roster, roster_cap, reset_caches


def _world4(gender="men", n=12):
    """A small slice of every division (D1..D4), full deep-copied rosters."""
    rosters = {}
    for div in ("D1", "D2", "D3", "D4"):
        prog = {p.school: p for p in load_division(div, gender).programs}
        schools = list(prog)[:n]
        rosters[(div, gender)] = {s: [copy.deepcopy(q) for q in build_roster(prog[s])]
                                  for s in schools}
    return rosters


def _div_of(rosters, gender):
    return {s: d for (d, g) in rosters for s in rosters[(d, g)] if g == gender}


def _apply(rosters, moves, gender):
    """Apply pid→dest moves to the roster dict (mirrors what commit + bake do)."""
    div_of = _div_of(rosters, gender)
    by_pid = {p.pid: (d, s, p) for (d, g) in rosters if g == gender
              for s in rosters[(d, g)] for p in rosters[(d, g)][s]}
    for m in moves:
        src_d, src_s, p = by_pid[m["pid"]]
        rosters[(src_d, gender)][src_s].remove(p)
        rosters[(m["dest_div"], gender)][m["dest_school"]].append(p)
    return rosters


@pytest.fixture(autouse=True)
def _clean():
    ov.clear_all(); reset_caches()
    yield
    ov.clear_all(); reset_caches()


# --- the cascade engine ---------------------------------------------------

def test_lower_division_star_rises():
    r = _world4()
    star = next(iter(r[("D4", "men")].values()))[0]
    ps = {star.pid: (56.0, 0.9)}                       # far above D4 level
    moves = world.fall_portal_proposals(r, ps, random.Random(0), "men")
    mine = [m for m in moves if m["pid"] == star.pid]
    assert len(mine) == 1
    rank = {"D1": 0, "D2": 1, "D3": 2, "D4": 3}
    assert rank[mine[0]["dest_div"]] < rank[mine[0]["src_div"]]   # climbed at least one level


def test_proposals_are_deterministic():
    r1, r2 = _world4(), _world4()
    star1 = next(iter(r1[("D4", "men")].values()))[0]
    star2 = next(iter(r2[("D4", "men")].values()))[0]
    a = world.fall_portal_proposals(r1, {star1.pid: (56.0, 0.9)}, random.Random(0), "men")
    b = world.fall_portal_proposals(r2, {star2.pid: (56.0, 0.9)}, random.Random(0), "men")
    key = lambda ms: [(m["pid"], m["src_school"], m["dest_school"]) for m in ms]
    assert key(a) == key(b)


def test_player_not_above_division_level_stays():
    """A merely-ordinary lower-division player (not above their division level) is
    never proposed — the portal corrects mis-allocation, it doesn't churn."""
    r = _world4()
    school, roster = next(iter(r[("D4", "men")].items()))
    weak = roster[0]
    moves = world.fall_portal_proposals(r, {weak.pid: (30.0, 0.9)}, random.Random(0), "men")
    assert all(m["pid"] != weak.pid for m in moves)


def test_cascade_keeps_every_roster_within_cap():
    r = _world4()
    # several reliable risers across the lower divisions to force some cascades
    ps = {}
    for d in ("D2", "D3", "D4"):
        for s, roster in list(r[(d, "men")].items())[:3]:
            ps[roster[0].pid] = (55.0, 0.8)
    moves = world.fall_portal_proposals(r, ps, random.Random(1), "men")
    assert moves                                        # something moved
    _apply(r, moves, "men")
    div_of = _div_of(r, "men")
    for (d, g), schools in r.items():
        for s, roster in schools.items():
            assert len(roster) <= roster_cap(d)         # no program overfilled


def test_displaced_player_moves_down_not_up():
    """When a riser bumps a full program's weakest, that player cascades DOWN the
    ladder (or into the vacated seat), never up."""
    r = _world4()
    ps = {}
    for d in ("D2", "D3", "D4"):
        for s, roster in list(r[(d, "men")].items())[:4]:
            ps[roster[0].pid] = (55.0, 0.8)
    moves = world.fall_portal_proposals(r, ps, random.Random(2), "men")
    rank = {"D1": 0, "D2": 1, "D3": 2, "D4": 3}
    for m in moves:
        if m["cascade_from"]:                           # a displaced (non-riser) move
            assert rank[m["dest_div"]] >= rank[m["src_div"]]


def test_prior_transfer_is_not_a_riser():
    r = _world4()
    school = next(iter(r[("D4", "men")]))
    star = r[("D4", "men")][school][0]
    star.history = [{"year": 0, "school": "Elsewhere"},
                    {"year": 1, "school": school}]      # already moved once
    assert world._career_transfers(star) == 1
    moves = world.fall_portal_proposals(r, {star.pid: (56.0, 0.9)}, random.Random(0), "men")
    assert all(m["pid"] != star.pid for m in moves)


# --- two-stint career history --------------------------------------------

def test_two_stint_season_counts_as_one_transfer():
    """A player who splits a year (ITA at A, regular+post at B) has TWO same-year
    history entries but only ONE school change — so the year-end portal's
    one-move-per-career guard treats them as already moved."""
    p = type("P", (), {})()
    p.history = [
        {"year": 3, "stint": 1, "school": "Beta"},      # out-of-order on purpose
        {"year": 3, "stint": 0, "school": "Alpha"},
        {"year": 2, "stint": 0, "school": "Alpha"},
    ]
    assert world._career_transfers(p) == 1


# --- proposal persistence table ------------------------------------------

def test_proposal_table_roundtrip_and_status():
    rows = [{"pid": "p1", "src_school": "A", "dest_school": "B", "src_div": "D3",
             "dest_div": "D1", "str": 55.0, "ita_w": 4, "ita_l": 1, "ita_line": "S1",
             "cascade_from": None},
            {"pid": "p2", "src_school": "B", "dest_school": "A", "src_div": "D1",
             "dest_div": "D3", "str": 40.0, "ita_w": 0, "ita_l": 3, "ita_line": "S6",
             "cascade_from": "B"}]
    ov.set_proposals(5, "men", rows)
    got = ov.get_proposals(5)
    assert {r["pid"] for r in got} == {"p1", "p2"}
    assert got[0]["str"] >= got[1]["str"]               # ordered strongest first
    assert {r["pid"]: r["ita_line"] for r in got} == {"p1": "S1", "p2": "S6"}
    assert all(r["status"] == "proposed" for r in got)

    ov.set_status(5, "men", "p1", "approved")
    assert [r["pid"] for r in ov.get_proposals(5, status="approved")] == ["p1"]

    ov.set_status(5, "men", "p1", "committed")
    assert ov.committed_movers(5) == {"p1"}

    ov.clear_year(5)
    assert ov.get_proposals(5) == []
