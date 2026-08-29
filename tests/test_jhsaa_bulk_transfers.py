"""The bulk-transfer workflow: the clearing-market proposal matcher and the
select-and-submit routes.

`_propose_destinations` is tested pure — synthetic ladders, no roster build —
because the rules it encodes are the brief's
(docs/reports/BRIEF-jhsaa-opportunity-clearing-market.md): lateral first, one
real competitive step at a time, freshman-aware projection, arrivals stack.
"""
import pytest

from app.jhsaa import _propose_destinations, CLEARING_LEVELS


def _cand(pid, school, group, ovr, grade=10, name=None):
    return {"pid": pid, "name": name or pid, "school": school, "group": group,
            "grade": grade, "ovr": ovr}


def test_lateral_same_class_beats_bandmate_and_drop():
    # A buried 9A player fits a weak 9A program: they must go THERE, not to the
    # 8A band-mate and not down to 7A, even though both would also take them.
    groups = {"Elite 9A": "9A", "Weak 9A": "9A", "Weak 8A": "8A", "Weak 7A": "7A"}
    ladders = {"Elite 9A": [70] * 11, "Weak 9A": [40] * 11,
               "Weak 8A": [30] * 11, "Weak 7A": [25] * 11}
    out = _propose_destinations([_cand("p1", "Elite 9A", "9A", 55)],
                                ladders, groups, top_slot=11)
    assert out[0]["to"] == "Weak 9A" and out[0]["drop"] == 0


def test_bandmate_taken_before_a_real_drop():
    groups = {"Elite 9A": "9A", "Other 9A": "9A", "Weak 8A": "8A", "Weak 7A": "7A"}
    ladders = {"Elite 9A": [70] * 11, "Other 9A": [70] * 11,
               "Weak 8A": [40] * 11, "Weak 7A": [25] * 11}
    out = _propose_destinations([_cand("p1", "Elite 9A", "9A", 55)],
                                ladders, groups, top_slot=11)
    assert out[0]["to"] == "Weak 8A" and out[0]["drop"] == 0


def test_drops_one_level_only_when_the_level_has_no_home():
    # Nothing in 9A/8A has a varsity seat -> the player enters 7A/6A, never 1A.
    groups = {"Elite 9A": "9A", "Other 9A": "9A", "Elite 8A": "8A",
              "Weak 6A": "6A", "Weak 1A": "1A"}
    ladders = {s: [70] * 11 for s in ("Elite 9A", "Other 9A", "Elite 8A")}
    ladders["Weak 6A"] = [40] * 11
    ladders["Weak 1A"] = [20] * 11
    out = _propose_destinations([_cand("p1", "Elite 9A", "9A", 55)],
                                ladders, groups, max_drop=6, top_slot=11)
    assert out[0]["to"] == "Weak 6A" and out[0]["drop"] == 1


def test_dominance_is_a_last_resort_on_a_drop_not_a_bar():
    # Two lower-level options: the one where the arrival slots in at #4 beats
    # the one where they'd be the outright new #1 — dominance is penalised…
    groups = {"Elite 9A": "9A", "Mid 7A": "7A", "Weak 7A": "7A"}
    ladders = {"Elite 9A": [70] * 11,
               "Mid 7A": [60, 58, 56] + [30] * 8, "Weak 7A": [25] * 11}
    out = _propose_destinations([_cand("p1", "Elite 9A", "9A", 55)],
                                ladders, groups, top_slot=11)
    assert out[0]["to"] == "Mid 7A" and out[0]["slot"] == 4
    # …but when the #1 seat is the ONLY home, they still get it (the market
    # guarantees everyone a home; a drop to #1 beats no move at all).
    groups2 = {"Elite 9A": "9A", "Weak 7A": "7A"}
    ladders2 = {"Elite 9A": [70] * 11, "Weak 7A": [25] * 11}
    out2 = _propose_destinations([_cand("p1", "Elite 9A", "9A", 55)],
                                 ladders2, groups2, max_drop=1, top_slot=11)
    assert out2[0]["to"] == "Weak 7A" and out2[0]["slot"] == 1


def test_max_per_school_spreads_a_wave():
    groups = {"Elite 9A": "9A", "Weak 9A": "9A", "Other 9A": "9A"}
    ladders = {"Elite 9A": [70] * 11, "Weak 9A": [40] * 11, "Other 9A": [41] * 11}
    cands = [_cand(f"p{i}", "Elite 9A", "9A", 55 - i) for i in range(4)]
    out = _propose_destinations(cands, ladders, groups,
                                max_per_school=2, top_slot=11)
    dests = [r["to"] for r in out]
    assert dests.count("Weak 9A") == 2 and dests.count("Other 9A") == 2


