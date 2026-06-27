import os
import sys

# Ensure the repo root is importable so `engine`, `app`, `generators` resolve.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    to it; only one division is played to keep the suite fast."""
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
    return
