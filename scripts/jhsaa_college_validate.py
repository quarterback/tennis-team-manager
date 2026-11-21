#!/usr/bin/env python3
"""Measure the alumni tracker's career models against each other — model 1 (the
rank-matched line) and model 2 (`app/jhsaa_college_v2.py`) — on the SAME
graduating classes, and print example careers.

    python3 scripts/jhsaa_college_validate.py                  # girls, 6 classes
    python3 scripts/jhsaa_college_validate.py --gender both --classes 8

It plays no season and writes nothing. The seniors are REAL: one year of real
Jefferson rosters is built (ratings, ceilings, academics, styles, nationality),
and each test class is a resample of those seniors with a small strength shift,
so classes differ the way classes do. What that cannot supply is a senior-year
RECORD — no season is played here — so the model's high-school-results inputs
are exercised by the unit tests, not by this report.

‼️ The `__main__` guard is required: the app's pools use a spawn context, and an
unguarded script is re-run whole by every worker.
"""
from __future__ import annotations

import argparse
import collections
import copy
import os
import random
import statistics as st
import sys
import tempfile
import time
from types import SimpleNamespace

SHIFTS = (0.0, 0.6, -0.6, 1.2, -1.2, 0.0, 0.3, -0.3)


def pct(n, d):
    return f"{100.0 * n / d:5.1f}%" if d else "   — "


def real_seniors(jh, jcol, gender: str, year: int, salt: str) -> list:
    out = []
    for school in jh.load_schools(gender):
        if school.state:                       # an out-of-state affiliate
            continue
        roster = jh.build_roster(school, year, salt)
        team = SimpleNamespace(school=school, roster=roster)
        out += [jcol.snapshot_of(p, team) for p in roster if p.grade == 12]
    return out


def resample(seniors: list, k: int, shift: float) -> list:
    r = random.Random(f"class|{k}")
    out = []
    for i in range(len(seniors)):
        s = copy.copy(r.choice(seniors))
        d = shift + r.gauss(0.0, 0.4)
        s["pid"] = f"{s['pid']}#{k}-{i}"
        s["ovr"] += d
        s["pot"] += d
        s["ceiling"] += d
        out.append(s)
    return out


def metrics(rows: list, model: int) -> dict:
    """One model's careers, reduced to the numbers the report compares. Model 1
    rows carry singles only; the keys they lack read as absent."""
    n = len(rows)
    m = {"n": n}
    m["div"] = collections.Counter(r["division"] for r in rows)
    fr = [r["seasons"][0] for r in rows]
    m["fr_start"] = sum(1 for s in fr if s.get("pos"))
    seniors = [r["seasons"][3] for r in rows if len(r["seasons"]) == 4]
    m["sr_playing"] = len(seniors)
    m["sr_start"] = sum(1 for s in seniors if s.get("pos"))
    m["never_singles"] = sum(1 for r in rows if r.get("peak") is None)
    m["never_anything"] = sum(
        1 for r in rows if r.get("peak") is None and r.get("d_peak") is None) \
        if model == 2 else m["never_singles"]
    m["peak1"] = sum(1 for r in rows if r.get("peak") == 1)
    m["transfer"] = sum(1 for r in rows if r.get("transfers"))
    m["status"] = collections.Counter(r.get("status", "graduated") for r in rows)
    m["years"] = collections.Counter(len(r["seasons"]) for r in rows)
    m["arc"] = collections.Counter(r.get("arc", "—") for r in rows)
    by_year = collections.defaultdict(list)
    move = []
    for r in rows:
        for i, s in enumerate(r["seasons"]):
            if s["w"] + s["l"] >= 10:
                by_year[i].append(s["w"] / (s["w"] + s["l"]))
        pos = [s.get("pos") for s in r["seasons"] if s.get("pos")]
        if len(pos) >= 2:
            move.append(pos[0] - pos[-1])          # + = moved UP the lineup
    m["win"] = {i: v for i, v in by_year.items()}
    m["move"] = move
    career = [r["w"] / (r["w"] + r["l"]) for r in rows if r["w"] + r["l"] >= 20]
    m["career_win"] = career
    m["losing"] = sum(1 for x in career if x < 0.5)
    hon = collections.Counter()
    for r in rows:
        for s in r["seasons"]:
            for h in s.get("honors", []):
                hon[(r["division"] if model == 1 else s.get("division", r["division"]), h)] += 1
    m["honors"] = hon
    m["honoured"] = sum(1 for r in rows if r.get("honors"))
    m["d1_never"] = sum(1 for r in rows if r["division"] == "D1" and r.get("peak") is None)
    m["d1"] = sum(1 for r in rows if r["division"] == "D1")
    if model == 2:
        m["dbl_spec"] = sum(1 for r in rows if r["arc"] == "doubles_specialist")
        m["dbl_starts"] = sum(1 for r in rows for s in r["seasons"] if s.get("d_pair"))
        m["seasons"] = sum(len(r["seasons"]) for r in rows)
    return m


