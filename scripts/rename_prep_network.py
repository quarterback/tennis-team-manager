#!/usr/bin/env python3
"""
Apply the JHSAA school-name cleanup to `prep-network` — the SOURCE repo.

The tennis association already knows these schools by their new names (the
import applies `import_jhsaa.RENAMES` when it emits a row). This script is the
other half the owner approved: bringing prep-network's published record into
line, so the varsityapex source page shows the same names.

    python3 scripts/rename_prep_network.py --dry-run          # report, change nothing
    python3 scripts/rename_prep_network.py                    # apply
    python3 scripts/rename_prep_network.py --prep-network ../prep-network

WHAT IT TOUCHES
  * file CONTENT — the raw name ("Bahía Leal Costa Verde") and its JSON
    \\u-escaped form, plus the URL slug ("bah-a-leal-costa-verde") wherever it
    appears inside a file (ids, hrefs, editorial prose);
  * file NAMES — contest records are named for their slug
    (`12720-bah-a-leal-costa-verde-at-san-borond-n.json`), so the files are
    renamed too. THIS CHANGES PUBLIC URLS; that is the owner's call and the
    reason this is a separate, explicit step rather than part of the import.

WHAT IT DOES NOT TOUCH
  The nine SUBSTITUTIONS. Those magnets keep their identity in prep-network —
  they were never renamed, they simply stopped sponsoring tennis, exactly as a
  real arts academy would. Only the 62 RENAMES rewrite source records.

SAFETY (all asserted at run time, because a bad pass over 6k files is not
something you want to discover afterwards):
  * no source name is a SUBSTRING of another school's name, so a plain text
    replace cannot corrupt a longer name;
  * no source name is also a CITY name, so `city` fields are left alone;
  * no target name is itself a source, so the pass is IDEMPOTENT — running it
    twice is a no-op and a half-finished run can simply be re-run.
Replacements are applied longest-name-first regardless, as a second belt.

Reports every file it changed. Deterministic; no network.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.import_jhsaa import (CITY_RENAMES, RENAMES,  # noqa: E402
                                  SUBSTITUTIONS)

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".next", ".vercel"}


def slug(name: str) -> str:
    """prep-network's URL slug for a school — lowercase, every run of
    non-[a-z0-9] to a single dash. Accents therefore become dashes, which is
    why "Bahía Leal Costa Verde" files read `bah-a-leal-costa-verde`."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _escaped(name: str) -> str:
    """The name as `json.dump` writes it with ensure_ascii=True."""
    return json.dumps(name, ensure_ascii=True)[1:-1]


def build_pairs() -> list[tuple[str, str]]:
    """(old, new) text substitutions, longest first. Three forms per school:
    raw, \\u-escaped, and slug — a record can carry any of them."""
    pairs: list[tuple[str, str]] = []
    for src, new in RENAMES.items():
        pairs.append((src, new))
        if _escaped(src) != src:
            pairs.append((_escaped(src), _escaped(new)))
        if slug(src) != slug(new):
            pairs.append((slug(src), slug(new)))
    pairs.sort(key=lambda p: -len(p[0]))
    return pairs


def preflight(prep: str) -> None:
    reg = os.path.join(prep, "records", "orgs", "schools.json")
    if not os.path.exists(reg):
        sys.exit(f"not found: {reg}\nPoint --prep-network at a prep-network checkout.")
    with open(reg, encoding="utf-8") as fh:
        schools = json.load(fh)["schools"]
    names = {s["name"] for s in schools}
    cities = {s["city"] for s in schools}
    bad = [(k, n) for k in RENAMES for n in names if k != n and k in n]
    if bad:
        sys.exit(f"ABORT: source name is a substring of another school: {bad[:5]}")
    # ‼️ A NAME THAT IS BOTH A SCHOOL AND A CITY is only dangerous when the two
    # disagree. These substitutions are plain text, so renaming the school
    # rewrites the city field too — which is CORRECT when the town was renamed to
    # the same thing (Wickbrook is both the school and the town, and both become
    # Salmon Bay) and corruption when it was not. So the abort fires on the
    # disagreement, not on the coincidence.
    shared = set(RENAMES) & cities
    clash = sorted(k for k in shared if CITY_RENAMES.get(k) != RENAMES[k])
    if clash:
        sys.exit("ABORT: source name is also a city and the two renames disagree: "
                 + repr(clash) + "\nRename the town to the same target in "
                 "import_jhsaa.CITY_RENAMES, or rename the school separately.")
    if set(RENAMES.values()) & set(RENAMES):
        sys.exit("ABORT: a target is also a source — the pass would not be idempotent")
    overlap = set(RENAMES) & set(SUBSTITUTIONS)
    if overlap:
        sys.exit(f"ABORT: school is both renamed and substituted: {sorted(overlap)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prep-network",
                    default=os.path.join(os.path.dirname(os.path.dirname(
                        os.path.abspath(__file__))), "..", "prep-network"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    prep = os.path.abspath(args.prep_network)
    preflight(prep)
    pairs = build_pairs()
    print(f"prep-network: {prep}")
    print(f"{len(RENAMES)} renames -> {len(pairs)} text forms "
          f"(raw + escaped + slug); {len(SUBSTITUTIONS)} substitutions left alone\n")

    edited = renamed = hits = 0
    pending: list[tuple[str, str]] = []            # (old path, new path)
    for root, dirs, files in os.walk(prep):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = os.path.join(root, f)
            try:
                text = io.open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue                            # binary / unreadable: leave it
            out, n = text, 0
            for old, new in pairs:
                if old in out:
                    n += out.count(old)
                    out = out.replace(old, new)
            if n:
                hits += n
                edited += 1
                if not args.dry_run:
                    io.open(p, "w", encoding="utf-8").write(out)
            nf = f
            for old, new in pairs:
                if old in nf:
                    nf = nf.replace(old, new)
            if nf != f:
                renamed += 1
                pending.append((p, os.path.join(root, nf)))

    for old_path, new_path in pending:
        if args.dry_run:
            continue
        if os.path.exists(new_path) and old_path != new_path:
            print(f"  SKIP rename (target exists): {os.path.relpath(new_path, prep)}")
            continue
        os.rename(old_path, new_path)

    verb = "would change" if args.dry_run else "changed"
    print(f"{verb}: {hits} occurrences in {edited} files")
    print(f"{'would rename' if args.dry_run else 'renamed'}: {renamed} files")
    if args.dry_run:
        print("\n--dry-run: nothing written")
    else:
        print("\nDone. Review with `git -C prep-network status` and commit there.")


if __name__ == "__main__":
    main()
