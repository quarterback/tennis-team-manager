# AAR — Fall transfer portal (post-ITA talent reshuffle)

## Why

A freshly generated world scatters some D1-caliber players into lower divisions.
The only previous fix was the editor's manual move, which (a) is tedious and (b)
**wipes the player's history**: career history is stored as *one entry per
season-year* (`world._record_world_history`, idempotent on `year`), so moving a
player mid-season collapses the whole year to one school and erases the stint they
already played. The owner wanted a "fall portal" that, after the ITA opener,
proposes a talent reshuffle, lets them approve it, and — crucially — lets a mover
**keep both stints**: the ITA at the old school, the regular season + postseason at
the new one.

Owner decisions captured up front: **sim proposes, user approves**; **cascade-pool
balance** (a displaced player ripples down so no program loses a spot); **every
fall, all divisions** (D4 already runs an 8-team ITA Indoor, so it has a fall
season).

## What it does

After every universe finishes its ITA opener, the world holds at a new
**`fall_portal`** phase. The sim proposes a cross-division reshuffle; the user
reviews/approves on `/fall-portal`; committing relocates the movers for the rest of
the season and releases everyone to the regular season.

- **Riser selection is TALENT-based, not result-based.** The ITA is only a handful
  of duals — far too few to trust a results reliability gate. A riser must be a
  top-2 starter at their school AND clear a **higher division's typical (median)
  expected level** (`div_level`) — proof they belong a tier up, not merely that
  they're the best of a weak team. The ITA *record* is kept only to stamp the
  mover's ITA stint on their history.
- **Curated, not a migration.** Only the most mis-allocated move, capped per gender
  (`FALL_PORTAL_MAX_RISERS`, default 30). Each riser can trigger at most one cascade
  demotion. A first run on a fresh world proposes ~60 moves (30 up + 30 down), not
  thousands.
- **Risers spread, they don't funnel.** D1 rosters are full (cap 12), so risers
  *displace*; without a guard every riser would pick the single top blue-blood. A
  `received` set makes each receiving program take at most one riser, so the 30
  spread across the 30 best fitting programs.
- **Cascade-pool balance.** A displaced player fills an open seat, preferring the
  seat the riser just vacated (a clean swap-back), else the best open seat further
  down. Each player is displaced at most once (strictly-down hops bottom out at D4),
  guaranteeing termination. Invariant: **no program exceeds its cap**; the only
  shrinkage is terminal at D4, refilled by `refill_walkons` at rollover. (Strict
  global conservation is impossible under the D1 12 / D4 16 cap asymmetry.)
- **Deterministic**: seeded `random.Random(f"{seed}|fallportal|{year}|{gender}")`;
  the cascade itself is fully ordered.

## How it's wired

- **Phase** (`seasonmode.py`): `_finish_indoor` parks the season in `fall_portal`
  (behind `FALL_PORTAL_ENABLED`). Standalone, `advance` treats `fall_portal` as a
  transparent pass-through to `regular` (so single-season tests/fixtures don't
  deadlock). The WORLD driver instead **holds**: `world.advance_week` skips
  `fall_portal` universes so they all converge at the boundary.
- **Barrier** (`world.advance_week`): once every active universe is in
  `fall_portal`, generate proposals (`run_fall_portal`) and return
  `fall_portal_pending` without advancing. An empty slate releases immediately.
- **Relocation reuses the editor move override**: commit calls
  `overrides.set_move(pid, dest)`; `ncaa.build_roster` honors it each week, so the
  mover plays the regular season at the new school while their already-played ITA
  duals stay frozen in the source universe's `duals` table.
- **Two-stint history**: an explicit `stint` key on history entries. Commit freezes
  the ITA stint (stint 0, old school) into `world_roster` JSON; year-end
  `_record_world_history` appends the destination stint (stint 1, new school) — its
  idempotency is now keyed on `(year, stint)`. Every year-only sort learned a
  `(year, stint)` secondary key (`_career_transfers`, `transfer_portal_view`,
  `player_career_table`). A two-stint season is ONE school change, so the year-end
  auto `transfer_portal` correctly treats the mover as already-moved
  (one-move-per-career).
- **Rollover bake** (`_finalize_year` → `_bake_fall_moves`): after history is
  recorded, the committed moves are made permanent — the Prospect is relocated
  src→dest in the roster dict, the move override is cleared, and the year's portal
  rows are dropped. Without this the override would re-relocate every season and
  `finalize_rollover` would run on the wrong (source) roster.
