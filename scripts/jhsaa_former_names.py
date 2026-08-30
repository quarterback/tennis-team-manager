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

‼️ A LIVE NAME ALWAYS WINS, and the excluded set is REPORTED rather than merely
dropped. A former name that is now a DIFFERENT school's live name is a REISSUE: the
bare name was vacated by one program and handed to another (Breakwater was vacated by
what is now Tide Point and handed to what was Fort Meriwether Breakwater). Such a name
is genuinely AMBIGUOUS without a year — before the handoff it is the first school's,
after it the second's — so it is excluded here, and `jhsaa.current_name` / `known_names`
check live names first regardless, because an alias must never outrank a school that
actually exists.

The COST of that exclusion is real and belongs on screen rather than in a comment: the
vacating program cannot reach seasons archived under the name it gave up. So `--check`
NAMES every reissue it drops. Do not "fix" one by aliasing it — that files the live
school's own archived seasons under its neighbour, which is strictly worse than a gap.
(There were three; there are six. A count in prose rots — the report is generated.)
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


def _renames_at(rev: str, path: str = "scripts/import_jhsaa.py") -> dict[str, str]:
    src = subprocess.run(["git", "show", f"{rev}:{path}"],
                         capture_output=True, text=True, cwd=_REPO).stdout
    i = src.find("\nRENAMES = {")
    if i < 0:
        return {}
    body = src[i:src.index("\n}\n", i)]
    return {m.group(1): m.group(2) for m in
            re.finditer(r'^\s*"((?:[^"\\]|\\.)*)":\s*"((?:[^"\\]|\\.)*)",', body, re.M)}


def collect(m, live: set[str]) -> dict[str, str]:
    chain = collections.defaultdict(list)
    # ‼️ TWO FILES HOLD RENAME HISTORY, and the heritage batch is the reason
    # (2026-08). `jhsaa_heritage_valley_renames.py` renamed schools through its
    # OWN `RENAMES` table, never `import_jhsaa`'s — so the display names it
    # coined and later gave up ("Singleton HS", "Clara Brown HS", dropped in the
    # suffix sweep) exist in NO revision of `import_jhsaa.py`, and a season
    # archived under one would have been unreachable. Its table is the same
    # `RENAMES = {…}` literal, keyed on the same identities, and that batch
    # predates every later `import_jhsaa` entry for those keys — so its chains
    # are walked FIRST and the importer's appended after.
    for path in ("scripts/jhsaa_heritage_valley_renames.py",
                 "scripts/import_jhsaa.py"):
        revs = subprocess.run(
            ["git", "log", "--reverse", "--format=%H", "--", path],
            capture_output=True, text=True, cwd=_REPO).stdout.split()
        for rev in revs:
            for k, v in _renames_at(rev, path).items():
                if not chain[k] or chain[k][-1] != v:
                    chain[k].append(v)

    former, reissued = {}, {}
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
        for raw in [source, *targets]:
            # ‼️ THE RAW STRING IS AN ALIAS TOO (2026-08). A historical target is
            # the literal display name seasons were archived under, and running it
            # through `_display_name` first can normalise it INTO the current name
            # — "Singleton HS" collapses to "Singleton", reads as a no-op, and the
            # archived "Singleton HS" seasons stay orphaned. So both spellings are
            # emitted; an alias no archive ever used is a harmless map entry.
            for old in dict.fromkeys((raw, m._display_name(raw))):
                if old != now and old not in live:
                    former[old] = now
                elif old != now:
                    # A REISSUE, not a no-op: `old` is a name this school gave up
                    # that another program now carries. Recorded so the cost is
                    # visible.
                    reissued[old] = now
    return former, reissued


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

    former, reissued = collect(m, live)
    block = render(former)
    if reissued:
        print(f"{len(reissued)} REISSUED name(s) excluded — a program that gave up "
              "this name cannot reach seasons archived under it, and the name now "
              "belongs to somebody else:")
        for old, now in sorted(reissued.items()):
            print(f"  {old!r} was given up by {now!r}; it is now a live school")
        print()

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
