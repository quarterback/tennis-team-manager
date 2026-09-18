"""JHSAA reclassification (owner spec 2026-09, `app/jhsaa_reclass.py`).

The cycle is a fold over the archive plus a sort, so most of it is tested as pure
arithmetic on the real seed file with a hand-built score table; the archive fold
and the commit path get a small hand-archived world. The commit test runs on a
COPY of `schools.json` — the real seed file is never touched by the suite.
"""
import copy
import importlib.util
import json
import os
import shutil

import pytest

from app import jhsaa as jh
from app import jhsaa_districting as jd
from app import jhsaa_reclass as rc
from app import world as wd

BIG = ("Baptist", "Mater Dei", "Minnesota City")


def _scores(**over):
    """A score table: every live school at .500 with no points, plus overrides."""
    out = {}
    for r in jh._rows():
        if r.get("girls") or r.get("boys"):
            out[r["name"]] = {"pts": 0, "wins": 10, "losses": 10, "wr": 0.5, "seasons": 4,
                              "by_gender": {}}
    for name, (pts, wr) in over.items():
        out[name] = {"pts": pts, "wins": int(wr * 100), "losses": int((1 - wr) * 100),
                     "wr": wr, "seasons": 4, "by_gender": {}}
    return out


@pytest.fixture
def clean_archive():
    """The two archive-touching tests insert hand-built `world_jhsaa` rows; they
    must not outlive the test — `get_jhsaa` reads the FIRST row for a year, so a
    stray one shadows the season a later suite plays (it did: the TOC suite's
    export read an empty standings blob and found no coefficient rows)."""
    w = wd.get_or_create(wd.DEFAULT_SEED)
    yield w
    conn = wd._db()
    try:
        conn.executescript(rc._SCHEMA)
        conn.execute("DELETE FROM world_jhsaa WHERE world_id=?", (w["id"],))
        conn.execute("DELETE FROM world_jhsaa_reclass WHERE world_id=?", (w["id"],))
        conn.execute("DELETE FROM world_jhsaa_reclass_move WHERE world_id=?", (w["id"],))
        conn.commit()
    finally:
        conn.close()
    jh.reset_schools()


@pytest.fixture
def scored(monkeypatch):
    table = _scores(**{"Baptist": (26, 0.94), "Observatory": (0, 0.07),
                       "Banfield Day": (23, 0.92), "Pacific Friends": (13, 0.83),
                       "Gagarin": (23, 0.9)})
    monkeypatch.setattr(rc, "score", lambda wid, years: table)
    return table


def _build(edits=None, redraw=False):
    return rc.build_proposal(0, [0, 1, 2, 3], rc.config(), edits or {}, redraw=redraw)


