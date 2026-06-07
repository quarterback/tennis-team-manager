"""Editor / roster-override behavior: moves relocate a player across programs and
divisions, lineup pins reorder the ladder, and clearing restores the defaults."""
import os
import tempfile

import pytest

# Point the override store at a throwaway DB before importing anything that reads it.
os.environ.setdefault("TENNIS_DB_PATH", tempfile.mktemp(suffix="-overrides.db"))

from app import ncaa, overrides as ov


@pytest.fixture(autouse=True)
def _clean():
    ov.clear_all(); ncaa.reset_caches()
    yield
    ov.clear_all(); ncaa.reset_caches()


def _strong_d1():
    d1 = ncaa.load_division("D1", "men")
    return max(d1.programs, key=lambda p: p.strength)


def test_no_overrides_equals_base():
    prog = _strong_d1()
    assert [p.pid for p in ncaa.build_roster(prog)] == [p.pid for p in ncaa._base_roster(prog)]


def test_move_relocates_player_across_divisions():
    src = _strong_d1()
    dest = ncaa.load_division("D3", "men").programs[0]
    star = ncaa.build_roster(src)[0]

    ov.set_move(star.pid, dest.school); ncaa.reset_caches()
    dest_roster = ncaa.build_roster(dest)
    assert star.pid in {p.pid for p in dest_roster}            # arrived
    assert dest_roster[0].pid == star.pid                      # and tops the ladder
    assert star.pid not in {p.pid for p in ncaa.build_roster(src)}   # left the source


def test_move_does_not_bleed_across_genders():
    src = _strong_d1()
    star = ncaa.build_roster(src)[0]
    # Oregon exists in both men's and women's D1; a moved male player must not
    # appear on the women's roster.
    ov.set_move(star.pid, "Oregon"); ncaa.reset_caches()
    women = ncaa.load_division("D1", "women").by_school("Oregon")
    assert star.pid not in {p.pid for p in ncaa.build_roster(women)}


def test_lineup_pin_reorders_ladder():
    prog = _strong_d1()
    base = [p.pid for p in ncaa.build_roster(prog)]
    pinned = [base[5]] + base[:5] + base[6:]
    ov.set_lineup(prog.school, pinned); ncaa.reset_caches()
    assert [p.pid for p in ncaa.build_roster(prog)][0] == base[5]


def test_clear_restores_default():
    prog = _strong_d1()
    base = [p.pid for p in ncaa.build_roster(prog)]
    ov.set_move(base[0], "Amherst"); ncaa.reset_caches()
    assert [p.pid for p in ncaa.build_roster(prog)] != base
    ov.clear_all(); ncaa.reset_caches()
    assert [p.pid for p in ncaa.build_roster(prog)] == base
