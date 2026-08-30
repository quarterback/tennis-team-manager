#!/usr/bin/env python3
"""A/B the ACCESS MODEL over real rosters, real ceilings and real grades.

    python3 scripts/dev_model_access_experiment.py <export-root> [--years ...]

`<export-root>` is the same directory `scripts/dev_model_baseline.py` reads —
`<year>/<gender>/players.csv` from two or more consecutive research exports.

The whole point is that NOTHING varies except the access model. Every run uses
the same programs, the same people, the same fixed ceilings and the same grades
straight out of the export; only the function turning (player, grade) into
current ability is swapped. So a metric that moves is attributable to the access
model and to nothing else — no talent-generator change, no cohort drift, no
roster-composition difference.

`M0` re-implements the shipped `jhsaa._dev_maturity` and is the control: it
reproduces the measured baseline to within a few tenths of a point (see
docs/REPORT-development-model-baseline.md §3), which is what licenses reading
the other rows as real differences rather than harness artefacts. ‼️ It is a
RE-IMPLEMENTATION, not an import — the shipped function takes a school key and a
salt this harness does not have. If `_dev_maturity`'s constants move, move M0's
with them or the control silently stops being the control.

`CHAOS` is not a proposal. It redraws access freely every year, which violates
both the no-reroll rule and monotonicity, and exists only to put a hard upper
bound on what ANY fixed-ceiling access model can do to a ladder.

Metrics — see the report for why the obvious one is the wrong one:
  * all-pair swaps        every returning-teammate pair. Dominated by pairs 15+
                          OVR apart that will never cross, so it mostly measures
                          roster size. Reported for continuity with the baseline.
  * near-pair swaps       pairs within 5 OVR — the ones that COULD cross.
  * top-11 swaps          pairs both in the varsity lineup.
  * No. 1 retention       of programs whose No. 1 returns, the share that keep
                          them. The cleanest single read of the seniority lock.
  * bench -> lineup       returning players outside the lineup who climb into it.
                          The guardrail on the playing-time odometer: a positive
                          feedback loop from playing shows up here FIRST, and
                          every other metric can look fine while it falls.
"""
from __future__ import annotations

import argparse
import collections
import csv
import itertools
import os
import random
import statistics as st

LINEUP = 11                      # jhsaa.lineup_need("regular") — the 3S/4D card
NEAR = 5.0                       # OVR gap under which a pair counts as "near"

#: (probability, exponent) — jhsaa.DEV_SHAPES, steady / early / late / spike.
SHAPES = ((0.38, 1.0), (0.36, 0.55), (0.21, 1.75), (0.05, 3.0))


def _pick_exp(r: random.Random) -> float:
    roll = r.random()
    for p, e in SHAPES:
        if roll < p:
            return e
        roll -= p
    return SHAPES[-1][1]


def _walk(m9: float, m12: float, exp: float, grade: int,
          min_step: float = 0.045, cap: float = 0.98) -> float:
    """jhsaa._dev_maturity's curve walk: arrival to `grade`, per-year floor applied
    along the way."""
    m = m9
    for g in range(10, grade + 1):
        m = max(m9 + (m12 - m9) * (((g - 9) / 3.0) ** exp), m + min_step)
    return min(cap, m)


# --- access models ---------------------------------------------------------
# Each takes (pid, grade, ceiling) and returns CURRENT ability.

def M0(pid: str, grade: int, C: float) -> float:
    """CONTROL — the shipped model. DEV_ARRIVAL (.40,.64) / DEV_READY (.66,.82) at
    24% / DEV_FINISH (.76,.94) / DEV_MIN_RISE .16 / DEV_MIN_STEP .045."""
    r = random.Random(f"m0|{pid}")
    m9 = r.uniform(.66, .82) if r.random() < .24 else r.uniform(.40, .64)
    m12 = max(r.uniform(.76, .94), m9 + .16)
    return C * _walk(m9, m12, _pick_exp(r), grade)


def M1(pid: str, grade: int, C: float) -> float:
    """Widen the FINISH band only. The shipped finish (.76-.94) is narrow while
    arrival is wide, so schedules CONVERGE: by senior year everyone sits near .87
    of their ceiling, the senior ladder is ceiling-ordered, and the ceiling is
    fixed at generation. This is the single highest-leverage change."""
    r = random.Random(f"m1|{pid}")
    m9 = r.uniform(.66, .82) if r.random() < .24 else r.uniform(.40, .64)
    m12 = max(r.uniform(.60, .99), m9 + .04)
    return C * _walk(m9, m12, _pick_exp(r), grade, min_step=0.0)


