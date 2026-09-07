# AAR — JHSAA navigation no longer waits for the college world prime

**Date:** 2026-09-07  
**Status:** Implemented

## Report

After restoring an older database, opening High School from the main Juniors menu
produced a very long loading poll. The JHSAA front page, its menus, and program
pages appeared inaccessible while the poll continued.

## Root cause

The global `_prime_world` before-request hook treated every application route as a
consumer of the college developed-roster cache. A restored or newly selected save
has a cold process cache, so the first `/jhsaa*` request started the roughly 170 MB
college-world prime and returned the warming shell. That shell polls readiness and
does not render any JHSAA navigation or program content.

This dependency was unnecessary. The JHSAA route/view family reads its own archive,
school data, and high-school roster builders; it does not call the college
`state.get_season` path or consume the college world roster cache. Existing route
tests already had to fake college warmth for exactly this reason.

## Fix

`_prime_world` now returns immediately for the complete `/jhsaa` route namespace,
before checking college cache warmth. The existing health/readiness/static bypass,
the salt-keyed cold loader for college pages, and the broader JHSAA Lab bypass are
unchanged. College pages still warm and validate the cache exactly as before.

A rendered-route regression test creates the cold-save condition (`exists=True`,
`is_primed=False`) and makes `prime()` fail if called. It then requests `/jhsaa` and
asserts that the real JHSAA front page—not the warming shell—is returned.

## Deliberately not changed

- No database or save-selection behavior changed. The boot log remains the source
  of truth for which database was opened.
- No JHSAA ingestion, scoping, seeding, bracket generation, or archiving function
  changed; the fix only removes an unrelated college-cache gate.
- The boot-time best-effort cache warmer remains intact. It can still prepare both
  college and JHSAA search caches in the background without controlling whether a
  JHSAA route may render.

## Trap

Do not replace this route-namespace bypass with a list of JHSAA endpoints. There are
dozens of program, player, history, tournament, and editor routes, and a typed list
will silently send the next new high-school page back through the college loader.
