"""5A 6S/5D petition — roster capacity, the JV ladder, and the shape menu.

    python3 scripts/jhsaa_5a_6s5d_roster_study.py EXPORT_ROOT [EXPORT_ROOT ...]

Each EXPORT_ROOT is an unpacked Play to Clinch research export laid out as
`<root>/<gender>/{programs,players,duals,lines,line_players}.csv` (i.e. the `2094/`
directory of a `play-to-clinch-jhsaa-2094-both.zip`). Reads the ARCHIVE — this is a
measurement of seasons as played, not an engine counterfactual like
`jhsaa_6a_format_study.py`.

Answers the association's objection to the petition (can 5A fill a sixteen-player
card) and the two things it turned out to depend on: what the JV ladder needs from
the bands, and which shapes tie. Pure stdlib.
See docs/reports/REPORT-jhsaa-5a-6s5d-format-study-2094.md."""
import csv, collections, statistics as st, sys, os

JV_MIN_SPARE = 5          # jhsaa.JV_MIN_SPARE — smallest JV shape (1S/2D)
VARSITY_CUT = 11          # jhsaa.jv_pool cuts at lineup_need("regular")
GENDERS = ("girls", "boys")
ORDER = ["9A", "8A", "Group 1", "7A", "6A", "Group 2", "5A", "4A", "3A", "2A", "1A", "Group 3"]


def jv_format(spare):
    """jhsaa.jv_format — unbounded: D = (spare+1)//3, S = spare - 2D."""
    if spare < JV_MIN_SPARE:
        return None
    d = (spare + 1) // 3
    return (spare - 2 * d, d)


def fmt_jv(x):
    return "no JV" if x is None else f"{x[0]}S/{x[1]}D({x[0] + x[1]})"


def load(roots):
    """-> rows of (group, roster) and per-dual fill observations."""
    rosters = collections.defaultdict(list)          # group -> [roster size]
    fill = collections.defaultdict(collections.Counter)   # (group, "SxD") -> counters
    for root in roots:
        for gender in GENDERS:
            base = os.path.join(root, gender)
            if not os.path.isdir(base):
                continue
            prog = {r["program_id"]: r for r in csv.DictReader(open(os.path.join(base, "programs.csv")))}
            roster = collections.Counter()
            for r in csv.DictReader(open(os.path.join(base, "players.csv"))):
                roster[r["program_id"]] += 1
            for pid, n in roster.items():
                p = prog.get(pid)
                if p:
                    rosters[p["championship_group"]].append(n)
            duals = {r["dual_id"]: r for r in csv.DictReader(open(os.path.join(base, "duals.csv")))}
            slots = collections.defaultdict(set)
            for r in csv.DictReader(open(os.path.join(base, "lines.csv"))):
                slots[r["dual_id"]].add(r["slot"])
            side = collections.defaultdict(lambda: collections.defaultdict(set))
            lineof = {}
            for r in csv.DictReader(open(os.path.join(base, "lines.csv"))):
                lineof[r["line_id"]] = r["dual_id"]
            for r in csv.DictReader(open(os.path.join(base, "line_players.csv"))):
                did = lineof.get(r["line_id"])
                if did:
                    side[did][r["side"]].add(r["player_id"])
            for did, sl in slots.items():
                d = duals.get(did)
                if not d or d.get("level") != "v":
                    continue
                S = sum(1 for s in sl if s[0] == "S")
                D = sum(1 for s in sl if s[0] == "D")
                shape = f"{S}S/{D}D"
                for which, pid in (("home", d["home_program_id"]), ("away", d["away_program_id"])):
                    g = prog.get(pid, {}).get("championship_group")
                    if not g:
                        continue
                    used = len(side[did][which])
                    c = fill[(g, shape)]
                    c["sides"] += 1
                    c["short"] += (used < S + 2 * D)
    return rosters, fill


def main(roots):
    rosters, fill = load(roots)
    n5 = sorted(rosters["5A"])
    N = len(n5)
    print(f"5A: {N} program-seasons across {len(roots)} export(s), both genders\n")

    print("=== On-court demand, and 5A headroom ===")
    print(f"{'shape':16} {'courts':>6} {'on court':>9} {'min spare':>10} {'median':>7} {'% short':>8}")
    for name, (S, D) in [("3S/2D", (3, 2)), ("2S/3D", (2, 3)), ("1S/4D (old)", (1, 4)),
                         ("3S/4D", (3, 4)), ("4S/4D", (4, 4)), ("3S/5D", (3, 5)),
                         ("4S/5D", (4, 5)), ("6S/5D (rule 2094)", (6, 5))]:
        on = S + 2 * D
        sp = [r - on for r in n5]
        print(f"{name:16} {S + D:6d} {on:9d} {min(sp):10d} {st.median(sp):7.1f} "
              f"{100 * sum(1 for x in sp if x < 0) / N:7.1f}%")
    print("\n  Even court counts (4S/4D, 3S/5D) can tie; 1S/4D, 3S/4D, 4S/5D and 6S/5D cannot.")

    print("\n=== Has it been done? 5A dual-sides by shape as PLAYED ===")
    for (g, shape), c in sorted(fill.items()):
        if g != "5A" or c["sides"] < 5:
            continue
        print(f"  {shape:7} {c['sides']:6d} sides   failed to fill the card: {c['short']}")

    print("\n=== What the JV ladder needs from the bands ===")
    print(f"  JV pool = roster - {VARSITY_CUT} (the regular-season card; a road/State")
    print("  shape change does NOT move it). Smallest JV shape needs 5 a side.\n")
    print(f"{'class':9} {'n':>5} {'roster min':>11} {'median':>7} {'JV spare at min':>16} {'JV card':>12}")
    for g in ORDER:
        v = sorted(rosters[g])
        if not v:
            continue
        sp = v[0] - VARSITY_CUT
        print(f"{g:9} {len(v):5d} {v[0]:11d} {st.median(v):7.1f} {sp:16d} {fmt_jv(jv_format(sp)):>12}")

    print("\n=== The JV ladder is unbounded: D = (spare+1)//3, S = spare-2D ===")
    row = [f"{n:2d}->{fmt_jv(jv_format(n))}" for n in range(5, 23)]
    for i in range(0, len(row), 6):
        print("  " + "  ".join(row[i:i + 6]))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
