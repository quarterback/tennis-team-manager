# AAR — Recruit-page redesign + Analytics Bureau

**Date:** 2026-06-14
**Scope:** Two related pushes off the same session. (1) Rebuild the recruit
profile + recruiting board to the visual depth of a real recruiting service
(247Sports/On3) — the existing pages were functionally rich but visually flat.
(2) Build an additive **Analytics Bureau** — a god-mode player-intelligence
platform that reads the engine's hidden truth to find underplaced talent,
scholarship misallocations, and best-fit landing spots.

## Why
In-session, with side-by-side 247Sports/ESPN screenshots: "the design is far
worse than what I shared — use my examples and redesign." Then two scoped
follow-ups: a team's signed class only surfaced 5★/4★ ("show 5 through 1 star
… not realistic"), and there was no way to see *uncommitted* prospects only.
Separately, a feature request for a talent-analysis layer over both recruits
**and** rostered players — "players who are good stuck at the wrong level,
walk-ons who should be getting scholarships, where they'd be useful … a player
intelligence platform." The brief was explicit: god mode, true talent, **no
noise**, and built as an additive mod.

---

## Part 1 — Recruit profile + board redesign

### What shipped
- **Prospect hero** (`recruit.html`): dark gradient header with flag, hometown,
  HS, gold star line, tier chip, and a prominent STR + 4-yr projection. A
  committed prospect shows the school crest and a signed banner.
- **Dual rating cards**, mirroring 247's "247Sports / Composite" split:
  - A 0–100 **Play to Clinch Rating** with a NATL / state / points rank trio.
  - A 0.xxxx **Composite** with the two scouting reads + projection.
- **Crystal-Ball-style StrikePrediction panel**: favourite school crest, big %,
  a fill bar, and a HIGH/MED/LOW confidence read derived from how clear the
  leader is of the field.
- **Recruiting board** (`recruiting.html`): crest-rich, star-driven rows
  (initials avatar, gold star line, composite grade, committed-school crest),
  mobile-first; collapses cleanly under 760px.

### The numeric grade
`app/juniors.py:recruit_grade(rank, class_size) -> (rating, composite)`. A
rank-percentile power curve, `composite = 0.74 + 0.26·(1−q)^1.8`, clamped to
0.9999. Pure function of board rank, so the number is identical everywhere a
recruit appears. Lands on a believable scale: rank 1 → 100 / 0.9999, blue chip
~0.98, 4★-top ~0.95, 3★ ~0.88, 2★ ~0.79.

### Follow-up: 5★→1★ team spread
The team class only exposed 5★/4★ counts — at the *top* programs (Duke,
Stanford) that's genuinely all the class is. The fix was a **display** fix, not
a sim change: `state.star_breakdown()` returns per-tier counts 5→1, rendered as
a colour-coded `rc-spread` chip on both the team class KPI strip and the Signing
Tracker's class table. Verified against a real 13-week cycle: nationally the
class signs **5★:75, 4★:143, 3★:200, 2★:265, 1★:317** — the sim was already
realistic; only the surface hid the tail. A developmental program (Valparaiso)
now shows e.g. `[4★:1, 1★:1]`.

### Follow-up: "Available only" filter
`recruit_rows(..., unsigned_only=)` + a Status select on the board excludes any
committed prospect (`status=unsigned`), so you can work the board down to who's
actually still on the market.

### Files (Part 1)
- `app/juniors.py` — `recruit_grade`.
- `app/web/state.py` — grade wired into `recruit_rows` + `recruit_profile`;
  `unsigned_only` filter; `star_breakdown`; full tier counts on
  `team_recruiting_class` and `signing_tracker`.
- `app/web/formatters.py` — `state_abbrev` filter; registered in `server.py`.
- `app/web/static/css/recruit.css` — **new** (hero, rating cards, crystal ball,
  board rows, star spread).
- `app/web/templates/_stars.html` — **new** (`stars` + `spread` macros).
- `recruit.html`, `recruiting.html`, `team_recruiting.html`,
  `signing_tracker.html`, `base.html` — redesigned / wired.

---

## Part 2 — Analytics Bureau (`app/scout_intel.py`)

### Design stance
Read-only analytics over data that already exists. **No simulation, no
mutation.** The platform reads each player's true ceiling
(`Prospect.ceiling_overall()` → STR) with **zero scouting fog** — never the
noisy `scouting_report`. Talent is the absolute 20–80 ceiling, so it is
directly comparable across D1/D2/D3 — that comparability is the whole reason
"stuck at the wrong level" is computable.

