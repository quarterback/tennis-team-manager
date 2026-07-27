"""
Repair an EXISTING save: make every service-academy roster American.

The citizenship gate (ncaa.SERVICE_ACADEMIES — Army / Navy / Air Force / Coast
Guard / Merchant Marine take US citizens ONLY) fixes generation and every
placement pipeline, but a save built BEFORE the fix already has its year-0
rosters persisted in `world_roster`, so it keeps whatever internationals it
generated. This script naturalizes them in place.

It rewrites ONLY the nationality-facing fields — name, country, domestic flag,
hometown, high school, region, secondary flag, homecooking. Every rating, grade,
class year, scholarship and pid is left exactly as it was, so the player is the
same tennis player with an American identity: no lineup churn, no team-strength
drift, no broken career history / injury rows / lineup pins (all keyed by pid).
That is precisely what generation would have produced, since nationality and
talent are drawn independently (see docs/AAR-base-roster-nationality-by-level.md).

Deterministic: the replacement identity is seeded from the pid, so re-running is
idempotent and two runs on the same save produce the same names.

Usage:
    python3 scripts/naturalize_academy_rosters.py            # dry run — list only
    python3 scripts/naturalize_academy_rosters.py --apply    # rewrite the rows
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import dbpath
from app.dbpath import resolve_db_path
from app.ncaa import SERVICE_ACADEMIES, is_domestic_player
from app.world import prospect_from_dict, prospect_to_dict

# (table, school column, data column) — every persisted place a rostered academy
# player's serialized Prospect lives. `world_graduates` covers alumni pages;
# `world_signing` covers a class signed but not yet intaken.
TABLES = (
    ("world_roster", "school", "data"),
    ("world_signing", "school", "data"),
)


def _pid_seed(pid: str) -> int:
    """Stable per-player seed, so the same save always naturalizes to the same
    identity (idempotent re-runs, no name churn between runs)."""
    return int(hashlib.sha256(f"naturalize|{pid}".encode()).hexdigest()[:8], 16)


def _naturalize(p, gender: str):
    """Give `p` an American identity, leaving every rating untouched."""
    from generators import make_name_picker, random_town, roll_high_school
    from app.ncaa import _pick_gender
    seed = _pid_seed(p.pid)
    rng = random.Random(seed)
    name_fn = make_name_picker(random.Random(seed ^ 0x5EED),
                               gender=_pick_gender(gender), region_weights={"us": 1.0})
    name, _country = name_fn()
    city, st = random_town(rng)
    p.name = name
    p.country = "US"
    p.domestic = True
    p.secondary_country = ""
    p.hometown = f"{city}, {st}"
    p.high_school = roll_high_school("US", rng, state=st, home_city=city)
    p.region = st
    # Internationals carry homecooking 0.0 (no schools near home); an American kid
    # has a real home pull. Draw it the same way generate_prospect does.
    p.homecooking = round(rng.random() ** 1.4, 3)
    return p


def _rewrite(conn, table, data_col, rowid, p, gender, label, apply) -> bool:
    """Naturalize one serialized row in place. Returns True if it needed it."""
    if is_domestic_player(p):
        return False
    was = f"{p.name} ({p.country})"
    _naturalize(p, gender or "men")
    print(f"  {table}: {label:22} {was:32} → {p.name} ({p.hometown})")
    if apply:
        conn.execute(f"UPDATE {table} SET {data_col}=? WHERE rowid=?",
                     (json.dumps(prospect_to_dict(p)), rowid))
    return True


def main(argv):
    apply = "--apply" in argv
    path = resolve_db_path()
    conn = dbpath.connect(path)
    print(f"DB: {path}")
    total = fixed = 0
    academy_pids: set[str] = set()
    for table, school_col, data_col in TABLES:
        try:
            rows = conn.execute(
                f"SELECT rowid, year, gender, {school_col} AS school, pid, "
                f"{data_col} AS data FROM {table}").fetchall()
        except Exception as exc:                     # table absent in an old save
            print(f"  skip {table}: {exc}")
            continue
        for r in rows:
            if r["school"] not in SERVICE_ACADEMIES:
                continue
            total += 1
            academy_pids.add(r["pid"])
            try:
                p = prospect_from_dict(json.loads(r["data"]))
            except Exception as exc:
                print(f"  !! {table} rowid={r['rowid']} unreadable: {exc}")
                continue
            fixed += _rewrite(conn, table, data_col, r["rowid"], p, r["gender"],
                              f"{r['school']} y{r['year']}", apply)
    # Alumni: world_graduates has no school column, so match the academy pids we
    # just collected — an academy grad's alumni page must read American too.
    grads = 0
    try:
        rows = conn.execute("SELECT rowid, year, gender, pid, data "
                            "FROM world_graduates").fetchall()
    except Exception:
        rows = []
    for r in rows:
        if r["pid"] not in academy_pids:
            continue
        try:
            p = prospect_from_dict(json.loads(r["data"]))
        except Exception:
            continue
        grads += _rewrite(conn, "world_graduates", "data", r["rowid"], p,
                          r["gender"], f"grad y{r['year']}", apply)
    print(f"\n{total} academy roster rows scanned, {fixed} international "
          f"(+{grads} graduate rows).")
    if not (fixed or grads):
        print("Nothing to do — every academy player is already American.")
    elif apply:
        conn.commit()
        print(f"Naturalized {fixed + grads} row(s). Restart the app to clear warm caches.")
    else:
        print("Dry run — re-run with --apply to rewrite these rows.")
    conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])
