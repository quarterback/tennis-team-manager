#!/usr/bin/env python3
"""Apply `import_jhsaa`'s name tables to the committed `data/jhsaa/schools.json`.

    python3 scripts/jhsaa_apply_renames.py [--dry-run]

‼️ WHY THIS EXISTS, AND WHY IT IS NOT `import_jhsaa.py`
-------------------------------------------------------
`data/jhsaa/schools.json` **can no longer be regenerated**, and that is a fact about
the world rather than a preference. `scripts/import_jhsaa.py` reads
`prep-network/records/orgs/schools.json`, and prep-network carries **840 schools in
seven classifications (7A-1A) at every revision on every ref in its history** — there
is no 9A or 8A anywhere in it. The committed data is 857 girls'/772 boys' programs
across NINE classes and was produced by commit `3c36b16` ("Re-imported against the
rebuilt records"); those rebuilt records were never committed to prep-network. Running
the importer today emits a different association: 637 sponsors, seven classes, no 9A.

So the committed file is the de-facto source of record, and a change to it has to be
applied AS A TRANSFORM rather than by regeneration. This script is that transform.

**It holds no names of its own.** Every table it applies — `RENAMES`, `MASCOTS`,
`COLORS`, `PRIVATE_SCHOOLS`, `_display_name` — is imported from `import_jhsaa`, which
stays the single authority the way `CLAUDE.md` requires. When prep-network's nine-class
records are eventually rebuilt, the importer produces the same rows and this script
becomes a no-op rather than a second opinion.

**It is idempotent**, and that is load-bearing because it rewrites the file in place.
`RENAMES` is keyed on the SOURCE name, and a renamed row stores that name in `source`
(`jhsaa.School.ident` reads `source or name`), so the second run looks the rename up
under the same key and computes the same answer. Running it twice changes nothing;
`--dry-run` proves it before you commit.

⚠️ `source` is the ROSTER IDENTITY — it seeds the RNG that builds a program's twelve
players and every pid on their records. Stamping it is not bookkeeping: without it a
renamed school gets twelve strangers, its juniors never become seniors, and every
archived award points at nobody.
"""
import argparse
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")
_ARCH = os.path.join(_REPO, "data", "jhsaa", "archetypes.json")


def _import_jhsaa():
    """Load `import_jhsaa` as a module without running its CLI."""
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def apply(rows: list[dict], m) -> list[tuple[str, str]]:
    """Rewrite `rows` in place; return the (old, new) pairs that actually moved."""
    moved = []
    for r in rows:
        # The identity, not the current display name — see the module docstring.
        src = r.get("source") or r["name"]
        display = m._display_name(m.RENAMES.get(src, src))
        if display != r["name"]:
            moved.append((r["name"], display))
        r["name"] = display
        # Only written when it differs, matching what `import_jhsaa.build` emits:
        # a school nobody renamed is its own identity and an absent key reads as
        # `name` in `School.ident`.
        if src != display:
            r["source"] = src
        else:
            r.pop("source", None)
        r["private"] = bool(r.get("private")) or display in m.PRIVATE_SCHOOLS
        if display in m.MASCOTS:
            r["mascot"] = m.MASCOTS[display]
        if display in m.COLORS:
            r["colors"] = m.COLORS[display]
    rows.sort(key=lambda r: r["name"])      # renamed rows land at their NEW name
    return moved


def check_unique(rows: list[dict]) -> None:
    """‼️ A DISPLAY NAME IS THE ARCHIVE IDENTITY — it keys `run_season`'s teams dict,
    `world_jhsaa_dual.school`, the routes and the pid space. Two schools sharing one
    silently merge into a single archive slot while the standings keep both rows, so a
    record stops covering the duals it played and nothing errors. Refuse to write."""
    seen: dict[str, int] = {}
    for r in rows:
        seen[r["name"]] = seen.get(r["name"], 0) + 1
    dupes = {k: v for k, v in seen.items() if v > 1}
    if dupes:
        sys.exit(f"display-name collisions (fix RENAMES before writing): {dupes}")


def move_archetypes(moved: list[tuple[str, str]], dry: bool) -> list[str]:
    """`data/jhsaa/archetypes.json` keys on the DISPLAY name, so a rename has to carry
    its archetype across or the program silently loses its tag."""
    with open(_ARCH, encoding="utf-8") as fh:
        doc = json.load(fh)
    progs = doc["programs"]
    notes = []
    for old, new in moved:
        if old in progs:
            progs[new] = progs.pop(old)
            notes.append(f"{old} -> {new} ({progs[new]})")
    if notes and not dry:
        with open(_ARCH, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    return notes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    m = _import_jhsaa()
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"]

    moved = apply(rows, m)
    check_unique(rows)

    for old, new in moved:
        r = next(x for x in rows if x["name"] == new)
        print(f"  {old:28} -> {new:26} {r['group']:5} {r['enrollment']:5} "
              f"{r['city']} ({r['area']})")
    print(f"{len(moved)} renamed; "
          f"{sum(1 for r in rows if r.get('private'))} private of {len(rows)}")
    for n in move_archetypes(moved, args.dry_run):
        print(f"  archetype moved: {n}")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_DATA}")


if __name__ == "__main__":
    main()
