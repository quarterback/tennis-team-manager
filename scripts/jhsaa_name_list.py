#!/usr/bin/env python3
"""Write the association's current school names to `docs/JHSAA-school-names.txt`.

    python3 scripts/jhsaa_name_list.py

‼️ WHY A GENERATED FILE AND NOT A HAND-KEPT ONE. Renaming is an ongoing pass — the
owner works a batch out elsewhere, brings a list back, and it lands in
`import_jhsaa.RENAMES`. A reference list typed by hand goes stale the moment that
happens and then quietly misinforms the next pass. This reads the committed data,
so re-running it after any rename regenerates a list that is true by construction.

The layout is built for the job it exists for — finding schools whose names do not
tell them apart:

  * grouped BY CITY, so a city's whole slate reads together;
  * a NEAR-DUPLICATE section listing every pair that shares a leading word, plus
    every city holding more than one school, which is where the problem lives;
  * every row carries its SOURCE KEY, which is what a rename must be keyed on.
"""
import argparse
import collections
import importlib.util
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")
_OUT = os.path.join(_REPO, "docs", "JHSAA-school-names.txt")


def _rows() -> list[dict]:
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    return doc["schools"] if isinstance(doc, dict) else doc


def _lead(name: str) -> str:
    """The leading word, which is what a reader actually tells names apart by."""
    return re.sub(r"[^a-z0-9]+", "", name.split()[0].lower()) if name.split() else ""


#: A name that is its own city plus nothing, or plus a compass point / Central.
#: These read as one district's schools and are deliberately NOT the target.
_DIRECTION = re.compile(
    r"^(north|south|east|west|northwest|northeast|southwest|southeast|central|heights)$",
    re.IGNORECASE)


def _city_direction(r: dict) -> bool:
    name, city = r["name"], r["city"]
    if name == city:
        return True
    if not name.startswith(city + " "):
        return False
    return bool(_DIRECTION.match(name[len(city) + 1:]))


def build(rows: list[dict]) -> str:
    out = []
    w = out.append
    by_city = collections.defaultdict(list)
    for r in rows:
        by_city[r["city"]].append(r)

    w("JHSAA — every school in the association")
    w("=" * 78)
    w(f"Generated from data/jhsaa/schools.json by scripts/jhsaa_name_list.py.")
    w(f"{len(rows)} programs across {len(by_city)} cities. Re-run after any rename.")
    w("")
    w("RENAMING IS SAFE AND IS THE DESIGNED PATH — but key it on the right thing:")
    w("")
    w("  * A rename goes in `scripts/import_jhsaa.py` -> RENAMES, keyed on the")
    w("    SOURCE key (the last column here), never on the display name. The source")
    w("    is the school's permanent identity: it seeds the RNG that builds its")
    w("    twelve players and the pids on their records. Rename through RENAMES and")
    w("    the roster, the history and the archived awards all follow the school.")
    w("    Rewrite the name in the data file directly and the program gets twelve")
    w("    strangers and its honours point at nobody.")
    w("  * If a school ALREADY has a RENAMES entry, rewrite that entry's target in")
    w("    place. Never chain A -> B -> C.")
    w("  * A DISPLAY NAME MUST BE UNIQUE across the whole association — it is the")
    w("    archive identity. Two schools sharing one name silently merge into one")
    w("    archive slot and nothing errors.")
    w("  * NO INSTITUTIONAL SUFFIX: a trailing 'High School' / 'HS' / 'School' is")
    w("    stripped at emit. Write names in full if you like; they emit bare.")
    w("  * MASCOTS / COLORS / PRIVATE_SCHOOLS and data/jhsaa/archetypes.json all key")
    w("    on the DISPLAY name, so those keys move with a rename.")
    w("  * NEVER RENAME A REAL PERSON'S SCHOOL. The person-named pool mixes invented")
    w("    names with genuine ones — every president, plus Thurgood Marshall, Octavia")
    w("    Butler, James Baldwin, Gwendolyn Brooks, Mae Jemison, Bayard Rustin, John")
    w("    Lewis, Ella Baker, Katherine Johnson, Rita Moreno, George Washington")
    w("    Carver and others. 'Looks like a person' is not the test.")
    w("")

    # ‼️ The point of the file. A name is a problem when it does not DIFFERENTIATE,
    # which is a property of a pair, not of a name — so the pairs are listed rather
    # than left to be spotted by scrolling.
    w("=" * 78)
    w("NEAR-DUPLICATES — pairs sharing a leading word, same city first")
    w("=" * 78)
    lead = collections.defaultdict(list)
    for r in rows:
        lead[_lead(r["name"])].append(r)
    # ‼️ A COMPASS POINT ON THE CITY'S OWN NAME IS NOT THE PROBLEM (owner, 2026-08):
    # "I do not mean [CITY] East or even [CITY] Central." Belmonte North and Belmonte
    # West are how real districts name schools and read as distinct places. What does
    # not differentiate is two schools whose names are the SAME WORDS plus something
    # that carries no identity — Altamonte beside Altamonte Civic, Archbishop Doyle
    # Prep beside Archbishop Doyle Prep North. So the city-direction family is split
    # out and marked rather than mixed in, because a list that flags 80 groups when 40
    # of them are fine is a list nobody finishes reading.
    same_city, city_dir, other = [], [], []
    for _, group in sorted(lead.items()):
        if len(group) < 2:
            continue
        cities = collections.Counter(r["city"] for r in group)
        if max(cities.values()) < 2:
            other.append(group)
        elif all(_city_direction(r) for r in group):
            city_dir.append(group)
        else:
            same_city.append(group)
    for label, groups in (
            ("SAME CITY — LOOK HERE FIRST", same_city),
            ("SAME LEADING WORD, DIFFERENT CITIES", other),
            ("CITY + COMPASS POINT — fine as they are, listed for completeness", city_dir)):
        w("")
        w(f"-- {label} ({len(groups)} groups)")
        for group in groups:
            for r in sorted(group, key=lambda r: (r["city"], r["name"])):
                w(f"   {r['classification']:>3} {r['enrollment']:5}  {r['name']:<38}"
                  f" {r['city']:<22} {r.get('source') or r['name']}")
            w("")

    w("")
    w("=" * 78)
    w("EVERY SCHOOL, BY CITY")
    w("=" * 78)
    w("class | enrollment | pub/priv | display name | locality | district | SOURCE KEY")
    for city in sorted(by_city):
        group = sorted(by_city[city], key=lambda r: (-r["enrollment"], r["name"]))
        w("")
        w(f"{city} — {len(group)} program{'s' if len(group) != 1 else ''} "
          f"({group[0]['county']} County, {group[0]['area']})")
        for r in group:
            w(f"   {r['classification']:>3} {r['enrollment']:5} "
              f"{'priv' if r['private'] else 'pub ':4} {r['name']:<38}"
              f" {r.get('locality', ''):<18} {r['girls_district']:<34}"
              f" {r.get('source') or r['name']}")
    w("")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=_OUT)
    args = ap.parse_args()
    text = build(_rows())
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {args.out} ({text.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
