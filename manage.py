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
    simulate_gtt_dual, GTTTeam,
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


def cmd_simulate_gtt(args):
    """Co-ed Global Team Tennis dual: 3 MS + 3 WS + 3 XD, first to 5 of 9."""
    men_fn = _picker(args.seed, "male", args.region)
    women_fn = _picker(args.seed ^ 0xC0FFEE, "female", args.region)
    rng = random.Random(args.seed)

    def franchise(label, base):
        men = [_gen_player(rng, men_fn, base=base) for _ in range(3)]
        women = [_gen_player(rng, women_fn, base=base) for _ in range(3)]
        return GTTTeam(name=label, men=men, women=women)

    home = franchise("Home Club", 0.60)
    away = franchise("Away Club", 0.57)
    res = simulate_gtt_dual(home, away, seed=args.seed, fidelity=args.fidelity)
    wname = (home if res.winner == 0 else away).name
    print(f"{home.name} {res.home_points} - {res.away_points} {away.name}   →  {wname}\n")
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


def cmd_persist_rosters(args):
    """Generate program rosters and write them to the DB — origins, scholarships
    and all. Exercises the persistence path the live (in-memory) app sidesteps,
    so rosters survive on disk with their hometowns/majors/aid intact."""
    from app.db import init_db, connect, save_prospect, DB_PATH
    from app.ncaa import load_division, build_roster, UNIVERSE_PAIRS, reset_caches
    from app import economy

    init_db()
    pairs = ([(args.division, args.gender)] if args.division
             else UNIVERSE_PAIRS)
    reset_caches()
    total = 0
    conn = connect()
    try:
        for division, gender in pairs:
            try:
                div = load_division(division, gender)
            except FileNotFoundError:
                continue
            for prog in div.programs:
                roster = build_roster(prog)
                for pr in roster:
                    save_prospect(conn, pr, school=prog.school, division=division)
                    total += 1
            cap = economy.cap_for(division, gender)
            print(f"  {division} {gender}: {len(div.programs)} programs "
                  f"(cap {cap:g} schol./team)")
        conn.commit()
    finally:
        conn.close()
    print(f"Persisted {total} players to {DB_PATH}")


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
    pros.sort(key=lambda p: (p.str_value(), p.star_rating()), reverse=True)

    if not args.reveal:
        print("\nRECRUITING BOARD — public view (STR · ranking · stars · scouting projections)\n")
        print(f"{'#':>3}  {'PLAYER':<26} {'CTY':<3} {'STR':>5} {'STARS':<7} {'SVC↑':>5} {'DEPT↑':>6}")
        for i, p in enumerate(pros, 1):
            print(f"{i:>3}  {p.name:<26} {p.country:<3} {p.str_value():>5} {'*' * p.star_rating():<7} "
                  f"{p.scouting_report('service'):>5} {p.scouting_report('dept'):>6}")
        print("\nSTR/stars = current ability (visible, from results). SVC/DEPT = two scouts'")
        print("independent CEILING projections (±fog). The trajectory is the gamble — --reveal.")
    else:
        print("\nREVEAL — current vs hidden ceiling vs 4-year projection\n")
        print(f"{'#':>3}  {'PLAYER':<24} {'STR':>5} {'STARS':<6} {'NOW':>4} {'CEIL':>4} {'4YR':>4}  {'TIER':<13} FLAG")
        for i, p in enumerate(pros, 1):
            proj = p.project(4)
            growth = proj - p.current_overall()
            flag = ""
            if p.star_rating() <= 2 and growth >= 12:
                flag = "GEM"          # modest now, big hidden upside (late/super bloomer)
            elif p.star_rating() >= 4 and growth <= 3:
                flag = "BUST"         # hyped now, but plateaus — peers pass him
            print(f"{i:>3}  {p.name:<24} {p.str_value():>5} {'*' * p.star_rating():<6} {p.current_overall():>4} "
                  f"{p.ceiling_overall():>4} {proj:>4}  {TIERS[p.tier][0]:<13} {flag}")


def cmd_recruits(args):
    from app.juniors import (generate_class, national_rankings, state_rankings,
                             international_rankings)
    rng = random.Random(args.seed)
    klass = generate_class(rng, n=args.n, grad_year=args.grad_year, gender=args.gender)
    if args.state:
        rows, title = state_rankings(klass, args.state), f"{args.state} — class of {args.grad_year}"
    elif args.intl:
        rows, title = international_rankings(klass), f"International — class of {args.grad_year}"
    else:
        rows, title = national_rankings(klass), f"National Top {args.top} — class of {args.grad_year}"
    national_rankings(klass)   # assigns national rank + count-based tiers to all
    print(f"\n{title} ({klass.gender})\n")
    print(f"{'#':>3}  {'PLAYER':<24} {'HOMETOWN':<26} {'STR':>5} {'NAT':>5}  TIER")
    for i, p in enumerate(rows[:args.top], 1):
        stars = "*" * p.recruit_stars if p.recruit_stars else "-"
        print(f"{i:>3}  {p.name:<24} {p.hometown:<26} {p.str_value():>5} {'#' + str(p.recruit_rank):>5}  "
              f"{stars:<5} {p.recruit_tier}")


