"""Profile ONE JHSAA program page against a COPY of a save — per tab, per section,
cold and warm, moving between schools.

    python3 scripts/jhsaa_school_profile.py --db /tmp/lab-copy.db --gender boys \\
        --school "Tallulah Canyon" --school "Averill"

Owner report 2026-10: clicking a team on any schedule could take minutes on a
mature universe. The page now builds only what the selected tab renders
(`jhsaa_school_view(hq=)`) and the hero's individual-champion count comes off one
memoised SQLite index (`world._school_champion_index`). This script is how to
confirm that on the real save: every section the page reads is timed on its own,
then every tab is requested through the Flask test client, first cold (fresh
process caches) and then warm, for each school given. Read-only: it opens the copy
you point it at and never writes.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.parse as up

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TABS = ("overview", "team", "season", "history", "honors", "records", "staff")


def _t(label, fn, out):
    t0 = time.perf_counter()
    r = fn()
    out.append((label, time.perf_counter() - t0))
    return r


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="path to a COPY of the save")
    ap.add_argument("--gender", default="girls")
    ap.add_argument("--school", action="append",
                    help="program(s) to open; default: three from the newest archive")
    args = ap.parse_args()

    os.environ["TENNIS_DB_PATH"] = args.db
    os.environ.setdefault("JHSAA_LAB_DEV_OVERRIDE", "1")
    from app import dbpath
    dbpath._resolved.clear()
    from app import jhsaa as jh, world as wd
    from app import jhsaa_coaches as jc
    import app.jhsaa_preseason as jps
    import app.web.state as st
    wd.WORLD_DB = args.db
    wd._schema_ready_for = None
    wd.is_primed = lambda *a, **k: True
    wd.prime = lambda *a, **k: None
    from app.web.server import create_app
    client = create_app().test_client()

    g = args.gender
    w = wd.load_world()
    years = wd.jhsaa_years(w["id"], g)
    if not years:
        sys.exit(f"no archived {g} season in {args.db}")
    yr = years[0]
    schools = args.school
    if not schools:
        arc = wd.get_jhsaa(w["id"], yr, g)
        names = sorted({s for grp in arc["standings"].values()
                        for d in grp.values() for s in d})
        schools = names[:3]
    print(f"save {args.db}\nworld year {w['year']} · {len(years)} archived {g} seasons · newest {yr}")

    # --- sections, cold then warm, on the first school -----------------------
    first = schools[0]
    sc = jh.former_school(first, g)
    if sc is None:
        sys.exit(f"no {g} program named {first!r}")
    salt = wd.active_salt(wd.DEFAULT_SEED)
    sy = wd.jhsaa_season_year(w)
    for pass_ in ("cold", "warm"):
        out = []
        _t("get_jhsaa (archive memo)", lambda: wd.get_jhsaa(w["id"], yr, g), out)
        _t("load_schools", lambda: jh.load_schools(g), out)
        seasons = _t("jhsaa_school_seasons (materialised rows)",
                     lambda: wd.jhsaa_school_seasons(w["id"], g, first), out)
        _t("jhsaa_school_individual_champions (champion index)",
           lambda: wd.jhsaa_school_individual_champions(w["id"], g, first, seasons), out)
        _t("jhsaa_schedule", lambda: wd.jhsaa_schedule(w["id"], yr, g, first), out)
        _t("jhsaa_match_dates (gender-season calendar)",
           lambda: wd.jhsaa_match_dates(w["id"], yr, g, sc_season_year(wd, w, yr, g)), out)
        _t("stored_roster", lambda: jps.stored_roster(w["id"], yr, g, first), out)
        _t("jhsaa_captains", lambda: wd.jhsaa_captains(w["id"], yr, g), out)
        _t("jhsaa_school_injuries", lambda: wd.jhsaa_school_injuries(w["id"], yr, g, first), out)
        _t("families", lambda: jh.families(), out)
        _t("rival_map", lambda: jh.rival_map(jh.load_schools(g)), out)
        _t("jhsaa_program_wins (Records tab)",
           lambda: wd.jhsaa_program_wins(w["id"], g, first, salt), out)
        _t("ensure_seated", lambda: jc.ensure_seated(w["id"], sy, salt), out)
        _t("program_staff", lambda: jc.program_staff(w["id"], sc.ident, g, sy), out)
        _t("program_head_coaches (History tab)",
           lambda: jc.program_head_coaches(w["id"], sc.ident, g, sy), out)
        _t("program_heads_by_year (History tab)",
           lambda: jc.program_heads_by_year(w["id"], sc.ident, g), out)
        print(f"\n== sections · {first} · {pass_}")
        for label, dt in out:
            print(f"  {dt*1000:9.0f} ms  {label}")

    # --- whole pages, every tab, every school ---------------------------------
    print("\n== pages (ms) · cold = first request of that school in this process")
    print("  " + "school".ljust(28) + "".join(t.rjust(10) for t in TABS))
    for name in schools:
        row = []
        for tab in TABS:
            url = f"/jhsaa/school/{up.quote(name)}?g={g}&view={tab}"
            t0 = time.perf_counter()
            r = client.get(url)
            dt = (time.perf_counter() - t0) * 1000
            row.append(f"{dt:8.0f}{'!' if r.status_code != 200 else ' '}")
        print("  " + name[:27].ljust(28) + "".join(c.rjust(10) for c in row))
    # second visit to the first school: everything warm
    row = []
    for tab in TABS:
        t0 = time.perf_counter()
        client.get(f"/jhsaa/school/{up.quote(schools[0])}?g={g}&view={tab}")
        row.append(f"{(time.perf_counter() - t0) * 1000:8.0f} ")
    print("  " + (schools[0][:20] + " (warm)").ljust(28) + "".join(c.rjust(10) for c in row))


def sc_season_year(wd, w, yr, g):
    arc = wd.get_jhsaa(w["id"], yr, g) or {}
    return arc.get("season_year") or wd.jhsaa_season_year(w)


if __name__ == "__main__":
    main()
