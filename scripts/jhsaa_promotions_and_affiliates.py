#!/usr/bin/env python3
"""Two more one-time transforms over the committed `data/jhsaa/schools.json`,
same shape as `jhsaa_heritage_valley.py`.

    python3 scripts/jhsaa_promotions_and_affiliates.py [--dry-run]

PART A -- 11 schools promote to 8A. A real RECLASSIFICATION (moves BOTH
`classification` AND `group`, per the `RECLASSIFY_TO_2A` precedent), not a
play-up or competitive-move: geography, mascot, colors, enrollment, private
status and history all stay untouched.

PART B -- JHSAA admits its first out-of-state affiliate members, the way
OSAA/WIAA/CIF/Arizona/Nevada admit border schools for geography and
proximity. Same RETIRE_AND_REPLACE pattern as `jhsaa_heritage_valley.py`: the
donor's sponsorship goes off (row stays -- `former_school` precedent), and a
brand-new school with real out-of-state geography takes its classification/
group and sponsorship pattern. Unlike the Heritage Valley replacements, these
13 carry REAL geography (real city/county/state) -- never a fictional
Jefferson county -- and a new `state` field on the row marks them as
out-of-state for display purposes (`app/jhsaa.py`'s `School.state`).
`area` is set for INTERNAL geographic clustering only (district/league draws
still need something to sort on) and is chosen for real-world adjacency to
the existing Jefferson footprint, per `docs/GAZETTEER-jefferson.md`:
Boise Frontier borders Ada County, ID (Peregrine School); Cascade Divide
(Cinder/Siskiyou CA -- Tamarack/Klamath OR) borders the Bend/Baker City/
Ukiah/Lower Lake corridor; Bear River Country is the same real Wyoming/Utah
ground this session's Heritage Valley migration already stood the Group
system on, so its five geographic affiliates (Rock Springs, Green River,
Jackson Hole, Spring Harvest, Money) join there. `area` is NEVER displayed
for an affiliate school -- only its real city/state are.
"""
import argparse
import collections
import hashlib
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")

# ============================================================================
# PART A -- 11 promotions to 8A.
# ============================================================================
PROMOTIONS = [
    "Vespertine", "Covenant", "Cook City", "Ditch Fork", "Olive Head",
    "Olivet County", "Plainfield", "Paddock County", "Bardsley County",
    "Mesa Dorada", "Crater View",
]

# ============================================================================
# PART B -- 13 out-of-state affiliate replacements.
# ============================================================================
_MASCOT_POOL = ["Bulldogs", "Trojans", "Prospectors", "Reapers", "Timberwolves"]
_COLOR_PAIRS = [
    ("#4b2e83", "#ffffff"), ("#0c2340", "#a5acaf"), ("#5c1a1a", "#e0dcd0"),
    ("#2d4a2d", "#f0e6c8"), ("#3a2a1c", "#d9a441"),
]


def _stable(seed: str, pool: list):
    h = hashlib.blake2s(seed.encode("utf-8")).digest()
    return pool[int.from_bytes(h[:4], "big") % len(pool)]


