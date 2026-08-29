# AAR: JHSAA bulk transfers — select-and-submit + clearing-market proposals

**Landed:** 2026-08, branch `claude/bulk-player-transfers-up7x9j`
**Design inputs:** `docs/reports/BRIEF-jhsaa-opportunity-clearing-market.md`,
`docs/reports/BRIEF-jhsaa-reserve-cohort-mobility.md`,
`docs/reports/REPORT-2040-opportunity-clearing-class.md`

## The problem

The owner runs offseason waves of ~40-50 moves, mostly to get buried players
somewhere they will actually play. The options were: one player card at a time,
or delegating a wave to an agent — which sometimes sent players places the
owner did not want. The scouting tools that FIND the candidates (Lineup Lab,
Talent Mismatch board, the underplayed Candidates board) had no way to ACT on
what they showed.

## What shipped — two things, one funnel

Everything lands on the transfers page's existing **Batch tab** (preview →
apply, backed by `jhsaa.transfer_batch`). Nothing new writes transfer rows;
nothing applies without the owner clicking Apply on a slate they can read and
edit. That is the design center: **the boards select, the batch decides.**

### 1. Select-and-submit from the boards

The Lineup Lab (`/jhsaa/lineup-lab`), the Talent Mismatch board
(`/jhsaa/misapplied`) and the HS Transfers → Candidates tab each grew a
checkbox column with a check-all header box. Check any set of players,
optionally type ONE shared destination, and "Send checked to transfer batch"
posts to `POST /editor/jhsaa-transfer-bulk`, which prefills the Batch tab with
`pid, destination` lines — each preceded by a `# Name — 9A School (10th, OVR
51…)` comment so the slate stays readable when edited by hand — and runs a
preview when a destination was given. The bulk route itself applies **nothing**.

Mechanics worth knowing:

- **The checkbox rides OUTSIDE any row form** via the `form="jhbulk"`
  attribute — the fall portal's idiom (`fall_portal.html`), needed because the
  Candidates tab's rows already contain their own per-row Move forms and HTML
  forbids nesting.
- Each checkbox value is `pid|display note`; the route partitions on the first
  `|`. The note becomes the batch comment line.
- Macros live in `_jhsaa.html` (`jh_bulk_check` / `jh_bulk_all` /
  `jh_bulk_form`) so the three surfaces share one implementation.
- ‼️ The bulk route reads the gender off the FORM (`g`), never
  `_jh_scope_args()` — the documented POST-has-no-query-string trap
  (`editor_jhsaa_family`).
- Both-gender boards ("Both" on Lab/Mismatch) work because `transfer_batch`
  resolves each pid's gender itself; the destination datalist is the union of
  both genders' school names there.

### 2. "Propose destinations" — the clearing-market generator

On the Candidates tab, once candidates are found, one button
(`?find=1&propose=1`) runs `jhsaa.clearing_proposals` over ALL of them and
prefills + previews the batch. The owner reviews, redirects or deletes lines,
then applies — the generator is a drafter, never an actor.

The matcher (`jhsaa._propose_destinations`, pure and unit-tested without a
roster build) implements the clearing-market brief:

- **The ladder is `CLEARING_LEVELS`, not `GROUPS`**: 9A/8A are one competitive
  level, 7A/6A another, every boundary below is real. `GB_GROUPS` are
  lateral-only islands.
- **Lateral first**: own class, then the level-mate class, then down ONE level
  at a time (capped by the "max drop" pref, default 2) — never straight to the
  bottom.
- A "home" is a projected slot inside the varsity lineup
  (`lineup_need("regular")` = 11). Within a tier the pick is the slot nearest
  the middle of the lineup.
- **Arrivals stack**: each placement is added to the destination's ladder and
  counts against a per-school allowance (default 2), so a wave spreads instead
  of piling onto one program.
- **Dominance on a drop is a last resort, not a bar**: becoming the outright
  new #1 one level down is penalised in the sort, but if it is the only home,
  the player gets it — the market's promise is that everyone lands somewhere.

### ‼️ Freshman-aware means "project against NEXT season's roster"

The owner's stated risk: move a kid, and a freshman shows up and takes the
spot anyway. No new mechanism was needed — `build_roster(school, next_year,
salt)` already contains that year's incoming freshman class and everyone's
development roll, so `clearing_proposals` builds the whole gender at
`next_year` (the move's effective season) and projects every "would they
actually crack the lineup?" against THAT ladder, including the candidate's own
next-year OVR (looked up by pid from the same build). The board's current-season
OVR is what the report displays; the projection never uses it.

## Costs and cautions

- `clearing_proposals` is a full-gender roster build (~seconds) plus
  `transfer_batch`'s two pid-index builds — explicitly button-gated, never on a
  default page load (the one-gthread rule).
- No new cache, no new table, no new write path: proposals are computed into
  locals and rendered; the only writes are the same `set_jhsaa_transfer` rows
  the player card makes, on Apply, via the batch route that already calls
  `reset_all()`.
- The candidate pool is `world.jhsaa_underplayed` — 9th/10th graders under a
  match ceiling, read off the archive. Widening the pool (juniors, JV-only
  players, "blocked talent") is a change to THAT board, not to the matcher.

## Deliberately not built

The briefs describe four separate markets (opportunity clearing · blocked
talent · reserve-cohort/affiliate loans · top-end portal). Only opportunity
clearing got a generator here. Reserve-cohort mobility moves 7-10 strong
players as a UNIT with recall rights — a different transaction shape (source
gets first call after graduation; host seniors get cleared first) that would
need its own lifecycle state, not more rows in this batch. Do not bolt it onto
`clearing_proposals`; the briefs are explicit that mixing the markets is how
the 2039 experiment went wrong.

Also deliberately absent: any automatic apply at the rollover. The generator
proposes; the owner applies. If a true auto-rung is ever wanted, it should
call `clearing_proposals` and write through `transfer_batch(apply=True)` as a
visible ladder step (the offseason-ladder rule), never inside `_finalize_year`.

## Tests

`tests/test_jhsaa_bulk_transfers.py` — the matcher pure (lateral-first,
band-before-drop, one-level-at-a-time, arrival caps, dominance-as-last-resort,
freshman-aware projection, GB lateral-only) plus the routes' empty-state
contract (bulk POST with nothing checked, propose with no archive).
