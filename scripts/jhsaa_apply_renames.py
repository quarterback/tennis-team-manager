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
import collections
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


def check_identities(rows: list[dict]) -> None:
    """‼️ `source or name` IS THE IDENTITY AND MUST BE UNIQUE. It keys RENAMES and it
    seeds the RNG that builds a program's players, so two rows sharing one string are
    two schools that a single rename catches together and that generate the same
    twelve people. This shipped once: a school kept `source: "Wheatley"` from a rename
    whose source prep-network had since renamed away, and a DIFFERENT school was
    actually named Wheatley — so `RENAMES["Wheatley"]` reached both. Caught only
    because the two then collided on the display name; had the targets differed it
    would have been silent."""
    import collections
    dup = {k: v for k, v in collections.Counter(
        (r.get("source") or r["name"]) for r in rows).items() if v > 1}
    if dup:
        sys.exit(f"rows sharing one identity (source or name): {dup}")


def check_rename_keys(rows: list[dict], m) -> None:
    """‼️ A RENAMES KEY MUST NAME EXACTLY ONE SCHOOL.

    The key is matched against `source or name`, and renaming a school that has never
    been renamed before means keying on its own name — that is the ORDINARY path, not
    a fault. The fault is AMBIGUITY: a key that matches one school's own name AND
    another school's `source`, so a single entry reaches two schools. `Wheatley` did
    exactly that. `check_identities` already forbids two rows sharing an identity,
    which makes that impossible; this is the second lock on the same door, stated in
    terms of the table rather than the data.

    Dead keys — matching neither any school here nor prep-network — are reported but
    do not stop the run: they cannot fire today, and they are only dangerous once a
    school is named that string, which the ambiguity check above would then catch.
    """
    ident = collections.Counter((r.get("source") or r["name"]) for r in rows)
    ambiguous = {k: v for k, v in m.RENAMES.items() if ident[k] > 1}
    if ambiguous:
        sys.exit("RENAMES keys that match more than one school — one entry would "
                 f"rename both: {ambiguous}")


def check_display_keyed_tables(rows: list[dict], m) -> None:
    """‼️ EVERY DISPLAY-KEYED TABLE MUST NAME A LIVE SCHOOL. MASCOTS, COLORS,
    PRIVATE_SCHOOLS and LOCALITIES all key on the display name, so a rename that
    misses one leaves an orphan and the school silently falls back to its source
    record's value — a mascot reverts, a locality disappears. It is invisible in the
    committed JSON, which is why it is asserted here rather than left to be noticed:
    a second rename of an already-renamed school (Cahaba Butte -> Gravity Falls ->
    Elias Boudinot) moved the RENAMES target and left LOCALITIES behind."""
    # ‼️ ONLY LOCALITIES CAN BE HARD-CHECKED. MASCOTS and COLORS are keyed over every
    # prep-network school, most of which sponsor no tennis, so a key naming no PROGRAM
    # is normal there and always will be. LOCALITIES is association-only, so an orphan
    # in it is always a rename that missed a table.
    # ‼️ A DUPLICATE KEY IN A DICT LITERAL IS SILENT — the last wins and one school
    # loses its locality with nothing to see. Renaming a school twice produced exactly
    # that. Counting the literal's entries against the loaded dict catches it.
    import re as _re
    with open(os.path.join(_HERE, "import_jhsaa.py"), encoding="utf-8") as fh:
        text = fh.read()
    lo = text.index("\nLOCALITIES = {")
    entries = _re.findall(r'^\s*"[^"]+":', text[lo:text.index("\n}\n", lo)], _re.M)
    if len(entries) != len(m.LOCALITIES):
        sys.exit(f"LOCALITIES has {len(entries)} entries but {len(m.LOCALITIES)} keys "
                 "— a duplicate key is silently dropping a school's locality")

    live = {r["name"] for r in rows}
    orphan = sorted(k for k in m.LOCALITIES if k not in live)
    if orphan:
        sys.exit(f"LOCALITIES keys naming no school (a rename left them behind): {orphan}")


def apply(rows: list[dict], m) -> list[tuple[str, str]]:
    """Rewrite `rows` in place; return the (old, new) pairs that actually moved."""
    moved = []
    for r in rows:
        # The identity, not the current display name — see the module docstring.
        src = r.get("source") or r["name"]
        # ‼️ ONLY A RECORDED RENAME MOVES A ROW (2026-08). Rows whose identity has
        # no RENAMES key used to have their display name RECOMPUTED from the source
        # anyway — harmless while every row came out of `import_jhsaa.build`, and
        # wrong the day the expansion scripts started committing rows whose names
        # are hand-assigned rather than `_display_name(source)`: the 2052/2046
        # affiliates ("Stanfield", source "Stanfield High") and the affiliate-names
        # batches would all have been silently renamed back toward their sources
        # (63 rows, measured, against the 2 actually keyed). A full import never
        # creates those rows, so recomputing them is outside this script's
        # jurisdiction; a name with no RENAMES entry stands as committed.
        if src not in m.RENAMES:
            continue
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
        # ‼️ TOWNS RENAME TOO, and the key is the SOURCE town — so this is idempotent
        # only because a town already renamed is no longer a key. Applied here rather
        # than left to a full import, which is not the path this file takes.
        r["city"] = m.CITY_RENAMES.get(r["city"], r["city"])
        r["private"] = bool(r.get("private")) or display in m.PRIVATE_SCHOOLS
        if display in m.MASCOTS:
            r["mascot"] = m.MASCOTS[display]
        if display in m.COLORS:
            r["colors"] = m.COLORS[display]
        # LOCALITY is keyed on the display name too, so it moves with a rename.
        # Absent means a CORE CITY school — a real distinction, so the key is
        # removed rather than blanked when a school no longer has one.
        if display in m.LOCALITIES:
            r["locality"] = m.LOCALITIES[display]
        else:
            r.pop("locality", None)
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

    check_identities(rows)          # before the rename, not after
    check_rename_keys(rows, m)
    moved = apply(rows, m)
    check_unique(rows)
    check_display_keyed_tables(rows, m)

    for old, new in moved:
        r = next(x for x in rows if x["name"] == new)
        print(f"  {old:28} -> {new:26} {r['group']:5} {r['enrollment']:5} "
              f"{r['city']} ({r['area']})")
    # ‼️ MASCOTS/COLORS/PRIVATE_SCHOOLS key on the DISPLAY name and live in
    # import_jhsaa.py, which this script cannot edit — so a rename leaves them behind
    # and the override is silently dropped on the next FULL import. build() refuses to
    # run in that state, but nobody runs a full import daily, so say it here where the
    # rename actually happens. Left behind three times before this line existed.
    for tname in ("MASCOTS", "COLORS", "PRIVATE_SCHOOLS"):
        stale = sorted(k for k in getattr(m, tname, ()) if k in m.RENAMES)
        if stale:
            print(f"  !! {tname} still keyed on {len(stale)} renamed name(s) — move "
                  f"them to the new display name in import_jhsaa.py: {stale[:6]}")
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
