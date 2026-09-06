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

Run it from the repo folder the game runs from, with NO TENNIS_DB_PATH, so it
reads exactly the save the app reads (the default is ./tennis.db next to the
repo):

    python3 scripts/diagnose_jhsaa_roster_drift.py "Coast Prairie" boys

Set TENNIS_DB_PATH only if your game runs with it set too.

Near read-only: the only write it can make is the one the app itself would make
on the next page load — persisting a MISSING era row at its self-configured
value. The sweep probes never write; the era memo caches are restored after.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import jhsaa as jh                                    # noqa: E402
from app import world as wd                                    # noqa: E402
from app import worldconfig                                    # noqa: E402
from app.dbpath import resolve_db_path                         # noqa: E402


def newest_played_season(world_id: int, gender: str, school: str,
                         latest: int | None) -> tuple[int | None, set]:
    """(archive year index, archived varsity line names) for the NEWEST archived
    season this school actually played — walking back from `latest`, because the
    current world year may not have played or archived yet. (None, empty) when
    no archived season carries a varsity line for the school. The calendar year
    to regenerate the roster at is `BASE_YEAR + index + 1`, the same conversion
    the era gates document."""
    for year_ix in range(latest if latest is not None else -1, -1, -1):
        got = set()
        for d in wd.jhsaa_schedule(world_id, year_ix, gender, school):
            if (d.get("level") or "v") != "v":
                continue
            side = "home" if d.get("home") else "away"
            for ln in d.get("lines") or ():
                got.update(ln.get(side) or ())
        if got:
            return year_ix, got
    return None, set()


def main() -> None:
    # --set-name-era N: repair a poisoned era row. While the dbpath probe race
    # was live (see app/dbpath.py), an era self-configured against the SHADOW
    # DB's archive could be persisted into the real save — a wrong value that
    # then renames every cohort it covers. Run the plain diagnostic first: its
    # sweep names the era that restores the archived names, and this writes it.
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fix = next((a for a in sys.argv[1:] if a.startswith("--set-name-era=")), None)
    if fix is not None:
        from app import worldconfig as wc
        val = str(int(fix.split("=", 1)[1]))
        print(f"jhsaa_name_era: {wc.get('jhsaa_name_era')!r} -> {val!r}")
        wc.set("jhsaa_name_era", val)
        jh._name_era_cache.clear()
        print("written — restart the app.")
    school_name = args[0] if args else None
    gender = args[1] if len(args) > 1 else "boys"

    configured = os.environ.get("TENNIS_DB_PATH")
    db = resolve_db_path()
    print(f"db: {db}")
    if configured and os.path.abspath(configured) != os.path.abspath(db):
        print(f"‼️ TENNIS_DB_PATH={configured!r} was NOT usable and the app fell back "
              f"to the file above. If that is not your real save, re-run from the "
              f"game's own folder with NO TENNIS_DB_PATH at all — the app's default "
              f"save is ./tennis.db next to the repo.")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    worlds = conn.execute("SELECT id, seed, salt, year FROM world").fetchall()
    for w in worlds:
        print(f"world row: id={w['id']} seed={w['seed']} salt={w['salt']!r} year={w['year']}")
    if len(worlds) != 1:
        print("‼️ EXPECTED EXACTLY ONE WORLD ROW — a stray world means pages can "
              "resolve a different salt than the one the season simulated with.")
    # Raw stored value ('' = the row does not exist) AND the value generation
    # actually resolves — resolving also self-configures and persists a missing
    # row, exactly as the first page load after an update does.
    for key, fn in (("jhsaa_name_era", jh.name_era), ("jhsaa_dev_era", jh.dev_era),
                    ("jhsaa_talent_era", jh.talent_era),
                    ("jhsaa_career_era", jh.career_era)):
        raw = worldconfig.get(key)
        print(f"worldconfig {key} = {raw!r} (missing)" if not str(raw).strip()
              else f"worldconfig {key} = {raw!r}", end="")
        print(f"  -> resolves to {fn()}")
    latest = conn.execute("SELECT MAX(year) FROM world_jhsaa").fetchone()[0]
    print(f"latest archived world_jhsaa.year index: {latest} "
          f"(season {wd.BASE_YEAR + latest + 1 if latest is not None else '—'})")

    w = wd.load_world(wd.DEFAULT_SEED)
    if not w:
        print("no world — nothing to compare"); return
    salt = wd.active_salt(wd.DEFAULT_SEED)

    schools = jh.load_schools(gender)
    sc = next((s for s in schools if s.name == school_name), None) if school_name \
        else schools[0]
    if sc is None:
        print(f"school {school_name!r} not found for {gender}"); return
    print(f"\nschool: {sc.name} ({gender}) — ident {sc.ident!r} key {sc.key!r}")

    # Newest archived season with line scores for this school — the current
    # world year may not have played/archived yet.
    arc_ix, archived = newest_played_season(w["id"], gender, sc.name, latest)
    if not archived:
        print("no archived lines for this school in ANY season — pick one that played")
        return
    season_year = wd.BASE_YEAR + arc_ix + 1
    print(f"comparing season {season_year} (archive year index {arc_ix})")
    print(f"archived varsity line names ({len(archived)}): "
          f"{sorted(archived)[:8]}{' …' if len(archived) > 8 else ''}")

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
