#!/usr/bin/env python3
"""Every out-of-state affiliate, and every school in 9A/8A/Group 1, must
sponsor BOTH girls' and boys' tennis (owner rule 2027-08).

Fixes 15 girls-only schools that slipped through: 4 affiliates (a leftover
from the affiliate script inheriting a girls-only donor's sponsorship
pattern instead of the owner's flat "both" rule for the new tier), plus 8
in 9A, 3 in 8A, 8 in Group 1 that were girls-only from import.

Purely additive — every one of these rows ALREADY carries a `boys_district`
identical to its `girls_district` (leagues are drawn once per classification
over the girls-inclusive superset, so a boys-eligible slot already exists;
see CLAUDE.md "BOYS AND GIRLS ALWAYS SHARE A LEAGUE"). Flipping `boys` to
True therefore needs no league redraw — the seat was already reserved, just
not fielded.

Deliberately leaves FULLY RETIRED donor rows alone (both girls AND boys
False — e.g. "Crow Basin", "Emigrant", the RETIRE_AND_REPLACE donors this
session sunset) — the rule is about programs that compete, not about
reactivating a program the owner already retired.

    python3 scripts/jhsaa_dual_gender_parity.py [--dry-run]
"""
import argparse
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")

TARGET_GROUPS = {"9A", "8A", "Group 1"}


def needs_fix(r: dict) -> bool:
    """A LIVE single-gender school in scope — not a fully retired donor."""
    in_scope = bool(r.get("state")) or r.get("group") in TARGET_GROUPS
    if not in_scope:
        return False
    girls, boys = bool(r.get("girls")), bool(r.get("boys"))
    return (girls or boys) and not (girls and boys)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    schools = doc["schools"]

    fixed = []
    for r in schools:
        if not needs_fix(r):
            continue
        before = (r.get("girls", False), r.get("boys", False))
        r["girls"] = True
        r["boys"] = True
        fixed.append((r["name"], r.get("state") or r.get("group"), before))

    print(f"{len(fixed)} schools brought to both genders:")
    for name, scope, before in fixed:
        print(f"  {name} ({scope}): was girls={before[0]} boys={before[1]}")

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
