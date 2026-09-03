#!/usr/bin/env python3
"""The Heritage Valley migration: reallocates 46 current school slots into
eastern Jefferson (Silver Basin / Snake River Plain / Bear River Country) and
a new Port Valdez satellite (Louisville by the Sea), net-zero on the
association's 957 total.

    python3 scripts/jhsaa_heritage_valley.py [--dry-run]

Same shape as `jhsaa_reclassify.py` / `jhsaa_expansion_2046.py`: a one-time
transform over the committed `data/jhsaa/schools.json`, no prep-network
dependency (every arrival's `city`/`county`/`area` is supplied directly by
this script's own tables, the same idiom `jhsaa_expansion_2046.new_school`
uses for a program with no prep-network origin).

‼️ THE 24 INTACT MOVES AND 14 REPLACEMENT SCHOOLS LEAVE THE 1A-9A LADDER
ENTIRELY and join the Great Basin's Group 1/Group 2 system as a THIRD group
(Section 11/12 of the migration guide: "the 24 intact eastern moves and 14
exact sunsets remove these slots from the ladder" and "post-migration eastern
Group pool: 222"). So `classification`/`group` for all 38 eastern arrivals is
NOT copied from the donor slot — it is assigned fresh in `retier_groups()`,
pooled with the CURRENT Group 1 + Group 2 membership (184) and cut into three
enrollment-sorted bands of exactly 74 (222 / 3), matching the guide's "roughly
70-80 per Group" target. The 8 Louisville-by-the-Sea moves are NOT eastern
arrivals — they keep their classification/group untouched, exactly as the
guide's Section 10 specifies ("These schools keep their classification and
history").

‼️ RETIRE_AND_REPLACE TURNS SPONSORSHIP OFF, IT DOES NOT DELETE THE ROW —
the `jhsaa.former_school` / `jhsaa_sponsors.py` precedent (CLAUDE.md: "a
program that stops sponsoring tennis keeps its page"). The retiring
institution's row stays in `data/jhsaa/schools.json` with `girls`/`boys` set
to `False` so its archived seasons and titles remain resolvable; the
replacement is a brand-new row (fresh `source`, mascot, colors — "the new
institution begins with its own... history") that inherits the donor slot's
sponsorship PATTERN, private/public status and enrollment approximately,
never its identity.

‼️ A GUIDE FIGURE CAN BE WRONG WITHOUT THE PLAN BEING WRONG. Section 3's
donor ledger states Halbrook Basin reallocates 12 slots; the per-school
tables in Sections 5/6/10 sum to 11 for Halbrook (5 intact moves + 4 sunsets +
2 Louisville moves). The per-school tables are followed exactly as written;
the 1-school rollup mismatch is a pre-existing inconsistency in the source
document and is not "corrected" by inventing an extra move that section 5
does not name."""
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
# PART A -- the 24 intact moves (Section 5). Each keeps its identity, its
# classification/group is reassigned in retier_groups(), and only geography
# changes here.
# ============================================================================
_SRP_COUNTY = "Minidoka"      # Snake River Plain's new arrivals -- real Idaho
                              # county name, adjoining Raft/Eden, the actual
                              # south-central-Idaho ground Snake River Plain
                              # already stands on.
_SILVER_COUNTY = "Vance"      # reuse the Area's existing dense urban core --
                              # this IS the "Heritage Valley core city" the
                              # guide's hints (Cahaba, Tuscarora, Romare
                              # Bearden...) describe.
_BEAR_COUNTY = "Lincoln"      # new -- real Wyoming county name, adjoining
                              # Star Valley, matching Bear River Country's
                              # existing real-ground convention.
_PORT_VALDEZ_COUNTY = "Valdez"

