# AAR — new save inherits the prior save's cups & pro leagues (stale players)

**Date:** 2026-07-25
**Scope:** `world.reset()` (+ new `gtt_seasonmode.reset()`); regression test
`tests/test_new_save_reset.py`.

## Problem
Starting a new save ("Start new league" → `world.start_new` → `world.reset`) did
**not** restart two off-season / cross-system surfaces: the **Davis Cup / BJK Cup**
(International events) and the **GTT pro tour** ("pro games"). Both came up populated
with the PREVIOUS save's players. WTT-style saves could be deleted to force a
restart, but the international events had no removal path, so they just showed stale
squads.

## Root cause
`world.reset()` wiped the college-world tables (`world_roster`, `world_signing`,
`world_graduates`, `world_pro`, `world_portal_move`, `world_crossmatch`, `world`),
plus `world_championship`, seasons/duals, honors, coaches, overrides — but missed:

1. **`world_cups`** (the national-team snapshots). It's keyed by `world_id`. The
   `world` table's `id` is a plain `INTEGER PRIMARY KEY`, so after the reset drops
   the world row, `get_or_create()` re-inserts and **SQLite reuses `world_id=1`**.
   The leftover cup rows then match the new world → `latest_world_cup()` served the
   prior save's squads. (Exactly the same rowid-reuse trap that `world_championship`
   was already deleted to avoid — cups were simply never added to that cleanup.)
2. **The `gtt_*` tables** (leagues, franchises, players, duals, seasons,
   transactions, Hall of Fame). `reset()` never touched them at all. GTT leagues
   bind to the active world's **seed** (always `2026`), and `list_leagues()` returns
   every league regardless of world — so old pro leagues persisted into the new save
   with their now-stale pros.

## Fix
- `world.reset()` now also `executescript("DELETE FROM world_championship; DELETE
  FROM world_cups;")` and calls a new **`gtt_seasonmode.reset()`** that wipes every
  `gtt_*` table and clears the in-memory `_str_cache` (whose `(league_id, …)` keys
  would otherwise collide with a fresh league that reuses a `gtt_leagues` rowid).
- The GTT wipe is deliberate: the pro tour is a *continuation* of the college world
  (its founders are the save's graduates; leagues bind to the world seed), so a new
  world orphans the old leagues.

## Verification
`tests/test_new_save_reset.py` seeds a prior save (a `world_cups` row + a GTT
league), asserts both are readable, runs `world.reset()`, then asserts the cup and
the leagues are gone — and that a re-inserted world **reuses the same `world_id`**
yet finds no stale cup under it (the crux of the bug).

## Notes / general pattern
Any store keyed by `world_id` **or** by the world seed must be cleared by
`world.reset()` — rowid reuse (`world_id=1`) means "keyed by the deleted world" is
NOT self-cleaning. When adding a new cross-save table, wire its wipe into
`world.reset()` in the same commit. (Still un-wiped and out of scope here:
`seasonmode.injuries`, keyed by a reused `season_id` — non-deterministic and
re-rolled, so low-impact, but the same class of latent issue.)
