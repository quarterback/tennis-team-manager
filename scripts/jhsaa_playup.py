#!/usr/bin/env python3
"""Seed the `play_up` flag in `data/jhsaa/schools.json`.

    python3 scripts/jhsaa_playup.py [--dry-run]

‼️ WHAT PLAYING UP IS (owner rule 2027-08). A school competing one classification
ABOVE its enrollment class, the way real associations let a strong program do. It is
a property of programs that are good at TENNIS, so the candidates are the blue-bloods
— `data/jhsaa/archetypes.json`, the association's own durable "this program is good"
list — and never a hand-written list of school names, which is the rule archetypes
themselves follow.

‼️ IT MOVES `group`, NEVER `classification`. `group` is the championship you enter;
`classification` is how many students you have, and `_TALENT` reads the latter
(`jhsaa.School.talent_group`). Playing up must COST you a harder field, not buy you
better players — key the bands on `group` and it silently becomes a free roster
upgrade, which inverts the entire choice. This script therefore writes only a flag;
`jhsaa.load_schools` derives the group, and `jhsaa.play_up_district` moves the league
with the program so it is not the only team in a district of its new class.

The flag is a SEED. `overrides.set_jhsaa_playup` layers on top — "yes" promotes a
school this file did not pick, "no" demotes one it did, clearing reverts — exactly
how the archetype table sits over its own seed list.

Idempotent: the pick is seeded and deterministic, so a second run writes the same
flags. `--dry-run` proves it before you commit.
"""
import argparse
import collections
import importlib.util
import json
import os
import random

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")
_ARCH = os.path.join(_REPO, "data", "jhsaa", "archetypes.json")


def _import_jhsaa():
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pick(rows: list[dict], m) -> list[dict]:
    """The blue-bloods that play up, weighted toward the top of their own class."""
    with open(_ARCH, encoding="utf-8") as fh:
        arch = json.load(fh)["programs"]
    # ‼️ SMALL SCHOOLS ONLY (owner correction 2027-08). "Play up is for schools at the
    # 4A or under level to play with teams at their competitive level, not already big
    # schools." An 8A blue-blood moving to 9A is not playing up — it is a big school in
    # a slightly bigger class — and the first pass shipped exactly that. Eligibility
    # starts at `PLAY_UP_MAX_GROUP` and runs down; 9A's exclusion falls out of it.
    # Ladder only (2046 expansion): the Great Basin Division 1/2 groups sit AFTER
    # 1A in GROUPS, so a raw index test read them as "4A or below" — but play-up
    # does not exist in the Division system (see `app.jhsaa.can_play_up`).
    ladder = [g for g in m.GROUPS if g not in ("Division 1", "Division 2")]
    floor = ladder.index(m.PLAY_UP_MAX_GROUP)
    pool = [r for r in rows
            if arch.get(r["name"]) == "blue_blood"
            and r["group"] in ladder and ladder.index(r["group"]) >= floor
            and (r["girls"] or r["boys"])]
    # Rank within the class by enrollment — a school already near the cut line is the
    # one that plausibly plays up — then draw without replacement on that weight.
    top = collections.defaultdict(list)
    for r in pool:
        top[r["group"]].append(r)
    rank = {}
    for group, rs in top.items():
        rs.sort(key=lambda r: -r["enrollment"])
        for i, r in enumerate(rs):
            rank[r["name"]] = 1.0 / (i + 1)
    rng = random.Random(m.PLAY_UP_SEED)
    chosen, left = [], sorted(pool, key=lambda r: r["name"])
    while left and len(chosen) < m.PLAY_UP_COUNT:
        weights = [rank[r["name"]] for r in left]
        r = rng.choices(left, weights=weights, k=1)[0]
        left.remove(r)
        chosen.append(r)
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    m = _import_jhsaa()
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"]

    chosen = {r["name"] for r in pick(rows, m)}
    for r in rows:
        if r["name"] in chosen:
            r["play_up"] = True
        else:
            r.pop("play_up", None)      # absent reads as False; never write a False

    for r in rows:
        if r.get("play_up"):
            print(f"  {r['name'][:30]:30} {r['classification']:5} -> plays up   "
                  f"{r['enrollment']:5}  {r['city']} ({r['area']})")
    print(f"{len(chosen)} programs play up")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_DATA}")


if __name__ == "__main__":
    main()
