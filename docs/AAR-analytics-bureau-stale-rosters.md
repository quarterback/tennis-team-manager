# AAR — Analytics Bureau linked to stale rosters; every player click 404'd

**Date:** 2026-06-19
**Scope:** In an advanced save (past Season 1), tapping a player on the Analytics
Bureau's **Underplaced Talent** board returned "Not Found." Reported as "I click
on these D3 female players in my active save and it triggers an error" — week 6,
all six universes active. Wire the Bureau to the same live rosters every other
surface reads, so its links resolve.

## Why
The board itself rendered fine — names, flags, teams, talent gaps all correct —
but the `/player/<pid>?u=D3-women` link behind each row 404'd. The symptom looked
D3/women-specific only because top D3 talent sits furthest above its (weak) team,
so D3 players dominate the underplaced board. The bug was not gender- or
division-specific: it hit any player who had moved since the cached snapshot.

The Bureau is an additive read layer: `scout_intel.scan(gender)` sweeps every
division for a gender, reading each program's `build_roster` to compare true
talent vs. team level. The player route resolves a clicked pid against the
**live** season roster (`seasonmode._pid_index` → `build_roster`) and
`abort(404)`s if it isn't there.

## Root cause
`scan()` read `build_roster` **without first priming the world**
(`app/scout_intel.py`). Priming (`world.prime(seed)`) is the hinge every live
surface uses (`state.get_season`) to load *this* world-year's actual rosters —
developed, graduated, transferred — into the shared `ncaa._roster_cache`. With no
prime, `scan` operated on whatever was already cached, which after a cache reset
falls back to the deterministic **year‑0 base roster** that `_base_roster`
regenerates on demand.

In Season 1 that's invisible (base == live, same pids). After a rollover the live
roster diverges — seniors graduate out, recruits arrive with new pids, transfers
move between programs — but `scan` kept emitting the **base** pids. Every link
then pointed at a player the live route couldn't find.

The trigger is a cache **asymmetry**, which is why it was intermittent ("it does
it once and never again"): another surface (dashboard/teams) primes the world and
builds a *live* `_pid_index`; a later week-advance calls `reset_caches()` and
clears `_roster_cache`; a web worker then hits the Bureau with the roster cache
empty but a live pid index still resolving clicks — so `scan` reads base while the
route reads live.

Reproduced directly against a world rolled to year 1 (one active universe for
speed), recreating that asymmetric cache state:

| `scan` reads | bureau D1-women links unresolved by the live route |
|--------------|----------------------------------------------------|
| base roster (no prime) | **826 / 3136** → 404 |
| live roster (prime first) | **0** |

## Fix
Prime the world at the top of `scan()`, before any `build_roster`, exactly as
`state.get_season` does:

```python
import app.world as world
if world.exists(seed):
    world.prime(seed)
```

`prime` also clears `seasonmode._pid_idx_cache`, so the player route rebuilds its
index from the **same** primed rosters — board and route are now guaranteed
consistent. `scan` is still memoised per `(world_id, year, week, gender)` and
`prime` is itself memoised per `(id, year, week)`, so the added call is free on
warm caches.

Dormant universes (single-gender / partial-division saves) stay correct: `prime`
materialises only active universes, and both `scan` and `_pid_index` then read the
same carried-forward base roster for a dormant universe — so those links resolve
too (verified separately).

## Tests
`tests/test_intel_bureau_live.py::test_bureau_player_links_resolve_after_rollover`
— plays one universe through a full year, recreates the prime-then-reset cache
asymmetry, then asserts every pid the Bureau links to resolves via the live player
route. Fails against the old code (826/3136 links 404); passes now. World /
season / web / seasonmode suites green.

## Files touched
- `app/scout_intel.py` — `scan()`: prime the world before reading rosters; comment
  explaining the stale-base-roster hazard.
- `tests/test_intel_bureau_live.py` — regression test above.

## Not touched (and why)
- `scout_intel` reports (`underplaced_board`, `fit_targets`, `scholarship_watch`,
  `playing_time_watch`) — all read through `scan`, so they inherit the fix; no
  per-report change needed.
- The player route's lookup order — left as-is. Once `scan` is live-consistent the
  pid always exists in the current season, so no cross-division fallback is
  required. (A defensive fallback to `world.find_persisted_player` could mask
  future staleness regressions and was deliberately avoided.)
- `_world_stamp`-based scan memoisation — already keyed by year+week, so it
  refreshes correctly once the underlying rosters are live.
