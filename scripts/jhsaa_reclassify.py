#!/usr/bin/env python3
"""Apply `import_jhsaa.PROMOTE_ABOVE` to the committed `data/jhsaa/schools.json`.

    python3 scripts/jhsaa_reclassify.py [--dry-run]

‼️ WHY IT IS A TRANSFORM AND NOT A RE-IMPORT — see
`scripts/jhsaa_apply_renames.py`'s docstring: the nine-class records the committed
data was built from were never committed to prep-network, so the importer cannot
reproduce this file. The cut lines still live in `import_jhsaa`, which stays the one
authority; this script only applies them.

‼️ WHAT IT IS FOR. `jhsaa.sponsor_floor` says a 40-field classification needs 76
sponsors per gender to field a full Semi-Conference, and 9A BOYS had 72 — four short,
the only class-gender under the line, and short for no reason but where the enrollment
cut lines happened to fall. The owner's call was to fix the association rather than
the format: move schools up a class and let the gap cascade back down (8A->9A,
7A->8A, 6A->7A, 5A backfills 6A). The engine's degradation path stays for drift; it
should simply never fire again.

‼️ LEAGUES MOVE WITH THE SCHOOL, AND ONLY FOR THE SCHOOL THAT MOVED. Redrawing every
affected class through `import_jhsaa.draw_districts` would be the obvious thing and it
is wrong here: league identity is a CURATED dataset (`LEAGUE_NAMES`, owner rule
2027-08 — names persist through realignment, and the drift is the realism), so a
redraw would rename the leagues of ~500 schools that did not move in order to
reclassify ~48 that did. A promoted school instead JOINS a league in its new class,
which is what actually happens when a school reclassifies. It picks the nearest one
by area, then county, and breaks ties on the SMALLEST current membership so a league
cannot be pushed past `MAX_DISTRICT` while an emptier neighbour sits beside it.

‼️ BOYS AND GIRLS ALWAYS SHARE A LEAGUE (owner rule 2027-08). A league belongs to the
SCHOOL, so a promoted school gets ONE new league for both fields. Placement is chosen
over the girls-inclusive pool because girls sponsorship is the superset.

Idempotent: a second run finds nothing at or above its cut line (the promoted schools
now sit in the class above, whose line is higher) and changes nothing. `--dry-run`
proves it before you commit.
"""
import argparse
import collections
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")


def _import_jhsaa():
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def promote(rows: list[dict], m) -> list[tuple[dict, str, str]]:
    """Move each class's largest schools up one. Top-down, so a school moves at most
    one class in a pass — promote 7A into 8A before 8A into 9A and a big 7A school
    lands in 9A in a single hop."""
    moved = []
    for src in ("8A", "7A", "6A", "5A"):
        dst = m._PROMOTE_TO[src]
        # ‼️ DECIDE THE WHOLE CLASS BEFORE MOVING ANY OF IT. A rivalry outranks the cut
        # line (owner rule 2027-08): a pair moves only if EVERY member clears it,
        # otherwise none of them do, because promoting one across a class boundary is
        # unrepairable — a district is (classification, name), so there is no league
        # both could then join. That check has to run against the state BEFORE this
        # pass mutates anything. Testing it row by row splits the pair the OTHER way
        # when both members qualify: the first is promoted, and the second then reads
        # its already-moved rival as no longer being in `src` and stays behind.
        #
        # The original report was the first half of this: Condotti Vanguard Academy
        # (1,666) cleared a 1,638 line, Romero-Finniski (1,526) did not, and two
        # Ashbury schools that had always shared Metro League ended a class apart with
        # every individual number correct.
        eligible = {r["name"] for r in rows
                    if r["classification"] == src
                    and r["enrollment"] >= m.PROMOTE_ABOVE[src]}
        here = {r["name"] for r in rows if r["classification"] == src}
        for pair in m.RIVALRIES:
            members = [n for n in pair if n in here or n in eligible]
            if members and not all(n in eligible for n in members):
                eligible -= set(members)
        for r in rows:
            if r["name"] not in eligible or r["classification"] != src:
                continue
            moved.append((r, src, dst))
            r["classification"] = dst
            r["group"] = m.champ_group(dst)
    return moved


