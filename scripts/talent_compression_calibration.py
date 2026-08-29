"""Measure the ceiling compression (development.compress_talent) against the
uncompressed draw — the numbers behind docs/AAR-talent-compression.md.

Builds every JHSAA roster for a season twice (talent_era forced off, then on)
and generates a national recruit class both ways, reporting the top of each
distribution in grade / STR / UTR terms plus elite counts and star tiers.
Deterministic (the era gate is the only variable), so one pass per salt is a
census, not a sample — add salts to see world-to-world variance.

Usage: python3 scripts/talent_compression_calibration.py [--year 2050] [--salt S]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import jhsaa as jh                                    # noqa: E402
from app.development import (TALENT_CAP, overall_to_str,        # noqa: E402
                             compress_talent, elite_talent)


def utr(grade: float) -> float:
    return round(1.0 + (overall_to_str(grade) - 31.0) / 26.0 * 15.5, 2)


def _jhsaa_census(gender: str, year: int, salt: str) -> dict:
    ceils, currents, elites = [], [], 0
    for school in jh.load_schools(gender):
        for p in jh.build_roster(school, year, salt):
            ceils.append(p.ceiling_overall())
            if p.grade == 12:
                currents.append(p.current_overall())
            key = ("jhsaa-elite", school.ident, school.gender, p.entry_year,
                   jh.resolve_seat(school, p.entry_year, p.pid))
            if elite_talent(key):
                elites += 1
    ceils.sort(reverse=True)
    currents.sort(reverse=True)
    cap = TALENT_CAP["male" if gender == "boys" else "female"]
    return {"n": len(ceils),
            "ceil_max": ceils[0], "ceil_top100": sum(ceils[:100]) / 100,
            "over_cap": sum(1 for c in ceils if c > cap + 0.01),
            "sr_max": currents[0] if currents else 0,
            "sr_top100": sum(currents[:100]) / max(1, min(100, len(currents))),
            "elites": elites}


def _pool_census(gender: str, year: int) -> dict:
    import random
    from app.juniors import generate_class
    cls = generate_class(random.Random(year), n=2500, grad_year=year,
                         gender=gender)
    ceils = sorted((p.ceiling_overall() for p in cls.recruits), reverse=True)
    stars = [p.star_rating() for p in cls.recruits]
    cap = TALENT_CAP[gender]
    return {"n": len(ceils), "ceil_max": ceils[0],
            "ceil_top100": sum(ceils[:100]) / 100,
            "over_cap": sum(1 for c in ceils if c > cap + 0.01),
            "five_star": sum(1 for s in stars if s == 5)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2050)
    ap.add_argument("--salt", default="")
    args = ap.parse_args()

    print("== JHSAA (full association, both eras) ==")
    for gender in ("boys", "girls"):
        rows = {}
        for label, era in (("legacy", 9999), ("compressed", 0)):
            jh.talent_era = (lambda e: (lambda: e))(era)   # force the gate
            jh.reset_schools()
            rows[label] = _jhsaa_census(gender, args.year, args.salt)
        for label, r in rows.items():
            print(f"  {gender:5} {label:10} n={r['n']:5}  "
                  f"top ceiling {r['ceil_max']:.1f} (UTR {utr(r['ceil_max'])})  "
                  f"top-100 ceil {r['ceil_top100']:.1f} (UTR {utr(r['ceil_top100'])})  "
                  f"over-cap {r['over_cap']:4}  elites {r['elites']:3}  "
                  f"best senior {r['sr_max']:.1f} (UTR {utr(r['sr_max'])})  "
                  f"sr top-100 {r['sr_top100']:.1f} (UTR {utr(r['sr_top100'])})")

    print("== National recruit pool (compressed as shipped vs raw) ==")
    import app.juniors as jn
    real, real_trim = jn.compress_talent, jn.trim_prospect_ceiling
    for gender in ("male", "female"):
        jn.compress_talent = lambda t, g, key=None: t          # raw
        jn.trim_prospect_ceiling = lambda p, g, key=None: p
        raw = _pool_census(gender, args.year)
        jn.compress_talent, jn.trim_prospect_ceiling = real, real_trim
        comp = _pool_census(gender, args.year)
        for label, r in (("raw", raw), ("compressed", comp)):
            print(f"  {gender:6} {label:10} top ceiling {r['ceil_max']:.1f} "
                  f"(UTR {utr(r['ceil_max'])})  top-100 {r['ceil_top100']:.1f} "
                  f"(UTR {utr(r['ceil_top100'])})  over-cap {r['over_cap']:4}  "
                  f"5-star {r['five_star']:4}")


if __name__ == "__main__":
    main()
