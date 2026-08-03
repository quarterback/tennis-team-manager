"""Team Scanner — the cross-division TEAM board in the Analytics Bureau.

Invariant-style checks (no golden values): the board must cover every division
in one list, carry both rating lenses per team (live STR + current/ceiling
OVERALL), sort/filter/flip coherently, and the expandable rosters must agree
with the same god-mode scan the player boards read.
"""
import pytest

import app.scout_intel as si
from app.ncaa import lineup_size
from app.web.server import create_app


@pytest.fixture(scope="module")
def board():
    create_app()                     # bootstrap schemas; base (no-world) rosters
    return si.team_board("men")


def test_board_spans_all_divisions_in_one_list(board):
    assert {t["division"] for t in board} == {"D1", "D2", "D3", "D4"}
    # one row per program, ranked 1..n after the sort
    assert [t["rank"] for t in board] == list(range(1, len(board) + 1))
    assert len({t["school"] for t in board}) == len(board)


def test_board_metrics_are_coherent(board):
    for t in board:
        # both lenses present; OVERALL numbers live on the 20–80 grade scale
        assert t["card_str"] > 0
        assert 20 <= t["card_ovr"] <= 80
        assert 20 <= t["roster_ovr"] <= 80
        assert 20 <= t["ceiling"] <= 80
        # ceiling is the same card's ceiling, so the core can only grow
        assert t["upside"] >= 0
        assert t["best_ovr"] >= t["card_ovr"] - 0.5   # best player tops the card average
        assert t["n_roster"] >= lineup_size(t["division"])
        assert t["n_buried"] >= 0


def test_default_sort_is_current_ability_descending(board):
    ovrs = [t["card_ovr"] for t in board]
    assert ovrs == sorted(ovrs, reverse=True)


def test_direction_flip_surfaces_weakest_first():
    asc = si.team_board("men", direction="asc")
    ovrs = [t["card_ovr"] for t in asc]
    assert ovrs == sorted(ovrs)


def test_division_conference_and_query_filters():
    d2 = si.team_board("men", division="D2")
    assert d2 and all(t["division"] == "D2" for t in d2)

    confs = si.team_board_conferences("men", "D2")
    assert confs, "D2 should expose conferences for the filter"
    one = si.team_board("men", division="D2", conf=confs[0])
    assert one and all(t["conf"] == confs[0] for t in one)
    # "All" divisions hides the conference cut — it only means something in-division
    assert si.team_board_conferences("men", "All") == []

    school = d2[0]["school"]
    hits = si.team_board("men", q=school[:8])
    assert any(t["school"] == school for t in hits)


def test_sort_lenses(board):
    by_str = si.team_board("men", sort="card_str")
    strs = [t["card_str"] for t in by_str]
    assert strs == sorted(strs, reverse=True)

    by_ceil = si.team_board("men", sort="ceiling")
    ceils = [t["ceiling"] for t in by_ceil]
    assert ceils == sorted(ceils, reverse=True)

    by_buried = si.team_board("men", sort="buried")
    buried = [t["n_buried"] for t in by_buried]
    assert buried == sorted(buried, reverse=True)


def test_rosters_agree_with_the_scan(board):
    data = si.scan("men")
    picks = [board[0], board[len(board) // 2], board[-1]]
    rosters = si.team_rosters("men", [t["school"] for t in picks])
    for t in picks:
        roster = rosters[t["school"]]
        assert len(roster) == t["n_roster"]
        card = lineup_size(t["division"])
        # ladder order: starters first, lines 1..card, then depth
        lines = [x["line"] for x in roster if x["line"] is not None]
        assert lines == list(range(1, min(card, len(roster)) + 1))
        strs = [x["live_str"] for x in roster]
        assert strs == sorted(strs, reverse=True)
        for x in roster:
            assert x["pid"] in data["by_pid"]          # links resolve into the scan
            assert x["true_overall"] >= x["cur_overall"]
        # the summary row's numbers are derived from exactly these players
        starters = [x["live_str"] for x in roster if x["line"] is not None]
        assert t["card_str"] == round(sum(starters) / len(starters), 1)
        allovr = [x["cur_overall"] for x in roster]
        assert t["roster_ovr"] == round(sum(allovr) / len(allovr), 1)
        assert t["n_buried"] == sum(1 for x in roster if x["buried"])


def test_route_renders_and_paginates():
    c = create_app().test_client()
    r = c.get("/intel/teams?u=D1-men")
    assert r.status_code == 200
    html = r.data.decode()
    assert "Team Scanner" in html and "BURIED" in html
    # filters + direction flip survive the round trip
    r2 = c.get("/intel/teams?u=D1-men&div=D3&dir=asc&sort=upside&page=2")
    assert r2.status_code == 200
