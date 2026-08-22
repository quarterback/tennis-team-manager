#!/usr/bin/env python3
"""Redraw league MEMBERSHIP inside chosen classifications, keeping the league NAMES.

    python3 scripts/jhsaa_redistrict.py 8A 7A 6A [--dry-run] [--prep-network PATH]

‼️ WHAT IS WRONG THAT THIS FIXES. A district is cut from a geographic ORDER (area →
county → city) into blocks of `MAX_DISTRICT`. That keeps most leagues tight and dumps
the REMAINDER — whatever is left once the metros have filled their own blocks — into
leagues that are geographic leftovers rather than regions. Measured across 6A/7A/8A,
ten leagues spanned more than 250 miles and the worst three about 400: a "league"
whose members are four hours apart is not a league, and its members play a schedule
nobody would drive.

‼️ THE NAMES STAY. League identity is a curated dataset (`LEAGUE_NAMES`, owner rule
2027-08 — real league names persist through realignment, and the drift IS the
realism). So this does not draw new leagues: it keeps exactly the leagues a class
already has and moves SCHOOLS between them. Each redrawn block inherits the name of
whichever existing league it overlaps most, so a league keeps its historical core and
its name follows the schools that have always been in it.

‼️ BOYS AND GIRLS ALWAYS SHARE A LEAGUE. A league belongs to the SCHOOL, so membership
is decided once per school and both gender fields are written from it.

‼️ RIVALRIES ARE NEVER SPLIT. A rivalry outranks geography exactly as it outranks
reclassification: after clustering, any pair sitting in different leagues is repaired
by moving one to join the other, swapping out that league's most distant member so no
league is pushed past `MAX_DISTRICT`.

Only the classifications named on the command line are touched. Everything else —
other classes, enrollments, names, sponsorship — is left exactly as it is.
"""
import argparse
import collections
import importlib.util
import json
import math
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")
_SEED = 20260822          # fixed: a redistricting must be reproducible


def _import_jhsaa():
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _miles(a, b):
    (la1, lo1), (la2, lo2) = a, b
    return 69.0 * math.hypot(la1 - la2,
                             (lo1 - lo2) * math.cos(math.radians((la1 + la2) / 2)))


def _span(pts):
    return max((_miles(p, q) for i, p in enumerate(pts) for q in pts[i + 1:]), default=0.0)


def cluster(items, k, cap, rng):
    """Capacitated k-means over (lat, lon). `items` is [(key, (lat, lon))].

    Plain k-means ignores capacity and would hand one metro every seat it wants while
    a neighbouring league starves. So each round assigns in order of REGRET — how much
    worse a school's second-best league is than its best — which gives the seats to
    the schools that would suffer most by missing out, the standard fix for exactly
    this failure.
    """
    pts = [p for _, p in items]
    centres = [pts[i] for i in rng.sample(range(len(pts)), k)]
    best = None
    for _ in range(40):
        order = []
        for idx, (_, p) in enumerate(items):
            d = sorted((_miles(p, c), ci) for ci, c in enumerate(centres))
            regret = (d[1][0] - d[0][0]) if len(d) > 1 else 0.0
            order.append((-regret, idx, d))
        order.sort()
        groups = collections.defaultdict(list)
        for _, idx, d in order:
            for _, ci in d:
                if len(groups[ci]) < cap:
                    groups[ci].append(idx)
                    break
        moved = False
        for ci, members in groups.items():
            if not members:
                continue
            la = sum(items[i][1][0] for i in members) / len(members)
            lo = sum(items[i][1][1] for i in members) / len(members)
            if _miles(centres[ci], (la, lo)) > 0.5:
                moved = True
            centres[ci] = (la, lo)
        cost = sum(_span([items[i][1] for i in m]) for m in groups.values())
        if best is None or cost < best[0]:
            best = (cost, {ci: list(m) for ci, m in groups.items()})
        if not moved:
            break
    return best[1]


def balance(groups, items, cap, floor):
    """‼️ LEAGUE SIZE IS THE SCHEDULE, so a redraw may not leave a rump. The capacitated
    assignment fills leagues to `cap` and can leave the last one with whatever is over,
    and a six-team league plays roughly half the league season everyone else does. Any
    league under `floor` therefore pulls its geographically NEAREST available member
    from a league that can spare one — nearest, so fixing the size does not undo the
    geography the redraw was for."""
    centre = {}
    def recentre(ci):
        mem = groups[ci]
        centre[ci] = (sum(items[i][1][0] for i in mem) / len(mem),
                      sum(items[i][1][1] for i in mem) / len(mem)) if mem else (0, 0)
    for ci in groups:
        recentre(ci)
    for _ in range(200):
        short = [ci for ci in groups if len(groups[ci]) < floor]
        if not short:
            break
        ci = min(short, key=lambda c: len(groups[c]))
        pool = [(_miles(items[i][1], centre[ci]), i, cj)
                for cj in groups if cj != ci and len(groups[cj]) > floor
                for i in groups[cj]]
        if not pool:
            break
        _, i, cj = min(pool)
        groups[cj].remove(i)
        groups[ci].append(i)
        recentre(ci)
        recentre(cj)
    return groups


