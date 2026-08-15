#!/usr/bin/env python3
"""Rebuild the hometown pools from real place data (owner rule 2027-08: "full tilt").

The original `us_states` lists were hand-typed flavour — heavy on campus towns,
never sized against draw volume. Measured before this script existed: 33 of 55
states drew more recruits per class than they had cities (Florida 248 recruits
from 46 cities). The fix is not to hand-type more names — that is how wrong data
gets in — but to generate the pools from a real dataset and keep the curated
lists as a union on top.

Sources — two, because neither is sufficient alone:
- GeoNames cities5000 (https://download.geonames.org/export/dump/, CC-BY):
  POPULATION for every place >= 5k in all three countries. But its feature
  codes are unreliable inside big cities — it classes DC neighbourhoods
  ("NoMa", "Foggy Bottom", "Downtown DC") as ordinary populated places, so it
  cannot be the sole authority on what IS a hometown.
- US Census Gazetteer nationals (2024_Gaz_place_national + cousubs):
  LEGITIMACY. A US name only qualifies if it is a real incorporated place or
  CDP — or, in the six New England states, a county-subdivision town, since
  New England's municipalities are towns and invisible in the place file.
  Hawaii's municipalities are CDPs, which the place file carries.
US pools take the intersection (GeoNames population × Gazetteer legitimacy);
Canada and Mexico take GeoNames alone (no Gazetteer exists for them — the
fcode filter plus the population floor is the best available gate).

Rules (all measured against the game's own draw mechanics):
- `us_states` (per-state pools feeding `roll_us_hometown` + `towns_in_region`):
  a GRADUATED floor — each state keeps the highest of (10k, 5k, 2k) that still
  yields ~40 places, so big states take no hamlets while VT/WY/MT are
  represented by the towns they actually have (owner rule 2027-08).
  Weighting is POPULATION REPEATS — `roll_us_hometown` is
  a flat rng.choice, so an entry's count IS its weight (the Jefferson pattern,
  see CLAUDE.md). `towns_in_region` DEDUPES, so repeats never distort a
  program's local-roster pool; only the distinct count counts there.
- neighbourhood/section entries (fcode PPLX/PPLH/PPLQ) and slash-named
  composites are dropped: "Kalihi-Palama" is not a hometown.
- every existing hand-curated city is KEPT (union) — the campus towns
  (Saint Leo, Moraga, Cheney...) matter to this game and many sit under 10k.
- Jefferson ("JF") is fictional and NOT regenerated here — it exports all 272
  of its cities UNCAPPED (owner rule 2027-08; the old cap defended a ~150-city
  western pool that no longer exists). This script reports JF's share of the
  west; scripts/import_jefferson.py owns the list and warns if the share ever
  climbs past 35% again.
- `cities` (international birthplace pools): CA and MX are regenerated from the
  same dump (CA >= 10k, MX >= 25k). ⚠️ Additions here FEED THE SURNAME
  SCRUBBER's city blocklist (`scripts/scrub_name_pools.py _surname_cities` —
  the `cities` tier only, never `us_states`). After running this, run the
  scrubber with --check and move any real family names it would strip into
  SURNAME_CITY_KEEP.

Idempotent: same dump in, same JSON out. Run with --dry-run to print the deltas
without writing.
"""
from __future__ import annotations

import argparse
import collections
import re
import io
import json
import os
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOMETOWNS = os.path.join(ROOT, "generators", "data", "names", "hometowns.json")
DUMP_URL = "https://download.geonames.org/export/dump/cities1000.zip"

GAZ_BASE = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer"

# Graduated per-state floor (owner rule 2027-08: "i don't need tiny places in
# big states but other ones should be represented more wholly"). Each state
# keeps the HIGHEST floor that still yields TARGET_PLACES distinct places, so
# Texas never takes hamlets while Vermont and Wyoming — states without big
# cities — go down to 2k and get represented by the towns they actually have.
US_FLOORS = (10_000, 5_000, 2_000)
TARGET_PLACES = 40
CA_FLOOR = 5_000
MX_FLOOR = 15_000

# New England: municipalities are county-subdivision TOWNS, not places.
NEW_ENGLAND = {"CT", "MA", "ME", "NH", "RI", "VT"}

# Fictional state: never regenerated from real data. Its cap is proportional to
# the western pool (see CLAUDE.md "Jefferson" §) and is only REPORTED here.
SKIP_STATES = {"JF"}
JF_WEST_SHARE = 0.23     # Jefferson's population share of the region
WEST_STATES = {"CA", "OR", "WA", "AK", "HI", "BC"}   # ncaa.STATE_REGION "W", minus JF

