#!/usr/bin/env python3
"""Put the affiliates that share a place into ONE league, and rescue the one
whose league is geographically impossible (owner rules, 2026-08).

    "all the Bend schools should be together is the biggest thing,
     preferably in 8A"          "and all the wyoming schools should be together"
    "they can be in a league with other jefferson schools - they should be!"
    "geography matters more than size here"   "the enrollments don't matter"

‼️ THIS IS NOT "ONE STATE, ONE LEAGUE". That reading was wrong and the owner
corrected it: **Baker is deliberately left where it is** — Baker City is 180 miles
from Bend, and Baker already sits 66 miles from a league-mate with "plenty of Idaho
and other Jefferson schools near it". The rule is that programs in the SAME PLACE
must not be split, not that a state border makes a league. Peregrine (Boise) is a
single school and needs nothing; Money and Spring Harvest are already together.

WHAT MOVES, and why only this much. Measured against real coordinates
(prep-network's `records/orgs/cities.json` + the gazetteer's 2046 Great Basin
table), most affiliates are NOT what makes their league wide — the league was
already that wide among its Jefferson members, so moving them fixes nothing:

    affiliate            league span   without it   the affiliate adds
    Baker                274           274            0 mi   <- left alone
    Bend Senior/
      Mountain View/
      Summit             268           268            0 mi
    Caldera              276           276            0 mi
    Money/Spring Harvest 105           100            5 mi   <- already together
    Peregrine            370           348           23 mi   <- left alone
    Lower Lake           462           268          194 mi   <- the broken one

  1. THE FOUR BEND SCHOOLS -> 8A, together, in a league with Jefferson schools.
     They were split across two groups (Bend Senior / Mountain View / Summit in
     6A's Cascade Divide, Caldera in 7A's Timber Valley), and a league is
     `(classification, name)` — so schools in different GROUPS cannot share one
     however close they stand. Uniting them is therefore a group move, not a
     re-lettering.
     ‼️ `group` ONLY, never `classification` — the documented play-up mechanism.
     `_TALENT` reads `classification`, so moving both would hand them 8A talent as
     a reward for being relocated; moving `group` alone means they play UP into a
     harder field and earn it, which is what the owner means by "schools play up
     all the time in my leagues". Enrollment is untouched: "the enrollments don't
     matter", and 8A's band is 378-2143 anyway, which already contains all four.

  2. ROCK SPRINGS -> Group 2, joining Green River and Jackson Hole in Olympic.
     The Wyoming three were split by group, and TWO of them were already in
     Olympic — so exactly one school has to move, not three. Rock Springs' nearest
     league-mate goes 94 mi -> 14 mi (Green River, the next town over and its real
     rival), and its 519-mile outlier is gone. Same `group`-only rule as above.

  3. LOWER LAKE -> Valle Vista, a plain league move inside 5A. The worst case in
     the association: 462-mile span and its NEAREST league-mate 223 miles away, so
     it had no plausible local rival at all. Valle Vista: 157 / 103.

  4. FIVE JEFFERSON 8A SCHOOLS join the Bend league. The Bend four must land
     somewhere, and every live 8A league already holds 10-11 of a 12 cap — so
     rather than shove four into one and breach it, this revives SUNKIST LEAGUE,
     which is empty: its only row is Crow Basin, a RETIRE_AND_REPLACE donor that
     sponsors neither sport (it keeps its row and its page, per `former_school`).
     8A goes from 85 schools in 8 leagues to 89 in 9 — closer to DISTRICT_TARGET
     10, not further. Donors are picked nearest-first and **no donor may fall
     below 9**, so the pull is spread rather than gutting one league.

    python3 scripts/jhsaa_affiliate_leagues.py [--dry-run]
"""
import argparse
import ast
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")
_CITIES = "/home/user/prep-network/records/orgs/cities.json"

MAX_DISTRICT = 12          # import_jhsaa.MAX_DISTRICT — a CAP, never a target
MIN_DONOR = 9              # a donor league may not be left thinner than this
BEND_LEAGUE = "Sunkist League"

#: Affiliates that must share a league, and the group that league lives in.
#: The group is stated because a league is `(classification, name)`: schools in
#: different groups cannot share one, so "together" implies a group.
TOGETHER = {
    "8A": (["Bend Senior", "Mountain View", "Summit", "Caldera"], BEND_LEAGUE),
    "Group 2": (["Rock Springs", "Green River", "Jackson Hole"], "Olympic League"),
}
#: Single-school league moves — no group change, just a better home.
RELEAGUE = {"Lower Lake": ("5A", "Valle Vista League")}

