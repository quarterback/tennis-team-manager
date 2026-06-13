# AAR: Export-Portal Health-Check Timeout

**Date:** 2026-06-13
**Repo:** tennis-team-manager
**Severity at time of incident:** P1 — site unreachable 3 minutes after every deploy

---

## What happened

After the PR #57 race-condition fix was merged and redeployed, the site loaded
briefly then health checks started failing ~3 minutes post-deploy. fly.io
killed the container and the app became unreachable on every deploy.

Health-check logs showed the `/healthz` endpoint timing out under the default
`timeout = '5s'` in `fly.toml`:

```
2026-06-13T...: Health check on port 8080 is warning, ...
2026-06-13T...: Health check on port 8080 is unhealthy, ...
```

No traceback — the process was alive but not answering HTTP requests.

---

## Root cause

`export_data_portal` in `app/web/server.py` iterates all 6 UNIVERSES
unconditionally and calls `data_portal_view(division, gender)` for each.
`data_portal_view` calls `recruiting_hub` → `get_recruits` → `run_junior_circuit`
on a 1 000-prospect class. With gunicorn running `--workers 1 --threads 8`,
Python's GIL means this CPU-bound work holds the interpreter long enough that
the health-check thread (sharing the same process) cannot service the `/healthz`
GET within the 5-second window.

The app had only ONE active universe (D1 Women), but the export loop was
spinning up the junior circuit for all 6 — a 6× slowdown from dead work.

---

## Fixes

### 1. Active-universe filter (`app/web/server.py`)

```python
from app import worldconfig

universes = []
for _u, division, gender, label in UNIVERSES:
    if not worldconfig.is_active(division, gender):
        continue
    try:
        portal = data_portal_view(division, gender)
    except Exception:
        continue
    universes.append({...})
```

Inactive universes skip entirely. A single-division league calls
`data_portal_view` exactly once instead of six times.

### 2. Portal cache (`app/web/state.py`)

Added a module-level `_portal_cache: dict = {}`, keyed by
`(division, gender, sid, current_week, phase)`. `data_portal_view` returns
the cached dict immediately after `load_season` if the key matches:

```python
_pkey = (division, gender, sid, s["current_week"], s["phase"])
_cached = _portal_cache.get(_pkey)
if _cached is not None:
    return _cached
```

The cache auto-invalidates when the season advances (new week or phase changes
the key). `reset_all()` also clears it so editor overrides invalidate correctly.

### 3. Health-check timeout bump (`fly.toml`)

Changed `timeout = '5s'` → `timeout = '30s'` in `[[http_service.checks]]`.
This is a safety net, not the root fix — but it gives headroom on cold starts
and any future first-call costs before the cache warms.

---

## What was NOT changed

- The gunicorn config (`--workers 1 --threads 8 --timeout 120`) — no change needed
- The junior circuit itself — the cost is real; we just stopped paying it 5 extra times
- The health-check endpoint `/healthz` — it was working fine, just blocked
- Any season data or DB schema

---

## Validation

- `worldconfig.is_active` filter and `_portal_cache` dict confirmed present
  in modified files before push
- Cache key `(division, gender, sid, current_week, phase)` covers all state
  that would make a stale result incorrect
- `reset_all()` already cleared every other cache; `_portal_cache.clear()` added
  in the same block

---

## Lessons

The GIL serialises CPU-bound work across threads. Any background/cron-style
function that does heavy computation in the same process as the web server will
block health checks. The pattern to watch: unbounded loops over "all universes"
that assume all are active.
