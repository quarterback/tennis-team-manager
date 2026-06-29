# AAR: boot-time cache warm (stop the crash-on-reload loop)

**Date:** 2026-06-29
**Scope:** `world.warm_caches` (new); `web/server.create_app` (boot daemon thread).

## The problem

Production (Fly) runs **one** gunicorn worker with threads (`Procfile`,
`wsgi.py`), on purpose: the season/roster/recruit caches live in process memory,
so a single shared process keeps them warm and coherent. The cost of that choice
is that any CPU-bound build holds the GIL and blocks every other request, because
threads do not parallelize pure-Python work.

The two expensive builds are:
- `world.prime` (the as-of-now roster cache, about 170 MB), and
- the junior circuit that enriches each gender's recruit board (`board_class`),
  measured at about 7.7s per gender, roughly 15s for both serial / 8s parallel.

Both ran **on the first request** (`@app.before_request _prime_world` calls
`prime`; the recruit board built lazily on first view). So after a cold start or
a Fly machine recycle, the first reload paid 15 to 80s AND held the worker's GIL
the whole time. That starved `/api/health`, Fly marked the machine unhealthy and
recycled it mid-build, and the next load started cold again: the crash-on-reload
loop the user reported. Memory was never the constraint (peak RSS about 111 MB on
a 4 GB machine), so a bigger machine does not fix it; more workers would (a worker
not building can answer health), but the in-process caches are invalidated with a
process-local `.clear()` (`state._season_cache` et al.), so multiple workers would
serve incoherent, flip-flopping save state. The fix is to keep one worker and move
the build off its GIL and off the request path.

## What changed

`create_app` now starts a **daemon thread at boot** that calls a new
`world.warm_caches()`, which builds:
1. the roster cache (`prime`), and
2. every active gender's enriched recruit board.

So the heavy build happens once during startup, with no user traffic yet, instead
of on a user's first reload.

```python
# web/server.py, right after db.bootstrap()
if "pytest" not in sys.modules and not os.environ.get("PTC_NO_BOOT_WARM"):
    threading.Thread(target=lambda: _try(wd.warm_caches), name="ptc-cache-warm",
                     daemon=True).start()
```

```python
# world.py
def warm_caches(seed=DEFAULT_SEED):
    if not exists(seed): return
    salt = active_salt(seed); w = get_or_create(seed)
    prime(seed)                                # roster cache
    prime_recruit_classes(seed, w["year"])     # parallel recruit prime (multi-core fast path)
    grad_year = BASE_YEAR + w["year"] + 1
    for gc in unique active genders:
        board_class(gc, grad_year, salt)       # ensure built even on the serial path
```

Why both `prime_recruit_classes` AND the `board_class` loop: `prime_recruit_classes`
is a parallel primer that **deliberately no-ops** when it cannot parallelize (fewer
than 2 genders or 2 cores, or `GEN_WORKERS=1`). On those configs it would leave the
class cache cold and the first request would still pay the build. The `board_class`
loop guarantees every active gender is built; it is a cache hit when the parallel
prime already did it.

This keeps the single-worker design (coherent caches) and removes the symptom:
- The roster prime is GIL-bound but runs during the health-check **grace window**
  (`fly.toml` `grace_period = 60s`), before traffic.
- The recruit prime offloads CPU to a **process pool** (`pmap`, spawn), so it does
  not hold the parent worker's GIL; the parent stays free to answer `/api/health`.

## Verified

- `create_app()` returns in **0.14s** (warm runs in the background, never blocks
  startup or the first health check).
- Warm fills both caches (`roster:True`, genders primed `['female','male']`).
  After warm, `GET /recruiting/hub` = **0.11s** and `GET /recruiting` = **0.22s**,
  versus 37 to 80s cold on the request path.
- Serial fallback works: with `GEN_WORKERS=1` (parallel prime no-ops) the
  `board_class` loop still warms both genders.
- Guards: under pytest the thread does **not** start (`"pytest" in sys.modules`);
  `warm_caches()` on an empty DB is a clean no-op; opt out with `PTC_NO_BOOT_WARM`.
- Peak RSS of the build is about 111 MB; this is not a memory fix and does not need
  a bigger machine.

## Gotchas for the next agent

- **Best-effort by design.** The thread swallows exceptions; the lazy request-path
  builds (`_prime_world`, `board_class` on first view) still cover anything the warm
  misses. Do not make a failed warm fatal to boot.
- **Spawn re-imports the worker's module, not `create_app`.** Under
  `gunicorn wsgi:app` the pool children import `app.world` to run `_build_board_class`
  and never re-run `create_app`, so the warm thread cannot recurse. It DOES recurse
  if you run the warm under a `python -c` / script with **no** `if __name__ ==
  "__main__"` guard (spawn re-executes `__main__`): that is a test-harness artifact,
  not a production bug. Test from a guarded module file with `PYTHONPATH` set.
- **`board_class` has no build lock.** If a request lands during the warm (before a
  class is cached) both can build the same class and contend on the GIL (seen as an
  ~80s request in a mid-warm test). In production the warm finishes inside the grace
  window before traffic, so the overlap is small; `prime` itself is still guarded by
  `_prime_lock`. If this ever bites, add a class-build lock rather than removing the
  warm.
- **Post-advance re-prime is still on the request path.** This change warms the
  *initial* (cold-start) build. Advancing the world clears caches and the next
  request rebuilds; that is a deliberate user action, not the cold-reload loop. If
  advance-time stalls become a problem, warm again after the rollover.
- Not started under `--preload` workers: the Procfile does not use `--preload`, so
  `create_app` runs in the worker process where the caches live. If `--preload` is
  ever added, move the warm to a `post_fork` hook so it runs per worker.
