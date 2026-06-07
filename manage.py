#!/usr/bin/env python3
"""
Tennis-sim CLI.

  python3 manage.py simulate-match --seed 7 [--format best_of_3_mtb] [--fidelity full]
                                   [--gender male] [--region global] [--pbp]
  python3 manage.py simulate-dual  --seed 7 [--fidelity full]
  python3 manage.py gen-players    --seed 7 --n 8 [--gender female] [--region european]
  python3 manage.py presets
  python3 manage.py initdb

Everything is seed-deterministic: the same seed + flags reproduces the
transcript and scoreline exactly.
"""
from __future__ import annotations

import argparse
import random

from engine import (
    PRESETS, random_player, simulate_match, simulate_dual, Team, box_score, pbp_text,
)
from engine.format import MatchFormat
from generators import make_name_picker, region_preset, list_presets


def _picker(seed: int, gender: str, region: str):
    rng = random.Random(seed ^ 0x5EED)
    weights = region_preset(region) if region else None
    return make_name_picker(rng, gender=gender, region_weights=weights)


def _gen_player(rng: random.Random, name_fn, base: float = 0.5):
    name, country = name_fn()
    return random_player(rng, name, country, base=base)


def cmd_simulate_match(args):
    fmt = PRESETS.get(args.format, PRESETS["best_of_3_mtb"]) if args.format else None
    name_fn = _picker(args.seed, args.gender, args.region)
    rng = random.Random(args.seed)
    p0 = _gen_player(rng, name_fn, base=0.58)
    p1 = _gen_player(rng, name_fn, base=0.55)
    result = simulate_match(p0, p1, seed=args.seed, fmt=fmt, fidelity=args.fidelity)
    print(box_score(result))
    if args.pbp:
        print("\n--- play-by-play ---")
        print(pbp_text(result))


def cmd_simulate_dual(args):
    name_fn = _picker(args.seed, args.gender, args.region)
    rng = random.Random(args.seed)

    def team(label, base):
        return Team(name=label, singles=[_gen_player(rng, name_fn, base=base) for _ in range(6)])

    home = team("Home U", 0.60)
    away = team("Away State", 0.57)
    res = simulate_dual(home, away, seed=args.seed, fidelity=args.fidelity)
    wname = (home if res.winner == 0 else away).name
    print(f"{home.name} {res.home_points} - {res.away_points} {away.name}   →  {wname}")
    print(f"(doubles point: {[home.name, away.name][res.doubles_point]})\n")
    for ln in res.lines:
        if not ln.completed:
            print(f"  {ln.slot}: (unfinished — clinched)")
            continue
        winside = home if ln.home_won else away
        print(f"  {ln.slot}: {winside.name:<12} def.  {ln.result.scoreline}")


def cmd_gen_players(args):
    name_fn = _picker(args.seed, args.gender, args.region)
    rng = random.Random(args.seed)
    for _ in range(args.n):
        p = _gen_player(rng, name_fn)
        print(f"{p.name:<28} {p.country:<3}  overall={p.overall:.2f}  "
              f"serve={p.serve_skill:.2f} rally={p.rally_skill:.2f}")


def cmd_presets(args):
    print("Match-format presets:")
    for k, v in PRESETS.items():
        print(f"  {k:<14} {v}")
    print("\nName-region presets:")
    print("  " + ", ".join(list_presets()))


def cmd_initdb(args):
    from app.db import init_db, DB_PATH
    init_db()
    print(f"Initialised DB at {DB_PATH}")


def cmd_season(args):
    from app.season import run_season
    from app.bracket import select_field, run_bracket, clamp_field
    field = clamp_field(args.field)
    sr = run_season(args.division, args.gender, seed=args.seed)
    ranked = sr.ranked()
    print(f"\n{args.division} {args.gender} — {len(sr.programs)} programs, "
          f"{len(sr.standings)} conferences, {len(sr.champions)} champions\n")
    print(f"{'#':>3}  {'SCHOOL':<22} {'CONF':<8} {'REC':>7}  {'POWER':>7} {'APR':>6} {'FQI':>6}")
    for i, p in enumerate(ranked[:25], 1):
        r = sr.ratings[p.school]
        print(f"{i:>3}  {p.school:<22} {p.conf_abbr:<8} {r.record:>7}  "
              f"{r.pi:.4f} {r.apr:.4f} {r.fqi:.4f}")

    seeded, autobids = select_field(sr.programs, sr.ratings, sr.champions, size=field)
    br = run_bracket(seeded, autobids, seed=args.seed)
    print(f"\nNCAA bracket — {len(seeded)} teams "
          f"({len(autobids)} autobids + {len(seeded) - len(autobids)} at-large)")
    print(f"  Champion:  #{br.seed_of(br.champion)} {br.champion.school}")
    print(f"  Runner-up: #{br.seed_of(br.runner_up)} {br.runner_up.school}")
    print("  Final Four:")
    for m in br.rounds[-2]:
        print(f"    #{m.hi_seed} {m.hi.school} vs #{m.lo_seed} {m.lo.school} "
              f"→ #{m.winner_seed} {m.winner.school}{'  (UPSET)' if m.upset else ''}")
    upsets = [m for rnd in br.rounds for m in rnd if m.upset and m.lo_seed - m.hi_seed >= 8]
    if upsets:
        print(f"  Notable upsets ({len(upsets)}):")
        for m in upsets[:6]:
            print(f"    {m.rnd}: #{m.lo_seed} {m.lo.school} d. #{m.hi_seed} {m.hi.school}")


