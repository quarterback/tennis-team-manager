# AAR — One world per save: the seed-matching failure (GTT + World Cups)

**Date:** 2027-07-17
**Scope:** `web/state.get_world_cup` (roster scan seed), `gtt_seasonmode.
_active_world_seed` + off-season self-heal, GTT New-league form (Seed box
removed), `scripts/cleanup_stray_worlds.py`, CLAUDE.md guardrail section.
**Severity:** save corruption + two features silently running on fake data.
**Found by:** the OWNER — recognizing that World Cup squads contained players
who don't exist in their game. No agent caught it; every automated check passed.

## What the player saw

- The World Cups page full of realistic-looking players connected to nothing
  in the save.
- The GTT pro league never pulling college players — "two self-contained
  systems" — even after the graduate-pipeline and takeover fixes.

## Root causes (two bugs, one disease)

1. **The live `/world-cups` view scanned rosters with the DERIVED year seed**
   (`year_seed = base + 1000×year`) instead of the base world seed.
   `scan_rosters → prime → get_or_create` found no world at that seed and
   **built a parallel universe** — generated fake players AND wrote a stray
   world row into the save.
2. **GTT resolved its college world by seed-matching.** The league stored
   whatever number was typed into the form's "Seed" box (a year, naturally);
   when no world matched, the fallback took the **newest** world row — after
   bug #1, the stray — so the graduate lookup found nothing and rosters filled
   with synthetics forever.

**The disease:** a save has exactly ONE real world (`start_new` resets before
creating; the salt provides freshness), yet multiple systems tried to *find*
it by matching numbers, with graceful fallbacks when the match failed.

## Why no agent caught it (recorded so the pattern is recognized)

- **Fixture-shaped verification.** Every repro built its own temp DB satisfying
  the code's assumptions (one world, default seed) — under which the code
  genuinely works. A test written by the author inherits the author's
  assumptions; it cannot catch the assumption being wrong. The failing
  condition (a second world row + a dead stored seed) existed only in the
  real save, which no check ever looked at.
- **Three meanings of "seed", one type.** Base world seed, derived year seed,
  and per-dual RNG seeds are all plain ints named `seed`. `current_year_seed()`
  is correct for season-mode calls and catastrophically wrong for
  `prime()`/`scan_rosters()`.
- **Silent graceful degradation at every layer.** Dead seed → fallback row.
  Missing world → `get_or_create` builds one. Each layer turned a should-be
  crash into plausible-looking wrong data — and generated players have
  realistic names, schools, and flags, so wrong data passes visual inspection
  by anyone but the owner.

## The fix (all landed)

- `get_world_cup` scans rosters with the **base** seed; the year seed only
  drives the draw RNG.
- `gtt._active_world_seed` binds to the **oldest** world row (the real one);
  `preferred` honored only when that exact world exists.
- The GTT off-season **self-heals** a dangling `world_seed` and persists it —
  existing broken leagues re-bind at their next "Start next season".
- The New-league **Seed box is removed**; leagues always bind to the active
  world. The dropdown's "(seed N)" label is gone.
- `scripts/cleanup_stray_worlds.py` (dry-run default, `--delete`) removes
  stray world rows precisely: a world whose seed equals another world's
  `seed + 1000×y` sits exactly where the bug wrote it.

## Invariants (locked — CLAUDE.md carries the short form)

1. **One world per save.** Bind to it; never seed-match, never `ORDER BY id
   DESC`, never trust a user-typed number to identify the world.
2. **`prime()`/`scan_rosters()` take the BASE world seed only.** They create
   what they can't find — a derived seed silently builds a parallel universe.
3. **No graceful fallbacks on world resolution.** Fail loudly. Wrong-but-
   plausible data (generated names) is strictly worse than a crash: a crash is
   found in minutes, fake data survives until the owner recognizes a name.
4. **Verify against the real save's shape, not just fixtures**: any test of
   cross-system linkage must include the hostile case — extra world rows, a
   dangling stored seed — because that is what real saves accumulate.
