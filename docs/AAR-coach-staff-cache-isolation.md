# AAR — coach-staff cache stale across registry resets

## Problem
`test_web_coaches::test_coaches_have_stable_ids_and_pages` failed only in the full
suite (passed in isolation): `get_coach(head_id)` returned `None`. Surfaced while
landing the ITA opener but unrelated to it — an order-dependent test-isolation bug.

## Root cause
`state.coaching_staff()` caches a school's staff (including each coach's `coach_id`)
in a module-level `_staff_cache`, keyed by `(division, gender, school, year)`. Coach
ids are random uuids persisted in `coachreg`. When a test reset the world — the
`played_season` fixture calls `world.reset()` → `coachreg.reset()`, which wipes the
`coach`/`coach_seat` tables — the staff cache was **not** invalidated, so a later
`coaching_staff()` call served pre-reset ids that `coachreg.get()` no longer knew.
Because these are standalone (no-world) seasons, the world salt is `''` for everyone,
so keying the cache by salt alone didn't help.

Reproduced deterministically: populate the cache → `world.reset()` →
`get_coach(cached_id)` was `None`.

## Fix
Add a **generation counter** to `coachreg`, incremented on every `reset()`, and fold
`coachreg.generation()` into the `_staff_cache` key. A registry wipe now bumps the
generation, so cached staff is naturally invalidated and the next call regenerates
against the current registry. (The cache key also carries the world salt/year, which
remains correct for distinguishing worlds.)

## Verification
The deterministic repro now regenerates fresh ids and resolves after a reset; the
`test_web_awards` → `test_web_coaches` ordering passes.

## Notes
A general pattern: any module caching `coachreg` ids should key on
`coachreg.generation()` so a reset invalidates it without cross-layer cache-clearing.
