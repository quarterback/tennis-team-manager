#!/usr/bin/env python3
"""Write Jefferson gazetteers — the state's geography, in the association's own names.

    python3 scripts/jefferson_gazetteer.py [--prep-network PATH]

The generator writes both `docs/GAZETTEER-jefferson.md` and the root-level
`GAZETTEERjefferson.md` so the two references cannot drift.

‼️ WHY THIS EXISTS. An agent asked to work on a school has no idea where it is. The
geography lives in `prep-network` (populations, counties, real coordinates) and the
NAMES live here — and the two differ on purpose, because the association renames towns
and areas at emit. So the one document that would answer "where is this school?"
existed in the repo whose names are wrong for the question.

This joins them: prep-network's places, carrying the association's names, with the
programs that actually play in each. It is generated for the same reason the school
list is — renaming is an ongoing pass, and a gazetteer that lags the tables sends a
reader to a town that no longer exists under that name.

‼️ ORIENTATION IS COMPUTED, NOT ASSERTED. "Southern Jefferson is in the south" is the
kind of claim that silently rots when a county moves. Every bearing in the output is
derived from the real coordinates, so it cannot drift from the map.
"""
import argparse
import collections
import importlib.util
import io
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")
_OUTS = (
    os.path.join(_REPO, "docs", "GAZETTEER-jefferson.md"),
    os.path.join(_REPO, "GAZETTEERjefferson.md"),
)


def _import_jhsaa():
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bearing(lat: float, lon: float, mid_lat: float, mid_lon: float) -> str:
    """Where a point sits relative to the state's middle, in plain words."""
    ns = "north" if lat > mid_lat + 0.6 else "south" if lat < mid_lat - 0.6 else ""
    ew = "west" if lon < mid_lon - 0.6 else "east" if lon > mid_lon + 0.6 else ""
    return f"{ns}{ew}" if (ns and ew) else (ns or ew or "central")


# --- 2046 Great Basin expansion (owner rule 2026-08) -------------------------
# The three NEW areas — Silver Basin, Snake River Plain, Bear River Country —
# are NET-NEW Jefferson territory (real Elko NV / south-central & southeast
# Idaho / Cache-Rich UT / Lincoln-Uinta WY ground) with NO prep-network
# counterpart: that repo's cities.json stops at the pre-2046 map. Their places
# are therefore anchored HERE, on real county-seat/town coordinates, and the
# areas are exempted from the two-repo agreement assertion below via
# NET_NEW_AREAS (an allowlist, not a deleted assertion — any OTHER disagreement
# still fails the run). If prep-network ever grows these counties, delete this
# table and the allowlist and let the join take over.
NET_NEW_AREAS = frozenset({"Silver Basin", "Snake River Plain",
                           "Bear River Country"})
