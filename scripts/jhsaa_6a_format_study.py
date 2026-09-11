"""6A format counterfactual — the 1A pilot harness pointed at 6A, four shapes.

    python3 scripts/jhsaa_6a_format_study.py [trials]

Calls the SHIPPED arrangers and engine (`jhsaa_1a_format_pilot_calibration` does the
roster build and seeding; this only adds 3S/2D and 4S/5D beside 1S/4D and 2S/3D) on
every 6A program, statewide adjacent-strength and top-vs-bottom pairings, matched
seeds across formats. Rosters are generated on an EMPTY override table at that
harness's fixed salt — a format-property measurement, not a replay of a save.
See docs/reports/REPORT-jhsaa-6a-format-decision-2077-2079.md."""
import importlib.util, statistics, sys, os
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, _REPO)
spec=importlib.util.spec_from_file_location("cal",os.path.join(_REPO, "scripts", "jhsaa_1a_format_pilot_calibration.py"))
cal=importlib.util.module_from_spec(spec); spec.loader.exec_module(cal)
jh=cal.jh; simulate_dual=cal.simulate_dual
from engine.dual import DualFormat
GROUP="6A"; TRIALS=int(sys.argv[1]) if len(sys.argv)>1 else 10
FMTS={
 "1S/4D": (jh.dual_format("state", None), lambda r: jh._arrange_state(r[:9], {})),
 "2S/3D": (jh.dual_format("state", "1A"), lambda r: jh._arrange_1a_postseason(r[:8], {})),
 "3S/2D": (DualFormat(n_singles=3, n_doubles=2, doubles_team_point=False), lambda r: jh._arrange_wide(r[:7], 3, {})),
 "4S/5D": (jh.dual_format("state", "8A"), lambda r: jh._arrange_wide(r[:14], 4, {})),
}
def run():
    programs=[]
    for g in jh.GENDERS:
        for s in jh.load_schools(g):
            if s.group==GROUP:
                programs.append((g,s,cal.order_program(s)))
    print(f"{GROUP}: {len(programs)} programs, {TRIALS} trials")
    # participation: who is cut vs 1S/4D's nine
    for label,(fmt,_arr) in FMTS.items():
        need=fmt.n_singles+2*fmt.n_doubles
        gaps=[]
        for g,s,r in programs:
            if need<9 and len(r)>=9:
                gaps.append(r[need-1].current_overall()-r[8].current_overall())
        if gaps: print(f"  {label}: dresses {need}; last dressed vs #9 cut mean gap {statistics.mean(gaps):.2f} OVR")
        else: print(f"  {label}: dresses {need}")
    for g in jh.GENDERS:
        pool=[(s,r) for gg,s,r in programs if gg==g]
        pool.sort(key=lambda sr:-statistics.mean(p.current_overall() for p in sr[1][:9]))
        half=len(pool)//2
        sets={"even (adjacent strength)":[(pool[i],pool[i+1]) for i in range(0,len(pool)-1,2)],
              "mismatched (top half vs bottom)":list(zip(pool[:half],reversed(pool[half:])))}
        for label,pairs in sets.items():
            stats={k:dict(fav=0,one=0,margin=[],same=0) for k in FMTS}
            for (sa,ra),(sb,rb) in pairs:
                arr={k:(f(ra),f(rb)) for k,(fmt,f) in FMTS.items()}
                fav_a=statistics.mean(p.current_overall() for p in ra[:9])>=statistics.mean(p.current_overall() for p in rb[:9])
                for t in range(TRIALS):
                    seed=cal._pair_seed(sa.name,sb.name,t); base=None
                    for k,(fmt,_f) in FMTS.items():
                        res=simulate_dual(cal.make_team(sa.name,arr[k][0],fmt),cal.make_team(sb.name,arr[k][1],fmt),
                                          seed=seed,play_all=True,fidelity=jh.FIDELITY,dual_fmt=fmt,
                                          singles_fmt=jh.MATCH_FORMAT,doubles_fmt=jh.MATCH_FORMAT)
                        wa=res.winner==0; m=abs(res.home_points-res.away_points)
                        st=stats[k]; st["fav"]+=(wa==fav_a); st["one"]+=(m<=1); st["margin"].append(m)
                        if base is None: base=wa
                        st["same"]+=(wa==base)
            n=len(pairs)*TRIALS
            print(f"\n{g} — {label}: {len(pairs)} pairings x {TRIALS} = {n} duals")
            print(f"  {'format':7}{'fav wins':>10}{'1-pt':>8}{'mean margin':>13}{'same winner as 1S/4D':>22}")
            for k,st in stats.items():
                pts=FMTS[k][0].n_singles+FMTS[k][0].n_doubles
                print(f"  {k:7}{st['fav']/n:>10.1%}{st['one']/n:>8.1%}{statistics.mean(st['margin']):>8.2f}/{pts:<4}{st['same']/n:>22.1%}")
run()
