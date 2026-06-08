# AAR — Match Realism, Playing-Time Guarantee, Season-Mode Unification & Staged UI

## Segment summary

This segment started as a bug report on a player card — singles results showing
nonsensical "games" like `12-13 → W`, and a full season of results after simming
one week — and grew into closing out the architectural debt the prior AAR flagged
(`docs/AAR-onboarding-ui-pagination-awards.md`): the **baseline-vs-Season-Mode
duality**. Along the way the simulation itself was made talent-driven, every
roster player was guaranteed match time, scoring was corrected to real college
rules, and the season was turned into an explicit, pushable pipeline.

All work landed on `claude/peaceful-faraday-ah5sE`, on top of the awards/coaches
work merged from `main`. **130 tests passing** throughout.

## Post-project report — root cause (the "how did this ship?")

Two independent season simulations existed:

- the **baseline** (`app/season.py:run_season`, via `app/web/state.py:get_season`)
  — the *entire* season pre-simulated at once, for ratings; and
- **Season Mode** (`app/seasonmode.py`, SQLite, week-gated, driven by
  `app/world.py:advance_week`) — the real week-by-week world.

The read surfaces (player card, team page, dashboard, rankings, bracket, awards)
were wired to the **baseline**. So a freshly-advanced league rendered a finished
season, player records listed every match immediately, and honors were computed
from a *projected* season rather than what was actually played. This was a design
mistake — a pre-simulated stand-in should never have been the source of truth for
per-entity surfaces. The fix below retires it.

A second, narrower defect: the player card's "GAMES" column printed *total games
won/lost across the match* (so `12-13` could be a win). Tennis is scored by sets;
the set scores existed in the data but were never surfaced.

## What was built / fixed

### 1. Scoring display + read-surface leak (the original report)
- Player card shows **set scores** from the player's POV (`6-3 6-2`,
  `1-6 7-5 2-6`); W/L is consistent with sets won.
- `player_career` / `team_results` read Season Mode (week-gated), so results fill
  in only as the world advances.
- No-ad is now the default match format (`engine/format.py`), matching college
  reality (the live dual sim already ran no-ad via `ncaa_dual` / `pro_set_8`).

### 2. Match-engine realism — talent + grit + luck, not pure RNG (`engine/fast.py`)
The season sims in the fast (game-level) path, which decided each game with a
shallow coin-flip on the overall-rating gap and never used `stamina` or `mental`
situationally. Now:
- **Talent**: steeper slope (`skill_slope` 3.0→4.5) — the better player wins
  reliably; near-even gaps stay a coin-flip (0.02≈60%, 0.04≈71%, 0.10≈91%).
- **Stamina**: a fatigue edge that ramps with total games played, favoring the
  fitter player late.
- **Grit**: the `mental` gap swings decisive games (set/match points) and
  tiebreaks, mirroring the full engine's pressure/clutch model at game grain.
- **Luck**: a bounded modifier, not the dominant force.
Deterministic (one RNG/match, unchanged draw count). Full point-by-point engine
untouched. Clinch-at-4 kept (it's realistic; duals don't always sum to 7).

### 3. Playing-time guarantee (`app/season.py`, `app/seasonmode.py`)
Lineups picked the top 6 by live form with only stochastic bench rotation, so
walk-ons could go a season without a match.
- `forced_appearances`: deterministic `dual_id -> {pid}` giving every roster
  player one regular-season dual — weakest players to the most favorable
  (weakest-opponent) duals, spread one per dual.
- `coach_lineup` seats a guaranteed player into a **completing slot** (S1–S3
  always finish before a 4-point clinch) only if not already there, so
  aces/starters are undisturbed and the bench plays *up* against weaker teams.
- Result: **0 unplayed** across D1/D2/D3 by season end; lineups changed on ~11%
  of team-duals (mostly non-conference); fully deterministic on re-sim.

### 4. Season-Mode unification — retire the baseline (`app/seasonmode.py`, `app/web/*`)
Every web surface now reads the live season; nothing in the app calls
`run_season`/`get_season` (kept only as a test utility).
- New Season-Mode helpers: `power_index` (full RatingLine pi/apr/fqi/record),
  `conf_rank`, `bracket_field` (seed + run the NCAA field from live ratings,
  autobids once conf tournaments run, None in preseason), `conf_champions`,
  `national_champion`, and one-pass `player_records` (replacing per-player
  `LIKE` scans — the cause of an 11-minute test run, now ~1 min).
- `ranking_rows`, `dashboard_view`, `team_roster`, `team_budget`,
  `conferences_for`, `get_bracket` repointed; preseason falls back to ability
  order so a fresh league still renders. `season_match_view` + the dead
  `/teams/match` route removed (team results link to the season box score).
- **Awards repointed**: `honor_records` / `coach_honor_records` / `season_awards`
  recompute from Season-Mode results + champions instead of the baseline — so
  honors reflect what was actually played. Honors schema and the persistence /
  career-honors readers are untouched (per the staged-UI spec).

### 5. Staged season UI (`SPEC-staged-season-ui.md`)
- World hub shows a 5-stage stepper: regular → conference tournaments → NCAA →
  **awards** → offseason, with one dynamic primary action.
- The all-in-one advance is split: when every bracket finishes you push **🏅 Run
  awards** (stamps honors *before* rollover), then **Begin next season**
  (rollover). `world_advance` refuses to roll over until honors are stamped.
- Null-safe bracket page in preseason.

## Validation

- `pytest -q` → **130 passing** after each workstream (awards/honors/coaches now
  compute from a played season via the new `played_season` fixture — one
  completed D1-men season, keeping the suite fast).
- Fresh-world smokes: every surface (`/`, `/rankings`, `/teams`, `/bracket`,
  `/world`, `/player/<pid>`, `/season`) returns 200 at **preseason (week 0)** and
  after advancing — showing only played results, not a projected season.
- Playing-time: every `build_roster` pid has a completed match by season end,
  across D1/D2/D3; lineups deterministic on re-sim (identical `lines_json` hash).
- Staged transitions: season-complete → *Run awards* (stage→offseason,
  `awards_done`) → *Begin next season* (year advances, week 0). Verified
  end-to-end over a full world.

## What I did NOT change (honesty section)

- **`run_season` / `get_season` remain in the tree** as a test utility
  (`test_season.py`, `test_roster.py`) — no longer wired into any surface, but
  not deleted.
- **Doubles are still drawn from the singles six** (with per-coach pairing
  variation). "Doubles specialists" were explicitly de-scoped in favor of the
  playing-time guarantee.
- **Multi-year career history**: `player_career` still returns a by-year
  structure with only the current season-year populated (persisted past seasons
  would fill it) — unchanged from before.
- **Engine tuning is conservative**: `skill_slope` etc. are calibrated against
  the test ranges; real rosters cluster tighter in talent than synthetic tests,
  so the steep tail rarely fires in practice.

## Deferred / next

1. Multi-season player/coach history surfacing (the structure is ready).
2. Doubles model (serve+volley/net play) and doubles-specialist lineups.
3. Optional full point-by-point fidelity for high-stakes duals (postseason).