_EXPANSION_2046_PLACES = [
    # (name, county, area, real_county, lat, lon, population)
    ("Elko",          "Ruby",        "Silver Basin",       "Elko County, NV",      40.833, -115.763, 20500),
    ("Carlin",        "Ruby",        "Silver Basin",       "Elko County, NV",      40.714, -116.104,  2000),
    ("Wells",         "Ruby",        "Silver Basin",       "Elko County, NV",      41.111, -114.964,  1200),
    ("Jerome",        "Eden",        "Snake River Plain",  "Jerome County, ID",    42.724, -114.518, 12300),
    ("Eden",          "Eden",        "Snake River Plain",  "Jerome County, ID",    42.605, -114.212,   400),
    ("Hazelton",      "Eden",        "Snake River Plain",  "Jerome County, ID",    42.594, -114.135,   750),
    ("Burley",        "Raft",        "Snake River Plain",  "Cassia County, ID",    42.535, -113.793, 11700),
    ("Oakley",        "Raft",        "Snake River Plain",  "Cassia County, ID",    42.243, -113.883,   760),
    ("Malta",         "Raft",        "Snake River Plain",  "Cassia County, ID",    42.305, -113.370,   190),
    ("Malad City",    "Malad",       "Bear River Country", "Oneida County, ID",    42.191, -112.251,  2000),
    ("Preston",       "Cub River",   "Bear River Country", "Franklin County, ID",  42.096, -111.877,  5600),
    ("Franklin",      "Cub River",   "Bear River Country", "Franklin County, ID",  42.013, -111.797,   640),
    ("Weston",        "Cub River",   "Bear River Country", "Franklin County, ID",  42.038, -111.976,   440),
    ("Montpelier",    "Beargrass",   "Bear River Country", "Bear Lake County, ID", 42.322, -111.298,  2500),
    ("Paris",         "Beargrass",   "Bear River Country", "Bear Lake County, ID", 42.227, -111.401,   500),
    ("Georgetown",    "Beargrass",   "Bear River Country", "Bear Lake County, ID", 42.478, -111.371,   470),
    ("Logan",         "Wellsville",  "Bear River Country", "Cache County, UT",     41.737, -111.834, 53000),
    ("Smithfield",    "Wellsville",  "Bear River Country", "Cache County, UT",     41.838, -111.833, 13300),
    ("Hyrum",         "Wellsville",  "Bear River Country", "Cache County, UT",     41.634, -111.852,  8100),
    ("Garden City",   "Laketown",    "Bear River Country", "Rich County, UT",      41.946, -111.394,   560),
    ("Randolph",      "Laketown",    "Bear River Country", "Rich County, UT",      41.665, -111.182,   460),
    ("Laketown",      "Laketown",    "Bear River Country", "Rich County, UT",      41.826, -111.322,   270),
    ("Afton",         "Star Valley", "Bear River Country", "Lincoln County, WY",   42.725, -110.933,  2000),
    ("Alpine",        "Star Valley", "Bear River Country", "Lincoln County, WY",   43.170, -111.020,   800),
    ("Kemmerer",      "Star Valley", "Bear River Country", "Lincoln County, WY",   41.792, -110.538,  2400),
    ("Evanston",      "Bridger",     "Bear River Country", "Uinta County, WY",     41.268, -110.963, 11700),
    ("Lyman",         "Bridger",     "Bear River Country", "Uinta County, WY",     41.327, -110.293,  2100),
    ("Mountain View", "Bridger",     "Bear River Country", "Uinta County, WY",     41.269, -110.336,  1200),
]


