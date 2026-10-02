#!/usr/bin/env python3
"""Redraw the JHSAA's Non-Public leagues (10B / 11B) like every other class's.

There are no pods (owner rule 2026-10). Every private program sits in its
Non-Public class — 10B at or above `jhsaa.NONPUBLIC_CUT` (nothing is pinned by name),
else 11B — and the two classes' leagues are drawn by `jhsaa_districting.redistrict`
with the association's own `district_count` and cap, over the programs that
sponsor a team. The app applies the same rule on every load
(`jhsaa_districting.ensure_nonpublic`, from `jhsaa._rows()`), so a save can never
play on a map that puts a private back in a public league or leaves a Non-Public
league of two; this script is the forced redraw for when the owner wants the
leagues drawn afresh.

Usage: python3 scripts/jhsaa_nonpublic_leagues.py [--dry-run]
"""
from __future__ import annotations

import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import jhsaa as jh                      # noqa: E402
from app import jhsaa_districting as jd          # noqa: E402

PATH = os.path.join(ROOT, "data", "jhsaa", "schools.json")


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    with open(PATH, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"]
    out = jd.ensure_nonpublic(rows, jh.NONPUBLIC_CUT, jh.NONPUBLIC_PLAYUP,
                              force=True, log=print)
    print(f"{out['moved']} private rows moved to their Non-Public class; "
          f"redrawn: {out['redrawn']}")
    for cls in jh.NONPUBLIC_GROUPS:
        for g in ("girls", "boys"):
            sizes = collections.Counter(r[f"{g}_district"] for r in rows
                                        if r["group"] == cls and r.get(g))
            print(f"{cls} {g}: {sum(sizes.values())} programs in {len(sizes)} leagues "
                  f"{sorted(sizes.values())}")
    if dry:
        print("dry run — nothing written")
        return 0
    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
