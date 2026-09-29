#!/usr/bin/env python3
"""Read-path audit for the JHSAA pages — COUNT, don't guess (owner rule 2026-09).

One request each against a save, reporting what a single click actually does:
roster builds, whole-association loads, ladder sorts, sibling rolls, whole-season
archive reads, SQLite connections and statements, and the top functions by wall
time. Run it against a COPY of a real save (the app creates missing tables on
open; it never rewrites a season):

    cp ~/.tennis-team-manager/jhsaa_lab.db /tmp/lab-copy.db
    python3 scripts/jhsaa_read_audit.py --db /tmp/lab-copy.db

The point of the tool is the "scope larger than the entity" question: a program
page has no business building any roster but that program's, reading any season
but the ones on screen, or loading the association more than once. Every number
here that is bigger than that needs a reason in the code.
"""
from __future__ import annotations

import argparse
import collections
import cProfile
import io
import os
import pstats
import sqlite3
import sys
import time
import urllib.parse as up

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="path to a COPY of the save")
    ap.add_argument("--gender", default="girls")
    ap.add_argument("--school", help="a program with an archived season (default: first in the newest archive)")
    ap.add_argument("--portal-build", action="store_true",
                    help="also build a rising-freshman portal proposal for the upcoming season (heavy)")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    os.environ["TENNIS_DB_PATH"] = args.db
    os.environ.setdefault("JHSAA_LAB_DEV_OVERRIDE", "1")
    from app import dbpath
    dbpath._resolved.clear()
    from app import jhsaa as jh, world as wd
    from app import jhsaa_coaches as jc
    wd.WORLD_DB = args.db
    wd._schema_ready_for = None
    wd.is_primed = lambda *a, **k: True          # a read audit, not a warm-up
    wd.prime = lambda *a, **k: None
    from app.web.server import create_app
    client = create_app().test_client()

    counts: collections.Counter = collections.Counter()
    statements: collections.Counter = collections.Counter()

    def wrap(mod, name):
        real = getattr(mod, name)

        def f(*a, **k):
            counts[name] += 1
            return real(*a, **k)
        setattr(mod, name, f)

    for name in ("build_roster", "load_schools", "district_teams", "_order", "coach_eval",
                 "sibling_link", "school_exposure", "staff_history", "_class_moves",
                 "pinned_talents", "enrolled_transfers", "families"):
        wrap(jh, name)
    wrap(wd, "get_jhsaa")
    real_connect = sqlite3.connect

    def counting_connect(*a, **k):
        counts["sqlite connect"] += 1
        conn = real_connect(*a, **k)

        def tracer(stmt):
            counts["sqlite statement"] += 1
            statements[" ".join(stmt.split())[:64]] += 1
        try:
            conn.set_trace_callback(tracer)
        except Exception:
            pass
        return conn
    sqlite3.connect = counting_connect

    w = wd.load_world(wd.DEFAULT_SEED)
    if not w:
        sys.exit("no world in that save")
    g = args.gender
    years = wd.jhsaa_years(w["id"], g)
    if not years:
        sys.exit(f"no archived {g} season in that save")
    arc = wd.get_jhsaa(w["id"], years[0], g) or {}
    season_year = arc.get("season_year") or (wd.BASE_YEAR + years[0] + 1)
    names = sorted(n for grp in (arc.get("standings") or {}).values()
                   for d in grp.values() for n in (d if isinstance(d, dict) else {}))
    school_name = args.school or (names[0] if names else jh.load_schools(g)[0].name)
    school = next((s for s in jh.load_schools(g) if s.name == school_name), None) or jh.former_school(school_name, g)
    salt = wd.active_salt(w["seed"])
    roster = jh.build_roster(school, season_year, salt)
    conn = real_connect(args.db)
    row = conn.execute("SELECT c.coach_id FROM jhsaa_coach c JOIN jhsaa_coach_seat s ON s.coach_id=c.coach_id"
                       " AND s.world_id=c.world_id WHERE c.world_id=? AND s.gender=? LIMIT 1",
                       (w["id"], g)).fetchone()
    conn.close()
    coach_id = row[0] if row else None
    print(f"save {args.db}: world year {w['year']}, {len(years)} archived {g} seasons, "
          f"{len(jh.load_schools(g))} programs, auditing {school_name} / season {season_year}")

    pages = [("/jhsaa/school/" + up.quote(school_name) + f"?g={g}", "program page"),
             (f"/jhsaa/rankings?g={g}&group=" + up.quote(school.group), "rankings"),
             (f"/jhsaa/player/{up.quote(school_name)}/{roster[0].pid}?g={g}", "player page"),
             (f"/jhsaa/portal?g={g}&group=" + up.quote(jh.EARLY_CLASSES[0]), "portal page")]
    if coach_id:
        pages.insert(2, (f"/jhsaa/coach/{coach_id}?g={g}", "coach page"))
    for path, label in pages:
        client.get(path)                          # first hit warms whatever is honestly memoised
        counts.clear()
        statements.clear()
        prof = cProfile.Profile()
        t = time.time()
        prof.enable()
        r = client.get(path)
        prof.disable()
        dt = time.time() - t
        print(f"\n=== {label}  {path}\n    {r.status_code} in {dt:.2f}s (second hit)")
        print("    " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        print("    statements: " + "; ".join(f"{n}x {q}" for q, n in statements.most_common(3)))
        st = pstats.Stats(prof, stream=io.StringIO())
        rows = sorted(((f, v) for f, v in st.stats.items() if "/app/" in f[0]), key=lambda fv: -fv[1][3])
        print("    top by cumulative time:")
        for (fn, _ln, name), (_cc, nc, _tt, ct, _callers) in rows[:args.top]:
            print(f"      {ct:6.2f}s {nc:7d}x  {os.path.basename(fn)}:{name}")
    if args.portal_build:
        from app import jhsaa_portal as jp
        counts.clear()
        t = time.time()
        data = jp.build(w["id"], jp.upcoming_season(w, lab=wd.is_jhsaa_only()), salt)
        print(f"\n=== portal build, both genders: {time.time()-t:.1f}s  moves={len(data['moves'])} stays={len(data['stays'])}")
        print("    " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main()
