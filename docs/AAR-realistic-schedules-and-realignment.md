# AAR — Realistic 25-dual schedules (+ the conference realignment behind them)

## What it was before
**Schedules were thin and unreliable.** The regular-season generator aimed for a
flat 7 non-conference duals per team via a random-dart matcher (`rng.choice`,
hard-reject on a prestige roll, `tries < 140`). It frequently fell short: across
a full D1 men's slate the league averaged **~17 duals/team with a min of 9** —
hundreds of teams under a believable 18-dual season. Conference play was a single
round-robin for everything with ≥8 teams (double only under 8).

**The conferences themselves were the real 2024 alignment** — a rump Pac-12, Cal
and Stanford in the ACC, the SWAC and MEAC as separate low-majors, etc.

## What changed

### Conference realignment (data/ncaa/d1_*.json, d2_*, d3_*)
A run of user-directed moves rebuilt the D1 map (each verified to keep every
roster summing correctly with no school double-listed):

- **Revived the Pac as the Pac-16** — the classic twelve plus Boise State,
  Colorado State, Gonzaga, San Diego State. Power-conference prestige (0.78) and
  back in the P5 display tier. The old rump's leftovers (Fresno State, Texas
  State, Utah State) went to the Mountain West.
- **New Yankee Conference** (BC, Syracuse, Rutgers, Pitt, West Virginia, Virginia
  Tech, Louisville, Temple, Notre Dame, UConn, Penn State — Cincinnati later moved
  on to the ACC). Seeded a strong mid-major (0.64).
- **Merged the SWAC + MEAC into the Heritage League** (18 teams, low-major prior
  kept at 0.34).
- Assorted moves: Maryland back to the ACC; Missouri/Kansas/Virginia/North
  Carolina to the Big Ten; SMU/Memphis/Florida A&M/Alabama State to the Big 12;
  Tulane/Cincinnati/NC A&T to the ACC; Saint Louis/Davidson to the Big East;
  Wichita State/Loyola Chicago to the MVC; Rhode Island to America East; Fordham
  to the Patriot; George Mason/Richmond to CUSA; Howard + William & Mary to the
  Ivy; Hampton/Northeastern/West Florida to the A-10.
- **Cross-division promotions:** the University of Chicago D3→D1 (Big Ten), and
  Tampa / Valdosta State / Rollins D2→D1 (ASUN). Their crests, locations, and
  (Chicago's) academic-flagship rating carry over. D1 now totals **370** schools
  per gender.

### The scheduler (app/seasonmode.py)
Rebuilt to hit a realistic slate **reliably**:

- **Target-driven slates.** Every team now plays toward `TARGET_DUALS = 25`.
  Conference carries the larger share and non-conference fills the rest
  (`25 − conf_games`), so the total lands on 25 regardless of league size.
- **Conference-heavy by design (`CONF_SHARE = 0.60`).** Each league's slate aims
  for ~60% conference so the standings actually mean something. A round-robin
  (double under 10 teams) is the base; leagues too small to reach 60% that way are
  **padded with extra intra-conference duals** beyond the round-robin (capped at
  `MAX_CONF_MEETINGS = 3` meetings per pair). Result: conference share averages
  **~61%** (min ~48% for one parity-edge team, max ~64%), up from ~49%.
- **Double round-robin under 10 teams.** `CONF_DOUBLE_MAX` 8 → 10, so sub-10
  leagues play home-and-away (they fit). Bigger leagues play a single round-robin
  plus any padding needed to reach the share.
- **A matcher that actually fills.** The random-dart loop is replaced by a
  deterministic greedy: each round, every still-short team takes its best
  available cross-conference partner, with the old cupcake-scheduling flavor kept
  as a *preference weight* (heavyweights still avoid each other and load up on
  mid/low-majors) rather than a hard reject — so targets are met instead of
  abandoned. Biased toward whoever else still needs games, so the league
  converges.
- **Tighter weeks.** Conference play is gated behind each team's *own* last
  non-conf week (not a global barrier), and `MAX_PER_WEEK` 2 → 3 (a 3-dual
  weekend), so a 25-dual slate packs into ~**12 weeks** instead of stretching to
  18-21.

## Why this is better
- **Every team plays exactly 25 duals** (verified league-wide, both genders),
  with conference the clear majority (**~61%** on average) — a believable
  Division I season whose conference standings carry real signal, instead of a
  thin, ragged, near-even slate.
- The season fits a realistic **~11-12 week** window.
- As a bonus, the previously-flaky `test_higher_seeds_usually_advance` now passes
  consistently: more duals per team means less variance, so higher seeds advance
  as expected.

## Verification
- League-wide: min/max/mean duals all **25**; total weeks **12**; full season
  advances cleanly to a crowned champion.
- `tests/test_seasonmode.py` and `tests/test_season.py` — **all 10 pass**
  (schedule structure, non-conf-first/ends-in-conference, standings, seeding).
- Every realignment step validated: rosters sum correctly per division, no
  school in two conferences, both genders load.

## Files
- `app/seasonmode.py` — target-driven slate, greedy non-conf matcher, double-RR
  threshold, per-team conf gating, `MAX_PER_WEEK`.
- `data/ncaa/d1_men.json`, `d1_women.json`, `d2_*`, `d3_*` — realigned membership.
- `app/ncaa.py` — Pac-16 / Yankee / Heritage prestige priors.
- `app/web/state.py` — Pac-16 in the P5 display tier.
- `docs/calibration-season-schedule.md` — sim recommendations updated to the
  25-dual target.
