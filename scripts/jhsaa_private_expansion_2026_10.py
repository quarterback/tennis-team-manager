#!/usr/bin/env python3
"""The 2026-10 private-school expansion — 25 net-new programs in the seven areas
with the thinnest private coverage (owner-named list, 2026-10).

    python3 scripts/jhsaa_private_expansion_2026_10.py [--dry-run]

Every private school prep-network carries was already in the association after
the 2026-09 expansion, so these are net-new, the Antler Valley idiom: a row
with the town's county and area (and `state` where the town is an Oregon
affiliate), `private` on, seated in 10B/11B by the 550 cut
(`jhsaa.NONPUBLIC_CUT`) through the forced redraw (`ensure_nonpublic(force=True)`),
and `old_group`/`old_league` taken from the public league of the biggest public
in its town, so the once-a-year public duals have a league to read. Public
classes are not redrawn. Names are the owner's (written bare per the no-suffix
rule); mascots and colours are placeholders the owner can change in
`import_jhsaa.MASCOTS`/`COLORS`. Idempotent — a row already present is skipped.
"""
import argparse
import collections
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")

# name, town, enrollment, mascot, colours
NEW_PRIVATES = [
    # Gold Valley
    ("Valderra Catholic",            "Valderra",       780, "Crusaders",   ["#8b0000", "#ffd700"]),
    ("Esperanza Bay Country Day",    "Lake Esperanza", 460, "Herons",      ["#005f73", "#e9d8a6"]),
    ("The Cortland School",          "Cortland",       390, "Foxes",       ["#b5451b", "#f5f5f0"]),
    ("St. Jude",                     "Moriarty",       610, "Saints",      ["#1b3a6b", "#ffffff"]),
    # Kangas
    ("Valois Military Institute",    "Fort Valois",    640, "Cadets",      ["#2f3e46", "#c9a227"]),
    ("Aurelia Hall",                 "Aurelia",        410, "Griffins",    ["#4a1942", "#d4af37"]),
    ("St. Luke's",                   "Harrow",         320, "Lions",       ["#0b6623", "#ffd700"]),
    ("Latgaway Christian",           "Latgaway",       280, "Eagles",      ["#1e3a8a", "#c0c0c0"]),
    ("Dovetail Mountain",            "Dovetail",       190, "Mountaineers",["#3b5f3b", "#f0e6c8"]),
    # Silver Basin
    ("Echevarria Christian",         "Echevarria",     680, "Warriors",    ["#7b1113", "#ffffff"]),
    ("Silver Basin Country Day",     "Carden City",    490, "Owls",        ["#4b5563", "#a7c7e7"]),
    ("Zubieta Catholic",             "Zubieta",        420, "Royals",      ["#2d1b69", "#f4c430"]),
    ("The Greaves School",           "Greaves",        350, "Hawks",       ["#003153", "#e8e8e8"]),
    # Cascade Divide
    ("San Cordero Catholic",         "San Cordero",    910, "Cardinals",   ["#c41e3a", "#ffffff"]),
    ("Cascade Ridge",                "Fort Carden",    580, "Rams",        ["#1f3d2b", "#d9c89e"]),
    ("Summit Pines",                 "Dahlberg Summit",310, "Pinecones",   ["#2e5339", "#f2e8cf"]),
    ("Annie Springs Christian",      "Annie Springs",  220, "Knights",     ["#0f2c5c", "#c0c0c0"]),
    # Alderwold
    ("Blackpine Christian",          "Blackpine",      630, "Falcons",     ["#4b0082", "#ffd700"]),
    ("Black Springs Country Day",    "Black Springs",  250, "Otters",      ["#1a5e63", "#f4f1de"]),
    ("Tamarack Lutheran",            "Tamarack Flat",  180, "Lancers",     ["#800020", "#ffffff"]),
    ("Canyon Creek",                 "Corey Canyon",   310, "Coyotes",     ["#a0522d", "#f5deb3"]),
    # Blue Mountain Country (Oregon affiliates)
    ("Blue Mountain Christian",      "Pendleton",      340, "Bulldogs",    ["#002868", "#ffc72c"]),
    ("Eastern Oregon Heritage Academy", "La Grande",   280, "Pioneers",    ["#5c4033", "#e3c565"]),
    ("Hermiston Catholic",           "Hermiston",      420, "Spartans",    ["#006400", "#ffffff"]),
    # Columbia Gorge
    ("Columbia Gorge Christian",     "The Dalles",     330, "Chinooks",    ["#1c4966", "#f0f0f0"]),
]


