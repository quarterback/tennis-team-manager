"""Career mode — end-of-season report card.

Read-only: it mirrors the prestige-momentum expectation-vs-result math (preseason
prestige rank vs Power-Index rank + postseason pedigree) without writing momentum.
"""
from app import worldconfig as wc, ncaa
from app.web.state import my_season_report


def test_report_unavailable_in_spectator_mode():
    wc.clear_user_program()
    assert my_season_report() is None


def test_season_report_after_complete(played_season):
    school = ncaa.load_division("D1", "men").programs[0].school
    wc.set_user_program("D1", school, "men")
    try:
        rep = my_season_report()
        assert rep and rep["started"] and rep["complete"]
        assert rep["verdict"] in ("overachieved", "met", "underachieved")
        assert 1 <= rep["pi_rank"] <= rep["field"]
        assert 1 <= rep["pres_rank"] <= rep["field_pres"]
        assert rep["wins"] + rep["losses"] > 0
        # signature wins are all against higher-ranked teams
        assert all(d["rank"] < rep["pi_rank"] for d in rep["notable"])
    finally:
        wc.clear_user_program()