def cmd_prospects(args):
    from app.development import generate_prospect, TIERS
    from generators import make_name_picker, region_preset
    rng = random.Random(args.seed)
    name_fn = make_name_picker(random.Random(args.seed ^ 0x5EED), gender=args.gender,
                               region_weights=region_preset("global"))
    pros = []
    for _ in range(args.n):
        nm, co = name_fn()
        pros.append(generate_prospect(rng, nm, co, gender=args.gender))
    pros.sort(key=lambda p: (p.utr(), p.star_rating()), reverse=True)

    if not args.reveal:
        print("\nRECRUITING BOARD — public view (UTR · ranking · stars · scouting projections)\n")
        print(f"{'#':>3}  {'PLAYER':<26} {'CTY':<3} {'UTR':>5} {'STARS':<7} {'SVC↑':>5} {'DEPT↑':>6}")
        for i, p in enumerate(pros, 1):
            print(f"{i:>3}  {p.name:<26} {p.country:<3} {p.utr():>5} {'*' * p.star_rating():<7} "
                  f"{p.scouting_report('service'):>5} {p.scouting_report('dept'):>6}")
        print("\nUTR/stars = current ability (visible, from results). SVC/DEPT = two scouts'")
        print("independent CEILING projections (±fog). The trajectory is the gamble — --reveal.")
    else:
        print("\nREVEAL — current vs hidden ceiling vs 4-year projection\n")
        print(f"{'#':>3}  {'PLAYER':<24} {'UTR':>5} {'STARS':<6} {'NOW':>4} {'CEIL':>4} {'4YR':>4}  {'TIER':<13} FLAG")
        for i, p in enumerate(pros, 1):
            proj = p.project(4)
            growth = proj - p.current_overall()
            flag = ""
            if p.star_rating() <= 2 and growth >= 12:
                flag = "GEM"          # modest now, big hidden upside (late/super bloomer)
            elif p.star_rating() >= 4 and growth <= 3:
                flag = "BUST"         # hyped now, but plateaus — peers pass him
            print(f"{i:>3}  {p.name:<24} {p.utr():>5} {'*' * p.star_rating():<6} {p.current_overall():>4} "
                  f"{p.ceiling_overall():>4} {proj:>4}  {TIERS[p.tier][0]:<13} {flag}")


def cmd_runserver(args):
    import os
    os.environ.setdefault("PORT", str(args.port))
    from app.web import main as web_main
    web_main()


def main():
    ap = argparse.ArgumentParser(description="Tennis-sim CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_common(p):
        p.add_argument("--seed", type=int, default=1)
        p.add_argument("--gender", default="mixed", choices=["male", "female", "mixed"])
        p.add_argument("--region", default="global")
        p.add_argument("--fidelity", default="full", choices=["full", "fast"])

    m = sub.add_parser("simulate-match")
    add_common(m)
    m.add_argument("--format", default="best_of_3_mtb")
    m.add_argument("--pbp", action="store_true")
    m.set_defaults(func=cmd_simulate_match)

    d = sub.add_parser("simulate-dual")
    add_common(d)
    d.set_defaults(func=cmd_simulate_dual)

    g = sub.add_parser("gen-players")
    add_common(g)
    g.add_argument("--n", type=int, default=8)
    g.set_defaults(func=cmd_gen_players)

    sub.add_parser("presets").set_defaults(func=cmd_presets)
    sub.add_parser("initdb").set_defaults(func=cmd_initdb)

    rs = sub.add_parser("runserver")
    rs.add_argument("--port", type=int, default=5000)
    rs.set_defaults(func=cmd_runserver)

    pr = sub.add_parser("prospects")
    pr.add_argument("--n", type=int, default=20)
    pr.add_argument("--seed", type=int, default=1)
    pr.add_argument("--gender", default="male", choices=["male", "female", "mixed"])
    pr.add_argument("--reveal", action="store_true")
    pr.set_defaults(func=cmd_prospects)

    se = sub.add_parser("season")
    se.add_argument("--division", default="D1")
    se.add_argument("--gender", default="men", choices=["men", "women"])
    se.add_argument("--seed", type=int, default=2026)
    se.add_argument("--field", type=int, default=64, help="bracket field size (16–128; 64 default)")
    se.set_defaults(func=cmd_season)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
