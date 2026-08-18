# AAR — `/world/advance` died with `sqlite3.OperationalError: database is locked`

**Date:** 2026-08-18
**Status:** FIXED (root cause reproduced in isolation; both mechanisms closed and
verified). PR #276.
**Scope:** `app/worldconfig.py` (new `init_schema()`), `app/db.py` (`bootstrap()`
now creates it), `app/seasonmode.py` (`advance()` primes the config cache before
opening its write transaction), `app/web/server.py` (`world_advance` serialized
with `_advance_lock`).

## Symptom

Owner pasted a Werkzeug debugger traceback from a local run:

```
sqlite3.OperationalError: database is locked
  File ".../app/web/server.py", line 827, in world_advance
    wd.advance_week()
  File ".../app/world.py", line 3402, in advance_week
    res = sm.advance(sid)
  File ".../app/seasonmode.py", line 849, in advance
    _play_and_store(conn, s, progs, d["id"], d["home"], d["away"], d["is_conf"], ...)
  File ".../app/seasonmode.py", line 480, in _play_and_store
    conn.execute("UPDATE duals SET status='final', home_points=?, ...")
sqlite3.OperationalError: database is locked
```

No task description beyond the traceback — this was a bug report to diagnose and
fix, not a request with a spec.

## Root cause — two independent ways to open a second writer against a held transaction

`seasonmode.advance()` opens one connection (`conn`) and holds it across an entire
phase's write transaction — for the `"regular"` phase, that's every scheduled dual
of the week for one division×gender universe, `conn.commit()` only firing once
*after* the whole loop. Measured on a fresh D3 world: **340 duals in one call,
~17 seconds**, all inside one open transaction. Anything that opens a *second*
writer to the same SQLite file during that window is racing a multi-second window,
not a few milliseconds.

