"""The front page's story desk (`app.jhsaa_desk`) — deterministic detectors over a
hand-built archive.

One played season cannot be made to contain every story shape, so these build
the archive by hand (the repeat-rolls idiom) and assert the detectors read it:
a low seed's run, a chalk count, a boys/girls sweep, a freshman champion, the
one-flight record, and the headline register the owner set — a number or a name
first, no adjectives, one line.
"""
import re

from app import jhsaa as jh
from app import jhsaa_desk as desk


def _bracket(field, rounds):
    """A state draw: `field` in seed order, `rounds` as [(home, away, hp, ap), ...]."""
    out = {"champion": None, "field": list(field), "rounds": [], "round_names": []}
    for rd in rounds:
        games = []
        for h, a, hp, ap in rd:
            games.append({"home": h, "away": a, "home_points": hp, "away_points": ap,
                          "winner": h if hp > ap else a})
        out["rounds"].append(games)
    last = out["rounds"][-1][0]
    out["champion"] = last["winner"]
    return out


def _arc(gender, champions, brackets, standings, season_year=2073, awards=None,
         ratings=None):
    return {"year": 46, "season_year": season_year, "gender": gender,
            "champions": champions, "brackets": brackets, "standings": standings,
            "awards": awards or {}, "ratings": ratings or {}, "toc": {}}


def _rows(names, records):
    return [{"school": n, "record": r, "drecord": "", "place": i + 1,
             "pf": 5.0, "pa": 2.0, "pi": 1.0 - i * 0.05, "atr": 0.5}
            for i, (n, r) in enumerate(zip(names, records))]


def _season():
    # 9A girls: an 8-team draw where the No. 7 seed reaches the final and loses
    # 3-2 to the No. 1 seed. 8A girls: No. 1 beats No. 2 5-0.
    g9 = _bracket(["A", "B", "C", "D", "E", "F", "G", "H"],
                  [[("A", "H", 5, 0), ("D", "E", 3, 2), ("C", "F", 4, 1), ("G", "B", 3, 2)],
                   [("A", "D", 5, 0), ("G", "C", 3, 2)],
                   [("A", "G", 3, 2)]])
    g8 = _bracket(["P", "Q", "R", "S"], [[("P", "S", 5, 0), ("Q", "R", 4, 1)], [("P", "Q", 5, 0)]])
    girls = _arc("girls", {"9A": "A", "8A": "P"}, {"9A": g9, "8A": g8},
                 {"9A": {"North": _rows(list("ABCDEFGH"), ["20-0"] + ["15-5"] * 7)},
                  "8A": {"East": _rows(list("PQRS"), ["18-2", "14-6", "12-8", "10-10"])}},
                 awards={"9A": {"poy": {"pid": "p1", "pids": ["p1"], "name": "Ada Lin",
                                        "names": ["Ada Lin"], "grade": 11, "grades": [11],
                                        "school": "A", "wins": 22, "losses": 1,
                                        "kind": "singles"}}})
    b9 = _bracket(["A", "K", "L", "M"], [[("A", "M", 5, 0), ("K", "L", 3, 2)], [("A", "K", 4, 1)]])
    boys = _arc("boys", {"9A": "A"}, {"9A": b9},
                {"9A": {"North": _rows(["A", "K", "L", "M"], ["19-1", "16-4", "12-8", "9-11"])}})
    return {"year": 46, "season_year": 2073, "arcs": {"girls": girls, "boys": boys},
            "prev": {"girls": None, "boys": None},
            "one_flight": {"girls": {"G": (9, 1), "A": (3, 0)}, "boys": {}},
            "indiv": {"girls": {"9A": {"S1": {"school": "C", "players": [
                {"pid": "x1", "name": "Mia Ortiz", "grade": 9}]}}}, "boys": {}},
            "records": {"girls": {"top": [], "titles": []}, "boys": {"top": [], "titles": []}}}


def test_cinderella_names_the_lowest_seed_to_reach_a_final():
    stories = desk.d_cinderella(_season())
    girls = next(s for s in stories if s["gender"] == "girls")
    assert girls["headline"] == "No. 7 seed G reached the 9A final"
    assert "lost to A 3–2" in girls["dek"]


def test_chalk_counts_top_four_seed_champions_and_lower_seed_wins():
    s = next(x for x in desk.d_chalk(_season()) if x["gender"] == "girls")
    assert s["headline"].startswith("2 of 2 girls' champions were top-4 seeds")
    # Ten girls' State duals (7 in 9A, 3 in 8A); the No. 7 seed won two of them.
    assert "Lower seeds won 20% of 10 State duals" == s["dek"]


def test_a_sweep_is_one_school_with_both_titles():
    s = desk.d_sweep(_season())
    assert [x["headline"] for x in s] == ["A won both 9A titles"]


def test_a_freshman_top_flight_champion_is_a_players_story():
    s = desk.d_freshman_champ(_season())
    assert len(s) == 1
    assert s[0]["headline"] == "Mia Ortiz won 9A No. 1 Singles as a freshman"
    assert s[0]["link"]["ep"] == "jhsaa_player"


def test_one_flight_needs_a_sample():
    s = desk.d_one_flight(_season())
    assert [x["headline"] for x in s] == ["G went 9–1 in one-flight duals"]


def test_undefeated_and_the_facts_strip():
    data = _season()
    u = desk.d_undefeated(data)
    assert [x["headline"] for x in u] == ["A went 20-0"]
    f = {x["label"]: x["n"] for x in desk.facts(data)}
    assert f["lowest seed to win a title"] == 1
    assert f["undefeated seasons"] == 1


def test_the_page_compiles_with_a_lead_and_a_bounded_feed():
    page = desk.compile_desk(_season(), feed=4)
    assert page["lead"] and page["lead"]["salience"] >= max(s["salience"] for s in page["feed"])
    assert len(page["feed"]) <= 4
    assert page["players"] and page["players"][0]["names"] == ["Ada Lin"]
    assert page["chart"]["champ_seeds"][0]["group"] == jh.GROUPS[0]


_BANNED = re.compile(r"\b(stunning|shock|remarkable|incredible|dominant|historic|"
                     r"thrilling|amazing|epic|massive|huge|dramatic)\b", re.I)


def test_headlines_lead_with_a_number_or_a_name_and_carry_no_adjectives():
    """The owner's register: no AI slop microcopy. A headline opens on a number
    ("No. 7", "2 of 2", "9–1") or a name, and never reaches for an adjective."""
    page = desk.compile_desk(_season())
    for s in page["all"]:
        h = s["headline"]
        assert not _BANNED.search(h), h
        assert not _BANNED.search(s["dek"]), s["dek"]
        assert "\n" not in h and len(h) < 90, h
        first = h.split()[0]
        assert first[0].isdigit() or first == "No." or first[0].isupper(), h


def test_every_detector_survives_an_empty_archive():
    data = {"year": 0, "season_year": 2027, "arcs": {"girls": _arc("girls", {}, {}, {})},
            "prev": {}, "one_flight": {"girls": {}}, "indiv": {"girls": {}}, "records": {}}
    page = desk.compile_desk(data)
    assert page["lead"] is None and page["feed"] == [] and page["players"] == []