AFFILIATES = {
    # donor -> replacement spec. classification/group inherited from donor.
    "Mountain House": {
        "name": "Peregrine School", "city": "Boise", "county": "Ada",
        "state": "Idaho", "area": "Boise Frontier", "private": True,
        "mascot": "Falcons", "colors": ["#1a2332", "#8ba3c7"],
    },
    "Copperview": {
        "name": "Baker High", "city": "Baker City", "county": "Baker",
        "state": "Oregon", "area": "Cascade Divide", "private": False,
        "mascot": "Bulldogs", "colors": ["#4b2e83", "#ffffff"],
    },
    "Meadowbrook": {
        "name": "Lower Lake High", "city": "Lower Lake", "county": "Lake",
        "state": "California", "area": "Cascade Divide", "private": False,
        "mascot": "Trojans", "colors": ["#0b6e4f", "#ffffff"],
    },
    "Shenango": {
        "name": "Bend Senior High", "city": "Bend", "county": "Deschutes",
        "state": "Oregon", "area": "Cascade Divide", "private": False,
        "mascot": "Lava Bears", "colors": ["#000000", "#f47c20"],
    },
    "Bahía Vista": {
        "name": "Mountain View High", "city": "Bend", "county": "Deschutes",
        "state": "Oregon", "area": "Cascade Divide", "private": False,
        "mascot": "Cougars", "colors": ["#1c5e3c", "#ffffff"],
    },
    "Empire Milling": {
        "name": "Summit High", "city": "Bend", "county": "Deschutes",
        "state": "Oregon", "area": "Cascade Divide", "private": False,
        "mascot": "Storm", "colors": ["#1a1a4d", "#a5acaf"],
    },
    "Junction": {
        "name": "Caldera High", "city": "Bend", "county": "Deschutes",
        "state": "Oregon", "area": "Cascade Divide", "private": False,
        "mascot": "Wolfpack", "colors": ["#5c1a2e", "#000000"],
    },
    "Crow Basin": {
        "name": "Ukiah High", "city": "Ukiah", "county": "Mendocino",
        "state": "California", "area": "Cascade Divide", "private": False,
        "mascot": "Wildcats", "colors": ["#1c3f5f", "#ffd200"],
    },
    "Emigrant": {
        "name": "Rock Springs High", "city": "Rock Springs", "county": "Sweetwater",
        "state": "Wyoming", "area": "Bear River Country", "private": False,
        "mascot": "Tigers", "colors": ["#f47c20", "#000000"],
    },
    "St. Gabriel Academy": {
        "name": "Green River High", "city": "Green River", "county": "Sweetwater",
        "state": "Wyoming", "area": "Bear River Country", "private": False,
        "mascot": "Wolves", "colors": ["#1c5e3c", "#ffd200"],
    },
    "Harrow": {
        "name": "Jackson Hole High", "city": "Jackson", "county": "Teton",
        "state": "Wyoming", "area": "Bear River Country", "private": False,
        "mascot": "Broncs", "colors": ["#0c2340", "#ffffff"],
    },
    "Buckhorn": {
        "name": "Spring Harvest", "city": "Spring Harvest", "county": "Box Elder",
        "state": "Utah", "area": "Bear River Country", "private": False,
        "mascot": "Reapers", "colors": ["#3a2a1c", "#d9a441"],
    },
    "Mirage Siding Regional": {
        "name": "Money", "city": "Money", "county": "Box Elder",
        "state": "Utah", "area": "Bear River Country", "private": False,
        "mascot": "Prospectors", "colors": ["#5c4a1c", "#c9a961"],
    },
}


def _import_jhsaa():
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _jhsaa():
    sys.path.insert(0, _REPO)
    os.environ.setdefault("TENNIS_DB_PATH", os.path.join(_REPO, ".jhsaa-tmp.db"))
    from app import jhsaa
    return jhsaa


def apply_promotions(rows: dict) -> set:
    """The 11 reclassifications. Returns the set of source classes touched
    (for the forced redraw), since PROMOTIONS itself only carries names."""
    touched = set()
    missing = []
    for name in PROMOTIONS:
        s = rows.get(name)
        if s is None:
            missing.append(name)
            continue
        touched.add(s["classification"])
        s["classification"] = s["group"] = "8A"
    if missing:
        sys.exit(f"PROMOTIONS names {len(missing)} school(s) that do not exist: {missing}")
    touched.add("8A")
    return touched


_DONOR_SPONSORSHIP: dict[str, tuple[bool, bool]] = {}


def capture_sponsorship(rows: dict) -> None:
    for old in AFFILIATES:
        d = rows.get(old)
        if d is not None:
            _DONOR_SPONSORSHIP[old] = (d["girls"], d["boys"])


