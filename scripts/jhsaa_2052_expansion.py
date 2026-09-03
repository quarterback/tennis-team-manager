#!/usr/bin/env python3
"""The 2052 eastern Oregon / Columbia Gorge affiliate expansion (owner rule 2026-08).

    python3 scripts/jhsaa_2052_expansion.py [--dry-run]

‼️ WHAT THIS IS. The JHSAA admits 39 net-new real Oregon/Washington programs by
geographic preference — one 5A league and four 2A districts, boys and girls
aligned identically — plus one net-new Jefferson city (Amelia City, a revived
ghost town, standing on the real Amelia City OR site at 44.3903,-117.6233) whose
9A program joins the Capital Athletic Association. Baker, already an affiliate
(3A, Sky-Em League), moves up into the new 5A Eastern Oregon League and keeps
its name, source and archive intact. 40 invented Jefferson programs are SUNSET
to balance it — owner-named, every one — by the `former_school` mechanism:
flags off, row kept, history reachable forever. Nothing is deleted.

Idempotent: every change is a keyed assignment over the committed file, so a
second run writes the same bytes. `--dry-run` prints the plan and touches
nothing.

‼️ AFFILIATE CONVENTIONS (the Baker/Bend/Rock Springs precedent):
- `state` names the real US state; a Jefferson school has none.
- `county` is the REAL county (Umatilla, Wallowa, Klickitat…), not a Jefferson
  one — the affiliate keeps its own ground even where Jefferson's fictional
  counties stand on the same real earth (Stagewater County IS Malheur County,
  and Fort Valois stands on Ontario's coordinates; the owner admits the real
  towns anyway, and the two ontologies coexist the way Baker has since 2046).
- `source` carries the real institution's name ("Hermiston High"), which keeps
  the roster identity stable if the display name is ever touched.
- Enrollments are VALID JHSAA BAND VALUES, not real figures — the number
  follows the classification decision (the COMPETITIVE_MOVES idiom), preserving
  only the owner's relative-stature ordering within the band.

‼️ NAME NOTES (owner-visible decisions, flagged in the session summary too):
- The 2A district first landed as "Columbia-Blue Mountain District" (the
  owner's "Columbia / Blue Mountain" — a slash cannot live in the
  `/jhsaa/district/<group>/<district>` route segment) and was then renamed
  "Columbia Range League" by the owner in the same session.
- ‼️ TROUT LAKE IS A RELOCATION, NOT A NEW SCHOOL (owner decision 2026-08,
  superseding a same-session San Fernando rename that never reached an
  archive). The real Trout Lake, WA shares its name with the invented
  Jefferson 2A (Rimrock County), and a display name IS the archive identity —
  two rows cannot both hold it. The owner's resolution: the invented program
  RELOCATES to Klickitat County, WA and simply IS the affiliate — same name,
  same archive key, one continuous history, roster identity (and every pid)
  intact. Do not split them back into two schools, and do not re-introduce
  the San Fernando rename: its RENAMES entry was removed as a dead key.
- "Amelia High School" is committed as "Amelia" — school names carry no
  institutional suffix (owner rule 2027-08).

The league seats are OWNER-ASSIGNED, so no `draw_districts` pass runs; the new
districts exist by the rows that name them, exactly as a district always has.
"""
import argparse
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")

EOL = "Eastern Oregon League"            # 5A
CBM = "Columbia Range League"            # 2A — the owner's rename of the batch's
                                         # original "Columbia / Blue Mountain
                                         # District" (whose slash could not live
                                         # in the district route segment anyway)
GRD = "Grande Ronde District"            # 2A
SRD = "Snake River District"             # 2A
CGD = "Columbia Gorge District"          # 2A

BMC = "Blue Mountain Country"            # area: Umatilla/Morrow/Union/Wallowa/Baker/Malheur
GORGE = "Columbia Gorge"                 # area: Wasco/Sherman/Gilliam/Klickitat

