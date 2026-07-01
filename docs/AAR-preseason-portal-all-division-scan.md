# AAR — Pre-season portal: scan ALL divisions, and the design intent behind it

## Design intent (owner)

The **pre-season portal** exists to correct world-generation mis-allocation **before the
season opens**: the over-talented players parked in lower divisions should be promoted UP
**immediately**, rather than waiting ~half a season for the fall transfer portal (after the
ITA opener) to rescue them. Rules of the road:

- **All four levels (D1–D4) are always active.** The owner plays the full pyramid; the
  portal must consider every level.
- **Walk-ons stay where they are.** A D1 bench walk-on chose D1 and "establishes they were
  D1 first" — the portal must not yank them down a level. Only genuinely under-placed
  *starters* at lower levels should rise.
- The value is speed: get the lower-level studs out **now**, at the outset.

## Symptom

On a full D1–D4 world the portal showed `0 rising · 0 cascading` / "No moves on the slate,"
while the Analytics Bureau's **Underplaced Talent** (873 players) and **Playing Time** (2,673
walk-ons) boards were overflowing with cross-division talent — including D4 schools
(Elizabethtown, Puget Sound, Carroll MT, George Fox).

## Root cause — two different roster sources

The boards and the portal read the world's talent through **different doors**:

- **`scout_intel.scan`** (Underplaced / Playing-Time) iterates **every** division via
  `ncaa.build_roster` — the whole universe, always.
- **`world.run_preseason_portal` / `resolve_preseason_portal`** sourced rosters from
  `developed_rosters(w)`, which is **restricted to the ACTIVE universes** (`_active_unis`).

So the portal was coupled to the active-division set in a way the boards are not. If a level
is ever not active, the portal silently can't see it — even though the boards still do — and
the most mis-allocated players become invisible to exactly the tool meant to move them.

## What was ruled out (so the next person doesn't re-chase these)

- **Not a stale/lagged persisted world.** Confirmed by repro: a freshly built world produces
  the documented **~60 moves** (30 riders + 30 cascades) per gender through the portal, both
  when D4 is active and when it isn't. The discovery/cascade algorithm is sound.
- **Not the analytics being a different (fresher) universe.** `prime()` loads
  `developed_rosters` into the same cache `scan` reads, so for active divisions the boards
  and the portal see identical rosters. The divergence is purely which *divisions* each
  enumerates.

## Fix

New **`world.scan_rosters(seed)`** — the portal's roster source, built the exact way the
Bureau boards are: `prime()` then `build_roster` for **every** division×gender in
`UNIVERSES`. `run_preseason_portal` (seeding) and `resolve_preseason_portal` (view/commit
cascades) now both call `scan_rosters` instead of `developed_rosters`, so the portal scans
exactly the universe the boards show — every level, decoupled from the active set.

Walk-ons remain excluded as risers (`discover` skips `p.walk_on`), matching the design
intent — a D1 walk-on is never promoted or pulled out of their level.

## Verify
```python
import app.world as world
world.run_preseason_portal()
res = world.resolve_preseason_portal()
# riders are drawn from across every level, including D4
assert any(m['src_div']=='D4' for m in res['women'] if m['cascade_from'] is None)
```
Tests: `test_preseason_portal`, `test_fall_portal`, `test_world*` all pass.

## Follow-ups shipped in the same pass

### Its own (larger, tunable) rider cap
Both portals called `discover(FALL_PORTAL_MAX_RISERS)` — the same **30**. That 30 is the
*fall* portal's deliberate mid-season curation ("~60 moves, not thousands"); the *pre-season*
portal is a **one-time generation fix** and 30 left ~800 qualifying studs stuck. The
pre-season portal now uses its own cap, **`worldconfig.preseason_portal_cap()` (default
250)**, tunable per save; the fall portal keeps its 30. At 250 the slate is 250 riders +
250 cascades per gender. Diagnostic on a fresh world: ~850 men / ~1090 women *qualify*, so
250 is a chosen middle ground, not a ceiling.

### UI: tuner, gender filter, pagination, re-scan
The slate now runs to hundreds of rows, so `/preseason-portal` got:
- **Cap tuner** — a "Max risers / gender" number input (`POST /preseason-portal/cap` →
  `set_preseason_portal_cap` + re-scan).
- **Gender tabs** — All / Men / Women with live counts (`?gender=`); the view no longer
  mixes both into one list.
- **Pagination** — 50 rows/page (`?page=`), Prev/Next.
- **Re-scan** — `POST /preseason-portal/rescan` clears the year's slate and re-runs
  discovery, recovering a "sticky" slate without a new league.
- **Empty-slate diagnostic** — `world.preseason_portal_debug()` shows, per gender, how many
  lower-division starters were scanned / are top-2 / clear a higher division / are riders,
  plus the per-division median bar, so an unexpected 0 is explainable.

Bug caught in review: the live-view loop `for gender, moves in resolved.items()` shadowed the
`gender` filter parameter, so pagination filtered by the last-iterated gender. Renamed the
loop var to `g`.

### Codex review: never promote INTO an inactive division
Feeding all divisions into `_FPPlanner` (the whole point — so a stud in a dormant level can
be rescued up) introduced a hazard for **subset-active** leagues: the planner could pick an
**inactive** higher-division school as a destination, and `commit_preseason_portal` would
record that override even though season simulation only iterates `_active_unis` — so the
mover would leave the playable season. Fix: `_FPPlanner` takes `active_divs`; **sources span
every division, but destinations (the `by_div` pool, the median bar, and `settle`'s
swap-back) are restricted to active divisions.** The pre-season paths pass
`worldconfig.active_divisions()`; the fall portal is unaffected (it already feeds only active
universes). Verified: with only D2+D3 active, D4 studs still rise into D2 and **no** move
lands in dormant D1/D4; with all four active (the intended setup), D2→D1 / D3→D1/D2 /
D4→D1/D2 promotions all happen normally.

## Still open

- **If the portal is still empty on an existing save with all four levels active**, the
  remaining suspect is a **"sticky" slate**: the route only scans when *no* proposals exist
  for the year, so a slate that was seeded/committed/dropped once stays empty and never
  re-scans. Fix (not yet built): an explicit **"Re-scan"** action to force a fresh scan
  without starting a new league.
- **First-advance as a roster-lock step** — the owner's idea to make the first "sim"
  simulate no matches, just set/persist rosters and hand the portal its turn, then move
  everyone, then start real play. A season-flow change; not attempted here.
- **D1 walk-on down-cascade** — `discover` never *promotes* a walk-on, but a riser landing
  on a full roster can still cascade that roster's weakest (possibly a walk-on) down a level.
  Tightening the cascade to spare established higher-division walk-ons is pending a decision.