def build(m, rows: list[dict], cities: list[dict]) -> str:
    out = io.StringIO()
    w = out.write

    # prep-network's names -> the association's, so every place in this document is
    # the name a reader will actually meet in the app.
    place = {}
    for c in cities:
        place[m.CITY_RENAMES.get(c["name"], c["name"])] = {
            **c,
            "name": m.CITY_RENAMES.get(c["name"], c["name"]),
            "area": m.AREA_RENAMES.get(c["area"], c["area"]),
        }
    # The 2046 Great Basin territory is net-new — prep-network has no rows for
    # it, so its places are anchored locally (see _EXPANSION_2046_PLACES above).
    for name, county, area, realc, lat, lon, pop in _EXPANSION_2046_PLACES:
        place.setdefault(name, {"name": name, "county": county, "area": area,
                                "real_county": realc, "lat": lat, "lon": lon,
                                "population": pop})
    by_town = collections.defaultdict(list)
    for r in rows:
        by_town[r["city"]].append(r)

    # ‼️ THE TWO AREA SETS MUST AGREE. The association's area names come from
    # AREA_RENAMES over prep-network's, and that table is keyed on prep-network's
    # CURRENT name — so when that repo renames an area, the entry stops firing and the
    # committed data (which already holds the right string) hides it until someone runs
    # a full import. Exactly that happened: "Mother Lode" -> Southern Jefferson went
    # dead when prep-network renamed the area to Siskiyou Valley. Comparing the sets
    # here costs nothing and is the only place the drift is visible.
    # NET_NEW_AREAS are exempt: they exist only on the association side, by
    # design — see the allowlist above. Everything else must still agree.
    from_schools = {r["area"] for r in rows} - NET_NEW_AREAS
    from_places = {c["area"] for c in place.values()} - NET_NEW_AREAS
    if from_schools != from_places:
        raise SystemExit(
            "area names disagree — an AREA_RENAMES key has gone stale.\n"
            f"  only in the association: {sorted(from_schools - from_places)}\n"
            f"  only in prep-network:    {sorted(from_places - from_schools)}")

    lats = [c["lat"] for c in place.values()]
    lons = [c["lon"] for c in place.values()]
    mid_lat = (min(lats) + max(lats)) / 2
    mid_lon = (min(lons) + max(lons)) / 2

    areas = collections.defaultdict(list)
    for c in place.values():
        areas[c["area"]].append(c)

    def area_stats(towns):
        pop = sum(t["population"] for t in towns)
        progs = sum(len(by_town.get(t["name"], ())) for t in towns)
        la = sum(t["lat"] for t in towns) / len(towns)
        lo = sum(t["lon"] for t in towns) / len(towns)
        counties = sorted({t["county"] for t in towns})
        return pop, progs, la, lo, counties

    w("# Jefferson — a gazetteer for the tennis association\n\n")
    w("Generated by `scripts/jefferson_gazetteer.py`. **Do not edit this file** — edit\n"
      "the generator, or the tables it reads. Re-run after any town or area rename,\n"
      "beside `jhsaa_name_list.py`.\n\n")
    w("## What this is for\n\n")
    w("Working on a school without knowing where it is produces confident nonsense: a\n"
      "coastal school given a high-desert name, two towns treated as neighbours when\n"
      "they are three hundred miles apart, a league described as regional when its\n"
      "members share nothing. **This is the document to read first.**\n\n")
    w("Jefferson is an alternate-history western state spanning territory in what are\n"
      "present-day Oregon, California, Nevada, Idaho, Utah, and Wyoming. The geography\n"
      "uses real coordinates and recognizable western landscapes, while the state's\n"
      "borders, population distribution, institutions, and settlement hierarchy are\n"
      "counterfactual. Existing fictional settlements remain canon; selected real-world\n"
      "city and place names may also be used where they fit.\n\n")
    w("The generated town tables below reflect the city and school source data currently\n"
      "present in `prep-network` and the JHSAA import. During the eastern expansion pass,\n"
      "new counties and settlements will appear here as those source tables are populated.\n\n")
    w("**‼️ The names here are the ASSOCIATION's.** `prep-network` holds the same places\n"
      "under their original names and the two differ on purpose; that is why a gazetteer\n"
      "read from that repo will not match what you see in the app. Its version has more\n"
      "detail per town — see `prep-network/jefferson_data/REFERENCE.md` — but the wrong\n"
      "names for this question.\n\n")

    w("## Expanded eastern Jefferson and FSAC\n\n")
    w("The expanded eastern territory has **always been part of Jefferson**. This is a\n"
      "retcon of the state's historical footprint, not a future annexation. The added\n"
      "territory corresponds to Elko County in Nevada; Jerome, Cassia, Oneida, Franklin,\n"
      "and Bear Lake counties in Idaho; Cache and Rich counties in Utah; and Lincoln and\n"
      "Uinta counties in Wyoming.\n\n")
    w("High schools in much of this eastern territory historically competed under the\n"
      "**Frontier Schools Athletic Commission (FSAC)** rather than JHSAA. FSAC operated\n"
      "inside Jefferson and awarded its own state championships. After fifteen years of\n"
      "negotiations, FSAC and JHSAA are scheduled to merge five years after the 2041\n"
      "season. A permanent merger condition preserves a separate geographic state title\n"
      "for the former FSAC territory. In tennis that becomes a tenth championship beside\n"
      "1A through 9A; it is geographic rather than enrollment-based. The permanent public\n"
      "name for that championship region is still to be chosen.\n\n")
    w("The prep-network canon for the enlarged state is recorded in\n"
      "`jefferson_data/EXPANSION_CANON.md`, `jefferson_data/REFERENCE.md`, and\n"
      "`jefferson_data/regions.json`.\n\n")

    w("## How the state is organised\n\n")
    w("Four layers, and they are NOT interchangeable:\n\n")
    w("| Layer | What it is | Where it matters |\n|---|---|---|\n")
    w("| **Area** | The state's broad regions. Geography and flavour. | Non-district scheduling, All-Region honours (region-wide and classification-BLIND) |\n")
    w("| **County** | Stands on a real county's ground. | Non-district opponent draw prefers the same county first |\n")
    w("| **Town** (`city`) | Where a school is. | Everything geographic |\n")
    w("| **Locality** | A settlement INSIDE a big city — a CDP, an unincorporated place, an absorbed town. | Display only; the city is unchanged |\n\n")
    w("A **district** (a league) is a fifth thing and is NOT geography: it is drawn per\n"
      "classification over a geographic order and named from an independent bank, so a\n"
      "league name need not describe its members. A district is keyed\n"
      "`(classification, name)` — the same name exists in several classes.\n\n")

    w(f"## The areas — {len(areas)}\n\n")
    w("Bearings are relative to the middle of the state and are derived from the\n"
      "coordinates, not written down by hand.\n\n")
    w("| Area | Where | Counties | Population | Towns | Tennis programs |\n")
    w("|---|---|---|---:|---:|---:|\n")
    for name in sorted(areas, key=lambda a: -area_stats(areas[a])[2]):
        pop, progs, la, lo, counties = area_stats(areas[name])
        w(f"| **{name}** | {_bearing(la, lo, mid_lat, mid_lon)} "
          f"({la:.1f}N, {abs(lo):.1f}W) | {len(counties)} | {pop:,} | "
          f"{len(areas[name])} | {progs} |\n")

    w("\n## Counties\n\n")
    w("| County | Stands on | Area | Population | Towns | Programs |\n")
    w("|---|---|---|---:|---:|---:|\n")
    counties = collections.defaultdict(list)
    for c in place.values():
        counties[c["county"]].append(c)
    for name in sorted(counties):
        ts = counties[name]
        progs = sum(len(by_town.get(t["name"], ())) for t in ts)
        w(f"| {name} | {ts[0]['real_county']} | {ts[0]['area']} | "
          f"{sum(t['population'] for t in ts):,} | {len(ts)} | {progs} |\n")

    w("\n---\n\n# Every town, by area\n\n")
    w("A town with no programs still appears — it is part of the state, and \"does this\n"
      "place exist?\" is a question worth being able to answer. Programs are listed\n"
      "class, enrollment, and locality where the school carries one.\n")
    for name in sorted(areas, key=lambda a: -area_stats(areas[a])[2]):
        pop, progs, la, lo, county_names = area_stats(areas[name])
        w(f"\n## {name}\n\n")
        w(f"*{_bearing(la, lo, mid_lat, mid_lon).capitalize()} Jefferson · "
          f"{', '.join(county_names)} · {pop:,} people · {progs} tennis programs*\n")
        for county in sorted({t["county"] for t in areas[name]}):
            ts = sorted((t for t in areas[name] if t["county"] == county),
                        key=lambda t: -t["population"])
            w(f"\n### {county} County — {ts[0]['real_county']}\n\n")
            for t in ts:
                progs = sorted(by_town.get(t["name"], ()), key=lambda r: -r["enrollment"])
                head = (f"**{t['name']}** — {t['population']:,} · "
                        f"{t['lat']:.2f}N {abs(t['lon']):.2f}W")
                if not progs:
                    w(f"- {head} · *no tennis programs*\n")
                    continue
                w(f"- {head}\n")
                for r in progs:
                    loc = f" · {r['locality']}" if r.get("locality") else ""
                    w(f"    - {r['name']} — {r['classification']}, "
                      f"{r['enrollment']:,}{loc} · {r['girls_district']}\n")
    return out.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prep-network",
                    default=os.path.join(os.path.dirname(_REPO), "prep-network"))
    args = ap.parse_args()

    m = _import_jhsaa()
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"] if isinstance(doc, dict) else doc
    path = os.path.join(args.prep_network, "records", "orgs", "cities.json")
    with open(path, encoding="utf-8") as fh:
        cities = json.load(fh)
    cities = cities["cities"] if isinstance(cities, dict) else cities

    text = build(m, rows, cities)
    for out_path in _OUTS:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {out_path} ({text.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
