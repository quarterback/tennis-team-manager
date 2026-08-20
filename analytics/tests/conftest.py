"""Sidecar test bootstrap.

The analytics package lives OUTSIDE the game's package tree (it's a sidecar,
imported by path from build.py), so put both the repo root (for `app.*` —
only the export builder is used, fed an in-memory season) and the analytics
dir (for `ptc_analytics`) on sys.path. TENNIS_DB_PATH is pointed at a
throwaway BEFORE any app import for the same hermeticity reason as the root
conftest — these tests never touch a database, but an app import must never
resolve to the repo's ./tennis.db either."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("TENNIS_DB_PATH",
                      os.path.join(tempfile.mkdtemp(prefix="ptc-sidecar-test-"), "tennis.db"))

_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parents[2]))   # repo root -> app.*
sys.path.insert(0, str(_here.parents[1]))   # analytics/ -> ptc_analytics
