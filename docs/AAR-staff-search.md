# AAR — Staff Search (scout coaches by ability, spot HC-ready assistants)

> **Status:** shipped. A Football-Manager-style **Management › Staff Search** page
> (`/staff-search`) lists every coaching seat in the world by ability — **Head coaches /
> Assistants / Both** — sortable by overall or any pillar, with an **HC-ready** flag on
> assistants good enough to run a program.

## 1. The ask (owner)
Like FM's staff search: find **assistant coaches ready for head-coaching jobs** by searching
on **attribute ratings**, filterable to head coaches, assistants, or both.

## 2. The data was already there — one perf wall
Every program already has three seats — **head / assoc / asst** (`coachgen`, `coachreg`) —
each carrying persisted **dev / rec / tac** ratings (20–80), archetype, home country, tenure.
The only problem was enumerating the whole world: `coachgen.ensure()` called
`ncaa.load_division()` **per seat**, ~11 ms × 6,642 seats ≈ **73 s** (timed out).

**Fix:** `coachgen.ensure(..., prog=None)` — a bulk caller passes the already-loaded program,
skipping the per-seat reload. With the division loaded once per universe the full world builds
in **~6 s cold**; scoped to one division×gender it's **~0.9 s**, and every universe result is
cached per world snapshot (`_uni_staff_cache`, keyed on `coachreg.generation()` + salt + year,
cleared on reset alongside `_staff_cache`).

## 3. The build
- **`state.coach_overall(dev, rec, tac)`** — a single 20–80 "current ability" = mean of the three
  pillars (legible; per-pillar columns show the real profile).
- **`state._universe_staff(division, gender)`** — every seat in one universe as flat rows, division
  loaded once, cached.
- **`state.staff_search(gender, division, role, sort, q)`** — assembles the requested
  divisions × genders (`All` / `Both` fan out), filters by role (`head` / `assistant` = assoc+asst /
  `both`) and a name/school/country/archetype query, sorts by overall / dev / rec / tac / tenure / name.
  Returns `{rows, hc_bar}` where **`hc_bar`** is the median HEAD-coach overall **in scope** — computed
  from the full head pool *before* the role filter, so "ready" means "as good as the median sitting
  head coach at this level." Each assistant at/above it gets `hc_ready=True`.
- **Route** `/staff-search` + **template** `staff_search.html` (Role / Gender / Division / Sort / Search
  toolbar; COACH · CURRENT SEAT · OVR · DEV · REC · TAC · TEN columns; a green **▲ HC-ready** chip;
  coach names link to `/coach/<id>`). Nav item **Staff Search** under Management.
- Registered `/staff-search` in `_active_nav` (→ `staff`). Also fixed two stale mappings from prior
  work: `/intel/portal-search` (→ `intel_search`) and `/intel/my-targets` (→ `intel_targets`) were
  shadowed by the `/intel` catch-all and never highlighted.

## 4. Using it
Role = **Assistants**, Sort = **Overall** → the HC-ready ones float to the top: your head-coaching
shortlist. Ratings are the same 20–80 scouting scale used everywhere else.

## 5. Files touched
- `app/coachgen.py` — `ensure(prog=None)` to hoist `load_division` out of bulk enumeration.
- `app/web/state.py` — `coach_overall`, `_universe_staff`, `staff_search`, cache + reset wiring.
- `app/web/server.py` — `/staff-search` route, nav item, `_active_nav` entries (+ two fixes).
- `app/web/templates/staff_search.html` (new).
