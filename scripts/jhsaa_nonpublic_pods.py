#!/usr/bin/env python3
"""Give the JHSAA's private programs their own districts — the PODS (owner rule
2026-09) — and record each one's OLD LEAGUE.

Reads and rewrites `data/jhsaa/schools.json`:
  * every private row's `group` becomes its Non-Public class (10B at or above
    `jhsaa.NONPUBLIC_CUT` or in `NONPUBLIC_PLAYUP`, else 11B);
  * `old_group` / `old_league` record the public class and league the row held,
    which is the league it plays once-each as non-conference duals;
  * both gender district fields become the pod. The MEMBERSHIP is the owner's
    (`POD_MAP`, 8-10 schools each, dictated by name 2026-09 — a pod is the owner's to
    draw, so this script never re-clusters it); only the NAME is drawn here, from
    the league bank (`jhsaa_districting`'s rules: unused statewide, no shared
    leading word, area affinity first). A later realignment re-pods through
    `app.jhsaa_districting.pod_nonpublic`, which clusters.
Public leagues keep their names and their public members; nothing else moves.

Usage: python3 scripts/jhsaa_nonpublic_pods.py [--dry-run]
"""
from __future__ import annotations

import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import jhsaa as jh                      # noqa: E402
from app import jhsaa_districting as jd          # noqa: E402

PATH = os.path.join(ROOT, "data", "jhsaa", "schools.json")


def road_class(r: dict) -> str:
    ident = r.get("source") or r["name"]
    if ident in jh.NONPUBLIC_PLAYUP or int(r["enrollment"]) >= jh.NONPUBLIC_CUT:
        return jh.NONPUBLIC_GROUPS[0]
    return jh.NONPUBLIC_GROUPS[1]


POD_MAP = {
    "10B": [
        ["Basalt", "Calasanz Prep", "Clarendon", "Lycee Valmont", "Pope Leo XIV",
         "St. Ignatius", "St. Teresa", "Telfair Country Day"],
        ["Abbey Prep", "Ashbury Latin", "Holy Cross", "Robledo", "Ryken",
         "St. Catherine Academy", "St. Francis", "Westfield Friends", "Westside Christian"],
        ["Baptist", "Condotti Vanguard Academy", "De La Salle", "Helena Academy",
         "Notre Dame", "Romero-Finniski", "Southridge Christian", "Trinity Catholic",
         "Valley Christian"],
        ["Belmonte Catholic", "Belmonte Collegiate", "Cardinal Echevarria", "Kingston",
         "Mater Dei", "Pacific Friends", "Rock on the Hill Christian Academy",
         "St. Gabriel Academy"],
        ["Bellarmine Prep", "Bishop Valera", "Delbarton", "Northside Christian",
         "St. Isidore Academy", "Verrettes", "Walter-Kenny", "Wheeler Academy"],
        ["Archbishop Gregory", "Borondón Hills", "Christian Brothers", "Hazel Country Day",
         "Jesuit", "Leidesdorff Country Day", "Marshfield Prep", "Natchez Prep",
         "Xavier College Prep"],
        ["Chaminade", "Christchurch Episcopal", "Henson Prep", "Metropolitan Country Day",
         "Port Veles Episcopal", "Providence Academy", "Sacred Heart", "St. Vincent",
         "Swiss Hills Prep"],
    ],
    "11B": [
        ["Bayside Christian", "Calvary Christian", "Coastal Christian", "Evans",
         "Fletcher-Garrison Hall", "Pinecrest", "Sage Summit", "Sinkford",
         "St. Norbert Abbey", "St. Sebastian Prep"],
        ["Bridger County Christian", "Covenant Christian", "Georgia Mills", "Ibarra",
         "Laketown County Christian", "Natchez Mercy", "Raft County Catholic",
         "Star Valley Catholic"],
        ["Barlowe Christian", "Espoo", "New Hope Christian", "Palisade Prep", "Peregrine",
         "St. Lucia Academy", "St. Lucy", "Veritas Academy", "Washington San Cordero"],
        ["Banfield Day", "Calderwood", "Christ the King", "Gottschalk-Herman", "Holy Family",
         "Kernwood Christian", "Kilbride Hall", "Mercy Academy Valley", "Olivet",
         "Pope Francis"],
        ["Copper Gap", "Featherstone Tech", "High Desert Christian", "Olive Baptist",
         "Paddock Episcopal", "Paddock Tech", "St. Dominic", "St. Josephine Bakhita",
         "Star Hollow"],
        ["All Saints Episcopal", "Bethel Christian", "Calvary Chapel Kernwood", "Cassius",
         "Foothills Christian", "Goldbank Hall", "Grace Christian", "Kernwood Lutheran",
         "Monsignor Barrow", "Quartz City Collegiate"],
    ],
}


