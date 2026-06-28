"""Career mode — the coached team's hand-set lineup actually reaches the court.

The engine (season.coach_lineup) normally derives the played ladder from player
STR + season-stable noise and IGNORES the set_lineup override for duals. Career
mode makes that override real, but ONLY for the human-coached program: every
other team — and a coached team whose coach never set a lineup — keeps the auto
ladder, so opting out / spectating never disadvantages anyone.
"""
import os
import tempfile

import pytest

os.environ.setdefault("TENNIS_DB_PATH", tempfile.mktemp(suffix="-career-lineup.db"))

from app import ncaa, overrides as ov, worldconfig as wc
from app.season import dual_between


@pytest.fixture(autouse=True)
def _clean():
    ov.clear_all(); ncaa.reset_caches(); wc.clear_user_program()
    yield
    ov.clear_all(); ncaa.reset_caches(); wc.clear_user_program()


def _two_d1():
    d1 = ncaa.load_division("D1", "men")
    a = max(d1.programs, key=lambda p: p.strength)
    b = next(p for p in d1.programs if p.school != a.school)
    return a, b


def _home_played(a, b):
    return dual_between(a, b, seed=4242, conf=True)["home_played"]


def test_pin_reaches_the_court_when_coached():
    a, b = _two_d1()
    base = [p.pid for p in ncaa.build_roster(a)]
    reverse = list(reversed(base))                 # weakest-first: clearly NOT the auto lineup
    ov.set_lineup(a.school, reverse); ncaa.reset_caches()
    wc.set_user_program(a.division, a.school, a.gender)

    played = _home_played(a, b)[:6]
    assert played == reverse[:6], "coached team must field its hand-set order"


def test_pin_ignored_without_a_coached_program():
    a, b = _two_d1()
    base = [p.pid for p in ncaa.build_roster(a)]
    reverse = list(reversed(base))
    ov.set_lineup(a.school, reverse); ncaa.reset_caches()
    # No coached program at all (spectator). The pin must NOT change who plays.
    played = set(_home_played(a, b)[:6])
    assert played != set(reverse[:6]), "spectator: pin is cosmetic, auto ladder still plays"


def test_pin_ignored_for_a_team_you_dont_coach():
    a, b = _two_d1()
    base = [p.pid for p in ncaa.build_roster(a)]
    reverse = list(reversed(base))
    ov.set_lineup(a.school, reverse); ncaa.reset_caches()
    # Coaching a DIFFERENT program (here: b) leaves a on the auto ladder.
    wc.set_user_program(b.division, b.school, b.gender)
    played = set(_home_played(a, b)[:6])
    assert played != set(reverse[:6]), "uncoached team is never disadvantaged by a stray pin"


def test_no_pin_no_change_for_coached_team():
    a, b = _two_d1()
    auto = _home_played(a, b)                       # auto ladder, no coaching
    wc.set_user_program(a.division, a.school, a.gender)   # coach it, but set NO lineup
    coached_no_pin = _home_played(a, b)
    assert coached_no_pin == auto, "coaching without touching the lineup == auto (no penalty)"
