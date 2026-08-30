#!/usr/bin/env python3
"""The 2056 move-up slate (owner list, 2026-08): 25 programs promoted to refill
the depleted top classes — above all 9A, which the closure batch left at 64/64
sponsors against the 40-field's 76 floor.

    python3 scripts/jhsaa_2056_promotions.py [--dry-run]

22 schools go to 9A (64/64 -> 86/86, matching 8A and clearing the floor), plus
the owner's marked exceptions: Evans Larsen Day and Baptist to 7A, Minnesota
City to 8A. This is a RECLASSIFICATION, not a play-up (the Lower Lake /
RECLASSIFY_TO_2A idiom): `classification`, `group` AND `enrollment` move
together — the association is saying these schools now ARE that size, and the
number follows the decision. Each incoming school's enrollment is spaced into
the target class's observed live band (25th-90th percentile), preserving the
batch's own relative-stature ordering; nothing else on the row moves.

Leagues are NOT assigned here — a district is `(classification, name)`, so
every affected class is redrawn immediately after through
`scripts/jhsaa_redistrict.py --cap 10` (the owner's 7-10 league preference).
Run the two together; a moved school's stale league field is meaningless until
the redraw lands.

Idempotent: keyed assignments; a school already at its target is skipped.
Replay after a full re-import (and after `jhsaa_2056_closures.py`, whose
sunsets this slate is the counterweight to).
"""
import argparse
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")

# display name -> target class. The owner's list, names resolved against the
# committed data (Wells = Ida B. Wells, Mondale = Walter Mondale, Banneker =
# Benjamin Banneker, "Telfair County Day" = Telfair Country Day, San Tomás).
MOVES = {
    # -> 9A (22)
    "De La Salle": "9A", "Ida B. Wells": "9A", "Arrieta": "9A",
    "Coolidge": "9A", "Cliffside": "9A", "Trinity Catholic": "9A",
    "Santa Laura": "9A", "Black Springs": "9A", "Arroyo Verde": "9A",
    "Westside Christian": "9A", "Harrisburgh": "9A",
    "Telfair Country Day": "9A", "Jimmy Carter": "9A", "Tidewater": "9A",
    "Walter Mondale": "9A", "San Tomás": "9A", "Jersey City": "9A",
    "Mater Dei": "9A", "Benjamin Banneker": "9A", "Commonwealth": "9A",
    "William Henry Harrison": "9A", "Thurgood Marshall": "9A",
    # the owner's marked exceptions
    "Evans Larsen Day": "7A", "Baptist": "7A",
    "Minnesota City": "8A",
}


def _band(rows, group):
    """The target class's observed live enrollment band, 25th-90th pct."""
    v = sorted(r["enrollment"] for r in rows
               if r["group"] == group and (r.get("girls") or r.get("boys"))
               and r["name"] not in MOVES)
    return v[len(v) // 4], v[int(len(v) * 0.9)]


def apply(rows: list[dict]) -> list[str]:
    log = []
    by_name = {r["name"]: r for r in rows}
    for name in MOVES:
        if name not in by_name:
            raise SystemExit(f"MOVES names a school the data does not have: {name}")
    for target in sorted(set(MOVES.values())):
        batch = [by_name[n] for n, t in MOVES.items() if t == target
                 if by_name[n]["group"] != target]
        if not batch:
            continue
        lo, hi = _band(rows, target)
        # Relative stature survives the move: the batch is spaced across the
        # band in its own current-enrollment order (the COMPETITIVE_MOVES
        # idiom — the number follows the decision, ordering is the owner's
        # only signal worth keeping).
        batch.sort(key=lambda r: r["enrollment"])
        for i, r in enumerate(batch):
            enr = round(lo + (hi - lo) * (i + 1) / (len(batch) + 1))
            log.append(f"promoted: {r['name']} {r['classification']} -> {target} "
                       f"(enroll {r['enrollment']} -> {enr})")
            r["classification"] = r["group"] = target
            r["enrollment"] = enr
    # ‼️ NO GIRLS-ONLY PROGRAMS AT THE 8A/9A LEVEL (owner rule 2026-08): the
    # JHSAA mandates both teams in its two deepest classes. A RULE, not a
    # name list, so it holds over whatever this script (or a later batch)
    # moves in; `import_jhsaa.sponsors()` enforces the same mandate at import
    # and `test_no_girls_only_programs_at_8a_9a` pins the committed data.
    for r in rows:
        if r["group"] in ("8A", "9A") and r.get("girls") and not r.get("boys"):
            r["boys"] = True
            log.append(f"boys team (8A/9A mandate): {r['name']} ({r['group']})")
    return log


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    log = apply(doc["schools"])
    for line in log:
        print(line)
    if not log:
        print("nothing to do (already applied)")
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nwrote {_DATA}")


if __name__ == "__main__":
    main()
