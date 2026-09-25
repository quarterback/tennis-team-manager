"""League redistricting — the clustering `scripts/jhsaa_redistrict.py` runs, made
callable from the app so a reclassification commit can redraw the leagues of the
classes it touched (owner spec 2026-09, `docs/DESIGN-jhsaa-reclassification.md`).

The functions are the script's, moved verbatim; the script imports them from here
so there is ONE clustering. What the script read off `scripts/import_jhsaa.py` —
the league-name bank, `MAX_DISTRICT`, `DISTRICT_TARGET`, `RIVALRIES` — the app reads
from `data/jhsaa/districting.json` (the app cannot read `scripts/`; the two are
asserted equal by `tests/test_jhsaa_reclass.py`, the rivalry-tables idiom). Town
positions come from `data/jhsaa/coords.json`, derived from the gazetteer by
`scripts/build_jhsaa_coords.py`; a town without one is placed at its county's
centroid, exactly as the script does.

‼️ A REDRAW POOLS LIVE SPONSORS ONLY, and a league is `(classification, name)`
shared by both genders — see the script's docstring for the rules; nothing here
changes them.
"""
from __future__ import annotations

import collections
import json
import math
import os
import random
from types import SimpleNamespace

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "jhsaa")
_DISTRICTING = os.path.join(_DATA_DIR, "districting.json")
_COORDS = os.path.join(_DATA_DIR, "coords.json")
#: The script's fixed seed — a redistricting must be reproducible.
SEED = 20260822
_cfg_cache: dict = {}
_coords_cache: dict = {}


