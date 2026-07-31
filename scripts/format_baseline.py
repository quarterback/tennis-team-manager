"""Format calibration: classic 6+3 vs the new per-division shapes.

One run_season per division per arm, same seed, fast fidelity, injuries off
(they're off by default outside the app). Metrics:
  fav_win   — share of duals won by the higher-card-mean-OVR team (upset rate = 1 - this)
  fav6_win  — same but favorite judged on top-6 mean (arm-independent yardstick)
  dbl_dec   — duals the doubles DECIDED: the winner's doubles-point edge covered
              their final margin (take the doubles away and they don't win)
  spread    — stddev of team win%, and mean win% of the top 5 (dominance)
"""
import statistics, sys, time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

import app.season as season
season._fidelity = lambda: "fast"          # same outcome model both arms, cheap
season.BOX_STATS = False
import app.ncaa as ncaa
from engine import CLASSIC, DualFormat

NEW = dict(ncaa.DUAL_FORMATS)
OLD = {d: CLASSIC for d in NEW}
SEED = 424242


def run(division, formats):
    ncaa.DUAL_FORMATS.clear(); ncaa.DUAL_FORMATS.update(formats)
    t0 = time.time()
    sr = season.run_season(division, "men", seed=SEED)
    dt = time.time() - t0

    def mean_ovr(school, k):
        r = sorted(sr.rosters[school], key=lambda p: p.current_overall(), reverse=True)
        r = r[:k]
        return sum(p.current_overall() for p in r) / len(r) if r else 0

    card = ncaa.lineup_size(division)
    strength = {s: mean_ovr(s, card) for s in sr.rosters}
    strength6 = {s: mean_ovr(s, 6) for s in sr.rosters}

    fmt = ncaa.dual_format(division)
    fav = fav6 = decisive = 0
    wl = {}
    for d in sr.duals:
        h, a = d["home"], d["away"]
        for t in (h, a):
            wl.setdefault(t, [0, 0])
        win, lose = (h, a) if d["home_won"] else (a, h)
        wl[win][0] += 1; wl[lose][1] += 1
        fav += strength[win] >= strength[lose]
        fav6 += strength6[win] >= strength6[lose]
        # Doubles points each side actually banked in the dual score.
        hd = sum(1 for ln in d["lines"] if ln["slot"].startswith("D") and ln.get("home_won"))
        ad = fmt.n_doubles - hd
        if fmt.doubles_team_point:
            hd, ad = (1, 0) if hd * 2 > fmt.n_doubles else (0, 1)
        w_dbl, l_dbl = (hd, ad) if d["home_won"] else (ad, hd)
        margin = abs(d["home_points"] - d["away_points"])
        if w_dbl - l_dbl >= margin:
            decisive += 1          # strip the doubles edge and the winner doesn't win

    n = len(sr.duals)
    pcts = [w / (w + l) for w, l in wl.values() if w + l]
    top5 = sorted(pcts, reverse=True)[:5]
    return {"n": n, "fav": fav / n, "fav6": fav6 / n, "flip": decisive / n,
            "spread": statistics.pstdev(pcts), "top5": sum(top5) / len(top5),
            "secs": round(dt, 1)}


print(f"{'div':4} {'arm':8} {'duals':>6} {'fav%':>6} {'fav6%':>6} {'dbldec%':>8} {'spread':>7} {'top5 win%':>9} {'secs':>6}")
for division in ("D1", "D2", "D3", "D4"):
    for arm, formats in (("classic", OLD), ("new", NEW)):
        m = run(division, formats)
        print(f"{division:4} {arm:8} {m['n']:>6} {m['fav']*100:>6.1f} {m['fav6']*100:>6.1f} "
              f"{m['flip']*100:>8.2f} {m['spread']:>7.3f} {m['top5']*100:>9.1f} {m['secs']:>6}")
ncaa.DUAL_FORMATS.clear(); ncaa.DUAL_FORMATS.update(NEW)
