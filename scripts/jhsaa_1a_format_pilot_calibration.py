#!/usr/bin/env python3
"""Offline calibration for the proposed 1A pilot: state postseason (+ showcases)
moved from 1S/4D to 2S/3D, TOC unchanged (1A reverts to 1S/4D for the TOC, per
owner ruling). Reads real 1A rosters, arranges BOTH shapes off the same frozen
Order of Ability, and reports:

  1. PARTICIPATION — who is cut entirely from the postseason 8 under 2S/3D that
     would have dressed under 1S/4D's 9, and how close they were to making it.
  2. COMPETITIVENESS — same statewide pairings, simulated under both shapes with
     matching seeds, to see whether 2S/3D produces different results than 1S/4D
     for the same two rosters (concordance, upset rate, margin distribution).

Anti-stacking rule for 2S/3D used here (owner spec, this session): S1 is always
rank #1; S2 is WHICHEVER of ranks #2-#4 plays best there (a real choice, unlike
1S/4D's forced S1+D1 top-3 pooling) with the other two of #2-#4 forming D1; D2/D3
come from #5-#8 by the SAME partition-search + rank-sum-boundary ordering
`_arrange_state` already uses for D2-D4. This is NOT wired into the live game —
it is a standalone reimplementation for measurement only.

    python3 scripts/jhsaa_1a_format_pilot_calibration.py
"""
import collections
import os
import random
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _REPO)
os.environ.setdefault("TENNIS_DB_PATH", os.path.join(_REPO, ".format-pilot-tmp.db"))

from app import jhsaa as jh                                     # noqa: E402
from engine.dual import DualFormat, Team, simulate_dual         # noqa: E402
from engine.doubles import doubles_rating                       # noqa: E402

YEAR = 2039
SALT = "format-pilot-2027-08"
FMT_14 = DualFormat(n_singles=1, n_doubles=4, doubles_team_point=False)
FMT_23 = DualFormat(n_singles=2, n_doubles=3, doubles_team_point=False)


def order_program(school) -> list:
    roster = jh.build_roster(school, YEAR, SALT)
    return sorted(roster, key=lambda p: (-jh.ladder_score(p, None), -p.str_value()))


def arrange_2s3d(eight: list) -> list:
    """[S1, S2, D1a, D1b, D2a, D2b, D3a, D3b]. S1 is fixed at rank #1; S2 is the
    best-scoring choice among ranks #2-#4 (the other two form D1); D2/D3 replay
    `_arrange_state`'s partition-search + rank-sum-boundary ordering on #5-#8."""
    eng = {p.pid: p.engine_player() for p in eight}
    rank = {p.pid: i + 1 for i, p in enumerate(eight)}

    def pr(a, b):
        return doubles_rating(eng[a.pid], eng[b.pid])

    s1 = eight[0]
    cand = eight[1:4]                                  # ranks #2-#4

    def cfg_score(i):
        s2 = cand[i]
        d = [p for j, p in enumerate(cand) if j != i]
        return eng[s2.pid].overall + pr(d[0], d[1])

    i = max(range(3), key=lambda i: (cfg_score(i), -i))
    s2 = cand[i]
    d1 = [p for j, p in enumerate(cand) if j != i]

    rest = eight[4:8]

    def part_key(part):
        return (-sum(pr(a, b) for a, b in part),
                [rank[a.pid] + rank[b.pid] for a, b in part])

    pairs = min(jh._pair_partitions(rest), key=part_key)
    pairs = jh._order_pairs(
        pairs,
        {jh._pk(pp): rank[pp[0].pid] + rank[pp[1].pid] for pp in pairs},
        {jh._pk(pp): pr(*pp) for pp in pairs})
    out = [s1, s2] + list(d1)
    for a, b in pairs:
        out += [a, b]
    return out


def make_team(name: str, lineup: list, fmt: DualFormat) -> Team:
    singles = [p.engine_player() for p in lineup[:fmt.n_singles]]
    dbl = [p.engine_player()
           for p in lineup[fmt.n_singles:fmt.n_singles + 2 * fmt.n_doubles]]
    return Team(name=name, singles=singles,
                doubles=[(2 * i, 2 * i + 1) for i in range(fmt.n_doubles)],
                doubles_players=dbl)


