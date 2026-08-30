#!/usr/bin/env python3
"""Measure the development model's REALISED behaviour off research exports.

The development model is easy to reason about wrongly from its constants: the
JHSAA side reads as a wide, overlapping trajectory model (`jhsaa.DEV_ARRIVAL`
through `DEV_SHAPES`) and the college side reads as the interest-rate model
from the owner's baseball write-up (`development.TIERS`). What each one
actually PRODUCES on a live save is a different question, and the only honest
way to answer it is over consecutive seasons of real players.

    python3 scripts/dev_model_baseline.py <export-root> [--years 2057 2058 2059]

`<export-root>` is a directory holding `<year>/<gender>/players.csv` — i.e. one
or more research-export zips unpacked side by side. Two or more CONSECUTIVE
years are required for the career-arc and ladder-mobility sections; a single
year still yields the cross-sectional ones.

`players.csv` carries `player_id` (stable across seasons — a JHSAA pid keys on
school/gender/entry year/seat), `grade`, `current_grade` and `potential_grade`,
which is everything the model's three questions need:

  * how much of a player's ceiling is visible at each grade (the access lens),
  * how a real career moves across seasons (the trajectory),
  * and who that leaves on court (the consequence).

Writes nothing; prints a report. See docs/REPORT-development-model-baseline.md
for the run this was written to produce and what it means.
"""
from __future__ import annotations

import argparse
import collections
import csv
import itertools
import os
import statistics as st

GRADES = ("9", "10", "11", "12")
#: The varsity regular-season format dresses eleven (jhsaa.lineup_need("regular")
#: on the 3S/4D league format). Imported lazily so the script runs against an
#: export without the app importable; falls back to the literal.
try:                                                # pragma: no cover - convenience
    from app.jhsaa import lineup_need
    LINEUP = lineup_need("regular")
except Exception:                                   # pragma: no cover
    LINEUP = 11


def load(root: str, year: int, gender: str) -> list[dict]:
    path = os.path.join(root, str(year), gender, "players.csv")
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def ladder(rows: list[dict]) -> dict[str, int]:
    """Each player's 0-indexed rank on their own program, by current ability.

    Ability order, not `jhsaa.ladder_score` — the export carries no per-player
    win/loss, and the ladder is ability-SEEDED with results worth at most
    ±LADDER_SWING, so the seat distribution this measures is the ladder's to
    within that swing. Stated rather than silently approximated.
    """
    by = collections.defaultdict(list)
    for r in rows:
        by[r["program_id"]].append(r)
    out = {}
    for rs in by.values():
        rs.sort(key=lambda r: -float(r["current_grade"]))
        for i, r in enumerate(rs):
            out[r["player_id"]] = i
    return out


def pct(v: list[float], q: float) -> float:
    return sorted(v)[min(len(v) - 1, int(q * len(v)))]


