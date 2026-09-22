#!/usr/bin/env python3
"""Write `data/jhsaa/coords.json` — {town: [lat, lon]} — from the generated gazetteer.

    python3 scripts/build_jhsaa_coords.py

The in-app reclassification redraws leagues through the same clustering
`scripts/jhsaa_redistrict.py` uses, and that clustering needs a position per
town. The script reads prep-network's `cities.json`, which the app cannot (a
sibling repo, absent in deployment). `docs/GAZETTEER-jefferson.md` already
prints every town's coordinates — it is generated from the same sources plus
the expansion tables — so this derives the app's copy from it, one line per
town, and never invents a place. Re-run after `scripts/jefferson_gazetteer.py`.
"""
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DOC = os.path.join(_REPO, "docs", "GAZETTEER-jefferson.md")
_OUT = os.path.join(_REPO, "data", "jhsaa", "coords.json")
_LINE = re.compile(r"^- \*\*(?P<town>.+?)\*\* — .*?(?P<lat>\d+\.\d+)([NS]) (?P<lon>\d+\.\d+)([EW])\s*$")


def build() -> dict:
    """{town: [lat, lon]}. The file is keyed on the town NAME because that is what a
    school row carries, and two towns in the state can share one (Trout Lake, WA
    and Jefferson's own Trout Lake in Rimrock County). When they do, the entry that
    lists tennis programs beneath it wins — the coordinate exists to place
    PROGRAMS, and the other town has none to place."""
    out: dict = {}
    progs: dict = {}
    cur = None
    with open(_DOC, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            m = _LINE.match(line)
            if m:
                cur = m["town"]
                lat = float(m["lat"]) * (-1 if m.group(3) == "S" else 1)
                lon = float(m["lon"]) * (-1 if m.group(5) == "W" else 1)
                n = 0 if "*no tennis programs*" in line else None
                if cur not in out or (progs.get(cur, 0) == 0 and n is None):
                    out[cur] = [lat, lon]
                    progs[cur] = 0
                elif n is None and progs.get(cur, 0) > 0:
                    cur = None   # a later duplicate with programs never displaces one that has them
                continue
            if cur and line.startswith("    - "):
                progs[cur] = progs.get(cur, 0) + 1
    return out


def main() -> None:
    coords = build()
    with open(_OUT, "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(coords.items())), fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {len(coords)} towns to {_OUT}")


if __name__ == "__main__":
    main()