# (name, source, city, county, area, state, class, enrollment, mascot, colors, league)
# Mascots are the real programs' where the association's records show them
# (Pendleton Buckaroos, Enterprise Outlaws, Arlington Honkers, Huntington
# Locomotives, Klickitat Vandals…); the handful without a well-known one carry a
# plausible pick the owner can rename.
NEW_SCHOOLS = [
    # --- 5A Eastern Oregon League (Hermiston largest; Pendleton/The Dalles near
    # the top; Umatilla/Riverside/La Grande middle; Baker/Ontario lower end — the
    # owner's stature ordering, mapped into the committed 5A band 806-1020).
    ("Hermiston",    "Hermiston High",    "Hermiston",        "Umatilla",  BMC,   "Oregon", "5A", 1015, "Bulldogs",     ["#0033a0", "#c8102e"], EOL),
    ("Pendleton",    "Pendleton High",    "Pendleton",        "Umatilla",  BMC,   "Oregon", "5A",  990, "Buckaroos",    ["#5b2b82", "#f1b82d"], EOL),
    ("The Dalles",   "The Dalles High",   "The Dalles",       "Wasco",     GORGE, "Oregon", "5A",  975, "Riverhawks",   ["#00205b", "#a2aaad"], EOL),
    ("Umatilla",     "Umatilla High",     "Umatilla",         "Umatilla",  BMC,   "Oregon", "5A",  905, "Vikings",      ["#3b2a82", "#ffb81c"], EOL),
    ("Riverside",    "Riverside High",    "Boardman",         "Morrow",    BMC,   "Oregon", "5A",  885, "Pirates",      ["#000000", "#ffb81c"], EOL),
    ("La Grande",    "La Grande High",    "La Grande",        "Union",     BMC,   "Oregon", "5A",  870, "Tigers",       ["#1d3c34", "#f2a900"], EOL),
    ("Baker",        None,                None,               None,        BMC,   None,     "5A",  830, None,           None,                   EOL),  # existing — moved, not created
    ("Ontario",      "Ontario High",      "Ontario",          "Malheur",   BMC,   "Oregon", "5A",  815, "Tigers",       ["#f47920", "#000000"], EOL),
    # --- 2A Columbia-Blue Mountain District
    ("McLoughlin",   "McLoughlin High",   "Milton-Freewater", "Umatilla",  BMC,   "Oregon", "2A",  360, "Pioneers",     ["#00539f", "#ffd200"], CBM),
    ("Weston-McEwen", "Weston-McEwen High", "Athena",         "Umatilla",  BMC,   "Oregon", "2A",  250, "TigerScots",   ["#00693e", "#ffb81c"], CBM),
    ("Irrigon",      "Irrigon High",      "Irrigon",          "Morrow",    BMC,   "Oregon", "2A",  300, "Knights",      ["#4b306a", "#c0c0c0"], CBM),
    ("Stanfield",    "Stanfield High",    "Stanfield",        "Umatilla",  BMC,   "Oregon", "2A",  220, "Tigers",       ["#f7941d", "#231f20"], CBM),
    ("Echo",         "Echo High",         "Echo",             "Umatilla",  BMC,   "Oregon", "2A",  120, "Cougars",      ["#8a1538", "#d0d3d4"], CBM),
    ("Pilot Rock",   "Pilot Rock High",   "Pilot Rock",       "Umatilla",  BMC,   "Oregon", "2A",  170, "Rockets",      ["#c8102e", "#0033a0"], CBM),
    ("Nixyaawii",    "Nixyaawii Community School", "Pendleton", "Umatilla", BMC,  "Oregon", "2A",   92, "Golden Eagles", ["#8b0000", "#ffd700"], CBM),
    ("Arlington",    "Arlington High",    "Arlington",        "Gilliam",   GORGE, "Oregon", "2A",  110, "Honkers",      ["#00563f", "#f1b82d"], CBM),
    ("Ione",         "Ione High",         "Ione",             "Morrow",    BMC,   "Oregon", "2A",  100, "Cardinals",    ["#c8102e", "#ffffff"], CBM),
    # --- 2A Grande Ronde District
    ("Elgin",        "Elgin High",        "Elgin",            "Union",     BMC,   "Oregon", "2A",  190, "Huskies",      ["#4b0082", "#ffffff"], GRD),
    ("Imbler",       "Imbler High",       "Imbler",           "Union",     BMC,   "Oregon", "2A",  160, "Panthers",     ["#0b0b0b", "#e8c46b"], GRD),
    ("Union",        "Union High",        "Union",            "Union",     BMC,   "Oregon", "2A",  200, "Bobcats",      ["#1e5631", "#ffffff"], GRD),
    ("Cove",         "Cove High",         "Cove",             "Union",     BMC,   "Oregon", "2A",  150, "Leopards",     ["#5b2b82", "#f2f2ee"], GRD),
    ("Powder Valley", "Powder Valley High", "North Powder",   "Union",     BMC,   "Oregon", "2A",  110, "Badgers",      ["#00205b", "#f2a900"], GRD),
    ("Enterprise",   "Enterprise High",   "Enterprise",       "Wallowa",   BMC,   "Oregon", "2A",  210, "Outlaws",      ["#8a1538", "#f1b82d"], GRD),
    ("Wallowa",      "Wallowa High",      "Wallowa",          "Wallowa",   BMC,   "Oregon", "2A",  130, "Cougars",      ["#1d3c34", "#c0c0c0"], GRD),
    ("Joseph",       "Joseph High",       "Joseph",           "Wallowa",   BMC,   "Oregon", "2A",  120, "Eagles",       ["#00337f", "#ffd200"], GRD),
    # --- 2A Snake River District
    ("Nyssa",        "Nyssa High",        "Nyssa",            "Malheur",   BMC,   "Oregon", "2A",  340, "Bulldogs",     ["#5b2b82", "#ffffff"], SRD),
    ("Vale",         "Vale High",         "Vale",             "Malheur",   BMC,   "Oregon", "2A",  300, "Vikings",      ["#00693e", "#ffd200"], SRD),
    ("Four Rivers Charter", "Four Rivers Community School", "Ontario", "Malheur", BMC, "Oregon", "2A", 200, "Falcons",  ["#0b3d2e", "#e8e6df"], SRD),
    ("Adrian",       "Adrian High",       "Adrian",           "Malheur",   BMC,   "Oregon", "2A",  140, "Antelopes",    ["#00539f", "#f2f2ee"], SRD),
    ("Huntington",   "Huntington High",   "Huntington",       "Baker",     BMC,   "Oregon", "2A",   90, "Locomotives",  ["#231f20", "#c8102e"], SRD),
    ("Burnt River",  "Burnt River High",  "Unity",            "Baker",     BMC,   "Oregon", "2A",   88, "Bulls",        ["#8b0000", "#e8c46b"], SRD),
    ("Pine Eagle",   "Pine Eagle High",   "Halfway",          "Baker",     BMC,   "Oregon", "2A",  120, "Spartans",     ["#1e5631", "#f2a900"], SRD),
    # --- 2A Columbia Gorge District
    ("Condon",       "Condon High",       "Condon",           "Gilliam",   GORGE, "Oregon", "2A",  130, "Blue Devils",  ["#0033a0", "#ffffff"], CGD),
    ("Sherman",      "Sherman High",      "Moro",             "Sherman",   GORGE, "Oregon", "2A",  125, "Huskies",      ["#5b2b82", "#c0c0c0"], CGD),
    ("Dufur",        "Dufur High",        "Dufur",            "Wasco",     GORGE, "Oregon", "2A",  160, "Rangers",      ["#00563f", "#f1b82d"], CGD),
    ("Glenwood",     "Glenwood High",     "Glenwood",         "Klickitat", GORGE, "Washington", "2A",  90, "Grizzlies", ["#4b2e2b", "#e8c46b"], CGD),
    ("Klickitat",    "Klickitat High",    "Klickitat",        "Klickitat", GORGE, "Washington", "2A",  95, "Vandals",   ["#8a1538", "#f2f2ee"], CGD),
    ("Lyle",         "Lyle High",         "Lyle",             "Klickitat", GORGE, "Washington", "2A", 105, "Cougars",   ["#00205b", "#a2aaad"], CGD),
    ("Wishram",      "Wishram High",      "Wishram",          "Klickitat", GORGE, "Washington", "2A",  88, "Falcons",   ["#231f20", "#f2a900"], CGD),
    # NB: no "Trout Lake" entry here — that seat is filled by RELOCATION, not
    # creation. See the merge step in apply() below.
]

