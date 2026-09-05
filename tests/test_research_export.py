import csv
import io
import json
import zipfile
from types import SimpleNamespace

import pytest

from app.research_export import ExportError, build_college, build_jhsaa, export_zip
from app.web.server import NAV_GROUPS, _active_nav


def _prospect(pid, name, grade):
    return SimpleNamespace(pid=pid, name=name, grade=grade, year=0, hometown="Northbank",
                           country="US", current_overall=lambda: 42,
                           ceiling_overall=lambda: 55,
                           academic_rating=81, traits={"play_style": "all_court"})


def _team(name, group, home):
    school = SimpleNamespace(name=name, key=f"{name}|girls", city="Aurora", locality="",
        county="Gold", area="North", classification=group, group=group, district="7A-1",
        enrollment=1200, private=False, mascot="Aces", colors=["#123456"])
    line = {"slot": "S1", "home": ["Ana Ace"], "away": ["Bea Ball"],
            "score": "6-3 6-4", "home_won": True}
    schedule = [{"opp": "Ball High" if home else "Ace High", "home": home,
                 "phase": "regular", "pf": 4, "pa": 3, "won": home,
                 "district": True, "lines": [line]}]
    player = _prospect("ana" if home else "bea", "Ana Ace" if home else "Bea Ball", 12)
    return SimpleNamespace(school=school, roster=[player], wins=1 if home else 0,
        losses=0 if home else 1, dwins=1 if home else 0, dlosses=0 if home else 1,
        district_place=1 if home else 2, points_for=4, points_against=3, power=1.25,
        schedule=schedule)


def test_jhsaa_bundle_is_self_describing_and_normalized():
    from app.jhsaa import GROUPS

    a, b = _team("Ace High", "7A", True), _team("Ball High", "7A", False)
    groups = {g: {"state": {"champion": "Ace High"}} for g in GROUPS}
    individual_draw = {"entries": [{"school": "Ace High", "players": [{"pid": "ana"}]}],
                       "rounds": [], "champion": 0, "runner_up": None}
    files = build_jhsaa(2027, "girls", "7A",
                        season={"teams": {"a": a, "b": b}, "groups": groups, "awards": {},
                                "individuals": {
                                    "girls": {"7A": {"S1": individual_draw},
                                              "6A": {"S1": {"not": "in scope"}}},
                                    "mixed": {"7A": {"XD": individual_draw}}}})
    assert {"README.md", "manifest.json", "programs.csv", "players.csv", "duals.csv",
            "lines.csv", "line_players.csv", "jhsaa_standings.csv",
            "jhsaa_individuals.json"} <= files.keys()
    manifest = json.loads(files["manifest.json"])
    assert manifest["dataset_family"] == "jhsaa"
    assert manifest["college_plan"]["status"] == "available"
    assert manifest["files"]["jhsaa_individuals.json"]["media_type"] == "application/json"
    individuals = json.loads(files["jhsaa_individuals.json"])
    assert individuals == {"girls": {"7A": {"S1": individual_draw}},
                           "mixed": {"7A": {"XD": individual_draw}}}
    duals = list(csv.DictReader(io.StringIO(files["duals.csv"].decode())))
    assert len(duals) == 1
    assert duals[0]["home_program_id"] == "Ace High|girls"
    players = list(csv.DictReader(io.StringIO(files["players.csv"].decode())))
    assert players[0]["grade"] == "12"
    assert players[0]["current_grade"] == "42"
    assert players[0]["potential_grade"] == "55"


def test_export_zip_contains_manifest(monkeypatch):
    monkeypatch.setitem(__import__("app.research_export", fromlist=["BUILDERS"]).BUILDERS,
                        "tiny", lambda **scope: {"manifest.json": b"{}"})
    with zipfile.ZipFile(export_zip("tiny", year=2027)) as zf:
        assert zf.namelist() == ["manifest.json"]


def test_export_is_discoverable_in_tools_menu():
    tools = dict(NAV_GROUPS)["Tools"]
    item = next(item for item in tools if item["id"] == "research_export")
    assert item["label"] == "Export Research Data"
    assert item["endpoint"] == "research_export"


def test_export_page_marks_tools_item_active():
    class Request:
        path = "/research/export"

    assert _active_nav(Request()) == "research_export"


