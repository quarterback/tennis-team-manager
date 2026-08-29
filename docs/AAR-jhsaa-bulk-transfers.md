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

## 3. The reserve-cohort FINDER (`/jhsaa/cohorts`, "Cohorts" on the rail)

The read-only half of reserve-cohort mobility
(`BRIEF-jhsaa-reserve-cohort-mobility.md`): the tool that answers "who is
carrying a Rockridge B, and where could it play?". `jhsaa.reserve_cohorts`
builds the gender's NEXT-season rosters (same freshman-aware rule as the
proposer) and the pure matcher `jhsaa._find_cohorts` reads three things off
them:

- **Sources**: programs whose top `RESERVE_COHORT_SIZE` (8, adjustable 4-12)
  reserves — the players below the league lineup's 11 — average to a
  varsity-caliber unit. `plays_like` is the HIGHEST class whose median team
  strength the cohort's mean clears, walked down `LADDER_GROUPS` (a GB group
  compares within itself only). A `weak varsity` flag marks a source whose own
  lineup is below its class median — those reserves may just belong in the
  lineup at home, per the brief's "who does not belong" list.
- **Hosts**: each class's weakest programs by best-nine mean, shaped per the
  brief — `rebuild` (≤1 player at class level), `core + void` (2-4 real varsity
  players, then the cliff a cohort fills), else `middling`. "At class level"
  means at/above the class's median team best-nine mean — one yardstick for
  every column on the page.
- **Suggested hosts per source**: the 3 weakest hosts in the fit class and one
  below, each with the COMBINED best-nine (cohort + the host's whole roster)
  ranked against that class's real field ("would rank ~#11 of 93") — the
  lineup-lab question asked of a real merger. Suggestions, never picks: the
  brief is explicit that different experiments want different drops.

Team strength everywhere is the **best-NINE mean** (`VARSITY_CORE`), not the
full 11 — the 3S/4D league lineup seats ranks #10-#11 at S2/S3, and the
`REST_GAP` machinery already measures teams on the top-nine mean.

Each source row expands to its cohort players, every one carrying the same
`jh_bulk_check` checkbox as the other boards — so "send this cohort to a host"
is: expand, check all eight, type the host into the bulk form, land on the
batch, apply. ‼️ A move made this way is an ORDINARY PERMANENT transfer. The
loan LIFECYCLE — one-season presumption, source recall rights at the next
rollover, host-senior clearing before placement — is deliberately not built;
it needs its own cohort record (`{source, host, year, members, per-player
resolved state}`), not more `jhsaa_transfer` rows, and a recall step at the
offseason ladder. If it is ever built, this finder is its front end and the
batch is still its write path.

Costs: one full-gender build behind an explicit `find=1` button (measured
5.7s warm on the 2039 boys), computed into locals, no new cache, no writes.
Sanity numbers from that run: 65 boys' sources, the top ones 9A/8A/6A programs
with ~49-51-mean cohorts playing like 3A/4A — the Rockridge shape the brief
predicted, visible without an export.

## Nothing loads until you ask (owner rule 2026-08)

The scouting boards used to pay the full-association census on every tab
click ("preloading a bunch of kids I don't need"). Players, Mismatches, the
Lineup Lab and the Cohort finder now open instantly with their controls and
compute ONLY on an explicit submit (a hidden `find=1` on each filter form);
the dropdowns are served from cheap statics (`GROUPS`, `load_schools`
districts), never the census. The cohort finder's sources are filterable
(source class, min cohort OVR) and PAGINATED — the first version hard-sliced
at 40 and silently hid the rest of its own reported count. The check-all
toggle (`jh_bulk_all`) is scoped to `this.closest('table')`, never the
document — squads and the candidate pool share a page, and a page-wide
toggle queued rows the reader never saw.

## Deliberately not built

The briefs describe four separate markets (opportunity clearing · blocked
talent · reserve-cohort/affiliate loans · top-end portal). Opportunity
clearing got a generator and reserve cohorts got a FINDER; nothing here moves
a cohort as a unit with recall rights — that transaction shape (source gets
first call after graduation; host seniors get cleared first) needs its own
lifecycle state, not more rows in this batch. Do not bolt it onto
`clearing_proposals`; the briefs are explicit that mixing the markets is how
the 2039 experiment went wrong.

Also deliberately absent: any automatic apply at the rollover. The generator
proposes; the owner applies. If a true auto-rung is ever wanted, it should
call `clearing_proposals` and write through `transfer_batch(apply=True)` as a
visible ladder step (the offseason-ladder rule), never inside `_finalize_year`.

## Tests

`tests/test_jhsaa_bulk_transfers.py` — the clearing matcher pure
(lateral-first, band-before-drop, one-level-at-a-time, arrival caps,
dominance-as-last-resort, freshman-aware projection, GB lateral-only), the
cohort finder pure (the Rockridge shape is flagged with its `plays_like` and
suggested hosts; host shapes classify), plus the routes' empty-state contract
(bulk POST with nothing checked, propose with no archive, `/jhsaa/cohorts`
cold).

## Deferred heavy builds (owner rule 2026-08 — "keep on performance")

Gating alone was not enough: the Search/Build/Find/Propose clicks still ran
10-40s of full-gender roster building ON the one gthread, so on the real
deployment they outlived the worker timeout and "only once loaded
successfully". `server._jh_deferred` generalises the lab's background-job
idea: the build runs in a daemon thread that publishes into the function's
own memo cache; the request waits ~2.5s and either proceeds (cache hit) or
answers a light page that refreshes the SAME url every 2.5s until the cache
is warm. Applied to the census boards (Players / Mismatches / Lineup Lab),
the cohort finder, the underplayed candidates search, and Propose (whose job
KEEPS its result, keyed on the transfer fingerprint so an Apply invalidates
it). The batch POSTs cannot show an interstitial, so the transfers page GET
fire-and-forget warms `roster_pid_index` for both genders while the owner is
still reading. Measured end-to-end: first click answers in 0.0s, results land
on the ~8th refresh (~22s of background build), every later search ~0.5s.