# GeoNames feature codes that are not hometowns: sections of cities,
# historical, abandoned.
BAD_FCODES = {"PPLX", "PPLH", "PPLQ", "PPLW"}

# Repeat-as-weight: the EXACT rule scripts/import_jefferson.py already
# established for JF (one slot per 25k residents, capped) — one idiom, not two.
_POP_PER_SLOT = 25_000
_MAX_SLOTS = 12


def _repeats(pop: int) -> int:
    return max(1, min(_MAX_SLOTS, round(pop / _POP_PER_SLOT)))


def _fetch(url: str, cache: str, member: str, encoding: str) -> list[str]:
    if not os.path.exists(cache):
        print(f"fetching {url} ...")
        urllib.request.urlretrieve(url, cache)
    with zipfile.ZipFile(cache) as z:
        return z.read(member).decode(encoding).splitlines()


# Gazetteer names carry a legal designator ("Pearl City CDP", "Essex town",
# "Nashville-Davidson metropolitan government (balance)"). Strip to the bare
# name GeoNames uses.
_GAZ_STRIP = re.compile(
    r"\s*\((balance)\)\s*$|\s+(city and borough|municipality and borough|"
    r"city|town|village|borough|municipality|CDP|"
    r"comunidad|zona urbana|urbana|plantation|gore|grant|location|purchase|"
    r"census area|metropolitan government|metro government|urban county|"
    r"consolidated government|unified government)\s*$", re.IGNORECASE)


def _gaz_variants(name: str) -> set[str]:
    """Every name a Gazetteer row legitimizes. Consolidated city-counties file
    under compound names ("Nashville-Davidson metropolitan government (balance)",
    "Athens-Clarke County unified government") while GeoNames uses the plain city
    ("Nashville", "Athens") — so the first hyphen component qualifies too. The
    variant set only matters where GeoNames has a matching name, so a spurious
    variant ("Winston" from Winston-Salem) legitimizes nothing real."""
    prev = None
    while prev != name:
        prev, name = name, _GAZ_STRIP.sub("", name)
    name = name.split("/")[0].strip()      # "Louisville/Jefferson County ..." -> Louisville
    out = {name}
    if "-" in name:
        out.add(name.split("-")[0].strip())
    if name.startswith("Urban "):          # Census "Urban Honolulu" = GeoNames "Honolulu"
        out.add(name[6:])
    return {v for v in out if v}


def _norm(name: str) -> str:
    return name.replace("\u2019", "'").casefold()


def _legit_us(cache_dir: str) -> dict[str, set[str]]:
    """{state: {normalized name}} of real municipalities: every incorporated
    place and CDP nationwide, plus county-subdivision towns in New England."""
    out: dict[str, set[str]] = {}
    for stem, states in (("place", None), ("cousubs", NEW_ENGLAND)):
        rows = _fetch(f"{GAZ_BASE}/2024_Gaz_{stem}_national.zip",
                      os.path.join(cache_dir, f"gaz_{stem}.zip"),
                      f"2024_Gaz_{stem}_national.txt", "latin-1")
        for ln in rows[1:]:
            f = ln.split("\t")
            st, name = f[0].strip(), f[3].strip()
            if states is not None and st not in states:
                continue
            if stem == "cousubs" and not re.search(r"\s(town|city)$", name):
                continue
            for v in _gaz_variants(name):
                out.setdefault(st, set()).add(_norm(v))
    return out


def _places(rows: list[str]):
    """Yield (country, admin1, name, population) for hometown-grade places."""
    for ln in rows:
        f = ln.split("\t")
        if len(f) < 15 or f[7] in BAD_FCODES or f[6] != "P":
            continue
        name = f[1].strip()          # unicode name — the file stores accents
        if not name or "/" in name or name.startswith("("):
            continue
        try:
            pop = int(f[14] or 0)
        except ValueError:
            continue
        yield f[8], f[10], name, pop


