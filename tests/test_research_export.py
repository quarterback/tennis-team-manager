import csv
import io
import json
import zipfile
from types import SimpleNamespace

from app.research_export import build_jhsaa, export_zip


def _prospect(pid, name, grade):
    return SimpleNamespace(pid=pid, name=name, year=grade, hometown="Northbank",
                           country="US", current_grade=42, potential_grade=55,
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
    a, b = _team("Ace High", "7A", True), _team("Ball High", "7A", False)
    groups = {g: {"state": {"champion": "Ace High"}} for g in
              ("9A", "8A", "7A", "6A", "5A", "4A", "3A", "2A-1A")}
    files = build_jhsaa(2027, "girls", "7A",
                        season={"teams": {"a": a, "b": b}, "groups": groups, "awards": {}})
    assert {"README.md", "manifest.json", "programs.csv", "players.csv", "duals.csv",
            "lines.csv", "line_players.csv", "jhsaa_standings.csv"} <= files.keys()
    manifest = json.loads(files["manifest.json"])
    assert manifest["dataset_family"] == "jhsaa"
    assert manifest["college_plan"]["status"] == "not implemented"
    duals = list(csv.DictReader(io.StringIO(files["duals.csv"].decode())))
    assert len(duals) == 1
    assert duals[0]["home_program_id"] == "Ace High|girls"


def test_export_zip_contains_manifest(monkeypatch):
    monkeypatch.setitem(__import__("app.research_export", fromlist=["BUILDERS"]).BUILDERS,
                        "tiny", lambda **scope: {"manifest.json": b"{}"})
    with zipfile.ZipFile(export_zip("tiny", year=2027)) as zf:
        assert zf.namelist() == ["manifest.json"]
