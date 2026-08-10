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

## ⚠️ JEFFERSON — a fictional 51st state (`JF`), imported from `prep-network`
Jefferson is an alternate-history West Coast state (~17.6M) whose 20 counties stand on
real southern-Oregon / northern-California / northern-Nevada / western-Idaho ground. It
is an ORDINARY state here: `("Jefferson","JF")` in `juniors.US_STATES`, `STATE_REGION
["JF"]="W"`, `scout_intel.US_REGIONS["JF"]="Pacific"`. Owner rule 2027-08: the JHSAA high
school season is **invisible** in this sim and recruits are **generated** like any other
state's — do not build a HS archive or import prep-network's simulated players. Traps:
- **The `us_states["JF"]` city pool is capped at 46 cities and MUST stay proportional.**
  It feeds `roll_us_hometown` (flat choice, so its population repeats are the weighting)
  AND `ncaa.towns_in_region("W")` (dedupes, so only the DISTINCT count counts) — the pool
  every western program draws local base-roster players from at `LOCAL_REGION_TARGET`
  0.70. All 272 cities made Jefferson **64%** of that pool: every CA/OR/WA roster fills
  with Jefferson kids and NOTHING ERRORS. 46 ≈ its 23% population share.
  `scripts/import_jefferson.py` prints the share and warns above 30%.
- **`US_JUNIOR_TENNIS_ORIGIN_WEIGHTS` no longer sums to 1.0** (~1.134) — deliberate, they
  are relative and `rng.choices` renormalizes. JF 0.1400, with OR/NV/ID/CA shaved by the
  county share Jefferson takes. Measured: **JF 188** · CA 186 · FL 166 · TX 113 · NY 82.
  One class is noisy enough to reorder the top two — average several before retuning.
- **Jefferson DEVELOPS and DRAWS (owner rule 2027-08), like TX/CA/FL.** Two separate
  levers: the origin weight above (produce), and `CONF_TIER["JVC"] = "major"` (draw) —
  which funds its ten JVC programs at 12–13, past the 10.5 floor for a 5★. Don't demote
  the JVC back to `mid`. Jefferson's GEOGRAPHY is otherwise ordinary: it is region "W"
  and gets no special pull table. Out-of-region signees are fine and expected; the
  regional preference is soft realism, not a gate.
- **JF is NOT in `SCHOOL_LOCAL_TERRITORY`** (it has a real `STATE_REGION`, so the normal
  geo tug already applies; adding it stacks `LOCAL_TERRITORY_PULL` 6.0 on top), **NOT in
  `WARM_STATES`** (it's the PNW), and **NOT in `cities._STATE_HEAT`** (its list is already
  population-repeated; heat would multiply an existing weighting).
- **‼️ A FLAGSHIP IS NEVER SUBSUMED (owner rule 2027-08).** Galena University was once
  written as a rename of **Nevada** — Galena County IS Washoe County, so absorbing UNR
  looked tidy. It was WRONG and was reverted; do not redo it. Jefferson may take the
  ground and the regional publics, but a real flagship keeps existing. Galena is net-new,
  badge-marked, and sits BESIDE Nevada in the MW.
- 39 colleges across D1–D4 (~2.2/million, matching CA). Several were ABSORBED — real
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
  in real life. Chosen over renaming Pac-16→Pac-18, whose abbr is a key in `CONF_PRESTIGE`,
  `CONF_TIER`, `state.py::_P5` and `polls.py::_POWER_CONFS`. Gonzaga is in the **Pac-16**,
  not the WCC — check the data before reasoning about it.

## Other notes
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
