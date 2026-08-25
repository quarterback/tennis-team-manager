#!/usr/bin/env python3
"""The 2046 JHSAA expansion: two new classifications, Group 1 and Group 2.

    python3 scripts/jhsaa_expansion_2046.py [--dry-run]

Owner spec (verbatim): "great basin counties are just gonna be called Division 1
and Division 2 for JHSAA purposes with their own leagues, think of them more as
10A and 11A than thinking of them as anything weird. just keeping the same setup,
just adding two classifications." So the pair (renamed to `Group 1`/`Group 2` — see GROUP_RENAME) are two more
entries in `GROUPS`/`STATE_FIELD` (done in `app/jhsaa.py` and this module already,
see those files) -- NOT a parallel subsystem. This script is the one-time data
migration, same shape as `jhsaa_reclassify.py` / `jhsaa_redistrict.py`: it reads
the target roster the owner supplied (`docs/handoff/JHSAA_2046_expansion_roster.
csv`, one row per school with its FINAL `championship_group`) and reproduces it
against the committed `data/jhsaa/schools.json`.

Three kinds of row:
  - `source == "current"`: an existing school, matched by DISPLAY NAME (every one
    of the 864 matched cleanly against the committed file -- no `RENAMES` lookup
    was needed). ‼️ HISTORICAL CLASSIFICATIONS STAND (owner correction, 2026-08):
    the roster CSV's `championship_group` re-cut every ladder class to a flat ~86
    band, which moved ~300 current schools off their owner-curated classes -- the
    exact "cut-line reband" the 2033/2039 realignments exist to forbid (moves are
    NAMED and minimal). The owner's goals were geography + "no class over 100
    teams", NOT equal bands. So a current school's `championship_group` is honored
    ONLY when it names Group 1/Group 2 (the Great Basin boundary move, which does
    stand); every other current school keeps its committed classification, group
    AND enrollment exactly as they are -- including the two pre-existing
    competitive moves (Condotti Vanguard Academy / Romero-Finniski, class 3A,
    group 7A), which the CSV would have re-cut and split. Verified against the
    owner's LIVE-SAVE 2042 research export (programs.csv, both genders): all 864
    current schools match the committed baseline on classification and group,
    except Jamaica (group 2A in the export vs 1A on file) -- that is the runtime
    PLAY-UP override applied by `jhsaa.plays_up`, not a data difference, so
    nothing is baked here.
  - `source in ("activation", "new_territory")`: 93 brand-new programs (63 filling
    out the 1A-4A ladder to its target size, 30 standing on the ten new Great
    Basin counties). Built fresh with `source == name` (no prep-network origin to
    diverge from -- see CLAUDE.md's `School.source` rule) and both genders
    sponsored (these are all-new programs; there is no dice roll to reproduce).

Districts are FULLY REDRAWN for every one of the eleven groups, because every
group's membership changed (300 of the 864 existing schools change `group`, and
two groups are new outright) -- there is no smaller edit that would be correct.
Reuses `import_jhsaa.draw_districts` exactly as `jhsaa_redistrict.py` does, fed a
synthetic `city -> county` map built off the rows themselves (no prep-network
checkout needed, since every row already carries its own county/area).

‼️ TWO CLASSES END UP UNDER `sponsor_floor` (76) AND THAT IS REPORTED, NOT FIXED:
the Great Basin boundary takes 10-17 schools out of 8A and 9A, leaving 8A at 75
girls'/73 boys' and 9A at 73/65. Girls sponsorship is the membership itself, so
no backfill exists; the association degrades LOUDLY by design (`sc_head` + a
warning naming the class). Re-cutting the classes to paper over it is the flat-86
mistake again; if the owner wants 8A/9A back over the floor, that is a named
realignment for them to call. Boys backfill (the 2039 fallback) IS applied where
1-3 schools clear a class's boys floor -- see `backfill_boys_sponsorship`.
"""
import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")
_ROSTER_CSV = os.path.join(_REPO, "docs", "handoff", "JHSAA_2046_expansion_roster.csv")

# Owner rename (2026-08, NJSIAA language): the groups the handoff CSVs call
# "Division 1"/"Division 2" are implemented as "Group 1"/"Group 2" so they never
# collide with the recovery-round unit names ("Division N", `renumber_divisions`).
# The handoff CSVs are immutable, so the translation happens at the READ.
GROUP_RENAME = {"Division 1": "Group 1", "Division 2": "Group 2"}
NEW_GROUPS = ("Group 1", "Group 2")

