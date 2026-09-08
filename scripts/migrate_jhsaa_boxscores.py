#!/usr/bin/env python3
"""Rewrite an existing JHSAA archive into the compressed, de-duplicated box-score
layout — in place, one season at a time, verifying before it keeps anything.

WHAT IT DOES, per `world_jhsaa_dual` row:
  * HOME row — re-stores `lines` through `world.pack_lines` (zlib). ~2.3x.
  * AWAY row — stores NULL, because the home row of the same dual holds the
    identical blob. Half the column is a literal duplicate.

Measured on the owner's real 50-season save: 2,976 MB of a 4,402 MB file was
this one column. Both changes together take it to roughly 645 MB.

‼️ NOTHING IS REQUIRED. The app reads BOTH encodings and prefers a row's own
copy, so an un-migrated save keeps working exactly as it does today. This
script only reclaims space that is already being wasted.

SAFETY, in the order it matters:
  * READ-ONLY UNLESS `--apply`. The default run reports and changes nothing.
  * An away row is nulled ONLY after its home counterpart is found AND its
    decoded box score compares EQUAL. Anything that does not match is left
    alone and counted — never guessed at, never dropped.
  * Every season-gender is verified INSIDE its own transaction: the box score
    for every dual is digested before, and re-read through the real resolution
    path after; a mismatch rolls that season back and stops the run. A partial
    run is safe to resume — the work is idempotent.
  * Nothing is deleted and no row is removed. Only `lines` is rewritten.

`--vacuum` at the end is what actually returns the freed pages to the OS.
SQLite rebuilds the file to do that, so it needs free space roughly the size of
the FINISHED database (~2 GB here), and it is skipped by default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time

CANONICAL = os.path.expanduser("~/.tennis-team-manager/jhsaa_lab.db")


def _digest(pairs) -> str:
    """A stable digest of every box score in one season-gender, keyed by dual."""
    h = hashlib.blake2s()
    for key, lines in sorted(pairs, key=lambda kv: repr(kv[0])):
        h.update(repr(key).encode())
        h.update(json.dumps(lines, sort_keys=True, separators=(",", ":")).encode())
    return h.hexdigest()


def _mb(n: int) -> str:
    return f"{n / 1e6:,.0f} MB"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=CANONICAL, help=f"database (default {CANONICAL})")
    ap.add_argument("--apply", action="store_true",
                    help="actually write; without it the run is read-only")
    ap.add_argument("--vacuum", action="store_true",
                    help="rebuild the file afterwards to return freed pages to the OS "
                         "(needs free space ~the size of the finished database)")
    args = ap.parse_args()

    db = os.path.abspath(os.path.expanduser(args.db))
    if not os.path.isfile(db):
        print(f"no such database: {db}", file=sys.stderr)
        return 2

    # Bind the app to THIS file before importing it, so the codec, the dual
    # identity and the resolution rule all come from the shipped code rather
    # than a second copy that could drift from it.
    os.environ["TENNIS_DB_PATH"] = db
    os.environ.pop("JHSAA_LAB_MODE", None)          # no lab preflight on a tool run
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.world import pack_lines, unpack_lines, jh_match_key   # noqa: E402

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")

    size0 = os.path.getsize(db)
    col0 = conn.execute("SELECT COALESCE(SUM(LENGTH(lines)),0) FROM world_jhsaa_dual"
                        ).fetchone()[0]
    seasons = conn.execute(
        "SELECT world_id, year, gender, COUNT(*) n FROM world_jhsaa_dual"
        " GROUP BY world_id, year, gender ORDER BY world_id, year, gender").fetchall()
    print(f"database   {db}")
    print(f"file       {_mb(size0)}")
    print(f"box scores {_mb(col0)}  ({col0 * 100 // max(size0, 1)}% of the file)")
    print(f"seasons    {len(seasons)}  "
          f"({sum(s['n'] for s in seasons):,} dual rows)")
    if not args.apply:
        print("\n-- READ ONLY. Re-run with --apply to migrate. --")

    packed = nulled = kept = already = empty = 0
    t0 = time.time()
    for s in seasons:
        wid, year, gender = s["world_id"], s["year"], s["gender"]
        rows = conn.execute(
            "SELECT rowid AS id, school, opp, home, phase, district, level, lines"
            " FROM world_jhsaa_dual WHERE world_id=? AND year=? AND gender=?",
            (wid, year, gender)).fetchall()

        decoded, home_of = {}, {}
        for r in rows:
            decoded[r["id"]] = unpack_lines(r["lines"])
            if r["home"]:
                home_of[jh_match_key(dict(r))] = r["id"]

        # What every dual's box score reads as BEFORE — the thing that must not move.
        before = _digest((jh_match_key(dict(r)),
                          decoded[r["id"]] or decoded.get(home_of.get(
                              jh_match_key(dict(r))), []))
                         for r in rows)

        writes = []
        for r in rows:
            mine = decoded[r["id"]]
            if not mine:
                empty += 1
                continue
            if r["home"]:
                if isinstance(r["lines"], (bytes, bytearray, memoryview)):
                    already += 1
                else:
                    writes.append((pack_lines(mine), r["id"]))
                    packed += 1
                continue
            # An away row is dropped ONLY against a home row that agrees.
            hid = home_of.get(jh_match_key(dict(r)))
            if hid is not None and decoded.get(hid) == mine:
                writes.append((None, r["id"]))
                nulled += 1
            else:
                # No counterpart, or it disagrees — keep this copy, just smaller.
                if not isinstance(r["lines"], (bytes, bytearray, memoryview)):
                    writes.append((pack_lines(mine), r["id"]))
                    packed += 1
                else:
                    already += 1
                kept += 1

        if not args.apply or not writes:
            continue

        conn.execute("BEGIN")
        conn.executemany("UPDATE world_jhsaa_dual SET lines=? WHERE rowid=?", writes)

        # Verify INSIDE the transaction, through the real resolution path.
        after_rows = conn.execute(
            "SELECT rowid AS id, school, opp, home, phase, district, level, lines"
            " FROM world_jhsaa_dual WHERE world_id=? AND year=? AND gender=?",
            (wid, year, gender)).fetchall()
        got, hmap = {}, {}
        for r in after_rows:
            got[r["id"]] = unpack_lines(r["lines"])
            if r["home"]:
                hmap[jh_match_key(dict(r))] = r["id"]
        after = _digest((jh_match_key(dict(r)),
                         got[r["id"]] or got.get(hmap.get(jh_match_key(dict(r))), []))
                        for r in after_rows)
        if after != before:
            conn.rollback()
            print(f"\n‼️  {year} {gender}: box scores would CHANGE — rolled back, "
                  "nothing written for this season. Stopping.", file=sys.stderr)
            conn.close()
            return 1
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")   # keep the sidecar small
        print(f"  {year} {gender}: {len(writes):,} rows rewritten", flush=True)

    print(f"\ncompressed {packed:,}   away rows cleared {nulled:,}   "
          f"kept (no match) {kept:,}   already packed {already:,}   "
          f"no box score {empty:,}")
    print(f"elapsed {time.time() - t0:,.0f}s")

    if args.apply:
        col1 = conn.execute(
            "SELECT COALESCE(SUM(LENGTH(lines)),0) FROM world_jhsaa_dual").fetchone()[0]
        free = conn.execute("PRAGMA freelist_count").fetchone()[0]
        page = conn.execute("PRAGMA page_size").fetchone()[0]
        print(f"box scores {_mb(col0)} -> {_mb(col1)}")
        print(f"reclaimable inside the file: {_mb(free * page)}"
              + ("" if args.vacuum else "  (run again with --vacuum to return it)"))
        if args.vacuum:
            print("rebuilding (VACUUM) — needs free space ~the finished size…",
                  flush=True)
            conn.execute("VACUUM")
            print(f"file {_mb(size0)} -> {_mb(os.path.getsize(db))}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
