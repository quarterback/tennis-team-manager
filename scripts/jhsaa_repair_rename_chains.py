"""Repair the RENAMES chains for the 2065 rename passes, and rename Martin Luther.

‼️ A RENAME IS NOT DONE WHEN THE DISPLAY NAME MOVES. `former_names.json` is
GENERATED from the git history of `import_jhsaa.RENAMES` — so a school whose
display name WAS its own roster identity (no prior rename, therefore no RENAMES
row) leaves the generator nothing to walk, and the alias written by hand is wiped
on its next run. Thirty-one of the fifty 2065 renames were in exactly that state:
every season archived under those names was unreachable, Seminary's state titles
among them, with nothing raising anywhere.

The fix is the table, not the JSON: `RENAMES[roster identity] = current display
name` for every renamed program, which is the contract the generator reads. One
existing row was also stale — "Port Veles International Academy" still pointed at
"Seminary High School", a name that stopped being live when Seminary became Veles
Park.

Martin Luther -> Coretta Scott King rides along (owner, 2026-09), and goes public
like the rest of that pass; it was held back only by the state-title rule, which
the owner has now lifted for it.

Run: python3 scripts/jhsaa_repair_rename_chains.py [--dry-run]
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHOOLS = ROOT / "data" / "jhsaa" / "schools.json"
IMPORTER = ROOT / "scripts" / "import_jhsaa.py"

# owner, 2026-09 — the one addition in this pass
LATE = {"Martin Luther": "Coretta Scott King"}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    dry = "--dry-run" in sys.argv
    doc = json.loads(SCHOOLS.read_text())
    rows = doc["schools"]
    by_name = {r["name"]: r for r in rows}

    for old, new in LATE.items():
        if old in by_name:
            if new in by_name:
                print("target already taken:", new)
                return 1
            r = by_name.pop(old)
            r.setdefault("source", old)   # pin the roster identity before the move
            r["name"] = new
            r["private"] = False
            by_name[new] = r
            print(f"  {old} -> {new}  ({r['group']} {r['city']}, now public)")

    passes = [
        _load(ROOT / "scripts" / "jhsaa_secularise_2065.py", "sec").RENAMES,
        _load(ROOT / "scripts" / "jhsaa_owner_renames_2065.py", "own").RENAMES,
        LATE,
    ]
    renamed = {}
    for table in passes:
        renamed.update(table)

    text = IMPORTER.read_text()
    imp = _load(IMPORTER, "imp")
    added, fixed = [], []
    for old, new in renamed.items():
        row = by_name.get(new)
        if row is None:
            continue                       # a later pass renamed it again
        ident = row.get("source") or row["name"]
        if ident == new:
            continue                       # went back to its own name; no row wanted
        current = imp.RENAMES.get(ident)
        if current is not None and imp._display_name(current) == new:
            continue                       # already correct
        if current is None:
            added.append((ident, new))
        else:
            fixed.append((ident, current, new))

    # RENAMES is one big literal; insert and repair by exact text so the file's
    # hand-authored grouping and comments survive.
    for ident, current, new in fixed:
        pat = re.compile(rf'("{re.escape(ident)}":\s*)"{re.escape(current)}"')
        text, n = pat.subn(lambda m: f'{m.group(1)}"{new}"', text, count=1)
        if not n:
            print("could not repair:", ident)
            return 1
    if added:
        block = "\n".join(f'    "{i}": "{n}",' for i, n in sorted(added))
        anchor = ("RENAMES = {\n")
        head = (
            "    # ‼️ THE 2065 SECULARISATION CHAINS (2026-09). These programs were\n"
            "    # renamed while their display name WAS their roster identity, so they had\n"
            "    # no row here — and `jhsaa_former_names.py` generates the alias table from\n"
            "    # THIS table's git history, so without a row the old name resolves to\n"
            "    # nothing and every season archived under it is unreachable. A rename is\n"
            "    # not done when the display name moves; it is done when this row exists.\n"
        )
        text = text.replace(anchor, anchor + head + block + "\n", 1)

    if not dry:
        IMPORTER.write_text(text)
        SCHOOLS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"  RENAMES rows added {len(added)}, repaired {len(fixed)}")
    print("dry run — nothing written" if dry else "written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
