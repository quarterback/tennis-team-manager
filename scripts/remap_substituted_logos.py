#!/usr/bin/env python3
"""Repair pass: many real programs (Duke, LSU, Michigan, Louisiana, Boston
University, Appalachian State, …) were wrongly demoted to a *borrowed* substitute
logo by the earlier fast-finisher (`substitute_logos.py`) — an espn_id-collision
heuristic mis-fired and handed e.g. Duke → Dartmouth's Big Green art.

This re-matches every ``logo_source: "sub:*"`` entry against the live ESPN index
and promotes only the *safe* hits: a match whose espn_id is **not already owned by
a different real school**. That guard rejects the classic false positive where
``norm()`` strips "College"/"University" as a stopword and collapses a small
school onto the D1 of the same city — "Colorado College" → Colorado (38),
"Boston University" → Boston College (103) — so those legitimately keep their
substitute. Promoted schools get the real logo downloaded (scaled to the game
box) and their entry rewritten to ``{"slug", "espn_id"}`` (dropping logo_source).

Run:
  python3 scripts/remap_substituted_logos.py --dry-run
  python3 scripts/remap_substituted_logos.py
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_team_logos as F
from substitute_logos import save_scaled, download, LOGO_DIR, MAP


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("Building ESPN team index…", file=sys.stderr)
    index = F.build_index()
    keys = list(index)

    logos = json.loads(MAP.read_text())
    # espn_id -> real owner(s) already in the map (so we never steal an id).
    owner: dict[str, list[str]] = {}
    for k, v in logos.items():
        if isinstance(v, dict) and v.get("espn_id"):
            owner.setdefault(v["espn_id"], []).append(k)

    subs = [k for k, v in logos.items()
            if isinstance(v, dict) and str(v.get("logo_source", "")).startswith("sub:")]

    promote: list[tuple[str, str, str]] = []   # (school, espn_id, href)
    collide: list[tuple[str, str, list[str]]] = []
    for s in sorted(subs):
        m = F.match(s, index, keys)
        if not m:
            continue
        tid, href = m
        if tid in owner:                        # id already a real school -> false match
            collide.append((s, tid, owner[tid]))
        else:
            promote.append((s, tid, href))
            owner.setdefault(tid, []).append(s)  # claim it so two subs can't share

    print(f"\nsub entries: {len(subs)}  promotable: {len(promote)}  "
          f"collisions kept as substitute: {len(collide)}")
    print("\nPromoting:")
    for s, tid, _ in promote:
        print(f"   {s:30} -> espn_id {tid}")
    print("\nKept as substitute (id owned by a different real school):")
    for s, tid, o in collide:
        print(f"   {s:30} -> {tid} already {o}")

    if args.dry_run:
        return 0

    ok = fail = 0
    for s, tid, href in promote:
        if href.startswith("//"):
            href = "https:" + href
        slug = F.slugify(s)
        if download(href, LOGO_DIR / f"{slug}.png"):
            logos[s] = {"slug": slug, "espn_id": tid}
            ok += 1
        else:
            fail += 1
    MAP.write_text(json.dumps(logos, indent=2, sort_keys=True) + "\n")
    print(f"\nPromoted {ok} logos ({fail} failed). Map -> {MAP.relative_to(F.ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
