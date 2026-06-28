"""Career mode — prestige-gated job offers (the coaching carousel).

Opt-in upward mobility only: offers open once the season is complete and are always
at least as prestigious as your current program. No firing, no forced moves.
"""
from app import worldconfig as wc, ncaa
from app.web.state import job_offers


def test_offers_none_in_spectator_mode():
    wc.clear_user_program()
    assert job_offers() is None


def test_offers_locked_until_complete():
    # A fresh program with no completed season: offers are not yet available.
    school = ncaa.load_division("D2", "men").programs[0].school
    wc.set_user_program("D2", school, "men")
    try:
        off = job_offers()
        assert off is not None and off["available"] is False
    finally:
        wc.clear_user_program()


def test_career_store_roundtrip():
    wc.set("coach_career", "[]")
    wc.push_coach_seat({"school": "TestU", "division": "D1", "year": 2026})
    assert wc.get_coach_career()[-1]["school"] == "TestU"
    wc.set("coach_career", "[]")


def test_offers_are_upward_after_complete(played_season):
    d1 = ncaa.load_division("D1", "men")
    low = min(d1.programs, key=lambda p: p.prestige)     # lots of room above
    wc.set_user_program("D1", low.school, "men")
    try:
        off = job_offers()
        assert off and off["available"]
        for o in off["offers"]:
            assert o["school"] != low.school
            assert o["prestige"] >= off["prestige"]      # never a worse job
    finally:
        wc.clear_user_program()