# ‼️ BALANCE MOVES -- the repo's convention: a NAMED table, never a cut line
# (the 2033/2039 pattern; each entry moves classification AND group together).
# MEASURED EMPTY: after the restore the ladder counts are
#   9A 73 · 8A 75 · 7A 85 · 6A 88 · 5A 85 · 4A 95 · 3A 96 · 2A 87 · 1A 89
# (baseline minus Great Basin departures plus the new 4A-1A programs) -- no class
# exceeds the owner's 100 cap, so zero schools move. The table stays so the next
# balancing pass has its named home and its rule: minimum moves, enrollment-
# boundary schools, rivalries never split, OWNER_EDICTS untouched where a choice
# exists.
_BALANCE_MOVES: dict[str, str] = {}

# ‼️ ONE NAME COLLISION IN THE SOURCE DATA, renamed here rather than reproduced:
# the new 1A activation "Ransom City Union" is also a FORMER NAME on file for
# the existing "Ransom Pass" (`import_jhsaa.RENAMES["Ransom City Union"] =
# "Ransom Pass"`, carried into `data/jhsaa/former_names.json`). CLAUDE.md is
# explicit that `source or name` must be globally unique -- a new program using
# a retired alias would either misresolve through `jhsaa.current_name`/
# `_relabel` or silently share an identity with Ransom Pass's archived history.
# Renamed to a name that collides with nothing in either the display-name set
# or the former-names table. "Reverend City" is an OWNER EDICT (2026-08 — it is
# in `import_jhsaa.OWNER_EDICTS`); an earlier draft used "Ransom City Regional".
# The town stays Ransom, Tamarack County, per the handoff. The school has never
# been archived, so no former_names/alias entry is needed.
_NAME_OVERRIDE = {
    "Ransom City Union": "Reverend City",
}

# A small bank of ordinary American high-school mascots (no foreign fauna, per
# `import_jhsaa.MASCOT_FIXES`'s own bar: "would a US high school put this on a
# jersey"). Picked per school on a stable hash, same idiom as `fix_mascot`, so a
# re-run of this script is reproducible and does not need the mascot recorded
# anywhere else.
_MASCOT_POOL = [
    "Eagles", "Wolves", "Bears", "Hawks", "Broncos", "Cougars", "Panthers",
    "Wildcats", "Falcons", "Tigers", "Bulldogs", "Mustangs", "Rangers",
    "Pioneers", "Trailblazers", "Miners", "Ranchers", "Homesteaders",
    "Prospectors", "Sagebrush", "Antelope", "Bighorns", "Cutthroats",
    "Timberwolves", "Coyotes", "Badgers", "Grizzlies", "Rattlers",
    "Sidewinders", "Foothillers", "Highlanders", "Frontiersmen", "Trappers",
    "Rockhounds", "Silvertips", "Mavericks", "Stampede", "Thunderbirds",
    "Redtails", "Sagehens",
]

_COLOR_PAIRS = [
    ("#1c3f5f", "#c9a961"), ("#5c1a1a", "#e0dcd0"), ("#2d4a2d", "#f0e6c8"),
    ("#3a2a1c", "#d9a441"), ("#1a1a2e", "#c0392b"), ("#4a2c40", "#e8d5b7"),
    ("#0f3d3e", "#f2c14e"), ("#5e2129", "#dcd6c9"), ("#22333b", "#c6ac8f"),
    ("#3c1518", "#a9927d"), ("#2b2d42", "#edf2f4"), ("#432818", "#bb9457"),
]


def _import_jhsaa():
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _jhsaa():
    sys.path.insert(0, _REPO)
    os.environ.setdefault("TENNIS_DB_PATH", os.path.join(_REPO, ".expansion-tmp.db"))
    from app import jhsaa
    return jhsaa


def _stable(seed: str, pool: list):
    h = hashlib.blake2s(seed.encode("utf-8")).digest()
    return pool[int.from_bytes(h[:4], "big") % len(pool)]


