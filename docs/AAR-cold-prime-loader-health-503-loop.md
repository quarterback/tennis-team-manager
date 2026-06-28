# AAR — Instant loader + health that never blocks on a cold prime (the 503 loop)

**Date:** 2026-06-28
**Status:** ✅ Implemented. Branch `claude/tennis-sim-engine-tests-tpbdfx` (PR #119
lineage; rebased onto current `main`).
**Reported:** "the pre-load takes a minute or more… what I got now was a 503 — so
that's not a loading issue, something is crashing." Then: "I don't care if it takes
that long, I just want it to boot some empty state / pre-loader as soon as the URL
is reached."

## Why (root cause)
The app runs **one gunicorn worker** (threads, not processes — the season/roster
caches live in process memory). The `@app.before_request _prime_world` hook ran the
heavy `wd.prime()` — which materialises the whole world's rosters, a minute+ on a
cold machine — **before EVERY request, including `/api/health`.**

So on a cold machine the **health check itself** triggered the full prime, held the
GIL for a minute, and timed out. fly then marked the machine unhealthy and recycled
it → it came back cold → the next health check primed again → the documented
"slow + crashing on load" loop (see the comment already in `fly.toml`). The user's
503 was not a crash in the usual sense — it was the health-check-induced recycle.
Every normal page also blocked on that same prime with no response (the "minute-long
pre-load"). A recent change (the Bureau `scan` now solving `season_player_str` ×4
divisions) made the GIL-holding compute heavier and tipped a previously-surviving
setup over the edge.

## Fix
Two parts, both in the request path — the slow gen itself was left alone (owner:
"I don't care if it takes that long").

1. **Health/readiness/static never prime.** `_prime_world` now returns early for
   `request.endpoint in ("health", "ready", "static")`. `/api/health` answers in
   ~2ms even while the world is stone cold, so the fly check stays green *during* a
   warm and the machine is never recycled mid-compute. **This alone breaks the 503
   loop.**

2. **Cold prime warms in the background; the URL answers instantly with a loader.**
   When the world exists but is cold, `_prime_world` starts `wd.prime()` in a daemon
   thread (guarded by a module-level `threading.Event`) and returns a **self-contained
   loader** immediately. The loader is a raw `Response` string — deliberately NOT
   `render_template`, because the context processor (`_inject_chrome` →
   `_game_context`) would itself touch the cold world. It polls `/api/ready` every
   1.5s and `location.reload()`s once warm.

   - `world.is_primed(seed)` — new, cheap, read-only: recomputes the prime stamp
     `(id, year, week, roster_version())` and checks it against `_primed` +
     `_roster_cache`. No `get_or_create`, no roster build. Lets the web layer choose
     "serve vs loader" without paying for a prime.
   - `/api/ready` → `{ready: not exists OR is_primed}`. Never primes. (No world yet →
     ready, so the loader hands off to the dashboard→onboarding redirect.)

## GIL note (why a background thread is enough)
One worker + 8 threads. The background warm is CPU-bound Python, so it holds the GIL —
but CPython switches threads every ~5ms (`sys.getswitchinterval`), and the heaviest
gen phases use `multiprocessing` (the main process waits on the pool with the GIL
released). So `/api/health`, `/api/ready`, and the loader all still get served during
the warm. A *process*-level fix wasn't needed; the key was simply not doing the prime
*inside* the health request.

## Validation
- `health (no world)` → 200 in 3ms; `health (cold)` → 200 in 2ms.
- `dashboard (cold)` → 200 in 4ms, body is the loader; warms in the background;
  `dashboard (warm)` → 200, real content, loader gone. `/api/ready` flips
  False→True across the warm.
- Web + world suites green (25 passed: `test_web_season`, `test_web_recruiting`,
  `test_web_coaches`, `test_world`). The web tests drive **seasonmode directly** and
  never create a *world*, so `wd.exists()` is False and the loader path isn't hit —
  no test churn.

## Known follow-up (not done)
`advance_week` ends with `_primed.pop` (next access re-primes with more development),
so the loader also flashes briefly after a **week advance**. That re-prime is *fast*
(the developed-roster cache stays warm — only `_primed`/`_roster_cache` were cleared),
so it flashes rather than hangs. If undesired, gate the loader on a process-level
"has ever warmed" flag so only the genuine cold boot shows it and post-advance
re-primes run synchronously. Flagged to the owner; left as a choice.

## Files touched
- `app/world.py` — `is_primed()` (read-only warmth check).
- `app/web/server.py` — exempt health/ready/static from `_prime_world`; background
  warm + instant loader; `/api/ready`; `LOADING_HTML`.