# Amelia — the one net-new JEFFERSON program of the batch (owner: a revived
# ghost town with its own city; the school is 9A and takes a Capital Athletic
# Association seat the sunsets below open up). Barlowe County is the nearest
# 9A-ladder ground to the real site; the city itself is anchored at the real
# coordinates in `jefferson_gazetteer._EXPANSION_2052_PLACES`.
AMELIA = {
    "name": "Amelia", "city": "Amelia City", "county": "Barlowe",
    "area": "Boise Frontier", "classification": "9A", "group": "9A",
    "enrollment": 2350, "private": False, "mascot": "Ghosts",
    "colors": ["#3b3b3f", "#e8e6df"], "girls": True, "boys": True,
    "girls_district": "Capital Athletic Association",
    "boys_district": "Capital Athletic Association",
}

# The sunsets, owner-named (2026-08): the batch's 40 (16×1A, 15×2A, 4×3A,
# 4×9A, 1×Group 1) plus Pennsauken, sunset separately the same session. Rows
# KEEP their data (former_school serves their pages and archives); only the
# sponsorship flags go off.
SUNSET = [
    "Pellmont", "San Benicio Regional", "Carverstead", "Juniper Bar",
    "Reverend City", "Harmon Siding", "South Fork", "Kendrickville",
    "Willow Gate", "Promise Land", "Ashstead", "Whistle Stop", "Pine Rim",
    "Aspen Spur Union", "Zion Hill", "Farleymere", "Sierra Works",
    # "Antler County High" was renamed "Antler County" in the 2026-08 suffix
    # sweep — this table keys on the display name, so the entry moved with it.
    "Sablewood Union", "Salmonberry Glen", "Trinity Fork", "Antler County",
    "Velasco", "High Timber", "Pasquale", "Fort Wren", "Wardlow Depot",
    "St. Norbert Abbey",
    # The owner's named 9A/Group removals ("i fucking hate those named schools"):
    "Sandra Day O'Connor", "Siskiyou Electric", "Ronald Reagan",
    "Ruth Bader Ginsburg", "Grande-Savane Arts",
    # Second tranche (owner, same message): "Talling Crossing" resolved to the
    # committed Tailing Crossing; bare "Harmon" to Annes Summit (source=Harmon —
    # Harmon Siding was already named above, so the bare name is the other one).
    "Tailing Crossing", "Chaff Crossing", "Sluice Landing", "Annes Summit",
    "Katherine Johnson", "Mercy Academy Valley", "Tidelands Union",
    "Alder Cooperative",
    # Pennsauken (9A) predates the batch — the decades-old duplicate of
    # Pennsauke, sunset by hand earlier the same session. Folded in here so
    # this script's claim to hold every table is TRUE: a full re-import
    # would otherwise resurrect it.
    "Pennsauken",
]