def keep_rivals(groups, items, pos, rivals, cap):
    """Pull split rivalry pairs back together, swapping out the most distant member of
    the receiving league so nothing exceeds `cap`."""
    where = {items[i][0]: ci for ci, m in groups.items() for i in m}
    index = {k: i for i, (k, _) in enumerate(items)}
    for a, b in rivals:
        if a not in where or b not in where or where[a] == where[b]:
            continue
        home, away = where[b], where[a]           # move `a` to `b`'s league
        if len(groups[home]) >= cap:
            centre = pos[b]
            far = max(groups[home], key=lambda i: _miles(pos[items[i][0]], centre))
            groups[home].remove(far)
            groups[away].append(far)
            where[items[far][0]] = away
        groups[away].remove(index[a])
        groups[home].append(index[a])
        where[a] = home
    return groups


def redistrict(rows, cls, pos, m, rng):
    members = [r for r in rows if r["group"] == cls and r["city"] in pos]
    missing = [r for r in rows if r["group"] == cls and r["city"] not in pos]
    if missing:
        print(f"  ! {cls}: {len(missing)} schools have no coordinates and are left put: "
              f"{[r['name'] for r in missing][:5]}")
    names = collections.Counter(r["girls_district"] for r in members)
    k = len(names)
    items = [(r["name"], pos[r["city"]]) for r in members]
    groups = cluster(items, k, m.MAX_DISTRICT, rng)
    # A floor one under the even split: even sizes are the goal, but forcing exact
    # evenness would drag distant schools in to satisfy arithmetic.
    floor = max(1, len(items) // k - 1)
    groups = balance(groups, items, m.MAX_DISTRICT, floor)
    rivals = [(a, b) for a, b in getattr(m, "RIVALRIES", ())]
    groups = keep_rivals(groups, items, {r["name"]: pos[r["city"]] for r in members},
                         rivals, m.MAX_DISTRICT)

    # ‼️ A BLOCK INHERITS THE NAME IT MOST OVERLAPS. Assigning names by centroid or
    # alphabetically would shuffle a class's league names wholesale; overlap keeps each
    # name on the schools that have always carried it, which is what makes a
    # realignment read as a realignment rather than a rebrand.
    by_name = {r["name"]: r["girls_district"] for r in members}
    taken, out = set(), {}
    order = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    for ci, idx in order:
        counts = collections.Counter(by_name[items[i][0]] for i in idx)
        pick = next((n for n, _ in counts.most_common() if n not in taken), None)
        pick = pick or next(n for n in names if n not in taken)
        taken.add(pick)
        out[ci] = pick
    return {items[i][0]: out[ci] for ci, idx in groups.items() for i in idx}, members


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("classes", nargs="+", help="classifications to redraw, e.g. 8A 7A 6A")
    ap.add_argument("--prep-network",
                    default=os.path.join(os.path.dirname(_REPO), "prep-network"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    m = _import_jhsaa()
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"] if isinstance(doc, dict) else doc
    with open(os.path.join(args.prep_network, "records", "orgs", "cities.json"),
              encoding="utf-8") as fh:
        cities = json.load(fh)
    cities = cities["cities"] if isinstance(cities, dict) else cities
    pos = {m.CITY_RENAMES.get(c["name"], c["name"]): (c["lat"], c["lon"]) for c in cities}

    rng = random.Random(_SEED)
    moved_total = 0
    for cls in args.classes:
        members = [r for r in rows if r["group"] == cls]
        if not members:
            sys.exit(f"no programs in {cls}")
        before = collections.defaultdict(list)
        for r in members:
            before[r["girls_district"]].append(r)
        assign, placed = redistrict(rows, cls, pos, m, rng)

        after = collections.defaultdict(list)
        for r in members:
            after[assign.get(r["name"], r["girls_district"])].append(r)
        moved = sum(1 for r in members if assign.get(r["name"], r["girls_district"])
                    != r["girls_district"])
        moved_total += moved

        def spans(d):
            return sorted((_span([pos[x["city"]] for x in v if x["city"] in pos]), k)
                          for k, v in d.items())
        b, a = spans(before), spans(after)
        print(f"\n== {cls}: {len(members)} programs, {len(before)} leagues — "
              f"{moved} schools change league")
        print(f"   span  worst {b[-1][0]:.0f} -> {a[-1][0]:.0f} mi · "
              f"mean {sum(x for x, _ in b)/len(b):.0f} -> {sum(x for x, _ in a)/len(a):.0f} mi · "
              f"over 250mi {sum(1 for x, _ in b if x > 250)} -> {sum(1 for x, _ in a if x > 250)}")
        for span, name in reversed(a):
            areas = collections.Counter(x["area"] for x in after[name])
            print(f"   {span:6.0f} mi  {name:<40} {len(after[name]):2}  {dict(areas)}")
        over = {k: len(v) for k, v in after.items() if len(v) > m.MAX_DISTRICT}
        if over:
            sys.exit(f"{cls}: league over MAX_DISTRICT after redraw: {over}")
        for r in members:
            new = assign.get(r["name"])
            if new:
                r["girls_district"] = r["boys_district"] = new

    print(f"\n{moved_total} schools changed league in total")
    if args.dry_run:
        print("--dry-run: nothing written")
        return
    with open(_DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_DATA}")


if __name__ == "__main__":
    main()