- **Persistence**: a `fall_portal` table in `overrides.py` holds proposals
  (proposed → approved → committed) with the snapshotted ITA W/L/line.
- **UI**: `/fall-portal` (review/approve/commit) + `fall_portal.html`; the World Hub
  stage stepper, dashboard badge, and `_PH`/`_ORD` maps learned the new phase
  (`_PH[p]` is a hard lookup — an unknown phase 500s the dashboard).

## Gotchas burned in during the build

- `sm.player_primary_lines` returns a **string label** (`'S6'`), not an int —
  `ita_line` is TEXT.
- `commit_fall_portal` must stamp all ITA stints on one connection and commit/close
  it BEFORE the per-row override writes, or SQLite deadlocks (held write lock vs. a
  second connection).
- Detecting risers by ITA-result reliability yields an **empty** portal on a fresh
  world (too few duals); detecting by raw ability with only a `level + 0.8` bar
  yields **thousands**. The fix is the higher-division median-level bar + the cap.

## Tuning knobs

`world.FALL_PORTAL_MAX_RISERS` (per-gender cap), `world.UP_THRESHOLD`, and the
`div_level` median bar. `seasonmode.FALL_PORTAL_ENABLED = False` restores the old
`ita_indoor → regular` flow.

## User-editable slate — intents → resolve (IMPLEMENTED)

`/fall-portal` is not just approve/reject — the owner gets three first-class actions
during the hold:
1. **Redirect a rider** to a different destination than the suggestion box picked
   (an editable destination cell → `POST /fall-portal/redirect`).
2. **Add a mover** the sim didn't propose (player-name box + optional destination →
   `POST /fall-portal/add`; name resolves via `state.search_players`).
3. **Drop / keep** a rider (`POST /fall-portal/approve`, status `rejected`/`proposed`).

### Architecture: intents → resolve
The `fall_portal` table stores only **rider intents** (one row per riser:
pid, src, chosen `dest_school`, status). Cascades are NOT stored — they're DERIVED:
- `world._FPPlanner` holds one gender's snapshot + the cascade engine (`place`,
  `settle`, `discover`). `place(p, src, dest=None)` auto-picks the highest fit; with
  an explicit `dest` it honors a redirect/add. A full destination displaces its
  weakest, who cascades down.
- `world.resolve_fall_portal(seed)` rebuilds a FRESH `developed_rosters` snapshot and
  replays every non-rejected rider intent (str desc, pid) through `place`, producing
  the full slate (riders + cascades). Called on every view and at commit, so any edit
  recomputes a correct, cap-safe cascade against all other locked-in choices.
- `run_fall_portal` stores the sim's discovered riders as intents; `commit_fall_portal`
  resolves, stamps each mover's ITA stint, writes a committed row for EVERY move
  (riders + cascades, so the year-end two-stint history + bake cover the cascade),
  `set_move`s them, and releases the hold.
- `add_fall_portal_mover` / `redirect_fall_portal_mover` mutate intents (bypassing the
  discovery gates for the user's pick; displaced players still respect them).

### Gotchas burned in here
- **`_FPPlanner` must shallow-copy each roster list.** `developed_rosters` is a shared
  cache; the planner relocates players by mutating lists, so without the copy every
  resolve corrupts the cache and movers' `src_school` drifts to wherever a prior pass
  placed them (their ITA stint then records the wrong school).
- ITA stint (`ita_w/l/line`) is read from the SOURCE universe at commit via
  `_ita_lookup` — the hold sits at the post-ITA boundary, so those ARE the ITA results.
- `FALL_PORTAL_MAX_RISERS` caps only the auto discovery pass; user-added riders are
  intentional and don't count against it.

### Editor-window two-stint (IMPLEMENTED)
`/editor/move` checks the world: while it's holding in `fall_portal`, a move is routed
through `add_fall_portal_mover` (queued as a portal add, landing when you commit the
portal) instead of a bare `overrides.set_move`, so an in-window editor move earns the
ITA-stint freeze + cascade too. It redirects to `/fall-portal` so the queued move is
visible. Outside the window an editor move stays a plain single-school move (there's
no clean stint boundary to split on). If the portal slate hasn't been generated yet
(user hit the editor before visiting `/fall-portal`), the route runs the sim discovery
first so the user's add coexists with the sim's picks.
