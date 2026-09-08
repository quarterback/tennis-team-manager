"""The per-dual box score is stored COMPRESSED, and reads BOTH encodings.

‼️ THIS ONE COLUMN IS MOST OF THE DATABASE. Measured on the owner's real
50-season lab save: 2,976 MB of `world_jhsaa_dual.lines` inside a 4,402 MB
file — 68% of everything the game has ever remembered, growing ~69 MB a season
(42,851 duals across both genders, varsity and JV). It is the most compressible
shape in the app, because the slot names, the key names and the player names
repeat on every court of every dual: zlib gets 2.3x on real data.

The encoding is SNIFFED, never migrated. Rows written before this are plain
JSON `str`; rows written after are `bytes`. SQLite's dynamic typing keeps both
in the same TEXT-declared column and the storage CLASS is the discriminator, so
a long save keeps reading with no migration, no version column and no flag to
drift — the `_relabel` idiom: derive on READ.

‼️ A MISSED READER DOES NOT FAIL LOUDLY. `json.loads` on compressed bytes
raises, but two call sites deliberately swallow ValueError to survive a
malformed row, so a reader that forgot `unpack_lines` reads as "this season has
no box scores" — every record, award résumé and court total silently zeroed for
those rows. That is what the reader sweep below is for.
"""
from __future__ import annotations

import json
import pathlib
import re
import sqlite3
import sys

from app import world as wd


def _blob():
    """A box score shaped exactly as `jhsaa.play_dual` builds one."""
    return [
        {"slot": "S1", "home": ["Jonathan Thomas"], "away": ["Liam Lee"],
         "score": "6-1, 6-4", "home_won": True},
        {"slot": "D1", "home": ["Urijah Cullen", "Cole Whitfield"],
         "away": ["Milo Vance", "Rafael Ortiz"],
         "score": "7-6, 3-6, 2-6", "home_won": False},
    ]


def test_a_box_score_survives_the_round_trip():
    assert wd.unpack_lines(wd.pack_lines(_blob())) == _blob()


def test_it_is_actually_smaller_than_the_json_it_replaces():
    blob = _blob() * 9                      # a real dual is 5-14 flights
    assert len(wd.pack_lines(blob)) < len(json.dumps(blob).encode())


def test_rows_written_before_this_change_still_read(tmp_path):
    """‼️ THE WHOLE POINT. A 50-season archive is plain JSON text; nothing is
    migrated, so a legacy row and a new row must read identically out of the
    same column."""
    db = tmp_path / "x.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE d (lines TEXT DEFAULT '[]')")
    conn.execute("INSERT INTO d VALUES (?)", (json.dumps(_blob()),))   # legacy
    conn.execute("INSERT INTO d VALUES (?)", (wd.pack_lines(_blob()),))  # new
    conn.commit()
    rows = [wd.unpack_lines(r[0]) for r in conn.execute("SELECT lines FROM d")]
    conn.close()
    assert rows == [_blob(), _blob()]


def test_empty_and_missing_box_scores_read_as_no_lines():
    """A JV row before `lines` existed, and a NULL column, are both 'no lines' —
    never an exception, and never a phantom court."""
    for empty in (None, "", "[]", wd.pack_lines([])):
        assert wd.unpack_lines(empty) == []


def test_every_reader_of_the_column_decodes_it(tmp_path):
    """‼️ THE SWEEP. Any `json.loads` still pointed at this column is a reader
    that will read a compressed row as no box score at all — silently. Catch a
    ninth reader at the source, not in a season's worth of zeroed records.

    ‼️ `scripts/` COUNTS. A maintenance script reads the same column through the
    same rules and is the one place nothing renders to show it broke — the
    sweep started at `app/` alone and `scripts/fix_name_era.py` came through it
    clean while raising on every compressed row it touched."""
    repo = pathlib.Path(__file__).resolve().parents[1]
    bad = []
    for root in (repo / "app", repo / "scripts"):
        for path in root.rglob("*.py"):
            for n, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                if "json.loads" not in line or "lines" not in line:
                    continue
                # `lines_json` is the COLLEGE duals table (seasonmode/gtt) — a
                # different column, deliberately untouched by this change.
                if "lines_json" in line or path.name.startswith("gtt_"):
                    continue
                if line.lstrip().startswith("#"):
                    continue
                bad.append(f"{path.relative_to(repo)}:{n}: {line.strip()}")
    assert not bad, (
        "these still json.loads the JHSAA box-score column — use "
        "world.unpack_lines:\n  " + "\n  ".join(bad))