def M2(pid: str, grade: int, C: float) -> float:
    """Widen finish AND arrival."""
    r = random.Random(f"m2|{pid}")
    m9 = r.uniform(.62, .90) if r.random() < .30 else r.uniform(.34, .70)
    m12 = max(r.uniform(.60, .99), m9 + .02)
    return C * _walk(m9, m12, _pick_exp(r), grade, min_step=0.0)


def M3(pid: str, grade: int, C: float) -> float:
    """M2 plus explicit PEAK TIMING — the schedule may top out before senior year
    and hold, so a chronological final season need not be a player's best."""
    r = random.Random(f"m3|{pid}")
    m9 = r.uniform(.62, .90) if r.random() < .30 else r.uniform(.34, .70)
    mpk = max(r.uniform(.60, .99), m9 + .02)
    peak = r.choices((10, 11, 12), weights=(.15, .25, .60))[0]
    exp = _pick_exp(r)
    if grade >= peak:
        return C * min(.98, mpk)
    t = (grade - 9) / max(1e-9, (peak - 9))
    return C * min(.98, m9 + (mpk - m9) * (t ** exp))


def OPTA(pid: str, grade: int, C: float, rho: float = 0.45) -> float:
    """ONE parameterisation of proposal Option A — illustrative, not definitive.
    Start and career PEAK are drawn with a controlled correlation instead of both
    being proportional to a single fixed ceiling, which is the structural thing
    Option A can do that Option B cannot."""
    r = random.Random(f"a|{pid}")
    peak = C * r.uniform(.72, .99)
    start = min(peak, max(12.0, rho * peak * r.uniform(.45, .98)
                          + (1 - rho) * r.gauss(34, 9)))
    pk = r.choices((10, 11, 12), weights=(.15, .25, .60))[0]
    exp = _pick_exp(r)
    if grade >= pk:
        return peak
    return start + (peak - start) * (((grade - 9) / max(1e-9, pk - 9)) ** exp)


def CHAOS(pid: str, grade: int, C: float) -> float:
    """NOT A PROPOSAL — access redrawn freely each year, violating both no-reroll
    and monotonicity. The hard upper bound on what any fixed-ceiling access model
    can do to a ladder."""
    return C * random.Random(f"ch|{pid}|{grade}").uniform(.34, .98)


MODELS = {"M0 shipped": M0, "M1 wide finish": M1, "M2 wide both": M2,
          "M3 peak timing": M3, "OPT-A decoupled": OPTA, "CHAOS (bound)": CHAOS}

#: Share of a season's SCHEDULED gain a player FAILS to realise, by what they did
#: the previous season. Proposal §6.4 Interpretation 1 — exposure can only fall
#: short of the generated schedule, never exceed it.
SHORTFALL = {"varsity": 0.00, "jv": 0.35, "none": 0.70}


def load(root: str, year: int, gender: str) -> list[dict]:
    with open(os.path.join(root, str(year), gender, "players.csv"), newline="") as f:
        return list(csv.DictReader(f))


def _rank(rows: list[dict], cur: dict, year: int) -> tuple[dict, dict, dict]:
    """(rank by player, No. 1 by program, roster membership by program)."""
    by = collections.defaultdict(list)
    for r in rows:
        by[r["program_id"]].append(r)
    rank, top1, roster = {}, {}, {}
    for prog, rs in by.items():
        rs.sort(key=lambda r: -cur[(year, r["player_id"])])
        top1[prog] = rs[0]["player_id"]
        roster[prog] = {r["player_id"] for r in rs}
        for i, r in enumerate(rs):
            rank[r["player_id"]] = i
    return rank, top1, roster