# Every 3A girls-only program fields a boys team (owner rule 2026-08 — it took
# boys' 3A from 75 sponsors to 82, clearing the 76 sponsor floor the sunsets
# had broken). A gender GAINED needs no league redraw: the league belongs to
# the school and these rows already carried `boys_district`.
FIELD_BOYS = (
    "Benedetti", "Funtsville", "Garfield", "Glassell Park", "Goldbank Hall",
    "Tamarack Harbor", "Valley Providence",
)


def apply(rows: list[dict]) -> list[str]:
    log = []
    by_name = {r["name"]: r for r in rows}

    # 1. Sunsets — flags off, rows kept.
    for name in SUNSET:
        r = by_name.get(name)
        if r is None:
            raise SystemExit(f"SUNSET names a school the data does not have: {name}")
        if r.get("girls") or r.get("boys"):
            r["girls"] = r["boys"] = False
            log.append(f"sunset: {name} ({r['classification']})")

    # 1b. The 3A girls-only programs field boys teams.
    for name in FIELD_BOYS:
        r = by_name.get(name)
        if r is None:
            raise SystemExit(f"FIELD_BOYS names a school the data does not have: {name}")
        if not r.get("boys"):
            r["boys"] = True
            log.append(f"boys team: {name} (3A)")

    # 2. Baker moves up. Name/source/city/county/state untouched — the archive
    # keys on the display name and the rosters on the source, so its history and
    # its players' identities survive the move; enrollment follows the decision.
    baker = by_name.get("Baker")
    if baker is None:
        raise SystemExit("Baker is missing from the data")
    if baker["classification"] != "5A":
        baker.update({"classification": "5A", "group": "5A", "enrollment": 830,
                      "area": BMC, "girls_district": EOL, "boys_district": EOL})
        log.append("moved: Baker -> 5A Eastern Oregon League")

    # 3. Trout Lake relocates (owner decision 2026-08): the invented Jefferson
    # 2A moves to Klickitat County, WA and IS the Columbia Gorge affiliate —
    # one school, one archive, one history. Keyed on the ROSTER IDENTITY
    # (`source or name`), so it finds the row whatever display name it carries
    # (a transient same-session San Fernando rename included). Enrollment
    # follows the decision (the COMPETITIVE_MOVES idiom); mascot and colors
    # stay the owner's Silverlegs — named for the fish, which swims in
    # Klickitat County too.
    tl = next((r for r in rows
               if (r.get("source") or r["name"]) == "Trout Lake"), None)
    if tl is None:
        raise SystemExit("Trout Lake is missing from the data")
    if tl.get("state") != "Washington":
        stale = next((r for r in rows
                      if (r.get("source") or r["name"]) == "Trout Lake School"),
                     None)
        if stale is not None:                 # the pre-merge affiliate row
            rows.remove(stale)
            by_name.pop(stale["name"], None)
        by_name.pop(tl["name"], None)
        tl.pop("source", None)                # name == identity again
        tl.update({"name": "Trout Lake", "city": "Trout Lake",
                   "county": "Klickitat", "area": GORGE, "state": "Washington",
                   "enrollment": 110,
                   "girls_district": CGD, "boys_district": CGD})
        by_name["Trout Lake"] = tl
        log.append("relocated: Trout Lake -> Klickitat, WA (Columbia Gorge District)")

    # 4. The affiliates.
    for (name, source, city, county, area, state, cls, enr,
         mascot, colors, league) in NEW_SCHOOLS:
        if name == "Baker":
            continue                      # handled above
        if name in by_name:
            continue                      # idempotent
        rows.append({
            "name": name, "source": source, "city": city, "county": county,
            "area": area, "state": state, "classification": cls, "group": cls,
            "enrollment": enr, "private": False, "mascot": mascot,
            "colors": colors, "girls": True, "boys": True,
            "girls_district": league, "boys_district": league,
        })
        by_name[name] = rows[-1]
        log.append(f"added: {name} ({cls}, {league})")

    # 5. Amelia.
    if AMELIA["name"] not in by_name:
        rows.append(dict(AMELIA))
        by_name[AMELIA["name"]] = rows[-1]
        log.append("added: Amelia (9A, Capital Athletic Association)")

    rows.sort(key=lambda r: r["name"])
    return log


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    log = apply(doc["schools"])

    # Uniqueness is the archive identity AND the roster identity — assert both.
    names = [r["name"] for r in doc["schools"]]
    assert len(names) == len(set(names)), "duplicate display name"
    idents = [r.get("source") or r["name"] for r in doc["schools"]]
    assert len(idents) == len(set(idents)), "duplicate roster identity"

    for line in log:
        print(line)
    if not log:
        print("nothing to do (already applied)")
    if args.dry_run:
        return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nwrote {_DATA}")


if __name__ == "__main__":
    main()
