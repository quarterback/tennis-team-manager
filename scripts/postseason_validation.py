"""
Post-season validation study — treat the NCAA Tournament as a test set.

This is NOT a unit test. It simulates full seasons, then mines the NCAA-tournament
box scores to answer three questions about the engine's *emergent* behaviour:

  1. UPSETS      — how often does the lower seed / weaker roster win, by round?
  2. REALISM     — what do the scorelines look like (dual margins, 3-setters,
                   doubles-point leverage), and do they feel like college tennis?
  3. CALIBRATION — how tightly do wins track relative strength (OVR/STR/seed),
                   and is the engine's own win-probability well-calibrated
                   (does a "90% match" actually win ~90%)?

Design notes that shape the analysis (verified against the engine source):
  * The fast model (engine.fast) decides every game from ONE signal: the gap in
    `player.overall`. A player's STR is `overall_to_str(current_overall())` — a
    monotone transform of the SAME attribute table. So at the SINGLES level OVR,
    STR and the engine's `overall` are rank-identical: they cannot disagree on who
    is favoured on a court. They only diverge at the TEAM level, where a non-linear
    STR is *summed* over the top six (different weighting than summing OVR).
  * There is NO per-match "form", "coach bonus" or "archetype" dial — coaching
    enters upstream (development + recruiting + lineup), not the match dice. The
    only match-time context edge is venue/wind/heat/crowd, which is neutral here.
    So the honest calibration question is purely: does outcome-vs-talent-gap match
    real college tennis, and are the tails too fat?

Outputs (written to --out, default scripts/out/postseason/):
  duals.csv        one row per NCAA dual  (both teams' strength features + result)
  singles.csv      one row per completed NCAA singles court (both players + result)
  summary.json     the computed analysis (bins, calibration, upsets, case studies)
  and a printed report.

Usage:
    python3 scripts/postseason_validation.py                       # D1 men+women, 1 seed
    python3 scripts/postseason_validation.py D1:men D2:men --seeds 3
    python3 scripts/postseason_validation.py D3:men --seeds 2 --out /tmp/pv
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.seasonmode as sm
from app.ncaa import load_division, build_roster
from app.ita import power6
from app.coaches import program_coach
from app.development import overall_to_str

# STR band 31-57 spans ~15.5 UTR; 1 UTR ~= 1.677 STR (from scripts/eval_realism).
_STR_PER_UTR = 1.677

# The engine's stated design target for favourite win-rate by UTR gap
# (engine/fast.py TUNE docstring). Used as the yardstick in the report.
DESIGN_TARGET = {  # UTR-gap bucket -> favourite win %
    "0.0-0.5": None, "0.5-1.0": None, "1.0-1.5": 63, "1.5-2.0": 69,
    "2.0-3.0": 77, "3.0+": 87, "overall": 65,
}
GAP_BUCKETS = [(0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 99)]

_CLASS_EXP = {"Fr": 1, "So": 2, "Jr": 3, "Sr": 4}

def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0

def _grade(pr, attr):
    try:
        return pr.current_grade(attr)
    except Exception:
        return float("nan")

def _base_class(cls: str) -> str:
    return cls[3:] if isinstance(cls, str) and cls.startswith("RS-") else (cls or "")


# ---------------------------------------------------------------- feature build
def _player_features(pr) -> dict:
    """Static pre-tournament ability for one Prospect."""
    ovr = pr.current_overall()
    serve = _mean(_grade(pr, a) for a in
                  ("first_serve_power", "first_serve_accuracy", "second_serve_quality"))
    fh = _mean(_grade(pr, a) for a in ("forehand_power", "forehand_control"))
    bh = _mean(_grade(pr, a) for a in ("backhand_power", "backhand_control"))
    move = _mean(_grade(pr, a) for a in ("footwork", "speed", "agility"))
    mental = _mean(_grade(pr, a) for a in ("composure", "clutch", "focus"))
    try:
        eng = pr.engine_player().overall
    except Exception:
        eng = float("nan")
    return {
        "ovr": ovr,
        "str": round(pr.str_value(), 2),
        "eng": round(eng, 4),                # the [0,1] signal the dice actually read
        "ceiling": pr.ceiling_overall(),
        "exp": _CLASS_EXP.get(_base_class(pr.class_year), 0),
        "serve": round(serve, 1), "fh": round(fh, 1), "bh": round(bh, 1),
        "move": round(move, 1), "mental": round(mental, 1),
        "stamina": round(_grade(pr, "stamina"), 1),
        "name": pr.name, "country": pr.country,
    }


def _team_features(prog) -> dict:
    roster = sorted(build_roster(prog), key=lambda p: p.current_overall(), reverse=True)
    top6 = roster[:6]
    coach = program_coach(prog.school)
    return {
        "top6_ovr": sum(p.current_overall() for p in top6),
        "top6_str": round(sum(p.str_value() for p in top6), 1),
        "top6_eng": round(sum(p.engine_player().overall for p in top6), 4),
        "top1_ovr": top6[0].current_overall() if top6 else 0,
        "avg_ceiling": round(_mean(p.ceiling_overall() for p in top6), 1),
        "avg_exp": round(_mean(_CLASS_EXP.get(_base_class(p.class_year), 0) for p in top6), 2),
        "power6": power6(prog),
        "coach_dev": round(coach.development_score, 1),
        "coach_rec": round(coach.recruiting_score, 1),
        "coach_tac": round(coach.grade("match_tactics"), 1),
    }


# ---------------------------------------------------------------- run one season
def run_season(division: str, gender: str, seed: int) -> dict:
    t0 = time.time()
    sm.DB_PATH = f"/tmp/pv_{division}_{gender}_{seed}.db"
    if os.path.exists(sm.DB_PATH):
        os.remove(sm.DB_PATH)
    sm._forced_cache.clear()

    div = load_division(division, gender)
    progs = {p.school: p for p in div.programs}

    sid = sm.create_season(division, gender, seed=seed)
    guard = 0
    while sm.load_season(sid)["phase"] != "complete" and guard < 300:
        sm.advance(sid)
        guard += 1
    s = sm.load_season(sid)

    # pid -> static player features (whole division; duals reference pids).
    pfeat: dict[str, dict] = {}
    tfeat: dict[str, dict] = {}
    for p in div.programs:
        tfeat[p.school] = _team_features(p)
        for pr in build_roster(p):
            pfeat[pr.pid] = _player_features(pr)

    # National seed 1..N (authoritative committee order).
    conn = sm._db()
    schools, _autobids, _played = sm._ncaa_seeds(conn, s, progs, div)
    seed_rank = {school: i + 1 for i, school in enumerate(schools)}

    rows = conn.execute(
        "SELECT conf AS round_name, round_no, bpos, home, away, home_points, away_points,"
        " winner, lines_json FROM duals WHERE season_id=? AND round='NCAA' AND status='final'"
        " ORDER BY round_no, bpos", (sid,)).fetchall()
    conn.close()

    duals, singles = [], []
    for r in rows:
        h, a = r["home"], r["away"]
        hf, af = tfeat.get(h, {}), tfeat.get(a, {})
        hseed, aseed = seed_rank.get(h, 9999), seed_rank.get(a, 9999)
        home_won = r["winner"] == 0
        dual = {
            "division": division, "gender": gender, "seed": seed,
            "round_no": r["round_no"], "round": r["round_name"],
            "home": h, "away": a,
            "home_pts": r["home_points"], "away_pts": r["away_points"],
            "home_won": int(home_won),
            "home_seed": hseed, "away_seed": aseed,
        }
        for k, v in hf.items():
            dual["home_" + k] = v
        for k, v in af.items():
            dual["away_" + k] = v
        duals.append(dual)

        for ln in json.loads(r["lines_json"] or "[]"):
            if not ln.get("completed") or not str(ln.get("slot", "")).startswith("S"):
                continue
            hp, ap = ln.get("home_pid"), ln.get("away_pid")
            if hp not in pfeat or ap not in pfeat:
                continue
            hpf, apf = pfeat[hp], pfeat[ap]
            sets = ln.get("sets") or []
            n_sets = len([1 for st in sets if sum(st) > 0])
            singles.append({
                "division": division, "gender": gender, "seed": seed,
                "round_no": r["round_no"], "round": r["round_name"],
                "slot": ln["slot"], "home": h, "away": a,
                "home_player": hpf["name"], "away_player": apf["name"],
                "home_ovr": hpf["ovr"], "away_ovr": apf["ovr"],
                "home_str": hpf["str"], "away_str": apf["str"],
                "home_eng": hpf["eng"], "away_eng": apf["eng"],
                "home_serve": hpf["serve"], "away_serve": apf["serve"],
                "home_fh": hpf["fh"], "away_fh": apf["fh"],
                "home_mental": hpf["mental"], "away_mental": apf["mental"],
                "home_exp": hpf["exp"], "away_exp": apf["exp"],
                "home_games": ln.get("home_games"), "away_games": ln.get("away_games"),
                "n_sets": n_sets, "home_won": int(ln.get("home_won")),
            })

    return {"division": division, "gender": gender, "seed": seed,
            "elapsed": time.time() - t0, "champion": s["champion"],
            "duals": duals, "singles": singles}


# ---------------------------------------------------------------- analysis
def _set_prob(p: float) -> float:
    """Prob the favourite wins one set (race to 6, win-by-2, tiebreak at 6-6
    decided with per-game prob p), given a serve-neutral per-game win prob p.
    Exact closed form."""
    from math import comb
    P = 0.0
    for l in range(0, 5):                       # win 6-0 .. 6-4
        P += comb(5 + l, l) * p**6 * (1 - p)**l
    p55 = comb(10, 5) * p**5 * (1 - p)**5       # reach 5-5
    P += p55 * p * p                            # 7-5
    P += p55 * (p * (1 - p) + (1 - p) * p) * p  # 6-6 then win tiebreak (~p)
    return min(1.0, P)


def _predicted_match_winprob(eng_gap: float) -> float:
    """The engine's OWN implied match win-prob for the higher-rated player, derived
    from engine.fast's hold logistic at the given gap in `overall`. Reproduces the
    per-game hold edge (favourite serving / returning), collapses to a serve-neutral
    per-game win prob, then rolls it up through a set and a best-of-3. Used only to
    build the reliability curve (predicted vs actual)."""
    from engine.fast import _logistic, TUNE
    base, slope = TUNE["hold_base_logit"], TUNE["skill_slope"]
    hf = _logistic(base + slope * eng_gap)     # favourite holds serve
    hu = _logistic(base - slope * eng_gap)     # underdog holds serve
    pg = 0.5 * hf + 0.5 * (1 - hu)             # favourite's serve-neutral game-win prob
    ps = _set_prob(pg)
    return ps**2 + 2 * ps**2 * (1 - ps)        # best-of-3: win 2-0 or 2-1


def analyse(duals, singles) -> dict:
    out: dict = {}

    # ---- SINGLES: favourite win-rate by OVR gap (== STR gap, rank-identical) ----
    bins = {f"{lo}-{hi}": [0, 0] for lo, hi in GAP_BUCKETS}
    fav_w = fav_n = 0
    reliab = defaultdict(lambda: [0, 0])       # predicted-decile -> [wins, n]
    straight = three = 0
    upset_cases = []
    for m in singles:
        gap_ovr = m["home_ovr"] - m["away_ovr"]
        fav_home = gap_ovr >= 0
        gap_utr = abs(m["home_str"] - m["away_str"]) / _STR_PER_UTR
        fav_won = (m["home_won"] == 1) == fav_home
        fav_w += fav_won; fav_n += 1
        for lo, hi in GAP_BUCKETS:
            if lo <= gap_utr < hi:
                key = f"{lo}-{hi}"
                bins[key][0] += fav_won; bins[key][1] += 1
                break
        # reliability: engine's implied win prob for the favourite
        eng_gap = abs(m["home_eng"] - m["away_eng"])
        pwin = _predicted_match_winprob(eng_gap)
        dec = min(9, int(pwin * 10))
        reliab[dec][0] += fav_won; reliab[dec][1] += 1
        if m["n_sets"] >= 3:
            three += 1
        elif m["n_sets"] == 2:
            straight += 1
        if not fav_won and abs(m["home_ovr"] - m["away_ovr"]) >= 6:
            upset_cases.append(m)

    out["singles_n"] = fav_n
    out["singles_fav_pct"] = round(fav_w / fav_n * 100, 1) if fav_n else None
    out["singles_by_gap"] = {
        k: {"fav_pct": round(w / n * 100, 1) if n else None, "n": n,
            "target": DESIGN_TARGET.get(k)}
        for k, (w, n) in bins.items()}
    out["singles_straight_pct"] = round(straight / (straight + three) * 100, 1) if (straight + three) else None
    out["singles_three_set_pct"] = round(three / (straight + three) * 100, 1) if (straight + three) else None
    out["reliability"] = {
        f"{d*10}-{d*10+10}%": {"predicted_mid": d * 10 + 5,
                               "actual_pct": round(w / n * 100, 1) if n else None, "n": n}
        for d, (w, n) in sorted(reliab.items())}
    upset_cases.sort(key=lambda m: abs(m["home_ovr"] - m["away_ovr"]), reverse=True)
    out["singles_upset_cases"] = [{
        "round": m["round"], "slot": m["slot"],
        "winner": m["away_player"] if m["home_won"] == 0 else m["home_player"],
        "winner_ovr": m["away_ovr"] if m["home_won"] == 0 else m["home_ovr"],
        "loser": m["home_player"] if m["home_won"] == 0 else m["away_player"],
        "loser_ovr": m["home_ovr"] if m["home_won"] == 0 else m["away_ovr"],
        "ovr_gap": abs(m["home_ovr"] - m["away_ovr"]),
        "score": f"{m['home_games']}-{m['away_games']} games ({m['n_sets']} sets)",
    } for m in upset_cases[:12]]

    # ---- DUALS: which team metric best predicts the winner? ----
    metrics = ["seed", "top6_ovr", "top6_str", "top6_eng", "power6", "coach_tac"]
    hit = {mt: [0, 0] for mt in metrics}       # [correct, total] where a favourite exists
    seed_upsets_by_round = defaultdict(lambda: [0, 0])   # round -> [upsets, n]
    margin_dist = Counter()
    dbl_leverage = [0, 0]                       # [dual won by doubles-point side, n]
    dual_upset_cases = []
    for d in duals:
        hw = d["home_won"] == 1
        # seed: lower number = better
        for mt in metrics:
            if mt == "seed":
                hv, av = -d["home_seed"], -d["away_seed"]   # higher = better
            else:
                hv, av = d.get("home_" + mt), d.get("away_" + mt)
            if hv is None or av is None or hv == av:
                continue
            fav_home = hv > av
            hit[mt][0] += (fav_home == hw); hit[mt][1] += 1
        # seed upsets by round
        if d["home_seed"] != d["away_seed"]:
            fav_home = d["home_seed"] < d["away_seed"]
            up = (fav_home != hw)
            seed_upsets_by_round[d["round"]][0] += up
            seed_upsets_by_round[d["round"]][1] += 1
            if up:
                dual_upset_cases.append(d)
        # scoreline margin (winner pts - loser pts)
        wp, lp = (d["home_pts"], d["away_pts"]) if hw else (d["away_pts"], d["home_pts"])
        margin_dist[f"{wp}-{lp}"] += 1

    out["duals_n"] = len(duals)
    out["predictor_accuracy"] = {
        mt: {"pct": round(c / n * 100, 1) if n else None, "n": n} for mt, (c, n) in hit.items()}
    _ROUND_ORD = {"First Round": 0, "Round of 96": 1, "Round of 64": 2, "Round of 32": 3,
                  "Round of 16": 4, "Quarterfinals": 5, "Semifinals": 6, "Final": 7}
    out["seed_upsets_by_round"] = {
        rn: {"upset_pct": round(u / n * 100, 1) if n else None, "upsets": u, "n": n}
        for rn, (u, n) in sorted(seed_upsets_by_round.items(),
                                 key=lambda kv: _ROUND_ORD.get(kv[0], 99))}
    tot_up = sum(u for u, n in seed_upsets_by_round.values())
    tot_n = sum(n for u, n in seed_upsets_by_round.values())
    out["seed_upset_pct_overall"] = round(tot_up / tot_n * 100, 1) if tot_n else None
    out["dual_margin_dist"] = dict(sorted(margin_dist.items(), reverse=True))
    dual_upset_cases.sort(key=lambda d: abs(d["home_seed"] - d["away_seed"]), reverse=True)
    out["dual_upset_cases"] = [{
        "round": d["round"],
        "winner": d["away"] if d["home_won"] == 0 else d["home"],
        "winner_seed": d["away_seed"] if d["home_won"] == 0 else d["home_seed"],
        "loser": d["home"] if d["home_won"] == 0 else d["away"],
        "loser_seed": d["home_seed"] if d["home_won"] == 0 else d["away_seed"],
        "seed_gap": abs(d["home_seed"] - d["away_seed"]),
        "score": f"{max(d['home_pts'], d['away_pts'])}-{min(d['home_pts'], d['away_pts'])}",
    } for d in dual_upset_cases[:12]]
    return out


# ---------------------------------------------------------------- report
def fmt_report(meta, A) -> str:
    L = []
    L.append("=" * 70)
    L.append(f"POST-SEASON VALIDATION — {meta}")
    L.append("=" * 70)
    L.append(f"NCAA duals: {A['duals_n']}   completed singles courts: {A['singles_n']}")
    L.append("")
    L.append("1) UPSETS (lower seed beats higher seed)")
    L.append(f"   overall seed-upset rate: {A['seed_upset_pct_overall']}%")
    for rn, v in A["seed_upsets_by_round"].items():
        L.append(f"     {rn:<14} {v['upset_pct']:>5}%  ({v['upsets']}/{v['n']})")
    L.append("")
    L.append("2) REALISM")
    L.append(f"   singles straight-sets {A['singles_straight_pct']}% / 3-set {A['singles_three_set_pct']}%")
    L.append("   dual final-score distribution (winner-loser team pts):")
    for k, v in A["dual_margin_dist"].items():
        L.append(f"     {k}  {'#' * min(40, v)} {v}")
    L.append("")
    L.append("3) CALIBRATION — favourite win% by OVR/STR gap (UTR units)")
    L.append(f"   {'gap':>9} {'fav%':>6} {'target':>7} {'n':>6}")
    for k, v in A["singles_by_gap"].items():
        tgt = v["target"]
        L.append(f"   {k:>9} {str(v['fav_pct']):>6} {str(tgt) if tgt else '-':>7} {v['n']:>6}")
    L.append(f"   overall favourite win%: {A['singles_fav_pct']}%  (design target ~65%)")
    L.append("")
    L.append("   reliability — engine's implied win% vs actual:")
    L.append(f"   {'predicted':>10} {'actual':>7} {'n':>6}")
    for k, v in A["reliability"].items():
        L.append(f"   {k:>10} {str(v['actual_pct']):>7} {v['n']:>6}")
    L.append("")
    L.append("   which TEAM metric best predicts the dual winner:")
    for mt, v in sorted(A["predictor_accuracy"].items(), key=lambda kv: -(kv[1]["pct"] or 0)):
        L.append(f"     {mt:<10} {v['pct']}%  (n={v['n']})")
    L.append("")
    L.append("4) BIGGEST UPSETS (case studies)")
    L.append("   singles (largest OVR gap the favourite lost):")
    for c in A["singles_upset_cases"][:6]:
        L.append(f"     {c['round']:<12} {c['winner']} ({c['winner_ovr']}) beat "
                 f"{c['loser']} ({c['loser_ovr']})  gap {c['ovr_gap']}  {c['score']}")
    L.append("   duals (largest seed gap):")
    for c in A["dual_upset_cases"][:6]:
        L.append(f"     {c['round']:<12} #{c['winner_seed']} {c['winner']} beat "
                 f"#{c['loser_seed']} {c['loser']}  ({c['score']})")
    return "\n".join(L)


# ---------------------------------------------------------------- main
def main(argv):
    targets, seeds, out = [], 1, os.path.join(os.path.dirname(__file__), "out", "postseason")
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--seeds":
            seeds = int(argv[i + 1]); i += 2; continue
        if a == "--out":
            out = argv[i + 1]; i += 2; continue
        if ":" in a:
            d, g = a.split(":", 1); targets.append((d, g))
        i += 1
    if not targets:
        targets = [("D1", "men"), ("D1", "women")]
    os.makedirs(out, exist_ok=True)

    all_duals, all_singles, per_target = [], [], {}
    for div, gen in targets:
        d_all, s_all = [], []
        champs, elapsed = [], 0.0
        for k in range(seeds):
            res = run_season(div, gen, seed=2026 + k)
            d_all += res["duals"]; s_all += res["singles"]
            champs.append(res["champion"]); elapsed += res["elapsed"]
            print(f"  [{div}:{gen} seed {2026+k}] {len(res['duals'])} duals, "
                  f"{len(res['singles'])} singles, champ={res['champion']} "
                  f"({res['elapsed']:.0f}s)")
        A = analyse(d_all, s_all)
        A["champions"] = champs
        per_target[f"{div}:{gen}"] = A
        all_duals += d_all; all_singles += s_all
        print("\n" + fmt_report(f"{div} {gen} ({seeds} seed(s), {elapsed:.0f}s)", A) + "\n")

    # combined
    combined = analyse(all_duals, all_singles)
    per_target["ALL"] = combined
    print("\n" + fmt_report(f"ALL TARGETS COMBINED", combined) + "\n")

    # write artefacts
    def _write_csv(path, rows):
        if not rows:
            return
        keys = list(rows[0].keys())
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow(r)
    _write_csv(os.path.join(out, "duals.csv"), all_duals)
    _write_csv(os.path.join(out, "singles.csv"), all_singles)
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump({"targets": [f"{d}:{g}" for d, g in targets], "seeds": seeds,
                   "analysis": per_target}, f, indent=2)
    print(f"Wrote duals.csv ({len(all_duals)}), singles.csv ({len(all_singles)}), "
          f"summary.json -> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
