"""List every JHSAA program that has ever won a title, so a rename pass can skip them.

A rename moves the DISPLAY name, which is the archive identity, and the owner's rule
is that a program with a title in the cabinet keeps its name. That cabinet lives in
the save, not in the repo — so this reads the archive the app reads and prints the
protected set. Run it against your own database:

    TENNIS_DB_PATH=/path/to/tennis.db python3 scripts/jhsaa_title_holders.py
    TENNIS_DB_PATH=... python3 scripts/jhsaa_title_holders.py --check docs/PROPOSAL-jhsaa-private-thinning.md

With --check it reads a proposal table and reports which rows name a title holder,
exiting non-zero if any do.
"""

from __future__ import annotations

import re
import sys

from app import world


def title_holders() -> dict[str, list[str]]:
    """school -> the titles it holds, over every archived season."""
    held: dict[str, list[str]] = {}

    def add(school: str, what: str) -> None:
        held.setdefault(school, []).append(what)

    for gender in ("girls", "boys"):
        for year in world.jhsaa_years(gender):
            season = world.get_jhsaa(gender, year)
            if not season:
                continue
            for grp, rows in (season.get("standings") or {}).items():
                pass
            for grp, champ in (season.get("champions") or {}).items():
                if champ:
                    add(champ, f"{year} {gender} {grp} state")
            toc = season.get("toc_champion")
            if toc:
                add(toc, f"{year} {gender} TOC")
            # unit titles (leagues and the road to State) count too — a district or
            # a region is a trophy the program keeps.
            for grp, districts in (season.get("district_champions") or {}).items():
                for name, champ in (districts or {}).items():
                    if champ:
                        add(champ, f"{year} {gender} {grp} {name}")
    return held


def main() -> int:
    held = title_holders()
    if "--check" not in sys.argv:
        for school in sorted(held):
            print(f"{school}\t{len(held[school])} title(s)\te.g. {held[school][0]}")
        print(f"\n{len(held)} programs hold at least one title")
        return 0

    path = sys.argv[sys.argv.index("--check") + 1]
    rows = [
        m.group(1).strip()
        for m in re.finditer(r"^\|\s*([^|]+?)\s*\|", open(path).read(), re.M)
    ]
    hits = [r for r in rows if r in held]
    for r in hits:
        print(f"PROTECTED — {r}: {len(held[r])} title(s), e.g. {held[r][0]}")
    print(f"{len(hits)} of the proposal's rows name a title holder")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
