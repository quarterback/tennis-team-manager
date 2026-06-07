# Deploying

This is a **Python Flask** app that simulates a full season in memory and
caches it. It needs a real container/VM with normal CPU + persistent process
memory — **not** an edge/serverless runtime.

> **Cloudflare Workers will not work.** Workers run JS/WASM (or a limited
> Python-on-Pyodide beta) under tight per-request CPU limits and with no
> persistent memory between requests. The first hit on a universe runs a ~2s
> CPU-bound season sim and caches it — Workers can't do either. `wrangler
> versions upload` also expects a Worker script, which this isn't. Use a
> container host below. (If you must stay on Cloudflare, use **Cloudflare
> Containers**, which runs this Dockerfile behind a Worker — ask and we'll add
> the `wrangler.toml` + container glue.)

The app is **stateless** (seasons are simulated + cached, nothing written), so
no database/volume is required.

## Run locally
```
pip install -r requirements.txt
python3 manage.py runserver          # dev server, http://localhost:5000
gunicorn wsgi:app                    # production server (what the container runs)
```

## Fly.io (same as the baseball sim)
```
flyctl launch --no-deploy            # first time — creates the app from fly.toml
flyctl deploy
```

## Render / Railway / any container host
- Build with the `Dockerfile`, or use the `Procfile`:
  `web: gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 120 wsgi:app`
- Health check: `GET /api/health` → `{"status":"ok"}`.

## Notes
- **One gunicorn worker + threads** on purpose: the season/bracket cache lives
  in process memory, so a single shared process keeps it warm while threads
  handle concurrency. Scaling to multiple workers just means each re-runs the
  sim on first hit (still correct, just less efficient).
- 1 GB RAM is plenty; CPU is the constraint on first hits (then cached).
