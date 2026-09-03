#!/usr/bin/env python3
"""The border realignment (owner spec, 2026-08): a California 8A district, the
three Wyoming affiliates together in Group 1, and Emigrant County given its own
league instead of being flown to Wyoming and back.

Three separate messes, one cause. An affiliate could only join a league whose
GROUP it already sat in, so the map kept solving "who is nearby" with schools
that merely shared a classification. This moves the group where the geography
says it should be, and every number below is measured from real coordinates
(prep-network `records/orgs/cities.json` + the gazetteer's 2046 Great Basin table).

1. CALIFORNIA — an 8A district, and Mariners League already WAS it.
   Six of the owner's eight (Bardsley County, Paddock County, Olivet County,
   Olive Head, Ditch Fork, Cook City) were already together in Mariners; the
   deliberate county-representation promotions had put them there. So Mariners
   becomes the California district rather than a new league being invented for
   it: Ukiah joins from Summit, Lower Lake from 5A, and the four Mariners members
   that are NOT in that cluster move to their own nearest 8A league (Breakwater
   -> Rim Country 21 mi, Chesapeake -> Narpes 0 mi, Pacific Gate -> Narpes 12 mi,
   Tidegate -> Sunkist 46 mi).

   ‼️ LOWER LAKE IS RECLASSIFIED, NOT FLAGGED (owner: "I would reclassify Lower
   Lake by changing its enrollment, not use the `play_up` flag"). So BOTH
   `classification` and `group` move to 8A and the enrollment moves with them —
   the COMPETITIVE_MOVES rule that the number follows the decision, since the
   numbers are fictional. It is the one school in this pass whose classification
   changes, and the guard below allows exactly that one.
   Why 8A is genuinely the better fit now, not a convenience: the promotions put
   an 8A cluster right on top of it — Bardsley County 30 mi, Paddock County 48,
   Olivet County 74, Olive Head 83, Ditch Fork 85 — while the nearest 7A school
   is Sluice Crossing at 86 mi and Ukiah's nearest 7A is 99+.

2. WYOMING — all three in Group 1 / Ambassador, which is where Rock Springs
   already lived. Green River and Jackson Hole come UP from Group 2 by explicit
   owner override. Ambassador ends as exactly the border district it was trying
   to be: Rock Springs, Green River, Jackson Hole, Rio San Juan (Evanston),
   Cincinnati (Malad City), Irvington (Preston), Utah (Logan), West Oberlin
   (Smithfield) — eight schools along one road.

3. EMIGRANT COUNTY — its own league, which is why nothing else has to move.
   Five Emigrant schools were in Ambassador and three in Olympic, and they were
   the entire reason both leagues sprawled: Ambassador spanned 432 mi and Olympic
   502. The owner asked why they could not simply be their own league; the only
   reason they were not is that a league is `(classification, name)` and they sat
   in two different groups. Put Aurelia, Frontier and Goodman up into Group 1 and
   all eight are one league — **27 miles across**, in two towns (Harriman and
   Aurelia). It costs NO Jefferson school a move, where filling a league around
   them would have displaced four.
   They land in SAGE PLAINS LEAGUE, which was empty — its single row is a
   RETIRE_AND_REPLACE donor sponsoring neither sport (it keeps its row and page
   per `former_school`), the same lever Sunkist gave 8A.

4. OLYMPIC then repairs itself with the two Bridger County schools it should
   always have had (Bridger County Christian, Mountain View WY; Bridger Regional,
   Lyman WY) coming across from Forks — which drops to 9 and keeps Money and
   Spring Harvest together. Nothing is sunset and nothing is invented.

‼️ GROUP-ONLY EVERYWHERE EXCEPT LOWER LAKE. `_TALENT` reads `classification`, so
moving both would hand a relocated school its new class's talent as a reward;
moving `group` alone means it plays UP into a harder field. This is a deliberate
group override and is NOT the seeded `play_up` system — no play-up row is read,
written or disturbed here.

    python3 scripts/jhsaa_border_realignment.py [--dry-run]
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")

MAX_DISTRICT = 12

#: The one reclassification: classification AND group AND enrollment.
#: 1,450 sits inside 8A's 378-2143 band beside its new league-mates (Olive Head
#: 1,423, Ditch Fork 1,462) and above 5A's 1,020 ceiling, so the row cannot read
#: as a 5A school that happens to be pointed at 8A.
RECLASSIFY = {"Lower Lake": ("8A", 1450)}

#: group override -> (new group, league). Classification is untouched.
REGROUP = {
    "Green River": ("Group 1", "Ambassador League"),
    "Jackson Hole": ("Group 1", "Ambassador League"),
    "Rock Springs": ("Group 1", "Ambassador League"),
    "Aurelia": ("Group 1", "Sage Plains League"),
    "Frontier": ("Group 1", "Sage Plains League"),
    "Goodman": ("Group 1", "Sage Plains League"),
}

#: plain league moves inside a group the school already belongs to
RELEAGUE = {
    "Ukiah": ("8A", "Mariners League"),
    "Gravel Narrows": ("Group 1", "Sage Plains League"),
    "Green Valley": ("Group 1", "Sage Plains League"),
    "Harriman": ("Group 1", "Sage Plains League"),
    "Kingsway": ("Group 1", "Sage Plains League"),
    "Ruth Bader Ginsburg": ("Group 1", "Sage Plains League"),
    "Bridger County Christian": ("Group 2", "Olympic League"),
    "Bridger Regional": ("Group 2", "Olympic League"),
    "Breakwater": ("8A", "Rim Country League"),
    "Chesapeake": ("8A", "Narpes Interscholastic League"),
    "Pacific Gate": ("8A", "Narpes Interscholastic League"),
    "Tidegate": ("8A", "Sunkist League"),
}

#: leagues whose exact membership the owner specified — asserted after the move,
#: because a league that quietly gained a ninth member is the failure this pass
#: exists to stop.
EXPECT = {
    ("8A", "Mariners League"): {
        "Lower Lake", "Ukiah", "Bardsley County", "Paddock County",
        "Olivet County", "Olive Head", "Ditch Fork", "Cook City"},
    ("Group 1", "Ambassador League"): {
        "Rock Springs", "Green River", "Jackson Hole", "Rio San Juan",
        "Cincinnati", "Irvington", "Utah", "West Oberlin"},
    ("Group 2", "Olympic League"): {
        "Bonds", "Chicago Island", "Star Valley Catholic", "Star Valley Regional",
        "Timberline", "Hyrum", "Bridger County Christian",
        "Bridger Regional"},
    ("Group 1", "Sage Plains League"): {
        "Gravel Narrows", "Green Valley", "Harriman", "Kingsway",
        "Ruth Bader Ginsburg", "Aurelia", "Frontier", "Goodman"},
}


def place(r, league):
    """Both gender fields together — a league belongs to the SCHOOL."""
    r["girls_district"] = league
    r["boys_district"] = league


def live(rows, group, league, gender):
    return {r["name"] for r in rows
            if r.get("group") == group and r.get(f"{gender}_district") == league
            and r.get(gender)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"]
    byname = {r["name"]: r for r in rows}
    before = {r["name"]: r.get("classification") for r in rows}

    for name, (cls, enroll) in RECLASSIFY.items():
        r = byname[name]
        print(f"RECLASSIFY {name}: {r['classification']} -> {cls}, "
              f"enrollment {r['enrollment']} -> {enroll}")
        r["classification"] = cls
        r["group"] = cls
        r["enrollment"] = enroll
        place(r, "Mariners League")

    print("\nGROUP OVERRIDE (classification untouched — they play up):")
    for name, (group, league) in REGROUP.items():
        r = byname[name]
        print(f"   {name:24} {r['group']:8} -> {group:8}  {r['girls_district']:22} -> {league}")
        r["group"] = group
        place(r, league)

    print("\nLEAGUE MOVE:")
    for name, (group, league) in RELEAGUE.items():
        r = byname[name]
        if r.get("group") != group:
            sys.exit(f"{name!r} is in {r.get('group')!r}, expected {group!r}")
        print(f"   {name:24} {r['girls_district']:34} -> {league}")
        place(r, league)

    after = {r["name"]: r.get("classification") for r in rows}
    drift = sorted(n for n in before if before[n] != after[n])
    if drift != sorted(RECLASSIFY):
        sys.exit(f"classification drifted for {drift}, expected only {sorted(RECLASSIFY)}")
    print(f"\nclassification changed for exactly {drift} — all "
          f"{len(rows) - len(drift)} other schools untouched")

    for (group, league), want in EXPECT.items():
        for gender in ("girls", "boys"):
            got = live(rows, group, league, gender)
            extra, missing = got - want, want - got
            if extra:
                sys.exit(f"{group} {league} {gender} has unexpected {sorted(extra)}")
            if gender == "girls" and missing:
                sys.exit(f"{group} {league} girls is missing {sorted(missing)}")
        print(f"   {group:8} {league:24} = {len(live(rows, group, league, 'girls'))} schools, as specified")

    bad = [r["name"] for r in rows
           if r.get("girls_district") and r.get("boys_district")
           and r["girls_district"] != r["boys_district"]]
    if bad:
        sys.exit(f"genders disagree on a league for {bad}")
    seen = {}
    for r in rows:
        for gender in ("girls", "boys"):
            lg = r.get(f"{gender}_district")
            if lg and r.get(gender):
                seen[(r["group"], lg, gender)] = seen.get((r["group"], lg, gender), 0) + 1
    over = {k: v for k, v in seen.items() if v > MAX_DISTRICT}
    if over:
        sys.exit(f"over MAX_DISTRICT {MAX_DISTRICT}: {over}")
    print(f"no league over {MAX_DISTRICT}; both genders agree everywhere")

    if args.dry_run:
        print("--dry-run: nothing written")
        return
    doc["schools"] = rows
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_DATA}")


if __name__ == "__main__":
    main()
