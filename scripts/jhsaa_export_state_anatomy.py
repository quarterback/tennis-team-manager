"""State-dual anatomy from research-export zips (unzipped under <dir>/x/<year>/<gender>/).

    python3 scripts/jhsaa_export_state_anatomy.py <dir> [2077,2078,2079]

Reads the archived brackets (seeds, at-larges, scores) and joins each State dual to
its box score by PROGRAM KEY, not display name (programs.csv maps the two). Pooled
one-point rate, lower-seed win rate, at-large win rate and champion seeds per class,
plus the flight anatomy of the five-point classes. Written for the 2079 6A format
decision — docs/reports/REPORT-jhsaa-6a-format-decision-2077-2079.md."""
import csv, json, sys, collections, statistics
W=sys.argv[1]; YEARS=tuple(sys.argv[2].split(",")) if len(sys.argv)>2 else ("2077","2078","2079"); GENDERS=("girls","boys")
agg=collections.defaultdict(lambda: dict(n=0,one=0,low=0,seeded=0,al_w=0,al_n=0,champ_seeds=[],final_seeds=[]))
flight=collections.defaultdict(lambda: collections.Counter())
for y in YEARS:
  for g in GENDERS:
    base=f"{W}/x/{y}/{g}"
    champs=json.load(open(f"{base}/jhsaa_championships.json"))
    key2name={r["program_id"]:r["name"] for r in csv.DictReader(open(f"{base}/programs.csv"))}
    duals={}
    for r in csv.DictReader(open(f"{base}/duals.csv")):
      if r["phase"]=="state" and r["level"]=="v":
        duals[(key2name.get(r["home_program_id"]), key2name.get(r["away_program_id"]))]=r
    lines=collections.defaultdict(list)
    for r in csv.DictReader(open(f"{base}/lines.csv")):
      lines[r["dual_id"]].append(r)
    for grp,d in champs.items():
      seed={t:i+1 for i,t in enumerate(d["field"])}
      al=set(d.get("at_large") or [])
      a=agg[grp]
      for rnd in d["rounds"]:
        for m in rnd:
          if not m.get("winner"): continue
          h,aw=m["home"],m["away"]; hp,ap=m["home_points"],m["away_points"]
          a["n"]+=1
          if abs(hp-ap)<=1: a["one"]+=1
          if h in seed and aw in seed:
            a["seeded"]+=1
            lo=h if seed[h]>seed[aw] else aw
            if m["winner"]==lo: a["low"]+=1
          for t in (h,aw):
            if t in al: a["al_n"]+=1
          if m["winner"] in al: a["al_w"]+=1
          if grp in ("6A","5A","4A","3A","1A"):
            row=duals.get((h,aw)) or duals.get((aw,h))
            if not row: continue
            homewon = row["winner_program_id"]==row["home_program_id"]
            ls={l["slot"]:(l["home_won"]=="1") for l in lines[row["dual_id"]]}
            if "S1" not in ls: continue
            f=flight[grp]; f["n"]+=1
            s1=ls["S1"]==homewon
            f["s1_aligned"]+=s1
            dbl=[v==homewon for k,v in ls.items() if k.startswith("D")]
            f["dbl_sweep"]+=all(dbl)
            if abs(hp-ap)<=1:
              f["one"]+=1; f["one_s1_loser_won"]+=(not s1)
            if "S2" in ls: f["s2_aligned"]+=(ls["S2"]==homewon)
            if "D1" in ls: f["d1_aligned"]+=(ls["D1"]==homewon)
      if d.get("champion") in seed:
        a["champ_seeds"].append(seed[d["champion"]])
      fin=d["rounds"][-1][0] if d["rounds"] and d["rounds"][-1] else None
      if fin:
        for t in (fin["home"],fin["away"]):
          if t in seed: a["final_seeds"].append(seed[t])
print("STATE duals pooled 2077-79, both genders")
print(f"{'class':8}{'duals':>6}{'1-pt':>7}{'lowseed W':>10}{'AL win%':>9}{'champ seeds':>26}")
order=["9A","8A","7A","6A","5A","4A","3A","2A","1A","Group 1","Group 2","Group 3"]
for grp in order:
  a=agg[grp]; n=a["n"] or 1
  print(f"{grp:8}{a['n']:>6}{a['one']/n:>7.1%}{a['low']/max(a['seeded'],1):>10.1%}{(a['al_w']/max(a['al_n'],1)):>9.1%}   {sorted(a['champ_seeds'])}")
print("\nFLIGHT ANATOMY of State duals (1S/4D classes + 1A 2S/3D)")
print(f"{'class':8}{'n':>5}{'S1 winner won dual':>20}{'D1 aligned':>12}{'dbl sweep':>11}{'1-pt duals':>11}{'1-pt won by S1 LOSER':>22}")
for grp in ("6A","5A","4A","3A","1A"):
  f=flight[grp]; n=f["n"] or 1
  s2=f" S2 {f['s2_aligned']/n:.0%}" if f["s2_aligned"] else ""
  print(f"{grp:8}{f['n']:>5}{f['s1_aligned']/n:>20.1%}{f['d1_aligned']/n:>12.1%}{f['dbl_sweep']/n:>11.1%}{f['one']:>11}{f['one_s1_loser_won']/max(f['one'],1):>22.1%}{s2}")
# per-year 6A one-point rate
print("\n6A one-point rate by year/gender:")
for y in YEARS:
  for g in GENDERS:
    d=json.load(open(f"{W}/x/{y}/{g}/jhsaa_championships.json"))["6A"]
    ms=[m for r in d["rounds"] for m in r if m.get("winner")]
    one=sum(1 for m in ms if abs(m["home_points"]-m["away_points"])<=1)
    print(f"  {y} {g}: {one}/{len(ms)} = {one/len(ms):.0%}  champion seed {d['field'].index(d['champion'])+1 if d['champion'] in d['field'] else '?'}")
