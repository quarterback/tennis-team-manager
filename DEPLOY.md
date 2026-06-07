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

## Fly.io via GitHub Actions (web-only, no CLI)
Deploys run automatically from `.github/workflows/deploy.yml` — same pattern as
the other sims. **Every push to `main` builds the Docker image and deploys to
Fly** (also runnable on demand via the Actions tab → "Deploy to Fly.io" → "Run
workflow").

One-time setup, all in the browser:
1. **Get a Fly token** — Fly.io dashboard → Account → **Tokens** → create a
   deploy token; copy it.
2. **Add it to GitHub** — repo → Settings → Secrets and variables → Actions →
   **New repository secret**, name `FLY_API_TOKEN`, paste the token.
3. **Merge to `main`.** The workflow creates the Fly app (`tennis-team-manager`)
   on its first run and deploys it; afterwards every merge re-deploys.

The workflow validates the Docker build, deploys with retries, then health-checks
`https://tennis-team-manager.fly.dev/api/health`. (If that app name is taken,
change `app =` in `fly.toml` and the two `tennis-team-manager` references in the
workflow to a free name.)

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
