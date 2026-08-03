"""Lineup Architect — deal underutilized talent into whole competitive squads."""
import pytest

import app.scout_intel as si
from app.ncaa import lineup_size
from app.web.server import create_app


@pytest.fixture(scope="module")
def arch():
    create_app()
    return si.lineup_architect("men", target_division="D2")


def test_squads_are_full_cards_dealt_best_first(arch):
    assert arch["card"] == lineup_size("D2")
    assert arch["squads"], "buried pool should field at least one D2 card"
    seen = set()
    prev = None
    for s in arch["squads"]:
        assert len(s["players"]) == arch["card"]
        ovrs = [x["cur_overall"] for x in s["players"]]
        assert ovrs == sorted(ovrs, reverse=True)
        assert [x["slot"] for x in s["players"]] == list(range(1, arch["card"] + 1))
        pids = {x["pid"] for x in s["players"]}
        assert not (pids & seen)                      # non-overlapping
        seen |= pids
        if prev is not None:
            assert prev >= s["avg_ovr"]               # squad 1 strongest
        prev = s["avg_ovr"]
        assert 1 <= s["rank"] <= s["n_div"] + 1
        assert s["avg_ceil"] >= s["avg_ovr"]


def test_pool_gates():
    buried = si.lineup_architect("men", target_division="D2", pool="buried")
    for s in buried["squads"]:
        for x in s["players"]:
            p = si.scan("men")["by_pid"][x["pid"]]
            assert (p.placement_gap >= si.UNDERPLACED_MIN_GAP
                    and p.true_overall >= si.UNDERPLACED_MIN_TRUE)

    below = si.lineup_architect("men", target_division="D1", pool="below")
    for s in below["squads"]:
        assert all(x["division"] != "D1" for x in s["players"])

    gated = si.lineup_architect("men", target_division="D2", pool="any",
                                min_ovr=55, min_str=40.0)
    for s in gated["squads"]:
        for x in s["players"]:
            assert x["cur_overall"] >= 55 and x["live_str"] >= 40.0

    # OVR band: a max keeps the elite out, so mid-tier squads are buildable
    band = si.lineup_architect("men", target_division="D3", pool="any",
                               min_ovr=45, max_ovr=52)
    assert band["squads"], "mid-tier band should still field squads"
    for s in band["squads"]:
        for x in s["players"]:
            assert 45 <= x["cur_overall"] <= 52

    impossible = si.lineup_architect("men", target_division="D2", min_ovr=80)
    assert impossible["squads"] == [] and impossible["pool_size"] == 0


def test_rank_is_against_real_division_cards(arch):
    data = si.scan("men")
    lvls = sorted((sum(t["top6_cur"]) / len(t["top6_cur"])
                   for t in data["team_ladder"] if t["division"] == "D2"), reverse=True)
    s = arch["squads"][0]
    assert s["n_div"] == len(lvls)
    assert s["rank"] == 1 + sum(1 for lv in lvls if lv > s["avg_ovr"])


def test_route_renders():
    c = create_app().test_client()
    r = c.get("/intel/architect?u=D1-men")
    assert r.status_code == 200
    assert b"Squad 1" in r.data
    assert c.get("/intel/architect?u=D1-men&div=D3&pool=below&min_ovr=50&squads=2").status_code == 200
    assert c.get("/intel/architect?u=D1-men&min_ovr=junk&squads=99").status_code == 200
