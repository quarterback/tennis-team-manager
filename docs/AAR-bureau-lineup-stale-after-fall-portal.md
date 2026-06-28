# AAR — Analytics Bureau & Lineup Lab stale after the fall portal (week-only cache stamp)

**Date:** 2026-06-28
**Scope:** Reported: *"the Bureau and these views in the Analytics Bureau do not
refresh after the ITA portal runs… which means Lineup Lab isn't updating weekly
either."* After the fall transfer portal committed, the Bureau boards (Underplaced
Talent, Buried Talent, Scholarship Watch) and the Lineup Lab kept showing the
**pre-transfer** rosters. Branch `claude/tennis-sim-engine-tests-tpbdfx` (PR #119).

## Why
Every Bureau surface and the Lineup Lab read through one function,
`scout_intel.scan(gender, seed)`, which is memoised per **world snapshot**:

```
key = (_world_stamp(seed), gender)        # _world_stamp = (world_id, year, week)
```

`world.prime()` (the one-world hinge that loads live rosters into the shared
`ncaa._roster_cache`) used the **same** `(id, year, week)` stamp.

The fall-portal commit (`world.commit_fall_portal`) applies each transfer with
`ov.set_move(...)`, then flips every held universe from the per-season
`fall_portal` phase to `regular`. Crucially it does **not** advance the world
week — the world sits at, e.g., Week 5 both before and after. So:

- `_world_stamp` returned the identical tuple → `scan` served its cached,
  pre-transfer snapshot and never even re-primed.
- The phase that *did* change lives per-season, not on the `world` row, so a
  world-level stamp could never see it.

`commit_fall_portal` already did `reset_caches(); _primed.pop(seed)`, so a *fresh*
prime would have rebuilt correctly — but `scan` short-circuited on its own
`_scan_cache` before reaching prime. The "Lineup Lab isn't updating weekly" half
was the same root cause observed from the other side: the lab is just another
`scan` consumer, so it inherited the stale snapshot.

## Root cause
A **week-only cache stamp** can't represent a roster change that doesn't move the
week — a fall-portal commit (and, generally, any mid-season editor move) mutates
rosters at a fixed week. The stamp needs to be sensitive to roster *mutations*,
not just the calendar.

## Fix
Add a cheap roster-override fingerprint and fold it into both stamps.

- `app/overrides.py::roster_version()` — md5 of the `move` + `lineup` rows of
  `roster_overrides` (ordered). Changes the instant a transfer or pinned lineup
  lands, including each `set_move` in the fall-portal commit. Prestige/academic
  overrides are excluded — they only shift at the year rollover, which already
  bumps `year`. The table is tiny (≈a few hundred rows after a portal), so hashing
  it per call is negligible next to the scan/prime it guards.
- `app/scout_intel.py::_world_stamp` → `(id, year, week, roster_version())`. The
  scan now invalidates the moment the portal commits — no week tick required.
- `app/world.py::prime` stamp → same 4-tuple, so the underlying live rosters +
  pid index also rebuild on a roster mutation (keeps prime and scan reading the
  same rosters, and makes mid-season editor moves reflect immediately too).

`_dev_cache` (developed rosters, `world.py:543`) was deliberately left keyed on
`(id, year, week)`: development is move-independent, and `build_roster` applies
moves *downstream*, so folding the override fingerprint in there would only force
needless recomputation.

## What this does and doesn't change weekly
The Bureau reads **true talent** (ceiling) and the Lineup Lab reads **current
ability** STR — neither is a results rating, so they change on roster events
(transfers, the rollover's development/graduation, injuries pulling depth up), not
on every match result. The fix guarantees the views are never *stale* — they
refresh the instant rosters actually change and on every week tick — but the
numbers won't drift week to week absent such an event. (If we later want the
Lineup Lab to track the **results-based** STR that evolves with match play, that's
a separate change to what `scan` emits, not a caching fix.)

## Tests
`tests/test_intel_bureau_live.py::test_bureau_and_lineup_lab_refresh_after_transfer_same_week`
— scans women, applies one `set_move` (as the portal does) **without advancing the
week or clearing any cache**, and asserts the Bureau (`by_pid`) and the Lineup Lab
(`conference_lineups`) both show the player at the new school. Fails against the
old week-only stamp; passes now. The existing
`test_bureau_player_links_resolve_after_rollover` still passes. World / seasonmode
/ web-season / overrides suites green.

## Files touched
- `app/overrides.py` — `roster_version()` fingerprint.
- `app/scout_intel.py` — `_world_stamp` folds in `roster_version()`.
- `app/world.py` — `prime` stamp folds in `roster_version()`; comment fixes.
- `tests/test_intel_bureau_live.py` — regression test above.

## Not touched (and why)
- `commit_fall_portal` — left as-is. It already clears world caches; the stamp
  change is what `scan` needed, and doing it in the stamp (not an explicit
  `_scan_cache.clear()` at the call site) also covers editor moves and can't be
  forgotten at a new mutation site.
- The Lineup Lab's use of ability STR — unchanged; see "weekly" note above.