def test_college_bundle_is_self_describing_and_normalized(played_season):
    import app.seasonmode as sm

    sid = sm.find_season("D1", "men", seed=2026)
    assert sid is not None
    files = build_college(2026, "D1", "men", season_id=sid)
    assert {"README.md", "manifest.json", "programs.csv", "players.csv", "duals.csv",
            "lines.csv", "line_players.csv", "college_standings.csv",
            "college_scholarships.csv", "college_rankings.csv"} <= files.keys()

    manifest = json.loads(files["manifest.json"])
    assert manifest["dataset_family"] == "college"
    assert manifest["scope"] == {"year": 2026, "division": "D1", "gender": "men"}

    duals = list(csv.DictReader(io.StringIO(files["duals.csv"].decode())))
    assert len(duals) > 0
    assert {"REG", "CT", "NCAA"} & {d["round"] for d in duals}

    programs = list(csv.DictReader(io.StringIO(files["programs.csv"].decode())))
    program_ids = {p["program_id"] for p in programs}
    assert all(d["home_program_id"] in program_ids for d in duals)

    players = list(csv.DictReader(io.StringIO(files["players.csv"].decode())))
    assert len(players) > 0

    line_players = list(csv.DictReader(io.StringIO(files["line_players.csv"].decode())))
    player_ids = {p["player_id"] for p in players}
    # every recorded line participant is a real, currently-rostered pid
    assert any(lp["player_id"] in player_ids for lp in line_players)


def test_college_bundle_rejects_bad_scope():
    # division/gender are validated before any DB access, so this needs no played
    # season — a real season_id would never even be reached.
    with pytest.raises(ExportError):
        build_college(2026, "D5", "men")
    with pytest.raises(ExportError):
        build_college(2026, "D1", "coed")


def test_college_export_without_a_world_errors_loudly(monkeypatch):
    import app.world as wd

    monkeypatch.setattr(wd, "load_world", lambda seed: None)
    with pytest.raises(ExportError):
        build_college(2026, "D1", "men")


def test_the_export_carries_the_computer_ratings_and_committee():
    """Owner spec 2026-09: the nine-system ratings layer rides as
    jhsaa_computer_ratings.csv (joined on program_id) and the at-large
    committee as jhsaa_committee.json, classification-scoped like everything
    else. A season without the keys (pre-layer archive, plain test season)
    emits an empty table and an empty dict rather than raising."""
    from app.jhsaa import GROUPS
    from app.jhsaa_ratings import SYSTEMS

    a, b = _team("Ace High", "7A", True), _team("Ball High", "7A", False)
    groups = {g: {"state": {"champion": "Ace High"}} for g in GROUPS}
    ratings = {"7A": {"teams": {
        "Ace High": {"record": "1-0", "district": "7A-1",
                     "ranks": {s: 1 for s in SYSTEMS},
                     "values": {s: 1.0 for s in SYSTEMS},
                     "mean": 1.0, "median": 1.0, "sigma": 0.0},
        "Ball High": {"record": "0-1", "district": "7A-1",
                      "ranks": {s: 2 for s in SYSTEMS},
                      "values": {s: 0.5 for s in SYSTEMS},
                      "mean": 2.0, "median": 2.0, "sigma": 0.0}},
        "disconnected": False, "systems": list(SYSTEMS), "sor_bench": 0.9},
        # out-of-scope group must be cut by the classification filter
        "6A": {"teams": {"Elsewhere": {"record": "0-0", "district": "x",
                                       "ranks": {}, "values": {}, "mean": 0,
                                       "median": 0, "sigma": 0}},
               "disconnected": False, "systems": list(SYSTEMS), "sor_bench": 0.5}}
    committee = {"7A": {"selected": ["Ball High"], "auto": [], "locks": [],
                        "borda": {"Ball High": 5}, "seed_borda": {"Ball High": 16},
                        "ballots": {}, "ranges": {}, "status": {}, "weights": {}},
                 "Group 1": None}
    files = build_jhsaa(2027, "girls", "7A",
                        season={"teams": {"a": a, "b": b}, "groups": groups,
                                "awards": {}, "individuals": {},
                                "ratings": ratings, "committee": committee})
    rows = list(csv.DictReader(io.StringIO(
        files["jhsaa_computer_ratings.csv"].decode())))
    assert {r["name"] for r in rows} == {"Ace High", "Ball High"}   # 6A scoped out
    ace = next(r for r in rows if r["name"] == "Ace High")
    assert ace["program_id"] == "Ace High|girls"                    # id join, not name
    assert ace["rank_massey_game"] == "1" and ace["sor_bench"] == "0.9"
    comm = json.loads(files["jhsaa_committee.json"].decode())
    assert list(comm) == ["7A"] and comm["7A"]["selected"] == ["Ball High"]
    # and a season with no keys at all still builds
    files2 = build_jhsaa(2027, "girls", "7A",
                         season={"teams": {"a": a, "b": b}, "groups": groups,
                                 "awards": {}, "individuals": {}})
    assert json.loads(files2["jhsaa_committee.json"].decode()) == {}
    assert list(csv.DictReader(io.StringIO(
        files2["jhsaa_computer_ratings.csv"].decode()))) == []
