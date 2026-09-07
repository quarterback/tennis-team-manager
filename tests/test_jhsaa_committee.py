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


def test_1a_takes_the_same_eight_bids_and_its_parastate_reduces_32_to_24(monkeypatch):
    """‼️ 1A IS THE ONE CLASS NOT ON A 40 (owner rule 2026-09: "I do not want 16
    at-large teams in 1A"). Sixteen bids is what a 40 costs off its 24 road, and
    it would have made 1A the only class where the committee picks 40% of the
    field. It takes the SAME EIGHT as 7A-2A, so its structure is 32 = 24 road +
    8: the Parastate is 17v32 … 24v25 with seeds 1-16 byeing, and the 24
    survivors play the 24-team draw 1A has always played — first round seeds
    9-24, its eight Zonal champions byeing to the Round of 16."""
    seeds = [_T(f"S{i:02d}") for i in range(1, 33)]
    monkeypatch.setattr(jh, "play_dual", lambda a, b, *, seed, phase: _Res(0))
    bids = jh.AT_LARGE_BIDS["1A"]
    assert bids == 8 == jh.AT_LARGE_BIDS["7A"] and jh.state_field_size("1A") == 24
    arc = jh.run_state_parastate(seeds, byes=jh.state_field_size("1A") - bids,
                                 seed=5)
    para = arc["rounds"][0]
    assert arc["round_names"][0] == jh.PARASTATE_NAME
    assert [(g["home"], g["away"]) for g in para] == \
        [(f"S{17 + k:02d}", f"S{32 - k:02d}") for k in range(8)]
    # 8 Parastate duals -> 24 alive; the 24 draw byes 8 and plays 8, then 8/4/2/1.
    assert [len(rd) for rd in arc["rounds"]] == [8, 8, 8, 4, 2, 1]
    alive = {g["home"] for g in arc["rounds"][1]} | {g["away"] for g in arc["rounds"][1]}
    assert alive == {f"S{i:02d}" for i in range(9, 25)}
    assert len(arc["field"]) == 32 and arc["champion"] == "S01"


def test_the_committee_blurb_is_derived_from_the_tables():
    """‼️ EVERY HAND-WRITTEN COPY OF "which classes use the committee" HAS GONE
    STALE. The sub-rail tooltip, the empty state and the research-export manifest
    each carried their own list ("7A and Group 1", "the 48-team groups", "sixteen
    selections seeded 33-48"), so after the expansion a reader browsing a 6A
    archive was told their class never uses the committee, and a 6A-1A export
    stated the wrong field semantics. `parastate_summary` is the one derivation
    all three read; a description of a table belongs to the table."""
    shapes = jh.parastate_summary()
    # Every Parastate class appears exactly once. The rows GROUP BY SHAPE, so the
    # flat order is not `GROUPS` order (Group 1 sits with 9A/8A at 48); within a
    # row it is, which is what makes each row read as a class list.
    listed = [g for _lbl, gs, _r, _b in shapes for g in gs]
    assert sorted(listed) == sorted(jh.ATLARGE_GROUPS)
    assert len(listed) == len(set(listed))
    for _lbl, gs, _r, _b in shapes:
        assert gs == [g for g in jh.GROUPS if g in set(gs)], gs
    for _lbl, gs, road, bids in shapes:
        for g in gs:
            assert (jh.state_field_size(g), jh.at_large_bids(g)) == (road, bids), g
    # The seed range an at-large occupies is `road+1 .. road+bids` — below the
    # whole road, whatever the shape (25-32 in 1A, not 33-40).
    by_class = {g: (r, b) for _l, gs, r, b in shapes for g in gs}
    assert by_class["1A"] == (24, 8) and by_class["7A"] == (32, 8)
    assert by_class["9A"] == (32, 16)
    blurb = jh.parastate_blurb()
    for g in jh.ATLARGE_GROUPS:
        assert g in blurb, g
    assert "Group 2" not in blurb


def test_the_bid_table_and_the_committee_seat_count_agree():
    """8A/9A/Group 1 at 16, everybody else at 8 (owner rules 2026-09 — 7A first,
    then 6A-1A with the playoff expansion). ‼️ THE BID COUNT IS THE DECISION AND
    THE FIELD IS THE CONSEQUENCE: eight bids is a 40 off a 32 road and a 32 off
    1A's 24, which is why 1A is not on a 40 and must not be "fixed" onto one.
    The committee selects exactly the group's seats and an automatic bid
    CONSUMES one of them."""
    assert jh.AT_LARGE_BIDS == {"9A": 16, "8A": 16, "7A": 8, "6A": 8, "5A": 8,
                                "4A": 8, "3A": 8, "2A": 8, "1A": 8,
                                "Group 1": 16, "Group 3": 4}
    for g in jh.ATLARGE_GROUPS:
        road = jh.state_field_size(g)
        bids = jh.at_large_bids(g)
        # Every at-large plays a ROAD qualifier for its seat — the Parastate is
        # the `2 × bids` lowest seeds, so the bids can never outnumber the road.
        assert bids <= road, g
        assert bids in (4, 8, 16), g
    # The consequence, spelled out so a "tidy 1A onto a 40" edit fails here:
    # eight bids is a 40 off a 32 road and a 32 off 1A's 24.
    assert jh.state_field_size("1A") + jh.at_large_bids("1A") == 32
    assert jh.state_field_size("7A") + jh.at_large_bids("7A") == 40
    assert jh.state_field_size("9A") + jh.at_large_bids("9A") == 48
    # ‼️ Group 3 is the ONE four-bid class and is deliberately not 1A's eight
    # though the classes look alike — measured, four bids clear 97% of its
    # omissions and eight would reach to #32 of ~68. Group 2 alone has no
    # committee at all.
    assert jh.state_field_size("Group 3") + jh.at_large_bids("Group 3") == 28
    assert jh.at_large_bids("Group 2") == 0
    # ‼️ THE EXPANSION IS PLAYOFF SIZE ONLY: the dual format is a SEPARATE axis
    # (`WIDE_GROUPS`) and did not move with it. Every class added in 2026-09
    # plays the Parastate at whatever shape its road already played.
    assert not (set(jh.ATLARGE_GROUPS) & set(jh.WIDE_GROUPS)) - {
        "7A", "8A", "9A", "Group 1"}
    # Group 2 is the one class with no committee at all (its road already
    # qualifies 32 of ~65 programs).
    assert jh.at_large_bids("Group 2") == 0
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
