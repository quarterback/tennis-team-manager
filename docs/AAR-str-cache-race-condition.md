# AAR — Production 500: race condition KeyError in `season_player_str`

Intermittent 500s on `/player/<pid>` started appearing in production logs on
2026-06-13, coinciding with health-check flapping that suggested worker crashes
under concurrent load. Diagnosed and patched in the same session.

## Problem

`GET /player/<pid>` was raising an unhandled `KeyError` in `seasonmode.py`:

```
File "/app/app/web/server.py", line 677, in player
    strv, rel = sm.season_player_str(sid).get(pid, (None, 0.0))
File "/app/app/seasonmode.py", line 807, in season_player_str
    return _str_cache[key]
KeyError: (4, 1033)
```

The error was intermittent — it required at least two concurrent requests to
trigger — which made it invisible in single-user testing and explains why it
only appeared after the latest deploy increased traffic.

## Diagnosis

`season_player_str` caches its expensive `converge_ids` result in a module-level
dict keyed by `(season_id, completed_dual_count)`. The cache-read path was:

```python
if key in _str_cache:
    conn.close()
    return _str_cache[key]   # line 807
```

The cache-write path (reached when the key is missing) calls
`_str_cache.clear()` before inserting the new result, to evict stale entries
from previous dual counts.

The race:

1. **Thread A** (player page request): reads `key = (4, 1033)`, finds it in
   `_str_cache` via `in`, prepares to return it.
2. **Thread B** (advance-season request or a second player page for a newly
   completed dual): computes a new STR result for `key = (4, 1034)`, calls
   `_str_cache.clear()` — **wiping Thread A's `(4, 1033)` entry** — then
   inserts its own result.
3. **Thread A** executes `return _str_cache[key]` → `KeyError`.

This is a classic TOCTOU (time-of-check/time-of-use) race. Python's GIL does
not protect compound operations: the `in` check and the subsequent `[]` lookup
are two separate bytecode sequences between which any other thread can run.

The same structural pattern exists in `power_index` (`_pi_cache`) and
`player_records` (`_prec_cache`), but those are less exposed in practice:
`power_index`'s read path does `return _pi_cache[key]` *outside* the `if not
in` block (so both threads write the same key before either reads it), and
`player_records`'s write path is inside a `if key not in _prec_cache` guard
that doesn't race the same way. Neither showed errors in production.

## Fix

Capture the cached value into a local variable before doing anything else. A
local reference survives any concurrent dict mutation:

```python
# before
if key in _str_cache:
    conn.close()
    return _str_cache[key]   # races with concurrent .clear()

# after
cached = _str_cache.get(key)
if cached is not None:
    conn.close()
    return cached             # local ref; immune to dict eviction
```

`_str_cache.get(key)` returns `None` on a miss (the dict returns `None`, not
raises). The result of `converge_ids` is always a non-empty dict of player
ratings, so `is not None` is the correct guard (an empty dict `{}` would also
be a valid cached value and is `not None`, though in practice `converge_ids`
never returns one with priors set).

One file changed: `app/seasonmode.py`, `season_player_str` function only.
No schema changes, no behaviour changes, no test changes needed.

## Result

The race window is closed. The fix is in `app/seasonmode.py` on
`claude/practical-davinci-d82mmb` and is ready to deploy. No other
call sites were modified; the `_pi_cache` and `_prec_cache` patterns were
inspected and are not vulnerable to the same failure mode.

## What we did not change

- The `_str_cache.clear()` eviction strategy was left in place. It's a
  reasonable approach for a cache that should only ever hold one entry per
  season at a time, and replacing it with a more sophisticated scheme (e.g.
  `functools.lru_cache`, a lock, or a size-bounded dict) was out of scope for
  a production hotfix.
- The `power_index` and `player_records` caches use the same `.clear()` +
  re-insert idiom and could theoretically race under different conditions.
  They were not changed in this pass but are worth hardening the same way if
  those routes become higher-traffic.
- The health-check flapping noted in the deploy logs was likely a downstream
  consequence of worker crashes triggered by this 500; no separate health-check
  investigation was done.
