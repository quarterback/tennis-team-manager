#!/usr/bin/env python3
"""Calibration for the 1A road-to-State pilot: 1S/4D -> 2S/3D (TOC stays 1S/4D,
regular season and showcases untouched — see `app/jhsaa.py`'s FORMATS docstring).
Reads real 1A rosters and, unlike the first draft of this script, calls the
SHIPPED production functions directly (`jh.dual_format`, `jh._arrange_state`,
`jh._arrange_1a_postseason`) rather than a parallel reimplementation, so this
measures the actual code path, not a stand-in for it. Reports:

  1. PARTICIPATION — who is cut entirely from the postseason 8 under 2S/3D that
     would have dressed under 1S/4D's 9, and how close they were to making it;
     who plays the new S2 court (by rank in the top-4 anti-stacking pool).
  2. COMPETITIVENESS — same statewide pairings, simulated under both shapes with
     matching seeds, to see whether 2S/3D produces different results than 1S/4D
     for the same two rosters (concordance, upset rate, margin distribution).

‼️ THE SEED MUST BE A STABLE DIGEST, NEVER `hash()`. Python salts `hash()` of
str/tuple per PROCESS (`PYTHONHASHSEED`), so a `hash((name_a, name_b))` seed
changes on every ordinary invocation and makes this report irreproducible — a
review with `PYTHONHASHSEED=1` vs `=2` moved concordance up to 8 points and
upset rate up to 16. `_pair_seed` below uses `hashlib.blake2s`, the idiom this
module already uses everywhere else it needs a stable per-entity seed
(`_coach_strategy`, `neglect_severity`, ...).

    python3 scripts/jhsaa_1a_format_pilot_calibration.py
"""
import argparse
import hashlib
import os
import statistics
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _REPO)

# ‼️ HERMETIC BY CONSTRUCTION — an EMPTY throwaway database, never `setdefault`.
# `build_roster` reads the override tables (archetype, play-up, transfer), so the
# rosters this script measures — and therefore every number it prints — depend on
# whatever those tables hold. `setdefault` let an inherited TENNIS_DB_PATH win
# silently, which meant "run the committed script with default arguments" did NOT
# name one experiment: two people could run the same commit and get tables that
# differ by a point or two per metric, with nothing looking wrong. A calibration
# whose output is an argument has to pin its own inputs.
_DB = os.path.join(tempfile.mkdtemp(prefix="jh-1a-pilot-"), "calib.db")
os.environ["TENNIS_DB_PATH"] = _DB

from app import jhsaa as jh                                     # noqa: E402
from engine.dual import Team, simulate_dual                     # noqa: E402

YEAR = 2039
SALT = "format-pilot-2027-08"


def _pair_seed(name_a: str, name_b: str, trial: int = 0) -> int:
    """A stable, reproducible seed for one pairing — never Python's `hash()`,
    which is salted per-process and would make this report irreproducible.

    `trial` re-rolls the SAME pairing under a different seed. One seed per
    pairing gives ~45 duals a cell, which is far too few to separate a real
    format effect from dual-to-dual variance — the first run of this script
    reported the nailbiter rate moving in OPPOSITE directions by gender off
    exactly that sample. Both formats always see the same trial seed, so the
    comparison stays paired however many trials are run."""
    h = hashlib.blake2s(f"jh-1a-pilot|{name_a}|{name_b}|{trial}".encode(),
                        digest_size=4)
    return int(h.hexdigest(), 16) % (2**31)


def order_program(school) -> list:
    roster = jh.build_roster(school, YEAR, SALT)
    return sorted(roster, key=lambda p: (-jh.ladder_score(p, None), -p.str_value()))


def make_team(name: str, lineup: list, fmt) -> Team:
    singles = [p.engine_player() for p in lineup[:fmt.n_singles]]
    dbl = [p.engine_player()
           for p in lineup[fmt.n_singles:fmt.n_singles + 2 * fmt.n_doubles]]
    return Team(name=name, singles=singles,
                doubles=[(2 * i, 2 * i + 1) for i in range(fmt.n_doubles)],
                doubles_players=dbl)