#: Real coordinates for the affiliate towns; prep-network only maps Jefferson.
AFFILIATE_COORD = {
    "Bend": (44.0582, -121.3153), "Baker City": (44.7749, -117.8344),
    "Boise": (43.6150, -116.2023), "Lower Lake": (38.9110, -122.6147),
    "Ukiah": (39.1502, -123.2078), "Rock Springs": (41.5875, -109.2029),
    "Green River": (41.5286, -109.4662), "Jackson": (43.4799, -110.7624),
    "Money": (41.5500, -112.3000), "Spring Harvest": (41.7000, -112.1500),
}


def coords():
    """town -> (lat, lon), over both places the map is anchored in."""
    out = {c["name"]: (c["lat"], c["lon"])
           for c in json.load(open(_CITIES, encoding="utf-8"))["cities"]}
    src = open(os.path.join(_HERE, "jefferson_gazetteer.py"), encoding="utf-8").read()
    blk = src[src.index("_EXPANSION_2046_PLACES = ["):]
    blk = blk[:blk.index("\n]") + 2]
    for name, _c, _a, _r, lat, lon, _p in ast.literal_eval(blk.split("=", 1)[1].strip()):
        out.setdefault(name, (lat, lon))
    out.update(AFFILIATE_COORD)
    return out


def miles(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    x = (math.sin((la2 - la1) * p / 2) ** 2
         + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2)
    return 7917.5 * math.asin(math.sqrt(x))


def size(rows, group, league, gender):
    return sum(1 for r in rows
               if r.get("group") == group and r.get(f"{gender}_district") == league
               and r.get(gender))


def place(r, league):
    """A league belongs to the SCHOOL — both gender fields move together, or the
    program is in two different leagues."""
    r["girls_district"] = league
    r["boys_district"] = league


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"]
    byname = {r["name"]: r for r in rows}
    CO = coords()

    # ‼️ SNAPSHOT WHAT MUST NOT MOVE. `classification` is the talent basis and no
    # school's may change here; asserted after, because a pass that quietly
    # re-tiered a program would look exactly like a successful run.
    frozen = {r["name"]: r.get("classification") for r in rows}

    for group, (names, league) in TOGETHER.items():
        print(f"{group} / {league}:")
        for n in names:
            r = byname.get(n)
            if r is None:
                sys.exit(f"no school named {n!r}")
            if not r.get("state"):
                sys.exit(f"{n!r} is not an out-of-state affiliate")
            was = f"{r['group']} / {r['girls_district']}"
            r["group"] = group          # group ONLY — never classification
            place(r, league)
            print(f"   {n:15} {was:34} -> {group} / {league}")

    for n, (group, league) in RELEAGUE.items():
        r = byname[n]
        if r["group"] != group:
            sys.exit(f"{n!r} is in {r['group']!r}, expected {group!r}")
        print(f"{group} / {league}:\n   {n:15} {r['girls_district']:34} -> {league}")
        place(r, league)

    # Fill the revived Bend league with the nearest Jefferson 8A schools, spread so
    # that no donor league drops below MIN_DONOR.
    bend = CO["Bend"]
    cand = sorted((miles(bend, CO[r["city"]]), r["name"])
                  for r in rows
                  if r.get("group") == "8A" and not r.get("state") and r.get("girls")
                  and r.get("girls_district") != BEND_LEAGUE and CO.get(r["city"]))
    print(f"8A / {BEND_LEAGUE} — Jefferson members:")
    taken = 0
    for d, n in cand:
        r = byname[n]
        src = r["girls_district"]
        if min(size(rows, "8A", src, g) for g in ("girls", "boys")) - 1 < MIN_DONOR:
            continue
        place(r, BEND_LEAGUE)
        taken += 1
        print(f"   {n:24} {d:5.0f} mi   from {src} -> "
              f"{size(rows, '8A', src, 'girls')}")
        if taken == 5:
            break

    after = {r["name"]: r.get("classification") for r in rows}
    drift = sorted(n for n in frozen if frozen[n] != after[n])
    if drift:
        sys.exit(f"classification changed for {drift} — refusing to write")
    print(f"\nclassification unchanged for all {len(rows)} schools")

    for group in ("8A", "Group 2", "5A"):
        for lg in sorted({r.get("girls_district") for r in rows
                          if r.get("group") == group and r.get("girls_district")}):
            for g in ("girls", "boys"):
                n = size(rows, group, lg, g)
                if n > MAX_DISTRICT:
                    sys.exit(f"{group} {lg} {g} is {n}, over MAX_DISTRICT {MAX_DISTRICT}")
    print("every touched group is within MAX_DISTRICT 12")

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
