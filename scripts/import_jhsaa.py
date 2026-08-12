#!/usr/bin/env python3
"""
Build the JHSAA — Jefferson's high-school tennis association — from `prep-network`.

Writes `data/jhsaa/schools.json`: every Jefferson school that sponsors tennis, with its
classification, city/county/area, mascot, colours, and its DISTRICT for each gender.

Two things this does NOT do, deliberately:

  * It does not import prep-network's players. That repo supplies INSTITUTIONS; the
    season is played here by this engine with players generated here.
  * It does not inherit prep-network's `sports` flags for tennis. That generator rolled
    `boys-tennis` and `girls-tennis` independently per school, producing 202 boys teams
    against 441 girls and only 117 schools fielding both — 3A alone has 10 boys teams
    and 81 girls. It is an artifact, and it leaves the boys' season unschedulable (20
    one-team leagues). Sponsorship is re-derived below on the real-world pattern.

Sponsorship: girls-sponsoring is the SUPERSET, boys a ~88% subset of it. Schools that
field girls tennis but not boys are common; the reverse essentially does not happen.
Co-op programs are not modelled — single schools only.

Districts: prep-network's 99 conferences are all-sport geographic groupings and 92 of
them span classifications, so they shatter when filtered to one class and to tennis
sponsors. Tennis draws its own map the way Oregon does — balanced districts of <= 12 per
classification, geographically contiguous, named for their dominant area (falling through
to the dominant county when that area name is already used in the same classification).

Deterministic: seeded, so two runs are identical. Idempotent.

    python3 scripts/import_jhsaa.py [--prep-network ../prep-network] [--dry-run]

See docs/DESIGN-jhsaa-high-school-season.md.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_OUT_DIR = os.path.join(_REPO, "data", "jhsaa")
_OUT = os.path.join(_OUT_DIR, "schools.json")

SEED = 11
MAX_DISTRICT = 12

# Girls sponsorship rate by classification; boys is a subset of the girls sponsors.
# 2A and 1A are deliberately well above a realistic sponsorship rate (owner rule
# 2027-08). Splitting 3A-1A into two championships left 2A-1A with 18 programs and an
# 8-team state field — 44% of the classification making state, which is not a
# tournament. The fix the owner chose is more programs rather than a smaller field —
# and then MORE again: 2A/1A sponsor at rates no real state would post, because a
# huge, ragged small-school classification is the fun of it. The talent bands say
# what the level is; the roster count says how much of it there is to watch.
GIRLS_RATE = {"7A": 0.85, "6A": 0.70, "5A": 0.55, "4A": 0.35,
              "3A": 0.26, "2A": 0.78, "1A": 0.62}
BOYS_OF_GIRLS = 0.88

# Schools the owner wants in the association without giving them an archetype. The
# archetype seed list is folded in automatically — see `always_sponsor`.
ALWAYS_EXTRA = [
    "Abbey Prep",
    "Annie Springs",
    "Arrieta Treasure Valley",
    "Aurelia",
    "Bahía Leal",
    "Baptist HS",
    "Beacon Hill",
    "Breakwater",
    "Calderwood School",
    "Caswell Depot High",
    "Central Christian",
    "Chaminade",
    "Commonwealth",
    "Condotti Vanguard Academy",
    "Cortland",
    "Crown Hill",
    "Dolores Huerta",
    "Dry Lake",
    "Eastmont Christian",
    "Echevarria Foundry High",
    "Elk Bluff",
    "Elk Crossing",
    "Emerson",
    "Ferris Union",
    "Fort Valois",
    "Gagarin School of Public Service",
    "Galena",
    "George Washington Carver",
    "Gold Junction",
    "Golden Gate",
    "Gwendolyn Brooks",
    "Halfway House",
    "Harlan Cole",
    "Hazel Bennett",
    "High Prairie",
    "Homestead",
    "Jean Lindgren",
    "Keldale",
    "Las Palmas",
    "Lorraine Calder",
    "Mabryville",
    "Marlow County",
    "Mesa Dorada",
    "Montelago",
    "Netherwood",
    "New Leiden",
    "Newark River North",
    "North Valley Christian",
    "Pacific Friends School",
    "Paul Robeson",
    "Pinecrest School",
    "Port Meridian Polytechnic",
    "Port Meridian West",
    "Providence Academy",
    "Puerto Gallego",
    "Ransom Spur",
    "Redwood Coast",
    "Romero-Finniski",
    "Saint Francis",
    "San Borondón",
    "San Cordero",
    "San Tomás",
    "Santa Cruz del Norte",
    "Santa Laura",
    "Santa Laura North",
    "Seafarer High",
    "Selbyville",
    "Silver Glen",
    "Sisters of Mercy",
    "Snowline",
    "St. Agnes Academy",
    "St. Basil Academy",
    "St. Gabriel Preparatory",
    "St. Isidore",
    "St. Norbert Abbey",
    "St. Perpetua",
    "St. Sebastian Prep",
    "St. Vincent School",
    "Steelbridge",
    "Summervale Northwest",
    "Svenja Ekström",
    "Telfair Country Day School",
    "Three Saints",
    "Timberline",
    "Treasure Valley",
    "Trinity Catholic",
    "Valderra",
    "Valley Christian",
    "Westover",
    "Westside Christian",
    "Winifred Booker",
]

# Championship groups. 3A stands ALONE and 2A/1A combine (owner rule 2027-08): the
# enrollment gap across the old 3A-1A group was the widest in the association — medians
# of 1,043 / 385 / 199 — so a 1,370-student school and a 108-student one were competing
# for the same trophy.
# ⚠️ RECLASSIFICATION (owner rule 2027-08). prep-network's 2A holds 88 schools and its
# 1A 111, so a combined 2A-1A dwarfed 3A's 140 — 151 tennis sponsors against 46. States
# readjust their enrollment cutoffs all the time, and this is that: the largest 2A schools
# move up to 3A, which balances the two smallest championships without splitting 2A from
# 1A (the owner does not want separate 2A and 1A tennis).
#
# By ENROLLMENT, because that is what a classification IS. Nothing here looks at who
# sponsors tennis or at how good anybody is.
PROMOTE_2A_ABOVE = 430          # 2A schools at or above this enrollment become 3A


def reclassify(schools: list[dict]) -> int:
    moved = 0
    for s in schools:
        if s["classification"] == "2A" and s.get("enrollment", 0) >= PROMOTE_2A_ABOVE:
            s["classification"] = "3A"
            moved += 1
    return moved


def champ_group(classification: str) -> str:
    return classification if classification in ("7A", "6A", "5A", "4A", "3A") else "2A-1A"


GROUPS = ("7A", "6A", "5A", "4A", "3A", "2A-1A")


def _load(prep: str) -> tuple[list[dict], dict[str, dict]]:
    orgs = os.path.join(prep, "records", "orgs")
    sp, cp = os.path.join(orgs, "schools.json"), os.path.join(orgs, "cities.json")
    for p in (sp, cp):
        if not os.path.exists(p):
            sys.exit(f"not found: {p}\nPoint --prep-network at a prep-network checkout.")
    with open(sp, encoding="utf-8") as fh:
        schools = json.load(fh)["schools"]
    with open(cp, encoding="utf-8") as fh:
        cities = json.load(fh)
    cities = cities["cities"] if isinstance(cities, dict) else cities
    return schools, {c["name"]: c for c in cities}


def always_sponsor() -> set[str]:
    """Schools that sponsor tennis because the OWNER says they do.

    ⚠️ Sponsorship below is a seeded coin flip per school against a per-classification
    rate — a reasonable way to pick ~335 tennis programs out of Jefferson's 840 schools,
    and a terrible way to decide whether a school the owner has named as a blue blood
    exists. Forty of the first seventy-eight archetype nominations landed outside the
    roll, which reads as "your list is wrong" when the truth is that a dice roll had
    already voted on it.

    So a named school is always in. Sourced from `data/jhsaa/archetypes.json` (the
    archetype seed list) plus `ALWAYS_EXTRA` for schools the owner wants in the
    association without tagging them. Names are matched accent- and punctuation-
    insensitively against prep-network, which is the source of truth for what exists."""
    out = set(ALWAYS_EXTRA)
    arch = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "jhsaa", "archetypes.json")
    try:
        with open(arch, encoding="utf-8") as fh:
            out |= set(json.load(fh).get("programs", {}))
    except (FileNotFoundError, ValueError):
        pass
    return out


def _key(name: str) -> str:
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def sponsors(schools: list[dict]) -> tuple[set[str], set[str]]:
    """(girls, boys) school names. One roll for girls; boys drawn from that set — except
    that owner-named schools are in regardless, for both genders."""
    rng = random.Random(SEED)
    forced = {_key(n) for n in always_sponsor()}
    girls, boys = set(), set()
    for s in sorted(schools, key=lambda s: s["name"]):        # stable order = stable draw
        hit = rng.random() < GIRLS_RATE[s["classification"]]  # drawn either way, so the
        sub = rng.random() < BOYS_OF_GIRLS                    # roll stays reproducible
        if _key(s["name"]) in forced:
            girls.add(s["name"])
            boys.add(s["name"])
        elif hit:
            girls.add(s["name"])
            if sub:
                boys.add(s["name"])
    return girls, boys


def draw_districts(pool: list[dict], cities: dict) -> dict[str, str]:
    """school name -> district name, for ONE classification group.

    Sorted by area → county → city so a district is geographically contiguous, then cut
    into the fewest balanced blocks of <= MAX_DISTRICT."""
    def county(s):
        return cities.get(s["city"], {}).get("county", "?")

    pool = sorted(pool, key=lambda s: (s["area"], county(s), s["city"], s["name"]))
    n = len(pool)
    if not n:
        return {}
    k = max(1, -(-n // MAX_DISTRICT))
    size = -(-n // k)
    out, used = {}, set()
    for i in range(k):
        block = pool[i * size:(i + 1) * size]
        if not block:
            continue
        # name for the dominant area, else the dominant county, else a numbered fallback
        cands = [f"{Counter(s['area'] for s in block).most_common(1)[0][0]} District"]
        cands += [f"{c} District"
                  for c, _ in Counter(county(s) for s in block).most_common()]
        name = next((c for c in cands if c not in used),
                    f"{block[0]['area']} {len(used) + 1} District")
        used.add(name)
        for s in block:
            out[s["name"]] = name
    return out


def build(schools: list[dict], cities: dict) -> list[dict]:
    moved = reclassify(schools)
    girls, boys = sponsors(schools)
    by_name = {s["name"]: s for s in schools}
    dist = {"girls": {}, "boys": {}}
    for g in GROUPS:
        for gender, pool_names in (("girls", girls), ("boys", boys)):
            pool = [by_name[n] for n in pool_names
                    if champ_group(by_name[n]["classification"]) == g]
            dist[gender].update(draw_districts(pool, cities))
    out = []
    for name in sorted(girls | boys):
        s = by_name[name]
        city = cities.get(s["city"], {})
        out.append({
            "name": name,
            "city": s["city"],
            "county": city.get("county", ""),
            "area": s["area"],
            "classification": s["classification"],
            "group": champ_group(s["classification"]),
            "enrollment": s["enrollment"],
            "private": s["private"],
            "mascot": s["mascot"],
            "colors": s["colors"],
            "girls": name in girls,
            "boys": name in boys,
            "girls_district": dist["girls"].get(name, ""),
            "boys_district": dist["boys"].get(name, ""),
        })
    return out


def report(rows: list[dict]) -> None:
    print(f"{'group':8}{'girls':>7}{'boys':>7}{'G dists':>9}{'B dists':>9}")
    for g in GROUPS:
        rs = [r for r in rows if r["group"] == g]
        gi = [r for r in rs if r["girls"]]
        bo = [r for r in rs if r["boys"]]
        print(f"{g:8}{len(gi):>7}{len(bo):>7}"
              f"{len({r['girls_district'] for r in gi}):>9}"
              f"{len({r['boys_district'] for r in bo}):>9}")
    gi = [r for r in rows if r["girls"]]
    bo = [r for r in rows if r["boys"]]
    print(f"{'TOTAL':8}{len(gi):>7}{len(bo):>7}")
    print(f"  {len(rows)} schools sponsor tennis; "
          f"{len(gi) - len(bo)} girls-only, {len([r for r in rows if r['boys'] and not r['girls']])} boys-only")
    # A district is keyed by (group, gender, name) — the same place name is reused
    # across classifications, exactly as "6A-1 PIL" and "5A-1 PIL" would be in Oregon.
    for gender, key in (("girls", "girls_district"), ("boys", "boys_district")):
        sizes = Counter((r["group"], r[key]) for r in rows if r[gender])
        big = [k for k, v in sizes.items() if v > MAX_DISTRICT]
        print(f"  {gender}: {len(sizes)} districts, sizes {min(sizes.values())}-{max(sizes.values())}"
              + (f"  OVERSIZED: {big}" if big else ""))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prep-network",
                    default=os.path.join(os.path.dirname(_REPO), "prep-network"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    schools, cities = _load(args.prep_network)
    rows = build(schools, cities)
    report(rows)
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    os.makedirs(_OUT_DIR, exist_ok=True)
    with open(_OUT, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_doc": ["JHSAA tennis-sponsoring schools with per-gender districts.",
                     "Generated by scripts/import_jhsaa.py from prep-network's",
                     "records/orgs/. Sponsorship is RE-DERIVED, not inherited —",
                     "see that script's docstring and",
                     "docs/DESIGN-jhsaa-high-school-season.md."],
            "schools": rows,
        }, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {os.path.relpath(_OUT, _REPO)}")


if __name__ == "__main__":
    main()
