# AAR — Media/Coaches polls, regional rankings, hometown breadth, territory recruiting

## Context

A batch session off the `player-hometown-diversity` branch. The owner asked, in order,
for: broader player hometowns; a cross-division exhibition dual; portal pagination that
doesn't lose your place; a bigger majors pool; island/remote-state programs that recruit
their own backyard; a Power-6 column and a both-records fix on Standings; the Rutgers
branch-campus logos; ITA-style **regional rankings**; and a full **AP/Coaches poll
ecosystem**. Each is small-to-medium on its own; this AAR records the design decisions and
the invariants worth not "fixing" later.

---

## 1. Hometown breadth — wire the rich pool into base rosters (`generators/cities.py`, `ncaa.towns_in_region`)

The rich per-state city pool (`hometowns.json` `us_states`, ~1.5k real US cities) already
existed and the **recruit** path used it (`flavor.roll_us_hometown`), but **base rosters**
still drew from two thin "college-town" lists, so team pages read as the same handful of
cities. Both base-roster paths now draw from the rich pool:

- `cities.random_town` (nationwide fallback + GTT + international fallback): **77 → 1,314
  distinct real cities**, each state weighted by a tennis-recruiting-heat table
  (`_STATE_HEAT`) and filtered to valid US codes (`_US_CODES`, drops a stray Canadian
  province in the shared data). Built once, cached. Single `rng.choice`, so no downstream
  draw-count shift.
- `ncaa.towns_in_region` (the 70% region-biased path, `LOCAL_REGION_TARGET`) now spans the
  whole region's real cities from the same pool, merged with the researched campus cities,
  deterministically ordered.

Measured: 233 sampled domestic D2 men → **210 distinct hometowns** (was heavy clustering).
`program_city` and its test are untouched (that's a separate deterministic team-location
fallback).

---

## 2. ⚠️ Island/remote-state programs recruit local kids — TWO layers, both curated

The owner wanted Puerto Rico / USVI / Guam programs stocked with local kids and Alaska
**favored but thin**. This is modelled exactly like the existing
`ncaa.SCHOOL_RECRUIT_TERRITORY` (Yeshiva⇄Israel, Simon Fraser⇄Canada) — **curated, not
automatic** — in a new `ncaa.SCHOOL_LOCAL_TERRITORY` map `{school: (USPS, local share)}`:

| Program(s) | Share | Result (measured) |
|---|---|---|
| Puerto Rico ×4 | 0.85 | 8–10 of ~10 local — PR hometowns, **Latin names**, PR dual flag |
| Virgin Islands | 0.80 | 8–10/10 — USVI hometowns + flag |
| Guam | 0.85 | 9/10 — **Chamorro names** (Mangilao, Hagåtña), Guam flag |
| Alaska Anchorage / Fairbanks | 0.45 | ~40–50% — AK hometowns, **US flag** (a state, no territory flag) |

Alaska is deliberately lower — the in-state junior pool is thin, so most of the roster is
still mainland; "favored but few," per the owner.

### Layer A — year-0 base roster (`ncaa.build_roster`)
A per-slot local draw displaces the level-based nationality mix, then overrides
hometown / high_school / region / secondary-flag for the local kid (Latin picker for PR,
Chamorro for Guam, US otherwise). Non-territory programs untouched; seed-deterministic.

### Layer B — the ongoing recruiting sim (`world._pick_school`, `recruiting.LOCAL_TERRITORY_PULL`)
> ⚠️ Coarse `STATE_REGION` proximity is **0 for PR/USVI/Guam** (they aren't in the region
> map), so nothing bound a Puerto Rican recruit to a Puerto Rico school — past year 0 the
> rosters drifted generic. `_recruit_market` now precomputes the territory maps and
> `_pick_school` adds a recruit's home-territory schools to its candidate set and multiplies
> their score by `1 + LOCAL_TERRITORY_PULL(6.0) * share`.

Key properties, so this isn't "tuned away" later:
- **Only fires** for a recruit whose hometown state/territory matches a listed program —
  general recruiting is provably untouched (all world/recruit tests unchanged).
- **Mid/low locals bind home; elites still escape** — a low-budget D2 territory school is
  gated out for a blue-chip by the budget floor regardless of the pull, so genuinely elite
  island kids leave for the mainland (realistic). Verified in a controlled-market test
  (pull raises local signing vs pull-off; elites still leave).
- **Thin pools self-limit** — the juniors floor guarantees ~1/territory/year, so island
  rosters end up local-heavy, not hermetic. Raising per-territory *pool* allocation (in
  `juniors`) is the lever if the owner wants PR closer to fully local.

---

## 3. Majors pool doubled (`generators/majors.py`)

`pick_major` unchanged (real weighted heavily, fictional ~6% garnish); just bigger, more
varied bios. Real **165 → 288** (broadened past the STEM/health lean — languages, area
studies, arts, business, health, engineering, sciences, ag/environment, education, applied),
fictional **40 → 87** (same tongue-in-cheek voice). No dupes within or across the lists.

---

## 4. Standings — Power 6 column + the both-records clipping bug (`season_standings.html`, `state.attach_power6`)

- **Power 6 column**: `state.attach_power6` enriches each conference-standings row with the
  existing Power-6 metric, its rank *within* the conference, and a bar relative to the
  table's range — so roster strength reads for every team, ranked nationally or not. Kept in
  the web layer so `seasonmode.standings` stays records-only.
- ⚠️ **The "no overall record" bug was a CSS clip, not missing data.** The row always
  rendered Conf W-L, Conf %, Overall W-L, Overall % — but the container was capped at
  `max-width:760px` while `.bl-table` has `min-width:920px`, so the right columns overflowed
  into the horizontal-scroll wrapper and only Conf showed. Fix: raise the standings
  container to `max-width:1040px` (matches how the un-capped rankings page shows both). If a
  "table only shows the left columns" report recurs, check container width vs
  `.bl-table{min-width}` first.

