"""6A format study, part 2 — two axes the shape sweeps never varied.

    python3 scripts/jhsaa_6a_format_study2.py [trials]

  A. SHAPE: 1S/4D (today) vs the college D1 rule, 4 singles + 3 doubles CONSOLIDATED
     to one team point (five points, ten on court), vs 3S/4D (the league format
     carried through State, eleven on court).
  B. SCORING: 1S/4D under high-school best-of-3, under 8-game pro sets (the pod
     showcase's scoring), and under best-of-3 with a 10-point match tiebreak in
     place of the third set. Same lineups; only the per-court scoring changes.

Same harness and caveats as `jhsaa_6a_format_study.py`: shipped arrangers and
engine, every 6A program, matched seeds, rosters on an empty override table.
"""
import importlib.util, os, statistics, sys
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, _REPO)
spec = importlib.util.spec_from_file_location("cal", os.path.join(_REPO, "scripts", "jhsaa_1a_format_pilot_calibration.py"))
cal = importlib.util.module_from_spec(spec); spec.loader.exec_module(cal)
jh = cal.jh; simulate_dual = cal.simulate_dual
from engine.dual import DualFormat
from engine.format import MatchFormat, PRESETS

GROUP = "6A"; TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
HS = PRESETS["high_school"]
MTB = MatchFormat(best_of=3, no_ad=True, set_tiebreak=True,
                  final_set_tiebreak=True, final_set_tiebreak_target=10)
F14 = jh.dual_format("state", None)
# (label, dual format, arranger, singles scoring, doubles scoring)
EXPERIMENTS = {
    "A. shape": [
        ("1S/4D",       F14, lambda r: jh._arrange_state(r[:9], {}), HS, HS),
        ("4S+3D->1pt",  DualFormat(n_singles=4, n_doubles=3, doubles_team_point=True),
                        lambda r: jh._arrange_wide(r[:10], 4, {}), HS, HS),
        ("3S/4D",       DualFormat(n_singles=3, n_doubles=4, doubles_team_point=False),
                        lambda r: jh._arrange_wide(r[:11], 3, {}), HS, HS),
    ],
    "B. scoring (1S/4D)": [
        ("best-of-3",   F14, lambda r: jh._arrange_state(r[:9], {}), HS, HS),
        ("pro set 8",   F14, lambda r: jh._arrange_state(r[:9], {}), PRESETS["pro_set_8"], PRESETS["pro_set_8"]),
        ("10-pt MTB",   F14, lambda r: jh._arrange_state(r[:9], {}), MTB, MTB),
    ],
}

def run():
    programs = []
    for g in jh.GENDERS:
        for s in jh.load_schools(g):
            if s.group == GROUP:
                programs.append((g, s, cal.order_program(s)))
    print(f"{GROUP}: {len(programs)} programs, {TRIALS} trials")
    for exp, rows in EXPERIMENTS.items():
        print(f"\n=== {exp} ===")
        for g in jh.GENDERS:
            pool = [(s, r) for gg, s, r in programs if gg == g]
            pool.sort(key=lambda sr: -statistics.mean(p.current_overall() for p in sr[1][:9]))
            half = len(pool) // 2
            sets = {"even": [(pool[i], pool[i + 1]) for i in range(0, len(pool) - 1, 2)],
                    "mismatched": list(zip(pool[:half], reversed(pool[half:])))}
            for label, pairs in sets.items():
                st = {k: dict(fav=0, one=0, margin=[], same=0, dbl_fav=0) for k, *_ in rows}
                for (sa, ra), (sb, rb) in pairs:
                    arr = {k: (f(ra), f(rb)) for k, _fmt, f, *_ in rows}
                    fav_a = statistics.mean(p.current_overall() for p in ra[:9]) >= \
                            statistics.mean(p.current_overall() for p in rb[:9])
                    for t in range(TRIALS):
                        seed = cal._pair_seed(sa.name, sb.name, t); base = None
                        for k, fmt, _f, sf, df in rows:
                            res = simulate_dual(cal.make_team(sa.name, arr[k][0], fmt),
                                                cal.make_team(sb.name, arr[k][1], fmt),
                                                seed=seed, play_all=True, fidelity=jh.FIDELITY,
                                                dual_fmt=fmt, singles_fmt=sf, doubles_fmt=df)
                            wa = res.winner == 0; m = abs(res.home_points - res.away_points)
                            s = st[k]; s["fav"] += (wa == fav_a); s["one"] += (m <= 1); s["margin"].append(m)
                            if base is None: base = wa
                            s["same"] += (wa == base)
                n = len(pairs) * TRIALS
                print(f"\n{g} — {label}: {len(pairs)} pairings x {TRIALS} = {n} duals")
                print(f"  {'format':12}{'fav wins':>10}{'1-pt':>8}{'mean margin':>13}{'same winner as first':>22}")
                for k, fmt, *_ in rows:
                    s = st[k]
                    print(f"  {k:12}{s['fav']/n:>10.1%}{s['one']/n:>8.1%}{statistics.mean(s['margin']):>8.2f}/{fmt.total_points:<4}{s['same']/n:>22.1%}")
run()