def demote(rows: list[dict], m) -> list[tuple[dict, str, str]]:
    """Apply `import_jhsaa.RECLASSIFY_TO_2A` — the 2033 realignment, the reverse of
    the cut-line cascade above.

    ‼️ IT MOVES `classification` AS WELL AS `group`. That is what separates a
    RECLASSIFICATION from a COMPETITIVE_MOVE, and it is not bookkeeping: `_TALENT`
    generates from `classification`, so a school moved on `group` alone keeps its old
    class's players. Right for a program petitioning down on results; wrong here,
    where the association is saying these schools are 2A-SIZED — and they are, every
    one already inside 2A's committed enrollment band.

    ‼️ AND THE ENROLLMENT IS NOT TOUCHED. The owner's standing rule is that the
    number follows the decision (enrollments are fictional and nothing about them is
    permanent), so scaling is available — but it is only needed when the number would
    otherwise contradict the move, and here it does not.
    """
    down = set(m.RECLASSIFY_TO_2A)
    by_name = {r["name"] for r in rows}
    unknown = sorted(down - by_name)
    if unknown:
        sys.exit(f"RECLASSIFY_TO_2A names {len(unknown)} school(s) that do not "
                 f"exist: {unknown}")
    moved = []
    for r in rows:
        if r["name"] in down and r["group"] != "2A":
            moved.append((r, r["group"], "2A"))
            r["classification"] = r["group"] = "2A"
    return moved


def reclassify_named(rows: list[dict], m, table=None, table_name="RECLASSIFY_2039"):
    """Apply a named cross-class realignment table — same shape as `demote()`'s
    2033 pass and for the same reason: the owner named the schools and their
    target classes directly.

    Defaults to `import_jhsaa.RECLASSIFY_2039` (the 30-school round). Pass
    `table`/`table_name` to apply a different one, e.g. `m.RECLASSIFY_2039B`
    — the 17-school correction batch the owner named after reviewing who was
    left in 9A/8A. Same mechanism, kept as a SEPARATE named table rather than
    merged, exactly like `RECLASSIFY_2039` itself relative to `RECLASSIFY_TO_2A`.

    ‼️ THE ENROLLMENT ALWAYS NEEDS SCALING. None of these schools already sit in
    their target class's committed enrollment band — moves span several classes
    — so every one gets a fresh `_reclass_enrollment` draw. `demote()`'s "only
    needed when the number would otherwise contradict the move" is the general
    rule; these tables are the case where it always fires.
    """
    down = dict(table if table is not None else m.RECLASSIFY_2039)
    by_name = {r["name"] for r in rows}
    unknown = sorted(set(down) - by_name)
    if unknown:
        sys.exit(f"{table_name} names {len(unknown)} school(s) that do not "
                 f"exist: {unknown}")
    moved = []
    for r in rows:
        dst = down.get(r["name"])
        if dst is not None and r["group"] != dst:
            moved.append((r, r["group"], dst))
            r["classification"] = r["group"] = dst
            r["enrollment"] = m._reclass_enrollment(r["name"], dst)
            # A school this table names IS its new class now, not playing up TO
            # it — a stale seeded `play_up` flag from an old, smaller class
            # would be a lying field (harmless, since `can_play_up` gates on
            # classification and blocks it the moment a school reclassifies out
            # of eligibility, but still worth not writing).
            r.pop("play_up", None)
    return moved


