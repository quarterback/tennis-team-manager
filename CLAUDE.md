# CLAUDE.md — agent guardrails for tennis-team-manager

**NEVER mention Replit.** The owner has not used Replit since this project's earliest
days. There is no Replit integration, no Replit MCP connection is needed, and no
agent should ask about, suggest, or report on Replit authentication — ever. If a
session surfaces a Replit connector as unauthenticated, ignore it silently.

College dual-match tennis simulator. Seed-deterministic engine; D1/D2/D3/D4 ×
men/women. Most tests assert invariants/determinism, not golden values.

## ⚠️ Per-division DUAL FORMATS (owner rule 2027-07) — no more universal 6+3
Real college tennis's 6+3 exists for court/Title-IX reasons this game doesn't have.
Each division plays its own shape (`ncaa.DUAL_FORMATS`, engine `dual.DualFormat`):
**D1 10 singles + 5 doubles consolidated to ONE doubles point (11 pts, clinch 6)** ·
**D2/D3 8 + 3 with EVERY doubles line its own point (11 pts, clinch 6)** ·
**D4 10 + 3 per-line (13 pts, clinch 7)**. D1 alone keeps the consolidated doubles
point (limits doubles stacking — deliberate). The engine default (`CLASSIC`) stays
6+3/7 for bare calls (cups, tests). Read shape ONLY via `ncaa.dual_format` /
`ncaa.lineup_size` — lineup depth, roster floors, portal "would-they-start" checks,
recruit playing-time, award position weights and the lineup editors all key off it;
never write `range(6)`/`[:6]` for anything lineup-shaped. The recruiting/scholarship
ECONOMY was deliberately NOT resized (core stays `SCHOLARSHIP_SLOTS` 6): a D1's paid
core no longer covers its card, so courts 7-10 are walk-on/portal depth — dominance
dilution is the point, don't "fix" it. See `docs/AAR-division-dual-formats.md`.

---

## ⚠️ Recruiting & scholarship economy — DESIGN INVARIANTS (do NOT "fix" without reading)

These values are **intentional game-design decisions**, not bugs, and several
**deliberately diverge from real NCAA rules**. A failing test is NOT proof the code
is wrong — the test may be the stale side. Before changing any number here, read
`docs/AAR-recruiting-prestige-budget-redesign.md`,
`docs/AAR-recruiting-budget-economy.md`, and
`docs/AAR-scholarship-full-funding-rule.md`, and check `git log`.

### ‼️ The big one: a program does NOT have a flat 8 scholarships
Rosters are built by a **scholarship-BUDGET economy**, not a fixed scholarship count.
A program **has a budget** (by **conference tier**) and **spends it on recruits**, who
**cost** scholarships by star. The "8" you'll see in `scholarships.py` is a *separate,
downstream aid-DISPLAY layer* — do not mistake it for "the program's scholarships."

### 1. Recruiting budget = what a program actually has to spend (`recruit_economy._D1_TIER_BANDS`, `_D2_BAND`, `_D3D4_BAND`)
Per-program budget (scholarship equivalency), with a per-world jitter; only D1 top
tier redraws season-to-season. The D1 band is keyed on the program's **prestige
tier** (`_prestige_tier`). At baseline prestige is re-leveled to the **CONFERENCE
TIER** (`ncaa.CONF_TIER` — the master 4-tier hand-curated hierarchy:
top/major/mid/low), so conference sets the *starting* band; the within-band slot is
set by prestige.

> ⚠️ **Prestige is DYNAMIC (YoY), not static.** A program's prestige drifts each
> world rollover by how it over/under-performs its expectation (`world.
> _update_prestige_momentum`; signed per-(school,gender) momentum persisted as
> `roster_overrides kind='prestige_dyn'`, applied in `load_division`, capped ±0.20).
> So budget moves BOTH ways over seasons: a low-major that keeps overachieving funds
> up a tier; a sliding blue-blood funds down. Tests asserting a fixed prestige must
> clear the momentum store. See `docs/AAR-dynamic-prestige-momentum.md`.

| Tier | Budget band |
|---|---|
| D1 Blue Blood (`CONF_TIER` "top") | **16–26** (wide, redraws yearly, so blue-bloods separate) |
| D1 Major / High-major ("major") | 9–16 |
| D1 Mid-major ("mid") | 6–9 |
| D1 Low-major ("low") | 6–7 (the floor, just above D2) |
| D2 | 4–6 (elite D2, prestige ≥ 0.28, funds at 6) |
| **D4** | **3–8, IN the scholarship economy** (owner rule 2027-07 — see `docs/AAR-diii-d4-economy-and-recruit-realism.md`). D4 = the academic-first tier holding the REAL best non-D1 programs (NESCAC/UAA/SCIAC/NCAC); it funds a 3 floor / 6–8 top (`_D4_BAND`) and builds via the star-plan like D1/D2, but ADMITS only recruits above a per-program **academic gate** (`d4_academic_min`, ~SAT 960 floor → 1400 for MIT-tier). D2 still beats D4 ON AVERAGE (most D4 sit at 3–4) because D2 takes anybody and D4 can't admit all it can afford. Do NOT restore D4 to budget-0 or the old tiny prestige clamp. |
| D3 | **0**, EXCEPT a thin **1–3 "gem" allocation** for the **Top-20 D3 by prestige** (`_d3d4_funded`, now D3-only) — lets them sop up one undervalued recruit. D3 is the widest-variety, lowest-floor tier (`_TALENT["D3"]`). |

### 2. Recruit cost by star — what the budget is spent on (`recruit_economy.TIERS`)
Steep curve (deliberately): a premium core is a real investment, so only the
deepest-funded blue-bloods stack blue-chips.

| Tier | Cost (scholarships) |
|---|---|
| Blue Chip | **7** |
| 5★ | **3.5** |
| 4★ | **3** |
| 3★ | **2** |
| 2★ | **1** |
| 1★ | **free (0)** |

### 3. Tier floors gate attainment (`_TIER_FLOOR`)
A program must clear a budget floor to *attract* a tier (not just afford it):
blue-chip ≥ **16.5** (Blue Bloods only), 5★ ≥ **10.5** (Major+), 4★ ≥ **5.0**
(any funded D1 / top D2 — cascades down so 4★s always find a home), 3★ and below
anywhere. So clustering is earned: only Blue Bloods land blue-chips; Majors top out
at a 5★/4★ core; mid/low majors build 4★/3★; a low-major can attract no 5★.

### 3b. Division radar — signing-time level gates (owner rule, do NOT relax)
The in-season signing drip (`world._pick_school`) is level-gated by CURRENT ability
(`recruit_economy.program_level_floor`): a program only has recruits near its own
level on its radar, so **sub-45-STR recruits are never in a D1 program's view**
mid-cycle (they still *dream* of D1 — aspiration is untouched). The floor ramps to a
**residual (0.65), never zero**, so late-window D1s sop up only the best leftovers.
D1 chases the ceiling projection (hype — its mistakes are intended); D2 reads current
ability; D3/D4 weigh current/potential evenly (their division gate uses the even
blend). **D1 classes top the scholarship core up to `SCHOLARSHIP_SLOTS` (6) and stop**
(`world._openings`): a D1 NEVER signs a recruit into a walk-on seat — depth backfills
from the portal or runs short, and rosters thinning toward ~6–8 over seasons is the
point (portal dynamism), not a bug. Target: ~90%+ of ≤45-STR recruits land D2–D4
(measured 97%+). See `docs/AAR-recruiting-division-radar.md`.