def dist(vals):
    if len(vals) < 5:
        return "—"
    q = st.quantiles(vals, n=10)
    return f"p10 {q[0]:.2f} · median {st.median(vals):.2f} · p90 {q[8]:.2f}"


def story(r: dict, ctx) -> str:
    """One career as a few lines, with the circumstances that produced it."""
    lv = r["level"]
    prog = ctx.programs[r["college"]]
    lines = [f"**{r['name']}** ({r['hs']}, class rank {r['hs_rank']}, exit {r['hs_ovr']}) — "
             f"*{r['arc'].replace('_', ' ')}*",
             f"  arrived at level {lv['arrive']:.1f} with {lv['head']:.1f} to grow "
             f"(staffs estimated {lv['est']:.1f}); development shape `{r['shape']}`; "
             f"wanted `{r['aspiration']}`; doubles lean {lv['doubles_lean']:+.1f}",
             f"  chose {r['college']} ({r['division']}, {r['conf']}) — roster talent "
             f"{ctx.level[prog.school]:.1f} against the player's {lv['talent']:.1f}"]
    for s in r["seasons"]:
        sp = f"No. {s['s_pos']} singles {s['s_w']}-{s['s_l']}" if s["s_pos"] else \
            (f"reserve, {s['s_w']}-{s['s_l']} in spot starts" if s["s_w"] + s["s_l"] else "did not play singles")
        dp = f"No. {s['d_pair']} doubles {s['d_w']}-{s['d_l']}" if s["d_pair"] else \
            (f"{s['d_w']}-{s['d_l']} doubles" if s["d_w"] + s["d_l"] else "no doubles")
        extra = (" · injured" if s["injury"] == "part" else " · out injured" if s["injury"] else "") \
            + ("".join(f" · {h}" for h in s["honors"]))
        lines.append(f"  {s['year']} {s['class']} {s['college']}: {sp}; {dp}{extra}")
    for t in r["transfers"]:
        lines.append(f"  transferred after {t['after']} year: {t['from']} → {t['to']} "
                     f"({t['reason']}; {t['role_before']} → {t['role_after']})")
    lines.append(f"  finished: {r['status'].replace('_', ' ')} after {r['years']} season(s); "
                 f"singles {r['s_w']}-{r['s_l']}, doubles {r['d_w']}-{r['d_l']}"
                 + (f"; {', '.join(r['honors'])}" if r["honors"] else ""))
    return "\n".join(lines)


