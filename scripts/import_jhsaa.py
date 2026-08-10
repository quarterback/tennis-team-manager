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
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_OUT_DIR = os.path.join(_REPO, "data", "jhsaa")
_OUT = os.path.join(_OUT_DIR, "schools.json")

SEED = 11
MAX_DISTRICT = 12

# Girls sponsorship rate by classification; boys is a subset of the girls sponsors.
GIRLS_RATE = {"7A": 0.85, "6A": 0.70, "5A": 0.55, "4A": 0.35,
              "3A": 0.18, "2A": 0.08, "1A": 0.02}
BOYS_OF_GIRLS = 0.88

# Championship groups — 3A/2A/1A combine, as prep-network's own tennis brackets do.
def champ_group(classification: str) -> str:
    return classification if classification in ("7A", "6A", "5A", "4A") else "3A-1A"


GROUPS = ("7A", "6A", "5A", "4A", "3A-1A")


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


def sponsors(schools: list[dict]) -> tuple[set[str], set[str]]:
    """(girls, boys) school names. One roll for girls; boys drawn from that set."""
    rng = random.Random(SEED)
    girls, boys = set(), set()
    for s in sorted(schools, key=lambda s: s["name"]):        # stable order = stable draw
        if rng.random() < GIRLS_RATE[s["classification"]]:
            girls.add(s["name"])
            if rng.random() < BOYS_OF_GIRLS:
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