def metrics(D: dict, years: list[int], cur: dict, rank: dict, top1: dict,
            roster: dict) -> dict:
    sw = tot = swn = totn = swt = tott = promo = cand = 0
    for y0, y1 in zip(years, years[1:]):
        alive = {r["player_id"] for r in D[y1]}
        here = collections.defaultdict(list)
        for r in D[y0]:
            if r["player_id"] in alive:
                here[r["program_id"]].append(r["player_id"])
                if rank[y0][r["player_id"]] >= LINEUP:
                    cand += 1
                    promo += rank[y1][r["player_id"]] < LINEUP
        for ps in here.values():
            for a, b in itertools.combinations(ps, 2):
                flip = ((rank[y0][a] - rank[y0][b]) * (rank[y1][a] - rank[y1][b])) < 0
                tot += 1; sw += flip
                if abs(cur[(y0, a)] - cur[(y0, b)]) <= NEAR:
                    totn += 1; swn += flip
                if rank[y0][a] < LINEUP and rank[y0][b] < LINEUP:
                    tott += 1; swt += flip
    y0, y1 = years[-2], years[-1]
    # ‼️ SAME PROGRAM. A global "is this pid anywhere next season" test counts a
    # player who TRANSFERRED as a returning No. 1, and then scores their old
    # school's new No. 1 as a retention failure — which depresses the headline
    # metric with cases the metric is not defined over.
    pairs = [(p, top1[y1].get(prog)) for prog, p in top1[y0].items()
             if p in roster[y1].get(prog, ())]
    held = sum(1 for p, q in pairs if p == q)
    no1 = collections.Counter()
    for r in D[y1]:
        if rank[y1][r["player_id"]] == 0:
            no1[r["grade"]] += 1
    n1 = sum(no1.values())
    return {"allpair": sw / tot, "near": swn / max(totn, 1), "top11": swt / max(tott, 1),
            "held": held / max(len(pairs), 1), "promo": promo / max(cand, 1),
            "fr1": no1["9"] / n1, "sr1": no1["12"] / n1,
            "ovr": st.mean([cur[(y1, r["player_id"])] for r in D[y1]])}


HDR = (f"{'model':17s} {'allpair':>8}{'near5':>8}{'top11':>8}{'No1 held':>10}"
       f"{'bench>':>8}{'Fr No.1':>9}{'Sr No.1':>9}{'meanOVR':>9}")


def row(name: str, m: dict) -> str:
    return (f"{name:17s} {m['allpair']:8.1%}{m['near']:8.1%}{m['top11']:8.1%}"
            f"{m['held']:10.1%}{m['promo']:8.1%}{m['fr1']:9.1%}{m['sr1']:9.1%}"
            f"{m['ovr']:9.1f}")


def run(root: str, years: list[int], gender: str) -> None:
    D = {y: load(root, y, gender) for y in years}
    ceil: dict[str, float] = {}
    for y in years:
        for r in D[y]:
            ceil.setdefault(r["player_id"], float(r["potential_grade"]))

    print(f"\n===== {gender}   seasons {years[0]}-{years[-1]}\n{HDR}")
    for name, fn in MODELS.items():
        cur, rank, top1, roster = {}, {}, {}, {}
        for y in years:
            for r in D[y]:
                pid = r["player_id"]
                cur[(y, pid)] = fn(pid, int(r["grade"]), ceil[pid])
            rank[y], top1[y], roster[y] = _rank(D[y], cur, y)
        print(row(name, metrics(D, years, cur, rank, top1, roster)))

    # --- the odometer, on top of M2 -------------------------------------
    # Exposure is resolved FORWARD: last season's rank decides this season's
    # exposure, which decides how much of this season's scheduled gain lands.
    print("\n  playing-time odometer, over M2 "
          f"(bench realises {1-SHORTFALL['none']:.0%} of the scheduled gain, "
          f"JV {1-SHORTFALL['jv']:.0%}, varsity {1-SHORTFALL['varsity']:.0%}):")
    print(f"  {HDR}")
    for label, on in (("M2 no odometer", False), ("M2 + odometer", True)):
        cur, rank, top1, roster, prev = {}, {}, {}, {}, {}
        for y in years:
            for r in D[y]:
                pid, g = r["player_id"], int(r["grade"])
                C = ceil[pid]
                target = M2(pid, g, C)
                base = M2(pid, max(9, g - 1), C)
                short = SHORTFALL[prev.get(pid, "none")] if on else 0.0
                cur[(y, pid)] = target - (target - base) * short
            rank[y], top1[y], roster[y] = _rank(D[y], cur, y)
            prev = {p: ("varsity" if i < LINEUP else "jv") for p, i in rank[y].items()}
        print("  " + row(label, metrics(D, years, cur, rank, top1, roster)))


# --- Option C (the CHOSEN model, proposal §22) -----------------------------
# Starting ability and career PEAK drawn separately, four yearly development
# capacities with no privileged senior year, clamped at peak (§23 allows a soft
# overflow past it). This is a PROJECTION over four years from each freshman in
# the newest season, not an access model, so it is reported as its own census
# rather than as a row in the table above.
#
# ‼️ START IS A FRACTION OF PEAK, DRAWN GRADE-FREE — never a blend of a
# peak-anchored term and an independent population draw clamped at peak. That
# clamp fires constantly for low-peak players, silently sets start = peak, and
# manufactured a 26% "already finished" share and 53% of players with no growth
# year in a first parameterisation. Nothing is clamped at generation here.

