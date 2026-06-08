# AAR — Onboarding, Rename, Pagination, Player History & Awards

## Segment Summary

This segment was a rapid, user-driven UX pass over the live web app, plus one
genuine production bug fix. The app had been dropping users straight into what
looked like an already-running season, simulating throws on a fresh DB were
500ing with `database is locked`, the product needed renaming, long lists were
unpaginated, players weren't clickable from results, and there was no honors
system. Each was addressed in turn, kept additive and seed-deterministic.

The work landed across four stacked branches/PRs (each built on the prior so the
critical fix can merge first):

- **#16 `database is locked` hotfix**
- **#17 onboarding + fresh preseason start**
- **#18 rename → "Play to Clinch", SEO/social, pagination, player history**
- **awards scheme** (this branch)

All suites green throughout: **121 tests passing** at the end (119 + 2 new
awards tests).

## What Was Built / Fixed

### 1. `database is locked` hotfix (#16)
Root cause: every `_db()` re-ran `executescript(_SCHEMA)` (a write) per call with
no WAL/busy-timeout, so a sim's open write transaction collided with the first
nested schema-write — and lazily creating another module's table *inside* world
seeding (`overrides` during `get_or_create`) deadlocked two writers. Fix: tuned
connections (WAL + `busy_timeout`) in `dbpath`/`world`/`seasonmode`, and an
eager `db.bootstrap()` at app start that creates **every** module's schema once,
before any long transaction. Verified the deadlock no longer reproduces.

### 2. Onboarding + fresh preseason start (#17)
- A real league lifecycle: `world.reset()` / `world.start_new()` wipe all
  season-to-season state (`world_*`, `seasons`, `duals`, caches) and create a
  fresh league at **preseason — year 0, week 0, nothing played**.
- First-login gate: with no league, the dashboard (`/`) redirects to a new
  `/start` onboarding page instead of a pre-simulated season; other pages stay
  browsable. "Start a new league" drops into the week-by-week World hub.
- "↺ New league" top-bar link routes to `/start` (two-step, never an instant
  wipe).

### 3. Rename → "Play to Clinch" + SEO (#18)
- All user-facing strings (titles, sidebar wordmark, prose, logo aria-labels).
- Meta description (overridable per page via a `meta_description` block),
  Open Graph + Twitter `summary_large_image` card, generated 1200×630
  `og-image.png` share image, `theme-color`, favicon.

### 4. Pagination everywhere (#18)
- `app/web/pagination.py`: `Page` + `paginate()` (clamps junk/out-of-range
  `?page` so stale links never 500 or blank) with a windowed page list.
- `_pager.html` macro preserves every current query arg (filters/sort/universe)
  when switching pages.
- Wired into **Rankings** (50/pg), **Recruiting** (50/pg), **All Teams** (8
  conferences/pg), and **Awards** (6 conferences/pg). Replaced the old
  `[:75]`/`[:100]` caps and the single long scroll.

### 5. Player linking + results by season (#18)
- Box-score singles players link to their player cards (doubles left as text).
- Player-card opponents and schools are clickable.
- Player card lists singles results **grouped by season-year** with per-season
  W-L and a career total. `state.player_career()` reads the same cached season
  the team/box-score pages render, so a card always matches the result clicked
  from.

### 6. All-American / All-Conference awards scheme (this branch)
- `app/web/awards.py`: `season_awards()` selects singles honors from the
  season's STR ratings (min 4 matches): **All-American** First/Second/HM
  nationally, **All-Conference** First/Second per conference, plus a
  `by_pid → [honor labels]` index.
- New **Awards** page (nav item, paginated by conference) and honor badges on
  player cards.
- Cache cleared via `state.reset_all()` alongside the season/bracket caches.

## Design Influences

A research subagent produced a design brief (SaaS-dashboard-weighted, with
sports-management games as cautionary tales on density). Key adopted principles:
right-aligned numerics, sticky/scannable tables, ratings-based honors kept
*consistent* with the rest of the app, and "advance the season" as the core
verb. Several larger recommendations (⌘K palette, bottom tab bar, dashboard
inverted-pyramid redesign) are **not** done — see Deferred.

## Validation

- `pytest -q` → **121 passing** (added 2 awards tests; updated assertions for
  the `/`→onboarding redirect and the renamed player panel).
- Headless-browser checks at desktop (1280/1440) and **390px mobile**: brand,
  onboarding flow (fresh boot → `/start` → world at week 0), pager (page 2 =
  51–100 of 366, filters preserved), player career grouping + opponent links,
  box-score links, awards page, player honor badges.
- **Mobile finding:** the responsive shell (hamburger drawer, stacked cards,
  table scrollers) already works locally. The live site's mobile breakage is a
  **deploy gap** — these branches aren't deployed — not missing code.

## What I Did NOT Change (honesty section)

- **The baseline-vs-seasonmode duality remains.** The dashboard/rankings still
  render the deterministic full "baseline" season (`run_season`) rather than the
  world's actual week-by-week progress, so a freshly-started league's dashboard
  still shows a complete projected season even at Week 1. Onboarding now lands
  users in the World hub (true week-0 state) to sidestep this, and
  `player_career` was deliberately built on the baseline season so player cards
  stay consistent with everything else — but unifying the two season systems is
  a separate, larger change.
- **Season-to-season retention** (drop game logs/scores at season end, keep
  career play data, archive program legends) — deferred per the user.
- **Multi-year career history** — `player_career` returns a by-year structure
  but only the current season-year is populated; persisted past seasons would
  fill it.
- Awards are a **ratings-based proxy**, not the real NCAA tournament-based
  selection.

## Deferred / Next

1. World-aware dashboard (retire the baseline duality).
2. Season-to-season retention + program legends archive.
3. Mobile/SaaS polish from the design brief (⌘K, bottom tab bar, dashboard
   inverted pyramid, frozen rank/name column on wide tables).
4. Doubles-team honors + team-page honor badges.
