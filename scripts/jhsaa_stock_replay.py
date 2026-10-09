"""Matched-player replay for the JHSAA attribute-development model
(`app/jhsaa_develop.py`, owner spec 2026-10).

    python3 scripts/jhsaa_stock_replay.py --db /tmp/scratch.db [--schools 8] [--seasons 3]

The SAME generated players — natural targets and the scalar baseline from a
pre-era build, the pinned latent profile from an era-on build — are replayed
under the addendum's staff shapes with everything else held fixed (exposure
1.0, bond 1.0, no transfer), so every difference between rows is the staff.
Then a remove-one-coach ablation on the complementary staff, and a CORRIDOR
table: the top-decile ethic × top-decile stock players over five seasons under
the complementary elite staff, which is the rare career the design must be able
to produce. Read-only on the file you point it at; a fresh scratch path is fine
(no archive is needed — the staffs are synthetic).
"""
from __future__ import annotations

import argparse
import copy
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GRADES = ("tactics", "singles", "doubles", "development", "talent_id",
          "adaptability", "builder", "feeder", "clutch", "changeover")


def coach(cid, slot, profile, q):
    from app.jhsaa_coaches import teaching_portfolio
    return (cid, slot, {g: q for g in GRADES}, teaching_portfolio(cid, profile))


def staffs() -> dict:
    return {
        "weak": [coach("w-h", "head", "generalist", 0.25),
                 coach("w-a1", "asst1", "generalist", 0.25)],
        "average": [coach("av-h", "head", "generalist", 0.5),
                    coach("av-a1", "asst1", "generalist", 0.5),
                    coach("av-a2", "asst2", "generalist", 0.5)],
        "strong head only": [coach("sh-h", "head", "practice", 0.95),
                             coach("sh-a1", "asst1", "generalist", 0.5),
                             coach("sh-a2", "asst2", "generalist", 0.5)],
        "elite assistant only": [coach("ea-h", "head", "generalist", 0.5),
                                 coach("ea-a1", "asst1", "doubles", 0.95),
                                 coach("ea-a2", "asst2", "generalist", 0.5)],
        "four overlapping elite": [coach("e-h", "head", "singles", 0.95)]
        + [coach(f"e-a{i}", f"asst{i}", "singles", 0.95) for i in (1, 2, 3)],
        "four complementary elite": [coach("c-h", "head", "practice", 0.95),
                                     coach("c-a1", "asst1", "singles", 0.95),
                                     coach("c-a2", "asst2", "doubles", 0.95),
                                     coach("c-a3", "asst3", "tactician", 0.95)],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--gender", default="girls")
    ap.add_argument("--schools", type=int, default=8)
    ap.add_argument("--seasons", type=int, default=3)
    ap.add_argument("--salt", default="replay")
    args = ap.parse_args()
    os.environ["TENNIS_DB_PATH"] = args.db
    os.environ.setdefault("JHSAA_LAB_DEV_OVERRIDE", "1")
    from app import jhsaa as jh, jhsaa_develop as jd
    from app.player_attributes import OVERALL_WEIGHTS, _WEIGHT_TOTAL
    jh.sixteen_state_era = lambda: 10 ** 6
    jh.circuit_era = lambda: 10 ** 6
    jh.nonpublic_era = lambda: 10 ** 6
    schools = jh.load_schools(args.gender)[:args.schools]
    year = 2030
    jh.stock_era = lambda: 10 ** 6
    pre = {p.pid: (sc, p) for sc in schools for p in jh.build_roster(sc, year, args.salt)
           if p.grade == 12}
    jh.stock_era = lambda: 0
    post = {p.pid: p for sc in schools for p in jh.build_roster(sc, year, args.salt)
            if p.grade == 12}
    S = staffs()

    def replay(a, sc, prof, staff, n):
        ceiling = sum(OVERALL_WEIGHTS[x] * v for x, v in a.potential.items()) / _WEIGHT_TOTAL
        start, _peak, _ = jh._career_plan(sc.key, a.entry_year, a.jhsaa["seat"], args.salt,
                                         ceiling, a.jhsaa.get("start", 0.0))
        qq = copy.deepcopy(a)
        res = jd.apply_stock(qq, a.pid, args.salt, prof, dict(a.current), start / ceiling,
                             [(year - n + i, 1.0, staff, 1.0) for i in range(n)])
        return res, qq

    def line(name, g):
        g = sorted(g)
        print(f"  {name:28s} n={len(g):3d} mean {st.mean(g):5.2f} med {st.median(g):5.2f}"
              f" p90 {g[int(len(g) * .9)]:5.2f} max {g[-1]:5.2f}"
              f" zero {sum(1 for x in g if x < 0.05) / len(g):.2f}")

    ext = [post[pid].jhsaa["stock_pin"]["extra_ovr"] for pid in pre]
    eth = [post[pid].jhsaa["stock_pin"]["ethic"] for pid in pre]
    print(f"{len(pre)} seniors · career coached-OVR budget mean {st.mean(ext):.1f}"
          f" p90 {sorted(ext)[int(len(ext) * .9)]:.1f} max {max(ext):.1f}"
          f" · work ethic mean {st.mean(eth):.2f}")
    print(f"== coached OVR over {args.seasons} seasons, by staff (everything else fixed)")
    for name, staff in S.items():
        line(name, [replay(a, sc, post[pid].jhsaa["stock_pin"], staff, args.seasons)[0]["coached_ovr"]
                    for pid, (sc, a) in pre.items()])
    print("== remove-one-coach ablation on the complementary elite staff")
    full = S["four complementary elite"]
    base = {pid: replay(a, sc, post[pid].jhsaa["stock_pin"], full, args.seasons)[0]["coached_ovr"]
            for pid, (sc, a) in pre.items()}
    for drop in full:
        staff = [c for c in full if c[0] != drop[0]]
        got = {pid: replay(a, sc, post[pid].jhsaa["stock_pin"], staff, args.seasons)[0]["coached_ovr"]
               for pid, (sc, a) in pre.items()}
        line(f"without {drop[0]} ({drop[2] and drop[1]})",
             [base[pid] - got[pid] for pid in pre])
    print("== the corridor: top-quartile ethic AND top-quartile budget, five seasons, complementary elite")
    cut_e = sorted(eth)[int(len(eth) * .75)]
    cut_x = sorted(ext)[int(len(ext) * .75)]
    rows = []
    for pid, (sc, a) in pre.items():
        prof = post[pid].jhsaa["stock_pin"]
        if prof["ethic"] < cut_e or prof["extra_ovr"] < cut_x:
            continue
        res, qq = replay(a, sc, prof, full, 5)
        rows.append((a.name, a.current_overall(), qq.current_overall(), res["coached_ovr"],
                     round(prof["extra_ovr"], 1), prof["ethic"]))
    for r in rows:
        print(f"  {r[0]:24s} natural-path OVR {r[1]:3d} → with staff {r[2]:3d}"
              f"  (+{r[3]:.1f} coached of budget {r[4]}, ethic {r[5]})")
    if not rows:
        print("  (no player cleared both deciles in this sample — widen --schools)")


if __name__ == "__main__":
    main()