**Mechanism 1 — a cold `worldconfig` read mid-loop.** Every dual calls
`dual_between()`, which reads match fidelity / box-stats / the coached lineup pin
via `worldconfig.get()`. On a cold in-process cache, `worldconfig._conn()` opens
its *own* connection and runs a lazy `CREATE TABLE IF NOT EXISTS world_setting` —
a write, contending with the transaction `conn` already holds. This is the exact
hazard CLAUDE.md already documents for the pro league
(`gtt_seasonmode._prime_world_config()`, "NEVER read worldconfig while holding a
GTT/world SQLite transaction") — it just hadn't been ported to the college path.
`app/db.py`'s `bootstrap()` already eagerly creates every OTHER module's schema
for exactly this reason (its own docstring: "the two writers deadlock"), but
`worldconfig` and `rankings_archive` were missing from that list — `worldconfig`
because nobody had hit its cold path from inside a held transaction yet; a warm
cache (module-global `_cache` dict, keyed per-process) hid it for as long as
nothing new called `get()`.

Reproduced in isolation: an outer connection holds an uncommitted `INSERT`, a
second connection cold-reads a not-yet-created `worldconfig` table → blocks the
full 5s `busy_timeout`, then raises `OperationalError` — exactly the traceback's
error string, exactly the 5000ms `PRAGMA busy_timeout` set in `dbpath.connect`.
Priming the cache (`worldconfig.prime_cache(worldconfig.snapshot())`) *before*
opening the writer collapses that to a pure cache hit (~0.001s, no connection at
all).

**Mechanism 2 — no guard against a concurrent `/world/advance`.** Given how long
one call can hold the writer (the 340-dual / 17s measurement above, and that's a
*single* universe — `advance_week()` loops every active division×gender), nothing
in the route stopped a second overlapping POST (a double-click, a slow first
request plus a retry, two open tabs) from opening its own connection and writing
concurrently. That second connection can fail on *any* statement in its own
loop — including, as in the traceback, an ordinary `UPDATE duals ...` deep inside
`_play_and_store` — once the first request has held the lock past 5s, which a
340-dual week trivially does. `gunicorn` runs one `gthread` worker (multiple
threads, one process — see the module-cache rules elsewhere in this file), so
this isn't a local-dev-server-only concern; it reproduces in production too.

Both mechanisms independently explain a crash at that exact line; either alone
was worth fixing, so both were.

## The design lessons (the part to internalize)

> ⚠️ **A schema module is not "safe" just because most reads hit a warm cache.**
> `worldconfig.get()`'s cold path (lazy `CREATE TABLE IF NOT EXISTS`) is a write
> like any other module's, and this app already has a rule and a mechanism
> (`db.bootstrap()`) for making sure no module's *first* schema-creating write
> happens while another module holds a transaction open. Adding a module's
> `init_schema()` is not optional polish — leaving one out of `bootstrap()` is
> the same bug as never having written it, just latent until the cache runs cold
> (a fresh process, a new key, a process restart) at the wrong moment.

> ⚠️ **"It's wrapped in `try/except Exception`" does not make a nested writer
> free.** `season._fidelity()` / `_box_stats_on()` / `_coached_pin()` /
> `_coached_doubles()` all swallow the `OperationalError` from a cold
> `worldconfig` read, so it never propagates as a crash from *there*. But the
> failed connection still burns the full `busy_timeout` (5s) on every call, every
> dual, for as long as the cache stays cold and the outer transaction stays open
> — a silent multi-minute stall dressed as a caught exception, on top of being
> the reason a *different*, unwrapped statement later in the loop finds the file
> contended. Priming the cache before the transaction opens is the fix, not a
> broader `except`.

> ⚠️ **A long-running write transaction is a lock, and a lock needs a lock
> around calling it.** `world._prime_lock` already exists because two gthreads
> both building the ~170MB roster cache is a known hazard; `advance_week()`
> holding the SQLite writer across hundreds of duals is the exact same shape —
> a second concurrent caller doesn't just do redundant work, it actively fails.
> If an operation is long enough to want a `busy_timeout`, it's long enough to
> want serialization at the call site, not just at the database driver.

> ⚠️ **A test that greps prose is a real constraint, not noise.**
> `test_web_layer_never_steps_a_season_directly` enforces "only `world_advance`'s
> standalone branch calls `sm.advance` directly" by grepping literal substrings
> across `app/web/*.py` — including comments. Writing `seasonmode.advance()` in
> an explanatory comment above unrelated code is a real false positive under that
> test, not a test bug; reword the comment rather than loosen the check (the
> check is doing its job — catching a second call site — it just can't tell code
> from prose about code).

## The fix (implemented, reproduced, verified)

1. **`worldconfig.init_schema()`** (new) creates `world_setting` eagerly with a
   short-lived, auto-committing connection — same idiom as
   `overrides.init_schema()`. Wired into `db.bootstrap()` alongside it (which
   also picked up `rankings_archive.init_schema()` for the same reason, since it
   was the other schema missing from the eager list).
2. **`seasonmode.advance()`** now calls
   `worldconfig.prime_cache(worldconfig.snapshot())` before opening `conn` —
   the same pattern as `gtt_seasonmode._prime_world_config()`, applied at the
   college entry point (covers both the world-driven path and a standalone
   `sm.advance()` call, e.g. tests/calibration).
3. **`/world/advance`** is now serialized with a module-level
   `threading.Lock()` (`_advance_lock`, non-blocking `acquire`). A duplicate
   concurrent POST is dropped (redirects immediately) instead of opening a
   second writer against the transaction the first request already holds.

**Verified:**
- Isolated repro: cold `worldconfig.get()` mid-transaction → 5.01s → `database is
  locked`; primed → 0.001s, no error.
- `create_app()` builds cleanly with the new lock in place.
- A fresh D3 season advances through ITA kickoff/indoor and several full regular
  weeks (up to 340 duals in one call) with no `OperationalError`, `TTM_FIDELITY`
  unset (full config-read path exercised).
- `tests/test_seasonmode.py` (27/28 → 28/28 after the comment reword),
  `tests/test_universe_sync.py` (7/7, including
  `test_web_layer_never_steps_a_season_directly`), `tests/test_world.py` — all
  pass.

## Takeaways

1. `db.bootstrap()`'s job is "every module's first write happens before any
   transaction can be open to contend with it" — that's a closed list to
   maintain, not a one-time list. When you add a module with a lazy
   `CREATE TABLE IF NOT EXISTS`, add its `init_schema()` to bootstrap in the
   same change, don't wait for the cold path to fire in production.
2. A `try/except` around a nested connection prevents a *crash*, not the
   underlying lock contention or the time it burns. Prime caches before opening
   a long write transaction; don't rely on exception handling downstream of it.
3. If an operation holds a SQLite writer for seconds (not milliseconds) across
   many rows, guard the entry point against concurrent callers explicitly — the
   database's own `busy_timeout` is a mercy, not a substitute for an
   application-level lock, once "seconds" becomes "tens of seconds" under real
   data volumes.
4. Greppy tests that scan source text (not ASTs) are still real constraints —
   satisfy them by not producing the matched string, not by weakening the test.