def load_roster() -> list[dict]:
    with open(_ROSTER_CSV, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["enrollment"] = int(round(float(r["enrollment"])))
        r["private"] = r["private"] == "1"
    return rows


def apply_current(rows: dict, roster: list[dict]) -> int:
    """Move ONLY the Great Basin departures (`championship_group` naming Group 1
    or Group 2) -- every other current school keeps its historical classification,
    group and enrollment untouched (see the module docstring: the CSV's ladder
    re-cut was a flat reband the owner rejected). `_BALANCE_MOVES` (named,
    currently empty) is the only other way a current school changes class."""
    n = 0
    unmatched = []
    for r in roster:
        if r["source"] != "current":
            continue
        s = rows.get(r["name"])
        if s is None:
            unmatched.append(r["name"])
            continue
        grp = GROUP_RENAME.get(r["championship_group"], r["championship_group"])
        if grp in NEW_GROUPS and s["group"] != grp:
            s["classification"] = s["group"] = grp
            n += 1
        bal = _BALANCE_MOVES.get(r["name"])
        if bal:
            s["classification"] = s["group"] = bal
            n += 1
    if unmatched:
        sys.exit(f"{len(unmatched)} 'current' roster row(s) matched no school in "
                 f"{_DATA}: {unmatched[:10]}")
    return n


def new_school(r: dict) -> dict:
    grp = GROUP_RENAME.get(r["championship_group"], r["championship_group"])
    name = _NAME_OVERRIDE.get(r["name"], r["name"])
    mascot = _stable(f"jhsaa-2046-mascot|{name}", _MASCOT_POOL)
    colors = list(_stable(f"jhsaa-2046-colors|{name}", _COLOR_PAIRS))
    return {
        "name": name,
        "source": name,   # no prep-network origin -- roster identity is its own name
        "city": r["city"],
        "county": r["county"],
        "area": r["area"],
        "classification": grp,
        "group": grp,
        "enrollment": r["enrollment"],
        "private": r["private"],
        "mascot": mascot,
        "colors": colors,
        "girls": True,
        "boys": True,
        "girls_district": "",
        "boys_district": "",
    }


def add_new_schools(schools: list[dict], rows: dict, roster: list[dict]) -> int:
    alias_sources = {s["source"] for s in schools if "source" in s}
    n = 0
    for r in roster:
        if r["source"] == "current":
            continue
        s = new_school(r)
        name = s["name"]
        if name in rows or name in alias_sources:
            sys.exit(f"new-school row {name!r} collides with an existing "
                     f"school name or former-name alias -- add a _NAME_OVERRIDE")
        schools.append(s)
        rows[name] = s
        alias_sources.add(name)
        n += 1
    return n


def redraw_all_districts(schools: list[dict], m) -> None:
    """Full redraw for every group -- every group's membership changed (the Great
    Basin boundary takes 7-27 schools out of every ladder class, the new 4A-1A
    programs join four of them, and two groups are brand new), so nothing short of
    a full redraw is correct. Reuses `draw_districts` exactly as
    `jhsaa_redistrict.py` does."""
    cities = {s["city"]: {"county": s["county"]} for s in schools}
    by_group = collections.defaultdict(list)
    for s in schools:
        if s["girls"] or s["boys"]:
            by_group[s["group"]].append(s)
    league = {}
    for g in m.GROUPS:
        pool = by_group.get(g, [])
        league.update(m.draw_districts(pool, cities, g))
    for s in schools:
        name = s["name"]
        if name in league:
            s["girls_district"] = s["boys_district"] = league[name]


def backfill_boys_sponsorship(schools: list[dict], jh) -> list[str]:
    """Add boys sponsorship to just enough girls-sponsoring schools to clear
    `sponsor_floor` in every group -- mirrors the check the 2039 realignment ran
    ("No boys sponsorship was added anywhere -- checked before and after, every
    class already clears sponsor_floor"); this time the roster CSV's 5A group
    does not clear it on its own (74 boys sponsors against a 76 floor) and the
    fix that AAR describes as the fallback is applied here. Picked in stable
    NAME order among girls-sponsoring, boys-not-sponsoring schools in the short
    group, so a re-run is reproducible."""
    by_group = collections.defaultdict(list)
    for s in schools:
        by_group[s["group"]].append(s)
    added = []
    for g, members in by_group.items():
        floor = jh.sponsor_floor(g)
        boys = sum(1 for s in members if s["boys"])
        if boys >= floor:
            continue
        need = floor - boys
        # ‼️ CAPPED AT 3 PER CLASS, AND ONLY WHERE IT ACTUALLY CLEARS THE FLOOR
        # (owner-approved scale: "small backfill... 1-3 schools"). 9A's boys
        # shortfall is 11 and its girls membership is itself under the floor --
        # forcing eight sponsorships there fixes nothing and rewrites a fifth of
        # the class; `preflight` reports it instead.
        candidates = sorted((s for s in members if s["girls"] and not s["boys"]),
                            key=lambda s: s["name"])
        if need > 3 or len(candidates) < need:
            continue
        for s in candidates[:need]:
            s["boys"] = True
            added.append(f"{s['name']} ({g})")
    return added


def preflight(schools: list[dict], jh) -> None:
    """`sponsor_floor` must clear for every group in both genders -- the load-
    bearing invariant CLAUDE.md calls out explicitly for any group-adding change."""
    counts = collections.defaultdict(lambda: [0, 0])
    for s in schools:
        if s["girls"]:
            counts[s["group"]][0] += 1
        if s["boys"]:
            counts[s["group"]][1] += 1
    problems = []
    for g in jh.GROUPS:
        floor = jh.sponsor_floor(g)
        girls, boys = counts.get(g, (0, 0))
        if girls < floor or boys < floor:
            problems.append((g, girls, boys, floor))
    if problems:
        lines = "\n".join(f"  {g}: girls={gi} boys={bo} floor={fl}"
                          for g, gi, bo, fl in problems)
        # ‼️ 8A AND 9A ARE EXPECTED SHORT (module docstring): the Great Basin
        # boundary thinned them below the 76-body floor and there is no honest
        # backfill (girls sponsorship IS the membership). The association degrades
        # loudly by design (`sc_head`); this is REPORTED, not silently fixed --
        # anything else short means a mechanism broke and the script stops.
        unexpected = [p for p in problems if p[0] not in ("8A", "9A")]
        print(f"‼️ sponsor_floor NOT cleared for {len(problems)} group(s) — the "
              f"State qualifying ladder will degrade (sc_head) there:\n{lines}")
        if unexpected:
            sys.exit("unexpected sponsor_floor shortfall(s): "
                     + ", ".join(p[0] for p in unexpected))


def report(schools: list[dict], jh) -> None:
    counts = collections.defaultdict(lambda: [0, 0])
    leagues = collections.defaultdict(lambda: [set(), set()])
    for s in schools:
        if s["girls"]:
            counts[s["group"]][0] += 1
            leagues[s["group"]][0].add(s["girls_district"])
        if s["boys"]:
            counts[s["group"]][1] += 1
            leagues[s["group"]][1].add(s["boys_district"])
    print(f"{'group':12}{'girls':>7}{'boys':>7}{'g-leagues':>11}{'b-leagues':>11}"
          f"{'floor':>7}")
    for g in jh.GROUPS:
        gi, bo = counts.get(g, (0, 0))
        gl, bl = leagues.get(g, (set(), set()))
        floor = jh.sponsor_floor(g)
        flag = " ⚠️" if gi < floor or bo < floor else ""
        print(f"{g:12}{gi:7}{bo:7}{len(gl):11}{len(bl):11}{floor:7}{flag}")
    print(f"\n{len(schools)} total schools")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    m = _import_jhsaa()
    jh = _jhsaa()

    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    schools = doc["schools"]
    rows = {s["name"]: s for s in schools}

    roster = load_roster()

    moved = apply_current(rows, roster)
    added = add_new_schools(schools, rows, roster)
    print(f"{moved} existing schools moved (Great Basin boundary + "
          f"{len(_BALANCE_MOVES)} named balance moves), {added} new schools added"
          "; all other current schools keep their historical classification")

    backfilled = backfill_boys_sponsorship(schools, jh)
    if backfilled:
        print(f"⚠️ boys sponsorship added to clear sponsor_floor: {backfilled}")

    redraw_all_districts(schools, m)
    preflight(schools, jh)
    report(schools, jh)

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return

    doc["schools"] = schools
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nwrote {_DATA}")


if __name__ == "__main__":
    main()
