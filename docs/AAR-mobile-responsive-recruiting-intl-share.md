# AAR — Mobile responsiveness, recruiting consistency, tunable international share

**Date:** 2026-06-14
**Scope:** One session, three shipped workstreams:
1. Kill the left↔right horizontal scrolling on phones across every page.
2. Fix recruiting so a signed recruit actually reads as signed — and collapse
   the recruit/junior surfaces onto the single active class the sim signs.
3. Add a per-league knob for how international the incoming recruit pool is.

Commits (branch `claude/fervent-archimedes-xo35i7`):
- `d6e40b8` Fix mobile horizontal-scroll: let grid/board items shrink
- `e6a3de7` Recruiting: one active class, and signed recruits show as signed
- `ee8aadb` Onboarding: make recruit international share tunable

---

## 1. Mobile horizontal scroll

### Why
On phones the whole page scrolled sideways on the dense pages — the
"severe scrolling right to left" report. The shell already had an
`overflow-x: hidden` safety net plus per-page media queries, so it *looked*
handled, but content was still overflowing (clipped on the body, and on real
mobile Safari `overflow-x:hidden` on `<body>` is unreliable, so it scrolled).

### Root cause
The two-column boards (`/data`, `/editor`, `/teams`, `/recruiting/hub`, the
dual result) are CSS grids. A grid item defaults to `min-width: auto`, so it
cannot shrink below its content's min-content width. Each board column holds a
`.bl-table` inside `.bl-tablescroll` with a `min-width` (640px on mobile). The
table's min-content forced the `1fr` track to ~640px+, which overflowed the
viewport — instead of the overflow staying inside `.bl-tablescroll` (which has
`overflow-x:auto` and is meant to scroll on its own).

Confirmed live at 390px: `.al-portal-grid` collapsed to a single 362px column
correctly, yet the `1fr` track resolved to **644px** because the `.bl-panel`
grid item had `min-width: auto`.

### Fix (`app/web/static/css/app.css`, `almanac.css`, `dual_result.html`)
- Give grid/flex items a `min-width: 0` floor so the inner `.bl-tablescroll`
  owns the overflow: `.bl-board, .bl-panel, .bl-board-grid > *,
  .al-portal-grid > *, .al-hero > *`.
- Collapse `.bl-board-grid` to **block flow** below 880px rather than a single
  `1fr` track (a `1fr` track keeps a content-based minimum and still
  overflowed; block flow takes the container width cleanly).
- Let toolbar action clusters and `.bl-scorehdr` pill rows wrap; give
  `.al-leadrow` / `.al-leadname` `min-width: 0` so long names truncate.
- The dual-result Re-run / Change-teams buttons were `width:100%` + `flex:1` in
  one row and couldn't share it; made them `flex:1 1 130px; min-width:0` and
  let the row wrap.

### Verified
Playwright sweep of **every route** at 320 / 360 / 390 / 414px: **0 page-level
horizontal overflow**. Remaining in-card horizontal scroll is confined to
`.bl-tablescroll` (intended for wide stat tables). Desktop two-column layouts
unchanged (verified side-by-side at 1280px).

---

## 2. Recruiting: signed recruits never read as signed

### Why (reported)
A recruit listed in the Signing Tracker showed **Uncommitted** on her profile,
her dreamsheet favoured a different school than the one she signed with, and a
signed player was still sitting in the recruiting pool as if open. "Once you
sign, the player page should show they signed — I have yet to see it."

### Root cause — three defects, all "board and sim read different things"
1. **Disjoint classes by gender vocab.** `recruit_class()` (and pids, via
   `make_pid`) keyed generation on the raw gender string. The sim's
   `national_class` uses world-vocab (`"women"`/`"men"`) while the web board
   uses juniors-vocab (`"female"`/`"male"`), so they built **two different
   classes with different pids**:
   `make_pid('recruit',2027,'women',0)` ≠ `make_pid('recruit',2027,'female',0)`.
   A signed recruit literally never appeared in the board's pool.
