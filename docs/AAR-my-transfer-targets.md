# AAR — My Transfer Targets (Fit Finder, inverted) + team-picker by conference

> **Status:** shipped. A coach-facing **My Transfer Targets** board lists the players who'd
> upgrade YOUR roster — the inverse of the per-player Fit Finder, scoped to the one program the
> user coaches. Plus a small usability fix: the team viewer's picker gets a **conference filter**
> and **alphabetical** schools.

---

## 1. My Transfer Targets (`scout_intel.targets_for_my_program`)

The existing **Fit Finder** (`fit_targets`) answers "for this player, which programs fit?" The
owner wanted the reverse, and only for their chosen team: **"for MY school, which players out
there are a fit?"**

- **Anchor:** `worldconfig.user_program()` (the coached division/school/gender). No program picked
  → the page shows a "pick a program first" prompt, so it's genuinely one-program-scoped — never
  computed across the league.
- **Mechanic (fit_targets flipped):** take my current top-6 by ability; for every player NOT on my
  team, project the lineup slot they'd claim — `slot = 1 + (# of my top-6 better than them)`. Slot
  ≤ cap → a target.
- **Impact filter (the key tuning):** with the compressed talent almost anyone clears a weak No. 6,
  so a raw slot-≤-6 net returned **1,337** fits for USC. An `impact` control trims to the
  meaningful ones — **Top-3 starter by default** (→ 163), widen to *Any starter (Top-6)* or narrow
  to *Instant No. 1* (→ 55).
- **Per row:** player + current team/division + their line there · talent · STR · **FITS AS** (slot
  label on my team) · **UPGRADE OVER** (who they'd leapfrog, or "open slot") · a ▲/▽ chip for
  poaching from a higher/lower division. Sort by best fit / ceiling / STR; filter by the target's
  current division; upgrades-only toggle.
- Nav: **Analytics Bureau → My Transfer Targets**. Route `/intel/my-targets`.

**Verified:** coaching USC (D1 W), top-6 read correctly; 163 Top-3 fits / 55 Instant-No.1;
division filter (D2 → 13) and upgrades toggle work; page renders 200; no-program empty state shows.

## 2. Team viewer — conference filter + alphabetical picker (`/teams`)

The team-detail picker listed every school in **ranking order** with no way to narrow, so finding a
team was hard even by typing. Fixed the picker (route + `teams.html`):

- A separate **Conference** dropdown (All + every conference in the division), built from each
  program's `conf_abbr`.
- The **Team** dropdown is now **alphabetical** and **filtered to the chosen conference** (the
  current team is always kept selectable). Both submit on change.

**Verified:** D1 women → 379 schools A→Z; conf filter narrows correctly (A-10 → 11, SEC → 17,
Pac-16 → 16), each alphabetical.

## 3. Files touched

- `app/scout_intel.py` — `targets_for_my_program` (+ `_IMPACT_SLOT`).
- `app/web/server.py` — `/intel/my-targets` route + nav item + active-id; `/teams` conference
  filter + alphabetical schools.
- `app/web/templates/intel_my_targets.html` — **new**.
- `app/web/templates/teams.html` — Conference dropdown.
