# AAR — Hometown pools rebuilt from real place data

**Date:** 2027-08
**Scope:** `generators/data/names/hometowns.json` (both tiers),
`scripts/build_hometowns.py` (new), `scripts/import_jefferson.py`
(`_MAX_CITIES` 46 → 199, two-way share warning), `scripts/scrub_name_pools.py`
(`SURNAME_CITY_KEEP` +20)

## The ask, and the question under it

Owner: *"US and Canadian cities (Mexico too) should be there. I just think there
should be way more hometown diversity, it's not costing us much of anything to
have more in there so why not go full tilt?"* — after catching a wrong number in
a blog draft ("only 272 western hometowns"; 272 was Jefferson's own count).

And, on seeing the original data: *"why is it set up that way? that's a really
stupid way to do it."* Fair. The lists were hand-typed flavour, skewed toward
campus towns (California carried Atherton, Moraga and La Verne but not Fontana
or Oxnard), and **nobody had ever sized them against draw volume**. Measured:
**33 of 55 states drew more recruits per class than they had cities** — Florida
248 recruits from 46 cities, 5.4 per city per class — and nothing errored,
because a repeated hometown is not an error.

The honest answer to "why not go full tilt" was: because I would have typed
~2,500 place names from memory, and invented data is how this codebase gets its
worst bugs. So the fix is a **generator over real datasets**, with the curated
lists kept as a union on top.

## Sources — two, because neither is sufficient alone

- **GeoNames `cities5000`** (CC-BY): population for every place ≥5k on earth,
  one pipeline for all three countries. But its feature codes are unreliable
  inside big cities: it classes DC neighbourhoods — "NoMa", "Foggy Bottom",
  "Downtown DC" — as ordinary populated places. First dry-run gave DC **28
  "cities"**. It cannot be the sole authority on what is a hometown.
- **US Census Gazetteer nationals** (place + cousubs, no API key): legitimacy.
  A US name qualifies only if it is a real incorporated place or CDP — or a
  county-subdivision *town* in the six New England states, whose municipalities
  don't exist in the place file at all (first Census-only attempt gave Vermont
  **4 places**). Hawaii's municipalities are CDPs, same story.

US pools take the **intersection** (GeoNames population × Gazetteer
legitimacy). Canada and Mexico take GeoNames alone — no Gazetteer exists for
them; the feature-code filter plus the floor is the best available gate, and
inspection showed their pools clean where the US one wasn't.

Name-matching traps that cost a pass each: Gazetteer designators
("Pearl City CDP", "Juneau city and borough"), consolidated city-counties
("Nashville-Davidson metropolitan government (balance)" vs GeoNames
"Nashville" — the first hyphen component must qualify too), and Census "Urban
Honolulu" vs everyone else's "Honolulu". Without those rules the gate silently
dropped **Nashville, Athens, Augusta, Juneau, Butte and Honolulu** — verified by
spot-check, not assumed.

## The numbers

| | before | after |
|---|---|---|
| distinct US cities | 1,218 | **~3,900** |
| Florida | 46 | 295 |
| California | 81 | 461 |
| `cities["CA"]` (Canada) | 60 | 405 |
| `cities["MX"]` (Mexico) | 19 | 396 |
| states over 1 recruit/city/class | 33 of 55 | **2 of 55** |

(The remaining two: DC — one real municipality, correctly — and Jefferson,
whose pool is capped by design.)

Weighting: **repeats are the weight in both tiers** — `roll_us_hometown` and
`roll_hometown` are flat `rng.choice`, so a city's entry count is its
probability. The rule is `import_jefferson`'s existing one, adopted verbatim
rather than inventing a second band table: one slot per 25k residents, capped
at 12. `ncaa.towns_in_region` dedupes, so repeats never touch the 70%
local-roster draw. Verified on draws: FL 2,000 rolls → 290 distinct, Jacksonville
and Tampa on top; Canada 372 distinct; Mexico 346.

## Jefferson's cap is a proportion, and it silently drifted

`_MAX_CITIES = 46` was derived as ~23% (Jefferson's population share of the
west) of a ~150-city western pool. Grow the west to ~666 and 46 becomes **8%** —
the *inverse* of the failure the cap was built against, and the share report
only warned one way (>30%). Worse, the report counted `us_states` alone while
the consumer (`towns_in_region`) merges campus cities on top, so it printed
24.9% when the true share was 26.6%.

Fixed: cap recomputed to **199** (199/(199+666) ≈ 23%, exact measured result
23.0%), the report now counts the union the way the consumer does, and it warns
in **both** directions. The cap comment now says the rule, not just the number.

## ‼️ `scrub_name_pools.py --check` is a REAL RUN

Second time this session the scrubber's semantics bit: `--check` scrubs and
then verifies idempotency — it is not a dry-run. The 801 new Canadian/Mexican
cities collided with 38 curated surnames (**García** — the city in Nuevo León;
Thompson MB, Brooks AB, Duncan BC, Mercier QC, Winkler MB, Linares NL…), and
the "check" deleted them from every surname bucket before the keep-set caught
up. Restored from git, all 20 distinct names added to `SURNAME_CITY_KEEP`,
re-run clean. Only the `cities` tier feeds the scrubber; `us_states` never does
(Austin, Jackson and Washington are surnames too — that exemption is old and
deliberate).

## Notes from the consumer map (full sweep, worth keeping)

- The two tiers share 14 colliding keys (`us_states["CA"]` = California,
  `cities["CA"]` = Canada; also AL/AR/CO/DE/ID/IL/IN/LA/MA/PA/TN…). Nothing
  enforces the separation — it holds by call-site discipline only.
- `flavor.py` defines `_load_us_states` and `roll_us_hometown` **twice**; the
  first pair is dead code (Python keeps the second). An edit to the first pair
  silently does nothing.
- Every hometown cache is module-global and cleared by nothing —
  `ncaa.reset_caches()` does not touch them. A data change needs a process
  restart. Do NOT wire `_REGION_TOWNS_CACHE` into `reset_caches()` casually:
  its read pattern is the exact non-atomic `in`-then-`[key]` shape CLAUDE.md
  bans, currently safe only because nothing evicts.
- A hometown is materialised onto the Prospect at generation and persisted
  (`world_roster.data`, `players.hometown`) — the expansion changes newly
  generated players only. Year-0 rosters of an **unprimed** world will shift
  (list order changed under `rng.choice`); a primed world is frozen.
- `junior_circuit` names tournaments off `cities` ("Nice Open") — new saves
  will see new event names. Cosmetic.

## Rerunning

```
python3 scripts/build_hometowns.py [--dry-run]      # fetches + rebuilds both tiers
python3 scripts/import_jefferson.py                 # re-derive JF at its share
python3 scripts/scrub_name_pools.py --check         # REAL RUN — read the diff
python3 -m pytest -q tests/test_world_model.py tests/test_juniors.py \
    tests/test_name_pool_clean.py tests/test_cities.py
```
