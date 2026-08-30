#!/usr/bin/env python3
"""The 2056 program closures (owner list, 2026-08): 40 programs sunset.

    python3 scripts/jhsaa_2056_closures.py [--dry-run]

Closures use the `former_school` mechanism the 2052 batch established
(`scripts/jhsaa_2052_expansion.py`): sponsorship flags off, row KEPT, no
league redraw — the row's districts stand as the last-known league, the
archive is untouched, and every program/player page stays reachable forever.
Nothing is deleted and `NEVER_SPONSOR` is deliberately not used (that deletes
the row and kills the pages).

List notes (owner messages, same session):
- "Savanee Brulee" resolved to the committed **Savane Brulee**; "Avalon PARK"
  and "Doyle ridge" case-normalised to the committed names.
- **Manzanita Ridge appeared on the close list AND the rename list; the rename
  wins** — it lives on as "Manzanita" (the owner's confirmation list omits it).
- Pascagoula, Pendleton Heights, Pinyon Ridge and Abbey Prep were added by the
  owner in follow-up messages.
- Four of these are already girls-only (Windmill Ridge, Bois Rouge, Pointe
  Coupee, Pascagoula) — the sunset flips both flags regardless, one statement.

Idempotent: keyed assignments over the committed file; a second run writes the
same bytes. `--dry-run` prints the plan and touches nothing.

SPONSOR FLOORS: reported per touched (class, gender) at run time against
`jhsaa.sponsor_floor`. Measured at apply: every class stays ABOVE its floor —
the two 76-floor classes (3A, 4A) land at 80-82 sponsors, the rest carry the
48 floor with room to spare. Were a future batch to break one, the ladder
degrades LOUDLY (`sc_head`) and the repair is more programs (the `FIELD_BOYS`
idiom), never a smaller field.
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")

SUNSET = [
    # The owner's 2026-08 list, verified against the committed data:
    "Belmonte Collegiate",              # 6A  Black Canyon League
    "Cherry Hill North",                # 8A  Four Rivers Interscholastic League
    "Port Meridian North",              # 8A  Narpes Interscholastic League
    "Olive Reach Baptist",              # 3A  Quarry League
    "St. Catherine Academy",            # 5A  Capital Athletic Association
    "Goldbank Hall",                    # 3A  Assay Athletic Association
    "Laketown County Christian",        # Group 3  Greater Ashbury IL
    "Bridger County Christian",         # Group 2  Olympic League
    "Tippah",                           # 4A  Far West League
    "Sparrowhawk",                      # 9A  Capital Athletic Association
    "I-50 Tech",                        # 9A  Capital Athletic Association
    "Rock on the Hill Christian Academy",   # 5A  Capital Athletic Association
    "Veles Vo-Tech",                    # 9A  Mariners League
    "Christchurch Episcopal",           # 6A  Mariners League
    "Rogers Park",                      # 9A  Forks League
    "Squier Park",                      # 7A  Valle Vista League
    "Maxwell Park",                     # 7A  Three Rivers League
    "Avalon Park",                      # 8A  Del Rey Athletic Association
    "Albany Park",                      # 7A  Timber Valley League
    "Jefferson Park",                   # 8A  Summit League
    "Glassell Park",                    # 3A  Gold Valley League
    "Fair Park",                        # 4A  Valle Vista League
    "Hayes Valley",                     # 9A  Ironwood League
    "Sluice Gate",                      # Group 1  Ostrobothnia League
    "Doyle Ridge",                      # 6A  Placer League
    "Stone Ridge",                      # 6A  Black Canyon League
    "Windmill Ridge",                   # 6A  Mission League (girls-only)
    "Nixyaawii",                        # 2A  Columbia Range League (2052 affiliate)
    "Bois Rouge",                       # 4A  Millworks AA (girls-only)
    "Savane Brulee",                    # 6A  Black Canyon League
    "La Savane",                        # 4A  Millworks Athletic Association
    "Pointe des Brumes",                # 2A  Del Rey Athletic Association
    "Pointe Coupee",                    # 5A  Valley Coast IL (girls-only)
    "Copperton Regional",               # 1A  East Cascades League
    "Copper Prairie",                   # 1A  Placer League
    "Antler Prairie",                   # Group 3  Inland Empire League
    "Pascagoula",                       # 5A  Capital Athletic Association (girls-only)
    # Follow-up additions (owner, same session):
    "Pendleton Heights",                # 7A  Valle Vista League
    "Pinyon Ridge",                     # Group 1  Far West League
    "Abbey Prep",                       # 5A  Narpes Interscholastic League
    # "Too many of them" — the owner thinned the High-x names rather than
    # renaming them (the suffix sweep left leading-word "High" alone as
    # identity; these three close instead). "High Timber" was named in the same
    # message and is ALREADY sunset — the 2052 batch's list carries it, so it is
    # deliberately not repeated here. High Desert Cooperative was not named and
    # stays.
    "High Bar",                         # 2A  (its town's name)
    "High Prairie",                     # Group 3
    "High Desert Christian",            # 3A  Doyle Pass
]


def apply(rows: list[dict]) -> list[str]:
    log = []
    by_name = {r["name"]: r for r in rows}
    for name in SUNSET:
        r = by_name.get(name)
        if r is None:
            raise SystemExit(f"SUNSET names a school the data does not have: {name}")
        if r.get("girls") or r.get("boys"):
            r["girls"] = r["boys"] = False
            log.append(f"sunset: {name} ({r['classification']})")
    return log


def floor_report(rows: list[dict]) -> list[str]:
    """Sponsor counts per (group, gender) the batch touches, against
    `jhsaa.sponsor_floor` — informational, the ladder degrades loudly on its
    own; this just puts the number where the closure decision is made."""
    sys.path.insert(0, _REPO)
    os.environ.setdefault("TENNIS_DB_PATH", "/tmp/jhsaa-closures-check.db")
    from app import jhsaa as jh
    touched = {r["group"] for r in rows if r["name"] in set(SUNSET)}
    out = []
    for g in sorted(touched):
        floor = jh.sponsor_floor(g)
        for gender in ("girls", "boys"):
            n = sum(1 for r in rows if r["group"] == g and r.get(gender))
            mark = "  ⚠️ under floor" if n < floor else ""
            out.append(f"  {g:8} {gender:5} {n:3} / floor {floor}{mark}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    log = apply(doc["schools"])

    names = [r["name"] for r in doc["schools"]]
    assert len(names) == len(set(names)), "duplicate display name"
    idents = [r.get("source") or r["name"] for r in doc["schools"]]
    assert len(idents) == len(set(idents)), "duplicate roster identity"

    for line in log:
        print(line)
    if not log:
        print("nothing to do (already applied)")
    for line in floor_report(doc["schools"]):
        print(line)
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nwrote {_DATA}")


if __name__ == "__main__":
    main()
