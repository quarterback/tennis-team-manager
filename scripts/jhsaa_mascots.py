#!/usr/bin/env python3
"""Apply the mascot cleanup to the committed association data.

‼️ HOLDS NO NAMES OF ITS OWN. Every table comes from `import_jhsaa` — `MASCOT_FIXES`
(the foreign-fauna cleanup, keyed on the offending mascot) and `MASCOTS` (per-school
owner picks) — exactly like `jhsaa_apply_renames.py` and `jhsaa_sponsors.py`. The
importer stays the one authority and a full re-import supersedes this; the script
exists only because the data file is committed and re-importing it is a bigger step
than fixing the names in place.

    python3 scripts/jhsaa_mascots.py --dry-run     # report, change nothing
    python3 scripts/jhsaa_mascots.py               # rewrite data/jhsaa/schools.json

Idempotent: a second run reports nothing to do, because the replacements are drawn
from pools that contain no offending name.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.import_jhsaa import MASCOTS, MASCOT_FIXES, fix_mascot  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "jhsaa", "schools.json")


def plan(rows: list[dict]) -> list[tuple[str, str, str, str]]:
    """(school, old, new, why) for every row the tables change."""
    out = []
    for r in rows:
        old = r.get("mascot", "")
        pick = MASCOTS.get(r["name"])
        new = pick or fix_mascot(r["name"], old)
        if new != old:
            out.append((r["name"], old, new, "owner" if pick else "fauna"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    doc = json.load(open(DATA, encoding="utf-8"))
    rows = doc["schools"]
    changes = plan(rows)

    before = collections.Counter(r.get("mascot", "") for r in rows)
    print(f"{len(rows)} schools · {len(before)} distinct mascots")
    if not changes:
        print("nothing to do — the data already matches the tables")
        return 0

    by_old = collections.defaultdict(list)
    for school, old, new, why in changes:
        by_old[old].append((school, new, why))
    print(f"\n{len(changes)} schools change, {len(by_old)} names retired:\n")
    for old in sorted(by_old, key=lambda k: (-len(by_old[k]), k)):
        picks = collections.Counter(new for _s, new, _w in by_old[old])
        tail = ", ".join(f"{n} ×{c}" if c > 1 else n for n, c in picks.most_common())
        print(f"  {old:<18} ({len(by_old[old])}) → {tail}")
    owner = [c for c in changes if c[3] == "owner"]
    if owner:
        print("\nowner picks:")
        for school, old, new, _w in owner:
            print(f"  {school:<32} {old} → {new}")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    fixes = {school: new for school, _o, new, _w in changes}
    for r in rows:
        if r["name"] in fixes:
            r["mascot"] = fixes[r["name"]]
    with open(DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    after = collections.Counter(r.get("mascot", "") for r in rows)
    print(f"\nwrote {DATA}")
    print(f"{len(after)} distinct mascots now · biggest: "
          + ", ".join(f"{m} {n}" for m, n in after.most_common(5)))
    # The cleanup must not leave a new pile-up where it removed one.
    grew = [(m, after[m] - before.get(m, 0)) for m in after
            if after[m] - before.get(m, 0) >= 4]
    if grew:
        print("names that grew by 4+: "
              + ", ".join(f"{m} +{d}" for m, d in sorted(grew, key=lambda x: -x[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
