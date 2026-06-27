# AAR — Name pool expansion + country diversity (diaspora names)

**Date:** 2026-06-27
**Scope:** Bigger name pools, a fix so place-names that are also real given names
(Denver, Houston, Dallas, Montana, London) survive the scrubber, and a diversity
blend so diverse nations field diverse people instead of a monoculture.

## Why

Two owner asks:
1. *"It rolls the same names too often."* The pools were already large, but the
   most-drawn buckets (American given names) are the dimension a player notices
   recurring. Grew them and widened the US first-name union.
2. *"Diverse countries should have diverse people."* Every nation drew a perfectly
   coherent monoculture name — a France player was always "French first + French
   surname + FR." Real diverse nations don't work that way.

## Changes

### 1. Pool expansion (`scripts/expand_name_pools.py`)
Adds ~1,000 curated real names (American male/female given names + surnames, plus
supplements to latin-american / german / japanese / korean buckets) and wires
`american_general` into the US first-name union in `regions.json`. Idempotent
(de-dupes), so re-running is a no-op. Run the scrubber + `test_name_pool_clean`
after.

### 2. Place-names that are real given names (`scripts/scrub_name_pools.py`)
The scrubber strips city/sports-junk tokens, which caught **Denver, Houston,
Dallas, Montana, London, Brooklyn, Austin** — all genuine American given names. New
`LEGIT_FIRST_NAME_KEEP` whitelist subtracts them from the first-name blocklist (and
`Pickering`, a real surname, added to `SURNAME_CITY_KEEP`). These are now seeded
into both male & female American pools and survive scrubbing.

### 3. Diaspora / diversity blend (`generators/names.py`, `DIASPORA_SHARE = 0.12`)
A share of draws give a citizen of one region a name from **another** culture — the
**country/flag stays the home region's**, only the name comes from elsewhere. So a
French national can read "Karim Diallo (FR)", a German "Piotr Brand (DE)", a US
player a Hispanic- or Turkish-heritage name. Only fires when the world mix spans
more than one region, and a region can override the rate with a `diversity` field in
`regions.json` (crank the melting-pot nations up, leave insular ones near 0).
Zaryanovia (the fictional, procedurally-named nation) is excluded as a *source* — it
isn't a real heritage.

This deliberately relaxes the **O27 coherence rule** (`test_draws_are_subregion_coherent`),
which forbade a name whose culture didn't match its country. That rule exists to
catch scraped *junk* ("Pérez (IT)"), not intentional diversity. So:
- `test_draws_are_subregion_coherent` now holds the blend OFF (`DIASPORA_SHARE = 0`)
  and still guarantees the underlying pools are per-subregion coherent.
- new `test_diaspora_pairs_real_names` forces the blend ON and guarantees it only
  ever pairs a real first+surname from some culture — diversity, never junk.

## Tuning knobs
- `DIASPORA_SHARE` (global default 0.12) and per-region `diversity` in regions.json.
- `scripts/expand_name_pools.py` — append more curated names per bucket and re-run.

## Note
Names are not save state, so this changes future-generated worlds only; existing
saves keep the names they were built with. The world **seed** (onboarding) still
makes each run reproducible.