def build(dry: bool, cache: str) -> None:
    with open(HOMETOWNS, encoding="utf-8") as fh:
        data = json.load(fh)
    us_states: dict[str, list[str]] = data["us_states"]
    cities: dict[str, list[str]] = data["cities"]

    cache_dir = os.path.dirname(os.path.abspath(cache)) or "."
    legit = _legit_us(cache_dir)
    best: dict[tuple[str, str, str], int] = {}
    for cc, adm, name, pop in _places(_fetch(DUMP_URL, cache, os.path.basename(DUMP_URL).replace(".zip", ".txt"), "utf-8")):
        if cc not in ("US", "CA", "MX"):
            continue
        # ⚠️ GeoNames classes big-city neighbourhoods ("NoMa", "Foggy Bottom")
        # as ordinary populated places — a US name must ALSO be a real
        # municipality in the Census Gazetteer to qualify.
        if cc == "US" and _norm(name) not in legit.get(adm, ()):
            continue
        key = (cc, adm if cc == "US" else "", name)
        if pop > best.get(key, 0):
            best[key] = pop

    # --- us_states -------------------------------------------------------------
    by_state: dict[str, dict[str, int]] = collections.defaultdict(dict)
    for (cc, adm, name), pop in best.items():
        if cc == "US" and adm and adm not in SKIP_STATES:
            by_state[adm][name] = pop

    report = []
    for st in sorted(set(by_state) | set(us_states) - SKIP_STATES):
        pool = by_state.get(st, {})
        floor = US_FLOORS[-1]
        for f in US_FLOORS:                 # highest floor that still fills the state
            if sum(1 for p in pool.values() if p >= f) >= TARGET_PLACES:
                floor = f
                break
        keep = {n: p for n, p in pool.items() if p >= floor}
        # Union with the curated list: an existing city absent from the dump (or
        # under the floor) stays, at weight 1 — curated campus towns are data.
        old = us_states.get(st, [])
        old_distinct = len(set(old))
        for n in old:
            keep.setdefault(n, 0)
        rows: list[str] = []
        for n in sorted(keep):
            rows.extend([n] * _repeats(keep[n]))
        if rows:
            us_states[st] = rows
            report.append((st, old_distinct, len(keep), len(rows), floor))

    # --- cities (international birthplaces) ------------------------------------
    intl_report = []
    for cc, floor in (("CA", CA_FLOOR), ("MX", MX_FLOOR)):
        pool = {name: pop for (c, _a, name), pop in best.items()
                if c == cc and pop >= floor}
        old = cities.get(cc, [])
        for n in old:
            pool.setdefault(n, 0)
        # `roll_hometown` is a flat rng.choice too (flavor.py:206), so the
        # birthplace pools take the same population repeats as the states.
        rows = []
        for n in sorted(pool):
            rows.extend([n] * _repeats(pool[n]))
        intl_report.append((cc, len(set(old)), len(set(rows)), len(rows)))
        cities[cc] = rows

    # --- Jefferson cap ---------------------------------------------------------
    # towns_in_region merges the campus cities from data/ncaa/locations.json on
    # top of us_states — count the DISTINCT union the way it does, or the share
    # is understated (the import_jefferson report had exactly this flaw).
    campus: dict[str, set[str]] = collections.defaultdict(set)
    loc_path = os.path.join(ROOT, "data", "ncaa", "locations.json")
    if os.path.exists(loc_path):
        with open(loc_path, encoding="utf-8") as fh:
            for row in json.load(fh).values():
                if not isinstance(row, dict):      # the "_doc" entry is a list
                    continue
                st, city = row.get("state"), row.get("city")
                if st and city:
                    campus[st].add(city)
    west_distinct = sum(len(set(us_states.get(s, [])) | campus.get(s, set()))
                       for s in WEST_STATES)
    jf_now = len(set(us_states.get("JF", [])))

    print(f"{'st':<4}{'old':>6}{'new':>6}{'entries':>9}{'floor':>8}")
    for st, old_d, new_d, entries, floor in report:
        print(f"{st:<4}{old_d:>6}{new_d:>6}{entries:>9}{floor:>8}")
    for cc, old_d, new_d, entries in intl_report:
        print(f"cities[{cc}]: {old_d} -> {new_d} distinct ({entries} entries)")
    share = jf_now / (jf_now + west_distinct) * 100 if west_distinct else 0
    print(f"\nwestern distinct pool (excl JF): {west_distinct}")
    print(f"JF {jf_now} distinct -> {share:.0f}% of the west "
          f"(uncapped, owner rule 2027-08; population share ~{JF_WEST_SHARE:.0%}; "
          f"import_jefferson warns if it climbs past 35%)")
    print("\n⚠️  cities[CA]/cities[MX] feed the surname scrubber's blocklist —")
    print("   run scripts/scrub_name_pools.py --check and review the diff before committing.")

    if dry:
        print("\n[dry-run] not written")
        return
    with open(HOMETOWNS, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)   # the file's canonical format (import_jefferson._dump_hometowns)
        fh.write("\n")
    print(f"\nwrote {HOMETOWNS}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cache", default="/tmp/cities5000.zip",
                    help="where to keep the downloaded dump")
    args = ap.parse_args()
    build(args.dry_run, args.cache)
