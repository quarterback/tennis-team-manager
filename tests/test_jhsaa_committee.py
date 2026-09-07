"""The at-large committee and the 48-team field (owner spec 2026-09) —
selection procedure, the hard seeding floor, ballot independence, automatic
bids, and the Parastate shape."""
import random

import pytest

from app import jhsaa as jh
from app import jhsaa_committee as jc
from app.jhsaa_ratings import SYSTEMS


def _ratings(n=60, twist=None):
    """A synthetic ratings layer: teams T01 (best) .. Tnn, every system
    agreeing, except where `twist` (a {system: {team: rank}} overlay) says
    otherwise."""
    teams = {}
    for i in range(1, n + 1):
        name = f"T{i:02d}"
        ranks = {s: i for s in SYSTEMS}
        for s, over in (twist or {}).items():
            if name in over:
                ranks[s] = over[name]
        vals = list(ranks.values())
        teams[name] = {"record": "10-5", "district": "Test League",
                       "ranks": ranks, "values": {},
                       "mean": sum(vals) / len(vals),
                       "median": sorted(vals)[len(vals) // 2],
                       "sigma": 0.0}
    return {"teams": teams, "disconnected": False, "systems": list(SYSTEMS)}


ROAD = {f"T{i:02d}" for i in range(1, 33)}          # T01-T32 qualified


def test_field_assembly_32_plus_16_and_the_selection_is_the_next_best():
    sel = jc.select(_ratings(), ROAD, [])
    assert len(sel["selected"]) == jc.AT_LARGE
    # every system agrees, so the sixteen best non-road teams are all locks
    assert set(sel["selected"]) == {f"T{i:02d}" for i in range(33, 49)}
    assert set(sel["locks"]) == set(sel["selected"])
    assert all(sel["status"][f"T{i:02d}"] == "Qualified" for i in range(1, 33))


def test_the_pool_is_every_non_road_team_including_ones_ranked_above_road():
    """Owner correction: the committee chooses from ANYONE outside the field —
    a team the systems rank above road qualifiers is a normal candidate."""
    # T50 is secretly rank 1 on every system; T01 pushed to 50.
    twist = {s: {"T50": 1} for s in SYSTEMS}        # T50 missed the road
    sel = jc.select(_ratings(twist=twist), ROAD, [])
    assert "T50" in sel["selected"]
    assert sel["selected"][0] == "T50"              # best Borda seeds 33 first


def test_an_at_large_is_never_seeded_above_33():
    """The hard rule: however high its ranks and Borda, an at-large arrives
    AFTER the 32 road seeds — the caller's `road_seeds + at_large` construction
    plus `run_state_48`'s field order."""
    twist = {s: {"T40": 1} for s in SYSTEMS}        # the best team missed the road
    sel = jc.select(_ratings(twist=twist), ROAD, [])
    assert sel["selected"][0] == "T40"
    field = [f"T{i:02d}" for i in range(1, 33)] + sel["selected"]
    assert field.index("T40") >= 32                 # seed 33 at best, never higher


def test_a_district_champion_who_missed_the_road_is_automatic():
    sel = jc.select(_ratings(), ROAD, ["T59"])      # ranked 59th — in anyway
    assert "T59" in sel["auto"] and "T59" in sel["selected"]
    assert len(sel["selected"]) == jc.AT_LARGE
    # the automatic consumed a seat: only 15 rank-selected teams remain
    assert set(sel["selected"]) - {"T59"} == {f"T{i:02d}" for i in range(33, 48)}


def test_ballot_independence():
    """Changing one member's weights changes only that member's ballot."""
    r = _ratings(twist={"elo": {f"T{i:02d}": 61 - i for i in range(1, 61)}})
    before = jc.ballots(r)
    saved = jc.MEMBERS["The Eye Test"]
    try:
        jc.MEMBERS["The Eye Test"] = {"elo": 1.0}
        after = jc.ballots(r)
    finally:
        jc.MEMBERS["The Eye Test"] = saved
    assert after["The Eye Test"] != before["The Eye Test"]
    for m in jc.MEMBERS:
        if m != "The Eye Test":
            assert after[m] == before[m], m


def test_the_bubble_borda_reads_the_full_bubble_ordering():
    """No. 17 on one ballot and No. 50 must stay distinguishable: Borda is
    scored over the whole bubble population's ordering, not membership in a
    top-N."""
    # Split the systems so the ranges disagree: the Quant loves T55, everyone
    # else has it far out; T33.. are near-unanimous.
    twist = {"massey_game": {"T55": 1}, "set_share": {"T55": 1},
             "massey_dual": {"T55": 1}, "srs": {"T55": 1}}
    sel = jc.select(_ratings(twist=twist), ROAD, [])
    assert "T55" in sel["borda"]                    # it reached a range
    assert sel["borda"]["T55"] > 0
    # and a team on nobody's range is Out, not silently Borda'd in
    assert sel["status"]["T60"] == "Out"


def test_statuses_partition_the_group():
    twist = {"elo": {"T45": 1, "T33": 55}}          # some disagreement
    sel = jc.select(_ratings(twist=twist), ROAD, [])
    seen = set(sel["status"].values())
    assert seen <= {"Qualified", "Lock", "In", "Bubble", "Out"}
    assert "Qualified" in seen and ("Lock" in seen or "In" in seen)


# --- the 48-team event shape --------------------------------------------------

class _S:
    def __init__(self, name):
        self.name, self.group, self.district = name, "7A", "Test League"


class _T:
    def __init__(self, name):
        self.school = _S(name)
        self.schedule = []


class _Res:
    def __init__(self, winner):
        self.winner, self.home_points, self.away_points = winner, 5, 4


def test_parastate_pairings_and_that_winners_retain_their_seed(monkeypatch):
    seeds = [_T(f"S{i:02d}") for i in range(1, 49)]
    played = []

    def fake_dual(a, b, *, seed, phase):
        assert phase == "state"
        played.append((a.school.name, b.school.name))
        return _Res(0)                              # higher seed always wins

    monkeypatch.setattr(jh, "play_dual", fake_dual)
    arc = jh.run_state_48(seeds, seed=7)
    # The Parastate: exactly 17v48, 18v47, ... 32v33, higher seed hosting.
    para = arc["rounds"][0]
    assert arc["round_names"][0] == jh.PARASTATE_NAME
    assert [(g["home"], g["away"]) for g in para] == \
        [(f"S{17 + k:02d}", f"S{48 - k:02d}") for k in range(16)]
    # 48 -> 32 -> 16 -> 8 -> 4 -> 2: byes 1-16 play their first dual in the R32
    assert [len(rd) for rd in arc["rounds"]] == [16, 16, 8, 4, 2, 1]
    assert len(arc["field"]) == 48
    # winners retain their original seed: the R32 field is exactly seeds 1-32
    r32 = {g["home"] for g in arc["rounds"][1]} | {g["away"]
                                                   for g in arc["rounds"][1]}
    assert r32 == {f"S{i:02d}" for i in range(1, 33)}
    assert arc["champion"] == "S01"


def test_the_48_field_is_road_then_at_large(monkeypatch):
    """Byes 1-16 and seeds 17-32 are road qualifiers; 33-48 are the at-larges —
    the structural floor the committee cannot move."""
    road = [_T(f"R{i:02d}") for i in range(1, 33)]
    al = [_T(f"A{i:02d}") for i in range(1, 17)]
    monkeypatch.setattr(jh, "play_dual",
                        lambda a, b, *, seed, phase: _Res(0))
    arc = jh.run_state_48(road + al, seed=1)
    assert arc["field"][:32] == [t.school.name for t in road]
    assert arc["field"][32:] == [t.school.name for t in al]


def test_the_40_team_parastate_is_eight_bids_and_byes_1_to_24(monkeypatch):
    """7A's shape (owner rule 2026-09): 32 road + 8 at-large. Seeds 1-24 bye to
    the Round of 32; the Parastate is 25v40 … 32v33, winners keep their seed,
    then 32 → 16 → 8 → 4 → 2 — the same mechanism as the 48 at a smaller bid
    count, which is the whole point of keeping Parastate rather than dropping
    it with the field size."""
    seeds = [_T(f"S{i:02d}") for i in range(1, 41)]
    monkeypatch.setattr(jh, "play_dual", lambda a, b, *, seed, phase: _Res(0))
    bids = jh.AT_LARGE_BIDS["7A"]
    assert bids == 8 and jh.state_field_size("7A") == 32
    arc = jh.run_state_parastate(seeds, byes=jh.state_field_size("7A") - bids, seed=3)
    para = arc["rounds"][0]
    assert arc["round_names"][0] == jh.PARASTATE_NAME
    assert [(g["home"], g["away"]) for g in para] == \
        [(f"S{25 + k:02d}", f"S{40 - k:02d}") for k in range(8)]
    assert [len(rd) for rd in arc["rounds"]] == [8, 16, 8, 4, 2, 1]
    r32 = {g["home"] for g in arc["rounds"][1]} | {g["away"] for g in arc["rounds"][1]}
    assert r32 == {f"S{i:02d}" for i in range(1, 33)}
    assert len(arc["field"]) == 40 and arc["champion"] == "S01"
    # the 48 is the same function at byes=16; `run_state_48` is that call
    assert jh.run_state_48(seeds + [_T(f"S{i}") for i in range(41, 49)], seed=3) \
        == jh.run_state_parastate(seeds + [_T(f"S{i}") for i in range(41, 49)],
                                  byes=16, seed=3)


def test_the_bid_table_and_the_committee_seat_count_agree():
    """8A/9A/Group 1 at 16, 7A at 8 (owner rule 2026-09); every Parastate class
    is a road-32 class and plays 4S/5D; the committee selects exactly the
    group's seats and an automatic bid CONSUMES one of them."""
    assert jh.AT_LARGE_BIDS == {"7A": 8, "8A": 16, "9A": 16, "Group 1": 16}
    for g in jh.ATLARGE_GROUPS:
        assert jh.state_field_size(g) == 32, g
        assert g in jh.WIDE_GROUPS, g
    assert jh.at_large_bids("6A") == 0
    sel = jc.select(_ratings(), ROAD, [], seats=8)
    assert len(sel["selected"]) == 8 == sel["seats"]
    assert set(sel["selected"]) == {f"T{i:02d}" for i in range(33, 41)}
    sel = jc.select(_ratings(), ROAD, ["T59"], seats=8)
    assert "T59" in sel["auto"] and len(sel["selected"]) == 8
    assert set(sel["selected"]) - {"T59"} == {f"T{i:02d}" for i in range(33, 40)}


def test_a_parastate_exit_reads_as_the_parastate(monkeypatch):
    """The finish label comes off the round's archived name — 'Parastate', short
    'Paras' — never the 'Round of 48' team-count band that files a seed's only
    State dual under a qualifying label (owner, 2026-09)."""
    import app.world as world
    import app.web.state as st
    seeds = [_T(f"S{i:02d}") for i in range(1, 49)]
    monkeypatch.setattr(jh, "play_dual",
                        lambda a, b, *, seed, phase: _Res(0))
    arc = jh.run_state_48(seeds, seed=1)
    res = world.jhsaa_state_result(arc, "S48")      # 17v48 loser
    assert res["finish"] == jh.PARASTATE_NAME
    assert res["place"] == 48 and res["made_state"]
    assert st._finish_short(jh.PARASTATE_NAME) == "Paras"
    # an R32 exit is a main-draw finish, not a Parastate one
    r32 = arc["rounds"][1][0]
    r32_loser = r32["away"] if r32["winner"] == r32["home"] else r32["home"]
    assert world.jhsaa_state_result(arc, r32_loser)["finish"] != jh.PARASTATE_NAME