def run(gender: str, n_classes: int, year: int, salt: str) -> None:
    from app import jhsaa as jh
    from app import jhsaa_college as jcol
    from app import jhsaa_college_v2 as v2

    t0 = time.time()
    seniors = real_seniors(jh, jcol, gender, year, salt)
    gaps = [s["ceiling"] - s["ovr"] for s in seniors]
    print(f"\n# {gender}: {len(seniors)} real seniors built in {time.time() - t0:.0f}s "
          f"(exit rating median {st.median(s['ovr'] for s in seniors):.1f}, "
          f"ceiling − exit median {st.median(gaps):.1f})")

    history = [resample(seniors, -k, 0.0) for k in range(1, v2.REF_CLASSES + 1)]
    pools = [sorted((s["ovr"] for s in c), reverse=True)[:v2.TARGET_BOUND] for c in history]
    a1, a2, per_class, stored, timing = [], [], [], {}, []
    ctx = None
    for i in range(n_classes):
        klass = resample(seniors, i + 1, SHIFTS[i % len(SHIFTS)])
        ref = sorted(x for p in pools[-v2.REF_CLASSES:] for x in p)
        gy = year + i
        r1 = jcol.build_class([dict(s) for s in klass], gender, gy, salt)
        t = time.time()
        r2 = v2.build_class([dict(s) for s in klass], gender, gy, salt, ref=ref,
                            stored=stored)
        timing.append(time.time() - t)
        if i == 0:                                 # determinism, on the first class
            again = v2.build_class([dict(s) for s in klass], gender, gy, salt, ref=ref,
                                   stored={})
            assert again == r2, "model 2 is not deterministic"
        for r in r2:
            for s in r["seasons"]:
                stored.setdefault((s["college"], s["year"]), []).append(
                    {"pid": r["pid"], "slv": s["slv"], "dlv": s["dlv"],
                     "s_pos": s["s_pos"], "d_pair": s["d_pair"]})
        pools.append(sorted((s["ovr"] for s in klass), reverse=True)[:v2.TARGET_BOUND])
        a1 += r1
        a2 += r2
        d2 = collections.Counter(r["division"] for r in r2)
        d1 = collections.Counter(r["division"] for r in r1)
        per_class.append((gy, SHIFTS[i % len(SHIFTS)], len(r1), d1, len(r2), d2))
        ctx = ctx or v2.Context(gender, salt)

    # ---- integrity -------------------------------------------------------------
    from app import ncaa, recruit_economy
    seen, clash = set(), 0
    for r in a2:
        for s in r["seasons"]:
            if s["s_pos"]:
                key = (s["college"], s["year"], s["s_pos"])
                clash += key in seen
                seen.add(key)
        assert r["s_w"] == sum(s["s_w"] for s in r["seasons"])
        for s in r["seasons"]:                     # All-Conference comes first
            assert "All-American" not in s["honors"] or "All-Conference" in s["honors"]
            assert "All-American (doubles)" not in s["honors"] \
                or "All-Conference (doubles)" in s["honors"]
        assert r["d_l"] == sum(s["d_l"] for s in r["seasons"])
        assert all(s["college"] in ctx.programs for s in r["seasons"])
        assert [c["college"] for c in r["colleges"]] == \
            [r["seasons"][0]["college"]] + [t["to"] for t in r["transfers"]]
    by_pid = {s["pid"]: s for i in range(n_classes)
              for s in resample(seniors, i + 1, SHIFTS[i % len(SHIFTS)])}
    for r in a2:
        snap = by_pid[r["pid"]]
        for c in r["colleges"]:
            p = ctx.programs[c["college"]]
            assert not (ncaa.us_only_program(p.school) and not snap["domestic"])
            if p.division == "D4":
                assert snap["academic"] >= recruit_economy.d4_academic_min(p, 0, salt)

    # ---- the report -------------------------------------------------------------
    print("\n## Class by class (the number of careers and where they start)\n")
    print("| class | strength | model 1 | D1/D2/D4/D3 | model 2 | D1/D2/D4/D3 |")
    print("|---|---|---|---|---|---|")
    for gy, sh, n1, d1, n2, d2 in per_class:
        print(f"| {gy} | {sh:+.1f} | {n1} | {d1['D1']}/{d1['D2']}/{d1['D4']}/{d1['D3']} "
              f"| {n2} | {d2['D1']}/{d2['D2']}/{d2['D4']}/{d2['D3']} |")
    m1, m2 = metrics(a1, 1), metrics(a2, 2)
    print(f"\n## All {n_classes} classes pooled\n")
    print("| | model 1 | model 2 |")
    print("|---|---|---|")
    rows = [
        ("careers", m1["n"], m2["n"]),
        ("singles starter as a freshman", pct(m1["fr_start"], m1["n"]), pct(m2["fr_start"], m2["n"])),
        ("still playing as a senior", pct(m1["sr_playing"], m1["n"]), pct(m2["sr_playing"], m2["n"])),
        ("singles starter as a senior (of those)", pct(m1["sr_start"], m1["sr_playing"]), pct(m2["sr_start"], m2["sr_playing"])),
        ("never a singles starter", pct(m1["never_singles"], m1["n"]), pct(m2["never_singles"], m2["n"])),
        ("never in a singles OR doubles lineup", pct(m1["never_anything"], m1["n"]), pct(m2["never_anything"], m2["n"])),
        ("D1 signees never a singles starter", pct(m1["d1_never"], m1["d1"]), pct(m2["d1_never"], m2["d1"])),
        ("reached No. 1 singles at some point", pct(m1["peak1"], m1["n"]), pct(m2["peak1"], m2["n"])),
        ("transferred", pct(m1["transfer"], m1["n"]), pct(m2["transfer"], m2["n"])),
        ("played all four seasons", pct(m1["years"][4], m1["n"]), pct(m2["years"][4], m2["n"])),
        ("career singles record under .500", pct(m1["losing"], len(m1["career_win"])), pct(m2["losing"], len(m2["career_win"]))),
        ("any honour", pct(m1["honoured"], m1["n"]), pct(m2["honoured"], m2["n"])),
        ("doubles specialists", "—", pct(m2["dbl_spec"], m2["n"])),
    ]
    for label, x, y in rows:
        print(f"| {label} | {x} | {y} |")
    for name, rows_ in (("model 1", a1), ("model 2", a2)):
        home = sum(1 for r in rows_ if ctx.programs[r["college"]].state == "JF")
        west = sum(1 for r in rows_ if ctx.programs[r["college"]].region == "W")
        print(f"\n**Where they sign ({name}):** in Jefferson {pct(home, len(rows_)).strip()}, "
              f"anywhere in the West {pct(west, len(rows_)).strip()}, "
              f"{len({r['college'] for r in rows_})} different colleges")
    gap = collections.defaultdict(list)
    for r in a2:
        gap[r["division"]].append(r["level"]["talent"] - ctx.level[r["college"]])
    print("**Player talent minus the roster's, at signing (model 2):** " + ", ".join(
        f"{d} {st.mean(gap[d]):+.1f}" for d in ("D1", "D2", "D4", "D3") if gap[d]))
    print("\n**How careers end (model 2):** " + ", ".join(
        f"{k.replace('_', ' ')} {pct(v, m2['n']).strip()}" for k, v in m2["status"].most_common()))
    print("**Seasons played (model 2):** " + ", ".join(
        f"{k} → {pct(v, m2['n']).strip()}" for k, v in sorted(m2["years"].items())))
    print("**Career types (model 2):** " + ", ".join(
        f"{k.replace('_', ' ')} {pct(v, m2['n']).strip()}" for k, v in m2["arc"].most_common()))
    print("\n## Singles winning percentage by class year (seasons of 10+ matches)\n")
    print("| | model 1 | model 2 |")
    print("|---|---|---|")
    for i, c in enumerate(("Fr", "So", "Jr", "Sr")):
        print(f"| {c} | {dist(m1['win'].get(i, []))} | {dist(m2['win'].get(i, []))} |")
    print(f"| career | {dist(m1['career_win'])} | {dist(m2['career_win'])} |")
    print("\n## Lineup movement, first starting season to last (+ = moved up)\n")
    for name, m in (("model 1", m1), ("model 2", m2)):
        mv = m["move"]
        up, down = sum(x > 0 for x in mv), sum(x < 0 for x in mv)
        print(f"- {name}: moved up {pct(up, len(mv)).strip()}, same {pct(len(mv) - up - down, len(mv)).strip()}, "
              f"moved DOWN {pct(down, len(mv)).strip()} (mean {st.mean(mv):+.1f} spots)")
    print(f"\n## Honours, per class (model 1 → model 2)\n")
    print("| division | honour | model 1 | model 2 |")
    print("|---|---|---|---|")
    keys = sorted(set(m1["honors"]) | set(m2["honors"]),
                  key=lambda k: (("D1", "D2", "D4", "D3").index(k[0]), k[1]))
    for k in keys:
        print(f"| {k[0]} | {k[1]} | {m1['honors'][k] / n_classes:.1f} | {m2['honors'][k] / n_classes:.1f} |")
    # ---- the owner's four calibration questions ----------------------------------
    print("\n## Departures, kept apart (model 2)\n")
    print("| how the career ended | share | after Fr | after So | after Jr | causes |")
    print("|---|---|---|---|---|---|")
    for kind in ("left_team", "left_college", "injury_ended", "turned_pro"):
        deps = [r["departure"] for r in a2 if r["status"] == kind]
        by = collections.Counter(d["after"] for d in deps)
        why = collections.Counter(d["cause"] for d in deps)
        print(f"| {kind.replace('_', ' ')} | {pct(len(deps), len(a2)).strip()} | {by['Fr']} | "
              f"{by['So']} | {by['Jr']} | "
              + ", ".join(f"{k} {v}" for k, v in why.most_common()) + " |")
    tr = [t for r in a2 for t in r["transfers"]]
    by = collections.Counter(t["after"] for t in tr)
    why = collections.Counter(t["reason"] for t in tr)
    print(f"| transferred (a move, not a departure) | "
          f"{pct(sum(1 for r in a2 if r['transfers']), len(a2)).strip()} | {by['Fr']} | "
          f"{by['So']} | {by['Jr']} | " + ", ".join(f"{k} {v}" for k, v in why.most_common()) + " |")
    d1 = [r for r in a2 if r["division"] == "D1"]
    ac = [r for r in d1 if any(h.startswith("All-Conference") and "doubles" not in h
                               for s in r["seasons"] for h in s["honors"])]
    acd = [r for r in d1 if any("All-Conference (doubles)" in s["honors"] for s in r["seasons"])]
    print(f"\n**D1 All-Conference (model 2):** {len(ac)} of {len(d1)} D1 signees earned it in "
          f"singles ({pct(len(ac), len(d1)).strip()}), {len(acd)} in doubles "
          f"({pct(len(acd), len(d1)).strip()}); All-American while in D1: "
          f"{sum(1 for r in d1 if any('All-American' in h for s in r['seasons'] if s['division'] == 'D1' for h in s['honors']))}.")
    floor = min(ctx.level[p.school] for p in ctx.by_div["D1"]) - v2.REACH["D1"]
    down = [r for r in a2 if r["level"]["talent"] >= floor
            and any(s["division"] != "D1" and s["role"] == "starter" for s in r["seasons"])]
    via = [r for r in down if r["division"] == "D1"]
    aa = lambda rs: sum(1 for r in rs if any(                       # noqa: E731
        "All-American" in h for s in r["seasons"] if s["division"] != "D1"
        for h in s["honors"]))
    low = [r for r in a2 if any(s["division"] != "D1" for s in r["seasons"])]
    print(f"**Lower-division All-Americans (model 2):** {aa(low)} of {len(low)} careers with a "
          f"lower-division season ({pct(aa(low), len(low)).strip()}), "
          f"{aa(low) / n_classes:.1f} a class. **D1-level players playing down:** "
          f"{len(down)} ({len(via)} of them by transferring out of D1); "
          f"{aa(down)} became All-Americans there ({pct(aa(down), len(down)).strip()}).")
    print(f"\n**Integrity (model 2):** deterministic rebuild identical; totals equal the "
          f"season sums; every All-American season is also an All-Conference season in "
          f"the same discipline; every college is a real program; no service academy holds a "
          f"non-American and every D4 signee clears that program's academic gate; "
          f"{clash} of {len(seen)} singles positions claimed twice at one college in "
          f"one season. Doubles lineup seasons: {m2['dbl_starts']} of {m2['seasons']}.")
    print(f"**Cost (model 2):** {st.mean(timing):.1f}s a class (max {max(timing):.1f}s); "
          f"no season simulated, no roster built by the model.")

    # ---- example careers ---------------------------------------------------------
    print("\n## Example careers (model 2)\n")
    want = ["immediate_star", "late_developer", "reserve", "doubles_specialist",
            "stalled_prospect", "transfer_success", "injury_affected", "left_team",
            "left_college", "injury_ended", "steady_contributor", "turned_pro"]
    r = random.Random("examples")
    for arc in want:
        pool = [x for x in a2 if x["arc"] == arc]
        if not pool:
            print(f"*(no `{arc}` career in these classes)*\n")
            continue
        print(story(r.choice(pool), ctx) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gender", default="girls", choices=("girls", "boys", "both"))
    ap.add_argument("--classes", type=int, default=6)
    ap.add_argument("--year", type=int, default=2030)
    ap.add_argument("--salt", default="validate")
    args = ap.parse_args()
    # A throwaway database: the roster builders read per-save settings, and this
    # must never touch a real save.
    tmp = tempfile.mkdtemp(prefix="jf-college-validate-")
    os.environ["TENNIS_DB_PATH"] = os.path.join(tmp, "validate.db")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    for g in (("girls", "boys") if args.gender == "both" else (args.gender,)):
        run(g, args.classes, args.year, args.salt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