def test_the_districting_data_matches_the_importer():
    """`data/jhsaa/districting.json` is the app's copy of `import_jhsaa`'s bank and
    constants (the app cannot read `scripts/`); the two must agree — the
    rivalry-tables idiom."""
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(os.path.dirname(__file__), "..", "scripts", "import_jhsaa.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    cfg = jd.districting_config()
    assert cfg.MAX_DISTRICT == m.MAX_DISTRICT and cfg.DISTRICT_TARGET == m.DISTRICT_TARGET
    assert cfg.LEAGUE_NAMES == [(n, a) for n, a in m.LEAGUE_NAMES]
    assert cfg.RIVALRIES == [tuple(p) for p in m.RIVALRIES]
    for n in (5, 10, 25, 85, 120):
        assert cfg.district_count(n) == m.district_count(n)


def test_bands_are_equal_and_every_pooled_school_is_placed(scored):
    p = _build()
    for key, classes in rc.POOLS.items():
        rows = [x for x in p["rows"] if x["pool"] == key]
        counts = {c: sum(1 for x in rows if x["proposed"] == c) for c in classes}
        assert max(counts.values()) - min(counts.values()) <= 1, (key, counts)
        assert all(x["proposed"] in classes for x in rows)
    # Every live school in a pooled class is in exactly one pool.
    pooled = [x["school"] for x in p["rows"]]
    assert len(pooled) == len(set(pooled))


def test_success_lifts_and_futility_sinks(scored):
    p = _build()
    row = {x["school"]: x for x in p["rows"]}
    assert rc._rank(row["Baptist"]["proposed"]) < rc._rank("7A")
    assert rc._rank(row["Observatory"]["proposed"]) > rc._rank("7A")
    assert rc._rank(row["Banfield Day"]["proposed"]) < rc._rank("1A")
    assert row["Baptist"]["adjustment"] > 0 > row["Observatory"]["adjustment"]


def test_no_guard_a_school_lands_where_it_ranks(scored):
    """Owner: no one-class-per-cycle guard. Baptist ranks a 9A seat and gets it."""
    p = _build()
    row = {x["school"]: x for x in p["rows"]}
    assert row["Baptist"]["proposed"] == "9A"


def test_the_big_programs_never_return_to_the_groups(scored):
    """The 2046 realignment moved them out; territory alone never moves them back."""
    p = _build()
    row = {x["school"]: x for x in p["rows"]}
    for name in BIG:
        assert row[name]["pool"] in ("A", "B"), name
    assert not any(g["school"] in BIG for g in p["geo"])


def test_only_approved_eastern_1a_areas_cross_into_the_groups(scored):
    p = _build()
    crossed = [g for g in p["geo"] if g["pool"] == "G"]
    assert crossed, "the initial reset repatriates the approved areas"
    approved = set(rc.config()["repatriate_areas"])
    assert all(g["from"] == "1A" and g["area"] in approved for g in crossed)
    # And no other A-ladder school reaches the Group pool.
    for x in p["rows"]:
        if x["pool"] == "G" and rc.pool_of(x["current"]) != "G":
            assert x["area"] in approved and x["current"] == "1A"


def test_an_owner_addition_is_placed_by_the_sort(scored):
    p = _build({"Pacific Friends": {"action": "add", "to": "A"}})
    pf = next(x for x in p["rows"] if x["school"] == "Pacific Friends")
    assert pf["pool"] == "A" and pf["edit"] == "add"
    assert pf["proposed"] in rc.POOL_A
    # Above where enrollment alone (814, the 5A band) would put it: the success
    # term is what lifts it. On the real 2083-86 scores it lands in 6A (the design
    # doc's worked example); against this flat table it ranks a class higher.
    assert rc._rank(pf["proposed"]) < rc._rank("5A")


def test_veto_and_redirect_pin_and_keep_the_bands_even(scored):
    p = _build({"Baptist": {"action": "veto"}, "Observatory": {"action": "redirect", "to": "8A"}})
    row = {x["school"]: x for x in p["rows"]}
    assert row["Baptist"]["proposed"] == "7A" and row["Baptist"]["pinned"] == "7A"
    assert row["Observatory"]["proposed"] == "8A"
    rows = [x for x in p["rows"] if x["pool"] == "A"]
    counts = {c: sum(1 for x in rows if x["proposed"] == c) for c in rc.POOL_A}
    assert max(counts.values()) - min(counts.values()) <= 1, counts


def test_the_proposal_is_deterministic(scored):
    a, b = _build(), _build()
    a.pop("built_at"), b.pop("built_at")
    assert a == b


def test_score_folds_both_genders_into_one_school(monkeypatch, clean_archive):
    """A hand-archived season: points and record are summed across the two programs,
    a lone sponsor is scored on its one, and the finish points follow place."""
    w = clean_archive
    conn = wd._db()
    try:
        conn.execute("DELETE FROM world_jhsaa WHERE world_id=?", (w["id"],))

        def arc(rec_a, rec_b, champ):
            field = ["Alpha", "Beta", "Gamma", "Delta"]
            rounds = [[{"home": "Alpha", "away": "Delta", "winner": "Alpha"},
                       {"home": "Beta", "away": "Gamma", "winner": "Beta"}],
                      [{"home": "Alpha", "away": "Beta", "winner": champ}]]
            return json.dumps({"season_year": 2040,
                               "standings": {"9A": {"League": [
                                   {"school": "Alpha", "record": rec_a},
                                   {"school": "Beta", "record": rec_b},
                                   {"school": "Gamma", "record": "5-15"},
                                   {"school": "Delta", "record": "4-16"}]}},
                               "brackets": {"9A": {"field": field, "champion": champ,
                                                   "rounds": rounds}}})
        conn.execute("INSERT INTO world_jhsaa (world_id, year, gender, data) VALUES (?,?,?,?)",
                     (w["id"], 0, "girls", arc("18-2", "12-8", "Alpha")))
        conn.execute("INSERT INTO world_jhsaa (world_id, year, gender, data) VALUES (?,?,?,?)",
                     (w["id"], 0, "boys", arc("10-10", "16-4", "Beta")))
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setattr(wd, "_relabel", lambda obj, *a, **k: obj)
    s = rc.score(w["id"], [0])
    assert s["Alpha"]["pts"] == 4 + 3 and s["Alpha"]["wins"] == 28 and s["Alpha"]["losses"] == 12
    assert s["Beta"]["pts"] == 3 + 4
    assert s["Gamma"]["pts"] == 2 * 2 and s["Delta"]["pts"] == 2 * 2   # semifinalists both
    assert s["Alpha"]["wr"] == pytest.approx(28 / 40)
    assert rc.cycle_years(w["id"], 4) == [0]


def test_commit_rewrites_the_seed_file_redraws_leagues_and_records_moves(scored, monkeypatch, tmp_path, clean_archive):
    """The commit path on a COPY of the seed file: classes move (classification and
    group together), moved play-up flags are popped, the touched classes' leagues are
    redrawn, every move is recorded, and the archive is untouched."""
    copy_path = tmp_path / "schools.json"
    shutil.copy(jh._DATA, copy_path)
    monkeypatch.setattr(jh, "_DATA", str(copy_path))
    jh.reset_schools()
    w = clean_archive
    conn = wd._db()
    try:
        conn.execute("DELETE FROM world_jhsaa WHERE world_id=?", (w["id"],))
        conn.execute("INSERT INTO world_jhsaa (world_id, year, gender, data) VALUES (?,?,?,?)",
                     (w["id"], 0, "girls", json.dumps({"standings": {}, "brackets": {}})))
        conn.commit()
        before_arc = conn.execute("SELECT data FROM world_jhsaa WHERE world_id=?",
                                  (w["id"],)).fetchall()[0]["data"]
    finally:
        conn.close()
    cur = rc.open_proposal(w, force=True)
    assert cur and cur["data"]["moves"]
    moves = {x["school"]: x for x in cur["data"]["moves"]}
    res = rc.commit(w)
    assert res["ok"] and res["moves"] == len(moves)
    doc = json.load(open(copy_path))
    rows = {r["name"]: r for r in doc["schools"]}
    for name, x in moves.items():
        assert rows[name]["classification"] == rows[name]["group"] == x["proposed"], name
        assert "play_up" not in rows[name]
    # The leagues of a touched class were redrawn and stay legal.
    from collections import Counter
    for cls in res["touched"]:
        sizes = Counter(r["girls_district"] for r in doc["schools"]
                        if r["group"] == cls and (r.get("girls") or r.get("boys")))
        assert max(sizes.values()) <= jd.districting_config().MAX_DISTRICT
        assert all(r["girls_district"] == r["boys_district"] for r in doc["schools"]
                   if r["group"] == cls)
    # Recorded, readable from the program side and the history side.
    baptist = rc.moves_for(w["id"], "Baptist")
    assert baptist and baptist[-1]["to_cls"] == "9A"
    hist = rc.history(w["id"])
    assert hist and len(hist[0]["moves"]) == len(moves)
    assert rc.pending(w["id"]) is None and rc.last_cycle_year(w["id"]) == w["year"]
    # The archive is byte-identical.
    conn = wd._db()
    try:
        after_arc = conn.execute("SELECT data FROM world_jhsaa WHERE world_id=?",
                                 (w["id"],)).fetchall()[0]["data"]
    finally:
        conn.close()
    assert after_arc == before_arc
    jh.reset_schools()


def test_due_counts_seasons_since_the_last_commit(monkeypatch):
    w = {"id": 4242, "year": 9}
    monkeypatch.setattr(rc, "cycle_years", lambda wid, n: [2, 3, 4, 5, 6, 7, 8][-n:])
    monkeypatch.setattr(rc, "last_cycle_year", lambda wid: None)
    assert rc.due(w)
    monkeypatch.setattr(rc, "last_cycle_year", lambda wid: 6)
    assert not rc.due(w)
    monkeypatch.setattr(rc, "last_cycle_year", lambda wid: 4)
    assert rc.due(w)
