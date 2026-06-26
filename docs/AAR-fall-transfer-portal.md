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

## Future work — make the slate user-editable (FOR THE NEXT AGENT)

Today `/fall-portal` only lets the owner **approve/reject** the sim's proposed slate.
The owner wants three more first-class actions during the hold:
1. **Redirect a riser** to a different destination than the suggestion box picked —
   the owner's words: "what if I want them to go to a school different than the one
   the suggestion box picks." This is the priority one.
2. **Add a mover** the sim didn't propose ("I see someone else I want moved").
3. Have **manual editor moves made during the fall window** get the same two-stint
   history + cascade balance, instead of collapsing the season to one school the way
   a normal editor move does.

All three are the same problem: a user-chosen move must flow through the SAME pipeline
as a sim proposal so it inherits the cascade balance + the ITA-stint freeze for free.

### Recommended design: intents → resolve
The `fall_portal` table currently stores a STATIC resolved slate (riders + their
cascade demotions as sibling rows). That's awkward to edit, because changing one
rider's destination invalidates its cascade child. Refactor to two layers:
- **Intents** (what the user wants): per rider, `pid → {dest: school | 'auto', status}`.
  Approve / reject / add / redirect all just mutate intents.
- **Resolve** (`world.resolve_fall_portal(seed)`): build the `developed_rosters`
  snapshot + the `fall_portal_proposals` indexing, then apply each *approved* intent
  in a deterministic order (str desc, pid) — explicit `dest` if set, else
  `highest_fit` — running the existing `place_riser`/`settle` cascade against the
  RUNNING snapshot so seats and caps stay correct across the whole slate. The output
  (riders + cascades) is the resolved set the page renders and `commit_fall_portal`
  applies. Re-resolve from a FRESH snapshot on every edit.

This makes redirect/add/remove correct by construction: the cascade is always
recomputed against every other locked-in choice, so a redirect that frees the old
destination's displaced player and creates a new displacement at the new one just
falls out of re-resolving.

### Wiring
- **Redirect**: `POST /fall-portal/redirect (pid, dest)` → set that intent's dest →
  re-resolve. The destination cell on `/fall-portal` becomes a program picker (offer
  programs where the player would make the lineup first, but allow any same-gender
  program — it's god-mode). `commit_fall_portal` already does `set_move` to whatever
  `dest_school` the row holds, so honoring a redirected dest is automatic once the
  resolved row carries it.
- **Add**: `POST /fall-portal/add (pid, dest='auto'|school)` → add an approved intent
  → re-resolve. UI: a player search (reuse `state.search_players`) + optional dest.
  **Bypass the discovery GATES** (top-2, median-level, `_career_transfers`) for a
  user pick — those gates exist only for *auto* discovery — but the players the pick
  DISPLACES should still respect them.
- **Editor-window two-stint**: in the `/editor/move` route (`server.py` ~1217), if the
  world is currently holding in `fall_portal`, route the move through the add path
  (add an intent + re-resolve) instead of a bare `overrides.set_move`. That one hook
  gives in-window editor moves the ITA-stint freeze + cascade automatically — i.e.
  "can I just move someone myself" becomes yes, treated like a portal add. Outside the
  window an editor move stays a plain single-school move (no clean stint boundary).

### Gotchas
- Snapshot the ITA stint (`ita_w/l/line`) from the SOURCE universe at resolve/commit
  time — the season is held at the post-ITA boundary, so `sm.player_records` /
  `player_primary_lines` ARE the ITA results.
- Re-resolve must start from a fresh `developed_rosters` snapshot each time, or
  repeated edits double-apply moves.
- A redirect into a FULL program must still displace + cascade; into an open seat,
  straight promotion. `place_riser` already does both — reuse it, don't fork it.
- Keep the per-gender `FALL_PORTAL_MAX_RISERS` cap on the *auto* discovery pass only;
  user-added riders are intentional and shouldn't count against it.