def test_the_archive_writes_through_the_packer():
    """The one INSERT must encode, or nothing above matters."""
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "app" / "world.py").read_text()
    ins = src[src.index("INSERT INTO world_jhsaa_dual"):]
    build = src[:src.index("INSERT INTO world_jhsaa_dual")]
    # both row builders (varsity and JV) sit just above the INSERT
    tail = build[-4000:]
    assert tail.count("_archive_lines(d)") == 2, (
        "the varsity and JV row builders must both go through _archive_lines")
    assert 'json.dumps(d.get("lines"' not in tail, "a raw json.dumps write survived"
    assert ins  # the statement still exists


def test_the_away_row_stores_no_box_score():
    """‼️ THE 2x. A dual is two rows and both used to carry the identical blob —
    half of a 2,976 MB column, pure redundancy. Only the home side stores it."""
    from app.world import _archive_lines
    blob = {"lines": _blob()}
    assert _archive_lines({**blob, "home": 1}) is not None
    assert _archive_lines({**blob, "home": 0}) is None
    assert wd.unpack_lines(_archive_lines({**blob, "home": 1})) == _blob()


def test_the_two_rows_of_a_dual_share_one_identity():
    """The away row resolves its box score through `jh_match_key`, so the key
    MUST come out identical from either side or the lines attach to the wrong
    dual — silently, with a plausible box score."""
    home = {"home": 1, "school": "Abbey Prep", "opp": "Scheelite County",
            "level": "v", "phase": "regular", "district": 1}
    away = {"home": 0, "school": "Scheelite County", "opp": "Abbey Prep",
            "level": "v", "phase": "regular", "district": 1}
    assert wd.jh_match_key(home) == wd.jh_match_key(away)
    # and the return meeting (venue reversed) stays a DIFFERENT dual
    ret = {**home, "school": "Scheelite County", "opp": "Abbey Prep"}
    assert wd.jh_match_key(ret) != wd.jh_match_key(home)


def test_no_loop_decodes_the_column_as_one_key_among_several():
    """‼️ THE MISS THAT ACTUALLY HAPPENED, and the exact shape of it.
    `_schedule_rows` decoded through a loop —
    `for k in ("lines", "played", "tiebreak"): d[k] = json.loads(...)` — so the
    word `lines` never appeared on the `json.loads` line and a same-line sweep
    read clean. It would have blanked every schedule box score, silently.

    Flags a `json.loads` driven by a loop variable whose tuple includes the
    box-score column. Deliberately narrow: a window-based heuristic flagged the
    CORRECT `("played", "tiebreak")` loop next door, and a check that cries wolf
    gets deleted by the next person."""
    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    loop = re.compile(r"for\s+(\w+)\s+in\s+\(([^)]*)\)")
    bad = []
    for path in root.rglob("*.py"):
        if path.name.startswith("gtt_"):
            continue
        src = path.read_text(errors="ignore").splitlines()
        for n, line in enumerate(src):
            if "json.loads" not in line or "lines_json" in line:
                continue
            for up in range(max(0, n - 6), n):
                m = loop.search(src[up])
                if m and '"lines"' in m.group(2) and m.group(1) in line:
                    bad.append(f"{path.relative_to(root)}:{n + 1}: {line.strip()}")
                    break
    assert not bad, (
        "a loop decodes the box-score column with json.loads — it must go "
        "through unpack_lines:\n  " + "\n  ".join(bad))


# --- the one-time migration of an existing archive ---------------------------

def _legacy_db(path, duals):
    """An archive in the PRE-migration layout: the identical blob on both rows."""
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE world_jhsaa_dual (world_id INTEGER, year INTEGER,
        gender TEXT, school TEXT, opp TEXT, home INTEGER, phase TEXT, pf REAL,
        pa REAL, won INTEGER, district INTEGER, lines TEXT DEFAULT '[]',
        level TEXT DEFAULT 'v', tied INTEGER DEFAULT 0, shape TEXT DEFAULT '',
        played TEXT DEFAULT '[]', tiebreak TEXT DEFAULT '[]')""")
    for gender, home, away, blob in duals:
        for side, (a, b) in ((1, (home, away)), (0, (away, home))):
            conn.execute(
                "INSERT INTO world_jhsaa_dual (world_id,year,gender,school,opp,home,"
                "phase,pf,pa,won,district,lines,level)"
                " VALUES (1,49,?,?,?,?,'regular',0,0,0,1,?,'v')",
                (gender, a, b, side, json.dumps(blob)))
    conn.commit()
    conn.close()


def _resolve(path):
    """Every dual's box score, resolved the way the app does — per (world, year,
    gender), which is the scope `jh_match_key` is unique within."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    out = {}
    for k in conn.execute("SELECT DISTINCT world_id, year, gender"
                          " FROM world_jhsaa_dual").fetchall():
        rows = conn.execute(
            "SELECT rowid AS id, school, opp, home, phase, district, level, lines"
            " FROM world_jhsaa_dual WHERE world_id=? AND year=? AND gender=?",
            (k["world_id"], k["year"], k["gender"])).fetchall()
        got = {r["id"]: wd.unpack_lines(r["lines"]) for r in rows}
        hmap = {wd.jh_match_key(dict(r)): r["id"] for r in rows if r["home"]}
        for r in rows:
            out[r["id"]] = got[r["id"]] or got.get(
                hmap.get(wd.jh_match_key(dict(r))), [])
    conn.close()
    return out