def main() -> None:
    programs = []             # (gender, school, ranked_roster)
    for gender in jh.GENDERS:
        for school in jh.load_schools(gender):
            if school.group != "1A":
                continue
            ranked = order_program(school)
            if len(ranked) < 9:
                continue      # can't field a real postseason nine; excluded, reported
            programs.append((gender, school, ranked))

    print(f"1A programs with a full postseason nine: {len(programs)} "
          f"(girls {sum(1 for g,_,_ in programs if g=='girls')}, "
          f"boys {sum(1 for g,_,_ in programs if g=='boys')})")

    # --- 1. PARTICIPATION -----------------------------------------------------
    cut_gaps, cut_ovrs, s2_from_rank = [], [], collections.Counter()
    for gender, school, ranked in programs:
        nine, eight = ranked[:9], ranked[:8]
        rank8_ovr = eight[-1].current_overall()
        rank9_ovr = nine[-1].current_overall()
        cut_ovrs.append(rank9_ovr)
        cut_gaps.append(rank8_ovr - rank9_ovr)
        arr23 = arrange_2s3d(eight)
        s2 = arr23[1]
        s2_rank = eight.index(s2) + 1        # 2..4
        s2_from_rank[s2_rank] += 1

    print("\n--- PARTICIPATION -----------------------------------------------")
    print(f"Player cut entirely from the postseason 8 (was seat #9 of 9):")
    print(f"  mean OVR {statistics.mean(cut_ovrs):.1f}  "
          f"median {statistics.median(cut_ovrs):.1f}")
    print(f"  mean gap to the last player who DOES dress (seat #8): "
          f"{statistics.mean(cut_gaps):.2f} OVR "
          f"(median {statistics.median(cut_gaps):.2f})")
    within2 = sum(1 for g in cut_gaps if g <= 2.0)
    print(f"  within 2 OVR of the roster (a real, close call): "
          f"{within2}/{len(cut_gaps)} programs ({within2/len(cut_gaps):.0%})")
    print(f"Who plays the new S2 court (by rank among the postseason eight):")
    for rk in (2, 3, 4):
        n = s2_from_rank[rk]
        print(f"  rank #{rk}: {n} programs ({n/len(programs):.0%})")

    # --- 2. COMPETITIVENESS ----------------------------------------------------
    print("\n--- COMPETITIVENESS (same pairings, both formats, matching seeds) -")
    for gender in jh.GENDERS:
        pool = [(s, r) for g, s, r in programs if g == gender]
        pool.sort(key=lambda sr: -statistics.mean(
            p.current_overall() for p in sr[1][:9]))
        half = len(pool) // 2
        adjacent = [(pool[i], pool[i + 1]) for i in range(0, len(pool) - 1, 2)]
        mismatched = list(zip(pool[:half], reversed(pool[half:])))
        for label, pairs in (("evenly matched (adjacent-strength)", adjacent),
                             ("mismatched (top half vs bottom half)", mismatched)):
            _run_pairings(gender, label, pairs)


def _run_pairings(gender: str, label: str, pairs: list) -> None:
        concord = upsets14 = upsets23 = nailbiters14 = nailbiters23 = 0
        margins14, margins23 = [], []
        for (sa, ra), (sb, rb) in pairs:
            nine_a, nine_b = ra[:9], rb[:9]
            eight_a, eight_b = ra[:8], rb[:8]
            arr_a14 = jh._arrange_state(nine_a, {})
            arr_b14 = jh._arrange_state(nine_b, {})
            arr_a23 = arrange_2s3d(eight_a)
            arr_b23 = arrange_2s3d(eight_b)
            seed = abs(hash((sa.name, sb.name))) % (2**31)
            res14 = simulate_dual(make_team(sa.name, arr_a14, FMT_14),
                                  make_team(sb.name, arr_b14, FMT_14),
                                  seed=seed, play_all=True, fidelity=jh.FIDELITY,
                                  dual_fmt=FMT_14, singles_fmt=jh.MATCH_FORMAT,
                                  doubles_fmt=jh.MATCH_FORMAT)
            res23 = simulate_dual(make_team(sa.name, arr_a23, FMT_23),
                                  make_team(sb.name, arr_b23, FMT_23),
                                  seed=seed, play_all=True, fidelity=jh.FIDELITY,
                                  dual_fmt=FMT_23, singles_fmt=jh.MATCH_FORMAT,
                                  doubles_fmt=jh.MATCH_FORMAT)
            fav_a = statistics.mean(p.current_overall() for p in nine_a) >= \
                    statistics.mean(p.current_overall() for p in nine_b)
            win14_a, win23_a = res14.winner == 0, res23.winner == 0
            if win14_a == win23_a:
                concord += 1
            if win14_a != fav_a:
                upsets14 += 1
            if win23_a != fav_a:
                upsets23 += 1
            m14 = abs(res14.home_points - res14.away_points)
            m23 = abs(res23.home_points - res23.away_points)
            margins14.append(m14)
            margins23.append(m23)
            if m14 <= 1:
                nailbiters14 += 1
            if m23 <= 1:
                nailbiters23 += 1
        n = len(pairs)
        print(f"\n{gender} — {n} pairings, {label}:")
        print(f"  same winner under both formats: {concord}/{n} ({concord/n:.0%})")
        print(f"  upset rate (weaker team by OVR wins): "
              f"1S/4D {upsets14/n:.0%} · 2S/3D {upsets23/n:.0%}")
        print(f"  mean margin (of 5 total points): "
              f"1S/4D {statistics.mean(margins14):.2f} · "
              f"2S/3D {statistics.mean(margins23):.2f}")
        print(f"  nailbiters (decided by 1 pt, e.g. 3-2): "
              f"1S/4D {nailbiters14}/{n} ({nailbiters14/n:.0%}) · "
              f"2S/3D {nailbiters23}/{n} ({nailbiters23/n:.0%})")


if __name__ == "__main__":
    main()