def check_rivals(rows: list[dict], m) -> None:
    """Rivals share a classification AND a league, in both genders. ASSERTED rather
    than repaired: if a pair has drifted apart, the mechanism that moved them is what
    needs fixing, and quietly pulling them back together would hide it."""
    by_name = {r["name"]: r for r in rows}
    for pair in m.RIVALRIES:
        live = [by_name[n] for n in pair if n in by_name]
        if len(live) < 2:
            continue
        groups = {r["group"] for r in live}
        assert len(groups) == 1, (pair, "split across classifications", groups)
        for key in ("girls_district", "boys_district"):
            leagues = {r[key] for r in live if r[key]}
            assert len(leagues) <= 1, (pair, key, leagues)


def rehome(rows: list[dict], moved: list[tuple[dict, str, str]], m) -> None:
    """Put every promoted school in a league of its new class — nearest first, and
    the smallest of the near ones, so nothing is pushed past MAX_DISTRICT while an
    emptier neighbour is available."""
    # ‼️ A PROMOTED SCHOOL IS NOT A LEAGUE OPTION UNTIL IT HAS BEEN PLACED. `promote`
    # moves `classification`/`group` and leaves the district alone, so between the
    # two passes a school sits in its NEW class still carrying its OLD class's league
    # name. Scanning the class naively therefore offers 5A league names to a school
    # being placed in 6A — and it took them: 9A came out with ten leagues where it has
    # seven, three of them 8A names that had walked up with their schools. Only the
    # STABLE membership of the target class is a valid destination.
    # ‼️ A CLASS THAT RUNS OUT OF SEATS IS REALIGNED, NOT OVERSTUFFED. Joining
    # existing leagues only works while the class HAS room: 9A held 80 girls' programs
    # in seven leagues — already 11.4 each against a MAX_DISTRICT of 12 — so twelve
    # arrivals cannot fit however cleverly they are placed, and the first attempt
    # produced leagues of 15 and 16 (a 30-dual double round robin against everyone
    # else's 22). When a class needs more leagues than it has, it gets a full redraw
    # through `import_jhsaa.draw_districts`, which is the authority for cutting
    # balanced blocks and naming them from the bank. That renames that class's
    # leagues — accepted, and only for a class that genuinely realigned by ~15%.
    # ‼️ A CLASS THAT SHRANK NEEDS THE REDRAW JUST AS MUCH. The condition used to be
    # "does it still fit under the cap", which only ever fires on growth — so the
    # class a realignment takes schools OUT of kept whatever leagues it had, at
    # whatever sizes were left. The 2033 realignment took 32 schools out of 3A and
    # left eleven leagues averaging 8.5, one of them at 6. `district_count` is the
    # authority on how many leagues a pool of n wants; a class is redrawn whenever
    # it no longer has that many, in either direction.
    cities = {r["city"]: {"county": r["county"]} for r in rows}
    # ‼️ AND `MAX_DISTRICT` IS A HARD CAP WHEREVER IT IS BROKEN, not only in the
    # classes this pass moved schools between. 1A's Rim Country League has carried
    # 13 members since the 1A/2A split and no reclassification was ever going to
    # touch it, because nothing about 1A had changed — a league over the cap plays a
    # 24-dual double round robin against its neighbours' 18, which is the schedule
    # the cap exists to prevent.
    over = {r["group"] for r in rows if r["girls"]
            and collections.Counter(x["girls_district"] for x in rows
                                    if x["girls"] and x["group"] == r["group"]
                                    )[r["girls_district"]] > m.MAX_DISTRICT}
    touched = ({r["group"] for r, _s, _d in moved}
               | {s for _r, s, _d in moved} | over)
    redrawn = set()
    for g in sorted(touched):
        pool = [r for r in rows if r["group"] == g and (r["girls"] or r["boys"])]
        have = len({r["girls_district"] for r in pool
                    if id(r) not in {id(x) for x, _s, _d in moved}})
        biggest = max(collections.Counter(r["girls_district"] for r in pool
                                          if r["girls"]).values(), default=0)
        if have and (have != m.district_count(len(pool))
                     or biggest > m.MAX_DISTRICT):
            for name, league in m.draw_districts(pool, cities, g).items():
                for r in pool:
                    if r["name"] == name:
                        r["girls_district"] = r["boys_district"] = league
            redrawn.add(g)
            print(f"  ({g} redrawn: {len(pool)} sponsors want "
                  f"{m.district_count(len(pool))} leagues, it had {have})")

    pending = {id(r) for r, _s, _d in moved if r["group"] not in redrawn}
    for r, _src, _dst in moved:
        if r["group"] in redrawn:
            continue
        pending.discard(id(r))
        settled = [x for x in rows if x["group"] == r["group"] and x is not r
                   and id(x) not in pending and x["girls_district"]]
        # Recomputed per school: an earlier placement changes the sizes this one
        # sees, which is the whole point of ranking on membership.
        members = collections.Counter(x["girls_district"] for x in settled)
        where = collections.defaultdict(lambda: [0, 0])
        for x in settled:
            slot = where[x["girls_district"]]
            slot[0] += x["area"] == r["area"]
            slot[1] += x["county"] == r["county"]
        if not where:
            sys.exit(f"no league to join in {r['group']} for {r['name']}")
        # ‼️ CAPACITY IS A HARD CONSTRAINT, NOT A TIE-BREAK. DISTRICT SIZE IS THE
        # SCHEDULE here — the league is a double round robin, so a 15-team league is
        # a 28-dual season against everyone else's 22. Ranking geography first and
        # size only among equals piled every promoted school in a county into the
        # same league and pushed six of them to 13-15. A league already at
        # MAX_DISTRICT is therefore skipped outright unless the class has no room
        # anywhere; only then does the nearest full one take the overflow.
        #
        # Order: has room · nearest by county · nearest by area · emptiest · name
        # (the last purely so the choice is reproducible rather than dict-ordered).
        best = min(where, key=lambda d: (members[d] >= m.MAX_DISTRICT,
                                         -where[d][1], -where[d][0], members[d], d))
        r["girls_district"] = r["boys_district"] = best