def apply_affiliates(schools: list[dict], rows: dict) -> set:
    """The 13 sunset-and-replace affiliates. Returns the set of classes
    touched (for the forced redraw -- membership COUNT is unchanged per
    class, but geography moved from fictional Jefferson ground to real
    out-of-state ground, which a league-count check alone can't see)."""
    alias_sources = {s["source"] for s in schools if "source" in s}
    touched = set()
    missing = []
    for old_name, spec in AFFILIATES.items():
        donor = rows.get(old_name)
        if donor is None:
            missing.append(old_name)
            continue
        touched.add(donor["classification"])
        donor["girls"] = False
        donor["boys"] = False
        new_name = spec["name"]
        if new_name in rows or new_name in alias_sources:
            sys.exit(f"affiliate name {new_name!r} collides with an existing "
                     f"school name or former-name alias")
        s = {
            "name": new_name,
            "source": new_name,  # no prep-network origin, real geography
            "city": spec["city"],
            "county": spec["county"],
            "area": spec["area"],          # internal clustering ONLY, never displayed
            "state": spec["state"],        # real state -- marks this an affiliate
            "classification": donor["classification"],
            "group": donor["group"],
            "enrollment": donor["enrollment"],
            "private": spec["private"],
            "mascot": spec["mascot"],
            "colors": list(spec["colors"]),
            "girls": _DONOR_SPONSORSHIP[old_name][0],
            "boys": _DONOR_SPONSORSHIP[old_name][1],
            "girls_district": "",
            "boys_district": "",
        }
        schools.append(s)
        rows[new_name] = s
        alias_sources.add(new_name)
    if missing:
        sys.exit(f"AFFILIATES names {len(missing)} school(s) that do not exist: {missing}")
    return touched


def redraw_touched(schools: list[dict], m, touched: set) -> None:
    """Force a redraw for every class in `touched`, exactly the
    `jhsaa_heritage_valley.redraw_all_groups` idiom -- a class's league
    COUNT can stay right while its membership (or, for the affiliates, its
    geography) goes stale, so `touched` classes are never gated on the
    count-match check."""
    cities = {s["city"]: {"county": s["county"]} for s in schools}
    by_group = collections.defaultdict(list)
    for s in schools:
        if s["girls"] or s["boys"]:
            by_group[s["group"]].append(s)
    league = {}
    for g in touched:
        pool = by_group.get(g, [])
        if not pool:
            continue
        league.update(m.draw_districts(pool, cities, g))
    for s in schools:
        name = s["name"]
        if name in league:
            s["girls_district"] = s["boys_district"] = league[name]


def preflight(schools: list[dict], jh) -> None:
    counts = collections.defaultdict(lambda: [0, 0])
    for s in schools:
        if s["girls"]:
            counts[s["group"]][0] += 1
        if s["boys"]:
            counts[s["group"]][1] += 1
    problems = []
    for g in jh.GROUPS:
        floor = jh.sponsor_floor(g)
        girls, boys = counts.get(g, (0, 0))
        if floor and (girls < floor or boys < floor):
            problems.append((g, girls, boys, floor))
    if problems:
        lines = "\n".join(f"  {g}: girls={gi} boys={bo} floor={fl}"
                          for g, gi, bo, fl in problems)
        print(f"‼️ sponsor_floor NOT cleared for {len(problems)} group(s) -- "
              f"the State qualifying ladder will degrade (sc_head) there:\n{lines}")
    else:
        print("preflight: every group clears its sponsor_floor")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    m = _import_jhsaa()
    jh = _jhsaa()

    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    schools = doc["schools"]
    rows = {s["name"]: s for s in schools}

    capture_sponsorship(rows)
    touched = apply_promotions(rows)
    touched |= apply_affiliates(schools, rows)
    print(f"11 promotions to 8A; {len(AFFILIATES)} out-of-state affiliates; "
          f"redrawing: {sorted(touched)}")

    redraw_touched(schools, m, touched)
    preflight(schools, jh)

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
