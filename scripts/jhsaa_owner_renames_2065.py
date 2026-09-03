"""One-off: the owner's 2065 JHSAA renames.

Eight programs, named by the owner. Two of them (Washington, Tidewater) are
REVERSALS of an earlier rename — the school is going back to a name it already
carried — so those alias entries are deleted rather than repointed: a former
name that is also the live name is a contradiction the alias table should not
hold, even though `jhsaa.current_name` would prefer the live school anyway.

Every rename stamps `source` where the record had none, so `source or name` —
the string that seeds the pids — never moves.

Run: python3 scripts/jhsaa_owner_renames_2065.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RENAMES: dict[str, str] = {
    "Eisenhower": "Flume River",              # 4A Sluice Crossing
    "Coolidge": "Seagrove",                   # 9A Olive Reach
    "Covenant": "Stonehaven",                 # 8A Calder
    "Adams": "Sally Ride",                    # 6A Port Veles
    "Madison": "Governor Woods",              # 2A Cook City
    "Prairie Union": "Deaconsburg",           # 7A Halbrook
    "Washington": "George Washington",        # 8A Port Veles — back to its old name
    "Tidewater": "Tamarack Harbor",           # 9A Tamarack Harbor — back to its old name
}

SCHOOLS = ROOT / "data" / "jhsaa" / "schools.json"
FORMER = ROOT / "data" / "jhsaa" / "former_names.json"

# Display-name-keyed occurrences, edited by exact text. NOT a blanket replace:
# "Washington" is also a US state, "Tidewater" is Tidewater Catholic's LOCALITY
# and another school's mascot, and "Adams" appears in FORMER_NAMES keys that
# name a different school.
EDITS: list[tuple[str, str, str]] = [
    # scripts/import_jhsaa.py — FORMER_NAMES values
    ("scripts/import_jhsaa.py",
     '    "Anton Sidorov":                               "Adams",',
     '    "Anton Sidorov":                               "Sally Ride",'),
    ("scripts/import_jhsaa.py",
     '    "John Adams":                                  "Adams",',
     '    "John Adams":                                  "Sally Ride",'),
    ("scripts/import_jhsaa.py",
     '    "Nadia Sidorov":                               "Adams",',
     '    "Nadia Sidorov":                               "Sally Ride",'),
    ("scripts/import_jhsaa.py",
     '    "Anneliese Halvorsen":                         "Washington",',
     '    "Anneliese Halvorsen":                         "George Washington",'),
    ("scripts/import_jhsaa.py",
     '    "Nicolás Quiñones":                            "Covenant",',
     '    "Nicolás Quiñones":                            "Stonehaven",'),
    ("scripts/import_jhsaa.py",
     '    "Halbrook Union":                              "Prairie Union",',
     '    "Halbrook Union":                              "Deaconsburg",'),
    # …and the two alias rows the reversals make self-contradictory.
    ("scripts/import_jhsaa.py",
     '    "George Washington":                           "Washington",\n', ''),
    ("scripts/import_jhsaa.py",
     '    "Tamarack Harbor":                             "Tidewater",\n', ''),
    # scripts/import_jhsaa.py — RENAMES values
    ("scripts/import_jhsaa.py",
     '    "Nadia Sidorov": "Adams",',
     '    "Nadia Sidorov": "Sally Ride",'),
    ("scripts/import_jhsaa.py",
     '    "Anneliese Halvorsen": "Washington",',
     '    "Anneliese Halvorsen": "George Washington",'),
    ("scripts/import_jhsaa.py",
     '    "Halbrook Union": "Prairie Union",                         # 7A Halbrook',
     '    "Halbrook Union": "Deaconsburg",                           # 7A Halbrook'),
    ("scripts/import_jhsaa.py",
     '    "Nicolás Quiñones":          "Covenant",                # 7A Calder',
     '    "Nicolás Quiñones":          "Stonehaven",              # 7A Calder'),
    # The 9A goes back to its own identity, so it is no longer renamed at all.
    ("scripts/import_jhsaa.py",
     '    "Tamarack Harbor": "Tidewater",                            # 3A Tamarack Harbor\n', ''),
    # scripts/import_jhsaa.py — LOCALITIES key
    ("scripts/import_jhsaa.py",
     '    "Adams":                                 "Roanoke",',
     '    "Sally Ride":                            "Roanoke",'),
    # scripts/import_jhsaa.py — RECLASSIFY_TO_2A, a tuple of display names
    ("scripts/import_jhsaa.py",
     '    "Lieksa", "Los Maderos", "Madison", "Mt Jacqueline", "Netherwood",',
     '    "Lieksa", "Los Maderos", "Governor Woods", "Mt Jacqueline", "Netherwood",'),
    # the other display-name-keyed tables
    ("scripts/jhsaa_2056_promotions.py",
     '    "Coolidge": "9A", "Cliffside": "9A", "Trinity Catholic": "9A",',
     '    "Seagrove": "9A", "Cliffside": "9A", "Trinity Catholic": "9A",'),
    ("scripts/jhsaa_2056_promotions.py",
     '"Jimmy Carter": "9A", "Tidewater": "9A",',
     '"Jimmy Carter": "9A", "Tamarack Harbor": "9A",'),
    ("scripts/jhsaa_promotions_and_affiliates.py",
     '    "Vespertine", "Covenant", "Cook City", "Ditch Fork", "Olive Head",',
     '    "Vespertine", "Stonehaven", "Cook City", "Ditch Fork", "Olive Head",'),
    ("scripts/jhsaa_2052_expansion.py",
     '    "Tidewater", "Valley Providence",',
     '    "Tamarack Harbor", "Valley Providence",'),
]


def main() -> int:
    dry = "--dry-run" in sys.argv

    doc = json.loads(SCHOOLS.read_text())
    rows = doc["schools"]
    names = {r["name"] for r in rows}

    missing = [o for o in RENAMES if o not in names]
    taken = [n for n in RENAMES.values() if n in names and n not in RENAMES]
    if missing or taken:
        print("no such school:", missing, "| new name already taken:", taken)
        return 1

    for row in rows:
        old = row["name"]
        if old not in RENAMES:
            continue
        row.setdefault("source", old)   # pin the roster identity before the name moves
        row["name"] = RENAMES[old]
        print(f"  {old:<16} -> {row['name']:<18} {row['group']:<8} {row['city']}")

    final = [r["name"] for r in rows]
    ident = [r.get("source") or r["name"] for r in rows]
    if len(set(final)) != len(final) or len(set(ident)) != len(ident):
        print("names or roster identities are no longer unique")
        return 1

    former = json.loads(FORMER.read_text())
    table = former["former_names"]
    for old, fresh in RENAMES.items():
        for key, val in list(table.items()):
            if val == old:
                table[key] = fresh
        # A reversal: the name coming back must not also sit in the alias table.
        table.pop(fresh, None)
        if fresh not in RENAMES:
            table[old] = fresh
    former["former_names"] = dict(sorted(table.items()))

    for rel, old, new in EDITS:
        path = ROOT / rel
        text = path.read_text()
        if old not in text:
            print("edit no longer matches:", rel, old.strip()[:60])
            return 1
        text = text.replace(old, new, 1)
        if not dry:
            path.write_text(text)

    if not dry:
        SCHOOLS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        FORMER.write_text(json.dumps(former, indent=2, ensure_ascii=False) + "\n")
    print("dry run — nothing written" if dry else "written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
