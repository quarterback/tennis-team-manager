#!/usr/bin/env python3
"""Why does a program sit in THAT Non-Public league? — a read-only diagnostic.

The leagues a save plays on are the SEED FILE, overwritten in memory on every
load by the save's newest COMMITTED REALIGNMENT MAP (`jhsaa_reclass.reapply`),
then put right by the standing Non-Public rule (`jhsaa_districting.
ensure_nonpublic`). When a page shows a league the seed file does not, the map
in the save is the usual reason, and nothing on a page says so. This prints all
three layers for 10B/11B, plus every reason the repair gave (or did not fire),
without writing anything — the seed file is copied to a temp path first.

Usage: python3 scripts/jhsaa_nonpublic_diag.py [--db PATH] [--school NAME]
       default --db is the lab save, ~/.tennis-team-manager/jhsaa_lab.db
"""
from __future__ import annotations

import collections
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _arg(argv, flag, default=None):
    if flag in argv:
        return argv[argv.index(flag) + 1]
    return default


def main(argv: list[str]) -> int:
    db = os.path.expanduser(_arg(argv, "--db", "~/.tennis-team-manager/jhsaa_lab.db"))
    school = _arg(argv, "--school", "Condotti Vanguard Academy")
    if not os.path.exists(db):
        print(f"no save at {db}")
        return 2
    os.environ["TENNIS_DB_PATH"] = db
    os.environ.pop("JHSAA_LAB_MODE", None)
    from app import jhsaa as jh, jhsaa_reclass as rc, jhsaa_districting as jd, world as wd

    def table(label, rows, key):
        print(f"\n== {label}")
        by = collections.defaultdict(list)
        for r in rows:
            g, lg = key(r)
            if g in jd.NONPUBLIC:
                by[(g, lg or "(none)")].append(r["name"])
        for (g, lg), names in sorted(by.items()):
            flag = "  <-- UNDER FLOOR" if len(names) < jd.districting_config().MIN_DISTRICT_SIZE else ""
            print(f"  {g:4} {lg:40} {len(names):2}{flag}")
        stray = [r["name"] for r in rows if r.get("private") and key(r)[0] not in jd.NONPUBLIC]
        if stray:
            print(f"  privates OUTSIDE 10B/11B: {len(stray)} e.g. {stray[:5]}")

    seed = os.path.join(ROOT, "data", "jhsaa", "schools.json")
    with open(seed, encoding="utf-8") as fh:
        file_rows = json.load(fh)["schools"]
    table(f"SEED FILE {seed}", file_rows, lambda r: (r.get("group"), r.get("girls_district")))

    conn = wd._db()
    try:
        cyc = conn.execute("SELECT year, status, committed, length(data) AS n FROM world_jhsaa_reclass"
                           " ORDER BY year DESC").fetchall()
    except Exception as exc:
        cyc = []
        print(f"\n(no reclass table: {exc})")
    finally:
        conn.close()
    print("\n== REALIGNMENT CYCLES IN THE SAVE")
    for c in cyc:
        print(f"  year {c['year']}: {c['status']} committed={c['committed']} data={c['n']}B")
    m = rc.committed_map(file_rows)
    if m:
        print("\n== NEWEST COMMITTED MAP (what reapply writes over the seed on every load)")
        privates = {r["name"] for r in file_rows if r.get("private")}
        mrows = [{"name": n, "private": n in privates,
                  "group": e.get("grp"), "girls_district": e.get("gd")} for n, e in m.items()]
        table("map entries in 10B/11B", mrows, lambda r: (r["group"], r["girls_district"]))
        e = m.get(school)
        print(f"  {school}: {e}")
    else:
        print("\n(no committed map)")

    tmp = tempfile.mkdtemp()
    shutil.copy(seed, os.path.join(tmp, "schools.json"))
    jh._DATA = os.path.join(tmp, "schools.json")
    jh._schools_cache = None
    import logging
    logging.basicConfig(level=logging.WARNING, format="  log: %(message)s")
    print("\n== LOADING AS THE APP DOES (temp copy; the real file is untouched)")
    rows = jh._rows()
    table("LOADED MAP", rows, lambda r: (r.get("group"), r.get("girls_district")))
    r = next((x for x in rows if x["name"] == school), None)
    print(f"\n  {school}: " + (", ".join(f"{k}={r.get(k)!r}" for k in
          ("classification", "group", "girls_district", "boys_district", "old_group",
           "old_league", "enrollment", "girls", "boys")) if r else "NOT IN FILE"))
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
