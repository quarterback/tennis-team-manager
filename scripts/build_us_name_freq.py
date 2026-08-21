#!/usr/bin/env python3
"""Build `generators/data/names/us_freq.json` — FREQUENCY-WEIGHTED US name pools.

Owner rule 2026-08 ("do like OOTP and other games do where more common names come
first rather than a lot of people repeating with uncommon surnames and first
names"): the name picker's flat `rng.choice` gave every name in a bucket the same
draw odds, so across a ~15,000-player JHSAA gender every first name landed ~10
uses whether it was James or Marcelino, and rare surnames repeated exactly as
often as Smith — measured on the owner's 2030 export before this existed. Real
name distributions are steeply head-heavy, and that head-heaviness is what makes
a league read as real people.

Sources (both fetched at build time; the emitted JSON is committed so runtime
never touches the network — the `build_hometowns.py` pattern):

* SURNAMES — US Census Bureau 2010 surname file (real counts for ~162k names).
  We keep the top `SURNAME_TOP` with their true counts as weights. The real mix
  is inherent: Garcia/Rodriguez/Martinez sit at their genuine ranks, which also
  retires the old failure mode where a 182-name hispanic bucket at 11% weight
  put Reyes/Flores/Cruz at the top of every league.
* FIRST NAMES — SSA top-1000 lists per sex for birth years 2010-2018 (via the
  aruljohn/popular-baby-names GitHub mirror; ssa.gov blocks non-browser
  fetches). The mirror carries RANKS, not counts, so counts are reconstructed
  from the real SSA rank-share curve (log-log interpolation through measured
  anchors: the #1 name is ~1.0% of a birth-year's names, #10 ~0.7%, #100
  ~0.16%, #1000 ~0.011%). Names are scored across all fetched years, so a kid
  entering high school in the 2030s draws from the cohorts actually born then.

The consumer (`generators.names.draw_us_weighted`) BLENDS this file with the
legacy curated buckets (`US_FREQ_SHARE` there): the weighted head gives common
names their real prominence, the legacy flat draw keeps the curated long tail
and regional flavor alive underneath it.

Usage: python3 scripts/build_us_name_freq.py  (writes the JSON in place)
"""
from __future__ import annotations

import io
import json
import math
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "generators" / "data" / "names" / "us_freq.json"

CENSUS_URL = "https://www2.census.gov/topics/genealogy/2010surnames/names.zip"
SSA_MIRROR = ("https://raw.githubusercontent.com/aruljohn/popular-baby-names/"
              "master/{year}/{sex}_names_{year}.json")
SSA_YEARS = (2010, 2012, 2014, 2016, 2018)
SURNAME_TOP = 20_000        # ~76% cumulative coverage of the US population

# The real SSA rank->share curve, measured off the published national files:
# (rank, share of that birth-year's top-1000 names). Interpolated log-log.
_RANK_ANCHORS = ((1, 0.0100), (10, 0.0070), (100, 0.0016), (1000, 0.00011))

# Census strips apostrophes and spaces; restore the famous ones so the emitted
# names read like names. Everything else gets plain title case.
_RECASE = {
    "OBRIEN": "O'Brien", "OCONNOR": "O'Connor", "ONEILL": "O'Neill",
    "ONEAL": "O'Neal", "ODONNELL": "O'Donnell", "OCONNELL": "O'Connell",
    "OMALLEY": "O'Malley", "OROURKE": "O'Rourke", "OKEEFE": "O'Keefe",
    "OLEARY": "O'Leary", "OSHEA": "O'Shea", "OSULLIVAN": "O'Sullivan",
    "OHARA": "O'Hara", "OREILLY": "O'Reilly", "OTOOLE": "O'Toole",
    "OBRIAN": "O'Brian", "OGRADY": "O'Grady", "OBANNON": "O'Bannon",
    "DELACRUZ": "De La Cruz", "DELAROSA": "De La Rosa", "DELEON": "De Leon",
    "DELATORRE": "De La Torre", "DELOSSANTOS": "De Los Santos",
    "DELAGARZA": "De La Garza", "DELVALLE": "Del Valle", "DELRIO": "Del Rio",
    "DELTORO": "Del Toro", "DELACERDA": "De La Cerda", "DELAO": "De La O",
    "VANDYKE": "Van Dyke", "VANHORN": "Van Horn", "VANBUREN": "Van Buren",
    "VANWINKLE": "Van Winkle", "VANMETER": "Van Meter", "VANPELT": "Van Pelt",
    "STCLAIR": "St. Clair", "STJOHN": "St. John", "STPIERRE": "St. Pierre",
    "LAFLEUR": "LaFleur", "LEBLANC": "LeBlanc", "LAROSE": "LaRose",
    "DIMAGGIO": "DiMaggio", "DEANGELIS": "DeAngelis", "DELUCA": "DeLuca",
    "MACDONALD": "MacDonald", "MACKENZIE": "MacKenzie", "MACLEOD": "MacLeod",
}


def _recase(up: str) -> str:
    if up in _RECASE:
        return _RECASE[up]
    if up.startswith("MC") and len(up) > 2:
        return "Mc" + up[2:].title()
    return up.title()


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def _rank_share(rank: int) -> float:
    """Log-log interpolation of the real SSA rank->share curve."""
    lr = math.log(rank)
    for (r1, s1), (r2, s2) in zip(_RANK_ANCHORS, _RANK_ANCHORS[1:]):
        if rank <= r2:
            t = (lr - math.log(r1)) / (math.log(r2) - math.log(r1))
            return math.exp(math.log(s1) + t * (math.log(s2) - math.log(s1)))
    return _RANK_ANCHORS[-1][1]


def build_surnames() -> dict[str, float]:
    raw = _fetch(CENSUS_URL)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
        text = z.read(csv_name).decode("utf-8", "replace")
    out: dict[str, float] = {}
    for i, line in enumerate(text.splitlines()):
        if i == 0 or not line.strip():
            continue
        parts = line.split(",")
        name, count = parts[0].strip(), parts[2]
        if name == "ALL OTHER NAMES" or len(name) < 2 or not name.isalpha():
            continue
        out[_recase(name)] = float(count)
        if len(out) >= SURNAME_TOP:
            break
    return out


def build_firsts(sex: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for year in SSA_YEARS:
        doc = json.loads(_fetch(SSA_MIRROR.format(year=year, sex=sex)))
        for rank, name in enumerate(doc["names"], 1):
            scores[name] = scores.get(name, 0.0) + _rank_share(rank)
    return scores


def main() -> None:
    surnames = build_surnames()
    boys = build_firsts("boy")
    girls = build_firsts("girl")
    doc = {
        "_doc": [
            "FREQUENCY-WEIGHTED US name pools — see scripts/build_us_name_freq.py.",
            "Weights are real US Census 2010 surname counts and SSA top-1000",
            "rank-shares summed over birth years 2010-2018. Consumed by",
            "generators.names.draw_us_weighted, BLENDED with the legacy curated",
            "buckets; regenerate with the build script, never hand-edit.",
        ],
        "male_first": boys,
        "female_first": girls,
        "surnames": surnames,
    }
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  male firsts {len(boys)}, female firsts {len(girls)}, "
          f"surnames {len(surnames)}")


if __name__ == "__main__":
    sys.exit(main())