MOVES = {
    # Snake River Plain -- 14
    "Chillicothe":          {"city": "Chillicothe", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Hagerstown":           {"city": "Hagerstown", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Monongahela":          {"city": "Monongahela", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Natchez":              {"city": "Natchez", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Caney":                {"city": "Caney", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Kingston":             {"city": "Kingston", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Paul Robeson":         {"city": "Boley", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Tallulah Central":     {"city": "Tallulah", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Wyalusing Providence": {"city": "Wyalusing", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Pacific Friends":      {"city": "Okmulgee", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Kishwaukee":           {"city": "Kishwaukee", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Natchez Mercy":        {"city": "Natchez", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Covenant Christian":   {"city": "Tuskegee", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Ella Baker":           {"city": "Langston", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    # Silver Basin -- 8
    "Cahaba":               {"city": "Cahaba", "county": _SILVER_COUNTY, "area": "Silver Basin"},
    "Tuscarora":            {"city": "Tuscarora", "county": _SILVER_COUNTY, "area": "Silver Basin"},
    "Kokomo":               {"city": "Kokomo", "county": _SILVER_COUNTY, "area": "Silver Basin"},
    "Chickasaw":            {"city": "Chickasaw", "county": _SILVER_COUNTY, "area": "Silver Basin"},
    "Romare Bearden":       {"city": "Carden City", "county": _SILVER_COUNTY, "area": "Silver Basin"},
    "Toussaint":            {"city": "Toussaint", "county": _SILVER_COUNTY, "area": "Silver Basin"},
    "Norwood Park":         {"city": "Carden City", "county": _SILVER_COUNTY, "area": "Silver Basin"},
    "Allegheny":            {"city": "Allegheny", "county": _SILVER_COUNTY, "area": "Silver Basin"},
    # Bear River Country -- 2
    "Petoskey":             {"city": "Petoskey", "county": _BEAR_COUNTY, "area": "Bear River Country"},
    "Timberline":           {"city": "Timberline", "county": _BEAR_COUNTY, "area": "Bear River Country"},
}

# ============================================================================
# PART B -- the 14 sunsets and their replacements (Sections 6-7). Keyed on the
# RETIRING school's current name; the replacement uses one of the guide's own
# suggested settlement/school names (Section 7's example list).
# ============================================================================
RETIRE_AND_REPLACE = {
    # Snake River Plain -- 8
    "Saddleback Central":   {"name": "Boley Union",       "city": "Boley",      "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "St. Lucia Academy":    {"name": "Langston Central",  "city": "Langston",   "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Preston Hollow":       {"name": "Hampton Technical", "city": "Hampton",    "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Willowbrook":          {"name": "Nicodemus",         "city": "Nicodemus",  "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Selby Tech":           {"name": "Muskogee",          "city": "Muskogee",   "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Springdale":           {"name": "Quincy Union",      "city": "Quincy",     "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Belden Springs":       {"name": "Eatonville Central","city": "Eatonville", "county": _SRP_COUNTY, "area": "Snake River Plain"},
    "Haverly":              {"name": "Topeka West",       "city": "Topeka",     "county": _SRP_COUNTY, "area": "Snake River Plain"},
    # Silver Basin -- 3
    "Northside Christian":  {"name": "Petersburg High",     "city": "Petersburg", "county": _SILVER_COUNTY, "area": "Silver Basin"},
    "Camas":                {"name": "Richmond Technical",  "city": "Richmond",   "county": _SILVER_COUNTY, "area": "Silver Basin"},
    "Los Alisos":           {"name": "Norfolk Central",     "city": "Norfolk",    "county": _SILVER_COUNTY, "area": "Silver Basin"},
    # Bear River Country -- 3
    "Juniper Crossing":     {"name": "Kearney",         "city": "Kearney", "county": _BEAR_COUNTY, "area": "Bear River Country"},
    "Quillan":              {"name": "Emporia",         "city": "Emporia", "county": _BEAR_COUNTY, "area": "Bear River Country"},
    "Ansotegui Siding":     {"name": "Guthrie Catholic","city": "Guthrie", "county": _BEAR_COUNTY, "area": "Bear River Country"},
}

# ============================================================================
# PART C -- the 8 Louisville-by-the-Sea moves (Section 10). Classification and
# group are UNTOUCHED -- these stay in the 1A-9A ladder, they are not eastern
# Group arrivals.
# ============================================================================
LOUISVILLE = {
    "Tower Grove":               "Tower Grove",
    "Forest Park":                "Forest Park",
    "Chaminade":                  "Kirkwood",
    "Providence Academy":         "St. Matthews",
    "Metropolitan Country Day":   "Ladue",
    "Websterfield":           "Carondelet",
    "St. Sebastian Prep":         "Webster Groves",
    "St. Norbert Abbey":          "Shively",
}

# Ordinary American high-school mascots, same idiom (and bar -- "would a US
# high school put this on a jersey") as `jhsaa_expansion_2046._MASCOT_POOL`.
_MASCOT_POOL = [
    "Statesmen", "Wildcats", "Engineers", "Homesteaders", "Roughriders",
    "Miners", "Hurstons", "Trojans", "Generals", "Ironsides", "Mariners",
    "Pioneers", "Hornets", "Crusaders", "Panthers", "Bears", "Eagles",
    "Wolves", "Rangers", "Prospectors",
]
_COLOR_PAIRS = [
    ("#1c3f5f", "#c9a961"), ("#5c1a1a", "#e0dcd0"), ("#2d4a2d", "#f0e6c8"),
    ("#3a2a1c", "#d9a441"), ("#1a1a2e", "#c0392b"), ("#4a2c40", "#e8d5b7"),
    ("#0f3d3e", "#f2c14e"), ("#5e2129", "#dcd6c9"), ("#22333b", "#c6ac8f"),
    ("#3c1518", "#a9927d"), ("#2b2d42", "#edf2f4"), ("#432818", "#bb9457"),
]


def _import_jhsaa():
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _jhsaa():
    sys.path.insert(0, _REPO)
    os.environ.setdefault("TENNIS_DB_PATH", os.path.join(_REPO, ".heritage-tmp.db"))
    from app import jhsaa
    return jhsaa


def _stable(seed: str, pool: list):
    h = hashlib.blake2s(seed.encode("utf-8")).digest()
    return pool[int.from_bytes(h[:4], "big") % len(pool)]


def apply_moves(rows: dict) -> int:
    """The 24 intact eastern moves: same institution, new geography. Area,
    county, city and locality change; identity, history, mascot, colors,
    enrollment, private status and sponsorship are untouched."""
    n = 0
    unmatched = []
    for name, dest in MOVES.items():
        s = rows.get(name)
        if s is None:
            unmatched.append(name)
            continue
        s["area"] = dest["area"]
        s["county"] = dest["county"]
        s["city"] = dest["city"]
        s.pop("locality", None)
        n += 1
    if unmatched:
        sys.exit(f"MOVES names {len(unmatched)} school(s) that do not exist: "
                 f"{unmatched}")
    return n


def apply_retire_and_replace(schools: list[dict], rows: dict) -> int:
    """Turn OFF sponsorship on the retiring institution (it keeps its row --
    `former_school`'s precedent) and append a brand-new eastern school in the
    donor slot's place, inheriting only its sponsorship pattern, private
    status and enrollment. Fresh name/source/mascot/colors, no history."""
    alias_sources = {s["source"] for s in schools if "source" in s}
    n = 0
    unmatched = []
    for old_name, dest in RETIRE_AND_REPLACE.items():
        donor = rows.get(old_name)
        if donor is None:
            unmatched.append(old_name)
            continue
        # ‼️ RETIRE: sponsorship off, row stays -- the archived seasons this
        # program earned must still resolve through `jhsaa.former_school`.
        donor["girls"] = False
        donor["boys"] = False
        new_name = dest["name"]
        if new_name in rows or new_name in alias_sources:
            sys.exit(f"replacement name {new_name!r} collides with an "
                     f"existing school name or former-name alias")
        s = {
            "name": new_name,
            "source": new_name,  # no prep-network origin
            "city": dest["city"],
            "county": dest["county"],
            "area": dest["area"],
            "classification": donor["classification"],
            "group": donor["group"],
            "enrollment": donor["enrollment"],
            "private": donor["private"],
            "mascot": _stable(f"heritage-valley-mascot|{new_name}", _MASCOT_POOL),
            "colors": list(_stable(f"heritage-valley-colors|{new_name}", _COLOR_PAIRS)),
            # Sponsorship pattern copied from the donor's state BEFORE
            # retirement (captured by `capture_sponsorship`, before girls/
            # boys were zeroed above).
            "girls": _RETIRED_SPONSORSHIP[old_name][0],
            "boys": _RETIRED_SPONSORSHIP[old_name][1],
            "girls_district": "",
            "boys_district": "",
        }
        schools.append(s)
        rows[new_name] = s
        alias_sources.add(new_name)
        n += 1
    if unmatched:
        sys.exit(f"RETIRE_AND_REPLACE names {len(unmatched)} school(s) that do "
                 f"not exist: {unmatched}")
    return n


_RETIRED_SPONSORSHIP: dict[str, tuple[bool, bool]] = {}


def capture_sponsorship(rows: dict) -> None:
    """Snapshot each retiring school's girls/boys sponsorship BEFORE
    `apply_retire_and_replace` zeroes it, so the replacement can inherit the
    donor slot's pattern rather than a flat True/True default."""
    for old_name in RETIRE_AND_REPLACE:
        donor = rows.get(old_name)
        if donor is not None:
            _RETIRED_SPONSORSHIP[old_name] = (donor["girls"], donor["boys"])


def apply_louisville(rows: dict) -> int:
    """The 8 Louisville-by-the-Sea moves: city and locality only.
    Classification, group, area and county are untouched -- these stay in
    the ordinary 1A-9A ladder, they are not eastern Group arrivals."""
    n = 0
    unmatched = []
    for name, locality in LOUISVILLE.items():
        s = rows.get(name)
        if s is None:
            unmatched.append(name)
            continue
        s["area"] = "Port Valdez"
        s["county"] = _PORT_VALDEZ_COUNTY
        s["city"] = "Louisville"
        s["locality"] = locality
        n += 1
    if unmatched:
        sys.exit(f"LOUISVILLE names {len(unmatched)} school(s) that do not "
                 f"exist: {unmatched}")
    return n


def retier_groups(schools: list[dict]) -> None:
    """Pool the CURRENT Group 1 + Group 2 membership (184) with the 38 eastern
    arrivals (24 intact moves + 14 replacements -- NOT the 8 Louisville
    moves, which stay in the ordinary ladder) and cut into three
    enrollment-sorted bands of exactly 74 (222 / 3 -- the guide's own
    "roughly 70-80 per Group" target, landing on an exact split here).
    Enrollment is the primary banding input per Section 12; ties break on
    name for reproducibility."""
    eastern_names = set(MOVES) | {d["name"] for d in RETIRE_AND_REPLACE.values()}
    pool = [s for s in schools
            if s["group"] in ("Group 1", "Group 2") or s["name"] in eastern_names]
    assert len(pool) == 222, f"expected a 222-school Group pool, got {len(pool)}"
    pool.sort(key=lambda s: (-s["enrollment"], s["name"]))
    bands = ("Group 1", "Group 2", "Group 3")
    for i, s in enumerate(pool):
        band = bands[i // 74]
        s["classification"] = s["group"] = band


def redraw_all_groups(schools: list[dict], m, extra_touched: set = frozenset()) -> None:
    """Full redraw for the ladder classes any of the three passes touched
    (the eastern moves/sunsets pull schools OUT of their 1A-9A class,
    Louisville arrivals move city/county within the ladder, and the whole
    Group 1/2/3 pool is entirely new membership) -- exactly the
    `jhsaa_expansion_2046`/`jhsaa_reclassify` idiom: a class whose membership
    OR GEOGRAPHY changed gets `import_jhsaa.draw_districts`, never a partial
    patch.

    ‼️ A CLASS'S LEAGUE *COUNT* CAN STAY RIGHT WHILE ITS LEAGUE *MEMBERSHIP*
    GOES STALE -- `district_count(len(pool))` only asks "does this class
    still want the same NUMBER of leagues", which a class can answer yes to
    while still containing schools whose real location moved out from under
    their old league assignment. 24 MOVES + 14 RETIRE_AND_REPLACE donors
    leave their SOURCE ladder class (their `classification` becomes Group
    1/2/3 in `retier_groups`) without necessarily changing that source
    class's league COUNT, and the 8 Louisville schools change city/county
    WITHOUT leaving their class at all -- three relocated 5A Louisville
    schools stayed split between their old western leagues while a fresh
    `draw_districts` call would put all three together in one eastern
    league, with 5A's league count never having moved. `extra_touched` is
    every class any of the three passes has a school ENTERING OR LEAVING
    (the MOVES/RETIRE_AND_REPLACE donors' ORIGINAL classes, captured in
    `main()` before `retier_groups` overwrites them) or CHANGING GEOGRAPHY
    WITHIN (the LOUISVILLE classes) -- caller-supplied because this function
    only sees the POST-migration `classification`, which is exactly the
    field that no longer names where a mover came from."""
    cities = {s["city"]: {"county": s["county"]} for s in schools}
    # Group 1/2/3 membership is ENTIRELY new (a fresh enrollment sort, not an
    # edit of the old Group 1/2 leagues), so it always redraws regardless of
    # whether its size happens to still fit its old league count.
    touched = {"Group 1", "Group 2", "Group 3"} | set(extra_touched)
    by_group = collections.defaultdict(list)
    for s in schools:
        if s["girls"] or s["boys"]:
            by_group[s["group"]].append(s)
    # Every OTHER class redraws only if its CURRENT league count no longer
    # matches what `district_count` wants for its membership -- the general
    # rule `jhsaa_reclassify.rehome` uses, catching any class this script's
    # `touched` set missed by name.
    league = {}
    for g in m.GROUPS:
        pool = by_group.get(g, [])
        if not pool:
            continue
        have = len({s["girls_district"] for s in pool if s["girls"] and s["girls_district"]})
        if have != m.district_count(len(pool)) or g in touched:
            league.update(m.draw_districts(pool, cities, g))
    for s in schools:
        name = s["name"]
        if name in league:
            s["girls_district"] = s["boys_district"] = league[name]


def preflight(schools: list[dict], jh) -> None:
    """`sponsor_floor` must clear for every group in both genders -- the
    load-bearing invariant CLAUDE.md calls out for any group-membership
    change."""
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
        print(f"‼️ sponsor_floor NOT cleared for {len(problems)} group(s) — "
              f"the State qualifying ladder will degrade (sc_head) there:\n{lines}")


def report(schools: list[dict], jh) -> None:
    areas = collections.Counter(s["area"] for s in schools if s["girls"] or s["boys"])
    print("AREAS:")
    for a, c in sorted(areas.items(), key=lambda x: -x[1]):
        print(f"  {a}: {c}")
    print()
    counts = collections.defaultdict(lambda: [0, 0])
    for s in schools:
        if s["girls"]:
            counts[s["group"]][0] += 1
        if s["boys"]:
            counts[s["group"]][1] += 1
    print("GROUPS:")
    for g in jh.GROUPS:
        gi, bo = counts.get(g, (0, 0))
        print(f"  {g}: girls={gi} boys={bo}")
    active = sum(1 for s in schools if s["girls"] or s["boys"])
    print(f"\n{len(schools)} rows on file, {active} active sponsors")


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
    moved = apply_moves(rows)
    replaced = apply_retire_and_replace(schools, rows)
    relocated = apply_louisville(rows)
    print(f"{moved} intact eastern moves, {replaced} retire-and-replace, "
          f"{relocated} Louisville-by-the-Sea relocations")

    # ‼️ CAPTURED BEFORE `retier_groups` OVERWRITES `classification` for the
    # 38 eastern arrivals -- these are the source 1A-9A classes that LOST a
    # school (MOVES/RETIRE_AND_REPLACE) or CHANGED a member's geography
    # in-class (LOUISVILLE), all of which need a real redraw even when the
    # class's league COUNT still happens to fit (see `redraw_all_groups`).
    touched_classes = {rows[name]["classification"] for name in MOVES if name in rows}
    touched_classes |= {rows[name]["classification"]
                        for name in RETIRE_AND_REPLACE if name in rows}
    touched_classes |= {rows[name]["classification"] for name in LOUISVILLE if name in rows}

    retier_groups(schools)
    redraw_all_groups(schools, m, touched_classes)
    preflight(schools, jh)
    report(schools, jh)

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
