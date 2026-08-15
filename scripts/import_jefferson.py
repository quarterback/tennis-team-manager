#!/usr/bin/env python3
"""
Import the fictional state of JEFFERSON from the `prep-network` repo into this
sim's per-state name pools, so Jefferson juniors read like every other state's.

Jefferson is an alternate-history West Coast state built in `prep-network`
(github.com/quarterback/prep-network): ~17.6M people across 20 fictional counties,
each standing on the real ground of southern Oregon, northern California, northern
Nevada and western Idaho. It has 272 cities and 840 high schools under its own
sanctioning body (the JHSAA), 526 of which sponsor tennis.

This sim allocates every domestic recruit a state (`juniors.US_STATES`) and then
rolls a real hometown and a real high school out of that state's pool
(`flavor.roll_us_hometown` / `flavor.roll_high_school`). Adding "JF" to those two
pools is the whole integration: no new code path, no runtime dependency on
prep-network, no import of its simulated players. The JHSAA season stays over
there — this side only borrows the geography and the school names.

WHAT IT WRITES (both files are the authoritative committed source; this script
exists so the pools can be REGENERATED when Jefferson changes, not so the game
reads prep-network at runtime):

  * generators/data/names/high_schools.json  -> "JF": [school names]
  * generators/data/names/hometowns.json     -> us_states["JF"]: [city names]

Idempotent: re-running replaces the JF key in place and is otherwise a no-op.
Each file keeps its own existing serialization (they differ — see _dump_*).

Usage:
    python3 scripts/import_jefferson.py [--prep-network ../prep-network] [--dry-run]

See docs/AAR-jefferson-state-integration.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_NAMES_DIR = os.path.join(_REPO, "generators", "data", "names")
_HS_PATH = os.path.join(_NAMES_DIR, "high_schools.json")
_HOMETOWNS_PATH = os.path.join(_NAMES_DIR, "hometowns.json")

STATE_ABBR = "JF"
# Jefferson sorts between Iowa and Kansas by full state name, which is the order
# both pools and `juniors.US_STATES` already use. Insert there rather than
# appending, so the files stay readable as state lists.
_INSERT_AFTER = "IA"

# A Jefferson recruit should come from a school that actually fields tennis.
_TENNIS_SPORTS = ("boys-tennis", "girls-tennis")

# Words that already mark a name as a school. If any of these appears ANYWHERE in
# the name we leave it alone; otherwise we append " High School". Matching the
# whole name rather than just its tail matters: prep-network has magnet schools
# like "San Cordero School of Commerce" and "Lake Esperanza School of Science and
# Industry", which end in a topic word but must not become "... High School".
_SCHOOL_WORDS = frozenset({
    "school", "schools", "academy", "institute", "prep", "preparatory",
    "collegiate", "high",
})

# Repeat-as-weight for the hometown pool: `roll_us_hometown` does a flat
# rng.choice over the list, so a city listed twice is twice as likely. This is the
# established idiom here — see the `_COLLEGE_TOWNS` comment in generators/cities.py.
# One slot per 25k residents, capped, so Port Veles (1.2M) outweighs a hamlet
# without swamping the pool.
_POP_PER_SLOT = 25_000
_MAX_SLOTS = 12

# ⚠️ HOW MANY DISTINCT CITIES — this is the number that bites.
# This pool feeds TWO consumers, and only one of them sees the repeat-weighting:
#   1. `flavor.roll_us_hometown("JF")` — a Jefferson recruit's own hometown. Wants
#      a rich list; repeats are the weighting.
#   2. `ncaa.towns_in_region("W")` — the pool EVERY western program draws its
#      local year-0 base-roster players from (`LOCAL_REGION_TARGET` = 0.70). It
#      dedupes by (city, state), so only the DISTINCT count matters there.
# Jefferson has 272 cities. The cap is Jefferson's share of the region's
# POPULATION (~17.6M of ~76M ≈ 23%) applied to the WESTERN pool's distinct
# count — so it moves whenever the real states' pools do, in either direction.
# At the original hand-curated pools (~153 other western cities) that came to
# 46; after the 2027-08 hometown rebuild (scripts/build_hometowns.py, real
# Census/GeoNames data — CA alone went 81 -> 461) the west carries ~665 other
# cities, so 199/(199+665) ≈ 23%. Exporting all 272 at the OLD pool size would
# have made Jefferson 64% of the pool — every California, Oregon and Washington
# roster would fill with Jefferson kids, and nothing would error. If Jefferson's
# population or the western pools change again, re-derive this — do not just
# raise it (the share report below now warns in BOTH directions).
_MAX_CITIES = 199


def high_school_name(name: str) -> str:
    """`name` as it should read in a player bio. prep-network stores the bare
    institution name ("Alder Landing", "Halbrook Technical") because its own site
    supplies the context; here the string stands alone in a "High school" row."""
    words = {w.strip(".,").lower() for w in name.split()}
    return name if words & _SCHOOL_WORDS else f"{name} High School"


def _load_prep_network(root: str) -> tuple[list[dict], list[dict]]:
    orgs = os.path.join(root, "records", "orgs")
    schools_path = os.path.join(orgs, "schools.json")
    cities_path = os.path.join(orgs, "cities.json")
    for p in (schools_path, cities_path):
        if not os.path.exists(p):
            sys.exit(f"not found: {p}\n"
                     f"Point --prep-network at a checkout of quarterback/prep-network.")
    with open(schools_path, encoding="utf-8") as fh:
        schools = json.load(fh)["schools"]
    with open(cities_path, encoding="utf-8") as fh:
        cities = json.load(fh)
    if isinstance(cities, dict):            # tolerate a wrapped {"$type":…, "cities":[…]}
        cities = cities.get("cities", [])
    return schools, cities


def build_high_schools(schools: list[dict]) -> list[str]:
    """Every Jefferson school that sponsors tennis, named so it reads as a school."""
    names = {high_school_name(s["name"]) for s in schools
             if any(sp in s.get("sports", ()) for sp in _TENNIS_SPORTS)}
    return sorted(names)


def build_hometowns(cities: list[dict]) -> list[str]:
    """Jefferson's `_MAX_CITIES` largest cities, each repeated by population so the
    big metros dominate a recruit's hometown roll the way they do in a real state.
    Capped rather than exhaustive — see the `_MAX_CITIES` note above."""
    out: list[str] = []
    ranked = sorted(cities, key=lambda c: (-c.get("population", 0), c["name"]))
    for c in ranked[:_MAX_CITIES]:
        slots = max(1, min(_MAX_SLOTS, round(c.get("population", 0) / _POP_PER_SLOT)))
        out.extend([c["name"]] * slots)
    return out


def _report_region_share(distinct: int) -> None:
    """Print what this export does to `towns_in_region("W")`, the shared pool every
    western program draws local base-roster players from. Loud on purpose: an
    oversized Jefferson pool quietly fills California/Oregon/Washington rosters
    with Jefferson kids and raises no error. See the `_MAX_CITIES` note."""
    try:
        sys.path.insert(0, _REPO)
        # Count the DISTINCT (city, state) union exactly the way the consumer
        # does — `ncaa.towns_in_region` merges the campus cities from
        # locations.json on top of us_states, so counting us_states alone
        # UNDERSTATES the pool (it printed 24.9% when the real share was 26.6%).
        from app.ncaa import STATE_REGION, cities_by_state   # noqa: PLC0415
        from generators.flavor import _load_us_states        # noqa: PLC0415
        west: dict[str, set] = {}
        for source in (_load_us_states(), cities_by_state()):
            for st, cs in source.items():
                if STATE_REGION.get(st) == "W":
                    west.setdefault(st, set()).update(cs)
        others = sum(len(cs) for st, cs in west.items() if st != STATE_ABBR)
        distinct = len(west.get(STATE_ABBR, set()) or set()) or distinct
    except Exception:                                        # pragma: no cover
        return                                               # reporting only
    total = distinct + others
    share = distinct / total * 100 if total else 0.0
    # The cap is a PROPORTION (JF ≈ 23% of the west's population), so it drifts
    # off its anchor in BOTH directions: too high fills western rosters with
    # Jefferson kids; too low starves Jefferson below its population share once
    # the real states' pools grow. Warn on both sides.
    warn = ""
    if share > 30:
        warn = "  <-- TOO HIGH, re-derive _MAX_CITIES"
    elif share < 16:
        warn = "  <-- TOO LOW, re-derive _MAX_CITIES (western pools grew?)"
    print(f"  -> region W town pool: {distinct} JF + {others} other "
          f"= {total} ({share:.0f}% Jefferson){warn}")


def _insert_state(mapping: dict, value) -> dict:
    """Set `mapping[STATE_ABBR] = value`, positioned after `_INSERT_AFTER`."""
    if STATE_ABBR in mapping:               # already present — replace in place
        mapping[STATE_ABBR] = value
        return mapping
    out: dict = {}
    for k, v in mapping.items():
        out[k] = v
        if k == _INSERT_AFTER:
            out[STATE_ABBR] = value
    if STATE_ABBR not in out:               # no anchor key — fall back to the end
        out[STATE_ABBR] = value
    return out


def _dump_high_schools(data: dict) -> str:
    """high_schools.json is stored flat (indent 0), no trailing newline."""
    return json.dumps(data, indent=0, ensure_ascii=False)


def _dump_hometowns(data: dict) -> str:
    """hometowns.json is stored indented 2, with a trailing newline."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prep-network", default=os.path.join(os.path.dirname(_REPO),
                                                           "prep-network"),
                    help="path to a prep-network checkout (default: ../prep-network)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be written, touch nothing")
    args = ap.parse_args()

    schools, cities = _load_prep_network(args.prep_network)
    hs_names = build_high_schools(schools)
    town_pool = build_hometowns(cities)
    if not hs_names or not town_pool:
        sys.exit("refusing to write an empty Jefferson pool")

    distinct = len({*town_pool})
    print(f"prep-network: {args.prep_network}")
    print(f"  {len(schools)} schools, {len(cities)} cities")
    print(f"  -> {len(hs_names)} tennis-sponsoring high schools")
    print(f"  -> {len(town_pool)} hometown slots across {distinct} cities")
    print(f"     e.g. {hs_names[0]!r}, {hs_names[len(hs_names) // 2]!r}")
    print(f"     top city {town_pool[0]!r} x{town_pool.count(town_pool[0])}")
    _report_region_share(distinct)

    with open(_HS_PATH, encoding="utf-8") as fh:
        hs_data = json.load(fh)
    with open(_HOMETOWNS_PATH, encoding="utf-8") as fh:
        ht_data = json.load(fh)

    hs_data = _insert_state(hs_data, hs_names)
    ht_data["us_states"] = _insert_state(ht_data["us_states"], town_pool)

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    with open(_HS_PATH, "w", encoding="utf-8") as fh:
        fh.write(_dump_high_schools(hs_data))
    with open(_HOMETOWNS_PATH, "w", encoding="utf-8") as fh:
        fh.write(_dump_hometowns(ht_data))
    print(f"\nwrote {os.path.relpath(_HS_PATH, _REPO)}"
          f" and {os.path.relpath(_HOMETOWNS_PATH, _REPO)}")


if __name__ == "__main__":
    main()