#: (name, peak multiplier band, start-fraction band, big-year probability,
#: big-year band, ordinary-year band). V1 is the closest fit to the owner's
#: growth-year spec; V2/V3 are progressively hotter.
CAREER_CFGS = {
    "V1": ((.85, 1.10), (.40, .95), .30, (7, 15), (0, 3.5)),
    "V2": ((.90, 1.15), (.35, .92), .34, (8, 17), (0, 4.0)),
    "V3": ((.95, 1.20), (.32, .90), .38, (8, 18), (1, 5.0)),
}


def career(pid: str, C: float, cfg, overflow: float = 0.0):
    """(start, peak, [ability at grades 9-12]) for one player.

    `overflow` is the share of a gain that still lands once past career peak
    (proposal §23): 0.0 is a hard clamp, 1.0 no cap at all. The senior TAPER is
    produced by this clamp — capacity is drawn identically in all four years and
    late years grow less only because most players have already reached peak —
    so raising it toward 1.0 flattens the taper and reintroduces senior leaps.
    """
    k, frac, big_p, big, small = cfg
    r = random.Random(f"optc|{pid}")
    peak = C * r.uniform(*k)
    v = peak * r.uniform(*frac)
    caps = [r.uniform(*big) if r.random() < big_p else r.uniform(*small)
            for _ in range(4)]
    path = [v]
    for i in range(3):
        gain = caps[i]
        if v >= peak:
            gain *= overflow
        elif v + gain > peak:
            gain = (peak - v) + (v + gain - peak) * overflow
        v += gain
        path.append(v)
    return path[0], peak, path


def career_census(rows: list[dict], ceil: dict, overflow: float = 0.0) -> None:
    """Project every freshman's four-year career and report the SHAPE of the
    resulting careers — which is what this model controls. Ladder churn is
    deliberately not reported here (proposal §22.7: roster order is handled
    dynamically elsewhere and is not a target for the development model)."""
    fresh = [r["player_id"] for r in rows if r["grade"] == "9"]
    if not fresh:
        return
    print(f"\n  OPTION C career census — {len(fresh)} freshmen projected "
          f"(overflow past peak {overflow:.2f})")
    print(f"    {'cfg':4s}{'9>10':>7}{'10>11':>7}{'11>12':>7}{'none':>7}"
          f"{'ready':>7}{'stag':>7}{'leap':>7}   mean ability 9/10/11/12")
    for name, cfg in CAREER_CFGS.items():
        big = collections.Counter()
        shape = collections.Counter()
        lvl = collections.defaultdict(list)
        for pid in fresh:
            start, peak, path = career(pid, ceil[pid], cfg, overflow)
            gains = [path[i + 1] - path[i] for i in range(3)]
            big[gains.index(max(gains)) + 1 if max(gains) >= 3 else 0] += 1
            for i, v in enumerate(path):
                lvl[9 + i].append(v)
            total = path[-1] - path[0]
            if start >= .90 * peak:
                shape["ready"] += 1
            elif total < 3:
                shape["stagnant"] += 1
            elif max(gains) >= 8:
                shape["leap"] += 1
        n = len(fresh)
        means = "/".join(f"{st.mean(lvl[g]):.1f}" for g in (9, 10, 11, 12))
        print(f"    {name:4s}{big[1]/n:7.0%}{big[2]/n:7.0%}{big[3]/n:7.0%}"
              f"{big[0]/n:7.0%}{shape['ready']/n:7.0%}{shape['stagnant']/n:7.0%}"
              f"{shape['leap']/n:7.0%}   {means}")
    print("    owner spec §6 growth-year target: 30% / 27% / 28% / 15% none")
    print("    ‼️ §22.6a CORRECTS that target — breakouts are sophomore and")
    print("       junior; the senior year is incremental, so a LOW 11>12 share")
    print("       is the model behaving correctly, not under-weighting.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--years", type=int, nargs="+", default=None)
    ap.add_argument("--genders", nargs="+", default=["girls", "boys"])
    args = ap.parse_args()
    years = args.years or sorted(int(d) for d in os.listdir(args.root) if d.isdigit())
    for gender in args.genders:
        run(args.root, years, gender)
        rows = load(args.root, years[-1], gender)
        ceil = {r["player_id"]: float(r["potential_grade"]) for r in rows}
        career_census(rows, ceil)


if __name__ == "__main__":
    main()
