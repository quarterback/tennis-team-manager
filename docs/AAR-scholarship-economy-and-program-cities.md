# AAR — Scholarship economy, program cities & persisted player origins

**Date:** 2026-06-07
**Scope:** Bring over baseball's (o27v2) economy concept as a college-tennis
**scholarship-equivalency** system, give every program a home **city**, and
close the **persistence gap** where generated player origins were dropped by
the DB schema.

## Why
Three things the design assumed but the code never had:

1. **Economy.** `docs/DESIGN-college-tennis-sim-fork.md` §5 calls for porting
   o27's `currency.py` into a per-program scholarship budget (equivalency
   caps, fractional offers). None of it existed — scholarships were a single
   binary flag (`walk_on`), top-6 vs the rest.
2. **Program cities.** Players already carry generated hometowns (`flavor.
   roll_hometown`), but **programs had no location at all** — a team page was a
   name floating in space. Baseball generates a city for every club; tennis
   didn't.
3. **Lossy persistence.** `generate_prospect` rolls hometown / high-school /
   birthday / major / secondary-country, but the `players` table had columns
   for none of them, so anything written to disk lost its identity. The live
   web app hides this (it regenerates rosters in memory), but the persistence
   path was silently dropping the data.

Decision (with the owner): **scholarship-equivalency system, no currency
flavor.** College tennis runs on fractions of a scholarship, not money, so the
guilder/zora display layer from baseball was deliberately *not* ported — only
the budget/cap idea was.

## What shipped

### Economy — `app/economy.py` (NEW)
- **Real NCAA equivalency caps** per (division, gender): D1 men 4.5 /
  women 8.0, D2 men 4.5 / women 6.0, D3 0.0 (no athletic aid).
- **Fractional offers:** full / ½ / ¼ / ⅙, with labels.
- `allocate_scholarships(roster, division, gender, scholarship_slots=…)` —
  spreads the cap down the sorted roster, best player first, largest
  affordable fraction each time. So a D1 men's roster is **4 full + 1 partial
  = 4.5**, not eight full rides.
- `budget_summary()` — the team-page ledger (cap / committed / open / full /
  partial / walk-on counts).
- `offered_fraction()` + `prestige_pull()` — the sticker price a program would
  put in front of a recruit, and the no-money lever that lets Ivy / top-D3
  compete on brand.

### Wiring (deliberately conservative)
- `app/ncaa.py::_base_roster` / `build_roster` now call
  `economy.allocate_scholarships(...)` instead of the binary loop. **`walk_on`
  semantics are unchanged** (top `SCHOLARSHIP_SLOTS` = recruited core), so the
  league/transfer-portal logic and the existing `test_roster` invariant keep
  their meaning — the fractional `scholarship` is layered *on top*.
- `Prospect.scholarship: float` added.

### Program cities — `generators/cities.py` (NEW)
- `program_city(school)` → deterministic `(city, state)` from a weighted pool
  of ~90 real US college towns (Sun Belt / CA / TX corridor heavy). Pure
  function of the school name, so D1-men and D1-women "Texas" share a campus
  and it never drifts across loads.
- `Program` gained `city` / `state` / `.location`, populated in
  `load_division`.
- These are *believable, generated* locations, **not** the literal real
  campus — same posture as the generated player hometowns.

### Persistence — `app/db.py`
- `players` schema extended with `pid`, `school`, `division`, `class_year`,
  `hometown`, `high_school`, `birthday`, `major`, `secondary_country`,
  `region`, `academic_rating`, `recruit_stars`, `scholarship`, `walk_on`.
- `_migrate_players()` ALTERs the missing columns onto an older DB (SQLite has
  no `ADD COLUMN IF NOT EXISTS`).
- `save_prospect()` (pid-keyed upsert) + `load_player_row()` round-trip the
  full identity payload.
- `manage.py persist-rosters [--division D1 --gender men]` generates rosters
  and writes them to disk — exercises the path the live app skips. Verified:
  2,928 D1-men players persisted with intact hometowns / majors / aid.

### UI
- **Team page:** home city in the header; a scholarship-equivalency ledger in
  the notes (or a "no athletic aid — commitment slots" note for D3); the
  STATUS column now reads Full / ½ / ¼ / ⅙ / Recruited / Walk-on.
- **Player page:** Program + city row; Scholarship row showing the fraction.
- **Recruit page:** a SCHOL. column on the College List with the offered
  equivalency.

## Validation
- `pytest -q` → **102 passed** (3 new suites: `test_economy`, `test_cities`,
  `test_db_persist`; existing `test_roster` walk-on invariant still holds).
- `manage.py persist-rosters` round-trips origins + scholarships.
- Web smoke: D1 team/player/recruit pages render the new fields; the D3 team
  page shows the no-aid path.

## What I did NOT do (honest scope)
- **No recruit-decision engine / budget-constrained signing simulation.** The
  recruiting board's scholarship column is a deterministic *sticker price*, not
  the output of programs spending a shared budget against each other. Design §5
  envisions a full motivation-driven offer auction (port of o27 `trades.py` /
  `front_office.py`) — that's the natural next step and is left for later.
- **`app/league.py` portal logic still uses the binary `SCHOLARSHIP_SLOTS`
  model.** The fractional layer is recomputed on every roster build, so it's
  correct for display/season; making the multi-year portal spend fractional
  budgets would be a deeper change.
- **No currency flavor** (guilder/zora/money toggle) — intentionally, per the
  owner's call. The hook is there if a future "NIL" layer ever wants money.
- Program cities are generated, not the literal real campus locations.
