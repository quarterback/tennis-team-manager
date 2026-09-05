"""Owner rule 2026-09: Port Meridian North and Cherry Hill North come back, in 2A.

Both compass campuses had stopped sponsoring tennis (the `former_school` path
kept their pages and their history). The owner brings both programs back as
2A schools — a RECLASSIFICATION, the Lower Lake idiom: `classification`,
`group` AND `enrollment` move together, the number following the decision
(both sit inside 2A's committed 86-431 band).

Each joins the CLOSEST existing 2A league (county match first, then area —
the play-up placement doctrine; both leagues are at 9-10 of 12, so nothing
redraws): Port Meridian North -> Foundry League (3 Bidwell county-mates,
4 Selquah area-mates), Cherry Hill North -> Desert Sky League (3 Halbrook
county-mates).

Their history is untouched: the archive keeps the seasons they played, the
dormant years list as nothing (no rows exist for them), and the record
simply resumes the year they next take the court. The rivalry triangles in
`jhsaa.RIVAL_OVERRIDES` go live by themselves once the flags are on, and
the two returning Norths are also each other's rival (both 2A now) — that
pair rides in RIVAL_OVERRIDES beside the triangles.

Replay AFTER a re-import, like the other targeted transforms. Idempotent.

Run: python3 scripts/jhsaa_norths_to_2a.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHOOLS = ROOT / "data" / "jhsaa" / "schools.json"

RETURNS = {
    "Port Meridian North": {"enrollment": 348, "district": "Foundry League"},
    "Cherry Hill North": {"enrollment": 361, "district": "Desert Sky League"},
}


def main() -> int:
    dry = "--dry-run" in sys.argv
    doc = json.loads(SCHOOLS.read_text())
    hit = 0
    for row in doc["schools"]:
        plan = RETURNS.get(row["name"])
        if not plan:
            continue
        hit += 1
        row.update(classification="2A", group="2A",
                   enrollment=plan["enrollment"],
                   girls=True, boys=True,
                   girls_district=plan["district"],
                   boys_district=plan["district"])
        print(f"  {row['name']:20} -> 2A · {plan['district']} · {plan['enrollment']}")
    if hit != len(RETURNS):
        print("missing school(s)")
        return 1
    if not dry:
        SCHOOLS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print("dry run — nothing written" if dry else "written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
