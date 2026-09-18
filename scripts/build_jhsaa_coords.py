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
    out = {}
    with open(_DOC, encoding="utf-8") as fh:
        for line in fh:
            m = _LINE.match(line.rstrip("\n"))
            if not m:
                continue
            lat = float(m["lat"]) * (-1 if m.group(3) == "S" else 1)
            lon = float(m["lon"]) * (-1 if m.group(5) == "W" else 1)
            out.setdefault(m["town"], [lat, lon])
    return out


def main() -> None:
    coords = build()
    with open(_OUT, "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(coords.items())), fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {len(coords)} towns to {_OUT}")


if __name__ == "__main__":
    main()
