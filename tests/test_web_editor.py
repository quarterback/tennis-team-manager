"""Editor batch move: several player moves land in ONE POST → one override write
per player but a SINGLE cache invalidation, instead of the old per-row form that
paid a whole-world rebuild per player moved."""
import os
import tempfile

# Point the stores at a throwaway DB before importing anything that reads them.
os.environ.setdefault("TENNIS_DB_PATH", tempfile.mktemp(suffix="-editorweb.db"))

import pytest

from app import ncaa, overrides as ov
from app.web.server import create_app


@pytest.fixture(autouse=True)
def _clean():
    ov.clear_all(); ncaa.reset_caches()
    yield
    ov.clear_all(); ncaa.reset_caches()


def test_editor_move_batch_applies_all_and_skips_unchanged():
    d1 = ncaa.load_division("D1", "men")
    schools = sorted(p.school for p in d1.programs)
    src, dest = schools[0], schools[1]
    roster = ncaa.build_roster(d1.by_school(src))
    p1, p2, p3 = roster[0].pid, roster[1].pid, roster[2].pid

    c = create_app().test_client()
    r = c.post("/editor/move_batch", data={"u": "D1-men", "school": src,
                                           f"dest_{p1}": dest, f"dest_{p2}": dest,
                                           f"dest_{p3}": src})        # unchanged → ignored
    assert r.status_code == 302
    moves = ov.get_moves()
    assert moves.get(p1) == dest and moves.get(p2) == dest
    assert p3 not in moves                       # a row left on its own school is a no-op
    # both movers actually arrive on the destination roster
    pids = {q.pid for q in ncaa.build_roster(d1.by_school(dest))}
    assert p1 in pids and p2 in pids
    # and left the source
    src_pids = {q.pid for q in ncaa.build_roster(d1.by_school(src))}
    assert p1 not in src_pids and p2 not in src_pids and p3 in src_pids


def test_editor_move_batch_empty_is_a_noop():
    c = create_app().test_client()
    r = c.post("/editor/move_batch", data={"u": "D1-men", "school": "Nowhere State"})
    assert r.status_code == 302
    assert ov.get_moves() == {}


def test_editor_single_move_still_works():
    d1 = ncaa.load_division("D1", "men")
    schools = sorted(p.school for p in d1.programs)
    src, dest = schools[0], schools[1]
    pid = ncaa.build_roster(d1.by_school(src))[0].pid
    c = create_app().test_client()
    r = c.post("/editor/move", data={"u": "D1-men", "school": src,
                                     "pid": pid, "dest": dest})
    assert r.status_code == 302
    assert ov.get_moves().get(pid) == dest


def test_editor_move_batch_rejects_cross_gender_dest():
    """A women's player must never move onto a men's roster. The MOVE picker is
    gender-filtered, but a hand-crafted POST naming a men's program is dropped."""
    dw = ncaa.load_division("D1", "women")
    dm = ncaa.load_division("D1", "men")
    src = sorted(p.school for p in dw.programs)[0]
    mens_dest = sorted(p.school for p in dm.programs)[0]
    pid = ncaa.build_roster(dw.by_school(src))[0].pid

    c = create_app().test_client()
    r = c.post("/editor/move_batch", data={"u": "D1-women", "school": src,
                                           f"dest_{pid}": mens_dest})
    assert r.status_code == 302
    assert pid not in ov.get_moves()             # cross-gender move silently dropped


def test_editor_move_batch_allows_cross_division_same_gender():
    """Cross-DIVISION moves within a gender stay allowed (the misallocation
    reshuffle depends on them) — a women's player can move D1→D2 women."""
    d1 = ncaa.load_division("D1", "women")
    d2 = ncaa.load_division("D2", "women")
    src = sorted(p.school for p in d1.programs)[0]
    dest = sorted(p.school for p in d2.programs)[0]
    pid = ncaa.build_roster(d1.by_school(src))[0].pid

    c = create_app().test_client()
    r = c.post("/editor/move_batch", data={"u": "D1-women", "school": src,
                                           f"dest_{pid}": dest})
    assert r.status_code == 302
    assert ov.get_moves().get(pid) == dest
