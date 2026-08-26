#!/usr/bin/env python3
"""Strip "High"/"School" off the 11 out-of-state affiliates that still
carried one — the same no-institutional-suffix rule (owner rule 2027-08,
CLAUDE.md) every other JHSAA school follows, missed on the affiliates'
first pass. `source` is left untouched (already the pre-rename identity),
per the standing JHSAA display-rename rule.

    python3 scripts/jhsaa_affiliate_names.py [--dry-run]
"""
import argparse
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")

RENAMES = {
    "Peregrine School": "Peregrine",
    "Baker High": "Baker",
    "Lower Lake High": "Lower Lake",
    "Bend Senior High": "Bend Senior",
    "Mountain View High": "Mountain View",
    "Summit High": "Summit",
    "Caldera High": "Caldera",
    "Ukiah High": "Ukiah",
    "Rock Springs High": "Rock Springs",
    "Green River High": "Green River",
    "Jackson Hole High": "Jackson Hole",
    # Spring Harvest, Money already carry no suffix -- untouched.
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    schools = doc["schools"]
    rows = {s["name"]: s for s in schools}

    missing, renamed = [], []
    for old, new in RENAMES.items():
        s = rows.get(old)
        if s is None:
            missing.append(old)
            continue
        if new in rows and rows[new] is not s:
            raise SystemExit(f"rename target {new!r} collides with an existing school")
        s["name"] = new
        renamed.append((old, new))
    if missing:
        raise SystemExit(f"RENAMES names {len(missing)} school(s) that do not exist: {missing}")

    print(f"{len(renamed)} renamed:")
    for old, new in renamed:
        print(f"  {old} -> {new}")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return

    doc["schools"] = schools
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nwrote {_DATA}")


if __name__ == "__main__":
    main()
