"""Owner rule 2026-09: person-named JHSAA schools abbreviate to the SURNAME.

Real named high schools rarely carry the person's full name day to day —
"Rita Moreno" is just Moreno, Malcolm X HS is just Shabazz — so the
commemorative full names are dropped to the last name. First/middle INITIALS
are used ONLY where the bare surname would duplicate something:

- another renamed school's surname (the two Harrisons, the two Johnsons,
  Jesse Jackson beside Ketanji Brown Jackson),
- a live school ("Baker" already exists, so Ella Baker is "E. Baker"),
- a former-name alias that serves ANOTHER school's archive ("Coolidge" is
  Seagrove's old name, "Eisenhower" is Flume River's, "Adams" is Sally
  Ride's) — reissuing those would put the alias table in contradiction.

"George Washington" -> "Washington" is a REVERSAL (that alias points at this
same school), so the alias entry is deleted rather than repointed — the
jhsaa_owner_renames_2065.py idiom.

Deliberately untouched: title-named schools (Bishop/Archbishop/Cardinal/
Saint/Pope, De La Salle, Sinkford), day schools ("Evans Larsen Day"), and
generated-person names that read as places or ordinary locals — this pass is
the famous-commemorative layer only.

Every rename stamps `source` where the record had none, so `source or name`
— the string that seeds the pids — never moves. Replay AFTER every earlier
JHSAA transform script; a full re-import supersedes it like the rest.

Run: python3 scripts/jhsaa_abbreviate_person_names.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RENAMES: dict[str, str] = {
    # surname only — the default
    "Alben Barkley": "Barkley",
    "Bayard Rustin": "Rustin",
    "Ben Franklin": "Franklin",
    "Benjamin Banneker": "Banneker",
    "Chester A. Arthur": "Arthur",
    "Clara Brown": "Brown",
    "Coretta Scott King": "King",
    "Dolores Huerta": "Huerta",
    "Earl Warren": "Warren",
    "Franklin Pierce": "Pierce",
    "George H. W. Bush": "Bush",
    "George Washington": "Washington",         # its own former name, back
    "George Washington Carver": "Carver",
    "Gerald Ford": "Ford",
    "Grace Lee Boggs": "Boggs",
    "Gwendolyn Brooks": "Brooks",
    "Harry Truman": "Truman",
    "Herbert Hoover": "Hoover",
    "Ida B. Wells": "Wells",
    "James Baldwin": "Baldwin",
    "Jean Baptiste": "Baptiste",
    "Leonard Coleman": "Coleman",
    "Ralph Bellamy": "Bellamy",
    "James K. Polk": "Polk",
    "James Monroe": "Monroe",
    "Jimmy Carter": "Carter",
    "John F. Kennedy": "Kennedy",
    "John Lewis": "Lewis",
    "Mae Jemison": "Jemison",
    "Malcolm X Shabazz": "Shabazz",            # the owner's own example
    "Martin Van Buren": "Van Buren",
    "Octavia Butler": "Butler",
    "Oscar Michaeux": "Michaeux",
    "Paul Robeson": "Robeson",
    "Rita Moreno": "Moreno",                   # the owner's own example
    "Ronald Reagan": "Reagan",
    "Rutherford Hayes": "Hayes",
    "Thurgood Marshall": "Marshall",
    "Ruth Bader Ginsburg": "Ginsburg",
    "Sally Ride": "Ride",
    "Sandra Day O'Connor": "O'Connor",
    "Shirley Chisholm": "Chisholm",
    "Sonia Sotomayor": "Sotomayor",
    "Ulysses Grant": "Grant",
    "Walter Mondale": "Mondale",
    "William Howard Taft": "Taft",
    "Yuri Kochiyama": "Kochiyama",
    "Zachary Taylor": "Taylor",
    # fake saints (owner rule 2026-09): the TOWNS St. Elian and St. Varian
    # keep their names, but the schools carrying them are renamed. Both new
    # names are the owner's picks: the St. Varian school is the Zora Neale
    # Hurston school (displayed "Hurston", the surname rule above).
    "Elian": "Kimberly",
    "Varian": "Hurston",
    # initials — only because the bare surname is a duplicate
    "Benjamin Harrison": "B. Harrison",        # two Harrisons
    "William Henry Harrison": "W.H. Harrison",
    "Jesse Jackson": "J. Jackson",             # two Jacksons
    "Ketanji Brown Jackson": "K.B. Jackson",
    "Katherine Johnson": "K. Johnson",         # two Johnsons
    "Lyndon B. Johnson": "L.B. Johnson",
    "Ella Baker": "E. Baker",                  # "Baker" is a live school
    "Calvin Coolidge": "C. Coolidge",          # "Coolidge" aliases Seagrove
    "Dwight Eisenhower": "D. Eisenhower",      # "Eisenhower" aliases Flume River
    "John Quincy Adams": "J.Q. Adams",         # "Adams" aliases Sally Ride
    "James Madison": "J. Madison",             # "Madison" aliases Governor Woods
    "Booker T Washington": "B.T. Washington",  # "Washington" goes to George W.
}

# Alias keys that ARE a new name and point at the school taking it back —
# deleted, never repointed (a former name that is also the live name is a
# contradiction the alias table should not hold).
REVERSAL_KEYS = {"Washington": "George Washington"}

# Owner rule 2026-09: no fake Catholic names. "Saint Marc" is not a real
# saint; the school already renamed to Cap Rouge, but the string survived as
# its LOCALITY. Nothing keys on a locality, so it is a plain display fix.
LOCALITY_FIXES = {"Saint Marc": "Saint Michel"}

SCHOOLS = ROOT / "data" / "jhsaa" / "schools.json"
FORMER = ROOT / "data" / "jhsaa" / "former_names.json"
IMPORTER = ROOT / "scripts" / "import_jhsaa.py"


def main() -> int:
    dry = "--dry-run" in sys.argv

    doc = json.loads(SCHOOLS.read_text())
    rows = doc["schools"]
    names = {r["name"] for r in rows}
    former = json.loads(FORMER.read_text())
    table = former["former_names"]

    missing = [o for o in RENAMES if o not in names]
    taken = [n for n in RENAMES.values() if n in names]
    # a new name that is an alias key for ANOTHER school is a contradiction
    clashes = [n for n in RENAMES.values()
               if n in table and REVERSAL_KEYS.get(n) not in RENAMES]
    if missing or taken or clashes:
        print("no such school:", missing, "| new name already taken:", taken,
              "| new name aliases another school:", clashes)
        return 1

    direct_renames: dict[str, str] = {}   # roster identity -> new display
    for row in rows:
        old = row["name"]
        if old not in RENAMES:
            continue
        row.setdefault("source", old)   # pin the roster identity first
        row["name"] = RENAMES[old]
        direct_renames[row["source"]] = row["name"]
        print(f"  {old:<26} -> {row['name']:<16} {row['group']:<8} {row['city']}")
    for row in rows:
        if row.get("locality") in LOCALITY_FIXES:
            row["locality"] = LOCALITY_FIXES[row["locality"]]

    final = [r["name"] for r in rows]
    ident = [r.get("source") or r["name"] for r in rows]
    if len(set(final)) != len(final) or len(set(ident)) != len(ident):
        print("names or roster identities are no longer unique")
        return 1

    # the alias table: reversals deleted, values repointed, old names added
    for key in REVERSAL_KEYS:
        table.pop(key, None)
    for old, fresh in RENAMES.items():
        for key, val in list(table.items()):
            if val == old:
                table[key] = fresh
        table[old] = fresh
    if any(k == v for k, v in table.items()):
        print("alias table maps a name to itself")
        return 1
    former["former_names"] = dict(sorted(table.items()))

    # ── the importer, TABLE-AWARE ─────────────────────────────────────────
    # A quoted old name means different things in different tables:
    # ALWAYS_EXTRA / ALWAYS_GIRLS_ONLY / EXTRA_SPONSORS / NEVER_SPONSOR /
    # SUBSTITUTIONS key on PREP-NETWORK source names and must keep them (the
    # sponsor draw and build()'s by_name run BEFORE renaming); RENAMES and
    # FORMER_NAMES have source-side KEYS and display-side VALUES; everything
    # else (MASCOTS, LOCALITIES, OWNER_EDICTS, RECLASSIFY_TO_2A…) is
    # display-keyed and takes the new name. Unquoted comment mentions,
    # "George Washington" the university and the US state are untouched.
    text = IMPORTER.read_text()
    for key, val in REVERSAL_KEYS.items():
        line = next((ln for ln in text.splitlines()
                     if ln.strip().startswith(f'"{key}":') and f'"{val}"' in ln), None)
        if line:
            text = text.replace(line + "\n", "")

    SOURCE_TABLES = ("ALWAYS_GIRLS_ONLY", "ALWAYS_EXTRA", "NEVER_SPONSOR",
                     "EXTRA_SPONSORS", "SUBSTITUTIONS")
    VALUE_TABLES = ("FORMER_NAMES", "RENAMES")

    def _sub(chunk: str) -> str:
        for old, fresh in RENAMES.items():
            chunk = chunk.replace(f'"{old}"', f'"{fresh}"')
        return chunk

    lines, table = text.splitlines(keepends=True), None
    for i, ln in enumerate(lines):
        head = ln.split(" = ")[0]
        if not ln[:1].isspace() and head in SOURCE_TABLES + VALUE_TABLES:
            table = head
        elif table and ln.rstrip() in ("}", "]", "})"):
            table = None
            continue
        if table in SOURCE_TABLES:
            continue                      # prep-network spelling stays
        if table in VALUE_TABLES:
            cut = ln.find('":')           # replace the VALUE, never the key
            if cut != -1:
                lines[i] = ln[:cut + 2] + _sub(ln[cut + 2:])
            continue
        lines[i] = _sub(ln)
    text = "".join(lines)

    # Direct-source renames: a school whose source key produced no RENAMES
    # entry before still needs one, or a re-import emits the full name while
    # every display-keyed table now says the abbreviation. Keys are each a
    # live school's roster identity, so check_rename_keys stays satisfied.
    start = text.index("RENAMES = {")
    span_end = text.index("\n}", start)
    span = text[start:span_end]
    inserts = [f'    "{key}": "{fresh}",'
               for key, fresh in sorted(direct_renames.items())
               if f'"{key}":' not in span]
    if inserts:
        head_end = text.index("\n", start) + 1
        block = ("    # ── the 2026-09 surname abbreviations "
                 "(scripts/jhsaa_abbreviate_person_names.py) ──\n"
                 + "\n".join(inserts) + "\n")
        text = text[:head_end] + block + text[head_end:]

    if not dry:
        SCHOOLS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        FORMER.write_text(json.dumps(former, indent=2, ensure_ascii=False) + "\n")
        IMPORTER.write_text(text)
    print("dry run — nothing written" if dry else "written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
