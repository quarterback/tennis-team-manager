#!/usr/bin/env python3
"""Apply `import_jhsaa`'s sponsorship tables to the committed `data/jhsaa/schools.json`.

    python3 scripts/jhsaa_sponsors.py [--prep-network PATH] [--dry-run]

‼️ WHAT THIS IS FOR
-------------------
Which schools sponsor tennis is a MAP decision, and the owner makes it by name:
a town with a high school and no tennis program joins the association
(`import_jhsaa.EXTRA_SPONSORS`), a program in a city that already has plenty
leaves it (`NEVER_SPONSOR`). Both tables live in `import_jhsaa`, which stays the
single authority; this script holds no names of its own and is a transform over
the committed file, exactly like `jhsaa_apply_renames.py`.

‼️ A SPONSORSHIP CHANGE REDRAWS THE LEAGUES OF THE CLASSES IT TOUCHES, and that
is not avoidable by being clever. A district is cut from a geographic ORDER into
balanced blocks of <= `MAX_DISTRICT`, so the league a new school belongs in is
whichever block its county falls in — and every such block is already full at 12.
Slotting the school somewhere with a spare seat would put a Timber Valley 1A in a
Gold Valley league to keep an arithmetic invariant. So the affected groups are
redrawn through `import_jhsaa.draw_districts`, the same function the import uses,
over the same geographic order. Groups nobody touched are left exactly as they
are: the draw is per classification and they are independent.

‼️ BOYS AND GIRLS SHARE A LEAGUE (see CLAUDE.md), so the map is drawn ONCE per
classification over the girls-inclusive pool and both gender fields read it.

Idempotent: the tables are keyed on the prep-network SOURCE name, and a row keeps
its source, so a second run finds the same set already applied and writes the same
file.
"""
import argparse
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")


def _import_jhsaa():
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(m, s: dict, cities: dict) -> dict:
    """One association row for a source school — the same shape `build()` emits."""
    town = m.RELOCATIONS.get(s["name"], s["city"])
    city = cities.get(town, {})
    display = m._display_name(m.RENAMES.get(s["name"], s["name"]))
    canonical = m.canon(s["name"])
    return {
        "name": display,
        **({"source": canonical} if canonical != display else {}),
        "city": m.CITY_RENAMES.get(town, town),
        "county": city.get("county", ""),
        "area": m.AREA_RENAMES.get(s["area"], s["area"]),
        "classification": s["classification"],
        "group": m.champ_group(s["classification"]),
        "enrollment": s["enrollment"],
        "private": s["private"] or display in m.PRIVATE_SCHOOLS,
        "mascot": m.MASCOTS.get(display, s["mascot"]),
        "colors": m.COLORS.get(display, s["colors"]),
        "girls": True,
        "boys": True,
    }


def apply(rows: list[dict], m, src: list[dict], cities: dict) -> tuple[list, list, list, set]:
    """Return (added, gained, dropped, groups_touched); `rows` is rebuilt by the caller."""
    by_src = {s["name"]: s for s in src}
    have = {(r.get("source") or r["name"]) for r in rows}

    dropped = [r for r in rows if (r.get("source") or r["name"]) in m.NEVER_SPONSOR]
    keep = [r for r in rows if r not in dropped]

    added, gained = [], []
    for name in sorted(m.EXTRA_SPONSORS):
        if name in have:
            # ‼️ ALREADY A ROW IS NOT ALREADY DONE. `EXTRA_SPONSORS` means "this school
            # sponsors tennis in BOTH genders" — that is what `sponsors()` does with it
            # — and a school can already be in the association on ONE side, which is
            # exactly an EXPANSION program: Minnesota City sponsored girls and lost the
            # boys' sub-roll. Skipping every existing row left the table saying one
            # thing and the data another, and a full re-import would then have silently
            # "added" a boys' team the committed file had never heard of.
            row = next((r for r in keep if (r.get("source") or r["name"]) == name), None)
            if row is not None:
                for g in ("girls", "boys"):
                    if not row.get(g):
                        row[g] = True
                        gained.append((row, g))
            continue
        s = by_src.get(name)
        if s is None:
            sys.exit(f"EXTRA_SPONSORS names a school prep-network does not have: {name}")
        added.append(_row(m, s, cities))

    # A gender GAINED needs no redraw: a league belongs to the SCHOOL (drawn once per
    # classification over the girls-inclusive pool), so the row's district fields are
    # already filled in and the gender's half of that league simply grows by one. Only
    # a row entering or leaving the association changes the cut.
    groups = {r["group"] for r in dropped} | {r["group"] for r in added}
    rows[:] = sorted(keep + added, key=lambda r: r["name"])
    return added, gained, dropped, groups


