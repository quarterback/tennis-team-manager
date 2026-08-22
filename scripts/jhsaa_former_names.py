#!/usr/bin/env python3
"""Rebuild `import_jhsaa.FORMER_NAMES` from the git history of `RENAMES`.

    python3 scripts/jhsaa_former_names.py [--check]

‼️ WHY THIS EXISTS. The JHSAA archive keys on a school's DISPLAY NAME at the moment
the season was written (`world_jhsaa`, `world_jhsaa_dual.school`). Rename the school
and those rows keep the old string — so the program page, keyed on the current name,
finds nothing, and the old name has no live school, so its page 404s. A 2031 state
champion vanished from its own program page that way. **The data was never lost; the
link was.**

So the association needs to know what each school used to be called. That list is not
something to type: a rename's target gets REWRITTEN IN PLACE when a school is renamed
twice (which is the rule — never chain A -> B -> C), so the intermediate names exist
nowhere in the current table. They do exist in git, which is what this reads: every
revision of `import_jhsaa.py`, the value `RENAMES[source]` held at each, and therefore
every display name the school has ever carried.

‼️ A LIVE NAME ALWAYS WINS. Three former names are now a DIFFERENT school's live name
— "Ashbury" was renamed to "Ashbury Central" and is now what Ashbury Heights is
called. Those are excluded here and `jhsaa.resolve_school` checks live names first
regardless, because an alias must never outrank a school that actually exists.
"""
import argparse
import collections
import importlib.util
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")
_TARGET = os.path.join(_HERE, "import_jhsaa.py")
# ‼️ THE APP CANNOT IMPORT A SCRIPT. `app/jhsaa.py` reads data files, not
# `scripts/`, so the table is emitted BOTH places: the Python block stays the
# readable record beside RENAMES, and this JSON is what the association loads.
_JSON = os.path.join(_REPO, "data", "jhsaa", "former_names.json")


def _import_jhsaa():
    spec = importlib.util.spec_from_file_location("import_jhsaa", _TARGET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _renames_at(rev: str) -> dict[str, str]:
    src = subprocess.run(["git", "show", f"{rev}:scripts/import_jhsaa.py"],
                         capture_output=True, text=True, cwd=_REPO).stdout
    i = src.find("\nRENAMES = {")
    if i < 0:
        return {}
    body = src[i:src.index("\n}\n", i)]
    return {m.group(1): m.group(2) for m in
            re.finditer(r'^\s*"((?:[^"\\]|\\.)*)":\s*"((?:[^"\\]|\\.)*)",', body, re.M)}


def collect(m, live: set[str]) -> dict[str, str]:
    revs = subprocess.run(
        ["git", "log", "--reverse", "--format=%H", "--", "scripts/import_jhsaa.py"],
        capture_output=True, text=True, cwd=_REPO).stdout.split()
    chain = collections.defaultdict(list)
    for rev in revs:
        for k, v in _renames_at(rev).items():
            if not chain[k] or chain[k][-1] != v:
                chain[k].append(v)

    former = {}
    for source, targets in chain.items():
        now = m.RENAMES.get(source)
        if now is None:                       # entry retired; nothing live to point at
            continue
        now = m._display_name(now)
        # The SOURCE name is itself a former display name whenever the school was
        # emitted under it before the rename landed. ‼️ ALL targets, not
        # `targets[:-1]`: run pre-commit (as documented), git history ends at the
        # previous revision, so the LAST target in the chain is the name being
        # renamed AWAY right now — dropping it omits exactly the alias the commit
        # needs. `old != now` already excludes the current name when it is present.
        for old in [source, *targets]:
            old = m._display_name(old)
            if old != now and old not in live:
                former[old] = now
    return former


def render(former: dict[str, str]) -> str:
    out = ['# ‼️ WHAT A SCHOOL USED TO BE CALLED — generated, never hand-edited.',
           '#',
           '# The archive keys on the DISPLAY NAME at the time a season was written, so a',
           '# rename orphans every row a school has already earned: its program page finds',
           '# nothing and the old name 404s. A 2031 state champion disappeared from its own',
           '# page that way. The data was never lost — only the link.',
           '#',
           '# Rebuild with `scripts/jhsaa_former_names.py`, which walks the git history of',
           '# RENAMES. It has to come from git: renaming a school twice REWRITES the target',
           '# in place (the rule — never chain A -> B -> C), so the intermediate name exists',
           '# nowhere in the current table.',
           '#',
           '# ‼️ A LIVE NAME ALWAYS WINS. A former name that is now some OTHER school\'s live',
           '# name is excluded here, and `jhsaa.resolve_school` checks live names first in any',
           '# case: an alias must never outrank a school that exists.',
           'FORMER_NAMES = {']
    for old in sorted(former):
        out.append(f'    "{old}":{" " * max(1, 44 - len(old))}"{former[old]}",')
    out.append('}')
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if the committed table is out of date")
    args = ap.parse_args()

    m = _import_jhsaa()
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"] if isinstance(doc, dict) else doc
    live = {r["name"] for r in rows}

    former = collect(m, live)
    block = render(former)

    with open(_TARGET, encoding="utf-8") as fh:
        text = fh.read()
    start = text.find("\n# ‼️ WHAT A SCHOOL USED TO BE CALLED")
    if start >= 0:
        end = text.index("\n}\n", start) + len("\n}\n")
        old_block = text[start + 1:end]
    else:
        old_block = ""

    if args.check:
        with open(_JSON, encoding="utf-8") as fh:
            on_disk = json.load(fh)["former_names"]
        if on_disk != former:
            sys.exit(f"data/jhsaa/former_names.json is out of date "
                     f"({len(former)} entries expected, {len(on_disk)} on disk). "
                     "Run scripts/jhsaa_former_names.py")
        if old_block.strip() != block.strip():
            sys.exit(f"FORMER_NAMES is out of date ({len(former)} entries expected). "
                     "Run scripts/jhsaa_former_names.py")
        print(f"FORMER_NAMES is current ({len(former)} entries)")
        return

    if old_block:
        text = text[:start + 1] + block + text[end:]
    else:
        anchor = "\nRENAMES = {"
        text = text.replace(anchor, "\n" + block + anchor, 1)
    with open(_TARGET, "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(_JSON, "w", encoding="utf-8") as fh:
        json.dump({"former_names": dict(sorted(former.items()))}, fh,
                  indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote FORMER_NAMES with {len(former)} entries (+ {_JSON})")


if __name__ == "__main__":
    main()