def districting_config() -> SimpleNamespace:
    """The importer's districting constants, as the namespace `redistrict()` reads
    (`district_count`, `MAX_DISTRICT`, `DISTRICT_TARGET`, `RIVALRIES`, `LEAGUE_NAMES`)."""
    hit = _cfg_cache.get("cfg")
    if hit is not None:
        return hit
    with open(_DISTRICTING, encoding="utf-8") as fh:
        doc = json.load(fh)
    # ‼️ `district_target` IS A FLOAT (9.5 since 2096) — `int()` silently made it 9 and
    # put the runtime redraw on a different rule from the importer while the sync test
    # still compared equal-ish. `min_district_size` is the hard floor the importer got
    # in the same rule; defaulted so an older config file still reads.
    max_d = int(doc["max_district"])
    target = float(doc["district_target"])
    min_size = int(doc.get("min_district_size", 1))

    def district_count(n: int) -> int:
        """`import_jhsaa.district_count`, mirrored. Must stay identical — the sync test
        compares both across a spread of pool sizes."""
        if n <= 0:
            return 0
        k = max(round(n / target), -(-n // max_d), 1)
        return max(1, min(k, n // min_size)) if n >= min_size else 1

    cfg = SimpleNamespace(MAX_DISTRICT=max_d, DISTRICT_TARGET=target,
                          MIN_DISTRICT_SIZE=min_size,
                          RIVALRIES=[tuple(p) for p in doc["rivalries"]],
                          LEAGUE_NAMES=[(n, a) for n, a in doc["league_names"]],
                          district_count=district_count)
    _cfg_cache["cfg"] = cfg
    return cfg


def coords() -> dict:
    """{town: (lat, lon)} — a COPY, since `redistrict` writes centroid fallbacks into
    the map it is handed."""
    hit = _coords_cache.get("pos")
    if hit is None:
        with open(_COORDS, encoding="utf-8") as fh:
            hit = {k: (float(v[0]), float(v[1])) for k, v in json.load(fh).items()}
        _coords_cache["pos"] = hit
    return dict(hit)


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
    """‼️ LEAGUE SIZE IS THE SCHEDULE, so a redraw may not leave a rump. Any league
    under `floor` pulls its geographically NEAREST available member from a league
    that can spare one — nearest, so fixing the size does not undo the geography."""
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


def spill(groups, items, cap):
    """The cap is re-enforced after every repair pass: any league over `cap` sheds
    its most distant member to the nearest league with room until none is over."""
    def centre(ci):
        mem = groups[ci]
        return (sum(items[i][1][0] for i in mem) / len(mem),
                sum(items[i][1][1] for i in mem) / len(mem))
    for _ in range(200):
        over = [ci for ci in groups if len(groups[ci]) > cap]
        if not over:
            break
        ci = max(over, key=lambda c: len(groups[c]))
        c = centre(ci)
        far = max(groups[ci], key=lambda i: _miles(items[i][1], c))
        dest = min((cj for cj in groups if cj != ci and len(groups[cj]) < cap),
                   key=lambda cj: _miles(items[far][1], centre(cj)), default=None)
        if dest is None:
            break                        # nowhere with room: cap is infeasible
        groups[ci].remove(far)
        groups[dest].append(far)
    return groups


def redistrict(rows, cls, pos, m, rng, cap=None, log=None):
    """Redraw the leagues of one class over `rows` (the schools.json rows, with
    `group` already holding the class each school ENTERS). Returns
    `(assign, members, notes)` — `assign` is {school name: league name} for every
    live member. Pure over its inputs; nothing is written."""
    say = log or (lambda s: None)
    live = [r for r in rows if r["group"] == cls
            and (r.get("girls") or r.get("boys"))]
    for r in live:
        if r["city"] in pos:
            continue
        for scope in ("county", "area", "group"):
            mates = [pos[x["city"]] for x in rows
                     if x.get(scope) == r.get(scope) and x["city"] in pos]
            if mates:
                pos[r["city"]] = (sum(p[0] for p in mates) / len(mates),
                                  sum(p[1] for p in mates) / len(mates))
                say(f"  ~ {cls}: {r['name']} ({r['city']}) placed at its {scope} centroid")
                break
    members = [r for r in live if r["city"] in pos]
    missing = [r for r in live if r["city"] not in pos]
    if missing:
        say(f"  ! {cls}: {len(missing)} schools have no coordinates and are left put: "
            f"{[r['name'] for r in missing][:5]}")
    names = collections.Counter(r["girls_district"] for r in members)
    k = m.district_count(len(members))
    items = [(r["name"], pos[r["city"]]) for r in members]
    cap = cap or m.MAX_DISTRICT
    k = max(k, -(-len(items) // cap))
    groups = cluster(items, k, cap, rng)
    assert sum(len(v) for v in groups.values()) == len(items), \
        "clusterer dropped a school — k×cap must cover the pool"
    floor = max(1, min(m.DISTRICT_TARGET - 1, len(items) // k))
    groups = balance(groups, items, cap, floor)
    rivals = [(a, b) for a, b in getattr(m, "RIVALRIES", ())]
    groups = keep_rivals(groups, items, {r["name"]: pos[r["city"]] for r in members},
                         rivals, cap)
    groups = spill(groups, items, cap)

    by_name = {r["name"]: r["girls_district"] for r in members}
    by_area = {r["name"]: r["area"] for r in members}
    # ‼️ EVERY OTHER CLASS'S LEAGUES ARE ALREADY CLAIMED (owner rule 2096: no league
    # name repeats anywhere in the association). Seeded from `rows` — which holds the
    # WHOLE state, not just `cls` — rather than passed in, so every caller gets this
    # without being updated: `redistrict` is the one door the offseason redraws and the
    # one-off scripts all come through. Scoped per class, a redraw could hand 3A a name
    # 9A already holds; on the current pools, drawing the classes independently yields
    # only 71 distinct names for 95 leagues.
    #
    # A name this class is RETIRING is not claimed elsewhere and stays available to it,
    # which is why `names` is excluded from the foreign set rather than added to it.
    foreign = {r["girls_district"] for r in rows
               if r.get("group") != cls and (r.get("girls") or r.get("boys"))
               and r.get("girls_district")} - set(names)
    taken, out = set(), {}
    heads = {n.split()[0] for n in names} | {n.split()[0] for n in foreign}
    bank = m.LEAGUE_NAMES[:]
    rng.shuffle(bank)
    order = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    for ci, idx in order:
        counts = collections.Counter(by_name[items[i][0]] for i in idx)
        pick = next((n for n, _ in counts.most_common()
                     if n not in taken and n not in foreign), None)
        if pick is None:
            area = collections.Counter(
                by_area[items[i][0]] for i in idx).most_common(1)[0][0]
            free = [(n, aff) for n, aff in bank
                    if n not in taken and n not in names and n not in foreign
                    and n.split()[0] not in heads]
            pick = (next((n for n, aff in free if aff == area), None)
                    or next((n for n, _ in free), None)
                    or f"District {ci + 1}")
        taken.add(pick)
        heads.add(pick.split()[0])
        out[ci] = pick
    notes = []
    retired = sorted(set(names) - taken)
    if retired:
        notes.append(f"   retired {len(retired)}: {', '.join(retired)}")
    new = sorted(n for n in taken if n not in names)
    if new:
        notes.append(f"   new     {len(new)}: {', '.join(new)}")
    return ({items[i][0]: out[ci] for ci, idx in groups.items() for i in idx},
            members, notes)


def redraw_classes(rows: list[dict], classes: list[str], cap: int | None = None,
                   seed: int = SEED) -> dict:
    """Redraw every class in `classes` over `rows` IN PLACE (both gender district
    fields) and return {class: notes}. The app's entry point; the script's `main`
    is the same loop with printing."""
    m = districting_config()
    pos = coords()
    rng = random.Random(seed)
    out = {}
    for cls in classes:
        notes: list[str] = []
        assign, members, more = redistrict(rows, cls, pos, m, rng, cap=cap,
                                           log=notes.append)
        notes += more
        for r in members:
            new = assign.get(r["name"])
            if new:
                r["girls_district"] = r["boys_district"] = new
        over = {}
        for r in members:
            over[r["girls_district"]] = over.get(r["girls_district"], 0) + 1
        big = {k: v for k, v in over.items() if v > m.MAX_DISTRICT}
        if big:
            raise ValueError(f"{cls}: league over MAX_DISTRICT after redraw: {big}")
        out[cls] = notes
    return out
