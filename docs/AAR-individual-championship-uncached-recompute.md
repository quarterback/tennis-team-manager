# AAR — NCAA individual championships recomputed on every request (dead cache)

**Date:** 2026-07-08
**Scope:** `web/state.get_singles_championship`, `get_doubles_championship`.
**Class:** the module-global-cache / request-thread-compute family in CLAUDE.md
(`AAR-perf-regression-and-power-index-thread-race.md`,
`AAR-cache-invalidation-scope-lineup-stall.md`).

## Symptom (owner report)
The NCAA singles/doubles individual championship pages "run really really slowly
if at all," it's not obvious they ever run, and "trying to display the page
crashes the app."

## Root cause — the caches were dead code
`web/state` declares `_singles_champ_cache` and `_doubles_champ_cache`, and
`reset_all()` dutifully clears them — but `get_singles_championship` /
`get_doubles_championship` **never read or wrote them.** So while a season is
`complete` (exactly the window when a user goes to look at the results, before the
year rolls over), *every request* re-ran the whole event **live on the gunicorn
request thread**:
- `select_singles_field` → `squad_and_ladder` over all ~380 D1 programs (~1.5s), then
- a 128-draw = **127 best-of-3 engine matches** (singles) and a 64-draw = **63
  doubles matches**.

Measured warm: ~0.6s per page, *identical* on repeat (0.594s → 0.59s) — proof it
recomputed every time. Cold, or concurrent with the ~170MB world prime / a
rollover under the single `gthread` worker, that uncached recompute is precisely
the "heavy compute on the request thread → gunicorn write timeout → `/api/health`
flap → 'no known healthy instances'" failure the CLAUDE.md caches section is about.
It doesn't hard-crash; the instance goes unhealthy and the page appears dead.

## Why it hid
- **The scaffolding looked done.** The caches existed and were wired into
  `reset_all()`, so a reader skimming assumed they were live. Only the read/write
  sites were missing. A declared-and-cleared cache that is never *populated* reads
  as "cached" at a glance.
- **The snapshot path masked it.** After a year rollover, `world._store_championships`
  persists the event and the view serves the stored snapshot (`latest_championship`)
  — fast. Only the *pre-rollover complete* window hit the live recompute, so it
  looked fine right up until you actually watched the current season finish.

## Fix
Memoize the serialized championship per `(division, gender, sid, size)` in the
existing caches, following the CLAUDE.md thread-safe pattern: compute into a
**local**, publish, and `return` the local (never `return cache[key]` after a
possible sibling-thread / `reset_all()` eviction); read with `.get()`, never
`key in cache` + `cache[key]`. The field is frozen once the season is `complete`,
so the key is stable; each field-size pill (32/64/128) gets its own key and
computes once. `reset_all()` already clears both (editor overrides re-derive).

This is the same shape as the `_bracket_cache` memo immediately above these
functions — the individual-championship path had simply never been given the same
treatment.

## Verified
Drove a fresh D1/men season to `complete`, rendered both pages through the Flask
test client:
- first view ~0.6s, **repeat views ~0.008s** (~70× faster, served from cache);
- cached render is **byte-identical** to the first (determinism preserved);
- `?size=64` computes once then caches; `reset_all()` empties both caches.
- `tests/test_individuals.py` (10) green.

## Not done (deliberate) — moving the compute earlier
The owner floated computing the events during the season instead of "waiting to
the end." The caching fix already makes the result available the instant the
season is complete and instant on every subsequent view, without touching the
rollover / world-prime path (the riskiest area per CLAUDE.md). Precomputing at the
`phase → complete` transition (writing the snapshot then, so even the *first* view
reads it) is a reasonable follow-up, but it moves a ~1s compute onto the
season-advance click and into `seasonmode`/`world`; left out of this change to
keep the fix scoped to the confirmed defect.

## Gotcha for the next agent
These caches key on `sid`, so they accumulate one small serialized dict per
season/size over a long world — bounded and cheap, matching `_bracket_cache`. Do
**not** global-`clear()` them inside a per-request seasons loop (the quadratic
trap of AAR-perf §2b); `reset_all()` is a full editor-override reset and is the
only intended clear.
