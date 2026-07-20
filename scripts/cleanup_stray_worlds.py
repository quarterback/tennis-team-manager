"""
Remove STRAY world rows created by the pre-fix /world-cups live view.

Before the fix in app/web/state.get_world_cup, the live cup view scanned rosters
with the DERIVED year seed (base + 1000×year) instead of the base world seed;
world.prime → get_or_create then CREATED a parallel world under that seed (fake
players, junk rows). This also confused GTT's newest-world default linkage.

A stray is identified precisely: a world whose seed equals another world's
`seed + 1000×y` for some year y ≥ 1 within that world's lifetime — i.e. it sits
exactly where the bug would have written it. Everything keyed to the stray's
world_id is removed across all world_* tables.

Usage:
    python3 scripts/cleanup_stray_worlds.py            # dry run — list only
    python3 scripts/cleanup_stray_worlds.py --delete   # actually remove
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import dbpath
from app.dbpath import resolve_db_path

WORLD_TABLES = ("world_roster", "world_signing", "world_crossmatch",
                "world_championship", "world_graduates", "world_cups",
                "world_pro", "world_portal_move")


def main(argv):
    delete = "--delete" in argv
    conn = dbpath.connect(resolve_db_path())
    worlds = [dict(r) for r in conn.execute(
        "SELECT id, seed, year, week FROM world ORDER BY id").fetchall()]
    if not worlds:
        print("No worlds in this save.")
        return
    # Derived-seed values a legitimate world could have produced via the bug.
    derived = set()
    for w in worlds:
        for y in range(1, int(w["year"]) + 2):
            derived.add(int(w["seed"]) + 1000 * y)
    strays = [w for w in worlds if int(w["seed"]) in derived]
    keep = [w for w in worlds if w not in strays]
    print(f"DB: {resolve_db_path()}")
    for w in keep:
        print(f"  keep : world id={w['id']} seed={w['seed']} year={w['year']} week={w['week']}")
    if not strays:
        print("No stray worlds found — nothing to do.")
        return
    for w in strays:
        counts = {t: conn.execute(f"SELECT COUNT(*) c FROM {t} WHERE world_id=?",
                                  (w["id"],)).fetchone()["c"] for t in WORLD_TABLES}
        rows = ", ".join(f"{t.replace('world_', '')}={n}" for t, n in counts.items() if n)
        print(f"  STRAY: world id={w['id']} seed={w['seed']} ({rows or 'no data'})")
    if not delete:
        print("\nDry run — re-run with --delete to remove the stray world(s).")
        return
    for w in strays:
        for t in WORLD_TABLES:
            conn.execute(f"DELETE FROM {t} WHERE world_id=?", (w["id"],))
        conn.execute("DELETE FROM world WHERE id=?", (w["id"],))
    conn.commit()
    print(f"\nDeleted {len(strays)} stray world(s).")
    conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])