def _migrate(path, *args):
    import subprocess
    script = (pathlib.Path(__file__).resolve().parents[1]
              / "scripts" / "migrate_jhsaa_boxscores.py")
    return subprocess.run([sys.executable, str(script), "--db", str(path), *args],
                          text=True, capture_output=True, check=True)


def test_the_migration_keeps_every_box_score(tmp_path):
    """Rewriting a real archive must not move a single flight."""
    db = tmp_path / "a.db"
    _legacy_db(db, [("boys", "Abbey Prep", "Scheelite County", _blob()),
                    ("boys", "Foxboro", "Eastmont", _blob() * 3),
                    ("girls", "Abbey Prep", "Scheelite County", _blob() * 2)])
    before = _resolve(db)
    _migrate(db, "--apply")
    assert _resolve(db) == before


def test_the_default_run_writes_nothing(tmp_path):
    """It reports unless told to --apply: a 4 GB save is not a dry run."""
    db = tmp_path / "a.db"
    _legacy_db(db, [("boys", "Abbey Prep", "Scheelite County", _blob())])
    raw = sqlite3.connect(db).execute(
        "SELECT lines FROM world_jhsaa_dual ORDER BY rowid").fetchall()
    out = _migrate(db)
    assert "READ ONLY" in out.stdout
    assert sqlite3.connect(db).execute(
        "SELECT lines FROM world_jhsaa_dual ORDER BY rowid").fetchall() == raw


def test_it_is_idempotent(tmp_path):
    """A run interrupted part-way is safe to resume."""
    db = tmp_path / "a.db"
    _legacy_db(db, [("boys", "Abbey Prep", "Scheelite County", _blob())])
    _migrate(db, "--apply")
    once = _resolve(db)
    out = _migrate(db, "--apply")
    assert _resolve(db) == once
    assert "away rows cleared 0" in out.stdout


def test_an_away_row_that_disagrees_is_kept_not_dropped(tmp_path):
    """‼️ THE SAFETY PROPERTY. The away copy is discarded only against a home row
    that COMPARES EQUAL. Anything else — a missing counterpart, a disagreement —
    keeps its own copy. A migration that guesses here loses a real box score and
    nothing ever says so."""
    db = tmp_path / "a.db"
    _legacy_db(db, [("boys", "Abbey Prep", "Scheelite County", _blob())])
    conn = sqlite3.connect(db)
    odd = [{"slot": "S1", "home": ["Someone Else"], "away": ["Nobody"],
            "score": "6-0, 6-0", "home_won": True}]
    conn.execute("UPDATE world_jhsaa_dual SET lines=? WHERE home=0", (json.dumps(odd),))
    conn.commit()
    conn.close()
    out = _migrate(db, "--apply")
    assert "kept (no match) 1" in out.stdout
    kept = _resolve(db)
    assert odd in kept.values(), "the disagreeing away box score was dropped"


def test_the_dual_identity_is_only_unique_within_one_world_year_gender(tmp_path):
    """‼️ `jh_match_key` carries NO gender and NO year — the same two schools meet
    in the boys' and the girls' season, in the same phase, at the same venue, and
    hash to ONE key. So every home-lines map must be built per (world, year,
    gender); a global one silently attaches the boys' box score to the girls'
    dual. Caught exactly that way while verifying the migration."""
    boys = {"home": 1, "school": "Abbey Prep", "opp": "Scheelite County",
            "level": "v", "phase": "regular", "district": 1}
    assert wd.jh_match_key(boys) == wd.jh_match_key(dict(boys))   # gender-blind

    db = tmp_path / "a.db"
    _legacy_db(db, [("boys", "Abbey Prep", "Scheelite County", _blob()),
                    ("girls", "Abbey Prep", "Scheelite County", _blob() * 4)])
    before = _resolve(db)
    _migrate(db, "--apply")
    after = _resolve(db)
    assert after == before
    # the two genders' box scores stayed different lengths — no cross-wiring
    assert sorted(len(v) for v in after.values()) == [2, 2, 8, 8]
