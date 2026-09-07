#!/usr/bin/env python3
"""What SHAPE is each archived JHSAA state draw? — a read-only dump of the save.

The bracket page renders whatever the archive holds: the "Field" stat is the
length of the draw's own `field` list, and the Parastate is drawn when the
archived `round_names` names it. So when a page does not show the shape you
expect, this says whether the archive ever held it — which separates "the
render broke" from "the season was played under different rules".

    python3 scripts/jhsaa_archive_shapes.py                # every season
    python3 scripts/jhsaa_archive_shapes.py --group 7A     # one class
    python3 scripts/jhsaa_archive_shapes.py --year 12      # one world year

Reads `world_jhsaa` straight out of the save (`$TENNIS_DB_PATH`, else
./tennis.db) — no simulation, no writes, nothing cached.

`pts` is the point total of the draw's first archived dual, which is the dual
FORMAT the season was played at: 5 = 1S/4D, 6 = 3S/3D, 9 = 4S/5D.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.dbpath import resolve_db_path                      # noqa: E402


def _shape(br: dict) -> dict:
    rounds = br.get("rounds") or []
    names = list(br.get("round_names") or ())
    first = next((gm for rd in rounds for gm in rd), None)
    pts = (int(first.get("home_points", 0)) + int(first.get("away_points", 0))
           if first else 0)
    return {"field": len(br.get("field") or ()), "names": names,
            "sizes": [len(r) for r in rounds], "pts": pts,
            "at_large": len(br.get("at_large") or ())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--group", help="one classification (7A, Group 1, …)")
    ap.add_argument("--year", type=int, help="one world year")
    ap.add_argument("--db", help="save file (default: $TENNIS_DB_PATH or ./tennis.db)")
    a = ap.parse_args()

    path = a.db or resolve_db_path()
    print(f"save: {path}\n")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT year, gender, data FROM world_jhsaa ORDER BY year, gender"
        ).fetchall()
    except sqlite3.OperationalError as e:
        print(f"no JHSAA archive in this save ({e})")
        return 1
    finally:
        conn.close()
    if not rows:
        print("no archived JHSAA seasons in this save")
        return 1

    print(f"{'year':>5} {'season':>6} {'gender':<6} {'class':<9} "
          f"{'field':>5} {'AL':>3} {'pts':>3}  rounds / round names")
    for r in rows:
        if a.year is not None and r["year"] != a.year:
            continue
        data = json.loads(r["data"])
        season_year = data.get("season_year", "")
        for grp, br in sorted((data.get("brackets") or {}).items()):
            if a.group and grp != a.group:
                continue
            if not br:
                continue
            s = _shape(br)
            para = "PARASTATE" if "Parastate" in s["names"] else ""
            named = " ".join(s["names"]) or "-"
            print(f"{r['year']:>5} {season_year:>6} {r['gender']:<6} {grp:<9} "
                  f"{s['field']:>5} {s['at_large']:>3} {s['pts']:>3}  "
                  f"{s['sizes']} {named} {para}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
