# AAR — Injuries: dice rolls on talent + a lever that forces depth

**Date:** 2026-06-22
**Scope:** New `app/injuries.py`, lineup filtering in `season.py`, per-save
persistence + rolling in `seasonmode.py`, and a medical-redshirt rollover in
`world.py`. This is the **one deliberately non-deterministic** corner of the
engine.

## The ask

> "How do we model injuries to use them as dice rolls on talent as well as a way
> to force teams to use depth?" … "I never wanted a deterministic sim — an agent
> engineer decided it and it's just been passed down as lore. Save scumming is
> perfectly acceptable and I'm the only player."

Parameters (owner's spec):
- Roll **per dual**.
- **~0.5 starters** hurt at any given time.
- **1-in-100** injuries are **season-ending** — those players need a 5th-year
  **medical redshirt** to come back.
- Otherwise out **1–6 duals**.
- Injuries are **common**.
- **True randomness** (real entropy, not a seed).

## Design

### Where injuries live by layer
- **Dice** — `app/injuries.py` (pure-ish; owns calibration + RNG only).
- **Lineup filter** — `season.coach_lineup` drops injured pids → the coach pulls
  up the next body → depth finally matters. Threaded through `dual_between`
  (`unavailable_home/away`), which also now returns `home_played`/`away_played`
  (the pids who actually competed) so the caller rolls on exactly them.
- **Persistence** — `seasonmode.py` `injuries` SQLite table, **per season_id**
  (i.e. per save). Injury state must NEVER ride on the Prospect object:
  `build_roster` Prospects are globally cached and shared across saves, so a flag
  on them would leak everywhere. The dice operate on cached Prospects read-only
  (durability inputs); all mutable "who's hurt, how long" lives in the save.
- **Medical redshirt** — `world.graduate` grants a returning RS year.

### Calibration (the numbers, and why)
`injuries.py`:
- `BASE_RATE = 0.025` per-dual chance for an average-durability starter.
- `durability(p)` ∈ 0..1 from stamina/recovery/strength/flexibility, minus a
  sliver for very high competitiveness (grinders push through and break more).
  Never feeds the match engine.
- `injury_rate(p) = BASE_RATE × (1 + 0.6·(0.5 − durability))` — a **narrow**
  swing so the tough break less but nobody is immune.
- Severity: 1% → season-ending (`-1`); else uniform **1–6** duals.

**Prevalence math:** steady-state hurt ≈ rate × mean-duration. With rate ≈ 0.025
and mean duration 3.5 (uniform 1–6), per-starter ≈ 0.0875, ×6 ≈ **0.52** hurt at
any time. Measured across divisions (seeded sim, top-6 per team): D1 0.40 ·
D2 0.47 · D3 0.53 · D4 0.52 — league avg ~0.48, on target. (Stronger programs are
more durable, so they sit a touch fewer — a feature.)

### Recovery model
A short-term injury is "out for N of the **team's** duals." Each dual a team plays
burns one dual of recovery for its hurt players (`_recover_team`); at zero they're
healed (row removed). Season-ending injuries don't tick — they're out until the
medical redshirt next year.

### Medical redshirt → RS class tag
`world.graduate(rosters, redshirts)`:
- A season-ending pid does **not** advance a class — it **repeats** it carrying an
  `RS-` tag that **persists until graduation**: a hurt Jr replays as **RS-Jr**,
  then **RS-Sr**, then graduates → a 5th year of eligibility. A hurt Sr returns as
  **RS-Sr** (their 5th year) rather than graduating.
- The tag is **cosmetic eligibility flavor only** — it never touches the match
  engine. Per the owner: "the RS can be ignored and matches to the year so the
  tool isn't confused by RS." So everywhere that keys off class year strips it via
  `world._base_class` ("RS-Jr" → "Jr"): graduation, `_save_graduates`,
  `_openings`, and the `scout_intel` class filter.
- Plumbing: `_finalize_year` collects `season_ending_pids` from every active
  universe's season and passes them to `_save_graduates` (so a redshirting senior
  is NOT recorded as a graduate) and `finalize_rollover` → `graduate`.

## Determinism / tests

Injuries ship **enabled** (real entropy). That would break the suite's
replay/determinism assertions, so an **autouse `tests/conftest.py` fixture turns
them off by default**; `tests/test_injuries.py` opts back in and **seeds** via
`injuries.seed_for_testing(...)`. `set_enabled(False)` makes `roll_injury` a
no-op (returns 0), so the deterministic bulk paths are untouched.

`tests/test_injuries.py` covers: durability/rate bounds, severity bounds,
~0.5 prevalence, ~1% season-ending share, lineup drops the injured (depth pulled
up), `dual_between` reports who played, seasonmode persistence over a full
division-season, and the RS rollover (repeat+tag, persist, graduate, senior 5th
year).

## Injury log UI

The `injuries` table is now an **append-only event log** (not a per-pid state row):
columns `id, season_id, pid, school, name, week, tag, total, duals_remaining,
season_ending`. A row is **kept after the player returns** (duals_remaining hits 0)
so the log shows returned injuries too; a fresh injury inserts a new row (re-injury
is its own entry). The lineup filter / recovery still key off "active" =
`season_ending=1 OR duals_remaining>0`. An `init_schema` migration drops the old
shape (injury state is per-save and cheap to re-accrue, never authoritative).

- `seasonmode.injury_log(season_id, school=None)` → display entries with a
  **length** (`"N duals"`, or `"Season"` for season-ending) and a status label
  (Season-ending / Out — N more / Returned), active entries first.
- `state.injury_rows(division, gender, school=None, conf_filter="All")` joins
  school→conference + crest for the views.
- **Per-program** (`/teams?school=…`, `teams.html`): an "Injury Log" panel in the
  side column. Leads with **matches left** (`left`: "N of M left" while out, "Out
  for season", or "Returned") — the actionable number at a program level — with
  the week + total length as the secondary line.
- **League-wide** (`/injuries`, new `injuries.html`): a sortable table **grouped
  by team** with a **conference dropdown** (and the division selector), colored
  status dots (out / season-ending / returned). Added to the World nav group.

## Notes / not done

- Injuries roll in the **gameplay path** (`seasonmode._play_and_store`, which the
  world sim drives per universe). The bulk `season.run_season` (fixed season
  squads for ratings convergence) is intentionally **not** an injury path.
- League mode (`app/league.py`) has its own graduate loop and isn't an injury
  path, so it never sees RS tags; left as-is.
- The web UI shows `class_year` as a plain string, so RS tags render for free; no
  template change needed.