2. **Wrong-year commit guard.** `_apply_committed_flag` compared the integer
   season index `w["year"]` (0,1,2…) to a calendar `grad_year` (2026…), so the
   guard `w["year"] != grad_year` was always true and it **always cleared** the
   committed flag.
3. **Future classes leaking in.** Recruit/junior routes defaulted to a
   hardcoded `grad_year = 2026`, but the sim signs the
   `BASE_YEAR + year + 1` = 2027 class. The board showed one class while the
   tracker signed another, and the year dropdown invited generating 2028/2029.

### Fix (`app/world.py`, `app/web/state.py`, `app/web/server.py`,
`recruit.html`, `tests/test_web_recruiting.py`)
- **One class, one gender vocab.** Canonicalise gender at the single
  generation chokepoint (`_GENDER_CANON` in `recruit_class`): `"women"`/`"female"`
  (and `"men"`/`"male"`) resolve to the SAME class, so the sim's signing pool
  and the board are identical.
- **`world.recruiting_grad_year()`** — the one active class
  (`BASE_YEAR + world.year + 1`). Every recruit/junior route now pins to it and
  the future-year dropdown collapses to that single year (only this year's pool
  is recruitable and plays the junior circuit).
- **Stamp commitments correctly.** New `_signed_school_map(gender, grad_year)`
  guards on the active signing class and returns `{pid: school}`. Both the board
  path (`_apply_committed_flag`) and the profile path (`get_recruit`, which
  resolves signed players straight out of `world_signing` and previously
  skipped stamping) now set `committed` / `commit_school`.
- **Profile UI.** A signed recruit shows a green **"Signed with <school>"**
  banner (replacing the contradictory StrikePrediction favourite) and the signed
  school is flagged "Signed" in the College List.

### Verified (Flask test client, isolated DB)
Signed → `committed=True` and present on **both** board and profile, "Signed
with X" rendered, no "Uncommitted", no contradictory favourite. Unsigned stays
"Uncommitted". Identical result for men and women. The dripping-signings model
is preserved (this was a consistency fix, not a timing change).

---

## 3. Tunable international recruit share

### Why
The incoming recruiting class was hard-capped at `RECRUIT_INTL_SHARE = 0.32`
(68% American) — unrealistic for college tennis, which runs far more
international. College rosters already derive nationality from the band mix
(≈84% international under `tennis_global`), so the recruit pool was the outlier.

### Fix (`app/worldconfig.py`, `app/world.py`, `app/web/server.py`,
`onboarding.html`)
- `worldconfig.intl_share()` / `set_intl_share()` persist a per-league float
  (clamped 0–0.95). `DEFAULT_INTL_SHARE = 0.30` is the single default, which
  `world.RECRUIT_INTL_SHARE` now references.
- `recruit_class()` reads the live value (set before `start_new()` seeds, like
  the nationality band).
- Onboarding gains an **"International recruits"** selector (30%–80%);
  `/world/new` persists it. The nationality band still decides *which* countries
  the internationals come from.

### Verified
`intl_share = 0.70` → ~70% international recruits; `0.30` → ~32%; values clamp;
default 30% option selected. Generator responsiveness to the country mix also
re-confirmed (`asian_pro` floods JP/KR/PH; an `africa×8` multiplier surfaces
NG/ET/GH) while the share stays where the knob sets it.

---

## Behaviour notes / caveats (by design)
- **Nationality + international-share knobs are new-league only.** They're read
  at seed time, before `start_new()` builds the world; editing them does not
  retune an existing save.
- **International share targets the recruit pipeline**, not existing rosters
  (rosters already draw nationality from the band). Higher-international classes
  flow into rosters over seasons via intake.
- **Gender canonicalisation realigns the pool**, so the cleanest way to see the
  recruiting fixes is a fresh league. Players signed under the old vocab still
  resolve on their profile, but won't all match the regenerated board.

## Tests
Full suite re-run: pass except the pre-existing `test_name_pool_clean`
("Sétif"/"Leone" in `data/names/*.json`, untouched here) and two
`test_overrides` errors that were a DB lock from a concurrently-running dev
server (green once it's stopped). `test_web_recruiting` updated to assert the
active-class behaviour instead of the old hardcoded 2026.
