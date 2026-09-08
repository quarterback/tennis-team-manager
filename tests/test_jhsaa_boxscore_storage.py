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
    ninth reader at the source, not in a season's worth of zeroed records."""
    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    bad = []
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
            bad.append(f"{path.relative_to(root)}:{n}: {line.strip()}")
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
    assert tail.count("pack_lines(d.get(\"lines\", []))") == 2, (
        "the varsity and JV row builders must both pack the box score")
    assert 'json.dumps(d.get("lines"' not in tail, "a raw json.dumps write survived"
    assert ins  # the statement still exists
