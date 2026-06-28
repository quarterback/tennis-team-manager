"""Career mode — preseason non-conference scheduling.

A coach may re-opponent their own UNPLAYED non-conference duals. The slate is one
shared row per dual, so a swap stays symmetric automatically: the chosen team gains
the dual, the dropped team loses it. Conference duals and played duals are untouchable.
"""
import os
import tempfile

import pytest

os.environ.setdefault("TENNIS_DB_PATH", tempfile.mktemp(suffix="-career-sched.db"))

from app import ncaa, seasonmode as sm


@pytest.fixture
def sid():
    return sm.get_or_create("D1", "men", seed=2026)


def _a_school_with_nonconf(sid):
    for p in ncaa.load_division("D1", "men").programs:
        if sm.nonconf_duals(sid, p.school):
            return p.school
    raise AssertionError("no program had a non-conf dual")


def test_nonconf_and_eligibility(sid):
    school = _a_school_with_nonconf(sid)
    booked = {d["opponent"] for d in sm.nonconf_duals(sid, school)}
    elig = sm.eligible_nonconf_opponents(sid, "D1", "men", school)
    assert school not in elig
    assert booked.isdisjoint(elig), "eligible pool must exclude teams already on the slate"


def test_swap_is_symmetric(sid):
    school = _a_school_with_nonconf(sid)
    duals = sm.nonconf_duals(sid, school)
    target, new_opp = duals[0], sm.eligible_nonconf_opponents(sid, "D1", "men", school)[0]
    dropped = target["opponent"]

    assert sm.swap_nonconf_opponent(sid, target["id"], school, new_opp, "D1", "men")

    mine = {d["id"]: d for d in sm.nonconf_duals(sid, school)}
    assert mine[target["id"]]["opponent"] == new_opp                 # I now play the new team
    assert dropped not in {d["opponent"] for d in mine.values()}     # ...not the dropped one (this dual)
    theirs = {(r["home"], r["away"]) for r in sm.team_schedule(sid, new_opp)}
    assert any(school in pair for pair in theirs), "dual must appear on the new opponent's slate"


def test_cannot_book_a_team_already_played_or_on_slate(sid):
    school = _a_school_with_nonconf(sid)
    already = sm.nonconf_duals(sid, school)[0]["opponent"]
    assert not sm.swap_nonconf_opponent(sid, sm.nonconf_duals(sid, school)[0]["id"],
                                        school, already, "D1", "men")


def test_conference_dual_is_not_editable(sid):
    # find a conference dual for some school and confirm it can't be swapped
    school = next(p.school for p in ncaa.load_division("D1", "men").programs)
    full = sm.team_schedule(sid, school)
    conf = next((d for d in full if d["is_conf"] and d["round"] == "REG"), None)
    if conf is None:
        pytest.skip("no conference dual to test")
    elig = sm.eligible_nonconf_opponents(sid, "D1", "men", school)
    assert elig and not sm.swap_nonconf_opponent(sid, conf["id"], school, elig[0], "D1", "men")


def test_home_away_toggle(sid):
    school = _a_school_with_nonconf(sid)
    d = sm.nonconf_duals(sid, school)[0]
    assert sm.set_nonconf_home(sid, d["id"], school, not d["home"])
    flipped = {x["id"]: x for x in sm.nonconf_duals(sid, school)}[d["id"]]
    assert flipped["home"] != d["home"]