def redraw(rows: list[dict], m, src: list[dict], cities: dict, groups: set) -> None:
    """Redraw every league in `groups`, over the girls-inclusive pool, in place."""
    by_src = {s["name"]: s for s in src}
    # ‼️ A ROW'S `source` OUTLIVES THE NAME PREP-NETWORK USES. It is the school's
    # stable identity (`canon`), and a handful of them name records prep-network has
    # since renamed away — "Annes Summit" still carries source "Harmon". The draw
    # only reads `name` and `city`, so a row that cannot be resolved back to a
    # source record stands in for itself, with its town mapped back through
    # CITY_RENAMES (the `cities` table is keyed on the SOURCE town).
    back_city = {new: old for old, new in m.CITY_RENAMES.items()}
    for g in sorted(groups):
        pool = []
        for r in rows:
            if r["group"] != g:
                continue
            key = r.get("source") or r["name"]
            back_area = {new: old for old, new in m.AREA_RENAMES.items()}
            pool.append(by_src.get(key) or
                        {"name": key, "city": back_city.get(r["city"], r["city"]),
                         "area": back_area.get(r["area"], r["area"]),
                         "classification": r["classification"]})
        league = m.draw_districts(pool, cities, g)
        for r in rows:
            if r["group"] != g:
                continue
            name = league[r.get("source") or r["name"]]
            r["girls_district"] = r["boys_district"] = name


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prep-network", default=os.path.join(os.path.dirname(_REPO),
                                                           "prep-network"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    m = _import_jhsaa()
    src, cities = m._load(args.prep_network)
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"] if isinstance(doc, dict) else doc

    added, gained, dropped, groups = apply(rows, m, src, cities)
    for r in dropped:
        print(f"  - {r['name']:30} {r['group']:>5} {r['classification']:>3} "
              f"{r['enrollment']:5} {r['city']}")
    for r in added:
        print(f"  + {r['name']:30} {r['group']:>5} {r['classification']:>3} "
              f"{r['enrollment']:5} {r['city']}")
    for row, g in gained:
        league = row.get(f"{g}_district") or "?"
        peers = sum(1 for r in rows if r.get(g) and r["group"] == row["group"]
                    and r.get(f"{g}_district") == league)
        print(f"  ± {row['name']:30} {row['group']:>5} {row['classification']:>3} "
              f"{row['enrollment']:5} {row['city']} — now sponsors {g.upper()} "
              f"({league}, {peers} teams)")
    if groups:
        redraw(rows, m, src, cities, groups)
        print(f"redrew leagues in: {', '.join(sorted(groups))}")
    print(f"{len(added)} added, {len(gained)} gained a gender, "
          f"{len(dropped)} dropped; {len(rows)} programs")

    # A district over MAX_DISTRICT is a longer league season than everyone else
    # plays, so the redraw is checked rather than assumed.
    import collections
    # BOTH halves: a gender gained grows one league's boys' side without touching the
    # girls' cut, so checking only the girls-inclusive pool would not see it.
    over = {(g, k): v for g in ("girls", "boys")
            for k, v in collections.Counter(
                (r["group"], r[f"{g}_district"]) for r in rows if r.get(g)).items()
            if v > m.MAX_DISTRICT}
    if over:
        sys.exit(f"district over MAX_DISTRICT after redraw: {over}")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_DATA}")


if __name__ == "__main__":
    main()