### The scan
`scan(gender, seed)` walks every program in every division, builds each roster
(`ncaa.build_roster`), and records per player: current vs true STR, upside,
walk-on/scholarship status, lineup slot, and their program's PI rank. Then two
global tables:
- **talent percentile** — each player's true-ceiling rank among all same-gender
  players.
- **program-level percentile** — each program's rank by the mean true ceiling
  of its top 6 (its singles ladder), blended into one ladder across divisions.

Memoised per world snapshot `((world_id, year, week), gender)` like the roster
caches. ~8.7k women / similar men, ~1.1k programs, **~3.4s cold**, instant warm.

### The three reports
1. **Underplaced Talent** (`/intel/underplaced`) — `placement_gap = talent_pct −
   program_level_pct`. Flags players ≥ 0.18 gap and ≥ true grade 46 (3★+
   talent), sorted by mismatch. Each carries a "deserves a program like X"
   computed by matching their talent percentile against the program ladder. A
   visual gap bar (blue = talent, black tick = program level) makes the mismatch
   legible. Verified: D3 players surface as deserving D1.
2. **Scholarship Watch** (`/intel/scholarships`) — walk-ons whose true ceiling
   out-strips a *funded* teammate, with how many they out-talent and the
   equivalency their calibre would merit. D3 (no athletic aid) excluded.
3. **Fit Finder** (`/intel/fit/<pid>`) — for one player, every program where
   they'd crack the lineup *now* (by current ability), tagged Instant No. 1 /
   Top-3 starter / No. N starter, with team STR, ▲ step-up marker, and aid. This
   is the "talent matching" half — where the ceiling would actually be deployed.

A **Bureau HQ** (`/intel`) ties them together with KPIs and previews; every
player on every board links to their Fit Finder.

### Files (Part 2)
- `app/scout_intel.py` — **new** engine (scan + three reports, memoised).
- `app/web/server.py` — "Analytics Bureau" nav group; `_active_nav` entries;
  four routes; a `crest` jinja global.
- `app/web/templates/intel_hub.html`, `intel_underplaced.html`,
  `intel_scholarships.html`, `intel_fit.html` — **new**.
- `app/web/static/css/recruit.css` — Bureau hero/KPI/gap-bar styles.
- `app/web/templates/dashboard.html` — **Analytics Bureau** quick-card so it's
  reachable from the dashboard, not only the nav.

---

## Accessibility / wiring
- **Nav:** "Analytics Bureau" group (Bureau HQ · Underplaced Talent ·
  Scholarship Watch) in both the sidebar and top-nav.
- **Dashboard:** quick-cards for the Recruiting Board, Recruiting HQ, **and the
  Analytics Bureau**.
- All four Bureau routes + the redesigned recruit/board/team/signing pages
  render `200` against a live world; bad pid → `404`.

## Tests
`test_web_recruiting.py` passes in full. No new test added: the Bureau is a pure
read-side view (its inputs — rosters, ceilings, scholarships — are already
covered) and the redesign is presentational. **Pre-existing, not caused by this
work** (both reproduce on the clean branch base): `test_name_pool_clean`
(scraped-name junk in data files) and `test_web_awards::test_season_awards_structure`
when run *after* the recruiting tests (a shared-world ordering issue — passes in
isolation).

## Decisions / notes
- **Grade is rank-based, not STR-based** — so it can't drift out of step with
  the star tiers and national rank the board already shows.
- **Recommended aid uses `economy.offered_fraction`** (a calibre sticker price),
  so a walk-on can "merit ½" while out-talenting a full-ride teammate — that's
  the division's funded-slot pecking order, not a bug. User explicitly steered
  away from econ ("interested in talent maxing & matching not econ"), so this is
  left as-is and the scholarship board is the only econ-flavoured surface.
- **God-mode by design** — the Bureau is the omniscient counterweight to the
  fogged public board; using the true ceiling (not the scouting read) is the
  point, per the brief.

## Follow-ups (not done)
- Underplaced board could precompute the single best-fit destination inline
  (today it shows the percentile-matched "deserves" program; the true best fit
  is one click away in the Fit Finder).
- A class-year lens on the Bureau HQ (freshmen gems vs seniors stuck) and a
  per-team "talent efficiency" view (are you starting your best 6 by ceiling?).
- Recruit-pool coverage: the Bureau scans **rostered** players; folding the
  incoming recruit class into the same talent ladder would let it rank a
  signee's fit against current rosters directly.
