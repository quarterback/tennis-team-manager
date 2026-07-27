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


# --- one move per player (the commit's UNIQUE key) ------------------------

def _resolve_riders(rosters, gender, riders, *, pretouch=True):
    """Drive the planner as the resolvers do: rider intents, best first, each placed
    at its stored destination. `pretouch=False` reproduces the pre-fix sequence, which
    protected only the rider currently being placed."""
    riders = sorted(riders, key=lambda r: (-r["str"], r["pid"]))
    plan = world._FPPlanner(rosters, {}, gender)
    if pretouch:
        plan.touched.update(r["pid"] for r in riders)
    for r in riders:
        entry = plan.by_pid.get(r["pid"])
        if not entry:
            continue
        src, p = entry
        if not pretouch:
            plan.touched.add(p.pid)
        plan.place(p, src, dest=r["dest_school"], gated=False)
    return plan


def _two_riders_into_one_full_team(r):
    """Rider A aimed at a FULL D2 program whose weakest man is himself rider B."""
    d2 = r[("D2", "men")]
    dest = next(iter(d2))
    while len(d2[dest]) < roster_cap("D2"):             # make sure it's genuinely FULL
        d2[dest].append(copy.deepcopy(d2[dest][-1]))
        d2[dest][-1].pid += "-x"
    d2[dest] = d2[dest][:roster_cap("D2")]
    weakest = min(d2[dest], key=lambda q: q.str_value())
    src_a = next(iter(r[("D3", "men")]))
    rider_a = r[("D3", "men")][src_a][0]
    return dest, weakest, [
        {"pid": rider_a.pid, "str": 58.0, "dest_school": dest},          # into the full team
        {"pid": weakest.pid, "str": weakest.str_value(),                 # ...where B lives
         "dest_school": next(iter(r[("D1", "men")]))},
    ]


def test_no_player_gets_two_moves_in_one_slate():
    """Regression for a 500 at /fall-portal commit: `UNIQUE constraint failed:
    fall_portal.year, fall_portal.gender, fall_portal.pid`.

    Rider A is sent into a FULL program where rider B is the weakest man. A displaced
    B as its cascade, then B's own stored intent placed B a SECOND time — two rows for
    one pid, which the (year, gender, pid) unique key rejects at commit."""
    r = _world4()
    _dest, _b, riders = _two_riders_into_one_full_team(r)
    for pretouch in (False, True):                      # old sequence and new
        plan = _resolve_riders(_world4(), "men", riders, pretouch=pretouch)
        pids = [m["pid"] for m in plan.moves]
        assert len(pids) == len(set(pids)), f"duplicate move rows (pretouch={pretouch}): {pids}"


def test_a_rider_keeps_their_own_destination():
    """The root fix: a rider is protected from every OTHER rider's cascade, so they
    land where they were sent instead of being dragged down the ladder first."""
    r = _world4()
    _dest, b, riders = _two_riders_into_one_full_team(r)
    plan = _resolve_riders(r, "men", riders)
    b_moves = [m for m in plan.moves if m["pid"] == b.pid]
    assert len(b_moves) == 1
    assert b_moves[0]["dest_school"] == riders[1]["dest_school"]
    assert b_moves[0]["cascade_from"] is None           # placed as a rider, not displaced


def test_planner_refuses_to_move_the_same_player_twice():
    """The structural guard behind the fix: whatever a caller asks for, one player
    gets at most one move per slate."""
    r = _world4()
    plan = world._FPPlanner(r, {}, "men")
    src = next(s for s in plan.schools if plan.div_of[s] == "D3")
    p = plan.pool[src][0]
    d1 = [s for s in plan.schools if plan.div_of[s] == "D1"]
    assert plan.place(p, src, dest=d1[0]) == d1[0]
    assert plan.place(p, d1[0], dest=d1[1]) is None      # second move refused
    assert sum(1 for m in plan.moves if m["pid"] == p.pid) == 1


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
