#!/usr/bin/env python3
"""Redraw the leagues of chosen classifications — membership, count and names.

    python3 scripts/jhsaa_redistrict.py 8A 7A 6A [--dry-run] [--prep-network PATH]

‼️ WHAT IS WRONG THAT THIS FIXES. A district is cut from a geographic ORDER (area →
county → city) into blocks of `MAX_DISTRICT`. That keeps most leagues tight and dumps
the REMAINDER — whatever is left once the metros have filled their own blocks — into
leagues that are geographic leftovers rather than regions. Measured across 6A/7A/8A,
ten leagues spanned more than 250 miles and the worst three about 400: a "league"
whose members are four hours apart is not a league, and its members play a schedule
nobody would drive.

‼️ LEAGUES REALIGN **AND REBRAND** (owner rule 2026-08). The first version of this
script held the names fixed as an absolute — it kept exactly the leagues a class had
and only moved schools between them. That is half the rule. Real associations redraw
on a cycle and names come and go with the map: the OSAA runs a four-year
classification-and-districting period, and its 2026-30 redraw did not merely reshuffle
membership, it created a brand-new seven-team 6A/5A **Southwest Hybrid** out of
Ashland, Crater and Eagle Point beside Grants Pass, Roseburg and the two Medfords.
So a block still INHERITS the name it most overlaps — a league keeps its historical
core, which is what makes a realignment read as a realignment — but a class that
gains leagues draws new names from `LEAGUE_NAMES`, and a class that loses them
retires names. The bank is the authority on what a league may be called; the
alignment is the authority on how many there are.

‼️ AND STRICT GEOGRAPHY IS NOT THE CONSTRAINT (same rule). Distance is a cost, not a
rule: the OSAA puts Bend's schools in leagues that involve real driving, and the
Southwest Hybrid above spans two classifications precisely because the geography left
no tidy answer. The redraw minimises span, but SIZE wins — a league near
`DISTRICT_TARGET` with one distant member is a better league than a tight one with
six, because district size IS the schedule here.

‼️ BOYS AND GIRLS ALWAYS SHARE A LEAGUE. A league belongs to the SCHOOL, so membership
is decided once per school and both gender fields are written from it.

‼️ RIVALRIES ARE NEVER SPLIT. A rivalry outranks geography exactly as it outranks
reclassification: after clustering, any pair sitting in different leagues is repaired
by moving one to join the other, swapping out that league's most distant member so no
league is pushed past `MAX_DISTRICT`.

Only the classifications named on the command line are touched. Everything else —
other classes, enrollments, names, sponsorship — is left exactly as it is.
"""
import argparse
import collections
import importlib.util
import json
import math
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")
_SEED = 20260822          # fixed: a redistricting must be reproducible


def _import_jhsaa():
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The clustering lives in the app now (`app/jhsaa_districting.py`) so the in-app
# reclassification can redraw leagues with the same algorithm; this script keeps
# its CLI and its printing and imports the functions.
sys.path.insert(0, _REPO)
from app.jhsaa_districting import (_miles, _span, cluster, balance,  # noqa: E402,F401
                                   keep_rivals, spill, redistrict as _redistrict)


def redistrict(rows, cls, pos, m, rng, cap=None):
    return _redistrict(rows, cls, pos, m, rng, cap=cap, log=print)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("classes", nargs="+", help="classifications to redraw, e.g. 8A 7A 6A")
    ap.add_argument("--prep-network",
                    default=os.path.join(os.path.dirname(_REPO), "prep-network"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cap", type=int, default=None,
                    help="pack leagues to this size instead of MAX_DISTRICT "
                         "(e.g. 10 for the owner's preferred 7-10 leagues)")
    args = ap.parse_args()

    m = _import_jhsaa()
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"] if isinstance(doc, dict) else doc
    with open(os.path.join(args.prep_network, "records", "orgs", "cities.json"),
              encoding="utf-8") as fh:
        cities = json.load(fh)
    cities = cities["cities"] if isinstance(cities, dict) else cities
    pos = {m.CITY_RENAMES.get(c["name"], c["name"]): (c["lat"], c["lon"]) for c in cities}

    rng = random.Random(_SEED)
    moved_total = 0
    for cls in args.classes:
        # Live sponsors only, matching the redraw pool: a sunset row keeps its
        # last-known league label but plays no league season, so counting it
        # here inflates league sizes and can fail the MAX_DISTRICT check on
        # schools that will never take the court.
        members = [r for r in rows if r["group"] == cls
                   and (r.get("girls") or r.get("boys"))]
        if not members:
            sys.exit(f"no programs in {cls}")
        before = collections.defaultdict(list)
        for r in members:
            before[r["girls_district"]].append(r)
        assign, placed, notes = redistrict(rows, cls, pos, m, rng, cap=args.cap)

        after = collections.defaultdict(list)
        for r in members:
            after[assign.get(r["name"], r["girls_district"])].append(r)
        moved = sum(1 for r in members if assign.get(r["name"], r["girls_district"])
                    != r["girls_district"])
        moved_total += moved

        def spans(d):
            return sorted((_span([pos[x["city"]] for x in v if x["city"] in pos]), k)
                          for k, v in d.items())
        b, a = spans(before), spans(after)
        print(f"\n== {cls}: {len(members)} programs, {len(before)} leagues — "
              f"{moved} schools change league")
        print(f"   span  worst {b[-1][0]:.0f} -> {a[-1][0]:.0f} mi · "
              f"mean {sum(x for x, _ in b)/len(b):.0f} -> {sum(x for x, _ in a)/len(a):.0f} mi · "
              f"over 250mi {sum(1 for x, _ in b if x > 250)} -> {sum(1 for x, _ in a if x > 250)}")
        for note in notes:
            print(note)
        for span, name in reversed(a):
            areas = collections.Counter(x["area"] for x in after[name])
            print(f"   {span:6.0f} mi  {name:<40} {len(after[name]):2}  {dict(areas)}")
        over = {k: len(v) for k, v in after.items() if len(v) > m.MAX_DISTRICT}
        if over:
            sys.exit(f"{cls}: league over MAX_DISTRICT after redraw: {over}")
        for r in members:
            new = assign.get(r["name"])
            if new:
                r["girls_district"] = r["boys_district"] = new

    print(f"\n{moved_total} schools changed league in total")
    if args.dry_run:
        print("--dry-run: nothing written")
        return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_DATA}")


if __name__ == "__main__":
    main()
