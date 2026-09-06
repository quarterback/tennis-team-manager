"""The Career Wins boards — specifically the TOP-FLIGHT board (owner rule
2026-09): No. 1 singles / No. 1 doubles wins only, the era-comparable list. The
flight-independent boards reward opportunity — a lower-flight career piles up
wins against lower flights, and the 4S/5D era hands wide-format seasons nine
flights of them — so the "all-time greatest" cut is S1/D1 alone.

Hand-archived duals, the repeat-rolls fixture's idiom: the fold reads only
`world_jhsaa_dual.lines`, so two crafted seasons are the whole input."""
import json

import pytest

from app import world as wd


def _line(slot, home_names, away_names, home_won, score="6-1, 6-2"):
    return {"slot": slot, "home": home_names, "away": away_names,
            "score": score, "home_won": home_won}


def _dual(year, school, opp, lines, level="v"):
    return (1, year, "girls", school, opp, 1, "regular", 4, 3, 1, 1,
            json.dumps(lines), level, 0, "", "[]")


@pytest.fixture(scope="module")
def archive():
    w = wd.get_or_create(wd.DEFAULT_SEED)
    conn = wd._db()
    try:
        conn.execute("DELETE FROM world_jhsaa_dual WHERE world_id=?", (w["id"],))
        conn.execute("DELETE FROM world_jhsaa WHERE world_id=?", (w["id"],))
        # Ada: two S1 wins and a D1 win — 3 top-flight wins, 3 overall.
        # Bea: five wins, every one at S4/D3 — 5 overall, 0 top-flight.
        duals = []
        for year in (0, 1):
            duals.append(_dual(year, "Foxboro", "Eastmont", [
                _line("S1", ["Ada Ace"], ["Rival One"], True),
                _line("S4", ["Bea Bulk"], ["Rival Two"], True),
                _line("D3", ["Bea Bulk", "Cara Depth"], ["R3", "R4"], True),
            ]))
        duals.append(_dual(1, "Foxboro", "Westlake", [
            _line("D1", ["Ada Ace", "Cara Depth"], ["R5", "R6"], True),
            _line("S4", ["Bea Bulk"], ["R7"], True),
        ]))
        # a JV dual must never reach any board (the section's level rule)
        duals.append(_dual(1, "Foxboro", "Eastmont", [
            _line("S1", ["Bea Bulk"], ["R8"], True)], level="jv"))
        conn.executemany(
            "INSERT INTO world_jhsaa_dual (world_id, year, gender, school, opp,"
            " home, phase, pf, pa, won, district, lines, level, tied, shape, played)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", duals)
        # minimal season summaries so `jhsaa_years` sees two archived years
        for year in (0, 1):
            conn.execute(
                "INSERT INTO world_jhsaa (world_id, year, gender, data)"
                " VALUES (?,?,?,?)",
                (w["id"], year, "girls",
                 json.dumps({"year": year, "season_year": 2027 + year,
                             "gender": "girls", "standings": {}})))
        conn.commit()
    finally:
        conn.close()
    wd._careerwins_cache.clear()
    out = wd.jhsaa_career_wins(w["id"], "girls", limit=10)
    return out


def test_the_top_flight_board_counts_s1_and_d1_only(archive):
    top = {r["name"]: r for r in archive["players"]["top"]}
    ada = top["Ada Ace"]
    assert ada["t_w"] == 3 and ada["t_l"] == 0          # 2x S1 + 1x D1
    assert ada["t_s_w"] == 2 and ada["t_d_w"] == 1
    bea = top.get("Bea Bulk")
    assert bea is None or bea["t_w"] == 0               # S4/D3 never count


def test_the_s1_and_d1_boards_are_each_half_alone(archive):
    s1 = {r["name"]: r for r in archive["players"]["top_s"]}
    d1 = {r["name"]: r for r in archive["players"]["top_d"]}
    assert s1["Ada Ace"]["t_s_w"] == 2
    assert d1["Ada Ace"]["t_d_w"] == 1
    # Cara's ONLY top-flight win is the D1 — she must lead nobody on the S1
    # board yet stand on the D1 board on her own merit.
    assert d1["Cara Depth"]["t_d_w"] == 1
    assert s1.get("Cara Depth", {"t_s_w": 0})["t_s_w"] == 0


def test_the_flight_independent_boards_are_unchanged_by_the_gate(archive):
    overall = {r["name"]: r for r in archive["players"]["overall"]}
    assert overall["Bea Bulk"]["w"] == 5                # opportunity still counts here
    assert overall["Ada Ace"]["w"] == 3
    # ...and the top board orders the other way around
    names = [r["name"] for r in archive["players"]["top"]]
    assert names.index("Ada Ace") < names.index("Bea Bulk") \
        if "Bea Bulk" in names else True


def test_jv_never_reaches_any_board(archive):
    for board in archive["players"].values():
        for r in board:
            if r["name"] == "Bea Bulk":
                assert r["t_s_w"] == 0                  # her JV S1 win is invisible