def report(rows: list[dict]) -> None:
    print(f"{'group':8}{'girls':>7}{'boys':>7}{'floor':>7}{'G dists':>9}{'B dists':>9}")
    jh = _jhsaa()
    for g in jh.GROUPS:
        gi = [r for r in rows if r["girls"] and r["group"] == g]
        bo = [r for r in rows if r["boys"] and r["group"] == g]
        floor = jh.sponsor_floor(g)
        flag = ""
        if floor and (len(gi) < floor or len(bo) < floor):
            flag = "   <-- UNDER THE SPONSOR FLOOR"
        print(f"{g:8}{len(gi):7}{len(bo):7}{floor or '-':>7}"
              f"{len({r['girls_district'] for r in gi}):9}"
              f"{len({r['boys_district'] for r in bo}):9}{flag}")
    sizes = collections.Counter()
    for r in rows:
        if r["girls"]:
            sizes[(r["group"], r["girls_district"])] += 1
    big = {k: v for k, v in sizes.items() if v > 12}
    if big:
        print(f"  ⚠️ leagues over MAX_DISTRICT: {big}")


def _jhsaa():
    sys.path.insert(0, _REPO)
    os.environ.setdefault("TENNIS_DB_PATH", os.path.join(_REPO, ".reclassify-tmp.db"))
    from app import jhsaa
    return jhsaa


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    m = _import_jhsaa()
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"]

    moved = (promote(rows, m) + demote(rows, m) + reclassify_named(rows, m)
             + reclassify_named(rows, m, m.RECLASSIFY_2039B, "RECLASSIFY_2039B"))
    rehome(rows, moved, m)
    for r, src, dst in moved:
        print(f"  {r['name'][:30]:30} {src} -> {dst}  {r['enrollment']:5}  "
              f"{r['girls_district']}")
    print(f"{len(moved)} promoted\n")
    check_rivals(rows, m)
    report(rows)

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nwrote {_DATA}")


if __name__ == "__main__":
    main()
