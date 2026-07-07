# AAR — ranking-cache perf regression, the power_index thread-race outage, and the infra thrash

## Context

Right after the regional-rankings / polls batch shipped, the owner reported (1) the app
was suddenly **laggy** accessing their own team, then after a redeploy (2) **pctennis.xyz
went fully down**. The two are the same root system — the ranking caches — and this AAR
records the actual causes so the mistakes aren't repeated. There was also a lot of infra
churn (Fly VM sizing, autostop, local-run) that turned out to be **red herrings** for the
outage; those lessons are recorded too.

---

## 1. ⚠️ The perf regression — an uncached `weekly_movers` in a hot function

The regional-rankings work added a `weekly_movers` call inside `state.ranking_rows` (for the
MOV column). `ranking_rows` is called on **many** pages (rankings, awards, hub, portal, dual
sim, and — critically — `scout_intel.scan` → the whole Analytics Bureau). `weekly_movers` ran
`compute_ratings` **twice, uncached** (current + prior week), the first being a duplicate of
the already-cached `power_index`. Net: `ranking_rows`' cost ~tripled app-wide → general lag.

**Fix:** cache `weekly_movers` by `(season_id, poll, completed-dual count)` like `power_index`,
and reuse the cached `power_index` for the current board so only the prior-week pass recomputes.

> Lesson: before calling a heavy function inside a **widely-called** helper, check whether it's
> cached and whether it duplicates work the caller already did. `ranking_rows` is a hub; adding
> a full ratings pass to it hits the whole app.

---

## 2. ‼️ The outage — a thread-race in `power_index` (`KeyError` → unhealthy → down)

The perf "fix" then **exposed a latent concurrency bug** and took the site down. The log:

```
File "app/seasonmode.py", in power_index
    return _pi_cache[key]
KeyError: (1, 3602)
```

Root cause — the cache pattern was **not thread-safe**:

```python
if key not in _pi_cache:
    _pi_cache.clear()            # keep only the newest entry
    _pi_cache[key] = compute_ratings(...)
return _pi_cache[key]            # ← re-reads the SHARED dict
```

Gunicorn runs a **threaded** worker (`gthread`, one worker to keep caches warm). Concurrent
requests call `power_index` with **different `season_id`s** (D1/D2/D3/D4 × M/W). Thread A stores
its key; thread B (different sid) then `.clear()`s the whole dict; thread A's `return
_pi_cache[key]` now `KeyError`s. That 500s **every ranking/intel page** → the `/api/health`
check fails → Fly proxy reports **"no known healthy instances found"** → site down.

The pattern was **pre-existing**, but §1's caching made `power_index` run *more often* (via
`weekly_movers`), tipping a rare race into a constant crash — so it read as "the latest update
broke the deploy."

**Fix (the important invariant):**

> ⚠️ Never `cache.clear()` and then `return cache[key]` under the threaded worker. Compute into
> a **local** and return that; read caches with `.get()`, not `key in cache` + `cache[key]`.

```python
ratings = _pi_cache.get(key)
if ratings is None:
    ratings = compute_ratings(...) or {}
    _pi_cache.clear(); _movers_cache.clear()
    _pi_cache[key] = ratings
return ratings                   # ← the local; a concurrent clear can't KeyError it
```

`weekly_movers` reads its cache with `.get()` for the same reason. Verified: 8 threads × 8 sids
hammering both → **0 errors** (was `KeyError`). Other `_*_cache` helpers that use the same
`clear()+return[key]` shape are latent risks — fix them the same way if they ever surface.

---

## 3. Infra thrash — what was a red herring, and the real lessons

Chasing the lag/outage we also churned `fly.toml`; most of it did **not** cause the outage
(the §2 code bug did), but the lessons stand:

- **Autostop was NOT the outage** (§2 was) — an early misdiagnosis. It's fine on this single
  `--ha=false` machine: `auto_stop_machines = 'stop'` (or `'suspend'`) + `auto_start_machines =
  true`. The one required setting is **`min_machines_running = 0`** — with `1`, Fly keeps a
  machine up and immediately un-stops any manual/idle stop (which read as "my stops keep
  auto-starting"). `'stop'` = truly off / zero compute when idle, cold start on return;
  `'suspend'` = warm instant resume but bills reserved RAM. Chose `'stop'` for real savings.
- **Dedicated `performance` CPUs hit a hard overcommit gate.** Scaling to `performance-6x`
  failed with `cpu_overcommit_exceeded` — the machine is **pinned to its volume's host**, which
  couldn't free 6 dedicated cores (and there's likely an account cap). 4×/2× placed. If a big
  dedicated size won't deploy, it's host/account capacity, not a retry problem.
- **More CPUs barely help per-request latency here.** The app is **one gunicorn worker**
  (GIL-bound per request); extra cores only help the parallel roster build (`prime`) and
  concurrency, not a single team-page load. The §1/§2 cache fixes are what made it snappy — not
  the box size. Size **up** (CPU/RAM) only for `prime`/concurrency; never size *out* (SQLite is
  single-host).
- **Deploys run only on push to `main`** (`.github/workflows/deploy.yml`, `--ha=false`). Feature-
  branch pushes don't deploy; recovery is a manual `fly deploy` or a merge to main.
- Minor perf: cached `towns_in_region` per region (the hometown-breadth change had it re-scanning
  the ~1.5k-city pool once per program during `prime`).

---

## 4. Running it locally (the owner's first local setup)

`python3 manage.py runserver --port 8000` (venv + `pip install -r requirements.txt`, Python
3.11+). Two gotchas that ate time:

- **macOS steals port 5000** (AirPlay Receiver) — the README's default. Use `--port 8000`.
- **macOS restricts programmatic writes under `~/Documents`**, so the SQLite save silently fell
  back to a temp dir (lost on restart). Fix: `dbpath.resolve_db_path` now falls back to a
  **persistent** `~/.tennis-team-manager/tennis.db` before temp, and the warning no longer reads
  as Fly-specific for local users. `TENNIS_DB_PATH` overrides. README gained a local quickstart +
  the `fly ssh sftp get /data/tennis.db` recipe to play the deployed save offline.

## Takeaways

1. A widely-called helper (`ranking_rows`) is a force multiplier — heavy work added there hits
   the whole app, and *more calls to a racy function turns a latent bug into an outage.*
2. The threaded worker means module-global caches must be read race-safely (`.get()` + return a
   local). This is the invariant most likely to be re-broken.
3. Hardware was never the fix — measure the code path before scaling; on a single-worker,
   single-host (SQLite) app, vertical helps `prime`/concurrency only, and horizontal isn't safe.
