#!/usr/bin/env python3
"""Real-world targets for lineup grade composition and ladder churn.

    python3 scripts/oregon_lineup_shape.py <clone of quarterback/or-tennis-data>

Reads six seasons of real OSAA varsity results (2021-2026) and answers the two
questions the development redesign is graded against:

  * what share of each lineup seat — especially No. 1 singles — is held by
    freshmen, sophomores, juniors and seniors, and
  * how often a returning No. 1 keeps the seat.

Both are computed here EXACTLY as `scripts/dev_model_access_experiment.py`
computes them for the sim, so the two are directly comparable.

‼️ THE DATA HAS NO GRADE FIELD, AND THE ONE THAT LOOKS LIKE IT IS NOT ONE.
Every player carries `grade`, but it is CURRENT status — 99% of rows read
"Graduated" — and the accompanying `graduatedDate` is largely a bulk data-entry
stamp (thousands of players across 2021-2023 seasons carry the same 2025 date).
Deriving grade from it puts 30.8% of appearances outside grades 9-12. Do not use
it; this script never reads either field.

Grade is instead inferred from each player's own appearance span, which has no
unbiased single form, so three passes bracket the answer:

  UPPER  assume a player's LAST season was their senior year. Every player who
         quits before senior year is then counted as a senior, and 51% of
         players appear in only one season, so this is a hard OVER-count of
         seniors.
  LOWER  assume a player's FIRST season was their freshman year. Everyone who
         takes up the sport late is then counted as a freshman — a hard
         UNDER-count of seniors. (2021 was COVID-shortened, ~46% of a normal
         season's appearances, so a 2022 "debut" may be a 2021 freshman who
         never played. Careers are therefore only counted from 2022.)
  EXACT  players with a full four-season career inside the window. Both
         assumptions agree, so the grades are certain rather than inferred.
         Selected for four-year players and so tilted toward committed ones,
         but it is the only pass with no inference in it.

Read the EXACT pass as the target and the other two as the bracket around it.

The churn measure needs no grade at all and is therefore free of all of this: a
school-season's No. 1 is the player with the most No. 1 singles appearances, and
retention asks how often that player, when they are on the roster again the
next season, is still the No. 1.

Regular season only (`postSeason` meets dropped, as the sim's ladder metrics
drop the postseason). Varsity only for the grade composition and the No. 1
counters; ROSTER MEMBERSHIP is collected at any level, so a No. 1 demoted to JV
counts as losing the seat rather than dropping out of the sample. (In the 2021-26
dataset every one of the 120,582 matches carries `isNotVarsity: false`, so that
split currently changes no number — it is correctness for a dataset that gains
JV rows, not a restatement of the figures.)

Retention is scoped to the SAME PROGRAM: a No. 1 who transfers is not a
returning No. 1, and must not count their old school's new No. 1 as a failure.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re

GENDERS = ((1, "boys"), (2, "girls"))
GRADES = (9, 10, 11, 12)


def read(root: str):
    """(appearances, seasons_by_player, s1_by_team, roster_by_team)."""
    rows = []
    seasons = collections.defaultdict(set)
    s1 = collections.defaultdict(collections.Counter)
    roster = collections.defaultdict(set)
    pat = re.compile(r"[/\\](\d{4})[/\\]")
    for f in sorted(glob.glob(os.path.join(root, "data", "*", "school_*_gender_*.json"))):
        m = pat.search(f)
        if not m:
            continue
        yr = int(m.group(1))
        try:
            with open(f) as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        for meet in d.get("meets") or []:
            if meet.get("postSeason"):
                continue
            for lst in (meet.get("matches") or {}).values():
                if not isinstance(lst, list):
                    continue
                for mm in lst:
                    # ‼️ ROSTER MEMBERSHIP IS COLLECTED BEFORE THE VARSITY
                    # FILTER, the No. 1 counters after it. Retention asks "the
                    # No. 1 came back — did they keep the seat?", and a player
                    # demoted all the way to JV is the STRONGEST case of losing
                    # it. Skipping their non-varsity appearances before building
                    # `roster` dropped them from the denominator entirely, so
                    # exactly the clearest lost-seat cases were excluded and the
                    # reported retention was biased UPWARD.
                    varsity = not mm.get("isNotVarsity")
                    mt, fl = mm.get("matchType"), str(mm.get("flight"))
                    top = varsity and mt == "Singles" and fl == "1"
                    for team in mm.get("matchTeams") or []:
                        for p in team.get("players") or []:
                            pid, sid, g = p.get("id"), p.get("schoolId"), p.get("genderId")
                            if pid is None:
                                continue
                            if sid is not None:
                                roster[(sid, yr, g)].add(pid)   # ANY level
                            if not varsity:
                                continue
                            # everything below is the varsity-only view: the
                            # grade composition is about varsity LINES, and the
                            # grade inference reads varsity career spans.
                            seasons[pid].add(yr)
                            rows.append((yr, pid, g, mt, fl))
                            if sid is not None and top:
                                s1[(sid, yr, g)][pid] += 1
    return rows, seasons, s1, roster


def composition(rows, keep, grade_of, label: str) -> None:
    for gid, gname in GENDERS:
        allc, s1c, players = collections.Counter(), collections.Counter(), set()
        for yr, pid, g, mt, fl in rows:
            if g != gid or not keep(pid):
                continue
            gr = grade_of(pid, yr)
            if gr not in GRADES:
                continue
            players.add(pid)
            allc[gr] += 1
            if mt == "Singles" and fl == "1":
                s1c[gr] += 1
        n, m = sum(allc.values()), sum(s1c.values())
        if not n or not m:
            continue
        print(f"  {label:26s} {gname:5s}  players={len(players)}")
        print(f"     every varsity line  n={n:6d}   "
              + "   ".join(f"{k}:{allc[k]/n:5.1%}" for k in GRADES))
        print(f"     No. 1 singles       n={m:6d}   "
              + "   ".join(f"{k}:{s1c[k]/m:5.1%}" for k in GRADES))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="clone of quarterback/or-tennis-data")
    args = ap.parse_args()

    rows, seasons, s1, roster = read(args.root)
    first = {p: min(v) for p, v in seasons.items()}
    last = {p: max(v) for p, v in seasons.items()}
    yrs = sorted({r[0] for r in rows})
    per_year = collections.Counter(r[0] for r in rows)
    print(f"seasons {yrs[0]}-{yrs[-1]}   appearances {len(rows)}   players {len(seasons)}")
    print("appearances by season: " + ", ".join(f"{y} {per_year[y]}" for y in yrs))
    span = collections.Counter(len(v) for v in seasons.values())
    print("career length: " + ", ".join(f"{k} season(s) {span[k]}" for k in sorted(span)))

    end = yrs[-1]
    print("\nUPPER BOUND on seniors — last season assumed to be grade 12")
    composition(rows, lambda p: last[p] < end, lambda p, y: 12 - (last[p] - y),
                "last=12, done by " + str(end - 1))
    print("\nLOWER BOUND on seniors — first season assumed to be grade 9")
    composition(rows, lambda p: first[p] >= yrs[0] + 1, lambda p, y: 9 + (y - first[p]),
                f"first=9, began {yrs[0]+1}+")
    print("\nEXACT — full four-season careers; both assumptions agree, no inference")
    composition(rows,
                lambda p: len(seasons[p]) == 4 and first[p] >= yrs[0] + 1 and last[p] < end,
                lambda p, y: 9 + (y - first[p]), "4-season cohort")

    print("\nLADDER CHURN — needs no grade, so none of the above applies")
    no1 = {k: c.most_common(1)[0][0] for k, c in s1.items() if c}
    for gid, gname in GENDERS:
        held = n = came = tot = 0
        for (sid, yr, g), pid in no1.items():
            if g != gid:
                continue
            # ‼️ SAME PROGRAM, ANY LEVEL. `roster` is keyed on (school, year,
            # gender), so this asks whether the player is back at THIS school —
            # a transfer is not a returning No. 1 and must not count the new
            # No. 1 as a retention failure. And `roster` now includes JV
            # appearances, so a No. 1 demoted off varsity counts as losing the
            # seat rather than dropping out of the sample.
            nxt = (sid, yr + 1, g)
            if nxt in no1 and pid in roster.get(nxt, ()):
                n += 1
                held += no1[nxt] == pid
            prev = (sid, yr - 1, g)
            if prev in roster:
                tot += 1
                came += pid in roster[prev]
        print(f"  {gname:5s} a returning No. 1 keeps the seat: {held/n:5.1%}  (n={n})")
        print(f"  {gname:5s} No. 1s who were on last year's roster: {came/tot:5.1%}  (n={tot})")


if __name__ == "__main__":
    main()
