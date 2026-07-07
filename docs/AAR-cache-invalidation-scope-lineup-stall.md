# AAR — a one-team lineup edit rebuilt the whole world (cache-invalidation SCOPE)

**Date:** 2026-07-07
**Status:** FIXED (profiled + verified). Root cause below; the two-part fix and its
measurements are in "The fix" section.
**Scope:** `ncaa.build_roster` (per-program gate), `ncaa.reset_effective` (new),
`web.state.reset_lineup` (new), and the `my_program_lineup` / `my_program_doubles`
/ `editor_lineup` / `editor_clear_lineup` / `editor_doubles` routes.

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

## The fix (implemented, profiled, verified)

1. **Per-program override gate in `build_roster`.** Replaced the global
   `any_overrides()` check with "is THIS program affected?" — `p.school in
   get_lineups()`, or a base-roster pid in `get_moves()`, or a move destined here.
   Unaffected programs return `_base_roster(p)` untouched. Provably equivalent: the
   heavy path's tail (sort by `current_overall` + `allocate_scholarships`) is
   exactly what `_base_roster` already produced.
2. **Scoped `reset_lineup()` (→ `ncaa.reset_effective()`) on the lineup/doubles
   routes.** Clears only the effective layer (`_eff_cache`, `_squad_cache`) and the
   staff board; the base roster cache, seasonmode caches, and world prime survive.
   The pin re-applies via `build_roster` (cheap off the intact base) and the live
   `coach_lineup` read. MOVE edits still use the full `reset_all()` (they change
   composition).

**Measured** (full-world `build_roster` sweep, 2,214 programs):

| | before | after |
|---|---|---|
| warm sweep, no override | 0.49s | 0.49s |
| warm sweep, ONE lineup pin present | **2.31s** | **1.10s** |
| next-page sweep after a pin (scoped reset) | (+ base regen risk) | **1.14s** |

Verified on a warm world: the pinned team reflects the new order, other teams are
byte-unchanged, the base roster cache is preserved (not wiped), and the live pin
is readable by `coach_lineup`. Override/roster/season test suites pass.

## ‼️ IT RESURFACED — a SECOND re-prime path the first fix missed (`world.prime` stamp)

**Date:** 2026-07-07 (same day, later). **Symptom:** the owner set a My-Program
singles lineup to **replace an injured starter**, and the site stalled again —
`gunicorn ... TimeoutError: [Errno 110] Connection timed out` on `sock.sendall`
(the write-timeout signature of a request-thread stall, exactly as in
`AAR-perf-regression...` §2b). "Custom roster change doing this again."

### Root cause — the fix above scoped the CACHE reset but not the PRIME STAMP

The first fix made the lineup routes call the scoped `reset_lineup()` instead of
`reset_all()`, and gated `build_roster` per-program. But it left a **second,
independent invalidation** untouched: `world.prime()` stamps its ~170MB
developed-roster cache on `ov.roster_version()`, and **`roster_version()` folds in
`lineup` and `doubles` rows**. So saving a lineup pin still bumped the prime stamp:

- The *save* itself was cheap (scoped `reset_lineup()`), so the redirect looked fine.
- But the pin left `_primed`'s stamp **stale**. The **next** call to `prime()` — from
  any full-world page (Analytics Bureau / `scout_intel`, rankings, hub), the
  `advance_week` tick, or the **background world-warm thread** — saw the changed stamp
  and **re-primed the entire world** (`developed_rosters` → `reset_caches` → repopulate
  ~170MB) on that request's thread. One GIL-bound worker → `/api/health` starves →
  unhealthy → the render is slow enough that the client (or Fly's proxy) gives up →
  the worker's `sendall` to the dead socket eventually `ETIMEDOUT` (errno 110).

A lineup/doubles pin **never changes the developed roster SET** `prime()` caches — it
only reorders who plays S1–S6, and that order is applied **live downstream** in
`build_roster` / `season.coach_lineup`. Folding pins into the prime stamp was the same
"invalidation scope > edit scope" mistake as the original, one layer deeper.

### The fix

New `overrides.move_version()` — a fingerprint of **only `move` rows** (the sole
composition change; editor moves and the fall-portal / preseason-portal commits all
land as `ov.set_move`). `world.prime()` and `is_primed()` now stamp on
`move_version()`, so a lineup/doubles pin leaves the world **warm** (no re-prime).
`roster_version()` (move+lineup+doubles) is unchanged and still used by
`scout_intel._world_stamp` — the Bureau *projects duals* and so must honor a pinned
order, and its recompute reads the now-still-warm primed rosters (cheap), not a full
regen. Verified: after `set_lineup` / `set_doubles`, `is_primed()` stays **True**;
after `set_move` it flips **False**. Regression test:
`test_overrides.test_move_version_ignores_lineup_and_doubles_pins`.

> ⚠️ **A cache has as many invalidation edges as it has stamps.** Fixing the
> `reset_*()` edge is not enough if a *version stamp* keyed on the same table also
> triggers the rebuild. When you narrow one invalidation path, grep every place the
> edited table (`roster_overrides`) feeds a cache key — here `roster_version()` in the
> prime stamp AND the scout stamp — and confirm each one's scope matches the edit.
> `grep -rn "roster_version\|move_version" app/`.

## Takeaways

1. Match invalidation scope to edit scope; a narrow edit that triggers a global
   `reset_*()` is the smell.
2. Don't gate expensive per-entity work on a global "any edits?" boolean.
3. On a single GIL-bound worker, an unbounded rebuild on the request path is an
   availability incident — treat it like one.
4. For tiny override rows, live reads beat cache+broad-invalidate.
5. A cache is invalidated by *both* its `reset_*()` calls *and* its version stamp.
   Fix the whole class in one pass: when you scope one edge, audit every stamp keyed
   on the same edited table (the lineup pin had TWO edges; the first fix closed one).