def cmd_junior_circuit(args):
    from app.juniors import generate_class, national_rankings
    from app.junior_circuit import run_junior_circuit, TIER_LABELS
    rng = random.Random(args.seed)
    klass = generate_class(rng, n=args.n, grad_year=args.grad_year, gender=args.gender)
    national_rankings(klass)
    run_junior_circuit(klass, seed=args.seed)

    # Tier distribution — the schedule-driven pyramid.
    tiers: dict[int, int] = {}
    for p in klass.recruits:
        tiers[p.junior_tier] = tiers.get(p.junior_tier, 0) + 1
    print(f"\nJunior circuit — class of {args.grad_year} ({klass.gender}), "
          f"{len(klass.recruits)} recruits\n")
    print("Tiers:")
    for t in sorted(tiers):
        print(f"  Tier {t} {TIER_LABELS[t]:<24} {tiers[t]:>4}")

    # Most-badged recruit's résumé — the lived-in profile this feature exists for.
    spotlight = max(klass.recruits, key=lambda p: (len(p.junior_badges), p.junior_str))
    print(f"\nSpotlight — {spotlight.name} ({spotlight.country}), "
          f"ability STR {spotlight.str_value():.1f} → junior STR {spotlight.junior_str:.1f} "
          f"(reliability {spotlight.junior_str_reliability:.2f}), "
          f"Tier {spotlight.junior_tier} {TIER_LABELS[spotlight.junior_tier]}")
    print("\n  Badges:")
    for b in spotlight.junior_badges:
        print(f"    • {b}")
    print("\n  Results:")
    print(f"    {'DATE':<10} {'TOURNAMENT':<26} {'LEVEL':<12} RESULT")
    for r in spotlight.junior_results:
        print(f"    {r['date']:<10} {r['tournament']:<26} {r['level']:<12} {r['result']}")
    print("\n  Match record (every opponent is a fellow recruit):")
    for m in spotlight.junior_matches:
        vs = "def." if m["won"] else "lost to"
        print(f"    {m['date']:<10} {m['tournament']:<24} {m['round']:<14} "
              f"{vs:<8} {m['opponent']:<22} {m['score']}")
    print("\n  Ranking history (STR re-solved from results at each date):")
    for h in spotlight.ranking_history:
        sec = f"#{h['secondary']}" if h['secondary'] else "—"
        print(f"    {h['date']:<10} {h['primary_label']} #{h['primary']:<5} "
              f"{h['secondary_label']} {sec:<6} STR {h['str']:.1f}")


def cmd_league(args):
    from app.league import new_league, advance_year
    lg = new_league(args.division, args.gender, seed=args.seed)

    def top_players(n=10):
        flat = []
        for school, roster in lg.rosters.items():
            for p in roster:
                s, rel = lg.player_str.get(p.pid, (p.str_value(), 0.0))
                flat.append((s, rel, p, school))
        flat.sort(key=lambda x: -x[0])
        return flat[:n]

    print(f"\n{args.division} {args.gender} — League opening season (year 0)\n")
    print(f"{'STR':>5} {'REL':>4}  {'CL':<3} {'PLAYER':<22} {'SCHOOL'}")
    for s, rel, p, school in top_players():
        print(f"{s:>5.1f} {rel:>4.2f}  {p.class_year:<3} {p.name:<22} {school}")

    for _ in range(args.years):
        summ = advance_year(lg)
        print(f"\n— Year {summ['year']}: {summ['graduated']} grad · {summ['intake']} fresh · "
              f"{summ['retained']} walk-ons kept · portal {summ['movers']} "
              f"(up {summ['up']} / down {summ['down']} / scholarship {summ['schol']} / "
              f"left div {summ['depart']}) —")
        arrows = {"up": "^", "down": "v", "schol": "$"}
        for kind, name, frm, to, s in summ["sample"][:8]:
            print(f"   {arrows.get(kind, '-')} {name} (STR {s})  {frm} -> {to}")
    print(f"\nTop players after {args.years} season(s):\n")
    print(f"{'STR':>5} {'REL':>4}  {'CL':<3} {'PLAYER':<22} {'SCHOOL'}")
    for s, rel, p, school in top_players():
        print(f"{s:>5.1f} {rel:>4.2f}  {p.class_year:<3} {p.name:<22} {school}")


