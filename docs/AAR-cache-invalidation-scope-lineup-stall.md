# AAR — a one-team lineup edit rebuilt the whole world (cache-invalidation SCOPE)

**Date:** 2026-07-07
**Status:** root cause traced from code + confirmed; the minimal fix is a scoped
follow-up (see "The fix should be" below — do it with profiling, not a guess).
**Scope of the lesson:** `web.state.reset_all`, `ncaa.build_roster` /
`ncaa.reset_caches`, `overrides.any_overrides` / `roster_version`, and the
`my_program_lineup` / `my_program_doubles` / `editor_lineup` routes.

## Symptom

Owner set a **non-conforming singles lineup** for one team (Monmouth women) via
the roster page's auto-sort + slot picker. ~immediately the live site went
**unhealthy for ~4 minutes** (Fly health check failed 16:37 → passed 16:41), with
`could not find a good candidate … no known healthy instances`. It self-recovered
(the always-on machine was NOT killed — that earlier fix held), no data loss.

## Root cause — the invalidation SCOPE didn't match the EDIT scope

A lineup pin reorders **one team's** singles ladder. Nothing else changes — not a
single player, rating, or another team. Yet saving it fired a **world-wide**
rebuild on the single GIL-bound worker:

1. **The route nukes everything.** `my_program_lineup` → `ov.set_lineup()` →
   `reset_all()`. `reset_all()` calls `ncaa.reset_caches()`, which clears the
   **base** roster caches (`_roster_cache`, `_eff_cache`, `_squad_cache`,
   `_index_cache`) plus every seasonmode + web display cache. A per-team batting
   order just invalidated the entire generated world.

2. **`build_roster` gates on a GLOBAL override flag.** `build_roster` returns the
   cheap `_base_roster(p)` only `if not ov.any_overrides()` — and `any_overrides()`
   is `SELECT COUNT(*) FROM roster_overrides > 0`, i.e. **global**. So the instant
   *one* lineup row exists anywhere, **every** program in **every** division takes
   the heavy override path (get_moves, get_lineups, build the global player index,
   deep-copy, re-sort, re-allocate scholarships) — forever, until all overrides are
   cleared.

3. **The next full-world page pays for it, on the request thread.** Any page that
   scans many programs (Analytics Bureau / `scout_intel`, rankings, hub, team
   pages) then regenerates thousands of rosters through that heavy path with the
   base cache cold. On ONE gunicorn worker, that pure-Python loop holds the GIL for
   minutes, so even the trivial `/api/health` can't get a response → Fly marks the
   instance unhealthy → route drops → "no known healthy instances." Health
   starvation, not a crash.

4. **Most of it was unnecessary for correctness.** The pin is read **live** at
   match time (`season.coach_lineup` → `ov.get_lineups()`), and `prime()` already
   folds `ov.roster_version()` (which includes `lineup`) into its stamp, so the
   world re-derives on the next tick anyway. The only thing that genuinely needed
   refreshing was the **one team's** `build_roster`/`_eff_cache` entry for display.
   `reset_all()` was a sledgehammer for a thumbtack.

## The design lessons (this is the part to internalize)

> ⚠️ **Invalidation scope must match edit scope.** A per-entity edit (one team's
> lineup, one player's move) must invalidate per-entity cache entries — never a
> global `cache.clear()` of the generated world. If you find yourself calling a
> broad `reset_*()` after a narrow edit, the blast radius is wrong.

> ⚠️ **Never gate an expensive path on a GLOBAL "any edits exist?" flag.**
> `build_roster`'s `if not any_overrides()` means one override taxes all ~4,000
> program builds. Gate per-entity: *does THIS program have a move in/out or a
> lineup pin?* If not, it is byte-identical to its base roster — return it cheaply.
> (`roster_version()` already reads the same tiny table; a per-school variant is
> the natural key.)

> ⚠️ **On this app a request-path rebuild IS an availability bug.** One gunicorn
> worker + the GIL means any multi-second CPU-bound rebuild on the request thread
> starves `/api/health` → the instance flaps unhealthy → the route drops. "Clear
> broadly to be safe" is the opposite of safe here. Rebuilds must be either scoped
> to a handful of entities, or moved off the request path (background warm, like
> `AAR-boot-cache-warm`). See also the sibling failure mode in
> `AAR-perf-regression-and-power-index-thread-race` (§2/§2b): under this worker,
> both *reading* caches unsafely and *rebuilding* them broadly take the site down.

> ⚠️ **Prefer a live read to cache-and-invalidate for tiny, cheap-to-read state.**
> A lineup is one small `roster_overrides` row read live at match time; it never
> needed to bake into the heavy generated-roster cache at all. Cache the expensive
> thing (the generated roster); read the cheap override live.

## The fix should be (scoped follow-up — profile first, don't guess)

1. **Per-program override gate in `build_roster`:** replace the global
   `any_overrides()` check with "is this program affected?" — `p.school in
   get_lineups()`, or a base-roster pid in `get_moves()`, or a move destined here.
   Unaffected programs return `_base_roster(p)` and never touch the heavy path.
   (Provably equivalent — safe.)
2. **A scoped `reset_lineup()` for the lineup/doubles routes** that clears only the
   effective/display layer (`_eff_cache`, `_squad_cache`) and NOT the base roster
   cache or the world prime — the pin propagates to the sim via the existing
   `roster_version()` stamp and the live `coach_lineup` read.

Both must be verified on a **primed** world: confirm the edited team's ladder
updates, other teams are untouched, the base cache survives, and a full-world
scan after a pin stays sub-second. The risk of a careless version is **stale
rosters that silently ignore the edit** — a worse bug than the stall, which is why
this AAR ships ahead of the change rather than bundled with a rushed one.

## Takeaways

1. Match invalidation scope to edit scope; a narrow edit that triggers a global
   `reset_*()` is the smell.
2. Don't gate expensive per-entity work on a global "any edits?" boolean.
3. On a single GIL-bound worker, an unbounded rebuild on the request path is an
   availability incident — treat it like one.
4. For tiny override rows, live reads beat cache+broad-invalidate.
