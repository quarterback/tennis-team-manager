#!/usr/bin/env python3
"""Move the Columbia Gorge District and Columbia Range League down to 1A
(owner rule 2026-09: "move the Columbia Gorge and Columbia Range 2A schools
down to 1A").

    python3 scripts/jhsaa_columbia_to_1a.py [--dry-run]

Two whole 2A leagues — the 2052 eastern Oregon / Columbia Gorge affiliates as
they stand after the border realignment, plus Mt Jacqueline, the one Jefferson
program seated in the Gorge district — reclassify to 1A AS INTACT LEAGUES. A
district is `(classification, name)`, so the league names travel with the rows
that carry them and the two leagues simply exist in 1A from here on; nothing is
redrawn (1A goes from seven leagues to nine and 2A from ten to eight, both
exactly what `import_jhsaa.district_count` wants for the new pool sizes, so no
class needs a redistricting pass).

This is a RECLASSIFICATION, not a play-down (the Lower Lake / RECLASSIFY_TO_2A
/ 2056-promotions idiom): `classification`, `group` AND `enrollment` move
together, because `_TALENT` and `roster_size` generate from `classification`
and the association is saying these are 1A-sized schools — which, at 88-300
students, nearly all of them already are. A row whose enrollment already sits
inside 1A's committed band keeps its number; one above it (Mt Jacqueline, 347)
takes a stable band-legal number (`_reclass_enrollment`'s seed idiom), so the
number follows the decision without reshuffling everybody else.

Every row seated in either league moves, sponsoring or not: Nixyaawii keeps its
data row under `former_school` and stays a member of its league, so the league
reads the same from its page and from a former program's.

Idempotent: keyed assignments; a row already at 1A is skipped. Replay after
`jhsaa_2052_expansion.py`, `jhsaa_affiliate_leagues.py` and
`jhsaa_border_realignment.py`, whose seating this reads.
"""
import argparse
import json
import os
import random

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")

LEAGUES = ("Columbia Gorge District", "Columbia Range League")
TARGET = "1A"


def _band(rows, group):
    """The target class's committed enrollment band, off the rows already in it."""
    v = sorted(r["enrollment"] for r in rows
               if r.get("classification") == group and r.get("enrollment"))
    return v[0], v[-1]


def apply(rows: list[dict]) -> list[str]:
    log = []
    lo, hi = _band(rows, TARGET)
    for r in rows:
        if not (r.get("girls_district") in LEAGUES or r.get("boys_district") in LEAGUES):
            continue
        if r.get("classification") == TARGET and r.get("group") == TARGET:
            continue
        enr = r.get("enrollment", 0)
        if not (lo <= enr <= hi):
            enr = random.Random(f"jhsaa-reclass-enrollment|{r['name']}").randint(lo, hi)
        log.append(f"{r['name']:18} {r.get('classification')}/{r.get('group')} -> {TARGET} "
                   f"({r.get('girls_district')}; enroll {r.get('enrollment')} -> {enr})")
        r["classification"] = r["group"] = TARGET
        r["enrollment"] = enr
    return log


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    log = apply(doc["schools"])
    for line in log:
        print(line)
    if not log:
        print("nothing to do (already applied)")
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nwrote {_DATA}")


if __name__ == "__main__":
    main()
