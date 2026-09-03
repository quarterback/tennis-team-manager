"""One-off: retire the Catholic/religious naming layer the owner did not keep, 2065.

Fifty programs are renamed and every one becomes PUBLIC. What is NOT here matters
as much as what is:

* **A program that has ever won a state title keeps its name.** Thirty-three
  candidates are protected by that rule, read off the association's own champions
  history — Valley Christian, Pacific Friends, Westfield Friends, St. Agnes Academy,
  Tidewater Catholic and the rest. Seminary is the single owner-granted exception.
* The owner's keep list stands: Christian Brothers, Hazel Country Day, Port Veles
  Episcopal, Fletcher-Garrison Hall, Chaminade, Metropolitan Country Day, St. Vincent,
  Delbarton, St. Teresa, Westside Christian, Romero-Finniski, Condotti Vanguard
  Academy, Jesuit, Baptist — plus Archbishop Gregory and the nine institutional
  flagships (Notre Dame, De La Salle, Mater Dei, Trinity Catholic, Xavier College
  Prep, Holy Cross, Sacred Heart, St. Ignatius, All Saints Episcopal).

Naming rules the owner set: no "Hall", no "Landing"/"Pointe"/"Coupee" or the
Louisiana-French appellation register, no "Bend" or "Creek", nothing industrial, and
**no literal Native placenames** — where the ground suggested one, its MEANING is
rendered in English instead (Reed Lake for the tule marshes, North Wind for Yamsay,
Whitegrass for Wabuska, Uplands for Latgawa, Bravewoman for Winema, Quaking Aspen
for Lostine). The rest is plain naturalistic English.

`source` is stamped where the record had none, so `source or name` — the string that
seeds the pids — never moves, and the old name goes into former_names.json so
archived seasons relabel on read.

Run: python3 scripts/jhsaa_secularise_2065.py [--dry-run]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RENAMES: dict[str, str] = {
    # Alderwold
    "North Valley Christian": "Trailsend",
    "St. Helena": "Saltmarsh",
    # Bear River Country
    "Beargrass Christian": "Beargrass",
    "Cub River Catholic": "Coldwater",
    "Malad County Christian": "Sixmile",
    "Wellsville County Catholic": "Hyrum",
    # Belmonte Metro
    "Belmonte Catholic": "Belmonte South",
    "Cahokia Mounds Catholic": "Cahokia Mounds",
    # Boise Frontier
    "Archbishop Quinlan": "Quaking Aspen",
    "St. Genevieve": "Whitegrass",
    "St. Lucy": "Tallgrass",
    # Cascade Divide
    "Pope Victor I": "Bravewoman",
    "St. Sophia": "North Wind",
    "Western Slope Christian": "Western Slope",
    # Gold Valley
    "Cascade Christian": "Evenfall",
    "Eastmont Christian": "Eastmont",
    "Pope Francis": "Elkhorn",
    "Providence Catholic": "Starfield",
    "St. Agnes Preparatory": "Montelago West",
    "St. Gabriel Preparatory": "Orchardgate",
    "St. Isidore": "Averill Grange",
    "St. Olga College Prep": "Mercer Latin",
    # Halbrook Basin
    "Archbishop Doyle Prep": "Doyle",
    "Bishop Valera": "Valera",
    "St. Francis Xavier": "Pomar Union",
    "St. Perpetua": "Farview",
    # Juniper Highlands
    "Central Christian": "Winter Valley School",
    "Cornerstone Christian": "South Rim",
    # Kangas
    "Southern Jefferson Christian": "Uplands",
    "St. Casimir": "Harriman Lyceum",
    "St. Michael Academy": "Harriman East",
    # Millersylvania
    "St. Dominic Academy": "Wildrye",
    "St. Raphael College Prep": "Elk Bluff West",
    # Port Valdez
    "Sisters of Mercy": "Websterfield",
    # Sebastian Cape
    "Natchitoches Catholic": "Brightwater",
    "Our Lady of the Coast": "Windward",
    # Selquah
    "Faith Academy": "Michaela East",
    "Port Veles Lutheran": "Veles Union",
    "Saint Francis": "Kingsley",
    "Seminary": "Veles Park",
    "St. Elias Academy": "Port Ainsley",
    "Valley Providence": "Meridian Valley",
    # Silver Basin
    "Ruby County Catholic": "Carlin",
    "St. Martin Preparatory": "Greaves West",
    # Snake River Plain
    "Eden County Christian": "Eden",
    # Yarrowmere
    "Bishop Ferraro": "Ferraro",
    "Heritage Christian": "Longmeadow",
    "Presentation Academy": "Garrow North",
    "Trinity Christian": "Stillwater",
    "Tumbleweed Lutheran": "Reed Lake",
}

BANNED = re.compile(r"\b(Hall|Landing|Pointe|Coupee|Bend|Creek|Electric|Water &"
                    r"|Power|Works|Foundry|Mutual|Packing)\b")

SCHOOLS = ROOT / "data" / "jhsaa" / "schools.json"
FORMER = ROOT / "data" / "jhsaa" / "former_names.json"
IMPORTER = ROOT / "scripts" / "import_jhsaa.py"

TOUCH = [
    IMPORTER,
    ROOT / "scripts" / "jhsaa_2052_expansion.py",
    ROOT / "scripts" / "jhsaa_2056_promotions.py",
    ROOT / "scripts" / "jhsaa_2056_closures.py",
    ROOT / "scripts" / "jhsaa_promotions_and_affiliates.py",
    ROOT / "scripts" / "jhsaa_border_realignment.py",
    ROOT / "scripts" / "jhsaa_heritage_valley.py",
    ROOT / "scripts" / "jhsaa_reclassify.py",
    ROOT / "data" / "jhsaa" / "archetypes.json",
]


def _always_extra_range(text: str) -> tuple[int, int]:
    """ALWAYS_EXTRA holds prep-network SOURCE names, which a rename must not move."""
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

    bad = [n for n in RENAMES.values() if BANNED.search(n)]
    if bad:
        print("new name uses a banned word:", bad)
        return 1

    doc = json.loads(SCHOOLS.read_text())
    rows = doc["schools"]
    names = {r["name"] for r in rows}
    missing = [o for o in RENAMES if o not in names]
    taken = [n for n in RENAMES.values() if n in names and n not in RENAMES]
    if missing or taken:
        print("no such school:", missing, "| already taken:", taken)
        return 1

    for row in rows:
        old = row["name"]
        if old not in RENAMES:
            continue
        row.setdefault("source", old)   # pin the roster identity before the name moves
        row["name"] = RENAMES[old]
        row["private"] = False
        print(f"  {old:<30} -> {row['name']:<20} {row['group']:<8} {row['city']}")

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
        table.pop(fresh, None)
        table[old] = fresh
    former["former_names"] = dict(sorted(table.items()))

    # PRIVATE_SCHOOLS forces its members private at emit, so a flipped program
    # listed there would revert on the next import.
    text = IMPORTER.read_text()
    for old in RENAMES:
        text = text.replace(f'"{old}", ', "").replace(f'"{old}",\n', "\n")
    if not dry:
        IMPORTER.write_text(text)

    for path in TOUCH:
        if path.exists():
            n = rewrite(path, dry)
            if n:
                print(f"  {path.relative_to(ROOT)}: {n} line(s)")

    if not dry:
        SCHOOLS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        FORMER.write_text(json.dumps(former, indent=2, ensure_ascii=False) + "\n")
    print("dry run — nothing written" if dry else "written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
