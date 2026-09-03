"""One-off: thin and correct the JHSAA's religious-school names (owner rule 2026-09).

Three faults, one pass:

* **Bare collapse artefacts.** "Baptist", "Jesuit" and "Seminary" are what the
  suffix-stripper leaves when a source record was `<X> High School` and X carried
  no place — a school is never called just "Baptist". They take their town
  ("Brynildson Baptist"), the PRE + PLACE form the naming rule already states
  ("Jesuit Mercer City"), or a secular name.
* **Religious names on public programs.** `private` is false on Covenant,
  Wyalusing Providence, Valley Providence and Bishop Turner. A public school does
  not carry a dedication or a prelate's title. (Saint Marc, Mission Bay/Butte/
  Ridge/Terrace and Zion Hill are PLACE names — Saint-Marc is a Haitian city and
  Belyakov is a Haitian-flavoured city — and are deliberately untouched.)
* **Template repetition.** Twenty-four "<X> Christian" and nine
  "<County> County Catholic/Christian" programs read as one generator, not as an
  association's private layer. Four county-template and three generic-compass
  programs become ordinary town schools.

Every rename keeps the roster identity: `source` is stamped with the old display
name where the record had none, so `source or name` — the string that seeds the
pids — never moves. The old name is recorded in `former_names.json` so archived
seasons relabel on read.

Run: python3 scripts/jhsaa_religious_renames.py [--dry-run]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# old display name -> new display name
RENAMES: dict[str, str] = {
    # bare collapse artefacts
    "Baptist": "Brynildson Baptist",
    "Jesuit": "Jesuit Mercer City",
    "Seminary": "Veles Hill",
    # a third St. Francis, and the only "Saint" spelling in the association
    "Saint Francis": "Kingsley Hall",
    # religious names on public programs
    "Covenant": "Calder North",
    "Wyalusing Providence": "Minidoka",
    "Valley Providence": "Meridian Valley",
    "Bishop Turner": "Henry Turner",
    # the "<County> County Catholic/Christian" template, thinned to three
    "Eden County Christian": "Eden",
    "Malad County Christian": "Malad",
    "Ruby County Catholic": "Carlin",
    "Wellsville County Catholic": "Hyrum",
    # the generic end of the "<X> Christian" cluster
    "Westside Christian": "Westside Prep",
    "Central Christian": "Summervale Academy",
    "North Valley Christian": "Netherwood Prep",
}

SCHOOLS = ROOT / "data" / "jhsaa" / "schools.json"
FORMER = ROOT / "data" / "jhsaa" / "former_names.json"
IMPORTER = ROOT / "scripts" / "import_jhsaa.py"

# Display-name-keyed tables live in these; data/ncaa is a different association
# entirely (Covenant College) and prep-network's own names must not move.
TOUCH = [
    IMPORTER,
    ROOT / "scripts" / "jhsaa_2052_expansion.py",
    ROOT / "scripts" / "jhsaa_2056_promotions.py",
    ROOT / "scripts" / "jhsaa_2056_closures.py",
    ROOT / "scripts" / "jhsaa_promotions_and_affiliates.py",
    ROOT / "scripts" / "jhsaa_border_realignment.py",
    ROOT / "scripts" / "jhsaa_heritage_valley.py",
    ROOT / "data" / "jhsaa" / "archetypes.json",
]


def _always_extra_range(text: str) -> tuple[int, int]:
    """Line span of ALWAYS_EXTRA, which holds SOURCE names and must not move."""
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("ALWAYS_EXTRA"))
    end = next(i for i in range(start, len(lines)) if lines[i].rstrip() == "]")
    return start, end


def rewrite(path: Path, dry: bool) -> int:
    text = path.read_text()
    skip = _always_extra_range(text) if path == IMPORTER else None
    out, hits = [], 0
    for i, line in enumerate(text.splitlines(keepends=True)):
        if skip and skip[0] <= i <= skip[1]:
            out.append(line)
            continue
        new = line
        for old, fresh in RENAMES.items():
            new = re.sub(rf'"{re.escape(old)}"', f'"{fresh}"', new)
        hits += new != line
        out.append(new)
    if not dry and hits:
        path.write_text("".join(out))
    return hits


def main() -> int:
    dry = "--dry-run" in sys.argv

    doc = json.loads(SCHOOLS.read_text())
    rows = doc["schools"]
    names = {r["name"] for r in rows}

    missing = [o for o in RENAMES if o not in names]
    if missing:
        print("no such school:", missing)
        return 1
    clash = [n for n in RENAMES.values() if n in names and n not in RENAMES]
    if clash:
        print("new name already taken:", clash)
        return 1
    dupes = [n for n in set(RENAMES.values()) if list(RENAMES.values()).count(n) > 1]
    if dupes:
        print("two renames share a target:", dupes)
        return 1

    for row in rows:
        old = row["name"]
        if old not in RENAMES:
            continue
        # `source or name` is the roster identity: pin it before the name moves.
        row.setdefault("source", old)
        row["name"] = RENAMES[old]
        print(f"  {old:<28} -> {row['name']:<22} {row['group']:<8} {row['city']}")

    final = [r["name"] for r in rows]
    if len(set(final)) != len(final):
        print("display names are no longer unique")
        return 1
    ident = [r.get("source") or r["name"] for r in rows]
    if len(set(ident)) != len(ident):
        print("roster identities are no longer unique")
        return 1

    former = json.loads(FORMER.read_text())
    table = former["former_names"] if "former_names" in former else former
    for old, fresh in RENAMES.items():
        for key, val in list(table.items()):
            if val == old:
                table[key] = fresh
        table[old] = fresh
    ordered = dict(sorted(table.items()))
    if "former_names" in former:
        former["former_names"] = ordered
    else:
        former = ordered

    if not dry:
        SCHOOLS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        FORMER.write_text(json.dumps(former, indent=2, ensure_ascii=False) + "\n")

    for path in TOUCH:
        if path.exists():
            n = rewrite(path, dry)
            if n:
                print(f"  {path.relative_to(ROOT)}: {n} line(s)")
    print("dry run — nothing written" if dry else "written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
