"""Diagnose "every roster shows 0-0" — regenerated names vs the archived season.

The JHSAA rebuilds every player on demand from (salt, school identity, entry
year, seat) + the persisted era gates, and a player's season W-L is matched to
the archive BY NAME while awards match BY PID (a pid carries no salt and no
name). So the signature "award chips still attach but every record reads 0-0"
means the NAMES the app generates today are not the names the season was
simulated with — one of the per-save inputs moved. This prints them all, then
compares one school's archived line names against its regenerated roster, and
sweeps the candidate inputs (each era key at its stored value vs the values it
could have held) to name the one that restores the match.

Run against the real save:  TENNIS_DB_PATH=/path/to/tennis.db \
    python3 scripts/diagnose_jhsaa_roster_drift.py [School Name] [boys|girls]

Read-only: nothing is written, and the era memo caches are restored after each
probe.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import jhsaa as jh                                    # noqa: E402
from app import world as wd                                    # noqa: E402
from app import worldconfig                                    # noqa: E402
from app.dbpath import resolve_db_path                         # noqa: E402


def main() -> None:
    school_name = sys.argv[1] if len(sys.argv) > 1 else None
    gender = sys.argv[2] if len(sys.argv) > 2 else "boys"

    db = resolve_db_path()
    print(f"db: {db}")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    worlds = conn.execute("SELECT id, seed, salt, year FROM world").fetchall()
    for w in worlds:
        print(f"world row: id={w['id']} seed={w['seed']} salt={w['salt']!r} year={w['year']}")
    if len(worlds) != 1:
        print("‼️ EXPECTED EXACTLY ONE WORLD ROW — a stray world means pages can "
              "resolve a different salt than the one the season simulated with.")
    for key in ("jhsaa_name_era", "jhsaa_dev_era", "jhsaa_talent_era",
                "jhsaa_career_era"):
        print(f"worldconfig {key} = {worldconfig.get(key)!r}")
    latest = conn.execute("SELECT MAX(year) FROM world_jhsaa").fetchone()[0]
    print(f"latest archived world_jhsaa.year index: {latest} "
          f"(season {wd.BASE_YEAR + latest + 1 if latest is not None else '—'})")

    w = wd.load_world(wd.DEFAULT_SEED)
    if not w:
        print("no world — nothing to compare"); return
    salt = wd.active_salt(wd.DEFAULT_SEED)
    season_year = wd.jhsaa_season_year(w)

    schools = jh.load_schools(gender)
    sc = next((s for s in schools if s.name == school_name), None) if school_name \
        else schools[0]
    if sc is None:
        print(f"school {school_name!r} not found for {gender}"); return
    print(f"\nschool: {sc.name} ({gender}) — ident {sc.ident!r} key {sc.key!r}")

    sched = wd.jhsaa_schedule(w["id"], w["year"], gender, sc.name)
    archived = set()
    for d in sched:
        if (d.get("level") or "v") != "v":
            continue
        side = "home" if d.get("home") else "away"
        for ln in d.get("lines") or ():
            archived.update(ln.get(side) or ())
    print(f"archived varsity line names ({len(archived)}): "
          f"{sorted(archived)[:8]}{' …' if len(archived) > 8 else ''}")
    if not archived:
        print("no archived lines for the current season — pick a school that played")
        return

    def overlap(label: str) -> int:
        roster = {p.name for p in jh.build_roster(sc, season_year, salt)}
        n = len(roster & archived)
        print(f"{label}: {n}/{len(archived)} archived names on the regenerated "
              f"roster ({sorted(roster)[:6]}{' …' if len(roster) > 6 else ''})")
        return n

    got = overlap("AS CONFIGURED")
    if got:
        print("names match — the 0-0 fold has a different cause; stop here and "
              "report this output.")
        return

    # Sweep the name era: the one gate that moves NAMES alone. Each probe forces
    # the memo + the resolved value, builds, and restores.
    print("\nname-era sweep (a hit names the era the season was simulated under):")
    cache_key = resolve_db_path()
    saved = jh._name_era_cache.get(cache_key)
    try:
        for era in [0] + list(range(max(0, season_year - 12), season_year + 3)):
            jh._name_era_cache[cache_key] = era
            roster = {p.name for p in jh.build_roster(sc, season_year, salt)}
            n = len(roster & archived)
            if n:
                print(f"  name_era={era}: {n}/{len(archived)} MATCH")
    finally:
        if saved is None:
            jh._name_era_cache.pop(cache_key, None)
        else:
            jh._name_era_cache[cache_key] = saved
    print("(no lines above = no era value restores the names → the drift is the "
          "SALT: compare the world rows printed at the top against your backup)")


if __name__ == "__main__":
    main()