def cmd_seasonmode(args):
    from app import seasonmode as sm
    sid = sm.get_or_create(args.division, args.gender, seed=args.seed)
    for _ in range(args.advance):
        if sm.load_season(sid)["phase"] == "complete":
            break
        r = sm.advance(sid)
        if r.get("phase") == "regular":
            print(f"  week {r['week']}: {r['played']} duals played")
        else:
            print(f"  {r}")
    s = sm.load_season(sid)
    print(f"\nSeason {sid}: {args.division} {args.gender} · phase={s['phase']} "
          f"· week {min(s['current_week'], s['total_weeks'])}/{s['total_weeks']}"
          f"{' · champion ' + s['champion'] if s['phase'] == 'complete' else ''}")
    # standings snapshot for one conference
    st = sm.standings(sid)
    conf = next(iter(st))
    print(f"\n{conf} (overall · conf):")
    for r in st[conf][:6]:
        print(f"  {r['school']:<22} {r['ow']}-{r['ol']}  ({r['cw']}-{r['cl']})")


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

    gtt = sub.add_parser("simulate-gtt", help="co-ed GTT dual: 3 MS + 3 WS + 3 XD, first to 5 of 9")
    add_common(gtt)
    gtt.set_defaults(func=cmd_simulate_gtt)

    g = sub.add_parser("gen-players")
    add_common(g)
    g.add_argument("--n", type=int, default=8)
    g.set_defaults(func=cmd_gen_players)

    sub.add_parser("presets").set_defaults(func=cmd_presets)
    sub.add_parser("initdb").set_defaults(func=cmd_initdb)

    persist = sub.add_parser("persist-rosters",
                             help="generate rosters and write them (origins + "
                                  "scholarships) to the DB")
    persist.add_argument("--division", default="", help="one division (e.g. D1); omit for all")
    persist.add_argument("--gender", default="men", choices=["men", "women"])
    persist.set_defaults(func=cmd_persist_rosters)

    sm = sub.add_parser("seasonmode")
    sm.add_argument("--division", default="D1")
    sm.add_argument("--gender", default="men", choices=["men", "women"])
    sm.add_argument("--seed", type=int, default=2026)
    sm.add_argument("--advance", type=int, default=99, help="advance this many steps/weeks")
    sm.set_defaults(func=cmd_seasonmode)

    rs = sub.add_parser("runserver")
    rs.add_argument("--port", type=int, default=5000)
    rs.set_defaults(func=cmd_runserver)

    pr = sub.add_parser("prospects")
    pr.add_argument("--n", type=int, default=20)
    pr.add_argument("--seed", type=int, default=1)
    pr.add_argument("--gender", default="male", choices=["male", "female", "mixed"])
    pr.add_argument("--reveal", action="store_true")
    pr.set_defaults(func=cmd_prospects)

    lge = sub.add_parser("league")
    lge.add_argument("--division", default="D1")
    lge.add_argument("--gender", default="men", choices=["men", "women"])
    lge.add_argument("--seed", type=int, default=2026)
    lge.add_argument("--years", type=int, default=4)
    lge.set_defaults(func=cmd_league)

    rc = sub.add_parser("recruits")
    rc.add_argument("--n", type=int, default=300)
    rc.add_argument("--top", type=int, default=25)
    rc.add_argument("--grad-year", type=int, default=2026, dest="grad_year")
    rc.add_argument("--gender", default="male", choices=["male", "female", "mixed"])
    rc.add_argument("--state", default="", help="state name, e.g. 'California'")
    rc.add_argument("--intl", action="store_true", help="international board")
    rc.add_argument("--seed", type=int, default=1)
    rc.set_defaults(func=cmd_recruits)

    jc = sub.add_parser("junior-circuit",
                        help="generate a class, run the junior circuit, show a résumé")
    jc.add_argument("--n", type=int, default=300)
    jc.add_argument("--grad-year", type=int, default=2026, dest="grad_year")
    jc.add_argument("--gender", default="male", choices=["male", "female", "mixed"])
    jc.add_argument("--seed", type=int, default=1)
    jc.set_defaults(func=cmd_junior_circuit)

    se = sub.add_parser("season")
    se.add_argument("--division", default="D1")
    se.add_argument("--gender", default="men", choices=["men", "women"])
    se.add_argument("--seed", type=int, default=2026)
    se.add_argument("--field", type=int, default=64, help="bracket field size (16–128; 64 default)")
    se.set_defaults(func=cmd_season)

    args = ap.parse_args()
    # Create all DB schemas up front so CLI sims never deadlock on first-time
    # table creation inside a held transaction.
    try:
        from app.db import bootstrap
        bootstrap()
    except Exception:
        pass
    args.func(args)


if __name__ == "__main__":
    main()
