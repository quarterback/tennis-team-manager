"""One-off: the owner's composer renames (2026-09).

Five programs whose names duplicated a neighbour's leading word without adding
any identity of their own — the near-duplicate groups `jhsaa_name_list.py`
leads with — renamed to the composers the owner named: Gershwin, Monk,
Mendelssohn, Coltrane, Miles Davis.

    Esperanza Basin  (5A, Lake Esperanza)  -> Gershwin       beside "Esperanza" (9A)
    Doyle Ridge      (6A, Halbrook)        -> Monk           beside "Doyle" (6A), same city
    Olive            (5A, Olive Reach)     -> Mendelssohn    beside "Olive Head" (8A), same county, same mascot
    Veles Central    (5A, Port Veles)      -> Coltrane       one of five "Veles X" programs
    Veles Union      (5A, Port Veles)      -> Miles Davis    the other 5A "Veles X"

Every one of these already carried a `source` (each is a RENAMES target), so
the rename REWRITES that entry's target in place — never A -> B -> C — and the
roster identity (`source or name`) does not move. The display-name-keyed tables
(`MASCOTS`, the one-off scripts' lists) move their keys with the name.

Run: python3 scripts/jhsaa_composer_renames.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RENAMES: dict[str, str] = {
    "Esperanza Basin": "Gershwin",
    "Doyle Ridge": "Monk",
    "Olive": "Mendelssohn",
    "Veles Central": "Coltrane",
    "Veles Union": "Miles Davis",
}

SCHOOLS = ROOT / "data" / "jhsaa" / "schools.json"
FORMER = ROOT / "data" / "jhsaa" / "former_names.json"

# Exact-text edits, never a blanket replace: "Olive" is also a town stem
# (Olive Reach, Olive Head) and a given name in the pools.
EDITS: list[tuple[str, str, str]] = [
    # scripts/import_jhsaa.py — FORMER_NAMES values
    ("scripts/import_jhsaa.py",
     '    "Archbishop Doyle Prep North":                 "Doyle Ridge",',
     '    "Archbishop Doyle Prep North":                 "Monk",'),
    ("scripts/import_jhsaa.py",
     '    "Nathaniel Cross North":                       "Veles Union",',
     '    "Nathaniel Cross North":                       "Miles Davis",'),
    ("scripts/import_jhsaa.py",
     '    "Olive Reach":                                 "Olive",',
     '    "Olive Reach":                                 "Mendelssohn",'),
    ("scripts/import_jhsaa.py",
     '    "Port Veles":                                  "Veles Central",',
     '    "Port Veles":                                  "Coltrane",'),
    ("scripts/import_jhsaa.py",
     '    "Thomas Jansen North":                         "Esperanza Basin",',
     '    "Thomas Jansen North":                         "Gershwin",'),
    # scripts/import_jhsaa.py — RENAMES values
    ("scripts/import_jhsaa.py",
     '    "Olive Reach": "Olive",',
     '    "Olive Reach": "Mendelssohn",'),
    ("scripts/import_jhsaa.py",
     '    "Nathaniel Cross North": "Veles Union",',
     '    "Nathaniel Cross North": "Miles Davis",'),
    ("scripts/import_jhsaa.py",
     '    "Archbishop Doyle Prep North": "Doyle Ridge",              # 6A Halbrook',
     '    "Archbishop Doyle Prep North": "Monk",                     # 6A Halbrook'),
    ("scripts/import_jhsaa.py",
     '    "Port Veles": "Veles Central",                             # 5A Port Veles',
     '    "Port Veles": "Coltrane",                                  # 5A Port Veles'),
    ("scripts/import_jhsaa.py",
     '    "Thomas Jansen North":       "Esperanza Basin",     # 5A Lake Esperanza',
     '    "Thomas Jansen North":       "Gershwin",            # 5A Lake Esperanza'),
    # scripts/import_jhsaa.py — MASCOTS key (display-name keyed)
    ("scripts/import_jhsaa.py",
     '    "Veles Central": "Chinook",                    # the port itself',
     '    "Coltrane": "Chinook",                         # the port itself'),
    # the other display-name-keyed tables
    ("scripts/jhsaa_secularise_2065.py",
     '    "Port Veles Lutheran": "Veles Union",',
     '    "Port Veles Lutheran": "Miles Davis",'),
    ("scripts/jhsaa_2056_closures.py",
     '    "Doyle Ridge",                      # 6A  Placer League',
     '    "Monk",                             # 6A  Placer League'),
]


def main() -> int:
    dry = "--dry-run" in sys.argv

    doc = json.loads(SCHOOLS.read_text())
    rows = doc["schools"]
    names = {r["name"] for r in rows}

    missing = [o for o in RENAMES if o not in names]
    taken = [n for n in RENAMES.values() if n in names]
    if missing or taken:
        print("no such school:", missing, "| new name already taken:", taken)
        return 1

    for row in rows:
        old = row["name"]
        if old not in RENAMES:
            continue
        row.setdefault("source", old)   # pin the roster identity before the name moves
        row["name"] = RENAMES[old]
        print(f"  {old:<16} -> {row['name']:<14} {row['group']:<8} {row['city']}")

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
