#!/usr/bin/env python3
"""The 2026-09 Non-Public (10B/11B) membership expansion — owner-approved list.

    python3 scripts/jhsaa_nonpublic_expansion.py [--prep-network PATH] [--dry-run]

Applies `import_jhsaa.EXTRA_SPONSORS` through `scripts/jhsaa_sponsors.py`'s own
`apply`/`redraw` (the importer stays the single authority on WHO sponsors), then
does the two things that script cannot know about:

* A prep-network row's `area` comes through `AREA_RENAMES`, which maps the SOURCE
  areas — and the association has since split Belmonte Metro and Boise Frontier
  off them. A new school takes the area (and county) of the rows already standing
  in its town, never the source's.
* ONE fictional program, owner rule 2026-09 ("alderwold gets an 8A school"):
  Alderwold has a single 9A, a single 8A and nothing at 7A; prep-network holds no
  absent 8A there, so this is the one school the expansion invents. Name is the
  owner's to change.

Redraws every touched class plus 8A. Idempotent.
"""
import argparse
import collections
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")


def _mod(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ALDERWOLD_8A = {
    "name": "Antler Valley", "city": "Blackpine", "county": "Antler", "area": "Alderwold",
    "classification": "8A", "group": "8A", "enrollment": 1950, "private": False,
    "mascot": "Timberwolves", "colors": ["#1f4e3d", "#c9a227"],
    "girls": True, "boys": True, "girls_district": "", "boys_district": "",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prep-network", default=os.path.join(os.path.dirname(_REPO), "prep-network"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    m = _mod("import_jhsaa")
    sp = _mod("jhsaa_sponsors")
    src, cities = m._load(args.prep_network)
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"]
    town = {}
    for r in rows:
        town.setdefault(r["city"], (r["county"], r["area"]))

    added, gained, dropped, groups = sp.apply(rows, m, src, cities)
    def _neighbour_league(r):
        # A placeholder the redraw's name-inheritance can read; the redraw reassigns it.
        for scope in ("city", "county", "area"):
            for x in rows:
                if x is not r and x.get("girls") and x["group"] == r["group"] \
                        and x.get(scope) == r.get(scope) and x.get("girls_district"):
                    return x["girls_district"]
        return next(x["girls_district"] for x in rows
                    if x.get("girls") and x["group"] == r["group"] and x.get("girls_district"))
    for r in added:
        if not r.get("girls_district"):
            r["girls_district"] = r["boys_district"] = _neighbour_league(r)
        if r["city"] in town:
            r["county"], r["area"] = town[r["city"]]
        else:
            sys.exit(f"new school in a town the association does not know: {r['name']} / {r['city']}")
    if not any(r["name"] == ALDERWOLD_8A["name"] for r in rows):
        rows.append(dict(ALDERWOLD_8A))
        rows[-1]["girls_district"] = rows[-1]["boys_district"] = _neighbour_league(rows[-1])
        added.append(rows[-1])
        groups.add("8A")
    rows.sort(key=lambda r: r["name"])
    # ‼️ REDRAW THROUGH `app.jhsaa_districting`, NOT `import_jhsaa.draw_districts`.
    # The importer's draw walks prep-network's geographic ORDER, which the 2052
    # affiliates (Oregon/Washington/Idaho rows) are not in — a first pass through it
    # scattered the Columbia Gorge and Blue Mountain leagues across Belmonte and Gold
    # Valley and left a two-team league behind. The reclassification redraw works on
    # real coordinates with the association's floor (8) and cap (11), which is what
    # every offseason cycle already uses. A row that gained a gender keeps its league
    # UNLESS that league no longer exists in its class (two 5A privates still named a
    # league that is 9A's now), in which case its class is redrawn too.
    counts = collections.Counter((r["group"], r.get("girls_district", "")) for r in rows if r.get("girls"))
    for r, _ in gained:
        if counts[(r["group"], r["girls_district"])] < 4:
            groups.add(r["group"])
    sys.path.insert(0, _REPO)
    os.environ.setdefault("TENNIS_DB_PATH", os.path.join(_REPO, ".jhsaa_expansion_scratch.db"))
    from app import jhsaa_districting as jd
    notes = jd.redraw_classes(rows, sorted(groups))
    for cls, ns in notes.items():
        for n in ns:
            print(f"  {cls}: {n.strip()}")

    for r in added:
        print(f"  + {r['name']:28} {r['classification']:>7} {r['enrollment']:5} "
              f"{'P' if r['private'] else 'pub':3} {r['city']:16} {r['area']:18} {r['girls_district']}")
    for r, g in gained:
        print(f"  ± {r['name']:28} {r['classification']:>7} now {g}")
    print(f"{len(added)} added, {len(gained)} genders gained; redrew {', '.join(sorted(groups))}; {len(rows)} rows")
    over = {(g, k): v for g in ("girls", "boys")
            for k, v in collections.Counter((r["group"], r[f"{g}_district"]) for r in rows if r.get(g)).items()
            if v > jd.districting_config().MAX_DISTRICT}
    if over:
        sys.exit(f"district over MAX_DISTRICT after redraw: {over}")
    if args.dry_run:
        print("--dry-run: nothing written"); return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False); fh.write("\n")
    print("wrote", _DATA)


if __name__ == "__main__":
    main()
