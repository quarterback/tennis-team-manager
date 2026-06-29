# AAR — Team-takeover hang: cold-prime loader must key on the league salt, not a process flag or rowid

**Date:** 2026-06-29
**Status:** ✅ Fixed. Branch `claude/tennis-sim-engine-tests-tpbdfx`.
**Reported:** "I took over a team and it's crashing again and won't reload." Then,
after a long wait, "it took forever but it's loading again."
**Sequel to:** `AAR-cold-prime-loader-health-503-loop.md` (the loader) and its
first-boot gating. This is a regression introduced by that gating.

## Why
Career mode's **team takeover** (and "New League") calls `world.start_new()` →
`reset()` + `get_or_create()` with a **fresh random salt**: a brand-new, heavy world
that needs a full cold prime (a minute+).

The loader's first-boot gating decided "loader vs prime-inline" with a **process-global
flag** (`_warmed_once`): show the loader only the first time the process warms; every
later cold cache is assumed to be a *fast* re-prime (post week advance) and is primed
**inline**. That assumption breaks on takeover: the process had already warmed a world
while spectating, so `_warmed_once` was set, so the brand-new takeover world was primed
**synchronously** — the request blocked for the entire cold-gen minute and the page
"wouldn't reload." (It wasn't a crash; it was a one-minute synchronous stall in the
single worker.)

## Two wrong identities before the right one
1. **Process flag (`_warmed_once`)** — conflates "warmed *this* world" with "warmed
   *any* world this process." Takeover is a new world; the flag was stale-true. ✗
2. **World row id (`load_world()["id"]`)** — looked right, but **SQLite reuses the
   rowid**: `start_new` deletes the single `world` row and inserts a new one, which
   comes back as `id = 1` again. The new league matched the warmed id → still primed
   inline. ✗ (Caught in test: takeover showed `loader: False, 2.76s` — an inline prime.)
3. **Generation salt (`world.active_salt()`)** — the per-league generation seed:
   fresh-random on every `start_new`, stable across week advances / edits / rollover
   within a league. Unique per world instance, survives rowid reuse. ✓

## Fix
Key the "already warmed" state on the salt:

```python
_warmed_salt = {"v": None}
...
cur_salt = wd.active_salt()
if cur_salt and _warmed_salt["v"] == cur_salt:
    wd.prime(); return                 # same league → fast inline re-prime, no loader
# different league (takeover / new / fresh machine) → background warm + loader
...
    def _warm():
        try:
            wd.prime(); _warmed_salt["v"] = cur_salt   # record on success only
        finally:
            _warming.clear()
return Response(LOADING_HTML, mimetype="text/html")
```

Behavior matrix now:
| Trigger | salt vs warmed | result |
|---|---|---|
| Fresh machine, first load | none warmed | loader + bg warm |
| Same league, post week-advance / edit | match | inline prime, no loader |
| **Takeover / New League** | **differs** | **loader + bg warm** (was: synchronous block) |

## Validation
Spectate to warm league A, then take over a team (new salt):
- same-league re-prime → `loader: False` (inline, ~1.3s)
- **takeover new world → `loader: True` (0.00s), 200** — instant, not a blocking prime.

## Lesson
"Has this world been warmed?" needs a **content identity that changes when the world
is regenerated**. A process boolean is too coarse; the DB rowid is unstable across
delete+reinsert. The generation salt is the canonical per-league identity and was the
right key (it's already what all roster/recruit generation is keyed on).

## Files touched
- `app/web/server.py` — `_warmed_salt` (was `_warmed_once`); `_prime_world` cold
  branch keys on `wd.active_salt()`.