def report(root: str, years: list[int], gender: str) -> None:
    D = {y: load(root, y, gender) for y in years}
    R = {y: ladder(D[y]) for y in years}
    last = years[-1]
    idx = {y: {r["player_id"]: r for r in D[y]} for y in years}

    print(f"\n{'=' * 72}\n{gender.upper()}   seasons {years[0]}-{last}\n{'=' * 72}")
    print("rows/season: " + ", ".join(f"{y} {len(D[y])}" for y in years))

    # --- 1. the access lens: how much ceiling is visible, by grade ------------
    print(f"\n[1] ACCESS — current/potential by grade ({last})")
    print("    grade      n   mean    p10    p50    p90   mean cur  mean ceil")
    by = collections.defaultdict(list)
    for r in D[last]:
        c, p = float(r["current_grade"]), float(r["potential_grade"])
        if p > 0:
            by[r["grade"]].append((c / p, c, p))
    med = {}
    for g in GRADES:
        v = [x[0] for x in by[g]]
        med[g] = pct(v, 0.50)
        print(f"    {g:>5} {len(v):6d} {st.mean(v):6.3f} {pct(v,.10):6.3f} "
              f"{med[g]:6.3f} {pct(v,.90):6.3f} {st.mean([x[1] for x in by[g]]):9.1f} "
              f"{st.mean([x[2] for x in by[g]]):10.1f}")
    fr = [x[0] for x in by["9"]]
    for g in ("11", "12"):
        share = sum(1 for x in fr if x >= med[g]) / len(fr)
        print(f"    freshmen at or above the grade-{g} MEDIAN access: {share:6.1%}")

    # --- 2. cohort confound: ceiling by entry year ---------------------------
    print("\n[2] COHORT — mean ceiling by ENTRY year (talent-compression era check)")
    ent = collections.defaultdict(list)
    for y in years:
        for r in D[y]:
            ent[y - (int(r["grade"]) - 9)].append(float(r["potential_grade"]))
    for e in sorted(ent):
        print(f"    entry {e}: n={len(ent[e]):6d}  mean ceiling {st.mean(ent[e]):5.1f}")

    # --- 3. the trajectory: same player, across seasons ----------------------
    if len(years) >= 2:
        span = years[-1] - years[0]
        common = set(idx[years[0]]) & set(idx[last])
        print(f"\n[3] TRAJECTORY — {span}-year current-grade gain, same player (n={len(common)})")
        gains = collections.defaultdict(list)
        for pid in common:
            g0 = idx[years[0]][pid]["grade"]
            gains[g0].append(float(idx[last][pid]["current_grade"])
                             - float(idx[years[0]][pid]["current_grade"]))
        for g in GRADES:
            if gains[g]:
                v = gains[g]
                print(f"    entered span in grade {g} (n={len(v):5d}): mean {st.mean(v):+5.1f}  "
                      f"p10 {pct(v,.10):+5.1f}  p50 {pct(v,.50):+5.1f}  p90 {pct(v,.90):+5.1f}")
        dp = [float(idx[last][p]["potential_grade"]) - float(idx[years[0]][p]["potential_grade"])
              for p in common]
        moved = [x for x in dp if x]
        print(f"    CEILING change over the same span: mean {st.mean(dp):+.2f}, "
              f"moved at all {len(moved)/len(dp):.1%}  (a fixed ceiling is the model's design)")

    # --- 4. ladder mobility --------------------------------------------------
    if len(years) >= 2:
        swaps = tot = 0
        for y0, y1 in zip(years, years[1:]):
            here = collections.defaultdict(list)
            alive = set(idx[y1])
            for r in D[y0]:
                if r["player_id"] in alive:
                    here[r["program_id"]].append(r["player_id"])
            for ps in here.values():
                for a, b in itertools.combinations(ps, 2):
                    tot += 1
                    if (R[y0][a] - R[y0][b]) * (R[y1][a] - R[y1][b]) < 0:
                        swaps += 1
        print(f"\n[4] MOBILITY — returning-teammate pairs that swap ladder order "
              f"year over year: {swaps/tot:.1%} (n={tot})")

    # --- 5. the consequence: who is on court --------------------------------
    print(f"\n[5] SEATS — share of each grade in the {LINEUP}-player lineup, and of No. 1 seats ({last})")
    start = collections.Counter(); tot_g = collections.Counter(); no1 = collections.Counter()
    for r in D[last]:
        g = r["grade"]; i = R[last][r["player_id"]]
        tot_g[g] += 1
        if i < LINEUP:
            start[g] += 1
        if i == 0:
            no1[g] += 1
    for g in GRADES:
        print(f"    grade {g}: in the lineup {start[g]/tot_g[g]:6.1%} of the grade   |   "
              f"holds {no1[g]/sum(no1.values()):6.1%} of No. 1 seats")

    # --- 6. the counterfactual: what the ceiling would seat ------------------
    by = collections.defaultdict(list)
    for r in D[last]:
        by[r["program_id"]].append(r)
    cur9 = pot9 = tot9 = 0
    for rs in by.values():
        cur9 += sum(1 for r in sorted(rs, key=lambda r: -float(r["current_grade"]))[:LINEUP]
                    if r["grade"] == "9")
        pot9 += sum(1 for r in sorted(rs, key=lambda r: -float(r["potential_grade"]))[:LINEUP]
                    if r["grade"] == "9")
        tot9 += sum(1 for r in rs if r["grade"] == "9")
    print(f"\n[6] HIDDEN — freshmen the lineup holds by CURRENT {cur9} ({cur9/tot9:.1%} of freshmen) "
          f"vs by CEILING {pot9} ({pot9/tot9:.1%}) — {pot9/max(cur9,1):.1f}x")

    # --- 7. never plays ------------------------------------------------------
    if len(years) >= 2:
        seen = collections.defaultdict(list)
        for y in years:
            for r in D[y]:
                seen[r["player_id"]].append(R[y][r["player_id"]])
        full = [v for v in seen.values() if len(v) == len(years)]
        never = sum(1 for v in full if all(i >= LINEUP for i in v))
        print(f"\n[7] UNPLAYED — of {len(full)} players present all {len(years)} seasons, "
              f"{never/len(full):.1%} never reached the lineup in any of them")

    # --- 8. spread: is the ceiling or the lens doing the sorting? ------------
    cs, ps = [], []
    for rs in by.values():
        if len(rs) >= 8:
            cs.append(st.pstdev([float(r["current_grade"]) for r in rs]))
            ps.append(st.pstdev([float(r["potential_grade"]) for r in rs]))
    print(f"\n[8] SPREAD — mean within-program sd: current {st.mean(cs):.2f}, "
          f"ceiling {st.mean(ps):.2f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="directory holding <year>/<gender>/players.csv")
    ap.add_argument("--years", type=int, nargs="+", default=None,
                    help="consecutive seasons to read (default: every year dir found)")
    ap.add_argument("--genders", nargs="+", default=["girls", "boys"])
    args = ap.parse_args()
    years = args.years or sorted(int(d) for d in os.listdir(args.root) if d.isdigit())
    for gender in args.genders:
        report(args.root, years, gender)


if __name__ == "__main__":
    main()