### 4. Aid-DISPLAY caps — a SEPARATE layer (`app/scholarships.py`)
Distinct from the budget above. `economy.allocate_scholarships` spreads a per-division
cap across the recruited core as full-ride/partial *display fractions* — it does NOT
determine roster quality (the budget does). Rule `d885f31` "fully fund men to match
women": caps are D1 **8.0**, D2 **6.0**, **D4 6.0** (owner rule 2027-07 — D4 joined the
scholarship economy, funds like D2), D3 0.0, **same for men and women** (NOT real men's
4.5 equivalency). Do **not** lower men to 4.5 to satisfy an old test — that reverts the
rule. (I did exactly this once; it's the mistake this section prevents.)

### 5. Recruiting realism levers (owner rule 2027-07 — `docs/AAR-diii-d4-economy-and-recruit-realism.md`)
- **Playing time** is a recruit factor (`world.PLAY_TIME_WEIGHT` 0.35): recruits lean
  toward programs where their OVR cracks the current top 6, and away from where they'd
  be buried — KEY but BELOW prestige (the `(0.15+pres)` term still dominates). Shown on
  the recruit board as a ROSTER FIT column. Don't raise it above prestige.
- **D2 absorbs aggressively** (`_D2_REACH_BAND` 0.22): D2's division radar reaches far
  below its level so mid-tier talent doesn't leak to D3/D4. Owner-authorized relaxation
  of §3b for D2 only.
- **Warm-weather / big-city** are MARGINAL tiebreaks only (`WARM_APPEAL_WEIGHT` /
  `CITY_APPEAL_WEIGHT` 0.06); they can pull a recruit against the home-state tug.
- **Fall portal diversifies** (`_FPPlanner.best_placement`): risers go where they'd
  slot highest (most playing time), not to the top-prestige few every resolve.
- **Power Index forgives losses to strong teams** (`rating.LOSS_FORGIVE` 0.55): a loss
  to a top team barely dents APR; a loss to a weak one still stings. Wins never
  discounted.

---

## ⚠️ Roster capacity & walk-on sourcing (`ncaa.roster_cap`, `autogen_walkons`)
Rosters are NOT a flat 8. Per-division caps = funded core + walk-on depth:
**D1 12** · **D2 10** · **D3/D4 16**. Walk-on sourcing:
- **D1**: NEVER recruits walk-ons at all (owner rule 2026-07 — see §3b above): the
  class tops the 6-seat scholarship core and stops; depth backfills from the portal
  or runs short. Year-0 built rosters still carry the 8+4 shape; live worlds thin.
- **D2**: walk-ons from the recruit pool ONLY — never auto-generated. Carry "up
  to" cap; if a program doesn't sign enough, it runs fewer walk-ons.
- **D3/D4**: fill from leftover pool recruits first (`world.assign_pool_walkons` — no
  junior goes unsigned), then auto-generate only the still-empty seats
  (`refill_walkons`).
`RECRUIT_POOL = 2500`/gender is sized to roster turnover (~2,200); don't drop it back
to the old 1,000 or D1/D2 can't fill from real recruits. See
`docs/AAR-roster-expansion-walkons-recruit-pool.md`.

**Every division has a HARD FLOOR of its LINEUP CARD** (`ncaa.lineup_size` — D1/D4
ten, D2/D3 eight; enforced at the rollover in `refill_walkons` on the real persisted
roster). "D1 carries no walk-on depth" is about keeping D1 rosters SMALLER than the
rest — never a licence to drop below a playable lineup. A dual fields the division's
full singles card and the doubles pairs index into it, so a short side used to 500
the page; the engine now degrades instead of crashing (`dual._court` clamps, `_pair`
wraps, `gtt._slot` likewise) and an EMPTY side raises loudly. The recording layer
resolves who played through the SAME engine rules (`court_index`/`pair_indices`/
`slot_index`) — never its own bounds check. Never patch a short roster at
squad-build time — `ncaa.squad_and_ladder` must not invent a player (a synthesised
pid exists in no roster, no pid index and no persisted world, so honors and
championship links point at nobody; a test pins this).
See `docs/AAR-roster-floor-and-walkon-personas.md`.

## ⚠️ Injuries are the ONE non-deterministic system — by design (`app/injuries.py`)
The engine is seed-deterministic everywhere EXCEPT injuries, which roll on **real
entropy** (`random.SystemRandom`). This is a deliberate owner decision ("I never
wanted a deterministic sim… save scumming is fine, I'm the only player") — do NOT
"fix" it back to a seed. Calibration (don't casually retune): `BASE_RATE=0.025`
per-dual, durability-scaled; ~**0.5 starters hurt at any time**; **1-in-100**
season-ending; otherwise **out 1–6 duals**.
- **Wiring:** dice AND the store (`unavailable`/`recover`/`roll_new`) live in
  `injuries.py` — ONE implementation for every league. College passes the `injuries`
  table keyed `(season_id, school)`; the pros pass `gtt_injuries` keyed
  `(_inj_scope(league, year), franchise id)`. Lineup filters: `season.coach_lineup`
  for college, `gtt_seasonmode._lineup` for the pros, both so depth gets pulled up.
  NEVER store injury state on `build_roster` Prospects — they're globally cached and
  shared across saves. **The pro league had NO injuries until 2026-07**: the rules
  lived in `seasonmode`, so `gtt_seasonmode` had nothing to call and durability meant
  nothing after graduation. Don't re-fork them — add a table + keys, not a second
  implementation.
- **Medical redshirt:** a season-ending injury → `world.graduate(rosters,
  redshirts)` repeats the class with an `RS-` tag that persists to graduation
  (RS-Jr → RS-Sr → grad = 5th year). The tag is cosmetic; strip it with
  `world._base_class` anywhere you key off class year.
- **Tests:** an autouse `conftest` fixture disables injuries (determinism);
  `test_injuries.py` re-enables + seeds. See `docs/AAR-injuries.md`.

## ⚠️ Fall transfer portal — the ONLY in-season player movement (`world.fall_portal_proposals`)
After the ITA opener every universe HOLDS at a new **`fall_portal`** phase while the
world runs a cross-division reshuffle (sim proposes → user approves on `/fall-portal`
→ commit). It rescues genuinely mis-allocated talent (a D1-caliber player stuck in a
lower division) and is **deliberately curated**, not a migration:
- Risers are picked on **ability**, NOT ITA results (the opener is too few duals to
  trust). A riser must be a top-2 starter AND clear a **higher division's median
  level** (`div_level`); only the most mis-allocated move, capped at
  `FALL_PORTAL_MAX_RISERS` (**30/gender**). ~60 moves on a fresh world, not thousands
  — do NOT "fix" the cap/median bar away. A receiving program takes at most one riser
  (spread, no blue-blood funnel); displaced players cascade DOWN to fill open seats.
- A mover keeps **both stints** of the split season via a `stint` key on history
  entries (ITA at old school = stint 0, frozen at commit; regular+post at new school
  = stint 1, at year-end). `_record_world_history` idempotency is `(year, stint)`;
  the rollover **bakes** the move and clears the override (`_bake_fall_moves`).
- `fall_portal` is a HOLD only under the world driver (`advance_week` skips it);
  standalone `sm.advance` passes it straight through to `regular`. Toggle with
  `seasonmode.FALL_PORTAL_ENABLED`.
- The slate is **user-editable** (intents→resolve): the `fall_portal` table stores only
  rider INTENTS; cascades are derived by `world.resolve_fall_portal` on every view/commit
  (`_FPPlanner` — which MUST shallow-copy roster lists, since `developed_rosters` is a
  shared cache). You can redirect a rider, add one the sim missed, or drop one. An editor
  move made **while holding in `fall_portal`** is routed through the portal (gets the
  two-stint + cascade); outside the window it's a plain move. See
  `docs/AAR-fall-transfer-portal.md`.

## ⚠️ Module-global caches under the THREADED worker (do NOT re-break — cost 2 outages)
Gunicorn runs ONE `gthread` worker (to keep caches warm), so module-global `_*_cache`
dicts are read by many threads at once. Two hard rules, each learned from a site-down
`KeyError` (`docs/AAR-perf-regression-and-power-index-thread-race.md`, §2 + §2b):
1. **Never `return cache[key]` after a possible `clear()`.** A sibling thread (different
   `season_id`) or a world-advance invalidation can evict `key` between your store and your
   return → `KeyError` → 500 → health flap → "no known healthy instances." Compute into a
   **local**, publish, `return` the local; read with `.get()`, never `key in cache`+`cache[key]`.
2. **Never global-`clear()` a `(season_id, …)`-keyed cache.** A `/player`/career page loops a
   player's seasons; a global clear makes each season wipe the others → quadratic recompute
   (the 18s renders + gunicorn write timeouts). Prune per season (`sm._prune_season`).
When fixing this class, GREP THE WHOLE CLASS in one pass — §2 fixed one cache and left the
siblings "for later"; they caused §2b. `grep -rn "return _.*cache\[" app/`.
3. **Invalidation scope must match EDIT scope, and never rebuild the world on the request
   thread.** A per-team edit (a lineup pin) that calls the global `reset_all()` / `ncaa.
   reset_caches()` nukes the base roster cache and — because `build_roster` gates on a GLOBAL
   `overrides.any_overrides()` — flips ALL ~4k program builds onto the heavy override path, so
   the next full-world page rebuilds everything and starves `/api/health` (site flaps
   unhealthy). Scope invalidation to the affected entity; gate `build_roster` per-program, not
   on "any overrides exist"; prefer a LIVE read for tiny override rows (a lineup is read live
   in `season.coach_lineup`). See `docs/AAR-cache-invalidation-scope-lineup-stall.md`.
4. **A cache is invalidated by BOTH its `reset_*()` calls AND its version STAMP — scope both.**
   The §3 fix scoped the lineup `reset_*()` but missed that `world.prime()` stamps its ~170MB
   roster cache on `ov.roster_version()`, which folded in `lineup`/`doubles` pins. So a lineup
   save still bumped the stamp → the NEXT full-world page (or the background warm) re-primed the
   whole world on the request thread → same [Errno 110] write-timeout stall. Pins are display-only
   (applied live in `build_roster`/`coach_lineup`) and never change the developed roster SET, so
   `prime()`/`is_primed()` now stamp on `ov.move_version()` (move rows ONLY — editor moves + the
   portal commits, all `set_move`). `roster_version()` (move+lineup+doubles) stays for
   `scout_intel` (it projects duals, so it must honor a pin). When you narrow one invalidation
   edge, `grep -rn "roster_version\|move_version" app/` and check every stamp keyed on the same
   edited table. See `docs/AAR-cache-invalidation-scope-lineup-stall.md` (the "IT RESURFACED" §).
5. **‼️ A MEMO CACHE IS ONLY AS CHEAP AS ITS KEY — never resolve a version FINGERPRINT
   inside a loop.** `plays_up()` read `_playup_map(ov.jhsaa_playup_version())`: the map was
   memoised, but the KEY cost a SQLite connect+query+close per call, so every lookup paid
   exactly the price the cache existed to avoid. It obeyed every rule above and saved
   nothing. Inside `load_schools`'s per-row loop (×3 per call, ×2 per program via the
   unmemoised `upstarts()`) that was **39,776 queries and 6.19s to build ONE program's
   roster** — ~65M queries and ~2.8 HOURS for the JHSAA rung, which is why a world advance
   "never finished". Resolve a fingerprint ONCE at the top of an operation and thread the
   resolved map down; cache the BUILT objects, not just the raw JSON behind them.
   ‼️ The trap that hid it: `load_schools` was a pure JSON-to-objects loop with **no DB
   access at all** until play-up landed, so nothing was cached and nothing needed to be.
   **A change can alter a function's COST CLASS while leaving its signature identical** —
   every existing caller keeps calling it as if it were still free. When you add a lookup
   to satisfy a rule, you own WHERE it happens; the owner asked for "a handful of play up
   schools and that was it", not a database read in a loop over the whole association.
   ‼️ MATCH THE MACHINERY TO THE SIZE OF THE PROBLEM: the seed list is **13 schools** and
   the override table is usually empty — a handful of rows needs reading ONCE, not a
   fingerprint-keyed invalidation protocol consulted per school per pass. Diagnose by COUNTING calls
   for the smallest unit of work (one `build_roster`) and multiplying — never by trying to
   reproduce a full season. See `docs/AAR-jhsaa-playup-fingerprint-query-storm.md`.
6. **‼️ A "read-only export" is still on the request thread — it must READ, never
   RESIMULATE.** `research_export.build_jhsaa` had no season to read, so it defaulted to
   `jhsaa.run_season(...)` — replaying an entire ~600-program state championship
   (district double round robin + the full postseason recovery ladder) from scratch on
   every export click. That season is already archived at world week 0
   (`world_jhsaa`/`world_jhsaa_dual`); nothing needed resimulating. On the one-gthread
   design this isn't just a slow request — it's the ONE thread gone for minutes, so it
   reads as the whole site hanging, not just the export. Any new export/report/snapshot
   feature must read the persisted archive (or an existing cache) the way every other
   page in that section already does — never reach for the simulator "because it's
   right there and simpler." See `docs/AAR-jhsaa-research-export-resimulation-hang.md`.

## ⚠️ ONE WORLD PER SAVE — "seed" means three different things (cost a corrupted save)
A save has exactly ONE real world (`world.start_new` resets before creating; the
salt provides freshness, not the seed). "seed" is used for three DIFFERENT things:
the **base world seed** (identifies THE world), the **derived year seed**
(`year_seed = base + 1000×year`, keys per-year season rows and RNG), and per-dual
RNG seeds. They are all plain ints — nothing stops you passing the wrong one.
- **`world.prime()` / `scan_rosters()` take the BASE seed ONLY.** They call
  `get_or_create`: pass a derived seed and they silently BUILD a parallel universe
  of fake players and write a stray world row into the save (this happened —
  `scripts/cleanup_stray_worlds.py` removes the debris).
- **Cross-system consumers (GTT, cups) bind to THE world, never seed-match.**
  `gtt._active_world_seed` resolves to the OLDEST world row; leagues self-heal a
  dangling `world_seed`. Never resolve "the world" via `ORDER BY id DESC` or a
  user-typed number.
- **Don't add graceful fallbacks on world resolution.** Every layer that
  "degrades" (fallback seed, get_or_create, swallowed exception) turns a
  should-be-crash into plausible-looking wrong data — generated players have
  realistic names, so nobody notices. Fail loudly instead.
See `docs/AAR-pro-grad-transfers.md` + the world-binding commit for history.

## ⚠️ ONE WORLD, ONE CLOCK, ONE BUTTON — `/world/advance` is the only advance surface
Every active division×gender universe advances TOGETHER under `world.advance_week`
(which also runs the cross-division slate, the recruiting drip, and `prime()`), and
**`POST /world/advance` is the ONLY route allowed to call it** — enforced by
`tests/test_universe_sync.py`. Never add a second advance button/route, however
scoped: the Season Hub used to carry its own "Advance week →" twenty pixels from the
header's, calling `sm.advance(sid)` on just the universe on screen. Saves forked into
universes at DIFFERENT weeks — D1 men 25 duals deep with a full conference slate, D1
women 15 deep with conference play barely started, both stamped "Week 10". Nothing
errors and every number is honest *for its own universe*; that's what makes it hard
to spot, and two identical-looking buttons meant it happened constantly. It also
skips the fall portal (`sm.advance` passes a `fall_portal` season straight through —
that pass-through is standalone-only). `sm.advance` direct is fine ONLY with no world
(standalone season, tests, calibration scripts).
Detect with `world.universes_in_sync()`; repair with `world.resync_universes()` /
`scripts/resync_universes.py --fix` (steps laggards up to the leader; the world week
is NOT touched). See `docs/AAR-universe-desync-season-hub-advance.md`.

> Related and NOT a bug: **conference play doesn't start until schedule week 4–5.**
> Non-conference is front-loaded (`place()` gates a team's conference duals behind its
> OWN last non-conf week), and D1 carries 6 ITA lead weeks on top, so an early-season
> board legitimately shows big overall records next to 0-0/2-1 conference records.

## ⚠️ The offseason is a LADDER — one advance step per event, never a bundle
`awards → Davis/BJK cups → year rollover → pro-league offseason → preseason`. Each is
one `/world/advance` click. The cups and the GTT off-season used to be interior lines
of `_finalize_year` (nine things behind one button), so neither could be seen or run
on its own — the owner stopped trusting the pro league because they couldn't tell
whether it had touched the college world (it never does: `run_pro_offseason` only
READS `world_graduates`). Do NOT fold a new world-changing event back into
`_finalize_year`; add a rung to the ladder in `advance_week`, marked by state that
already exists (the rows it writes — `world_cups` rows are the cups' done-marker)
rather than a new flag.
- **Cups run BEFORE the rollover** so seniors play their last cup — that ordering is
  the requirement, previously bought by sitting above `_save_graduates`.
- **Cup pool = `world.cup_rosters(w)`** — active universes developed to now + dormant
  universes as persisted in `world_roster`. NEVER `scan_rosters` (it re-derives
  dormant divisions from the generator). `state.get_world_cup` is archive-only; a
  second live-computed view drew from a different pool than the archive, so the cup
  you previewed could crown a different nation than the one that stamped honors.
- Cups are a COLLEGE event (owner rule 2026-07): current rosters, all divisions,
  pre-graduation. The pro league is the graduates-only side. Don't merge them.
See `docs/AAR-offseason-visible-steps-cups-and-pros.md`.

## ⚠️ JEFFERSON — a fictional US state (`JF`), imported from `prep-network`
Jefferson is an alternate-history West Coast state (~17.6M) whose 20 counties stand on
real southern-Oregon / northern-California / northern-Nevada / western-Idaho ground. It
is the **55th** entry in `juniors.US_STATES` — that list is NOT 50 states, it already
carries DC and Puerto Rico / USVI / Guam as first-class entries (and `scout_intel.
US_REGIONS` maps 58 codes, adding AS/MP/BC). Jefferson is an ORDINARY state here: `("Jefferson","JF")` in `juniors.US_STATES`, `STATE_REGION
["JF"]="W"`, `scout_intel.US_REGIONS["JF"]="Pacific"`. Its recruits are **generated
here** — prep-network supplies INSTITUTIONS only; never import that repo's players.
Traps:
- **The `us_states["JF"]` city pool is UNCAPPED (owner rule 2027-08) — but its SHARE of
  the western pool is still the thing that bites.** It feeds `roll_us_hometown` (flat
  choice, so its population repeats are the weighting) AND `ncaa.towns_in_region("W")`
  (dedupes, so only the DISTINCT count counts) — the pool every western program draws
  local base-roster players from at `LOCAL_REGION_TARGET` 0.70. Against the ORIGINAL
  ~150-city hand-curated west, all 272 cities made Jefferson **64%** of that pool
  (every CA/OR/WA roster filled with Jefferson kids, NOTHING ERRORED), which is why a
  46-city cap existed. The 2027-08 hometown rebuild (`scripts/build_hometowns.py`)
  took the west to ~729 real cities, so the full 272 is ~27% vs a ~23% population
  share — accepted. `scripts/import_jefferson.py` reports the share and warns past
  **35%**: if the western pools ever shrink, a cap must come back.
- **`US_JUNIOR_TENNIS_ORIGIN_WEIGHTS` no longer sums to 1.0** (~1.134) — deliberate, they
  are relative and `rng.choices` renormalizes. JF 0.1400, with OR/NV/ID/CA shaved by the
  county share Jefferson takes. Measured: **JF 188** · CA 186 · FL 166 · TX 113 · NY 82.
  One class is noisy enough to reorder the top two — average several before retuning.
- **Jefferson DEVELOPS; its kids LEAVE, and that is the point.** Jefferson produces
  talent at a top-tier rate (the origin weight above, ~188 a class, second only to CA)
  and most of it goes elsewhere to play — exactly as it does for California, Texas and
  Florida. "A good tennis state" has never meant "a state that keeps its own kids", and
  a big in-state D1 footprint is NOT how the state's quality is expressed. Jefferson has
  **four D1 programs**, all in existing leagues: the flagship (University of Jefferson)
  in the Pac-16, **Jefferson State in the WAC**, **Southern Jefferson in the Big West**,
  **Jefferson A&M in CUSA**. The **Jefferson Valley Conference is D2** (8 programs,
  including Galena) — do not put it back in D1. Jefferson's GEOGRAPHY is otherwise
  ordinary: it is region "W" and gets no special pull table. Out-of-region signees are
  fine and expected; the regional preference is soft realism, not a gate.
- **JF is NOT in `SCHOOL_LOCAL_TERRITORY`** (it has a real `STATE_REGION`, so the normal
  geo tug already applies; adding it stacks `LOCAL_TERRITORY_PULL` 6.0 on top), **NOT in
  `WARM_STATES`** (it's the PNW), and **NOT in `cities._STATE_HEAT`** (its list is already
  population-repeated; heat would multiply an existing weighting).
- **‼️ A FLAGSHIP IS NEVER SUBSUMED (owner rule 2027-08).** Galena University was once
  written as a rename of **Nevada** — Galena County IS Washoe County, so absorbing UNR
  looked tidy. It was WRONG and was reverted; do not redo it. Jefferson may take the
  ground and the regional publics, but a real flagship keeps existing. Galena is net-new,
  badge-marked, and sits BESIDE Nevada in the MW.
- 39 colleges across D1–D4 (~2.2/million, matching CA), but only FOUR in D1 — a
  17.6M state with a dozen D1 programs broke immersion. Several were ABSORBED — real
  programs standing on Jefferson ground, RENAMED so each keeps its own logo (Oregon Tech→
  Cascade Polytechnic, Southern Oregon→Siskiyou, Cal Poly Humboldt→Humboldt Polytechnic,
  Chico State→Bidwell State, College of Idaho→College of Jefferson). Only **three** Golden
  State campuses relocated (D3 CA 20→17, not 20→11 — the GSAA exists to fill a D3
  California hole). Dean (WY), Elms (NV), Lasell (AK), Talladega (VI), Judson (NV) and
  Voorhees (GU) were left in place because they are what keeps those states on the D3
  map — worth a look before moving one. Fontbonne (WY) and Carroll (MT) were taken by
  owner decision; Montana now has NO D4 program.
- **The flagship is in the Pac-16 (`top`, 16–33.5 budget) and Colorado State moved out to
  the MW** to keep it at 16 — a correction, not a demotion, since that is where CSU plays
  in real life. Galena is **D2** (in the JVC); Jefferson A&M took the D1 seat, in CUSA. Chosen over renaming Pac-16→Pac-18, whose abbr is a key in `CONF_PRESTIGE`,
  `CONF_TIER`, `state.py::_P5` and `polls.py::_POWER_CONFS`. Gonzaga is in the **Pac-16**,
  not the WCC — check the data before reasoning about it.
- **‼️ TODO (owner approved, DEFERRED): push the school-name cleanup INTO prep-network.**
  The tennis association renamed 62 confusingly-similar schools and handed 9 magnets'
  seats to their city flagships (`import_jhsaa.RENAMES` / `SUBSTITUTIONS` are the
  authoritative list; `docs/JHSAA-name-cleanup-2027.md` is generated from them). The
  owner wants prep-network brought in line but **explicitly did not want it done
  immediately** — do it when asked, never on your own initiative. It is already
  automated and verified end-to-end on a copy: `python3 scripts/rename_prep_network.py
  --dry-run`, then without the flag. Scope: ~59k occurrences in ~6.3k files PLUS ~5.7k
  contest FILENAME slugs, so it changes public URLs — that is why it is a separate
  explicit step and not part of the import. The script preflights its own safety
  invariants and is idempotent. Only the 62 RENAMES rewrite source records; the 9
  substituted magnets keep their identity in prep-network and merely stop sponsoring
  tennis, so they must NOT be renamed there.

## ⚠️ THE JHSAA — Jefferson's high-school season is SIMULATED and VISIBLE (`app/jhsaa.py`)
Owner rule 2027-08, and it REVERSED an earlier "keep the HS season invisible" decision:
Jefferson's ~335 girls'/~292 boys' programs play a full season **in this engine**, browsable
at `/jhsaa`, and its graduating seniors ARE Jefferson's entries on the college recruit board.
`prep-network` supplied the INSTITUTIONS only (`scripts/import_jhsaa.py`); no player ever
comes from that repo. Design: `docs/DESIGN-jhsaa-high-school-season.md`; lessons:
`docs/AAR-jhsaa-high-school-season.md`.
- **Two format axes, both explicit.** SHAPE (`jhsaa.dual_format`): regular **5S/2D**,
  state tournament **1S/4D**, early non-district **3S/4D** (see below) — all odd, so a
  dual can never tie, and there is no tie-breaking logic anywhere. SCORING
  (`jhsaa.MATCH_FORMAT` = `PRESETS["high_school"]`): **all high-school tennis is no-ad,
  and DOUBLES is a full best-of-3, not the college 8-game pro set.** `simulate_dual`
  defaults to the college presets, so both `singles_fmt` and `doubles_fmt` must be
  passed — miss `doubles_fmt` and lines silently score `5-8`. Every match plays to
  completion; there is no clinch in high school.
- **‼️ THE EARLY NON-DISTRICT WINDOW PLAYS 3S/4D, not 5S/2D (owner rule 2027-08,
  `jhsaa.EARLY_FORMAT_PHASE = "early"`).** A JHSAA roster carries 12 players but the
  league card only gives nine of them a real match; this association had no JV system
  to develop the rest (it does now — see the JV § below, which does NOT supersede this
  window), so the FIRST non-district window (played in `play_regular_season`
  BEFORE any district round — `NONDISTRICT_MIN/MAX` × `EARLY_SHARE` already lands most
  programs at 1-3 duals here) plays 3 singles / 4 doubles instead, putting roster spots
  #10-11 on court. **Scoped to that one block only**: the mid-season non-district window
  and the late tune-up are both scheduled AFTER district play starts and stay
  `phase="regular"`; district duals are always `phase="regular"`; the mid-season Match
  SHOWCASES and the whole postseason stay 1S/4D, untouched. All seven courts are real,
  TOSS-rated results on the existing `FLIGHT_WEIGHTS` table (D4's 0.10 weight keeps the
  extra developmental court from moving TOSS much). Displays as an ordinary INVITE tag
  with a "3S/4D" `d.round` chip, the same slot a showcase names its event in.
  `_lineup`'s doubles-forward philosophy overlay (`_arrange_regular`) is built for the
  5S/2D card's nine fixed positions and does not apply here — the early card's top
  three land on S1-S3 and the next eight on D1-D4 in plain ladder order by
  construction, which is the whole point (no overlay to bench #10-11 behind).
  `district_oowp`'s opponent filter reads by EXCLUSION (not `phase == "regular"`) for
  exactly this reason — an inclusion filter silently drops a new phase's opponents from
  OOWP. The format-profile metrics below deliberately EXCLUDE this phase from their
  "regular" sample — it is a third shape, not noise to average into the 5S/2D baseline.
  See `docs/AAR-jhsaa-early-nondistrict-3s4d.md`.
- **SCHEDULE (owner rule 2027-08, CAPPED 2026-08): district double round-robin UNDER
  `jhsaa.DISTRICT_DUAL_CAP` (18) + 4-8 non-district.** A league of ≤10 teams plays the
  full home-and-away double; a bigger one plays pass 1 COMPLETE (everyone meets
  everyone — that is what a league season is) plus only the first rounds of the
  mirrored pass 2 until the cap — an unbalanced second leg, 16-18 district duals,
  never more (owner: "double round robins are bad when leagues are more than 10
  teams"). This REVERSED the earlier "never cut the second league leg" rule. The
  mid-season split point is `district_pass1_rounds`, NEVER `len(rounds)//2` — on a
  capped league the list is asymmetric and a halfway split breaks pass 1 mid-stride.
  Which opponents rematch varies by season (truncation runs on the seasonally-rotated
  pass-2 order). To shorten seasons further, lower the cap or shrink `MAX_DISTRICT`
  in `scripts/import_jhsaa.py`.
  `NONDISTRICT_MIN/MAX` is an ALLOWANCE ON TOP, not a season total. Non-district
  opponents are drawn on **geography** (same county → area → anywhere), then **talent**
  (nearest strength off this year's roster, so weak teams aren't fed to teams that beat
  them, and pairings re-form yearly), gated to the **same classification or one apart** —
  so non-district pairing runs over the WHOLE gender at once, and awards/state selection
  come after.
- **‼️ A DOUBLE ROUND ROBIN IS TWO SEPARATED PASSES, NOT A HOME-AND-HOME SERIES.** The
  order of play is the schedule — there is no clock inside a JHSAA season, so a dual's
  POSITION in `schedule` is all the calendar there is (`state._jh_dates` just lays that
  order on a spring calendar). `play_regular_season` runs, across the whole gender:
  **early non-district → district pass 1 → mid-season window → district pass 2 → late
  tune-up**. The league is generated as ROUNDS (`_rr_rounds`, circle method — every team
  plays once per round), never `for a: for b: for leg in (0,1)`, which is a correct
  double round robin and a schedule no high school has played: it put both meetings with
  every opponent on consecutive dates all season.
  - **A plain `reversed()` is NOT the mirror** — it makes the last opponent of pass 1 the
    first of pass 2, recreating the back-to-back pairing for one opponent per team while
    the other ten look perfect. `_mirror_orders` scores every rotation of both families
    (serpentine and straight mirror) by its worst pair and keeps those clearing HALF A
    PASS; `district_rounds` draws one per season, so the rotation varies by year and the
    separation floor does not.
  - **Venue is ONE BIT PER PAIRING**, not per meeting — pass 2 is its inverse. "The return
    match reverses venue" therefore holds by construction, and `_orient`'s home/away
    balancing (which only flips that bit) cannot break it.
  - **The dual SEED comes off the PAIRING, never its position** (`play_rounds`). The
    caller SLICES the round list around the mid-season window, so a local `enumerate`
    restarts at zero on the second pass and every second-pass dual gets a different seed
    from the same district played straight through by `play_district` — identical inputs,
    different results. The ordered (home, away) pair is already unique in a double round
    robin, so no index is needed.
  - **District place is district win %, then the association's TIEBREAK LADDER** (owner
    rule 2027-08, `_tiebreak`): **1.** head-to-head among the tied teams · **2.** the
    aggregate of those meetings (courts won − lost across the series) · **3.** overall
    season record · **4.** Power Index · **5.** OOWP. A tie is resolved as a GROUP, not
    pairwise — three-way head-to-head is a mini-league and a pairwise comparator on it
    isn't transitive. ⚠️ Every LEAGUE figure is read off the district schedule entries,
    NEVER off `points_for`/`points_against`: those accumulate over every dual a team
    plays, so using them lets a blowout in the non-district window decide a district
    title (the same trap in `_challenge_pairs`'s provisional mid-season rank). Settling
    happens AFTER the Power Index exists, since rung 4 reads `t.power`.
  - Non-district pairing still seeds on ROSTER STRENGTH, not results, so the early window
    can lead. The ONE exception is the mid-season **challenge** (`_challenge_pairs`),
    paired after pass 1 on district record so a #3 draws another district's #3 — it only
    exists because it sits after a pass. It is a `challenge` LABEL on a non-district dual,
    never a phase (a phase would change its dual format and drop it out of TOSS), and it
    can never touch district place. The label is IN-MEMORY ONLY and deliberately not
    archived — the owner does not want it distinguished on a card.
  See `docs/AAR-jhsaa-district-schedule-passes.md`.
- **‼️ THE MID-SEASON MATCH SHOWCASES — the only 1S/4D duals before the postseason
  (owner spec 2027-08, `jhsaa.SHOWCASE`).** The association's postseason is a different
  sport from its league season (5S/2D all spring, 1S/4D from Sectionals on), so a
  program that only plays its league card arrives at Sectionals having never fielded
  the lineup it must win with. Six to eight weekend windows in the mid-season block,
  half of each kind, ~50% of programs attending — nearly all of them once.
  - **Two phases, not one** (`showcase_pod` / `showcase_tiered`): a phase is the
    archive's identity for an event, and these two are scored and dated differently.
    **POD** = 4 programs, full round robin, 3 duals, ONE Saturday, **one 8-game pro set
    a court** (`PRESETS["pro_set_8"]`, 7-point tiebreak at 8-8) — three pro sets is the
    USTA junior daily limit exactly, which is why the pod is sized at 4 and scored this
    way. **TIERED** = 6 programs, 2 duals a day over Friday-Saturday, the ordinary
    high-school best-of-3 (it exists to replicate State length). Six, not five: a
    6-team round robin's first four rounds are four PERFECT matchings, so nobody sits
    out a session. **‼️ ALL JHSAA PLAY IS NO-AD, showcases included** — both formats.
  - **‼️ NOT A TOURNAMENT, BUT FULLY RATED.** No bracket, no draw, no elimination, no
    champion, no title — and **they ARE TOSS-rated, which is the point of playing
    them** (`SHOWCASE_RATED` True; kept in the cutoff table AND the prestate
    recomputes). "Non-competitive" means no advancement, NOT that the results are
    thrown away: playing power programs from other leagues is precisely what a program
    wants out of the weekend, and TOSS is 40% APR + 40% FQI + 20% oGS with all three
    opponent-weighted — a season played only inside one league rates on a nearly
    disconnected graph, and the showcases are the cross edges. **A different dual shape
    does not make a result less real.** `rating._flight_score` normalises by the weight
    actually CONTESTED per dual, so a 1S/4D showcase (2.85) and a 5S/2D league dual
    (3.70) each contribute a 0-1 share — which is what lets two shapes share one table.
    ‼️ `FLIGHT_WEIGHTS`'s D3/D4 are therefore load-bearing in the REGULAR season now,
    not just in the in-postseason recomputes. They also count in the record and feed
    every résumé the awards read.
  - **‼️ GROUPS ARE SHUFFLED AND DEALT — SIMPLER MATCHING BEATS PRECISE MATCHING HERE
    (owner rule 2026-08).** `_showcase_groups` shuffles the tier's pool and deals
    groups of 4 (pod) / 6 (tiered) in ONE PASS. It was a placement solver first — seed
    a group, scan the whole pool for members that fit, pop the seed and rescan when it
    could not be filled — which is quadratic per tier per window and was written while
    hunting a rung that stopped finishing. **The quality of a showcase dual comes from
    the TIER CUT; who lands in which group inside a tier carries no information**, so
    choosing carefully was precision spent on a decision that does not matter. Owner:
    "just randomly match people and be done… so long as it's truly random and follows
    the rules outlined (no district matchups) it should be fine."
  - **‼️ HARD DISTRICT GUARDRAIL, enforced at GROUP formation, not per pairing.** A
    group is a round robin, so every member meets every other: a candidate sharing a
    `(classification, name)` district with ANY member is held back and dealt into a
    later group — that IS the spec's "swap across pods", done in one pass rather than
    by repair. `showcase_conflicts` is the validator and `play_showcases` refuses to
    play a slate that fails it. It is the ONLY rule inside a tier; do not add a second.
  - **`SHOWCASE_ENABLED` is the kill switch and the FIRST diagnostic.** Checked at the
    top of `showcase_schedule`, so off it returns before touching a team and the rung
    runs exactly the pre-feature code. The events add ~234 duals to a gender's ~5,100
    (~5%): if the rung is slow with it off, they were never the cause.
  - **The 2-day block TRADES a weekday date** (owner spec) and the pod does not, so
    `play_showcases` returns what each program traded and the late tune-up's allowance
    is shortened by it. ‼️ Showcase duals are non-district but are NOT part of the
    `NONDISTRICT_MIN/MAX` allowance — counted there, a pod would eat a program's whole
    remaining card.
  - **‼️ A SHOWCASE MUST NOT FREEZE THE ORDER OF ABILITY.** The freeze binds from a
    program's first POSTSEASON dual; freezing it in April would bind the championship
    lineup to a mid-season ladder — the drift the anti-stacking rule exists to stop.
    A showcase dresses the LIVE ladder with the league's bench rotation, arranged onto
    the 1S/4D card by the same `_arrange_state`.
  - **Tiers (Open/B/C) are statewide and CLASSIFICATION-BLIND**, cut on a provisional
    mid-season standing (`_showcase_rank` — TOSS does not exist yet mid-season). The
    scarce 2nd/3rd seats go to the Top 25 (`SHOWCASE_ELITE`), max 3 statewide.
  - **A window lands on ONE weekend** (`world._jh_showcase_days`): the slate is played
    session by session across the whole gender, so a window occupies a contiguous block
    of rounds and is dated as the single event it is. Left on the Mon/Wed/Fri/Sat
    pattern a pod would read as three duals on three days — a different event with
    different daily limits.
  - On a card these are their own tag (`SHOWCASE`, naming Pod or Tiered) — and a plain
    non-district dual is now labelled **INVITE / "Invitationals"** (owner, 2027-08):
    that is what the association calls the duals a program arranges outside its league.
    "Non-district" remains the right word for the scheduling RULE, never for the match.
  See `docs/AAR-jhsaa-mid-season-showcases.md`.
- **‼️ THERE IS NO SEPARATE POSTSEASON RECORD (owner rule 2027-08).** A record is a
  record: the NCAA and the NFHS both carry the postseason INSIDE the season total, and
  neither publishes a regular-season record beside it as though the year had two halves.
  So `run_season` plays every state draw AND the TOC and only THEN snapshots `t.record`
  into the standings, and the school page shows ONE record with a FINISH beside it
  (`state_finish` / `toc_finish`) — never a "Post 6-1" tile, which invited the owner to
  add 27-4 and 6-1 into 33-5 when the 27-4 already contained the six. The snapshot used
  to sit inside the loop that ran each classification's state draw, which was right for
  state (that group was done) and silently wrong for the TOC, since the TOC needs every
  group's champion and so cannot run until the loop is over: the six programs in it
  archived their last duals on their SCHEDULE and left them off their RECORD. 131 of 137
  balanced and the six that didn't were exactly the TOC field — the shape a spot check
  misses. Pinned by `test_every_archived_record_covers_every_dual_played`.
- **A program's RECORD persists year to year, not just its trophies.** `world_jhsaa`
  archives `record`/`drecord`/`place` per school per year, and `jhsaa_school_history`
  emits a row for EVERY archived year — a program history has to show the losing seasons
  too. It once returned only years with a title or an honour, so a school looked like it
  had never played in between.
- **‼️ HONOURS ANNOTATE SEASONS; the SEASONS are the history.** `jhsaa_school_history`
  returns TWO things — `totals` (the career) and `seasons` (one row per archived year) —
  and every number in `totals` is a FOLD OVER `seasons`, so the two halves of a program
  page cannot disagree and a new season moves the totals only by being appended. Do NOT
  add a `world_jhsaa_school_season` table: the postseason record, courts won/lost, state
  seed and state finish are all DERIVED from `world_jhsaa` + `world_jhsaa_dual` (one
  indexed read of ~26 rows per season), and a second store would be a second source of
  truth for numbers the archive already determines. Before persisting, check whether the
  thing is a PROJECTION of a layer you already have.
- **Seeding runs on TOSS, not on win-loss** (`jhsaa.power_index` → `app.rating`). TOSS is
  oregontennis.org's Tennis Opponent-Strength System, the same composite the college
  league uses: **0.40 APR + 0.40 FQI + 0.20 oGS**. `qualifiers` sorts at-large bids AND
  seed order on it, so an automatic bid buys entry rather than a seed. Rules:
  **`jhsaa.FLIGHT_WEIGHTS` is the association's own table** (S1 1.00, S2 0.75, S3 0.25,
  S4/S5 0.10, D1 1.00, D2 0.50 — max 3.70/dual, owner's numbers); it is NOT the college
  table and NOT Oregon's 4S/4D one, and it is the only place a flight is weighted.
  It is computed over the **whole gender at once** (non-district play crosses
  classifications, so rating a class alone cuts those edges out of the graph) and over
  the **regular season only** (`rating_duals` drops `phase == "state"` — it is the
  seeding input, and state's 1S/4D would drag D3/D4 into a table that stops at D2).
  Game share is parsed back out of the archived score strings (`jhsaa._games`), so no
  column was added and pre-TOSS seasons still rate. **The index is ARCHIVED per school
  per season (`pi` on the standings rows) and read back, never recomputed** — a rating
  is a function of the whole results graph, so a re-read would only match by chance, and
  a ranking that drifts from the seeds it produced is the NCAA region-drift bug again.
  `jhsaa_group_ranking` falls back to win% for seasons archived before TOSS. **Archive it
  at FULL precision and round only in the template** — it was stored `round(pi, 6)` once,
  which looks free because nothing shows more than 3 decimals, but `qualifiers` seeds on
  the raw value while `jhsaa_group_ranking` re-sorts the stored one and breaks ties by
  school name, so any two teams inside 1e-6 collapse and the displayed ranking
  contradicts its own seeds. Rounding is a display concern; it does not belong in a
  store that exists to reproduce a decision.
  See `docs/BLOG-toss-in-a-third-format.md`.
- **‼️ STATE QUALIFICATION IS EARNED ON COURT (owner rule 2027-08, expanded fields).**
  State is **40 in EVERY classification** (`jhsaa.STATE_FIELD`; 9A and 8A were
  raised in 2027-08 because the association's deepest classes were leaving plainly
  good teams home, and **7A followed in 2026-08** — it was simply the class that pass
  did not touch, never a special case). It stays a per-class TABLE because the field
  size is an owner decision per class and the whole ladder derives from it. **A 40 IS A 24 WITH A QUALIFIERS ROUND IN
  FRONT OF IT** (`run_state(champions=)`): the Zonal champions take a DOUBLE bye
  while seeds 9-40 play the Qualies and then the First Round, and the eight
  survivors join them in a FRESH draw — so both shapes converge at the Octofinals,
  and there is NO bracket path from a Qualies slot to a main-draw slot (the
  bracket page therefore renders TWO trees, `state._jh_split_state`; one
  positional tree would invent links). The old TOSS wild cards are GONE — a rating
  never hands out a berth again (the report: a #14 missed State while #23 got in by
  winning). Three ways in: the 8 **Zonal champions** — automatic, AND **seeds 1-8 of
  the State draw**. That is a SEEDING guarantee, not a bye rule (owner clarification
  2027-08): a 24-field's eight byes fall to them as a consequence, but a power-of-two
  field has NO byes and they are still seeded 1-8 there. Both shapes are pinned by
  `test_zonal_champions_are_the_top_seeds_byes_or_not` — keep it that way even though
  no class currently plays the byeless shape, since the table can move a class back. Then the
  **‼️ THERE IS NO DISTRICT GUARANTEE — YOU WIN YOUR WAY IN (owner reversal
  2027-08).** It briefly existed and was retired for contradicting the rule it sat
  beside: a district champion could keep losing and still be handed a berth. A
  district title buys a **PROTECTED seat** (entry at Regionals, skipping Sectionals
  and Wards) and NOTHING at State — a champion that loses falls into the same
  recovery pools as everyone else and earns a berth on court or does not go.
  `district_qualifiers` stays in the return and the archive as an EMPTY list so
  seasons played under the old rule still read. So there are TWO ways in, not three:
  a Zonal title, or the **recovery rounds** `super_regional` → `semi_state` →
  `divisional` → conditional `semi_conference` → conditional `conference`
  (Regional losers first, Zonal losers joining at Semi-State, and only once the
  ladder's OWN losers are exhausted do Ward → Sectional → Area losers come in as
  BODIES, never berths). **‼️ NO WARD PLAYBACKS — Ward losers enter at the
  SEMI-CONFERENCE and nowhere else** (owner rule 2027-08). They used to be
  drafted into the Super Regional pool as bodies, which gave them TWO OR THREE
  bites (Super Regionals, a readmission to Semi-State, then Divisionals) while a
  Zonal loser got one, and berths were being earned off them three rounds early.
  Super Regionals is now the 16 Regional losers, full stop.
  **‼️ THE SEMI-CONFERENCE — EVERYONE BUT THE DIVISIONAL LOSERS QUALIFIES FOR THE
  CONFERENCE ON COURT (owner rule 2027-08).** The Conference awards the largest
  single block of berths in recovery (14 of 40) and used to admit its whole field
  directly — **22 of its 28 entrants were Ward/Sectional/Area losers who had
  played NO recovery dual at all**, level with 6 Divisional losers who had come
  through three rounds. Owner: they "should have to play a qualify match rather
  than giving the teams direct access when other teams will have played several
  matches where they've gotten wins before making it to that round." So a byeless
  `semi_conference` (44 teams → 22 in a 40-field class) now sits in front of it.
  It grants **ZERO extra bites at a berth** — the Conference is still the only
  berth-bearing round these teams see — it makes them earn the seat, and that is
  exactly what separates it from the retired playbacks. Dormant wherever the
  Conference is.
  **‼️ ITS POOL WALKS THE LADDER BACK IN ROUND ORDER, and never skips a survivor
  of a LATER round**: district champions still outside → **Semi-State losers the
  Divisionals could not take** → **Super Regional losers Semi-State could not
  readmit** → Ward → Sectional → Area. ATR orders WITHIN a tier, never across
  one. The two orphan tiers are usually empty and were in NO tier at all before —
  `bodies` starts at Wards and `taken` excludes every Regional and Zonal loser,
  so an orphan could be walked straight past by a Ward loser. It is live in the
  24-classes already (the Divisionals take 10 of 11 Semi-State losers, orphaning
  one a season) and invisible only because those classes never convene a
  Conference. CONFERENCE is the last rung and fills every berth the ladder's own
  losers could not: ONE pool — **Divisional losers plus the Semi-Conference
  winners, and nothing else** — reseeded and paired like every other round. It
  takes twice the outstanding berths, so it is byeless by construction, and it
  convenes only if berths remain: dormant in the 24-classes, 28 teams in the 40s.
  **Units are LETTERED STATEWIDE,
  BACKWARDS FROM Z, carrying their own class** — "6A-Z Conference", "6A-Y
  Conference" — via `jhsaa.reletter_conferences` (the Divisions' pattern: after
  both genders, girls first, classes bottom-up, letters never recycled; past A
  the sequence doubles, ZZ, ZY, …).
  **‼️ ITS POOL IS RANKED ON `jhsaa.atr`, NOT TOSS** — Average Team Rating,
  `ATR_TOSS_WEIGHT` (0.5) × `pi_raw` + the rest win percentage, and the ONE
  place the association rates a team on anything but TOSS. TOSS is an
  opponent-strength composite, so a middling team in a brutal district is
  propped up by the company it keeps while a 20-win season against an ordinary
  schedule rates below it — right for seeding a draw, wrong for the last seat in
  the tournament. Arithmetic is
  DYNAMIC (`_recovery`: berths = field − champions; the Semi-State floor is
  `ceil(4·berths/3)` **rounded UP TO EVEN before the reservoir is sized** — rounding
  after left 4A one berth short of a 40 field at full size while every other class
  filled, and the scaled fixture could not see it). `jhsaa.recovery_shape(group)`
  PROJECTS the whole ladder from the constants with no season, which is what lets
  `jhsaa.sponsor_floor(group)` state the DATA invariant the Semi-Conference needs:
  **76 sponsors per gender in a 40-field class** (`WARD_FIELD` 32 + the 44-team
  qualifying field). It is a projection, not a second implementation — a full-size
  run must land on it. Under the floor the round degrades LOUDLY rather than
  shipping a short State field: the best bodies by ATR enter the Conference
  directly (`sc_head`) and a warning names the class. Draw rule: never immediately
  replay the team that just eliminated you — and **bye selection and pairing are
  ONE problem**, since choosing byes first froze a bye team into an unreachable
  rematch. Finishes for recovery runs SUPERSEDE the ladder round that sent them
  there.
  - **‼️ NOBODY REACHES STATE ON A BYE — the rounds are BYELESS BY CONSTRUCTION
    (owner rule 2027-08, after three reports).** Recovery is THREE rounds and each
    pairs its ENTIRE field: **Super Regionals** (Regional losers) → **Semi-State**
    (SR winners + Zonal losers + readmitted SR losers) → **Divisionals** (the
    best Semi-State losers), the last two taking berths. A bye is therefore not
    disallowed, it is impossible. The rounds used to be CUTS sized to whatever the
    pool was, leaving byes over — a No. 19 seed byed through both; a No. 4-TOSS
    Zonal loser took the Semi-State bye and reached State "without winning their
    district"; and every rule patch just moved which bye was unearned. The
    Divisionals absorb the berths that used to become byes AND fixes the
    inequity that caused it: a Regional loser got two or three chances, a Zonal
    loser one. Now everyone in recovery gets two. **The State field is FIXED**
    (32/24) and recovery conforms — never extra duals, a deeper cut, or a short
    field. Bodies come best-pool-first: readmitted **SR losers**, then a walk back
    through **Ward → Sectional → Area** losers, best TOSS within each tier; a body
    is a chance to PLAY, never a berth. `jhsaa.DIVISIONAL_NAME` is the only place
    the round is named — PLURAL, no "Round" ("7A Divisionals"), matching every
    other stage heading; the per-dual UNIT keeps the singular "Division N". **‼️ DIVISIONS ARE NUMBERED STATEWIDE**, unlike every
    other unit (a Region IX exists once per classification; there is ONE Division
    I in Jefferson per year): `jhsaa.renumber_divisions` assigns them after BOTH
    genders have played — girls first, then boys, classifications bottom-up
    (1A → 9A) — because how many there are depends on how many berths the
    round had to fill that year. Roman on the honours chip like the rest
    ("Division XI"). Pinned by `test_no_recovery_round_has_a_bye`; explainer in
    `docs/JHSAA-road-to-state.md`.
  See `docs/AAR-jhsaa-state-expansion-recovery-rounds.md`.
- **‼️ 1A CROWNS ON A FIXED 24-team shape — not the dynamic format above (owner
  rule 2027-08; 2A left it in the 2033 realignment).** 1A and 2A used to share one
  combined "2A-1A" group (neither cleared the 76-sponsor floor the dynamic
  Semi-Conference needs on its own), then crowned separately on this shape. **2A
  now plays the standard ladder** — the realignment took it to 95 programs, 95
  girls'/87 boys' sponsors against the 76 floor, and the owner's rule is that its
  playoff "mirrors every other classification"; 1A is the only class left on the
  24. `jhsaa._recovery_24` is a DIFFERENT, non-dynamic wiring, not
  `_recovery` fed a smaller number — but **the Zonal-champion guarantee is
  UNCHANGED here, same as every other class**: an early design retired it for
  1A/2A only (Zonal win = advancement only, no automatic berth), shipped, was
  playtested, and was explicitly rejected by the owner — do not reintroduce
  that version. **Zonal champions are still 8 automatic State berths, seeded
  1-8** exactly like the other seven classes; only the RECOVERY ladder
  underneath them is re-plumbed:
  ```
  Zonal 16 (Regional winners) -> 8 winners AUTOMATIC state berths, 8 losers -> Super Regional
  Regional losers (16), split by PRIORITY: district-champion losers first
    (best-TOSS if >8), then highest-TOSS others, until 8 -> Super Regional
    (the "preferred" 8); the other 8 -> Semi-State directly (the "held-back" 8)
  Super Regional 16 (8 Zonal losers + 8 preferred Regional losers)
    -> 8 qualify, 8 losers -> Semi-State
  Semi-State 16 (8 held-back Regional losers + 8 Super Regional losers)
    -> 8 -> Divisional, 8 -> Semi-Conference
  Divisional 8 -> 4 qualify, 4 losers -> Conference
  Semi-Conference 8 -> 4 winners -> Conference (no berths)
  Conference 8 (4 Divisional losers + 4 Semi-Conference winners) -> 4 qualify
  8 (Zonal) + 8 (Super Regional) + 4 (Divisional) + 4 (Conference) = 24
  ```
  This gives district champions the strongest recovery protection (first claim
  on Super Regional slots) WITHOUT an automatic State berth — they still have
  to win. `_recovery_24` returns only the 16 EARNED qualifiers; the caller adds
  the 8 automatic Zonal champions using the SAME seeding code every other class
  uses (`zc + rest, champions=len(zc)`) — there is no 1A/2A-specific branch in
  the State-seeding loop, only in the recovery loop.
  Every round size is a FIXED function of `PROTECTED`/`WARD_FIELD` alone, never
  of sponsor count — so `sponsor_floor` for these two is just `PROTECTED +
  WARD_FIELD = 48`, not the dynamic 76-body formula. `run_state` needed NO
  changes: a 24-field with `champions=8` already selects the plain single-draw
  branch (seeds 1-8 bye, 9-24 play in), never the Qualifiers-Round expansion.
  District-champion `PROTECTED` entry at Regionals is unchanged. See
  `docs/AAR-jhsaa-1a-2a-classification-split.md`.
- **‼️ 1A'S ROAD TO STATE PLAYS 2S/3D — a PILOT, scoped three ways (owner rule
  2026-08, `docs/AAR-jhsaa-1a-2s3d-postseason-pilot.md`).** `dual_format(phase,
  group)` / `lineup_need(phase, group)` / `_arrange_1a_postseason`. 1A alone, its
  ROAD ONLY (Sectionals→State), postseason only. Read the shape through
  `dual_format(phase, group)`, never `dual_format(phase)` — the bare call resolves to
  1S/4D and is now a WRONG ANSWER for a 1A postseason dual.
  - **‼️ `POSTSEASON` IS NOT THE RIGHT SET — it contains `"toc"`.** The Tournament of
    Champions fields every class's champion at ONE shape, so 1A's entrant plays it at
    1S/4D like everyone else (owner: "1A just goes back to 1/4 for TOC"). The branch is
    `phase in POSTSEASON and phase != "toc"`.
  - **The REGULAR SEASON and the SHOWCASES are untouched, 1A included** — owner: "3/4
    is fundamentally contained within 2/3 so a coach can see it without any tweaks". A
    1A coach already manages three singles courts every league dual.
  - **‼️ THE ANTI-STACKING RULE IS ONE MECHANISM, GENERALISED — not a second regime.**
    The top N of the frozen order are consumed by the singles seats PLUS D1 and the
    coach picks which of them plays singles; **the best player is NOT pinned to S1**
    (a team may pair #1 into D1 and start #2 or #3). 1S/4D pools the top THREE and
    picks ONE; 2S/3D pools the top FOUR and picks TWO. `_arrange_state` already
    implemented the general rule and needed NO change. Do not "fix" the pilot to pin
    S1 — that draft was written and explicitly corrected.
  - **The freeze stores the FULL ladder**, sliced per phase — that is what lets 1A's
    road dress eight and its TOC entry nine off ONE frozen order. A fixed-length
    freeze would force a re-freeze for the TOC, i.e. the mid-postseason re-rank the
    rule forbids.
  - **‼️ `_slot_players` MUST be told the shape its side was DRESSED with** (the JV
    season's trap, second instance): without it a 1A postseason D-slot resolves
    against 1 singles instead of 2 and names the WRONG PLAYERS in the box score,
    the award résumés and the archive, raising nothing. `_credit` takes `opp_group`
    for the same reason.
  - `FLIGHT_WEIGHTS` needed nothing (S1/S2/D1-D3 all already weighted; TOSS
    normalises by weight CONTESTED per dual). `ROSTER_FLOOR`/`jv_pool` key off the
    REGULAR shape and are untouched.
  - **Measured** (`scripts/jhsaa_1a_format_pilot_calibration.py`, 179 programs ×
    20 trials): the format decides **~27-30% of evenly-matched duals** (same winner
    only 70-73%) while mismatched duals agree 85-90% and the upset rate moves ≤3
    points — it flips close matches without making the association chaotic. Cost: the
    postseason roster drops 9→8, and for **71% of programs the cut player is within
    2 OVR** of dressing. The new S2 goes to the #2 player 79% of the time, #3 20%.
  - **‼️ THE NAILBITER RATE IS A FEATURE, NOT A CAVEAT (owner, 2026-08).** An
    evenly-matched 1A dual lands **3-2 ~70% of the time under BOTH formats** — a
    five-point shape in a flat field is coin-flip-adjacent by construction, and that
    is the juice a 24-team 1A bracket is meant to have. A draft filed this under
    "noise" and buried the most characteristic number in the study.
  - **‼️ CLOSENESS COMES MOSTLY FROM COURT COUNT** (owner preference "I prefer the
    1/4 format over something more traditional", MEASURED —
    `docs/reports/REPORT-jhsaa-dual-shape-competitiveness.md`). Five-court shapes
    finish on ONE court **61-73%** of the time, seven-court shapes **58-60%**, and
    every seven-court shape sits in that band whatever its composition; holding
    doubles share fixed and changing only court count moves it **8-13 points**. A
    dual is an average over its courts and fewer courts average less. **Doubles share
    is a REAL SECONDARY term** — ~6-10 points across a full 80%→0% sweep at five
    courts (girls 68/73/70/65/63, boys 67/67/62/62/61). **That is why 2S/3D was the
    only workable pilot shape**: it holds five courts while adding the singles seat,
    2S/4D and 3S/3D are six courts and can TIE (no tie-break exists, by design), and
    anything at seven gives the closeness up — and it sits at/near the PEAK of that
    curve. **3S/2D**, the classic American format, is 70%/62% (G/B) and dresses only
    seven — legitimate, not adopted. Upset rate is flat across every shape (44-51%):
    shape buys CLOSENESS, not chaos.
    ‼️ **TWO measurement traps, both of which shipped a confident wrong answer once.**
    (1) That report's first run included EVEN-court shapes: at an even court count
    `margin` has even parity, so `margin <= 1` silently stops measuring "decided by
    one court" and starts measuring TIES — and an even dual also trips `winner = 0 if
    points[0] > points[1] else 1` (the `jv_outcome` trap). Compare only ODD shapes.
    (2) Its first conclusion was "doubles share is irrelevant", generalised from a
    SEVEN-court sweep spanning only 57%→14% — which is genuinely flat. The full
    five-court sweep (80%→0%, which needed 3S/2D and 4S/1D) reversed that qualitative
    claim. **Do not state a conclusion wider than the range you swept.**
  - **‼️ THE BOYS/GIRLS SPLIT IS THE FIELD, NOT THE FORMAT.** Boys' 1A is stronger
    AND more spread (top-9 mean OVR 42.09 vs 38.52, sd 4.64 vs 4.27, p90−p10 12.11
    vs 10.78 — the good programs separate; girls are flatter *by design*). So 2S/3D
    has MORE leverage in girls' 1A: mismatched duals agree 85% (girls) vs 90%
    (boys), upsets 16% vs 10%. Never read a gender gap in a future run as a format
    regression without checking the strength distribution first.
  - **‼️ A CALIBRATION SEED MUST BE A STABLE DIGEST, NEVER `hash()`** — Python salts
    str/tuple hashes per process, so a `hash()` seed moved concordance 8 points and
    upset rate 16 between ordinary runs, with nothing looking wrong. Use `blake2s`,
    the idiom this module already uses. And a calibration must call the SHIPPED
    functions, not a reimplementation — the two drift silently.
  - **‼️ AND ONE SEED PER PAIRING IS NOT A SAMPLE.** Determinism is necessary, not
    sufficient: the reproducible one-trial run still reported a gender divergence in
    the nailbiter rate (boys 81→53%, girls 63→72%) that **does not exist** — gone at
    20 trials (70→68%, 67→70%). It looked like a census because it covered every 1A
    program; it was exhaustive over PROGRAMS and a single draw over OUTCOMES. **When
    the quantity is a rate over simulated results, the sample size is the number of
    DUALS, never the number of teams.**
- **‼️ THE LEAGUE SEASON PLAYS 3S/4D, NOT 5S/2D (owner rule 2027-08, swapped).**
  `FORMATS['regular']`/`['early']` were swapped so the whole league year trains
  the postseason's doubles-forward shape, not just the early non-district
  window (which now plays the OLD 5S/2D card instead). The 3S/4D lineup
  ALLOCATION is fixed, never searched: S1 = top seed, doubles pool = exactly
  #2-#9, S2/S3 = exactly #10-#11 — a coach's `maximize`/`balanced`/`traditional`
  strategy only decides how the fixed 8-player pool pairs into D1-D4, never who
  plays singles vs. doubles. `doubles_rating` needed a real pair-synergy term
  (`engine.doubles._pair_synergy`) for the pairing choice to mean anything — the
  bare `(idx(a)+idx(b))/2` base is invariant across every partition of a fixed
  pool, so "best pairing" was previously undefined. ‼️ A COMPLEMENTARITY TERM
  MUST BE A CROSS TERM (`-(a1-a2)*(b1-b2)`-shaped), never two independent
  per-axis spreads summed — the first version used `max(sa,sb)+max(ra,rb)` and
  `|aa-ab|+|ca-cb|`, which score a lopsided pair (one player strong at
  everything, partner weak at everything) IDENTICALLY to a genuinely
  complementary pair, since neither knows which player owns which strength.
  Roster depth now scales by classification (`ROSTER_SIZE_BAND_BY_CLASS`, a BAND
  per class — 9A/8A 20-24 down to 1A 14-16, each program drawing one stable point
  in its band via `roster_size(classification, school_key, salt)`, same idiom as a
  recruiting budget band — same `ncaa.ROSTER_CAP` pattern, same talent metrics, not
  weaker filler) because 3S/4D dressing 11-of-12 left almost no bench.
  **`ROSTER_FLOOR` (**16** — the regular-season format's 11 distinct players PLUS
  `JV_MIN_SPARE` (5), raised from 12 for the JV season, owner rule 2026-08; it is
  ASSERTED as `lineup_need("regular") + JV_MIN_SPARE`, never a literal, so raising
  the smallest JV format without the floor fails loudly at import. ‼️ 15 would have
  changed NOTHING — it lifts the 12-14 rosters to 15 and leaves them, plus the 61
  girls'/42 boys' already AT 15, still one short of 11+5; it looks like a fix and
  moves zero programs. 16 takes JV participation to 100%) is a HARD floor UNDER that band, and
  there is NO CEILING: the band is a target `_freshman_class_size` draws around, real
  rosters run 12-36, and the transfer portal appends on top without a check. Both are
  deliberate — the owner reallocates talent by hand, and a big school rolling a deep
  squad is what makes moving players down the ladder worth doing. Do not clamp it.** — `_freshman_class_size` rolls each grade independently
  with real downside variance, so `build_roster` tops a short roster up to 11 by
  growing ONLY the current year's incoming freshman class (never grades 10-12,
  already fixed from a prior roll) — without it, a program that rolled thin across
  its four grades could and did drop below what a dual needs, forcing the same
  player onto two lines of one match at once. See
  `docs/AAR-jhsaa-roster-floor-and-depth-bands.md`. Grade
  distribution is no longer an even ~3-per-grade split — `_freshman_class_size`
  rolls ONCE per `(school, entry_year)`, so year 1 shows a naturally random
  class mix (four independent entry-year rolls) while every later year's growth
  comes ONLY from that year's own freshman roll; no non-freshman players are
  ever procedurally generated — a real sophomore/junior arrival is meant to be
  a TRANSFER (scaled from the college portal, not built yet), never a
  generation roll pretending to be one. See
  `docs/AAR-jhsaa-doubles-lineup-and-league-format.md`.
- **‼️ THE JV SEASON — every program fields one, concurrently (owner rule 2026-08,
  `jhsaa.play_jv_season`).** Measured on the real 2038 save, **40.8% of girls' and
  42.3% of boys' players finished a season on ≤5 matches** and 18-19% of SENIORS
  reached the college hand-off that way — ~750 a gender arriving on the recruit board
  at 0-0, because the league format dresses eleven of a median-19 roster. JV is where
  ranks #12-down play. Design + measurements: `docs/BRIEF-jhsaa-jv-and-varsity-2-
  feasibility.md`; lessons: `docs/AAR-jhsaa-jv-season.md`.
  - **ONE roster, ONE ladder, no JV squad.** `jv_pool(ts)` is literally
    `_order(ts)[lineup_need("regular"):]` — a SLICE of the one ladder, not a standing
    team, so it is porous for free (a varsity player who lost through the season has
    fallen past a JV player's seed and they swap, which the ladder already did).
    Nothing was added to make it porous; do not add anything.
  - **‼️ THE POROUSNESS IS NOT TEMPORAL — do not describe JV as a "daily slice".**
    `run_season` plays the ENTIRE varsity regular season, then the entire JV season, so
    `ts.records` is complete before the first JV dual and `play_jv_dual` credits nothing
    back: every JV dual of the year resolves `jv_pool` to the SAME ordering. The swap
    happens once, ahead of the JV season, not date by date within it — a JV dual dated
    12 April is staffed off the June ladder. This was written up as a daily re-cut and
    it never was one; a reviewer caught it. **Measured before re-deriving it:** reading
    the ladder 10% into the season instead of at the end moves **4.1% of the JV pool**
    (13 of 408 players, 42 programs), median rank change over a season **0 places**
    (mean 0.5, max 4) — small only because `ladder_score` is deliberately sticky
    (±`LADDER_SWING` 7 OVR, damped by evidence). ‼️ **The error scales with
    `LADDER_SWING`**: raise it and the shortcut bites, at which point the fix is to
    interleave `play_jv_season` with `play_regular_season`'s block seams (early → pass
    1 → mid-season → pass 2 → tune-up) rather than calling it once at the end.
  - **‼️ THE ELASTIC FORMAT IS THE WHOLE FEATURE, and the reason is arithmetic.** A
    FIXED JV format must be fielded by BOTH schools, so its reach is the PRODUCT of two
    roster constraints — measured as a share of real league dates where both sides could
    dress: 3S/4D **7-9%**, 2S/3D 32-36%, 2S/2D 61-64%, 1S/2D 78-79%. `jv_format(spare)`
    takes the THINNER side's spare, so there is no product and the condition collapses
    to "both sides have 5 spare" — 100% of programs with the floor at 16. Do NOT
    "improve" the table to a nicer fixed shape.
  - **‼️ THE TABLE IS ONE RULE, UNCAPPED**: `D = (spare + 1) // 3`, `S = spare - 2D`.
    `JV_FORMATS`' eight authored literals (5→1S/2D … 12→4S/4D) stay as the record of
    what was decided and an **import-time assertion pins the rule to them**, so the two
    cannot drift; past 12 it continues 14→4S/5D, 15→5S/5D, 17→5S/6D. No ceiling, and
    none is needed — the shape is always the SMALLER side's capacity, and only 2.0%
    girls'/3.3% boys' of real pairings exceed 4S/4D at all. **A table a rule reproduces
    is a rule with a cache in front of it** — check for that before extending an
    authored table by hand.
  - **‼️ `jv_outcome` NEVER READS `res.winner` — it is WRONG for any even-court dual.**
    `engine.dual` computes `winner = 0 if points[0] > points[1] else 1`, so a **level
    dual reports an AWAY win**. Every VARSITY format here has an odd court count and can
    never draw, which is exactly why that has always been safe and why it would have
    been silent: three of the eight JV shapes are even and 2S/2D is among the commonest.
    JV therefore has the association's first **ties** — points, then sets, then games,
    then a draw (~0.24% of JV duals; 21% of even-court duals are level on points).
  - **‼️ `world.jh_match_key` GAINED `level` AND FOUR CONSUMERS READ IT POSITIONALLY.**
    Without it a varsity and a JV dual between the same two programs in the same phase
    hash to ONE key, `_jh_global_order` takes a self-edge and the whole gender's
    topological sort falls into its cycle fallback — nothing raises, every card just
    stops reading in play order. The key went 4-tuple → 5-tuple and **three of the four
    positional readers fail SILENTLY** (the stage sort, the monotonic pass,
    `_jh_showcase_days`). **A positional read of a shared key is a latent dependency on
    that key's arity** — grep every index of it before changing its shape.
  - **‼️ JV MUST NEVER ENTER THE VARSITY DATE ALLOCATOR.** `jhsaa_match_dates` advances
    a per-school cursor on every distinct key, so a JV dual sharing a school pushes the
    varsity one to a later round and the two seasons SERIALISE — the calendar overruns
    its window, `_jh_pattern` degrades to a six-day week, and every individual card
    still reads correctly because only the SPAN is wrong (exactly how
    `AAR-jhsaa-postseason-calendar-lanes.md` hid). JV is dated by its own
    `world._jh_jv_dates`, may use **Sundays** (varsity never does), and opens a month
    late (girls April, boys September) — which also steps past the early window where
    `lineup_need` is nine rather than eleven.
  - **‼️ THE ARCHIVE PERSISTS THE FULL BOX SCORE** (`world_jhsaa_dual` gains
    `level`/`tied`/`shape`/`played`; JV rows carry per-court `lines` exactly as varsity
    does). **23.4 MB a season, MEASURED**, against varsity's 40.0 — owner rule 2026-08:
    *"the jv box score is worth the small annual MB add it's trivial."* ‼️ **A cost
    figure that DECIDED something has to be re-measured when the thing it measured
    changes shape** — this was quoted at 15.3 before the uncapped table took
    courts/dual from 4.8 to 5.22, and the owner decided against it on the low number.
  - **‼️ `level` IS NOW THE ONLY THING KEEPING JV OUT OF A VARSITY RECORD.** It used to
    be structural — JV rows had no `lines`, and every varsity reader iterates `lines`.
    That is gone. **Six readers, and the filter lives INSIDE each one, never at the call
    site** (`_jh_line_records` has three callers, `_season_row` two; a filter per caller
    is a chance to forget, and next year's caller cannot know): `state._jh_line_records`
    · `state._jh_slot_records` · `world._season_row` (courts won/lost) ·
    `world.jhsaa_underplayed` (SQL). `jhsaa.rating_duals`/`_weighted_lines` need none —
    they take `TeamSeason` and JV teams are `JVTeam`, which is that separation earning
    its keep. ‼️ **`world.jhsaa_history_rows` is the trap**: it re-reads the dual table
    in BULK for the research export and hand-builds its row dicts, so it does not share
    `_schedule_rows` — it dropped `level`, every row read as varsity, and JV courts
    joined each program's exported court totals. **A filter is only as good as the field
    reaching it.**
  - **`played` stays beside `lines`** — the names that dressed, folded by
    `world.jhsaa_jv_player_record` into the **JV column on the career ledger**. Derivable
    from `lines` now, and kept because that column should not parse court detail it does
    not show. ‼️ A JV record is the TEAM's result in the duals a player dressed for, so
    never render it as though it were a per-court W-L beside the varsity
    singles/doubles figures. A season archived before `played` folds to (0,0,0) and
    shows nothing, which is honest.
  - **‼️ THE ANALYTICS SIDECAR IS VARSITY-ONLY, BY DECISION** (owner 2026-08: *"it can
    ignore JV generally i do not need JV analytics"*). `research_export.build_jhsaa`
    iterates `season["teams"]` and never `season["jv"]`, so no JV dual has ever reached
    a zip. If that is revisited, `duals.csv` needs a `level` column FIRST: `analytics/
    ptc_analytics/aggregate.py` DERIVES each phase's dual shape by counting the lines it
    sees, and JV duals are `phase="regular"` with an elastic shape — dropped in
    unlabelled they would corrupt the derived shape of the varsity regular season rather
    than adding a JV section.
  - **‼️ AND WHEN THE JHSAA NEEDS SOMETHING, CHECK WHAT THE COLLEGE SIDE ALREADY HAS.**
    Full per-court JV detail was argued against partly on "the JHSAA flight box is
    fixed at S1-S5/D1-D4 and elastic JV needs dynamic columns" — which was WRONG:
    `state.player_career_records` has flexed since divisions stopped sharing a lineup
    size (`n_s = max([f.n_singles] + [...])`, *"widened to any line they actually
    played … career history can span formats"*), the exact problem. `_jh_flight_box`'s
    own docstring says it mirrors that helper and it is a DEGRADED COPY that hardcodes
    the ranges. Owner: *"the college game has everything i'm asking for (save for JV)
    and works perfectly fine, which is why it's all in the same repo."* Widen the
    shared helper; do not describe a solved problem as a design obstacle because you
    only read the copy.
  - **`JVTeam` is a SEPARATE type** with no `records` and no `matches` — a JV result
    cannot reach a varsity counter, an award résumé or TOSS by construction. JV is
    excluded from TOSS, seeding, awards, development and the recruit hand-off entirely.
  - **Schedule**: district single round robin → invitationals to `JV_DUAL_CAP` (16) →
    one **JV Showcase Weekend** (`showcase_pod`), OUTSIDE the cap. ‼️ It needed its own
    PHASE — at `phase="regular"` it was indistinguishable from an invitational in the
    archive and the cap arithmetic could not even be checked. The section's own rule: **a
    phase is the archive's identity for an EVENT.**
  - **Pairing is a talent SORT and a WALK** — pair each team with the next one still
    free, one rule surviving (no league-mate). It was a windowed scorer first; owner:
    *"it's literally whoever has someone, the precision isn't crucial."* Same lesson
    `_showcase_groups` already learned — **when the quality of a matchup comes from the
    ORDERING, searching inside the ordering buys nothing.** Deliberately the INVERSE of
    varsity's geography-first `_nondistrict_pairs` (median gap 0.0 OVR vs 4.2-5.2):
    travel is not a real cost in a simulation and a JV player facing their own level is
    the entire point. Classification is deliberately NOT a gate.
  - **NO PLAYOFFS** (asked directly, 2026-08): a bracket needs a ranking to seed it and
    JV has none by design; a JV team is a ladder slice rather than a standing squad, so
    the squad that qualified need not be the squad that plays; and the elastic format means a semifinal and a final could be
    different shapes. More showcase weekends are the shape that works.
  - Cost: the week-0 rung goes **~5 → ~7 minutes** for both genders (+40%).
    `tests/test_jhsaa_jv.py`.
- **Team honours exist beyond titles (same rule):** every unit won is an honour in
  ROMAN numerals ("Region IX", "Ward IV"; Zonals keep letters), all on ONE line —
  led by the DISTRICT TITLE when the program won its district (owner rule 2027-08:
  it sits with the zone/ward/section chips, chip text = the district name) — and
  reaching State is its own line — gold title / silver finalist / bronze semifinalist /
  **blue** every other State finish. `honoured` = honors | champion | toc_champion |
  unit_wins | made_state.
- **The state draw is SEEDED, with byes to the top seeds, and then FIXED.** `run_state`
  places entrants via `engine.tournament.seeded_draw` (the college championship's
  helper), so a 12-team field is a 16 draw where **seeds 1-4 sit out and 5-12 play into
  an eight-team quarterfinal**, and a 24-team field is a 32 draw where the top eight sit
  out. **No reseeding between rounds** (owner rule 2027-08 — most states don't). It used
  to pad the field with `None` at the END, which meant the byes paired off with each
  other and went to nobody, and slot order was finishing order — so **round one paired
  seed 1 against seed 2** at every field size. Don't reintroduce positional padding.
- **A state finish is TEAMS STILL ALIVE, counted down — never `2**n`.** A field that
  isn't a power of two doesn't halve out of the gate: a 24-team draw plays
  **24 → 16 → 8 → 4 → 2** (eight byes), and saves archived BEFORE the seeding fix hold
  odder shapes still (24 → 12 → 6 → 3 → 2, with a three-team semifinal round), which
  must keep rendering. `jhsaa_state_rounds` counts `alive(n+1) = alive(n) - games(n)`
  (every game eliminates exactly one); `state_place` is 1 champion / 2 runner-up / 3-4
  semifinalist, so "made the semis" is `place <= 4`, a NUMBER, never a string compared
  to a label. The champion is read off the archived bracket, not inferred from "won its
  last game" — a bye lets a program miss a round without being out.
- **‼️ LEAGUE IDENTITY IS ITS OWN DATASET, NOT THE MAP (owner rule 2027-08).**
  Every league used to be named `<Jefferson area> District`, so the league names
  and the administrative areas were one ontology — "the repetition is happening
  because right now they sound like the same ontology". `import_jhsaa.LEAGUE_NAMES`
  is now a separate bank (~100 names: landform, watershed, historical, coined
  compound, evocative geography, institutional, metropolitan, paired environment,
  directional) with varied suffixes — League · Interscholastic League · Athletic
  Association · Assembly · Province · Organization · the plain legacy District.
  **`affinity` is a SOFT tug toward a region, never a rule**: a name need not
  describe its current members, because real league names persist through
  realignment and the drift is the realism.
  - **‼️ NEVER Conference, Division, Region, Ward, Zone, Section or Area** — every
    one is a PLAYOFF unit here (`_STAGE_NAMES`, `_RECOVERY_UNITS`,
    `renumber_divisions`, `reletter_conferences`), and a league sharing a word
    with a bracket round is the same ambiguity one level up.
  - **‼️ BOYS AND GIRLS ALWAYS SHARE A LEAGUE.** A league belongs to the SCHOOL,
    so the map is drawn ONCE per classification over every sponsor and both
    gender fields read it. It used to be drawn per gender — a school could be
    Chinook League for girls and Quarry League for boys, invisible for as long as
    both draws produced "<area> District" from the same map. Blocks balance on
    the girls-inclusive pool (girls sponsorship is the superset), so a league's
    boys half is the ~88% that fields a boys team; 11 girls' teams and 9 boys' in
    one league is correct, not an imbalance.
  - Names must be **distinct to a READER, not merely unequal**: a candidate
    sharing its LEADING WORD with a league already drawn in that class is
    rejected. "Halbrook Basin" (area) beside "Halbrook" (county inside it)
    shipped, and read as one league. Never a numbered fallback.
  See `docs/AAR-jhsaa-league-identity.md`.
- **‼️ A DISTRICT IS `(CLASSIFICATION, name)`, never the name alone.** The JHSAA reuses
  its geographic district names at every level — "Halbrook Basin District" is FIVE
  leagues — which is why the archive is keyed `standings[group][district]`. A route or
  lookup keyed on the name alone silently serves the 3A-1A league under a 7A heading,
  with all the right data and all the wrong league. Route: `/jhsaa/district/<group>/<district>`.
- **‼️ `m.score` on a shared bracket card is WINNER-FIRST, never home-first.**
  `_bracket.html`'s `brk_row` splits the string and picks its half by which side WON, so
  a `f"{home_points}-{away_points}"` string swaps the two numbers on every card the AWAY
  team won — and is correct on every card the home team won, which is what hid it through
  a design pass, a review and a merge (the wrong half reads as upsets). Build it
  `max-min`. Same family, and worse: **a tennis SET score is ALWAYS written from the
  WINNER's side** — a domain convention, not a perspective, so both teams' cards show the
  identical string and only the names and the d./l. marker differ. The engine already has
  this (`MatchResult.scoreline`, "from the winner's perspective"; the college league
  stores it and un-flips with `home_won`), but `jhsaa._score_str` reimplemented it
  HOME-first. Normalise at the render — `state._jh_reported_lines`, keyed on `home_won`,
  and it COPIES (`play_dual` appends the SAME `lines` list to both teams). Flipping "for
  the away card" is NOT the fix; that just moves the error onto the home card. The stored
  JHSAA string stays home-first because seasons are already archived that way and
  `jhsaa._games` wants the directional split for oGS.
  See `docs/AAR-jhsaa-bracket-score-sides.md`.
- **The state draw uses the SHARED bracket tree** (`state._bracket_canvas` +
  `templates/_bracket.html`), like the NCAA bracket and the Preseason NIT — the macros
  take `ep`/`epq` for the link endpoint and honour a team's own `mark`. Don't fork a
  fourth bracket; small screens get round TABS (`jh_round_tabs`), a second presentation
  of the same rounds. **`_bracket_canvas` connects columns POSITIONALLY** (equal width →
  one feeder each, otherwise the `2k`/`2k+1` halving), so raw JHSAA round sizes
  (12→6→3→1→1) are an invalid input: at 3→1 it draws nothing for the third winner, who
  byed into the final. `_jh_bracket_cols` materialises each bye as an explicit
  pass-through card (`_jh_bye_card`), making it 3→2→1 — a shape the halving rule already
  draws right. Feed the helper the real shape; don't teach it special cases.
  - **‼️ `brk_canvas` takes a `_bracket_canvas` RESULT, never the column list that goes
    INTO it.** It dereferences `cv.width` / `cv.columns` / `cv.cards` / `cv.links`, and
    Jinja resolves a missing attribute on a list to Undefined and prints nothing — so the
    TOC page shipped as a toolbar and a champion above a zero-size empty box, with no
    error, no log line and correct columns sitting one function call away. A template is
    the one place here where the wrong TYPE renders a page instead of raising: anything a
    template dereferences by attribute must be checked by RENDERING it. Same family:
    `jh_round_tabs(rounds, u, gender, id='jhrd', pin=none)` — the fourth positional is the
    DOM id, and passing `scope.pin` there silently un-keys the round list from its script.
- **‼️ THE INDIVIDUAL STATE TOURNAMENTS — six flighted draws, PRESEASON, fully credited
  (owner rule 2026-08, `app/jhsaa_individuals.py`).** No. 1-3 singles and No. 1-3
  doubles, each crowning its own individual state champion, per classification per
  gender, plus a separate **mixed doubles** event. The high-school port of
  `app/individuals.py` and deliberately the same shape. Lessons:
  `docs/AAR-jhsaa-individual-state-tournaments.md`; design:
  `docs/DESIGN-jhsaa-individual-tournament.md`.
  - **‼️ IT IS 3 SINGLES + 3 DOUBLES IN EVERY CLASSIFICATION, 1A INCLUDED, AND IT READS
    NO DUAL FORMAT** (owner: *"so the 1/4, 2/3, 3/4 discussion is irrelevant"*, *"even
    in 1A, it's still a 3/3 event"*). The 1S/4D postseason, the 3S/4D league season and
    1A's 2S/3D pilot are all irrelevant here; no branch in the module reads a group's
    shape. Do not "fix" 1A to six flights of eight.
  - **‼️ ENTRIES COME OFF THE ABILITY LADDER, NOT THE LEAGUE LINEUP.** The 3S/4D league
    format is doubles-forward — S1 = #1, the doubles pool = #2-#9, **S2/S3 = #10-#11** —
    so a program's "No. 2 singles" in a league dual is its TENTH-best player. Entries are
    `S1=#1 S2=#2 S3=#3 D1=#4+#5 D2=#6+#7 D3=#8+#9` off `_order`.
  - **PRESEASON is what makes ability-selection honest** and it is why the event is an
    INPUT: run before a league dual there are no results to earn a berth on, and
    `credit_draw` writes into the same `records` `ladder_score` reads, so a deep run
    moves a player up the ladder before the season starts.
  - **OPEN FIELD, NO DISTRICT QUOTA** (owner: talent is not evenly distributed
    geographically — "a strong league's third-best beats a weak league's champion").
    82-107 entries into a flat **128**, byes to the top seeds, the NJSIAA model. ‼️ An
    open field is CHEAPER than qualifying, not dearer: a single-elimination draw plays
    `entries − 1` matches whatever its shape, so qualifying rounds ADD matches (10,569
    open vs 12,204 with a quota).
  - **‼️ SEEDS ARE THE ENGINE'S EXISTING RULE AND ARE PUBLISHED IN TIERS.**
    `seed_count` is already a quarter of the draw and `seeded_draw` already places
    [1], [2], [3-4], [5-8], [9-16] onto mirror anchors — which is exactly how a real
    association releases them ("SEEDS 5-8 (Alphabetical)"), because a No. 6 seed is not
    ranked under No. 5, it is a member of that tier. Never print a flat 1..32 list.
  - **‼️ SCORED WITH `individuals.INDIV_FMT`, IMPORTED — never re-declared.** Best-of-3,
    no-ad, **10-point match tiebreak** deciding set: the college individual
    championships' own format. A draft added a `best_of_3_ad` preset to justify a
    "championships are played with ads" exception; the owner asked whether the college
    event already did 2-of-3 with a 10-point breaker, and it did. **Look the constant up
    before writing an exception to a rule.** This is the one place JHSAA scoring differs
    from `MATCH_FORMAT` (whose third set is full).
  - **‼️ FULL CREDIT, AND IT NEEDED NO NEW CODE** (owner: *"treat them like the regular
    season + playoffs, easiest idea no fuss"*). Three earlier decisions carry it: the
    flights are named **S1-S3/D1-D3, the same slots a dual uses**, so `FLIGHT_WEIGHTS`
    already prices them; the phase is deliberately **outside `POSTSEASON`**, so
    `jhsaa_awards._phase_weight` gives 1.0; and a pair credits BOTH members with
    `partner` set, which is what `_pairs` keys a partnership on. It is still its OWN
    phase (`"individual"`) — a phase is the archive's identity for an event.
  - **‼️ AND THE OWN-PHASE DECISION IS LOAD-BEARING FOR A REASON NOBODY PLANNED.**
    `jhsaa_awards.FLIGHT_S2S3_REGULAR` deflates S2/S3 to roughly **D4's weight**, but
    ONLY when `phase == "regular"` — because the league's 3S/4D format seats ranks
    #10-#11 there. This event's S2/S3 are the program's genuine #2/#3. Archived as
    `phase="regular"` (the obvious way to get "ordinary weight, no fuss"), **every
    individual No. 2 singles champion in Jefferson would have been scored as a
    tenth-best player** — silently, with normal-looking résumés. Reusing a phase to
    inherit its behaviour inherits ALL of it, including corrections written for that
    phase's particular lineup shape. Pinned by
    `test_individual_s2_s3_escape_the_LEAGUE_s2_s3_deflation`.
  - **‼️ `state._finish_short` IS WRONG FOR A 128 DRAW and says so in its own docstring**
    ("every field converges on the same 24-team main draw… so a team still alive above 24
    went out in the QUALIFIERS"). True for the TEAM event; here it renders R128, R64 AND
    R32 all as QUAL. The individual event has its own `FINISH_BANDS`; the team path is
    untouched. A function documenting itself as needing no parameter is stating an
    assumption — adding the parameter is the wrong repair.
  - **‼️ MIXED DOUBLES CANNOT LIVE IN `run_season`.** That takes ONE gender and a mixed
    pair is one player from each, so it runs at the WORLD rung after both
    (`run_mixed_season`) — where `renumber_divisions`/`reletter_conferences` run, and
    where it belongs on the calendar (the owner put it in the **summer**). One flight,
    one bracket, **one entry per school**, drawn from **below #9** (a consolation event
    for the players the six flights have no seat for; `ROSTER_FLOOR` 16 − 9 leaves ≥7,
    median 8). It is archived under gender **`'mixed'`** — it belongs to neither field —
    and **credits NOTHING to anybody** (owner rule), which is what lets it run outside
    any season at all.
  - **‼️ THE ARCHIVE IS ITS OWN TABLE (`world_jhsaa_individual`), one row per draw**, and
    two size mistakes got it there. (1) Matches stored full COPIES of their entrants on
    both sides, repeating each up to eight times over — **3.5 MB** a gender; they now
    store INDICES into `entries`, the way the engine's own `TourneyMatch` does (**1.7
    MB**). (2) 1.7 MB is still far too much for the `world_jhsaa` summary blob, which
    every JHSAA page reads IN FULL — the hub's champion list would deserialise every
    bracket in the association. Same reason the duals table exists. ‼️ And NOT a row in
    `world_jhsaa_dual`: that row is a dual between two SCHOOLS with pf/pa and `lines`,
    and six readers fold it into records and court totals — an individual match dropped
    in there lands on programs' records exactly as JV duals did before `level`.
  - **‼️ `_draw_seed` USES `blake2s`, NEVER `hash()`** — Python salts str hashes per
    process and these draws are ARCHIVED, so "the same season" must survive a restart.
    `run_season`'s own `hash(group) % 9973` is an older wart of the same shape: it is
    left alone (fixing it would change every archived season) and must not be copied.
  - **UI: the Championship sub-rail, labelled "Individual State"** (owner, 2026-08),
    with the flights switched INSIDE that view as a second sub-rail — never six items on
    the Championship rail, never one page with every draw splayed down it. The draw uses
    the SHARED tree (`_bracket_canvas` + `templates/_bracket.html`), which grew two
    optional attributes rather than a fourth bracket: **`t.name`** (the card shows a
    person, not a school) and **`t.pid`** (the link is `/jhsaa/player/<school>/<pid>`,
    whose pid varies card by card and so cannot ride in the canvas-constant `epq`). The
    pid is passed as DATA and the URL built in the template — `state.py` is a view-model
    layer with no request context. ‼️ The mobile `jh_round_tabs` fallback is deliberately
    NOT wired: `jh_mgame` renders a DUAL (two schools, a points score, a district) and
    would show empty rows for an individual card while raising nothing.
- **‼️ THE TOURNAMENT OF CHAMPIONS IS ITS OWN EVENT, with its own PHASE** (`jhsaa.
  POSTSEASON = ("state", "toc")`). It borrows the state event's 1S/4D shape and its strict
  best-nine lineup, but `run_toc` plays `phase="toc"`, because the phase is the ONLY thing
  that tells the two apart once they are rows in `world_jhsaa_dual`: written as `"state"`
  its duals landed on a program's state-tournament record and "did they reach the TOC?"
  had no answer to read. A phase is the archive's identity for an event, not a format
  selector. Both are excluded from TOSS (`rating_duals`). `world.jhsaa_toc_result` reuses
  the state draw's arithmetic with its OWN labels — `_finish_label` bands 5-8 as
  "Quarterfinalist" and a six-team meta-event has no quarterfinal. The finish rides on the
  ledger row, the totals, the honours panel and a GOLD `jh-tag toc` on the schedule (never
  the state event's green — the TOC is the rung above it).
- **‼️ AWARDS ARE RÉSUMÉ SELECTIONS, on their own page (owner SOP 2027-08,
  `app/jhsaa_awards.py`, `/jhsaa/honors`).** Never an ability leaderboard: selections
  come off the per-match log (`TeamSeason.matches` — opponent pids, flight, phase),
  scored on record, FLIGHT played (`FLIGHT_WEIGHTS`), opponent quality (two-pass),
  quality wins, cheap "good losses", head-to-head among near-ties, and postseason
  weight. Nothing reads OVR/talent/class year/last year. Per classification: State
  POY, All-State First/Second/Third (+**Fourth in 7A**) each **10 singles + 8
  doubles — the same size as an All-District team**, then Honorable Mention, plus a
  District POY and one All-District team per district. **HM is a THRESHOLD, not a
  team**: no slot count, size varies by how
  deep the class actually was (measured boys 7A 30 vs 5A 7), and **max 2 per school
  — a cap that applies to HM ALONE**; the numbered teams stack a school as high as
  its résumés earn (4 seen). If every class shows the same HM count, a slot count
  has crept back in — pinned by `tests/test_jhsaa_awards.py`.
  - **‼️ REGIONS ARE NOT THE SAME SIZE, so the honour scales with them** (owner rule
    2027-08). Halbrook Basin has 199 boys'/219 girls' programs; Millersylvania has 25.
    A region of **`AR_TIER2_MIN_PROGRAMS` (45)+** crowns a **First AND Second
    Team**; below that, ONE unnumbered team (calling it "First" with no second
    promises a tier that does not exist). Halbrook alone clears
    **`AR_HM_MIN_PROGRAMS` (100)** and adds an **Honorable Mention** — All-State's
    threshold logic exactly (no slot count, same criteria and flight weighting)
    but capped at **ONE entry per school** (`AR_HM_PER_SCHOOL`), an entry being a
    singles player OR a pairing. **Thresholds are on the PROGRAM COUNT, never a
    list of region names** — the owner named four regions and the counts said five
    (Sebastian Cape, 49, is bigger than Ashbury Metro, 45). `all_region[region]` is
    `{tiers, honorable_mention, programs}` and **`jhsaa_awards.region_rows()` is
    the ONE place that knows that shape** — a reader that walks the dict itself
    will silently show a big region's First Team only.
  - **‼️ `used` CARRIES ACROSS THE TIERS OF A LEVEL** (`_pick_team`). Ranked slices
    keep tiers disjoint by INDEX, but a player with two strong partnerships sits at
    two indices, so a per-team `used` put the same athlete on the First Team with
    one partner and the Second with another. Owner: "that should not happen." The
    All-State tier loop had the identical shape and the same latent bug.
  - **‼️ AN ATHLETE'S CATEGORY IS THEIR BETTER DISCIPLINE, NOT THEIR MORE FREQUENT
    ONE** (owner rule 2027-08: "kids can't play singles and doubles in the same
    match so just take their better thing and give them that"). `_assign_primary`
    compares STANDING — percentile in the gender-wide singles field vs percentile
    of their strongest partnership in the gender-wide pairs field — because a
    singles résumé and a partnership's are different currencies and cannot be
    compared raw. Ties to singles. ⚠️ `_pairs` therefore builds EVERY partnership
    and the cross-category ones are dropped after; gating pairs on the primary is
    circular, since the primary is derived from the pair ratings.
  - **‼️ ALL-REGION IS REGION-WIDE AND CLASS-BLIND** (owner rule 2027-08). There is
    no 7A All-Region team — there is a **Gold Valley All-Region team**, drawn from
    every program in Gold Valley whatever its enrollment, exactly as in real life.
    It is therefore selected ONCE PER GENDER (`jhsaa_awards.region_awards`, off the
    gender-wide `build_pool`), archived at the SEASON level beside `all_district`
    (NOT in `awards[group]`), and every reader merges it in — `honors_for` takes it
    via `{**aw, "all_region": arc["all_region"]}`. Per classification it was a
    DISTRICT BY ANOTHER NAME: a class-region holds 4-5 schools, so ten regions × six
    classes × 18 selections honoured ~1,080 players out of ~300 programs and every
    school placed somebody. Region-wide: 180 selections, 47% of schools placing vs
    All-District's 83%, teams mixing 4-5 classifications. **Class → district IS a
    hierarchy (a district is `(classification, name)`); class → region is NOT** — the
    honors page's Region tab deliberately ignores the classification dropdown and
    says so on screen. Do not "tidy" All-Region back inside a class's slate.
  - **Ratings are computed GENDER-WIDE, once** (`build_pool`), then each class's
    slate is selected from it. Non-district play crosses classifications, so rating a
    class alone cut those edges out of the opponent graph and defaulted every
    cross-class opponent to 0.5 — the same reason TOSS is computed over the whole
    gender.
  - **‼️ DOUBLES HONOURS GO TO PAIRINGS, NOT TO INDIVIDUAL DOUBLES PLAYERS** (owner
    correction 2027-08). "8 doubles" is eight doubles TEAMS — sixteen athletes. The
    candidate entity is the PARTNERSHIP (`_pairs`, keyed on the sorted pids), its
    résumé is only the matches those two played TOGETHER, and it is rated against
    the OPPOSING PAIR (`_q_pairs`/`_h2h_pairs`), never against individuals. Partners
    rotate in this format, so one player is several candidates (`MIN_PAIR_MATCHES`
    6 separates a partnership from two people put together once). **Which category
    an athlete is considered in is decided by ACTUAL PARTICIPATION**
    (`_primary_discipline`, ties to singles) — not by whichever résumé scores
    higher — which is also what makes "no athlete in both halves of one team" true
    by construction; `_take`'s `used` set catches the rest. ‼️ **Every "was this
    person honoured?" test goes through `jhsaa_awards.row_pids`** — matching on
    `row["pid"]` credits HALF of every pairing and looks perfectly fine on the
    surface it is on. A team may be short a pairing where the pool cannot supply
    eight disjoint ones (thin regions); **do not backfill**.
  - **‼️ FLIGHT WEIGHTING IS STRUCTURAL, NOT A SMALL BONUS** (same correction). Two
    mechanisms, both load-bearing: `FLIGHT_ALPHA` (1.00/0.90/0.70) sets how far
    apart the flights sit, `FLIGHT_FLOOR` sets how far down the card a level reaches
    at all — **State is a #1/#2 honour**, Region reaches #3, District has no floor.
    Below the floor a player needs `_extraordinary`: a near-perfect record AND a win
    over somebody who played at or above the floor, **checked against the match log,
    not by re-scoring** (re-scoring only re-asks what the weights already answered).
    Do NOT soften the alpha to open a lower level up — that was the old shape and it
    opens the state list at the same time. The **flight sanity check**
    (`_flight_report`) is archived per season (`awards[g]["flight_check"]`) and
    rendered on the page: counts by flight plus every below-band pick by name,
    flight and record. It is an artefact of a DECISION — never recompute it on read.
  - **‼️ AWARDS ARE SELECTED AFTER THE LAST DUAL**, beside the record snapshot in
    `run_season`. They used to be selected inside the qualification loop, i.e.
    BEFORE Sectionals: `PHASE_WEIGHT` weighted a postseason nobody had played, and —
    silently — the 1S/4D postseason moves most of a roster into doubles, so the
    participation split the category rule reads was taken with a third of the season
    missing. Same fault, same function, as the record-snapshot bug above; that one
    had arithmetic that failed, this one had none.
  - **The page is four VIEWS of one slate, not one scroll** — All-State /
    All-Region / All-District / method as TABS, and the two that are themselves a
    set of teams get a `<select>` switcher (one region, one district on screen;
    the Region tab is class-blind and carries a note saying so). Each
    team announces its halves ("Singles 10" / "Doubles teams 8 pairs · 16 athletes"),
    because eight pairing rows otherwise read as eight individuals. The hub rail is
    an INDEX of the page, not a copy of it. `.jh-award` is a fixed-column CSS grid —
    **always emit the rank cell**, empty or not, or every unnumbered team shifts a
    column. Data-bearing coverage lives in `tests/test_jhsaa_toc.py`.
- **A classification's rankings have a PAGE, not a rail panel** (`/jhsaa/rankings`,
  `jhsaa_rankings_view`). `jhsaa_group_ranking` always returned every program in the
  class; the hub shows the first twelve of it beside the bracket and links to the rest.
  Same archived index, no second computation.
- **A cross-link carries `scope.pin`, never `scope.year`.** `pin` is the year ONLY while
  browsing an archived season (None on the latest), so drilling from the 2027 hub into a
  program shows 2027's roster/schedule/record/finish, while links taken on the live
  season stay clean and follow the world forward. Omit it and `jhsaa_school` silently
  falls back to the newest archived year. The season buttons in `jh_header` stay explicit
  (`year=y`) — that is how you pick a season; everything else pins. Every roster / All-State / POY / bracket name links to
  `/jhsaa/player/<school>/<pid>` — **by PID, not name**: a pid keys on (school, gender,
  entry year, seat), so it is stable across all four years and matches the award rows.
- **‼️ THE SCOPE BAR SWITCHES SCOPE, NOT PAGE (owner rule 2026-08).** Gender, class and
  season all go to the page you are **ON**, swapped for that axis — `server.
  jh_scope_url` (a Jinja global) resolves `request.endpoint` and re-emits it, carrying
  the page's own query state (a sort, a filter, a district select) so a gender switch
  does not also re-sort the table you were reading. They were hardcoded to `jhsaa_page`,
  so comparing the boys' and girls' rankings meant hub → rankings again, on every page
  for every axis. Two fallback tables, for where "stay here" has no meaning: a class
  switch on a page keyed to ONE program (`jhsaa_school`, `jhsaa_player`) goes to the
  hub, on a `jhsaa_district` to that class's league index (a league is
  `(classification, name)` — the same name in another class is a different league, and
  may not exist), and a GENDER switch on `jhsaa_player` goes to the school (a pid is a
  seat on one gender's roster). A class-BLIND page (TOC, History) is NOT a fallback and
  stays put — `jhsaa_toc_view`/`jhsaa_past_winners` take `group` for the rail alone, so
  the class you were browsing survives the visit. ⚠️ `page` and the Players directory's
  own `gender` filter are deliberately DROPPED from the carried args: kept, `gender`
  silently outranks the gender just picked in the header.
- **Sport is a DROPDOWN** (owner, 2026-08), like the season — not a two-button rail.
- **‼️ ONE "CHAMPIONSHIP" TAB, THREE VIEWS OF IT (owner, 2026-08).** State, Bracket and
  TOC each led with the same champion hero and the same draw, so three of twelve tabs
  asked one question. They are still three PAGES (an index, a full tree, a different
  event) reached as ONE destination and switched on the `jh-subrail` under the tabs —
  the section's own layout rule for parallel views. Don't promote one back to a tab.
- **‼️ THE TITLE BOARD (`/jhsaa/titles`, `world.jhsaa_title_board`) — owner rule
  2026-08.** One row per program, one column per thing there is to win: the TOC, each
  STATE finish (CHAMP · F · SF · QF · OF · R1 · QUAL — `world.JH_STATE_COLUMNS`, the
  same short set as `state._FINISH_SHORT`), each round of the ROAD (Areas · Sectionals
  · Wards · Regionals · Zonals · Super Regionals · Semi-State · Divisionals ·
  Semi-Conference · Conference), and the league title. Sortable and filterable in the
  browser; it lives on the **History** sub-rail beside the champions grid, which
  answers the same question from the other end ("who won 9A in 2035" vs "what has this
  program ever won").
  - **‼️ ROAD CELLS ARE TITLES, STATE CELLS ARE FINISHES.** A unit won is an honour
    the program keeps, so the road counts wins; the State event has exactly ONE title
    per class, so the rest of that group is how often a program got that far.
  - **‼️ ONE PASS PER SEASON, NOT ONE PER SCHOOL.** `_season_row` answers this for ONE
    program and reads the whole year's archive to do it — asking it for ~860 programs
    across every season re-reads each season ~860 times. The board walks each season's
    archive ONCE and credits whoever it names, which costs what the program-history
    page costs instead of 860 of them.
  - **It is a FOLD, not a store** — the same rule as `jhsaa_school_history`. Do NOT add
    a `world_jhsaa_titles` table: the archive already determines every number, and a
    second store is a second source of truth for a decision already recorded.
  - **‼️ STAGE NAMES COME FROM `jhsaa`'S OWN CONSTANTS** (`jhsaa_title_stages` reads
    `_STAGE_NAMES` / `_RECOVERY_NAMES`), because a unit win is bucketed by the stage's
    archived `round_names`: rename a round (`DIVISIONAL_NAME` has moved once already)
    and a typed column would silently stop counting, which looks exactly like an
    association that stopped playing that round.
  - **The class filter is the PAGE's, and it ignores the header's class rail** — the
    All-Region call, for the same reason: reclassification and play-up move a program,
    so its 4A titles and its 5A titles are one cabinet. Pinned by
    `tests/test_jhsaa_toc.py` against the program ledgers themselves, never against a
    second copy of the board's arithmetic.
- **‼️ THE PROGRAM DIRECTORY (`/jhsaa/schools`, `jhsaa_schools_view`) — owner rule
  2026-08, modelled on the OSAA's two schools pages.** There was no way to see all the
  programs: the only full list was Rankings, one class at a time and ordered on TOSS, so
  finding a program by town or league meant ctrl-F. Three groupings of ONE list
  (`JH_DIRECTORY_MODES`: county · classification & leagues · A–Z), never three pages.
  It reads `load_schools` and NOTHING else — no archive, no standings, no rating — which
  is deliberate: a directory answers "which programs are there and where", and it must
  render before a season has been played. Every row carries a lower-cased `q` haystack
  (name, town, locality, county, area, league, class) because the filter box is the
  thing replacing ctrl-F and ctrl-F could only ever match the NAME; narrow `q` back to
  the name and the page stops answering its question while looking perfectly correct.
  Pinned by `tests/test_jhsaa_routes.py` — the one JHSAA surface a route test CAN fully
  see, since it depends on no archive.
- **Layout rules the JHSAA surfaces are built on (they were each a long scroll first):**
  parallel views of ONE set of teams are **tabs**, not a stack (`_jhsaa.html::jh_tabs` —
  a district's standings / head-to-head / results); a parent page gets an **index** of
  its children, not their contents (the hub lists districts + champions, the standings
  live on the district page); sibling pages get a **`<select>` switcher** rather than a
  trip back to the index (the pattern `season_standings.html` already uses for
  conferences); and if two panels answer the same question, delete one — "District
  Champions" in the rail *was* the district index's champion column.
- **Schedule tags are THREE things, not one**: the league season (`dist`), the
  ROAD to State — Areas through Divisionals (`road`) — and the State event itself
  (`state`/`toc`). A State or TOC dual also carries its BRACKET ROUND beside the
  tag (R32/R24 · Octas · QF · SF · Final), read off the archived bracket rather
  than inferred from schedule position.
- **‼️ Schedule dates are a DISPLAY calendar, and the date belongs to the MATCH
  (`world.jhsaa_match_dates`), never to a card.** There is no clock inside a JHSAA
  season — it all runs in one rung at week 0 — so dates are derived from the persisted
  ORDER of play. They used to be derived per school from that school's POSITION in its
  own card, so the same dual showed two different days on the two schools' pages (Lake
  Esperanza's Super Regional read May 14, its opponent's read May 17): each card was
  internally plausible and only RECIPROCITY was wrong, which is why it survived. One
  date is now assigned per dual for the whole gender-season and both cards look it up
  (`world.jh_match_key` is the identity, the same from either side).
  - Matches are packed into **ROUNDS** (a round = duals with no team in common, so
    everything that can share a day does) over a topological order of the play
    sequence. Assigning day-by-day in play order instead lets the constraint chain
    through opponents — A waits on B, B on C — and a 30-dual card sprawled over three
    months. Ties in the topological sort break on ARCHIVE order, because district play
    is already generated as rounds and an alphabetical tie-break scrambles that.
  - **Boys play a fall calendar, girls a spring one** — cosmetic only; both are still
    simulated together in the same rung, with no separate clock, phase or season state.
    **‼️ THE SEASON IS FITTED TO A WINDOW, NOT RUN UNTIL IT ENDS (owner rule 2026-08).**
    `_JH_SEASON_CLOSE`: boys are DONE BY END OF OCTOBER (early Nov at the latest),
    girls by early June. The calendar used to lay four days a week and stop when the
    rounds ran out — nothing in it knew when a season is meant to be over, and the
    postseason finished in DECEMBER. `_jh_pattern` now picks the loosest day pattern
    that fits the rounds in the window: Mon/Wed/Fri/Sat, else + Tue, else + Thu.
    **Never a Sunday** by construction (6 is in no pattern). One continuous round index
    runs the whole season — the postseason no longer restarts its count after the
    regular season, which used to insert a break for nothing.
  - Classifications deliberately do NOT share stage dates — a 7A Super Regional and a
    3A one can fall on different days. The only invariant is that both sides of one
    dual show the same date.
  - **‼️ EACH CLASSIFICATION HAS ITS OWN POSTSEASON LANE (owner rule 2026-08).** The
    stage floor was GLOBAL (`floor_r = top_r + 1` over the whole gender), so 7A's
    Regionals waited on 2A-1A's Sectionals: eight classes that never meet were
    serialised into one queue and the 11-stage ladder cost ~8× what any class plays.
    **The boys' postseason ran to January and the girls' to July.** A class now waits
    only on the previous stage of its OWN class; lanes open together and advance
    independently. The REGULAR season keeps one shared calendar (invitationals and
    showcases cross classifications). ‼️ The **TOC is NOT a lane** — it fields every
    class's champion, so it takes `max` over all lanes and still waits on all of them.
    Lanes key on the classification the season was **ARCHIVED** in
    (`_jh_school_groups`), never today's school list, since reclassification and
    play-up both move a program; no archive → one lane → the old behaviour.
    ‼️ **A change to how many MONTHS a season spans is a product decision, not an
    implementation detail** — say so before committing it. This shipped unflagged and
    the owner found it themselves: the calendar is presentation, so no test covers it,
    and every individual card reads correctly because only the SPAN is wrong.
  - **‼️ A SHOWCASE WEEKEND IS ANCHORED TO ITS OWN ROUND.** `_jh_showcase_days` kept
    windows on distinct Saturdays by walking forward from the PREVIOUS window, with no
    reference to the round it was played in, so the last of seven landed a month past
    its rounds: October showcases printed between September league duals, and an
    18-day hole where they belonged. **The "skipped month" was matches moved OUT of
    it, not a gap in the schedule.** A collision now moves a week at most, within the
    block's own span. And a final pass in `jhsaa_match_dates` holds every dual on or
    after the last date either team already has, so a card cannot read backwards
    whatever dates it — nothing is reordered, only pushed to the next slot.
  See `docs/AAR-jhsaa-program-history-and-design-pass.md`,
  `docs/AAR-jhsaa-postseason-calendar-lanes.md` and `docs/AAR-jhsaa-season-window.md`.
- **The rung runs at week 0, BEFORE anything college**, marked done by the `world_jhsaa`
  rows it writes (the cups' pattern, not a flag). It must simulate the SAME season the
  recruit hand-off does — `world.jhsaa_season_year()` and seed 0, never the world index.
- **‼️ THE JV SEASON AND VARSITY SHARE `world_jhsaa_dual`, so EVERY READER OF THAT
  TABLE MUST FILTER ON `level` — the research export did not, and shipped corrupt
  zips.** `research_export._load_archived_jhsaa_season` SELECTed `level` and never
  used it, so JV duals reached `duals.csv` with nothing marking them: 2039 boys
  carried **18,096 duals against 2038's 10,709**, and under `phase="regular"` only
  62% were the varsity 3S/4D shape. That matters beyond row counts — `analytics/
  aggregate.py` derives a phase's dual shape from the most common line count, so
  the elastic `JV_FORMATS` shapes were one growth step from inverting it (in
  `showcase_pod` they already had), and any join of `line_players` → `lines` →
  `duals` merged JV appearances into varsity player and program totals while
  `jhsaa_standings.csv` stayed varsity-only. Fixed with `AND COALESCE(level,'v')
  = 'v'` — **COALESCE, because a pre-JV archive reads back NULL and those are all
  varsity** — plus a `level` column on the exported row so the guarantee is
  assertable rather than implied. ‼️ "Carries no lines" is NOT a substitute for
  the column: that is also what a varsity dual whose lines failed to record looks
  like. ‼️ AND EVERY EXPORT TEST INJECTS A SEASON (`build_jhsaa(season=...)`),
  where JV lives in `season["jv"]` and cannot reach a team's schedule — so the
  whole suite stayed green while the ARCHIVE path, the only one a real export
  uses, was broken. When a builder takes an injectable input, the injected path
  and the database path are two different code paths. See
  `docs/AAR-jv-duals-leaked-into-the-research-export.md`.
- **`talent` on `generate_prospect` is the CEILING**, current is maturity-derived, so the
  `_TALENT` bands look absurdly high next to the college ones. Don't "fix" them down.
- **‼️ SMALLER CLASSIFICATIONS ARE THINNER, NOT CAPPED (owner rule 2027-08).** Tennis is
  not a sport where the big school simply has better players — good players turn up
  everywhere, and enrollment buys DEPTH. So `_TALENT` varies the MEAN while the SPREAD
  WIDENS as the mean falls: 7A/6A are near-indistinguishable at the top, the real steps
  come below, and every classification can still produce an elite number one. Do NOT
  "tidy" it back into an even ladder with shrinking spreads — that was the old shape and
  it got the sport backwards in a way only a position-by-position measurement shows: the
  #1s were 12.4 apart and the #9s only 8.3, so the TOP fell faster than the depth, and a
  3A-1A program could never produce a 60 at all. Now: top-end gap 4.5, depth gap 8.3, and
  the #1→#9 drop RISES as schools shrink. Real high-school tennis routinely puts the
  smallest classification in a state top ten (Oregon 2026 boys: Oregon Episcopal No. 9,
  four of the top eight 5A). Pinned by `tests/test_jhsaa_talent_shape.py`.
- **‼️ PROGRAM ARCHETYPES are a SCHOOL-level modifier on top of that (owner rule 2027-08,
  `jhsaa.ARCHETYPES`).** Durable program conditions — facilities, feeder networks,
  community participation, coaching tradition, reputation — NOT current strength, and
  NEVER derived from classification or public/private (those may inform who gets seeded
  onto the list; the property belongs to the school). Stored in an EDITABLE override
  table (`overrides.set_jhsaa_archetype`, `/editor/jhsaa-archetype`), never branched on a
  school name in generation code.
  - **blue_blood** generates better and CLUSTERS (`BLUE_BLOOD_REDRAW` keeps the better of
    two draws per seat, which lifts the middle of a lineup far more than a flat mean
    shift). It shows on day one — ninth-graders in the low 30s where an ordinary
    program's are mid-20s — and it beats a development program ON BALANCE. That is what
    makes it a blue blood.
  - **development** has ORDINARY freshmen and the best seniors in the association:
    `mean` is 0, the gain is potential plus a maturity bonus that starts at ZERO for
    ninth-graders (`(grade - 9)`) and compounds. It CAN beat a blue blood outright — that
    is the point, it levels a field facilities tilt — but it earns it over four years.
    Arrive good vs leave great.
  - **doubles** generates completely normally; the edge is an EPHEMERAL per-match lift
    (+5..+11 on the 20-80 grade scale) applied to a COPY on the way into the engine —
    `build_roster` caches Prospects globally and shares them across saves. It lands only
    on `Team.doubles_players`, the separate doubles lineup `_squad` already builds, so it
    is structurally incapable of reaching a singles court. (Nothing existed to reuse:
    `coaches.development_multiplier` is a growth RATE at the rollover, a different thing.)
  - **upstart** is a TEMPORARY multi-year run (~10 live statewide, 15–30% over the
    program's OWN baseline, so an upstart 1A is a strong 1A), rolled per world from the
    salt and expiring by itself — deliberately NOT storable, since a stored tag would make
    it permanent. ⚠️ The draw runs over the WHOLE pool and skips tagged schools AT
    APPLICATION: filtering the pool made the table non-local, so tagging one school
    changed which OTHERS drew an upstart.
  A blue-blood small school SHOULD beat an average big one — that is the talent model's
  thesis, not a bug. What must survive is the class ladder INSIDE each tag.
  Pinned by `tests/test_jhsaa_archetypes.py`.
- **‼️ THE LINEUP LADDER IS SEEDED ON ABILITY AND MOVED BY RESULTS** (`jhsaa.
  ladder_score` / `_order`) — never ranked on a win COUNT. It sorted `(-wins, -pct, -ovr,
  -str)` for a release, which is a ratchet, not a ladder: a win total measures
  OPPORTUNITY, so dressing earns wins, wins earn the next start, and a player who dropped
  his opening duals — or who was tenth in week one — could never climb back past
  team-mates whose only edge was having been picked first. Ability sat third and was
  unreachable. It also ranked 5-15 above 4-0, and doubles credits BOTH partners, so a
  rotation player banked wins faster than a number one drawing the toughest opponent.
  Measured: a top-four player finished outside the nine on **55 of 400 rosters**, 21 under
  seven matches all year (the report was a 51-OVR senior on six matches beside a 28-OVR
  team-mate on twenty-seven). Now `ovr + LADDER_SWING × (pct − ½) × n/(n + LADDER_PRIOR)`
  — a perfect record is worth ±7 OVR weighted by evidence, so **a player who has not
  played sits at his SEED, not at the bottom**, and a 1-2 opening week cannot outrank a
  season. The bench ROTATION (`_ROTATE_ONE`/`_ROTATE_TWO`) is the variation the owner
  asked for and was never the bug — it must move the ninth seat around the BEST nine.
  Pinned by `tests/test_jhsaa_lineup.py`.
- **‼️ THE POSTSEASON PLAYS THE ORDER OF ABILITY (owner rule 2027-08, NFHS
  anti-stacking).** Before a program's first postseason dual the ladder is FROZEN as
  its Order of Ability (`TeamSeason.order_of_ability`) and binds all postseason —
  never re-sort it between rounds; a live re-rank mid-bracket is the violation the
  rule exists to stop. The 1S/4D card then must have S1+D1 consume ranks #1-#3 (no
  top-three player at D2-D4) and D2-D4 ordered on combined ladder rank as a BOUNDARY
  (`PAIR_SUM_TOL` 2): within it, real `doubles_rating` decides — the coach picks which
  of the top three plays singles and pairs #4-#9 for chemistry (`_arrange_state`, in
  SLOT order so `_squad`/`_slot_players` keep one indexing rule). The rank sum is not
  a sort key and `doubles_rating` is not the boundary — both halves are load-bearing.
  The REGULAR season stays league policy (live ladder + rotation, no freeze), and it
  is VARIED by design: each program has a durable lineup PHILOSOPHY
  (`_doubles_forward`, hashed off the school key) — roughly half play the classic
  singles-first card, half the owner's doubles-forward permutation (S1=#1, D1 = two
  of #2-#4, S2 the third, D2 = any two of #5-#9, rest at S3-S5 in order) via
  `_arrange_regular`, with a 0.15 per-dual flip. Do not "simplify" the league back to
  one shape. Pinned by `tests/test_jhsaa_lineup.py`; see
  `docs/AAR-jhsaa-order-of-ability.md`.
- **‼️ DEVELOPMENT IS PER-PLAYER TRAJECTORIES, ERA-GATED (owner rule 2026-08,
  `jhsaa._dev_maturity` / `jhsaa.dev_era()`).** New-era cohorts (entry ≥ the era —
  the `name_era()` idiom exactly: self-configured from the newest archive,
  persisted as `worldconfig` `jhsaa_dev_era`, memoised, cleared by
  `reset_schools()`) roll a whole four-year maturity path at entry on their OWN
  rng stream (`jhsaa-dev`): wide overlapping arrival (`DEV_READY_RATE` 0.24 of
  freshmen arrive ready to play — ordinary, distinct from the 1-in-100 PRODIGY),
  wide finish, a curve SHAPE (steady/early/late/spike so players PASS each other
  between seasons), and a `DEV_MIN_STEP` floor so every kid on a roster visibly
  improves every year. Pre-era cohorts keep the legacy `_MATURITY` lockstep bands
  byte-for-byte — that gate protects every archived season's ladders and player
  cards; do not remove it. **‼️ The bands are DELIBERATELY NOT MEAN-PRESERVING**
  (owner, a real HS coach, rejected a mean-preserving draft as too conservative:
  four playable years beat preserving the association's level) — freshmen ~0.57
  of ceiling, seniors ~0.85; don't "correct" them back to the legacy means. The
  HM runaway guard `HM_MAX_MULT` was raised 2.5→3.5 because deeper fields now
  legitimately clear the merit threshold in bigger numbers — if HM sizes ever hug
  the cap again, fix the guard, not the merit bar. Pinned by
  `tests/test_jhsaa_development.py`; see
  `docs/AAR-jhsaa-development-curves-and-rest-staffing.md`.
- **‼️ TALENT-AWARE REST STAFFING vs. truly bad teams (owner rule 2026-08,
  `jhsaa._rest_count`).** Written when injuries and fatigue were owner-declined for
  the JHSAA and there was no JV (there IS one now — see the JV § below; rest staffing
  is UNCHANGED by it and still the reason a starter sits): against a clearly weaker regular-season opponent — a
  `REST_GAP` (10 OVR top-nine-mean) strength gap ALWAYS, plus a ≤.300 record once
  the opponent has `REST_MIN_SAMPLE` duals (gap alone before that) — a coach
  rests 1-2 starters from the TOP of the ladder at `REST_RATE` 0.75; everyone
  shifts up a rung so the card still reads as the ladder. **NEVER in the
  postseason or at a showcase** (both branches sit above the check in `_lineup`
  by construction — keep it that way), and never past the bench (`spare` guard —
  resting below the card wraps one player onto two lines). A weak-LOOKING roster
  that is actually winning is never rested on. Pinned by
  `tests/test_jhsaa_rest.py`.
- **‼️ AN OFFSEASON TRANSFER IS A HISTORY, NOT A CURRENT SETTING (owner rule
  2026-08, `overrides` kind `jhsaa_transfer`).** The record is
  `{from, gender, entry, seat, moves: [{to, year}, …]}` — `from` is the ORIGIN and is
  NEVER rewritten, because the pid is a one-way hash of (origin identity, gender,
  entry year, seat) and is the only school the player can be regenerated from; a
  later move records a destination, never a new origin. It held ONE move, so a second
  one had to cancel the first — and since the career card DERIVES each season's
  school from this record, the seasons played at the forgotten school were
  re-attributed to the origin and their results read 0-0, while `world_jhsaa_dual`
  still named the right school. Nothing errored; two surfaces just disagreed. The
  college side has always written a history row per player per season
  (`_record_world_history`); this is that idea in the shape high school needs.
  - **`jhsaa.transfer_school(rec, season_year)` is the ONE authority on where a player
    is** — the outbound skip in `build_roster`, its inbound pull, and the card all ask
    it, so they cannot disagree. Records written before `moves` existed read back as a
    one-move history (**derived on READ, never migrated**).
  - **‼️ A MOVE BACK TO THE ORIGIN WOULD ROSTER THEM TWICE.** The origin's own seat
    loop generates them (it no longer skips them once they are back) AND the inbound
    pull would add them again, so the pull refuses anyone whose `from` IS this school.
    A phantom team-mate reads as a roster quirk, never as a bug.
  - Undo is per MOVE (`clear_jhsaa_transfer(pid, year)`); the rest of the career
    stands, and a record left with no moves is deleted rather than kept as a row
    saying the player transferred nowhere. Re-recording a move for a year that already
    has one EDITS it — one decision changed, not two moves.
  - The ledger is **one row per move**, each row's `from` being where they were
    BEFORE it (the previous destination), which is the only reading where a move home
    does not print as a move from itself. `tests/test_jhsaa_transfers.py`.
- **‼️ FAMILY TIES ARE OWNER-AUTHORED METADATA (owner rule 2026-08, `jhsaa.family_add`
  / `overrides` kind `jhsaa_family`).** A tie links two PIDS and never touches a name —
  required, since `world_jhsaa_dual.lines` archives NAMES and `_jh_line_records` keys
  off them, so a surname rewrite silently zeroes an archived record. **NO generator, NO
  suggestion pass, NO same-surname candidate scan — the owner rejected all three
  explicitly**; the association is made by hand on the player page (roster picker, not
  a search). One row per family, opaque id, members carry denormalised name/school/
  entry (a parent need not be enrolled). Works cross-gender, cross-school and
  cross-era by construction.
  - **‼️ A RELATION BELONGS TO THE PAIR, NOT THE HOUSEHOLD (owner rule 2026-08,
    `jhsaa.family_links`).** It was one `relation` per family, so a household begun
    as cousins made every later member a cousin of everyone — "it doesn't let you
    connect siblings if the cousin relationship was started". Each `family_add`
    records ONE `{a, b, relation}` link; a family is the connected component and
    holds siblings, their cousins and a parent at once. Families written before
    `links` existed carry only `relation` and are read back as the complete graph at
    that relation (**derived on READ, never migrated** — the section's own idiom).
    The page therefore claims a relation ONLY where one was stated and lists the rest
    as "also in this family": a sibling's cousin is not your cousin, and the old
    model said it was.
  - **‼️ AND A PERSON CAN BE TIED MORE THAN ONCE.** Two members of one family used to
    be refused outright ("already in the same family"), so a second, different fact
    about them could never be stated; and two people who each had a family were
    refused too, leaving no way to say a tie you had just decided on. The first adds
    a link, the second MERGES the households (union members + links, absorbed row
    deleted) — a pid must still resolve to exactly ONE family or `families()` returns
    whichever row it met last and half the household disappears. Only a duplicate of
    an existing link is refused. Removing a member takes their links with them.
  - **‼️ NO older/younger/twin (owner rule 2026-08).** It was derived from entry years
    — correctly, an earlier entry year is the older player — and still read backwards,
    because the derivation describes THEM while the template's sentence ("older
    sibling of Jane") describes the page's player. The relation is now a label ON the
    member it describes ("Jane Doe · sibling"), which has no perspective to invert,
    and seniority is not stated at all. PARENT keeps its direction: that asymmetry is
    the content of the tie.
  - **‼️ REMOVING A MEMBER MAY SPLIT THE FAMILY.** A family IS the connected
    component of the tie graph, so dropping a BRIDGE (A-B, B-C, C-D, remove B) leaves
    two households, not one row of three: `family_remove` re-splits, gives each
    surviving component its own row, and drops anyone left with no ties (they are not
    a household of one). And `family_links` tests for an ABSENT `links` key, never a
    falsy one — an empty list is a real new-format family with no stated ties, and
    reading it as legacy synthesised a tie nobody made, then refused the genuine one
    as a duplicate.
  - **‼️ THE DOUBLES NUDGE IS SIBLINGS ONLY** (owner rule 2026-08: "only siblings get
    the bonus NOT family connections at all"). `_family_pairs` asked whether two pids
    shared a family ID, so under the per-pair model cousins — and anyone merely
    reachable through a third member's tie — drew it. `TeamSeason.sibling_ids` is
    therefore `{pid: {sibling pids}}`, not `{pid: family_id}`, still resolved once per
    team from one `families()` read. Low stakes by construction (owner: "you only get
    the bump if you're a doubles pairing anyway") — but it is a stated fact or nothing.
  Doubles:
  `FAMILY_CHEMISTRY` (0.025, ~¼ sd of pair-rating spread) is a TIEBREAK in both
  arrangers, applied under the anti-stacking boundary; `TeamSeason.sibling_ids` is
  resolved once in `district_teams`, never per dual. ‼️ `_resolve_member` NEVER
  defaults the salt — the name draw is salted but `make_pid` is not, so the wrong salt
  resolves the same pid to a DIFFERENT PERSON and stores the stranger's name. ‼️ A
  JHSAA POST route reads gender off the FORM: `_jh_scope_args` reads `request.args`,
  which a POST does not have. See `docs/AAR-jhsaa-family-ties-and-honours-tabs.md`.
- **Team trophies and player honours are TWO TABS, and team-level text goes in
  `team_honors`** (`_season_row`): a TOC finish short of the title is a TEAM result and
  must never ride in the individual `honors` list. The active tab is the one with
  content — `jh_tabs` activates the first pane, and most programs have player honours
  but no trophy. Same AAR.
- **An empty-state route test cannot see a page.** `tests/test_jhsaa_routes.py` renders
  every JHSAA surface with nothing archived and stayed green through four faults that only
  exist once there is data. `tests/test_jhsaa_toc.py` runs a REAL season (two districts per
  classification via a `load_schools` patch, ~10s a gender), archives it through
  `run_jhsaa`, and asserts on the HTML. Add data-bearing coverage there, not another
  empty-state route.
- **`FIDELITY = "fast"`, always.** Full point-by-point put 103s on the request thread.
- **‼️ UPSETS FALL AWAY SHARPLY PAST A MARGIN-OF-ERROR GAP (owner rule 2027-08,
  `engine.fast.effective_gap`).** The fast model plays on a HINGED gap: identical below
  `gap_knee` 0.06 overall-units (~1 UTR — near-equal matches keep their 2026-rule
  volatility, 3-2 upsets stay common), accelerated ×2.8 beyond it, shared by singles
  hold/tiebreak AND the doubles fast model so a dual's curves steepen together. Fix for
  a materially weaker team ripping consecutive 5-0/4-1 postseason upsets (state 1S/4D
  underdog rate at a 0.10-0.15 gap 12.7%→4.6%, 0.15+ ≈0 and 3-2 only). Do NOT delete
  the hinge to "restore upsets" (sub-knee never changed) and do NOT raise `gap_accel`
  past 1.8 (it already saturates). Seeds/TOSS still never touch a match — TOSS rank ≠
  strength (corr ~0.76), so diagnose "upsets" on eff gaps via
  `scripts/jhsaa_upset_calibration.py` first. See
  `docs/AAR-jhsaa-upset-variance-recalibration.md`.
- **`Prospect.jhsaa` is a real dataclass field** — `prospect_to_dict` is `asdict()`, so an
  ad-hoc attribute would erase a recruit's entire high-school past the moment they sign.

## ⚠️ THE SUITE MUST NOT SHARE A DATABASE WITH THE APP (it isn't about the save)
`app.dbpath.resolve_db_path()` returns `$TENNIS_DB_PATH` or the repo's `./tennis.db`, and
**`world.WORLD_DB` resolves to the SAME file** (one database, separate tables). The
`played_season` fixture calls `world.reset()` (`DELETE FROM world`) and then plays a
season into that file. So the suite READ AND WROTE whatever `./tennis.db` happened to
contain, and its results depended on local state rather than on the code.
> ⚠️ Do NOT write this up as save protection. **The owner never keeps a `tennis.db`** —
> they rebuild the sim from scratch on every reload, so a wiped world costs them nothing
> and is not a reason to do anything. The reason is HERMETICITY: a test that reads a file
> the app also writes passes or fails on leftovers.
The root `conftest.py` now points `TENNIS_DB_PATH` at a throwaway temp file BEFORE any
`app` import. That guard is load-bearing — without it a test result is a statement about
the developer's disk.
- **This is what broke the awards test.** A world reset with the played SEASON rows left
  behind means the season's ~4,600 pids name people `build_roster` no longer produces.
  `awards._eligible` `continue`d past every one, returned `[]`, and every All-American
  tier came back empty on a fully played season — no error, no log, a clean and
  completely wrong "nobody was honored". Diagnosed by measuring the two pid sets (4,596
  each, **zero** overlap), not by reading the selector, which was correct. `_eligible`
  now logs loudly when nothing resolves, because an empty honors board on a played season
  is a FAULT and not a result. **If awards are empty, check that log before the selection
  code.**
- **"Pre-existing" describes WHEN a failure started, not whether it matters.** This one
  was correctly bisected to "not mine" and was still a real bug in the suite.

## ⚠️ TYPE SCALE — a scale that is not used is not a scale (owner rule 2027-08)
The app had **768 px font-size declarations against a 12-token scale used SEVEN times**:
78% of all type under 14px, 34% under 12px, 31 distinct sizes with seven half-pixel
steps. Raised across the board with a hard floor of 11px (uppercase tracked labels only);
`tokens/typography.css` owns SIZES and weights, `tokens/fonts.css` owns FAMILIES (they
both declared families once and typography, importing second, silently won). **Use a
token; a literal is how the scale drifted from 12 values to 31.**
- **‼️ FIXED-SIZE BOXES ARE EXEMPT AND MUST CLIP.** A crest is an ICON, not prose:
  `.bl-crest.xs` is a 20px square, and four glyphs of 800-weight display type only fit it
  at ~9px, so the sweep's 9→11px raise pushed WAKE/TAMU/MICH/NCST out over the school
  name on every bracket, standings, portal and search row. Raising it means widening
  every crest box and so every dense row in the app. Compact sizes + `overflow: hidden`,
  which is a guarantee rather than an assumption about label length. Same for the recruit
  crest and the almanac rank pip.
- **Fixed grid columns are sized against the type they were designed with** — seven
  column sets needed widening.

## ⚠️ COLOUR — ten light schemes, and components read ALIASES ONLY
`tokens/colors.css` is three layers: palette slots → structural slots → semantic aliases.
A scheme (`[data-theme="…"]`) overrides the first two only, which is what lets ten
palettes exist without touching a component rule. **Never write a raw colour outside this
file.** `color-scheme: only light` is deliberate (Chromium's Auto Dark Theme re-inverts a
page that never asked). Schemes are shared with `prep-network/site/style.css`; the picker
list is `server.SCHEMES`.
- **Measure every slot against its own ground before writing it down.** The `clay` scheme
  contains NO colour dark enough to be ink — the darkest is 1.8:1 — so its ink and link
  are derived by pushing the palette's hues down. Dropped in as sent it would have
  rendered unreadable body text with no error anywhere.
- **Win/loss stays green/red in every scheme**: those carry MEANING, not identity.
- **A swatch is keyed on the scheme NAME** — rename a scheme and its chip goes blank
  while everything else still works. Every key in `SCHEMES` needs a `.fm-theme-sw.s-*`
  rule.
- A token that is referenced but never DEFINED silently keeps its hard-coded fallback and
  ignores every scheme (`--surface`, `--border`, `--text`, `--pos`, `--neg` all did).
  `grep -o 'var(--[a-z-]*' | sort -u` against the defined set after any token change.
See `docs/AAR-design-port-readability-and-suite-hermeticity.md`.

## ⚠️ VOCABULARY — "card" is NOT how tennis talks about a lineup (owner rule 2026-08)
An agent introduced "card" for a team's lineup/format and every later agent copied it
out of the code comments; it is now ~120 occurrences and it is **wrong**. Nobody in
high-school tennis says it. GHSA states the format as three singles and two doubles and
names the positions No. 1 through No. 3 singles / No. 1-No. 2 doubles; coverage says
"No. 1 singles spot", "second flight", "singles lineup". "Lineup Card" exists as KHSAA
*paperwork* (a form you hand the official) and some scorecards use it — administrative
language, never the natural noun for a team's competitive structure.

The real vocabulary: **lineup · dual format · singles lineup · doubles lineup ·
No. 1 singles · No. 1 doubles · flight · court · position · playoff roster ·
state lineup**.

| Wrong | Right |
|---|---|
| state card | state format · state lineup · 1S/4D format |
| regular-season card | regular-season format · 3S/4D format · league lineup |
| doubles-forward card | doubles-forward format |
| championship card | postseason format · state lineup |

‼️ **"card" has THREE senses here and only the lineup one is the mistake.** A **UI card**
(bracket card, player card, matchup card, `.brk-card`/`.jh-card`) is ordinary interface
language and is correct. A **schedule** sense ("a dual on a card") is real sports English
but not tennis — prefer *schedule* or *slate*. So this is never a blanket find-and-replace:
a sweep that rewrote `cv.cards` or `card_w` would break the bracket geometry.

**Not worth a migration on its own** (owner: the microcopy is all bad anyway) — the code
is unchanged and this is filed so it stops spreading. Fix the wording in files you are
already editing for another reason; don't open a rename PR for it.

## ⚠️ NAMES — the pools are curated data with THREE authorities that must agree
`generators/names.py` draws a player's name from `regions.json` (regions, subregions
and the owner's international-distribution PRESETS) over three bucket-keyed pools
(`male_first.json`, `female_first.json`, `surnames.json`).
See `docs/AAR-international-distribution-and-name-pools.md`.
- **‼️ DIASPORA IS DIRECTED, never a second roll on the world mix.** A region may only
  receive a name from a heritage it DECLARES (`diaspora` in `regions.json`); a region
  that declares none is monocultural. The 2026 blend drew the donor culture from the
  whole world mix, so **11.4%** of players had a name with no link to their country —
  Russian names on Dominicans, Chinese names on Africans ("the pool is a sieve … it's
  breaking my immersion"). Nothing errors: generated names are real names, so it reads
  as an odd squad, not a bug. `DIASPORA_SHARE` (0.12) is now ONLY the default RATE for
  a region that has declared sources — not licence to restore the undirected draw.
- **‼️ THE SCRUBBER IS AUTHORITATIVE — a name added only to the JSON is deleted on the
  next run.** `scripts/scrub_name_pools.py` rewrites several buckets wholesale from
  in-script allowlists (`KOREAN_SURNAMES`, `CHINESE_SURNAMES`, `KOREAN_FEMALE_GIVEN`,
  `TAIWAN_SURNAME_ADD`) and strips any token that is also a city or a scraped club
  name. Additions to a scrubbed bucket go IN THE SCRUBBER; place-name collisions that
  are genuine family names go in `SURNAME_CITY_KEEP` (Rosario, Jerez, Ramsay,
  Grandison, Toledo, Pickering…). **Always finish with `--check` and read the diff.**
  Write JSON the way the scrubber does — `indent=2`, `ensure_ascii=False`, trailing
  newline, **insertion key order (no `sort_keys`)** — or a four-name change reformats
  16,800 lines.
- **Repetition is measured as PRESSURE, not pool size**: expected draws per 10k ÷
  bucket size, at each bucket's HEAVIEST preset weight. A 200-name bucket at 4% is
  under more strain than a 40-name one at 0.1%. Target ≤1.5×; currently ≤1.1×.
  The exhaustion path returns the last valid (name, country), NEVER a
  `f"Player {randint}"` placeholder with an empty country — a repeated real name is
  cosmetic, `Player 447` is a visible defect.
- **The five owner presets each sum to EXACTLY 100.0 with `us` pinned at 30.0.** That
  anchor is what makes them comparable — fund any change from somewhere else. The
  Caribbean (12 regions) and `pacific_islands` were boosted 2–4× in 2027-08 (owner
  rule: warm-weather, high-sun, emergent), funded from `anzac` down to a floor and
  then Europe pro-rata — deliberately NOT from Africa or Asia, which the owner had
  just raised.
- **‼️ `region_weights()` IS NOT A PICKER MAP — it omits `us` by contract** (its share
  is the domestic split, not a region weight). Hand it straight to
  `make_name_picker` and the picker renormalizes over the international regions
  alone, so the world generates **100% international** players whatever split the
  owner chose; nothing errors and every name is real. `worldconfig.with_domestic
  (weights, share)` is the ONE place that scales an international mix and restores
  `us`; `full_region_weights()` is it applied to the world's own `intl_share()` (for
  generators with no per-program share — the pro league, free agents, rookies), and
  `ncaa.region_weights_for` is it applied to a program's level-derived share. The pro
  league shipped the bare map for a release.
- **‼️ A RETIRED REGION ID IS A SILENT LOSS OF SHARE, not an error.** `_draw_from_region`
  returns nothing for an id the table lacks and the picker just retries, so a
  persisted `region_w` naming an old id quietly redistributes that share — and a mix
  made ONLY of old ids burns all 500 retries into the `Player NNN` placeholder.
  `region_w` outlives the build that wrote it, so retired ids are folded into their
  successors in `worldconfig._LEGACY_REGIONS`, applied on READ (`region_weights_custom`,
  `parse_region_mix`) rather than by a one-shot migration nobody will run. **Renaming
  or removing a region id means adding a row there**, splitting by what the old region
  actually contained.
- **‼️ NEVER read `worldconfig` while holding a GTT/world SQLite transaction.** They
  share ONE file; `worldconfig.get()` opens its own connection and runs `CREATE TABLE
  IF NOT EXISTS`, which takes a write lock → "database is locked". Call
  `gtt_seasonmode._prime_world_config()` at the entry point BEFORE the transaction.
  This was latent for as long as the picker needed one config key (a warm cache meant
  the second connection was never opened); adding a second key fired it at once.
- **A new region needs a row in THREE files or it half-works silently**:
  `regions.json` (pools), `worldconfig._CONTINENTS` (editor grouping — anything
  unlisted is filed under "Other", which is how China, Japan and France ended up
  there) and `coaches.COUNTRY_REGIONS` (an unmapped ISO code becomes `"global"`).
  **A fourth consequence:** a renamed or new region id silently changes what an
  exported mix means, which is why `parse_region_mix` REPORTS `unknown`/`missing`
  instead of dropping them.
- **‼️ A REGION MIX IS A FILE FIRST, a saved row second (owner rule 2027-08).** The
  ~90 authored weights are the owner's most-retyped input — they rebuild the sim on
  every reload, so a mix stored in `world_setting` dies with the save it was meant to
  outlive. `/start` therefore DOWNLOADS a `*.ptc-mix.json` (`worldconfig.
  PRESET_FORMAT`/`PRESET_VERSION`, built client-side from the LIVE grid so it works
  before a world exists) and loads one back; "Save to this world" is a within-save
  convenience and the UI says so. Do not make the saved copy the primary and do not
  drop the download for it.
  - **Weights in a document are the EDITOR's integers, not fractions.** Normalising
    on save round-trips the MIX but not the DISPLAY — 160 comes back as 561, and the
    owner is authoring by eye. `applyWeights(map, fractions)` is the ONE apply path:
    bands pass fractions, files and saved mixes pass raw. A region at 0 is OMITTED
    (a missing key already reads as zero; ~60 explicit zeros would triple the file).
  - Loading sets the band `<select>` **silently** — firing its change event would run
    `applyBand` and clobber the mix you just loaded.
  - Coverage is a real browser (`node` + `playwright-core` against
    `/opt/pw-browsers/chromium-1194`), because the whole feature is client-side and a
    Flask test client cannot see a Blob download. `tests/test_region_mix_presets.py`
    covers the document, the drift report and the routes.
- Names are not save state — this changes future-generated worlds only.
- **‼️ US NAMES ARE FREQUENCY-WEIGHTED (owner rule 2026-08, OOTP-style).**
  `generators.names.draw_us_weighted` blends a real-frequency HEAD
  (`us_freq.json` — Census 2010 surname counts + SSA rank-shares, regenerate with
  `scripts/build_us_name_freq.py`, never hand-edit; the scrubber never touches it)
  at `US_FREQ_SHARE` 0.80 over the untouched curated buckets (the long tail). The
  curated pools were NOT removed — do not "dedupe" them against the freq file.
- **‼️ JHSAA NAMES ARE ERA-GATED BY ENTRY YEAR (`jhsaa.name_era()`).** Players are
  regenerated deterministically, so a draw change RENAMES every archived roster
  unless gated: cohorts entering ≥ the era draw the new ~90% weighted-US / 5%
  Canada / 5% international (exchange students) mix; earlier cohorts keep their
  exact old names. The era self-configures once per save (latest archived JHSAA
  year + 1, else 0) and persists in `worldconfig`; memoised, cleared by
  `reset_schools()`. ‼️ `_gen_seat` consumes EXACTLY ONE main-rng draw for naming
  in both eras, and always calls `generate_prospect` with country "US" (stamping
  `p.country` after) — passing the real country shifts talent/academic/hometown
  rolls and changes attributes, which the gate exists to prevent. Verified by
  byte-comparing rosters across the change.

## ⚠️ HOMETOWNS — generated from real place data, never hand-typed (owner rule 2027-08)
`generators/data/names/hometowns.json` holds two tiers with DIFFERENT key spaces that
collide (`us_states["CA"]` is California, `cities["CA"]` is Canada — 14 such keys; the
tiers are kept apart only by which function reads them). `scripts/build_hometowns.py`
rebuilds both from GeoNames (population) × the US Census Gazetteer (legitimacy —
GeoNames alone classes DC neighbourhoods like "NoMa" as towns; New England's
municipalities are cousub TOWNS and Hawaii's are CDPs, invisible in the place file).
Curated cities are a UNION on top (campus towns matter and sit under the floor). Do
NOT hand-type city lists back in — 33 of 55 states drew more recruits per class than
they had cities and nothing errored; regenerate instead. ~5,100 distinct US cities.
- **The floor is GRADUATED, per state (owner rule 2027-08)**: each state keeps the
  HIGHEST of (10k, 5k, 2k) that still yields ~`TARGET_PLACES` (40) places — "i don't
  need tiny places in big states but other ones should be represented more wholly."
  CA/TX/FL sit at 10k with no hamlets; VT/WY/MT/ME go to 2k and field their real
  small towns (VT 40, ME 124). The point is NARRATIVE DIVERSITY, not realism (owner:
  "the more the better — realism isn't the issue, it's interestingness").
- **Repeats ARE the weighting, in BOTH tiers** (`roll_us_hometown` and
  `roll_hometown` are flat `rng.choice`): one slot per 25k residents capped at 12 —
  the `import_jefferson` rule, ONE idiom. `ncaa.towns_in_region` DEDUPES, so repeats
  never distort the 70% local-roster draw; only distinct counts count there.
- **JF exports all 272 cities UNCAPPED** (owner rule 2027-08 — see the Jefferson §
  above; ~27% of the ~1,000-city west vs a 23% population share, accepted). The old
  cap defended a ~150-city pool that no longer exists; `import_jefferson`'s share
  report is the tripwire (warns past 35%) that lets it stay uncapped.
- **‼️ `scrub_name_pools.py --check` IS A REAL RUN, not a dry-run** (scrub, then
  verify idempotency). The rebuild's new Canada/Mexico cities deleted curated
  surnames TWICE — 38 at the first pass (García, Thompson, Brooks, Mercier…), 38
  more at the graduated-floor pass (King and Almonte are Ontario townships,
  Armstrong/Merritt BC towns, Alvarado/Hidalgo Mexican municipios) — each time
  before the keep-set caught up. Restore from git, extend `SURNAME_CITY_KEEP`,
  re-run. Only the `cities` tier feeds the scrubber; `us_states` never does.
- **The curated baseline lives in `hometowns_curated.json`, NOT the live file.** The
  generator unions THAT over its output; unioning the live file (mostly generated
  after one rebuild) would grandfather every generated town in forever — a place
  GeoNames drops or a tightened floor excludes could never leave. Add hand-picked
  cities to the BASELINE and they survive every rebuild. The dump cache is validated
  by member name (a stale zip from a different dump shadowed the download once).
- `flavor.py` defines `_load_us_states`/`roll_us_hometown` TWICE (the first pair is
  dead code — Python keeps the second); hometown caches are module-global and cleared
  by NOTHING, so a data change needs a process restart. A player's hometown is
  materialised at generation and persisted — expansions change new players only.

## ⚠️ SCHOOL NAMES carry NO institutional suffix (owner rule 2027-08)
"You don't need to have HS or High School ever, or even 'School' because nobody uses
it" — a day school reads "X Day" ("usually it just says Day"), and **"School of
SUBJECT" collapses to the subject, truncated at "and"**: "San Cordero Commerce",
"Calder Science", and — the validating real case — "Bronx Science". This REVERSED
the original rule, which APPENDED " High School" to bare names and, not knowing "HS"
was a school marker, shipped "Baptist HS High School".
- **PLACE of-phrases collapse too** (owner correction: "Jesuit Sacramento is exactly
  what it'd be called. Just like Chicago or Boston Latin"): normally PRE + PLACE
  ("Jesuit Sacramento", "Jesuit Dallas" — "College Preparatory School of" collapses
  like "School of"), but the classic type-named schools read PLACE + TYPE
  ("Chicago Latin", "Boston English", "Wilmington Charter") — `_TYPE_FIRST` in both
  import scripts. **"of the X" where X is not a subject stays whole** ("Jewish
  Community High School of the Bay", "Carnahan High School of the Future") — no
  colloquial collapse exists for those. New subject/type words go in BOTH copies.
- Enforced in THREE places that must agree: `import_jefferson.high_school_name`
  (strips + collapses, never appends), `import_jhsaa._display_name` (at EMIT,
  exactly like `RENAMES` — dice/districts/identity all run on the source name), and
  the one-time pass applied to all 56 states of `high_schools.json` (13,800+
  suffixes stripped, 16 School-of names collapsed).
- **‼️ FETCH BEFORE YOU CONCLUDE THE SOURCE IS GONE.** `data/jhsaa/schools.json` IS
  regenerable: prep-network carries **1,111 schools across nine classifications
  (9A-1A), enrollment 56-2,597**, and `scripts/import_jhsaa.py` reproduces the
  association from it (852 girls'/767 boys' programs, every 40-field class clear of
  `jhsaa.sponsor_floor` in both genders).
  > ⚠️ An agent concluded the opposite in 2027-08 and wrote it down as a rule — that
  > the nine-class records "were never committed to prep-network", so the file was the
  > de-facto source of record and changes had to be applied as transforms. It was
  > checked with `git log --all` against a LOCAL clone that was **eight commits behind
  > on main**, and `--all` does not see what has not been fetched. The records had
  > landed in "Nine counties settled, and one classification ladder for the whole
  > state". Two transform scripts and an enrollment cascade were built on that
  > mistake. **`git fetch` first; "not in any ref" is a statement about your clone.**
  `scripts/jhsaa_apply_renames.py` and `scripts/jhsaa_reclassify.py` survive that
  episode as targeted transforms and hold **zero names or numbers of their own** —
  every table comes from `import_jhsaa`, which stays the one authority — but the
  importer is the primary path and a re-import supersedes them.
- **‼️ RIVALRIES — pairs that must NEVER be separated (owner rule 2027-08,
  `import_jhsaa.RIVALRIES`).** A rivalry is a fact about two programs, not about their
  enrollments, so it outranks reclassification, league assignment and playing up alike.
  It NEEDS a rule because a district is `(classification, name)`: once two rivals sit
  in different classes there is no league either could join to be with the other, so
  the split is unrepairable. Condotti Vanguard Academy (1,666) and Romero-Finniski
  (1,526) — both Ashbury, both always Metro League — were split by a 1,638 cut line
  with every individual number correct.
  - **A pair is promoted only if EVERY member clears the cut**, and **the whole class
    is decided BEFORE any of it moves**: checked row by row it splits the pair the
    OTHER way when both qualify, because the first is promoted and the second then
    reads its already-moved rival as no longer being in the source class.
  - **`draw_districts` sorts a pair adjacently AND walks the block boundary past it.**
    Adjacency alone is not enough — the boundary landing exactly between them is what
    split those two on a 7A redraw, with nothing having moved either school.
  - `jhsaa_reclassify.check_rivals` ASSERTS the invariant rather than repairing it: a
    drifted pair means the mechanism that moved them is broken, and quietly pulling
    them back together hides that.
- **‼️ PLAYING UP — a school competes ONE class above its enrollment class (owner rule
  2027-08).** 13 blue-bloods, seeded by `scripts/jhsaa_playup.py` from the archetype
  list with `overrides.set_jhsaa_playup` / `/editor/jhsaa-playup` layered on top, the
  archetype pattern exactly ("yes" promotes, "no" holds, clearing reverts to the file).
  - **Archetypes have the same board** (`jhsaa.archetype_board`, `/editor`): the ~91
    tagged programs grouped by kind, each row's `<select>` changing kind in place, add by
    type-ahead, Remove demoting a seeded program and clearing an added one, demotions
    shown as restorable chips. `EDITABLE_ARCHETYPES` excludes `upstart` — it is a rolled
    run and storing one would make it permanent.
  - **‼️ BOTH BOARDS LIVE AT `/jhsaa/programs`** (the section's "Programs" tab), NOT on
    `/editor`. They were panels three and four down the COLLEGE roster editor — whose
    toolbar is Division / Conference / Team — where the owner could not find them. A
    JHSAA property belongs under the JHSAA. The POST routes keep their `/editor/jhsaa-*`
    paths (they are the same writes) and carry `back=jhsaa` so `_editor_redirect` returns
    to the JHSAA page instead of the college one.
  - **The BOARD** (`jhsaa.playup_board`) shows ONLY the ~13
    programs that play up: add is a type-ahead over the names, remove is a button on the
    row, and a removed default shows as "held" so it can be restored. ‼️ Never render the
    association as a list to scroll (owner, 2026-08: "I don't want a list with 100s of
    schools I have to scroll"). The add field is **`jh_school`**, not `school` — `school`
    on that page is the COLLEGE program `_editor_redirect` reads to come back, so a JHSAA
    name in it sends the editor to a school its division has never heard of.
  - **‼️ SMALL SCHOOLS ONLY — `PLAY_UP_MAX_GROUP` 4A and below, enforced at RUNTIME
    (`jhsaa.can_play_up`), not just at import.** The constant lived only in
    `scripts/import_jhsaa.py`, so the rule bound the SEED LIST and nothing else — the
    editor would promote an 8A program into 9A, and a crafted POST anything. It is now
    checked in `plays_up()` (the read, so a stale or crafted row cannot promote), in the
    picker (`playup_board` offers 366 of 857) and in the route. "no"/clear stay legal for
    every school: holding a program in its own class is always allowed.** (owner correction
    2027-08): "play up is for schools at the 4A or under level to play with teams at
    their competitive level, not already big schools". An 8A blue-blood moving to 9A is
    not playing up, it is a big school in a slightly bigger class — and the first pass
    shipped exactly that. 9A's exclusion falls out of the same rule.
  - **‼️ IT MOVES `group`, NEVER `classification`.** `group` is the championship you
    enter — leagues, the ladder, State, All-State; `classification` is how many students
    you have, and `_TALENT` reads THAT (`School.talent_group`). Keyed on `group`, a 5A
    blue-blood playing up to 6A is silently GENERATED with 6A talent: a free roster
    upgrade that inverts the whole choice, since playing up must cost you a harder field.
    Pinned by measurement in `tests/test_jhsaa_playup.py` — hold one in its own class via
    the override and its twelve players come out identical to six decimals. Nothing else
    catches it; the rosters look fine either way.
  - **The LEAGUE moves with the program** (a district is `(classification, name)`, so a
    6A competitor carrying its 5A league name is alone in a 6A district — no league
    season at all), and **all play-ups are placed in ONE pass**: applied per school
    independently, two 8A blue-bloods both picked the same 9A league and took it from 11
    to 13, because neither could see the other. The running count must include the
    play-ups already placed.
  - **`jhsaa_playup_version()` keys the season cache beside the archetype one**, and
    `jhsaa.reset_schools()` exists because `load_schools` bakes group and league into the
    School objects — `reset_all()` alone does not clear them.
- **‼️ THE PRIVATE-SCHOOL LAYER — VARIED INSTITUTIONAL GRAMMAR (owner rule 2027-08).**
  25 of the most obvious generated-person schools became institutions, spread EVENLY
  across all eight classifications ("about 15-25 institutional private-school names,
  not hundreds" — never a mass rename; 297 person-named schools remain and that is
  fine). The register lives in the MIX — Academy · Cathedral · Prep · College Prep ·
  Catholic · Christian · bare — because a layer built from one template reads as one.
  **Prelate names come from Jefferson's OWN surname pool** (Bishop Valera, Archbishop
  Valois, Cardinal Mercier, Cardinal Echevarria); never coin a fresh surname.
  Archbishop Gregory is an owner mandate. Sinkford is a UU boarding school in the
  Juniper Highlands with an inexplicably serious tennis program, and it exists so the
  layer is not Catholic prep and evangelical academy and nothing else.
  - **‼️ AND STILL NO SUFFIX.** Asked directly whether these keep "High School", the
    owner said no — "you say Archbishop Gregory, I know what you're talking about …
    you don't have to go to school after it". `_SUFFIX_RE` is UNTOUCHED and there is
    no exemption list; the names are simply written bare. Academy, Prep, Cathedral and
    Catholic were never suffixes and survive on their own, which is the whole reason
    the varied grammar needs no rule change. **Prep, never Preparatory** (owner).
  - `MASCOTS`/`COLORS`/`PRIVATE_SCHOOLS` key on the **DISPLAY** name, so a rename
    silently orphans a mascot entry and the school reverts to its source record's
    (`MASCOTS["Oskar Bellini"]` did exactly that). Move the key with the name.
  - **‼️ NEVER RENAME A REAL PERSON'S SCHOOL.** The person-named pool mixes invented
    names with genuine ones — Theodore Roosevelt, Bayard Rustin, Octavia Butler, James
    Baldwin, Gwendolyn Brooks, Thurgood Marshall, Mae Jemison, Barack Obama, John
    Lewis and every president. The presidents and justices are in `OWNER_EDICTS`; the
    rest are NOT, so "looks like a person" is not the test.
- **‼️ A PROGRAM THAT STOPS SPONSORING KEEPS ITS PAGE (owner rule 2026-08,
  `jhsaa.former_school` / `sponsors_sport`).** `load_schools` filters on the
  `girls`/`boys` flag — correct for every CURRENT-season surface (the directory, the
  leagues, the ladder, the rankings) and it also meant the program page and every
  player page 404'd the moment the flag went off. The archive is untouched by a
  sponsorship change, so the school's state title went on standing on the title board
  and the champions grid with a DEAD LINK under it: the trophies stayed and the pages
  that explain them died. Measured, not theorised.
  - The two views fall back to `former_school`, which builds the School from its data
    row whatever the flag says; `None` still means a name no row carries, which is a
    real 404. **Resolved on READ, nothing migrated** — the same answer a rename gets
    (`world._relabel`), for the same reason.
  - **It opens on the LAST SEASON THEY PLAYED.** The default year is the newest the
    association has archived, which a former program has no row in, so the page would
    render its header over an empty season and read as a bug. An explicit `year` is
    still honoured.
  - `former_school` is deliberately NOT part of `load_schools`: that is the hot path
    (~1,600 roster builds a season) and every caller of it means "the programs playing
    this year". It is a fallback, and the only way a non-sponsor is ever built.
  - Sponsorship is per SPORT — dropping the girls' team leaves the boys' program live.
  - A sponsorship change still redraws the leagues of the classes it touches
    (`scripts/jhsaa_sponsors.py`); that is unavoidable and is the section's own rule.
    An incoming 1:1 replacement is a new row with a new name, so it generates twelve
    new players and inherits nothing — which is what an expansion program should do.
    `tests/test_jhsaa_former_program.py`.
- **‼️ MASCOTS: THE FOREIGN-FAUNA CLEANUP (owner rule 2026-08,
  `import_jhsaa.MASCOT_FIXES` + `scripts/jhsaa_mascots.py`).** An earlier pass was
  asked to forage the world's animals so the state would not be five hundred Eagles.
  It worked at the head of the list and left ~130 programs named after animals no
  American high school has ever used — Muntjac (7), Sitatunga, Bogongs, Serows,
  Saiga, Takin, Markhor, Hamerkops, Kookaburras, Quolls, plus a shelf of foraged
  insects. 134 schools changed, 70 names retired; the head is untouched (Eagles 19).
  - **‼️ THE BAR IS "WOULD A US HIGH SCHOOL PUT THIS ON A JERSEY", NOT "IS IT
    OBSCURE".** The genuinely strange AMERICAN names are the best thing in the file
    and none was touched — Beetdiggers, Cornjerkers, Whistlepunks, Shingle Weavers,
    Highclimbers, Tie Hackers, Gandy Dancers, Cheesemongers, Onion Toppers, Hop
    Pickers, Sugarbeeters, Hardrockers, Orediggers, Lava Bears, Vaudevillians, Poets,
    Pelotaris, Bar Pilots, Fogbells all have real counterparts (Jordan HS
    Beetdiggers, Hoopeston Cornjerkers, Shelton Highclimbers, Bend Lava Bears,
    Whittier Poets, Alva Goldbugs). Local fauna stays too, however unusual —
    Ensatinas, Giant Salamanders, Kokanee, Chukars, Sage Grouse, Rockchucks,
    Skookums, Chinook — because it belongs to this ground. Overlaps are fine and
    expected ("like real life").
  - **Keyed on the MASCOT, not the school**: the offending NAME is what is wrong, so
    one entry fixes every program carrying it and any future import that draws it.
    Each maps to a POOL, picked per school on a stable hash, so seven Muntjac do not
    become seven of anything else — check the script's "names that grew by 4+" line
    after any retune, which is what caught Goldbugs +11 and Hornets +14 in drafts.
  - Per-school OWNER PICKS go in `MASCOTS` (keyed on the display name) and outrank the
    table: Plainfield are the Cardinals, Condotti Vanguard Academy the Valiant.
  - Nothing keys on a mascot string and no archive stores one — it is read live off
    the school row — so this is display-only and cannot disturb a played season.
- **‼️ A JHSAA display rename MUST stamp `School.source`** with the pre-rename name
  (generation keys pids on `source or name` — move the name without it and the
  program gets twelve strangers and archived awards point at nobody), and
  `data/jhsaa/archetypes.json` keys on the DISPLAY name, so its keys move too.
- **‼️ OWNER EDICTS ARE NOT UP FOR REVISION** (`import_jhsaa.OWNER_EDICTS`, 2027-08).
  57 names — schools, towns and two areas — were dictated BY NAME rather than
  arrived at by a generator or proposed by an agent. A later pass may rename
  anything it finds bland; it may NOT "improve" one of these, fold it into a
  naming family, or trade it away to settle a collision. **If one collides, the
  OTHER thing moves.** The list exists because this map has been swept a dozen
  times and the failure mode of a sweep is treating a deliberate name as noise.
  Verified against the data: all 57 are live.
- **‼️ A JHSAA DISPLAY NAME MUST BE UNIQUE — it IS the archive identity.** It keys
  `run_season`'s teams dict, `world_jhsaa_dual.school`, the routes and the pids; two
  schools sharing one name silently merge into one archive slot while the standings
  keep both rows, so a record stops covering the duals played and NOTHING errors
  (shipped once: a split campus's "…Science and Technology North" collapsed to the
  same "Jefferson Science" as its sibling — the collapse now keeps a trailing
  campus qualifier, `import_jhsaa.build` refuses to emit a collision, and
  `test_display_names_are_unique_identities` pins the data).
- **‼️ AND `source or name` — THE ROSTER IDENTITY — MUST BE UNIQUE TOO (2026-08).**
  The display name is one identity; the SOURCE is the other, and it is the one that
  keys `RENAMES` and seeds the RNG that builds a program's players. Two consequences,
  both live faults that shipped:
  - **Two rows sharing one identity string** are two schools that a single `RENAMES`
    entry catches together and that generate the same twelve people. One school kept
    `source: "Wheatley"` from a rename whose source prep-network had since renamed
    away, while a DIFFERENT school was simply CALLED Wheatley.
  - **A `RENAMES` key that is a live school's own name** reaches that school. It lies
    dormant until some school carries the string and fires the day one does — so a
    DEAD entry (key matching neither prep-network nor any school here) is not history
    worth keeping, it is a loaded gun; 16 were removed. Prune them.
  `scripts/jhsaa_apply_renames.py` asserts both BEFORE renaming (`check_identities`,
  `check_rename_keys`) and exits naming the offender. The Wheatley case surfaced only
  because the two then collided on a DISPLAY name; had the targets differed it would
  have been silent.
- **‼️ LOCALITY — the settlement inside the city, and NOT a second city (owner spec
  2026-08, `import_jhsaa.LOCALITIES` → the row's `locality` → `jhsaa.School`).** The
  five big metros carried 28-44 tennis programs each, which no single municipality
  does; in life those schools sit in CDPs, unincorporated places and absorbed towns.
  So `city` stays the metro — every district cut, geography lookup and non-district
  pairing reads it and none of them change — and `locality` names the settlement,
  shown ahead of the city in the address line. Keyed on the DISPLAY name like MASCOTS,
  so it moves with a rename. **Empty means a CORE CITY school**, a real distinction
  rather than a missing value, so there is no default. Localities REPEAT by design,
  within a metro (Natchez Prep and Natchez Cliff) and across two of them; nothing keys
  on one. 121 of 862 programs carry one.
- **‼️ WHO SPONSORS TENNIS IS A MAP DECISION** (`import_jhsaa.EXTRA_SPONSORS` /
  `NEVER_SPONSOR`, applied in `sponsors()` AFTER the draw beside `SUBSTITUTIONS`, and
  to the committed data by `scripts/jhsaa_sponsors.py`). 83 Jefferson towns had a high
  school and no tennis at all while five cities carried 28-44 programs. ‼️ Both tables
  must be applied in `sponsors()` and not only in the transform, or a full rebuild
  silently drops a forced-in school the dice never drew. **A sponsorship change redraws
  the leagues of the classes it touches** and that is not avoidable: a district is a cut
  of a geographic ORDER into blocks of `MAX_DISTRICT`, so there is no seat to slot into
  — measured, every league a new school belonged in was already full at 12 and every
  league with room was elsewhere in the state. The script redraws the affected groups
  through `draw_districts` and checks `MAX_DISTRICT` after, leaving other classes alone.
- **‼️ A SCHOOL HAS THREE IDENTITIES AND THEY ARE ALL `str`** (owner rule 2026-08,
  four faults — `docs/AAR-jhsaa-identity-names-and-redistricting.md`): `source or name`
  is the ROSTER identity (seeds the players and their pids), the DISPLAY name is the
  ARCHIVE identity (keys `world_jhsaa`, the routes), and prep-network's name is the
  SOURCE identity (what `RENAMES` and `AREA_RENAMES` are keyed on). Nothing tells them
  apart at runtime.
  - **A rename must not cost a school its history.** The archive keys on the display
    name at the moment a season was written, so a rename orphans everything the program
    already earned — a 2031 state champion vanished from its own page. Archived seasons
    are RELABELLED INTO TODAY'S NAMES ON READ (`world._relabel`, in `get_jhsaa` and the
    dual rows), never migrated: the archive stays the record of what was written and the
    next rename needs no migration. ‼️ The relabel is KEY-DRIVEN, not a blanket string
    swap — ten former school names are also live TOWN names (Port Veles, Ashbury,
    Telfair, Orellana), so matching on the string alone rewrites addresses. A missed
    shape keeps an old name (a visible broken link); a blanket swap moves a school to
    another town silently.
  - **The alias table cannot be typed** — renaming twice REWRITES the target in place,
    so intermediate names live only in git. `scripts/jhsaa_former_names.py` walks every
    revision of `import_jhsaa.py` and emits `data/jhsaa/former_names.json` (the app reads
    data files, not `scripts/`). ‼️ **A LIVE NAME ALWAYS WINS** (`jhsaa.current_name`):
    a retired name reissued to another program must never serve the wrong record.
  - **A DEAD KEY IS A LOADED GUN, not history.** A `RENAMES` key matching neither
    prep-network nor any school here cannot fire — until some school is named that
    string, which is exactly what "Wheatley" did (one entry reached two schools; it
    surfaced only because they then collided on a display name, and would otherwise have
    had both generate the same twelve people). 16 were pruned;
    `jhsaa_apply_renames.check_identities` / `check_rename_keys` assert it now.
  - ‼️ **A GUARD WRITTEN FROM ONE INCIDENT TENDS TO FORBID THE INCIDENT, NOT THE FAULT.**
    The first version of that check refused any key that was a live school's own name —
    which is the ORDINARY path, since a school never renamed IS its own identity — and
    it blocked four legitimate renames.
  - **A rename table keyed on ANOTHER repo's names is a foreign reference with no
    constraint behind it.** prep-network renamed Mother Lode to Siskiyou Valley and the
    `AREA_RENAMES` entry silently stopped firing; the committed data already held the
    right string, so only a re-import would have shown it. `jefferson_gazetteer.py`
    compares the two area sets on every run and caught it immediately.
- **‼️ REDISTRICTING: LEAGUES REALIGN **AND REBRAND**, AND SIZE OUTRANKS GEOGRAPHY**
  (`scripts/jhsaa_redistrict.py`, owner rule 2026-08). Leagues are cut from a geographic
  ORDER into blocks, which leaves the REMAINDER as geographic leftovers: ten leagues in
  6A/7A/8A spanned over 250 miles, the worst about 400. A block still INHERITS the name
  it most OVERLAPS — a league keeps its historical core, which is what makes most of a
  realignment read as a realignment — but the first version held the names FIXED as an
  absolute, and that is half the rule. Real associations redraw on a cycle and names
  come and go: the OSAA runs a four-year classification-and-districting period, and its
  2026-30 redraw created a brand-new seven-team 6A/5A **Southwest Hybrid** rather than
  merely reshuffling membership. So a class that GAINS leagues draws new names from
  `LEAGUE_NAMES` (the same authority the importer names from, same rules — unused in
  the class, no two sharing a LEADING WORD) and a class that loses them retires names;
  a block with no free overlap rebrands rather than reaching for an unrelated leftover.
  **‼️ AND STRICT GEOGRAPHY IS NOT THE CONSTRAINT** (same rule): distance is a cost,
  not a rule — the OSAA puts Bend's schools in leagues that involve real driving. The
  redraw minimises span, but SIZE wins: a league near `DISTRICT_TARGET` with one distant
  member beats a tight one with six, because **league size IS the schedule**. Assignment
  order is REGRET, not nearest-centroid (which hands one metro every seat while its
  neighbour starves); the floor pass pulls a short league up to strength using its
  NEAREST available member; rivalries are repaired last and outrank geography.
- **‼️ `MAX_DISTRICT` (12) IS A CAP, `DISTRICT_TARGET` (10) IS THE SIZE** (owner rule
  2026-08). `draw_districts` took `k = ceil(n / MAX_DISTRICT)` — the FEWEST blocks that
  fit under the cap — which quietly turned a ceiling into a target: every class packed
  its leagues to 11-12 and the cap became the design. Owner: "no conference should be
  over 12 teams like I said before, with 40 teams there's no reason for some weird cap
  on districts when smaller ones (around 10 teams) would be fine." `import_jhsaa.
  district_count(n)` is now the ONE authority on how many leagues a pool wants — aim at
  ten, never exceed twelve — and both the importer and the redistricter read it. A class
  is redrawn whenever its league count no longer matches it **in EITHER direction**: the
  old condition was "does it still fit under the cap", which only ever fires on GROWTH,
  so the class a realignment takes schools OUT of kept whatever leagues it had at
  whatever sizes were left. Every class now runs 9-12.
- **‼️ THE 2033 2A/3A REALIGNMENT — a RECLASSIFICATION, not a competitive move**
  (`import_jhsaa.RECLASSIFY_TO_2A`, owner rule 2026-08). 2A carried 63 programs to 3A's
  125, so 3A crowned from 40 and 2A from 24 — and 2A was the class the 1A/2A split was
  meant to leave viable. 32 named schools moved down; 2A is 95 programs in 10 leagues
  with a 40-team field, 3A is 93 in 9, 1A is untouched. **It moves `classification` AS
  WELL AS `group`, and that is the whole distinction from `COMPETITIVE_MOVES`**:
  `_TALENT` generates from `classification`, so a school moved on `group` alone keeps
  its old class's players — right for a program petitioning down on RESULTS, wrong here,
  where the association is saying these schools are 2A-SIZED. They are: every one
  already sat inside 2A's committed enrollment band (306-375 against 86-431), so nothing
  needed scaling. It is a NAMED TABLE rather than a moved cut line because the owner
  named the schools — a line at ~380 takes a different 32 (3A's smallest is 303 and
  stays 3A), and the association's judgement is the input, not a threshold
  reverse-engineered to approximate it. Keyed on the DISPLAY name (everything else in
  `reclassify()` is on prep-network's canonical name), and it runs LAST, because every
  school it names sits above `PROMOTE_2A_ABOVE` and would otherwise be promoted straight
  back.
- **‼️ `COMPETITIVE_MOVES` is the mirror of PLAY_UP** — a program may be placed BELOW its
  enrollment class when it cannot compete where enrollment puts it, and the ENROLLMENT is
  scaled to match rather than the other way round (the numbers are fictional; the number
  follows the decision instead of blocking it). Like play-up it moves `group`, NEVER
  `classification`: keyed on `group` a demoted school would also be GENERATED with the
  weaker class's talent, turning a fairer field into a self-fulfilling collapse.
- **‼️ WHERE A SCHOOL IS: `docs/GAZETTEER-jefferson.md`, generated by
  `scripts/jefferson_gazetteer.py`.** Read it before working on a school. The
  geography is REAL — each fictional county stands on a real one in southern
  Oregon / northern California / northern Nevada / western Idaho and every town has
  real coordinates — so bearings and distances are answerable, and are COMPUTED in
  the document rather than asserted (a hand-written "X is in the south" rots the
  moment a county moves). Four layers that are not interchangeable: **area** →
  **county** → **town** (`city`) → **locality** (a settlement INSIDE a big city). A
  DISTRICT is a fifth thing and is NOT geography — drawn per classification over a
  geographic order and named from an independent bank.
  ‼️ prep-network has its own, richer gazetteer, but under ITS names — which is
  exactly why one was needed here; a reader looking a town up there will not find
  what the app shows. The generator asserts the two AREA sets agree on every run,
  and that check immediately caught a dead `AREA_RENAMES` key: prep-network had
  renamed Mother Lode to Siskiyou Valley, so the entry no longer fired and a full
  import would have emitted the wrong area name for Southern Jefferson. Nothing
  else could have shown it — the committed data already held the right string.
- **The mapping prep-network carries is generated too** —
  `scripts/prep_network_name_map.py` writes `docs/JHSAA-name-map.txt` into that repo.
  Run it beside the two above after any rename batch.
- **The current name list is GENERATED, never hand-kept** — `scripts/jhsaa_name_list.py`
  → `docs/JHSAA-school-names.txt`. Renaming is an ongoing owner pass, so a typed list is
  stale the moment one lands. It groups by city and leads with the NEAR-DUPLICATES,
  because a name is a problem when it fails to DIFFERENTIATE, which is a property of a
  pair. ‼️ A compass point on the CITY's own name (Belmonte North) is how real districts
  name schools and is deliberately NOT the target; the fault is the same words plus a
  word carrying no identity (Harrow Works beside Harrow). Re-run after any batch.
- `flavor._HS_SUFFIX` (the no-list fallback) says "Day", never "Day School".

## Other notes
- **⚠️ TOSS flight weights are PER-DIVISION, and there is NO fallback (`app/rating.py`)** —
  the dual is per-division, so the weight table is too: `rating.DIVISION_WEIGHTS` has one
  per format and `weights_for(division)` raises on a division nobody has weighted. The
  module-level `FLIGHT_WEIGHTS` is the engine's CLASSIC 6+3 (cups, tests, bare calls) —
  **not** what D1-D4 play; never let a division fall back to it. `_flight_score` raises on
  an unrecognised flight for the same reason: a missing weight is a missing DECISION, and
  the caller must stop rather than be served a number nobody chose. This is not
  hypothetical — a `.get(slot, 0.3)` default was **26% of a D1 dual's flight weight** for a
  release, with #10 singles counting **1.5× #6**, so the index ran backwards across the
  bottom half of every D1 lineup while nothing errored. If you add a division or change a
  dual's shape, add its table. See `docs/AAR-toss-per-division-flight-weights.md` (and
  `docs/BLOG-toss-in-a-third-format.md`). **Validate a rating change on the SEEDS, not the
  cutline**: `committee_seed_score` is only 45% Power Index rank, so that inversion moved
  92% of D1 programs and 61% of the field's seeds while changing tournament membership by
  exactly one team — checking who made the field would have called it a rounding error.
- **Coach development multiplier is STRONG (±30%) and anchored on the OBSERVED
  score band (owner rule 2027-07)** — `coaches.development_multiplier` maps
  development_score 35..65 → 0.70×..1.30× growth in `world.developed_rosters`.
  Generated scores cluster ~40-65, so anchoring on the theoretical 20-80 scale
  compresses the real spread to ~±12% and silently reverts the owner's choice —
  don't "fix" the anchors back. Juniors and pro decline stay coach-free. See
  `docs/AAR-coach-development-growth.md`.
- **Postseason lineups are strict best-six (owner rule 2027-07)** — CT/NCAA duals
  field the healthy top six by results STR, no rotation/resting/coach noise
  (`coach_lineup best_six`); ITA events deliberately KEEP rotation (everyone
  plays). See `docs/AAR-postseason-best-six-lineups.md`.
- **D3/D4 play "play-play" — every match finishes (owner rule 2026-07)** — D3/D4
  **regular-season + ITA** duals play ALL singles to completion instead of
  abandoning dead rubbers at the 4-point clinch (`simulate_dual play_all`, gated
  in `season.dual_between` on both-D3/D4 + `not best_six`). Real ITA D3 format;
  the point is fuller player stats for portal/move-up. It NEVER changes the winner
  (4th point locks it; loser caps at 3) — only fills the margin, so a D3 dual
  showing **6–2/7–0 is correct, not a bug**. D1/D2 and D3/D4 **postseason** keep
  clinch-play. See `docs/AAR-d3-d4-play-play-format.md`.
- **NCAA bracket is TRUE-SEEDED (owner rule 2026-07): no conference separation** —
  the draw is never rearranged to keep same-conference teams apart, for BOTH genders
  and every division. `_pair_penalty` deliberately has no same-conference term; do
  not add one back. Only rematch and AQ-vs-AQ avoidance shape the draw. See
  `docs/AAR-true-seed-no-conference-separation.md`.
- **The NCAA field is SELECTED ONCE AND LOCKED (`ncaa_draw`) — never re-derived** —
  the seeds and the four S-curve regions are the same computation, so anything that
  moves `committee_seed_score` moves teams between regions. The field used to be
  recomputed on every read while one input (`team_form`) counted the very bracket it
  was seeding, so the labels drifted mid-tournament: 67–80 of 96 seed positions moved,
  most duals showed no region and some teams no seed at all (the bracket itself was
  always correct — only the labels lied, which is why it hid for so long). Never feed
  `committee_seed_score` anything outside `SEED_ROUNDS`, and read the field back from
  the lock (`_load_draw`) instead of re-selecting. The bracket page is a real
  elimination tree positioned SERVER-SIDE (`state._bracket_canvas`): cards and the SVG
  elbows share one coordinate system, so never "fix" bracket alignment in CSS — resize
  through that function's `card_w`/`card_h`/`gutter`/`leaf_gap`. See
  `docs/AAR-ncaa-bracket-region-drift.md`.
- **ONE bracket surface — the Preseason NIT draws on the NCAA's tree** — a Kickoff site
  is a region ladder and the Team Indoor is the draw they feed, so `/season/ita` and
  `/ncaa` share `_bracket_canvas`, `templates/_bracket.html` (the `brk_row`/`brk_canvas`/
  `brk_toolbar`/`brk_script` macros) and the `.brk-*` block in `static/css/bracket.css`.
  Don't fork the markup for a third bracket — import it. NIT seeds are read back off the
  PERSISTED DRAW (sites pair 1v4/2v3; the Indoor uses `bracket._seed_positions`), never
  re-derived from `_ita_ranking` — that's a live Power Index, so re-reading it would
  relabel a week-1 bracket all season, exactly the drift above. See
  `docs/AAR-preseason-nit-bracket.md`.
- International roster share is by division + gender + academics + a coach dice roll;
  academics damps it (academic schools are US-heavy). See
  `docs/AAR-base-roster-nationality-by-level.md`. Tuned for playability, not 1:1 realism.
- **Service academies are US-citizens-ONLY — a HARD gate, not a low share (owner rule
  2026-07)** — `ncaa.SERVICE_ACADEMIES` (Army, Navy, Air Force, Coast Guard, Merchant
  Marine) can NEVER roster an international, through ANY pipeline: base roster, recruiting
  drip, fall/pre-season/year-end portals, `_normalize`, coach carousel, pro free agents,
  walk-on fill. Every path calls one authority (`ncaa.admits_nationality` /
  `blocked_schools_for`); if you add a pipeline that places a player at a program, wire it
  too. The Citadel/VMI are state military colleges, NOT federal academies — deliberately
  ungated, don't add them. The `/editor` move is the owner's god-mode and stays ungated.
  See `docs/AAR-service-academy-us-only-rosters.md`.
- Pre-existing test fragility: `test_roster` `strong > weak` is a borderline
  calibration check that can flip with RNG shifts — investigate, don't blindly edit.
- Run the full suite with `python3 -m pytest -q` (≈10 min).