def classification_for(enrollment: int, bands: dict) -> str:
    """The size class whose band the enrollment falls in; a gap between bands
    takes the class below it (the importer's cut lines are the band tops)."""
    best = None
    for cls, (lo, hi) in bands.items():
        if lo <= enrollment <= hi:
            return cls
        if enrollment > hi and (best is None or hi > bands[best][1]):
            best = cls
    return best or "1A"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    import importlib.util
    spec = importlib.util.spec_from_file_location("import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.path.insert(0, _REPO)
    os.environ.setdefault("TENNIS_DB_PATH", os.path.join(_REPO, ".jhsaa_expansion_scratch.db"))
    from app import jhsaa as jh
    from app import jhsaa_districting as jd

    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"]
    live = {r["name"] for r in rows}
    town = {}
    for r in rows:
        t = town.setdefault(r["city"], {"county": r["county"], "area": r["area"],
                                        "state": r.get("state"), "publics": []})
        if not r["private"] and (r["girls"] or r["boys"]) and r["group"] not in jh.NONPUBLIC_GROUPS:
            t["publics"].append(r)
    added = []
    for name, city, enr, mascot, colors in NEW_PRIVATES:
        if name not in m.PRIVATE_SCHOOLS:
            sys.exit(f"{name} is not in import_jhsaa.PRIVATE_SCHOOLS — the single authority")
        if name in live:
            continue
        if city not in town:
            sys.exit(f"{name}: town {city} is not in the association")
        t = town[city]
        cls = classification_for(enr, m._CLASS_ENROLLMENT_BAND)
        pubs = sorted(t["publics"], key=lambda r: -r["enrollment"])
        same = [r for r in pubs if r["group"] == cls] or pubs
        row = {"name": name, "city": city, "county": t["county"], "area": t["area"]}
        if t["state"]:
            row["state"] = t["state"]
        row.update({"classification": cls, "group": cls, "enrollment": enr, "private": True,
                    "mascot": mascot, "colors": colors, "girls": True, "boys": True,
                    "girls_district": same[0]["girls_district"] if same else "",
                    "boys_district": same[0]["girls_district"] if same else ""})
        rows.append(row)
        added.append(row)
    rows.sort(key=lambda r: r["name"])
    before = {c: collections.Counter(r["girls_district"] for r in rows
                                     if r["group"] == c and r["girls"]) for c in jh.NONPUBLIC_GROUPS}
    out = jd.ensure_nonpublic(rows, jh.NONPUBLIC_CUT, jh.NONPUBLIC_PLAYUP, force=True, log=print)
    print(f"{out['moved']} rows seated; redrawn {out['redrawn']}")
    for r in added:
        print(f"  + {r['name']:32} {r['classification']:>3} {r['enrollment']:4} -> {r['group']} "
              f"{r['girls_district']:34} old {r.get('old_group')} {r.get('old_league')}")
    cfg = jd.districting_config()
    for c in jh.NONPUBLIC_GROUPS:
        after = collections.Counter(r["girls_district"] for r in rows if r["group"] == c and r["girls"])
        print(f"  {c}: {sum(before[c].values())} -> {sum(after.values())} programs, "
              f"leagues {sorted(before[c].values())} -> {sorted(after.values())}")
        if after and (max(after.values()) > cfg.MAX_DISTRICT or min(after.values()) < cfg.MIN_DISTRICT_SIZE):
            sys.exit(f"{c}: league outside {cfg.MIN_DISTRICT_SIZE}-{cfg.MAX_DISTRICT}")
    for r in rows:
        if r["private"] and r["group"] != jd.nonpublic_class(r, jh.NONPUBLIC_CUT, jh.NONPUBLIC_PLAYUP):
            sys.exit(f"{r['name']}: private in {r['group']} against the cut")
    print(f"{len(added)} added; {len(rows)} rows")
    if args.dry_run:
        print("--dry-run: nothing written"); return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False); fh.write("\n")
    print("wrote", _DATA)


if __name__ == "__main__":
    main()
