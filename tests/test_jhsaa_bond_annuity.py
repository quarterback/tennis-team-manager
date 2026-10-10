"""Coach bond: ordinary performance, decade annuity and veteran developer security.

Every score is read from seasons completed BEFORE the one being archived.
The stock-era cutover also respects players already archived in grades 7/8.
"""
import json
import sqlite3

from app import jhsaa as jh
from app import jhsaa_coaches as jc
from app.world import BASE_YEAR


GRADES = jc.GRADES


def db():
    c = sqlite3.connect(":memory:")
    c.executescript(jc._SCHEMA)
    c.execute("CREATE TABLE world_jhsaa_season_row "
              "(world_id INTEGER, year INTEGER, gender TEXT, school TEXT, data TEXT, v INTEGER)")
    return c


def coach(c, cid, *, birth_year=1990, profile="practice", development=0.9):
    grades = {g: 0.5 for g in GRADES}
    grades["development"] = development
    p = jc.Coach(cid, cid, grades, profile=profile, birth_year=birth_year)
    jc.save_coach(c, 1, p)
    return p


def season(c, y, cid, *, ident="p", school="P", wins=17, losses=8,
           district=True, state=False, place=0, toc=False, eff=None):
    row = {"wins": wins, "losses": losses, "district_title": district,
           "place": 1 if district else 2,
           "unit_wins": (["P District", "Region IV"] if district else ["Region IV"]),
           "made_state": state, "state_place": place,
           "champion": state and place == 1, "toc_champion": toc}
    c.execute("INSERT INTO jhsaa_coach_history"
              " (world_id,year,ident,gender,slot,coach_id,school,classification,"
              " grp,wins,losses,ties,eff) VALUES (1,?,?,'girls','head',?,?,'4A',"
              " '4A',?,?,0,?)", (y, ident, cid, school, wins, losses,
                                 json.dumps(eff) if eff else None))
    c.execute("INSERT INTO world_jhsaa_season_row VALUES (1,?,'girls',?,?,1)",
              (y, school, json.dumps(row)))


def test_preexisting_middle_school_students_keep_the_old_development_model(monkeypatch):
    monkeypatch.setattr(jh, "stock_era", lambda: 2113)
    # Already appeared in 7th or 8th: the archived talent pin has no stock profile.
    assert not jh.stock_cohort_eligible(2113, {"stock": None})
    assert not jh.stock_cohort_eligible(2114, {"stock": None})
    # First appearance as freshman (or an early entrant not yet archived).
    assert jh.stock_cohort_eligible(2113, None)
    # Returning student originally generated under the new stock model.
    assert jh.stock_cohort_eligible(2113, {"stock": {"ethic": 0.65}})
    assert not jh.stock_cohort_eligible(2112, None)


def test_annuity_requires_ten_completed_consecutive_head_years_and_age_over_40():
    c = db()
    veteran = coach(c, "v", birth_year=1990)
    younger = coach(c, "y", birth_year=2000)
    for y in range(10):
        season(c, y, "v", ident="v", school="V", state=True, place=4)
        season(c, y, "y", ident="y", school="Y", state=True, place=4)
    before = jc.head_bond_details(c, 1, "v", 9, "girls", veteran, BASE_YEAR + 10)
    at = jc.head_bond_details(c, 1, "v", 10, "girls", veteran, BASE_YEAR + 11)
    too_young = jc.head_bond_details(c, 1, "y", 10, "girls", younger, BASE_YEAR + 11)
    assert before["annuity_active"] == 0
    assert at["annuity_active"] == 1 and at["tenure"] == 10
    assert too_young["annuity_active"] == 0
    # The ELEVENTH season earns the boost; the ten qualifying years never do.
    season(c, 10, "v", ident="v", school="V", state=True, place=4)
    following = jc.head_bond_details(c, 1, "v", 11, "girls", veteran, BASE_YEAR + 12)
    assert following["recent"][0]["annuity_active"] == 1
    assert following["recent"][0]["annuity_bonus"] > 0
    assert following["recent"][1]["annuity_active"] == 0
    c.close()


def test_annuity_is_school_specific_and_success_amplifier_not_free_points():
    c = db()
    v = coach(c, "v", birth_year=1980)
    for y in range(10):
        season(c, y, "v", ident="v", school="V", state=False)
    before_move = jc.head_bond_details(c, 1, "v", 10, "girls", v, BASE_YEAR + 11)
    assert before_move["annuity_active"] == 1
    season(c, 10, "v", ident="other", school="Other", wins=0, losses=20,
           district=False, state=False)
    after_move = jc.head_bond_details(c, 1, "v", 11, "girls", v, BASE_YEAR + 12)
    assert after_move["tenure"] == 1 and after_move["annuity_active"] == 0
    assert after_move["recent"][0]["annuity_active"] == 0
    c.close()


def test_veteran_development_coach_retains_bond_at_a_struggling_program():
    c = db()
    teacher = coach(c, "teacher", birth_year=1960, profile="practice")
    normal = coach(c, "normal", birth_year=1960, profile="singles", development=0.4)
    season(c, 0, "teacher", ident="d", school="D", wins=2, losses=20,
           district=False, eff={"bond": 1.09})
    season(c, 0, "normal", ident="n", school="N", wins=2, losses=20,
           district=False, eff={"bond": 1.09})
    v = jc.head_bond_details(c, 1, "teacher", 1, "girls", teacher, BASE_YEAR + 2)
    n = jc.head_bond_details(c, 1, "normal", 1, "girls", normal, BASE_YEAR + 2)
    assert v["veteran_protected"] == 1 and v["bond"] >= 1.09
    assert n["veteran_protected"] == 0 and n["bond"] < 1.09
    c.close()


def test_district_success_counts_even_when_the_teams_record_is_ordinary():
    c = db()
    a = coach(c, "a")
    b = coach(c, "b")
    for y in range(5):
        season(c, y, "a", ident="a", school="A", wins=10, losses=15,
               district=True)
        season(c, y, "b", ident="b", school="B", wins=10, losses=15,
               district=False)
    d = jc.head_bond_details(c, 1, "a", 5, "girls", a, BASE_YEAR + 6)
    no = jc.head_bond_details(c, 1, "b", 5, "girls", b, BASE_YEAR + 6)
    assert d["bond"] > no["bond"]
    assert d["recent"][0]["district_points"] == 12.0
    assert d["recent"][0]["road_units"] == 1
    c.close()


def test_bond_details_round_trip_into_effect_json():
    d = {"bond": 1.08, "tenure": 13, "annuity_active": 1,
         "recent": [{"annuity_bonus": 3.25, "total": 32.0}]}
    eff = jc.StaffEffect(lens=jh.CoachLens(), culture=1.0,
                         strategy="balanced", bond=d["bond"], bond_detail=d)
    back = jc._eff_from_json(jc._eff_to_json(eff))
    assert back.bond == 1.08 and back.bond_detail == d