def test_freshman_aware_projection_uses_next_season_ladder():
    # The board says OVR 45 today, but next season's roster (incoming freshmen
    # included) buries anyone under 50 at the lateral option -> the projection
    # must be run against the NEXT-season ladder handed in, not the label.
    groups = {"Elite 9A": "9A", "Weak 9A": "9A", "Weak 7A": "7A"}
    ladders = {"Elite 9A": [70] * 11,
               "Weak 9A": [50] * 11,       # next year's freshmen already inside
               "Weak 7A": [46, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30]}
    out = _propose_destinations([_cand("p1", "Elite 9A", "9A", 45)],
                                ladders, groups, max_drop=2, top_slot=11)
    assert out[0]["to"] == "Weak 7A"


def test_unladdered_group_is_lateral_only():
    groups = {"GB One": "Group 1", "GB Two": "Group 1", "Weak 1A": "1A"}
    ladders = {"GB One": [70] * 11, "GB Two": [30] * 11, "Weak 1A": [20] * 11}
    out = _propose_destinations([_cand("p1", "GB One", "Group 1", 45)],
                                ladders, groups, max_drop=6, top_slot=11)
    assert out[0]["to"] == "GB Two"


def test_clearing_levels_cover_the_ladder_once():
    flat = [g for band in CLEARING_LEVELS for g in band]
    assert flat == ["9A", "8A", "7A", "6A", "5A", "4A", "3A", "2A", "1A"]


# --- routes respond (the empty-state contract every JHSAA surface keeps) -------

@pytest.fixture(scope="module")
def client():
    import os
    os.environ.setdefault("PTC_NO_BOOT_WARM", "1")
    from app.web.server import create_app
    return create_app().test_client()


def test_bulk_post_with_nothing_checked_renders(client):
    r = client.post("/editor/jhsaa-transfer-bulk", data={"g": "boys"})
    assert r.status_code == 200
    assert b"Nothing was checked" in r.data


def test_bulk_post_prefills_the_batch(client):
    r = client.post("/editor/jhsaa-transfer-bulk",
                    data={"g": "boys",
                          "pids": ["jh_deadbeef|Test Player — 9A Nowhere"]})
    assert r.status_code == 200
    assert b"jh_deadbeef," in r.data
    assert b"# Test Player" in r.data


def test_transfers_page_with_propose_and_no_archive_renders(client):
    r = client.get("/jhsaa/transfers?find=1&propose=1&g=boys")
    assert r.status_code == 200


# --- the reserve-cohort finder (read-only) -----------------------------------

def _school(n_varsity, v_ovr, n_reserve, r_ovr, start=0):
    rows = ([{"pid": f"v{start+i}", "name": f"V{start+i}", "grade": 11, "ovr": v_ovr}
             for i in range(n_varsity)]
            + [{"pid": f"r{start+i}", "name": f"R{start+i}", "grade": 10, "ovr": r_ovr}
               for i in range(n_reserve)])
    return sorted(rows, key=lambda r: -r["ovr"])


def test_finder_flags_the_rockridge_shape():
    from app.jhsaa import _find_cohorts
    rosters = {
        "Deep 9A": _school(11, 65, 8, 55),          # the second-team program
        "Ordinary 9A": _school(11, 50, 8, 30, 100),
        "Weak 9A": _school(11, 40, 8, 25, 200),
        "Weak 5A": _school(11, 35, 8, 20, 300),
    }
    groups = {"Deep 9A": "9A", "Ordinary 9A": "9A", "Weak 9A": "9A",
              "Weak 5A": "5A"}
    res = _find_cohorts(rosters, groups)
    srcs = {s["school"]: s for s in res["sources"]}
    assert "Deep 9A" in srcs
    src = srcs["Deep 9A"]
    # 55-OVR cohort clears 9A's median team strength (50) -> plays like 9A.
    assert src["plays_like"] == "9A" and src["cohort_mean"] == 55.0
    assert len(src["cohort"]) == 8 and src["strong_varsity"]
    # Suggested hosts never include the source itself, and carry a combined rank.
    assert src["hosts"] and all(h["school"] != "Deep 9A" for h in src["hosts"])
    assert all(h["rank"] >= 1 and h["combined"] > 0 for h in src["hosts"])
    # An ordinary reserve group (30 vs a 35 floor anywhere) is not a cohort.
    assert "Ordinary 9A" not in srcs or srcs["Ordinary 9A"]["plays_like"] != "9A"


def test_finder_host_shapes():
    from app.jhsaa import _find_cohorts
    core_void = _school(3, 60, 16, 20)              # 3 real players, then a cliff
    rebuild = _school(11, 20, 8, 15, 100)           # weak throughout
    strong = _school(11, 60, 8, 40, 200)
    rosters = {"CoreVoid": core_void, "Rebuild": rebuild, "Strong": strong}
    groups = {s: "5A" for s in rosters}
    res = _find_cohorts(rosters, groups)
    shapes = {h["school"]: h["shape"] for h in res["hosts"]["5A"]}
    assert shapes["Rebuild"] == "rebuild"
    assert shapes["CoreVoid"] == "core + void"


def test_cohorts_route_empty_state(client):
    r = client.get("/jhsaa/cohorts?g=boys")
    assert r.status_code == 200
