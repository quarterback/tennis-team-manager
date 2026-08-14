import os
import sys
import tempfile

# Ensure the repo root is importable so `engine`, `app`, `generators` resolve.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ‼️ THE SUITE GETS ITS OWN DATABASE, AND THIS MUST HAPPEN BEFORE ANY `app`
# IMPORT. `app.dbpath.resolve_db_path()` reads $TENNIS_DB_PATH at import time and
# falls back to the repo's `./tennis.db` — which is a REAL SAVE. `app.world`'s
# `WORLD_DB` resolves to the same file (one file, separate tables), and the
# `played_season` fixture below calls `world.reset()`, whose first statement is
# `DELETE FROM world`.
#
# So running the test suite DELETED THE DEVELOPER'S WORLD, every time. It is not
# a hypothetical: it is why `test_season_awards_structure` failed. The reset
# wiped the world while leaving the played SEASON rows behind, so the season's
# ~4,600 player pids referred to people the roster generator no longer produces
# — `awards._eligible` resolved none of them, returned an empty list, and every
# All-American tier came back empty on a season that had been fully played.
#
# A test suite must never be able to touch a save. One temp file per run, torn
# down with the process; nothing else in the app needs to know.
os.environ.setdefault("TENNIS_DB_PATH",
                      os.path.join(tempfile.mkdtemp(prefix="ptc-tests-"), "tennis.db"))

# Run generation serially in the suite: parallel world-build / junior-circuit
# spawn worker processes (re-import cost, slower in CI) and are byte-identical to
# serial anyway. The parallel path has its own focused determinism test
# (test_parallel_gen.py), which clears this for the cases it exercises.
os.environ.setdefault("GEN_WORKERS", "1")

import pytest


@pytest.fixture
def played_season():
    """A fully-played D1-men season-year (regular season + conference tournaments
    + NCAA) so awards/honors have real results to compute from — since the
    season-mode unification, honors read actual results, not a pre-simulated
    baseline. Uses the standalone (no-world) season so the default seed resolves
    to it; only one division is played to keep the suite fast.

    ⚠️ This RESETS the world, which is why the whole suite is redirected to a
    throwaway database above. Do not run it against a real one."""
    import app.world as wd
    import app.seasonmode as sm
    from app.web.server import create_app
    create_app()                                   # bootstrap schemas
    if wd.exists():
        wd.reset()                                 # so the seed resolves to the base season
    sid = sm.get_or_create("D1", "men", seed=2026)
    guard = 0
    while sm.load_season(sid)["phase"] != "complete" and guard < 80:
        sm.advance(sid)
        guard += 1
    assert sm.load_season(sid)["phase"] == "complete", (
        "the season never concluded — every honors surface reads `_concluded()` "
        "and would render empty, which is indistinguishable from 'nobody qualified'")
    return
