#!/usr/bin/env python3
"""Cleanup pass on the Heritage Valley migration's RETIRE_AND_REPLACE schools,
plus three unrelated pre-existing duplicate-name fixes flagged in the same
review (owner rule).

    python3 scripts/jhsaa_heritage_valley_renames.py [--dry-run]

PART A -- 14 replacement schools (`jhsaa_heritage_valley.RETIRE_AND_REPLACE`)
templated their names on their city ("Boley Union", "Hampton Technical",
"Petersburg High"...), which reads redundant once the city itself already
carries the identity (owner: "too redundant"). Most simplify to the bare city
name -- the ordinary convention for a single-school town, matching how
"Nicodemus"/"Muskogee"/"Kearney"/"Emporia" (city-named from the start) already
read. Two (Langston Central, Petersburg High) get a genuinely distinct
person-named identity instead (Singleton HS, Clara Brown HS) and are marked
PUBLIC -- an owner style choice for variety in that layer, matching the
person-named-school convention already used elsewhere in the JHSAA (Bayard
Rustin, Octavia Butler, ...). `source` is left untouched on every rename --
it already holds the pre-rename identity string these schools were built
with, and per `jhsaa`'s own rule (CLAUDE.md: "a JHSAA display rename must
stamp `School.source`") that is exactly what must NOT move: `name` is the
display/archive identity, `source` is what seeds the roster.

PART B -- three pre-existing, unrelated schools whose names read as
near-duplicates (a school name embedding its own county's name reads as one
thing twice, the same "Halbrook Basin"/"Halbrook" collision CLAUDE.md
documents for league names) get a full identity replacement: new display
name AND new mascot. Also renames-with-source-preserved, same rule.
"""
import argparse
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")

# old display name -> new display name. Six unchanged (already the bare city
# name) are omitted -- Nicodemus, Muskogee, Kearney, Emporia never needed a
# rename, and are listed here in the docstring, not the table, so an
# unchanged entry can't silently no-op through `rows[old]["name"] = old`.
RENAMES = {
    "Boley Union": "Boley",
    "Langston Central": "Singleton HS",
    "Hampton Technical": "Hampton",
    "Quincy Union": "Quincy",
    "Eatonville Central": "Eatonville",
    "Topeka West": "Topeka",
    "Petersburg High": "Clara Brown HS",
    "Richmond Technical": "Richmond",
    "Norfolk Central": "Norfolk",
    "Guthrie Catholic": "Guthrie",
    # Part B -- pre-existing duplicate-name fixes, name + mascot together.
    "Bardsley County High": "Violet City",
    "Olivet Regional": "Silva",
    "Stagewater County High": "Wong",
}

# Renamed schools that also get a new mascot (Part B only -- Part A keeps
# whatever mascot `jhsaa_heritage_valley._stable` already assigned).
MASCOTS = {
    "Bardsley County High": "Green Orioles",
    "Olivet Regional": "Switchbacks",
    "Stagewater County High": "Herons",
}

# Renamed schools that become PUBLIC (owner rule -- these two carry a
# person's name and an "HS" suffix like a real public school, not the
# private-institution register).
MAKE_PUBLIC = {"Langston Central", "Petersburg High"}


def apply(schools: list[dict]) -> dict:
    rows = {s["name"]: s for s in schools}
    report = {"renamed": [], "remascoted": [], "made_public": [], "missing": []}
    for old, new in RENAMES.items():
        s = rows.get(old)
        if s is None:
            report["missing"].append(old)
            continue
        if new in rows and rows[new] is not s:
            raise SystemExit(f"rename target {new!r} collides with an existing school")
        s["name"] = new
        # `source` is deliberately left untouched -- it already holds the
        # pre-rename identity string (`source == old` for every one of
        # these, since none of them predate this migration by more than the
        # one earlier rename this script performs).
        report["renamed"].append((old, new))
        if old in MASCOTS:
            s["mascot"] = MASCOTS[old]
            report["remascoted"].append((new, MASCOTS[old]))
        if old in MAKE_PUBLIC:
            s["private"] = False
            report["made_public"].append(new)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    schools = doc["schools"]

    report = apply(schools)
    if report["missing"]:
        raise SystemExit(f"RENAMES names {len(report['missing'])} school(s) that do "
                          f"not exist: {report['missing']}")

    print(f"{len(report['renamed'])} renamed, {len(report['remascoted'])} "
          f"remascoted, {len(report['made_public'])} made public")
    for old, new in report["renamed"]:
        print(f"  {old} -> {new}")
    for name, mascot in report["remascoted"]:
        print(f"  {name}: mascot -> {mascot}")
    for name in report["made_public"]:
        print(f"  {name}: now public")

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