---

## 5. Regional rankings + movement column (`rankings.html`, `state.regional_ranking_rows`)

- **Regional** tab: splits the national board into the seven geographic regions
  (`scout_intel.US_REGIONS`, by each program's home state) and shows each region's top 10
  with its national rank — so mid-pack teams that never crack the national list surface
  where they stack. Reuses `ranking_rows` order.
- **MOV column**: `LiveRow.move` (from `seasonmode.weekly_movers`, the poll-position top-25
  delta) rendered as ▲n/▼n/—/NEW. Power Index / Power 6 columns unchanged.

---

## 6. ⚠️ Media & Coaches polls — a simulated AP ecosystem, SEPARATE from Power (`app/polls.py`)

The owner spec'd the real AP/Coaches ecosystem, and the governing principle is a hard
invariant: **polls are "what humans believe," Power Index / Power 6 are "what the game
knows" — keep them separate.** Poll signals are results + reputation ONLY; the Power Index
is never fed in.

- **Two polls, one scoring system, different electorates.** Media = 51 reactive voters
  (rewards upsets, moves fast); Coaches = 40 conservative voters (reputation-leaning, slow).
  Every voter submits a top-25 ballot (25 pts for 1st … 1 for 25th); ballots sum, first-place
  votes are tracked, teams past #25 are Others Receiving Votes.
- **Voter archetypes** (`_ARCHETYPES`: résumé / analytics / traditionalist / upset-chaser)
  each weight the signals differently, plus per-voter noise. The pool's archetype **mix**
  (`_POOLS`) + its inertia/noise/prestige knobs are the ONLY thing separating media from
  coaches — exactly as in real life.
- **Human inertia**: boards are computed **forward** from a preseason (reputation) seed, each
  week leaning on the last, so a one-loss #1 slides a few spots, not off a cliff. A
  result-less week (bye / preseason) carries the board forward unchanged, so **movement only
  ever reflects real games** — verified in preseason (0 spurious moves) and with a synthetic
  simmed season (undefeated #1 loses once → #1→#5, not cratered).
- **Scope**: `poll(seed, gender, which, division=None)` — `None` = a national board across
  D1-D4 (D1 dominates on reputation, a dominant lower-div team can crack the bottom, and the
  storylines surface highest mid-major / D2 / D3 / D4); a division sets a single-division
  board (the cross-division storylines fall away naturally). The `/polls` page has
  Poll · Gender · **Scope (National · D1–D4)** toggles, plus auto storylines and a Biggest
  Movers panel.

> ⚠️ **Determinism gotcha (already fixed, don't reintroduce):** `_candidates` originally
> returned a `set`→`list`, whose order is `PYTHONHASHSEED`-dependent, which flipped ballot
> tie-breaks — so the same poll could differ between web workers. Candidate order is now
> `sorted` (prelim score, then school). The regression test runs under several hash seeds.

### Note on the running DB
`poll()` reads the same `duals` table (keyed by world seed + week) that rankings/standings
use. A **preseason** DB (0-0 records) therefore yields a static, reputation-seeded board by
design; records, movement, first-place shifts and storylines populate once a season is
actually simmed.

---

## 7. Smaller items

- **Exhibition Dual Simulator, cross-division** (`web/sim.py`, `/dual`): the engine was
  always division-blind (STR is one scale); only the picker was locked to one universe.
  `run_dual_view` now takes a division per side; the setup page has a per-side division
  picker (same gender). Elite gap shows honestly (D1 sweeps D4). Exhibition only — nothing
  persisted.
- **Portal pagination** (`preseason_portal.html`, `fall_portal.html`): swapped the bare
  Prev/Next for the numbered `_pager`, and every per-row action (redirect a rider, sign/drop
  a pro, drop a move, add) returns to the **same page** via `_pp_return`/`_fp_return` +
  hidden `page` fields instead of bouncing to page 1. The fall portal was also paginated.
  ⚠️ **Codex-caught bug:** the single-row drop form posts `gender = the player's own gender`
  (ps_set_status needs it), which `_pp_return` was reusing as the view **filter** — dropping
  a men's move while viewing "All" collapsed the slate to Men. Fixed with a distinct `fg`
  (filter-gender) field the helper prefers.
- **Singles/doubles min-matches gate** (`ita_singles_points`, rankings page): the singles
  board ranked anyone with a result, so a **1-0 player topped D3 Women** — meaningless.
  Added a `min_matches` gate to `ita_singles_points` (doubles already had one) and a **Min
  matches** selector (1/2/3/**5**/8/10, default 3) on the singles + doubles rankings views, so
  a single result can't crown a player and the owner can tighten the bar as a season fills in.
- **Rutgers-Camden / Rutgers-Newark logos**: both showed a borrowed Radford mark
  (espn_id-collision substitute). Their PNGs now hold the real Rutgers art (byte-identical to
  `rutgers.png`) and `logo_source` records `sub:Rutgers Scarlet Knights`; slugs unchanged, so
  only the displayed art changed.

## Tests

`test_polls.py` (ballot scoring, records, inertia, determinism across hash seeds, media-vs-
coaches volatility), plus the territory-pull regression in `test_recruit_signing.py`. Existing
`test_cities`, `test_juniors`, `test_world_model`, `test_recruit_signing`, `test_world`,
`test_roster`, portal and web tests pass. (Note: the web-coaches/season suites have known
cross-test DB pollution that surfaces different failures per run when many web tests share one
process; each affected file passes on its own.)