def _positive(v: str) -> int:
    """`--trials` must be >= 1. Left unvalidated, 0 or a negative value builds
    every roster, runs no duals, and dies on a ZeroDivisionError while printing
    the FIRST result cell — minutes of setup for a traceback. Fail at parse."""
    n = int(v)
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {n}")
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trials", type=_positive, default=20,
                    help="duals simulated per pairing per format (default 20). "
                         "One is far too few to separate a format effect from "
                         "dual-to-dual variance.")
    trials = ap.parse_args().trials
    # Provenance, so a pasted table can always be traced back to what produced it.
    # A number in a document that cannot be tied to a commit is an assertion, not
    # evidence — and this report's figures have already been queried once.
    try:
        rev = subprocess.run(["git", "-C", _REPO, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "-C", _REPO, "status", "--porcelain"],
                               capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:                       # git absent / not a checkout — not fatal
        rev, dirty = "", ""
    print(f"commit {rev or '(unknown)'}{' +dirty' if dirty else ''} · "
          f"trials {trials} · year {YEAR} · salt {SALT!r} · empty db")

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
    cut_gaps, cut_ovrs = [], []
    s2_from_rank = {2: 0, 3: 0, 4: 0}
    for gender, school, ranked in programs:
        nine, eight = ranked[:9], ranked[:8]
        rank8_ovr = eight[-1].current_overall()
        rank9_ovr = nine[-1].current_overall()
        cut_ovrs.append(rank9_ovr)
        cut_gaps.append(rank8_ovr - rank9_ovr)
        arr23 = jh._arrange_1a_postseason(eight, {})
        s2 = arr23[1]
        s2_rank = eight.index(s2) + 1        # 1..4 (1 would mean S1 chose S2 seat too)
        s2_from_rank[s2_rank] = s2_from_rank.get(s2_rank, 0) + 1

    print("\n--- PARTICIPATION -----------------------------------------------")
    print("Player cut entirely from the postseason 8 (was seat #9 of 9):")
    print(f"  mean OVR {statistics.mean(cut_ovrs):.1f}  "
          f"median {statistics.median(cut_ovrs):.1f}")
    print(f"  mean gap to the last player who DOES dress (seat #8): "
          f"{statistics.mean(cut_gaps):.2f} OVR "
          f"(median {statistics.median(cut_gaps):.2f})")
    within2 = sum(1 for g in cut_gaps if g <= 2.0)
    print(f"  within 2 OVR of the roster (a real, close call): "
          f"{within2}/{len(cut_gaps)} programs ({within2/len(cut_gaps):.0%})")
    print("Who plays the new S2 court (by rank in the top-4 anti-stacking pool):")
    for rk in sorted(s2_from_rank):
        n = s2_from_rank[rk]
        print(f"  rank #{rk}: {n} programs ({n/len(programs):.0%})")

    # --- 2. COMPETITIVENESS ----------------------------------------------------
    print(f"\n--- COMPETITIVENESS (same pairings, both formats, stable seeds,\n    {trials} trials each) ---")
    for gender in jh.GENDERS:
        pool = [(s, r) for g, s, r in programs if g == gender]
        pool.sort(key=lambda sr: -statistics.mean(
            p.current_overall() for p in sr[1][:9]))
        half = len(pool) // 2
        adjacent = [(pool[i], pool[i + 1]) for i in range(0, len(pool) - 1, 2)]
        mismatched = list(zip(pool[:half], reversed(pool[half:])))
        for label, pairs in (("evenly matched (adjacent-strength)", adjacent),
                             ("mismatched (top half vs bottom half)", mismatched)):
            _run_pairings(gender, label, pairs, trials)


def _run_pairings(gender: str, label: str, pairs: list, trials: int = 1) -> None:
    concord = upsets14 = upsets23 = nailbiters14 = nailbiters23 = 0
    margins14, margins23 = [], []
    fmt14 = jh.dual_format("state", None)
    fmt23 = jh.dual_format("state", "1A")
    for (sa, ra), (sb, rb) in pairs:
        nine_a, nine_b = ra[:9], rb[:9]
        eight_a, eight_b = ra[:8], rb[:8]
        # Arranged ONCE per pairing, outside the trial loop: the lineup is a
        # function of the frozen order, not of the dual's seed.
        arr_a14 = jh._arrange_state(nine_a, {})
        arr_b14 = jh._arrange_state(nine_b, {})
        arr_a23 = jh._arrange_1a_postseason(eight_a, {})
        arr_b23 = jh._arrange_1a_postseason(eight_b, {})
        fav_a = statistics.mean(p.current_overall() for p in nine_a) >= \
                statistics.mean(p.current_overall() for p in nine_b)
        for t in range(trials):
            seed = _pair_seed(sa.name, sb.name, t)
            res14 = simulate_dual(make_team(sa.name, arr_a14, fmt14),
                                  make_team(sb.name, arr_b14, fmt14),
                                  seed=seed, play_all=True, fidelity=jh.FIDELITY,
                                  dual_fmt=fmt14, singles_fmt=jh.MATCH_FORMAT,
                                  doubles_fmt=jh.MATCH_FORMAT)
            res23 = simulate_dual(make_team(sa.name, arr_a23, fmt23),
                                  make_team(sb.name, arr_b23, fmt23),
                                  seed=seed, play_all=True, fidelity=jh.FIDELITY,
                                  dual_fmt=fmt23, singles_fmt=jh.MATCH_FORMAT,
                                  doubles_fmt=jh.MATCH_FORMAT)
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
    n = len(pairs) * trials
    print(f"\n{gender} — {len(pairs)} pairings × {trials} "
          f"trial{'s' if trials != 1 else ''} = {n} duals, {label}:")
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
