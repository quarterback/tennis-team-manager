"""The roster-drift diagnostic's season selection (scripts/diagnose_jhsaa_roster_drift.py).

The first field run of the diagnostic bailed with "no archived lines for the
current season" — the save's current world year had not archived yet, so the
comparison the script exists to make never ran. `newest_played_season` walks
back from the newest archive to the newest season the school actually PLAYED,
and the roster is regenerated at THAT season's calendar year: comparing a
2073 archive against a 2074 roster would misread ordinary graduation as drift.
"""
import importlib.util
import json
import os
import sqlite3

import pytest

from app import world as wd

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _diag():
    spec = importlib.util.spec_from_file_location(
        "diagnose_jhsaa_roster_drift",
        os.path.join(_REPO, "scripts", "diagnose_jhsaa_roster_drift.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def lab_world(tmp_path):
    """A JHSAA-only world on a database of its own — the test_jhsaa_toc idiom,
    without a season: the duals are hand-archived, the way the repeat-rolls
    tests do, because one real season cannot exercise 'the current year has
    not archived yet'."""
    db = str(tmp_path / "drift.db")
    real_db, real_ready = wd.WORLD_DB, wd._schema_ready_for
    wd.WORLD_DB, wd._schema_ready_for = db, None
    try:
        yield wd.get_or_create(wd.DEFAULT_SEED, skip_college=True)
    finally:
        wd.WORLD_DB, wd._schema_ready_for = real_db, real_ready


def _archive_dual(w, year_ix, school, names, level="v"):
    lines = [{"slot": "S1", "home": [n], "away": ["Opponent Player"],
              "home_won": 1, "score": "6-0, 6-0"} for n in names]
    conn = sqlite3.connect(wd.WORLD_DB)
    conn.execute(
        "INSERT INTO world_jhsaa_dual (world_id, year, gender, school, opp,"
        " home, phase, pf, pa, won, district, lines, level)"
        " VALUES (?,?,?,?,?,1,'regular',5,2,1,1,?,?)",
        (w["id"], year_ix, "boys", school, "Rival", json.dumps(lines), level))
    conn.commit()
    conn.close()


def test_walks_back_to_the_newest_season_the_school_played(lab_world):
    """Year 1 is the newest archive but carries nothing for this school (its
    season has not archived yet); the diagnostic must compare year 0 — and the
    roster year it implies is that OLDER season's calendar year, not the
    current one."""
    diag = _diag()
    _archive_dual(lab_world, 0, "Walkback", ["Alice Player", "Betty Player"])
    _archive_dual(lab_world, 1, "Somebody Else", ["Carol Player"])
    ix, names = diag.newest_played_season(lab_world["id"], "boys", "Walkback", 1)
    assert ix == 0
    assert names == {"Alice Player", "Betty Player"}
    assert wd.BASE_YEAR + ix + 1 == wd.BASE_YEAR + 1      # the 2027-not-2028 year


def test_prefers_the_current_season_when_it_has_lines(lab_world):
    diag = _diag()
    _archive_dual(lab_world, 0, "Walkback", ["Alice Player"])
    _archive_dual(lab_world, 1, "Walkback", ["Zoe Player"])
    ix, names = diag.newest_played_season(lab_world["id"], "boys", "Walkback", 1)
    assert ix == 1 and names == {"Zoe Player"}


def test_jv_lines_never_stand_in_for_a_varsity_season(lab_world):
    """The research-export lesson, applied here: every reader of the shared dual
    table filters on level. A season whose only lines are JV must not be
    'played' — matching a varsity roster against JV names is a guaranteed miss
    that would misread as drift."""
    diag = _diag()
    _archive_dual(lab_world, 0, "Walkback", ["Alice Player"])
    _archive_dual(lab_world, 1, "Walkback", ["Jay Vee"], level="jv")
    ix, names = diag.newest_played_season(lab_world["id"], "boys", "Walkback", 1)
    assert ix == 0 and names == {"Alice Player"}


def test_no_played_season_reports_none(lab_world):
    diag = _diag()
    ix, names = diag.newest_played_season(lab_world["id"], "boys", "Ghost", 1)
    assert ix is None and names == set()
