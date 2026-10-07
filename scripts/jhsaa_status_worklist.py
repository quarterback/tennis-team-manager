#!/usr/bin/env python3
"""Apply the owner's public/private STATUS decisions to `data/jhsaa/schools.json`.

    python3 scripts/jhsaa_status_worklist.py [--dry-run]

**It holds no names of its own.** `import_jhsaa.PRIVATE_SCHOOLS` and
`import_jhsaa.PUBLIC_SCHOOLS` are the single authority (the 2026-10 worklist: 15
publics ruled private, 3 privates ruled public); this script is the transform that
brings the committed file in line with them, the `jhsaa_apply_renames.py` idiom.

What a status change does, and does not, touch:
  * `private` follows the tables. A school ruled PRIVATE goes to its Non-Public
    class by the 550 cut — `jhsaa_districting.ensure_nonpublic` under its standing rule (force OFF, so a
    private a later cycle has already placed stays put), which also records the public league it leaves as
    `old_group`/`old_league` and redraws 10B/11B. A school ruled PUBLIC returns to
    its size class (`group = classification`), drops `old_group`/`old_league`, and
    takes the seat in that league (no redraw of the class for one returning member).
  * Public classes are NOT redrawn for a status change: a departing private's
    league loses one member, a returning public takes the seat its `old_league`
    held for it. `redraw_classes` runs only for a returning public with no old
    league recorded.
  * `source`, `name` and so every pid are UNTOUCHED — rosters, history and archived
    seasons stay as played. Status is a map decision, not an identity.

Idempotent: a second run finds every flag already agreeing with the tables and
changes nothing.
"""
import argparse
import collections
import importlib.util
import json
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")


def _import_jhsaa():
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def wanted_private(row: dict, m) -> bool:
    name = row["name"]
    if name in getattr(m, "PUBLIC_SCHOOLS", set()):
        return False
    return bool(row.get("private")) or name in m.PRIVATE_SCHOOLS


def sizes(rows, cls):
    out = {}
    for g in ("girls", "boys"):
        c = collections.Counter(r[f"{g}_district"] for r in rows
                                if r["group"] == cls and r.get(g))
        out[g] = (sum(c.values()), sorted(c.values()))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    m = _import_jhsaa()
    sys.path.insert(0, _REPO)
    os.environ.setdefault("TENNIS_DB_PATH", os.path.join(_REPO, ".jhsaa_status_scratch.db"))
    from app import jhsaa as jh
    from app import jhsaa_districting as jd

    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"]

    to_private, to_public = [], []
    for r in rows:
        want = wanted_private(r, m)
        if want and not r.get("private"):
            to_private.append(r)
        elif not want and r.get("private"):
            to_public.append(r)
    touched = set()
    for r in to_private:
        # The public league it leaves simply loses a member; its class is NOT
        # redrawn (a full redraw through the clusterer moves every school's
        # league and, measured on 7A and 1A, leaves 5- and 3-team leagues).
        r["private"] = True                  # ensure_nonpublic does the move
    for r in to_public:
        r["private"] = False
        r["group"] = r["classification"]
        # A private already carries the public league it would sit in
        # (`old_league`, reset at every realignment), so a school ruled public
        # simply takes that seat — no redraw of its class, which would move every
        # other school's league for one returning member.
        r["girls_district"] = r["boys_district"] = r.pop("old_league", "") or ""
        r.pop("old_group", None)
        if not r["girls_district"]:
            touched.add(r["group"])
    if not (to_private or to_public):
        print("every flag already agrees with the tables; nothing to do")
        return
    public_cls = {r["classification"] for r in to_private} | {r["group"] for r in to_public}
    before = {cls: sizes(rows, cls) for cls in sorted(touched | public_cls | set(jh.NONPUBLIC_GROUPS))}

    # Standing rule, force OFF: only a private still in a public group (the ones
    # this run just flagged) is cut by enrollment and seated; a private a later
    # reclassification cycle moved between 10B and 11B stays where the cycle
    # put it. (The run already returns above when no flag changes.)
    out = jd.ensure_nonpublic(rows, jh.NONPUBLIC_CUT, jh.NONPUBLIC_PLAYUP, log=print)
    print(f"{out['moved']} private rows moved to their Non-Public class; "
          f"redrawn: {out['redrawn']}")
    notes = jd.redraw_classes(rows, sorted(touched))
    for cls, ns in notes.items():
        for n in ns:
            print(f"  {cls}: {n.strip()}")

    for r in to_private + to_public:
        print(f"  {r['name']:26} {'private' if r['private'] else 'public ':7} "
              f"{r['classification']:>7} {r['enrollment']:5} -> {r['group']:7} "
              f"{r['girls_district']}" + (f"  (old: {r.get('old_group')} {r.get('old_league')})"
                                         if r.get('old_group') else ""))
    # Only the rows THIS run seated must agree with the cut — an older private may
    # legitimately sit where a later reclassification cycle moved it.
    for r in to_private:
        if r["group"] != jd.nonpublic_class(r, jh.NONPUBLIC_CUT, jh.NONPUBLIC_PLAYUP):
            sys.exit(f"{r['name']}: seated in {r['group']} against the {jh.NONPUBLIC_CUT} cut")
    for r in rows:
        if not r.get("private") and r["group"] in jh.NONPUBLIC_GROUPS:
            sys.exit(f"{r['name']}: public row in {r['group']}")
    cfg = jd.districting_config()
    for cls in before:
        for g, (n, s) in sizes(rows, cls).items():
            bn, bs = before[cls][g]
            print(f"  {cls:8} {g:5} {bn:3} -> {n:3} programs, leagues {bs} -> {s}")
            # Leagues are drawn once per class over the girls-inclusive pool; the
            # boys' half is whatever share of it fields a boys team, so only the
            # girls' sizes are the drawn 8-11 (CLAUDE.md, league identity).
            if cls in jh.NONPUBLIC_GROUPS and g == "girls" and s and (
                    max(s) > cfg.MAX_DISTRICT or min(s) < cfg.MIN_DISTRICT_SIZE):
                sys.exit(f"{cls} {g}: league outside {cfg.MIN_DISTRICT_SIZE}-{cfg.MAX_DISTRICT}: {s}")
    if args.dry_run:
        print("--dry-run: nothing written")
        return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("wrote", _DATA)


if __name__ == "__main__":
    main()
