# AAR — Hometown pools rebuilt from real place data

**Date:** 2027-08
**Scope:** `generators/data/names/hometowns.json` (both tiers),
`scripts/build_hometowns.py` (new), `scripts/import_jefferson.py`
(`_MAX_CITIES` 46 → 199 → uncapped; see addendum), `scripts/scrub_name_pools.py`
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

---

## Addendum (same day): uncapped Jefferson, graduated floors

Two owner rulings landed right after the first pass shipped:

**"jefferson doesn't have to be capped anymore clearly."** Correct — the cap
defended a ~150-city western pool that the rebuild abolished. `_MAX_CITIES` is
now `None`: all 272 Jefferson cities export, ~27% of the ~1,000-city west
against a ~23% population share. The share report stays as the **tripwire**
(warns past 35%): if the western pools ever shrink — a floor change, a
regeneration bug — the old 64% disaster comes back and a cap must too.

**"you can go down to like cities of 5k or 2k not 10k … i don't need tiny
places in big states but other ones should be represented more wholly …
realism isn't the issue it's interestingness."** So the floor is GRADUATED,
not uniform: each state keeps the highest of (10k, 5k, 2k) that still yields
`TARGET_PLACES` (40) distinct places. Source moved from `cities5000` to
`cities1000` to reach the 2k tier. CA/TX/FL stay at 10k with no hamlets;
VT/WY/MT/ME/NV fall to 2k and field their real small towns — Vermont 40
(Bennington, Lyndon), Wyoming 32 (Lovell, Lyman), Maine 124.

Final: **~5,100 distinct US cities** (from 1,218), Canada 659, Mexico 610.
Pressure unchanged at 2 states over 1.0/city, both by design.

The scrubber bit a SECOND time, same session, same way: the 2k-floor
Canadian/Mexican towns collided with 38 more curated surnames (King and
Almonte are Ontario townships; Armstrong, Merritt, Oliver, Hope and Trail are
BC towns; Alvarado, Hidalgo, Nava and Arriaga are Mexican municipios).
Restored, 24 more names into `SURNAME_CITY_KEEP`, re-run clean. If the floors
ever drop again, budget for a third pass.

---

## Addendum 2: review fixes, and school names lose their suffixes

Three review findings and one owner rule, landed together.

**A stale cache shadowed the download.** `--cache` defaulted to
`/tmp/cities5000.zip` after the source moved to `cities1000.zip`; a leftover
file from the earlier run satisfied the exists-check and `_fetch` raised
`KeyError` on the member. The default now derives from the dump URL, and a
cached zip that does not contain the expected member is treated as stale and
refetched.

**Generated output was becoming next run's "curated" input.** The union ran
over the LIVE file, so after one rebuild every generated town read as curated —
a place GeoNames drops or a tightened floor excludes could never leave, kept
forever at weight 1. The hand-curated baseline is now frozen in
`hometowns_curated.json` (extracted from the pre-rebuild git state, 1,315 US +
79 CA/MX entries), the generator unions THAT, and the rebuild verifies
byte-identical against the current pools. New hand-picked cities go in the
baseline, where they survive every rebuild.

**"Baptist HS High School."** `high_school_name()` appended " High School" to
any name without a school word, and did not know "HS" was one. The owner's
ruling went further than the fix: *"you don't need to have HS or High School
ever, or even 'School' because nobody uses it"* — school names on real sites
are written bare. So:

- `import_jefferson.high_school_name` now STRIPS trailing `High School` / `HS`
  / `School` and never appends anything.
- The same strip runs at `import_jhsaa`'s emit point, exactly like `RENAMES` —
  everything internal (sponsorship dice, district draws, pid identity) still
  runs on the source name.
- All 56 states of `high_schools.json` were stripped in place: **13,800+
  names** ("A. H. Parker High School" → "A. H. Parker"), 13 collapsing as
  duplicates of an existing bare name.
- Day schools keep the word "Day" but not "School" (owner: *"usually it just
  says Day"*): "Telfair Country Day School" → "Telfair Country Day". The
  fallback suffix list's "Day School" became "Day". (This took three passes —
  strip, restore, re-strip — as the rule sharpened; the final rule is
  UNIVERSAL, no exceptions.)
- The 11 suffixed JHSAA display names were renamed **with `source` stamped** —
  generation keys pids on `source or name`, so a bare rename hands a program
  twelve strangers and unlinks its archived awards. `archetypes.json` keys on
  the display name and moved too.

**And "School of SUBJECT" collapses to the subject** (a follow-up owner rule:
*"you just say San Cordero Commerce or Plainfield Science"*), truncated at
"and" — "Calder School of Science and Industry" reads "Calder Science". The
collapse is GATED on a subject vocabulary because the same shape carries
places ("Jesuit High School of Sacramento", "Latin School of Chicago"), where
the of-phrase is the name. 16 collapsed across the pool, including the
validating real case: "Bronx High School of Science" → **"Bronx Science"**,
which is exactly what everyone calls it.