def name_pods(rows: list[dict], log=print) -> None:
    """Name every pod in `POD_MAP` from the league bank and write it onto its
    members' district fields — the `redistrict` naming rules, without the draw."""
    m = jd.districting_config()
    by = {r["name"]: r for r in rows}
    taken = {r.get("girls_district") for r in rows
             if r["group"] not in jh.NONPUBLIC_GROUPS and r.get("girls_district")}
    heads = {n.split()[0] for n in taken}
    rng = jd.random.Random(jd.SEED)
    bank = m.LEAGUE_NAMES[:]
    rng.shuffle(bank)
    for cls, pods in POD_MAP.items():
        for pod in pods:
            areas = collections.Counter(by[n]["area"] for n in pod)
            free = [(n, a) for n, a in bank
                    if n not in taken and n.split()[0] not in heads]
            pick = next((n for n, a in free if a == areas.most_common(1)[0][0]), None) \
                or next((n for n, _ in free), None)
            if pick is None:
                raise SystemExit(f"{cls}: the league bank is exhausted")
            taken.add(pick)
            heads.add(pick.split()[0])
            for n in pod:
                by[n]["girls_district"] = by[n]["boys_district"] = pick
            log(f"{cls}  {pick}: {', '.join(pod)}")


def apply(rows: list[dict], log=print) -> None:
    listed = {n for pods in POD_MAP.values() for pod in pods for n in pod}
    by = {r["name"]: r for r in rows}
    privates = {r["name"] for r in rows if r.get("private")}
    if listed != privates:
        raise SystemExit(f"POD_MAP and the private rows disagree: "
                         f"unlisted {sorted(privates - listed)}, "
                         f"unknown {sorted(listed - privates)}")
    moved = 0
    for r in rows:
        if not r.get("private"):
            continue
        if r["group"] not in jh.NONPUBLIC_GROUPS:
            r["old_group"] = r["group"]
            r["old_league"] = r.get("girls_district") or r.get("boys_district") or ""
            moved += 1
        r.pop("play_up", None)
    for cls, pods in POD_MAP.items():
        for pod in pods:
            for n in pod:
                by[n]["group"] = cls
                want = road_class(by[n])
                if want != cls:
                    log(f"note: {n} sits in the owner's {cls} pod; the cut alone says {want}")
    log(f"{moved} private rows left their public league for the Non-Public classes")
    name_pods(rows, log)
    # The public leagues after the privates leave — a reader's check, no redraw.
    sizes = collections.Counter()
    for r in rows:
        if r.get("girls") and r["group"] not in jh.NONPUBLIC_GROUPS:
            sizes[(r["group"], r["girls_district"])] += 1
    small = sorted((k, v) for k, v in sizes.items() if v < 6)
    if small:
        log("public leagues now under six girls' programs: "
            + ", ".join(f"{g} {d} ({v})" for (g, d), v in small))
    for cls in jh.NONPUBLIC_GROUPS:
        for g in ("girls", "boys"):
            pods = collections.Counter(r[f"{g}_district"] for r in rows
                                       if r["group"] == cls and r.get(g))
            log(f"{cls} {g}: {sum(pods.values())} programs in {len(pods)} pods "
                f"{sorted(pods.values())}")


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    with open(PATH, encoding="utf-8") as fh:
        doc = json.load(fh)
    apply(doc["schools"])
    if dry:
        print("dry run — nothing written")
        return 0
    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
