#!/usr/bin/env python3
"""Integrate a finished JHSAA lab save into a full college save (owner request
2026-09): copy the lab database to a college save file, build the college
universes into it at the world's CURRENT year (`world.attach_college`), and set
the display-year offset so the first college season renders as 2026-27 with the
decades of high-school history backdated behind it.

The lab file itself is NEVER touched — the merge runs on a copy, and the copy
becomes the college save you launch through the ordinary route (no
JHSAA_LAB_MODE, no TENNIS_DB_PATH needed when it lands at ./tennis.db).

    python3 scripts/integrate_lab_world.py                    # preflight report
    python3 scripts/integrate_lab_world.py --apply            # do it
    python3 scripts/integrate_lab_world.py --from X --to Y --apply

Read-only without --apply (the migrate_jhsaa_boxscores idiom). Refuses to
overwrite an existing target — never abandon or clobber a save file.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys

LAB_DEFAULT = os.path.abspath(os.path.expanduser("~/.tennis-team-manager/jhsaa_lab.db"))


def _world_rows(path: str) -> list[dict]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM world ORDER BY id")]
        arch = conn.execute("SELECT MAX(year) y, COUNT(DISTINCT year) n FROM world_jhsaa"
                            ).fetchone()
        return rows, (arch["y"], arch["n"])
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="src", default=LAB_DEFAULT,
                    help=f"lab database to integrate (default {LAB_DEFAULT})")
    ap.add_argument("--to", dest="dst", default=os.path.abspath("tennis.db"),
                    help="college save file to create (default ./tennis.db)")
    ap.add_argument("--apply", action="store_true",
                    help="copy and attach; without it, report only")
    args = ap.parse_args()
    src, dst = os.path.abspath(args.src), os.path.abspath(args.dst)

    if not os.path.exists(src):
        print(f"‼️ lab database not found: {src}")
        return 1
    if os.path.exists(dst):
        print(f"‼️ target already exists: {dst} — refusing to overwrite a save. "
              "Move it aside or pass a different --to.")
        return 1

    rows, (max_idx, n_years) = _world_rows(src)
    if len(rows) != 1:
        print(f"‼️ expected exactly ONE world row in {src}, found {len(rows)} — "
              "run scripts/cleanup_stray_worlds.py against it first.")
        return 1
    w = rows[0]
    # One-world doctrine: the seed and salt come off the row, never typed.
    base = 2026                      # world.BASE_YEAR; not imported here so the
    #                                  preflight never binds app.world to a path
    season = base + w["year"] + 1
    print(f"lab world: seed {w['seed']}, year {w['year']} (JHSAA season {season}), "
          f"salt {w.get('salt') or '(none)'}")
    print(f"archive: {n_years} JHSAA season(s), newest index {max_idx} "
          f"(season {base + (max_idx or 0) + 1})")
    if max_idx is not None and max_idx != w["year"]:
        print(f"‼️ archive newest index {max_idx} != world year {w['year']} — "
              "finish or replay the lab season before integrating.")
        return 1
    print(f"plan: copy → {dst}, build college rosters at world year {w['year']}, "
          f"display offset {w['year']} (world year {w['year']} renders as {base}, "
          f"season {season} renders as {base + 1}).")
    if not args.apply:
        print("read-only preflight — re-run with --apply to integrate.")
        return 0

    print("copying …")
    shutil.copy2(src, dst)
    # Bind the app to the COPY before any app import resolves the db path.
    os.environ["TENNIS_DB_PATH"] = dst
    os.environ.pop("JHSAA_LAB_MODE", None)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import world as wd
    print("building college universes (all divisions × genders — takes a while) …")
    out = wd.attach_college(w["seed"])
    print(f"done: world year {out['year']}, display offset {wd.display_offset()} — "
          f"first college season shows as {wd.display_base_year() + out['year']}"
          f"-{wd.display_base_year() + out['year'] + 1}.")
    print(f"launch the game plainly against {dst} (or with TENNIS_DB_PATH={dst}) "
          "and advance from /world/advance as usual. The lab file was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
