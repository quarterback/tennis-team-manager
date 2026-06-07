# AAR — Unified world, recruiting realism, lineups (PR #14)

Session retrospective for the work on branch `claude/awesome-ramanujan-mvMeN`.

## What shipped (committed + green: 90 tests)

1. **Box scores / team pages / schedule (commit 1).** Match records now store who
   played every singles *and* doubles court (pids, names, flags, set scores).
   Team pages gained a results rail; the schedule was restructured (date/week,
   vs·at, crests, conf tags, box-score links) with conference→team dropdowns;
   responsive CSS pass.

2. **Prestige + academics program model.** Every program carries `prestige`
   (athletic brand pull) and `academics` (academic profile) as stable [0,1]
   traits, separate from hidden per-season strength. Real priors for blue-bloods,
   Ivies, NESCAC/UAA/Centennial D3s, and the service academies.

3. **Recruiting realism.** Recruit appeal blends athletic fit (talent vs
   prestige) with academic fit (recruit academic rating vs program academics),
   so high-academic talent is genuinely drawn to Ivies / NESCAC / academies and
   recruits *above* their athletic station (a smart, strong kid can pick
   Swarthmore/Harvard over a low-major D1; a non-academic kid of the same
   caliber goes D1). College List now drawn from one national, cross-division
   pool.

4. **Unified week-to-week world** (`app/world.py`). One clock across all six
   universes. Each weekly tick simulates that week's slate (reusing season mode),
   develops players a slice of a year, and signs a slice of the next national
   class. Post-season **finalize**: graduate, run a global cross-division
   transfer portal off real results, intake the signed class, top up walk-ons,
   roll to next year. Indexed portal keeps finalize at ~20s; weekly ticks ~7–10s.

5. **Coach lineups.** Results-driven ladder (live STR) + season-stable coach
   noise; bench/walk-ons get reps (rest starters vs weaker foes + a baseline look
   even vs peers, rotating *which* bench players appear), so nearly the whole
   roster is evaluated over a season instead of the bottom never playing. Doubles
   pairings are season-stable permutations.

6. **Realistic non-conference scheduling.** Powerhouses load up on mid/low-majors
   (and host them); two heavyweights rarely meet in the regular season
   (elite-vs-elite non-conf ≈ 6%).

7. **The World hub** (`/world`). Drives the season-to-season world from the web;
   a before_request hook + world-aware `get_season` make every read surface
   reflect the world's current year.

## Process retro — honest

- **I pivoted the season driver three times** (whole-season batch →
  week-by-week → week-by-week *itemized* drip) because I started building before
  the cadence model was locked. I asked a cadence question early and got
  "whole season," then the real intent ("week to week, itemized") emerged only
  once results were visible. Lesson: for a system this central, prototype the
  *driver shape* on a tiny scale and confirm against the user's mental model
  before building the full engine.
- **A one-line bug (`dict.get(pid, (p.str_value(), 0.0))`) cost ~5×** in the
  rollover because the default is eagerly evaluated on every hit — 145M needless
  attribute recomputations. Profiling found it immediately; I should profile the
  moment something "feels" slow rather than reasoning about it.
- **The portal was O(movers × programs)**; sorted-array fit + prestige bands took
  finalize 167s → 19s. Write the indexed version first for whole-world loops.
- Good calls: keeping rollover steps as **pure functions** (cheap to unit-test
  without DB/sim), and **re-simulating seasons on demand** from persisted
  rosters rather than storing every box score.

## Geography, homecooking, internationals, cross-division (shipped)

8. **Researched campus locations** (`data/ncaa/locations.json`). Real city +
   state for all 1,086 programs, looked up per-school by parallel research
   subagents and disambiguated by conference region (the right Trinity /
   Concordia / Wesleyan campus). Programs carry city/state/region; a coarse
   region map + adjacency drive proximity.

9. **Homecooking (recruit-side, one-way).** Each recruit rolls a homecooking
   value; a homebody is pulled toward nearby programs that fit, while programs
   do **not** hunt locals. Internationals have homecooking 0 — no schools near
   home — so geography never moves them. Applied in the College List and the
   world's signing model.

10. **International knob.** `RECRUIT_INTL_SHARE` sets how many internationals
    exist; `INTL_TIER_PULL` routes them (D1 → D2 → elite D3; ordinary D3 stays
    local), since internationals chase prestige/academics with no home pull.
    Both are plainly tunable.

11. **Cross-division scheduling.** A geography-driven cross-class slate per year:
    adjacent classes (D1↔D2, D2↔D3) plus elite (high-academic) D3 reaching D1,
    ≤ 3 per team, higher classification hosts. Stored in `world_crossmatch`,
    simulated on the year's first weekly tick (the lineup model rests starters
    vs a weaker class, so bench/walk-ons play). Verified: ~1,040 men's cross
    duals (D1-D2 444 / D2-D3 444 / D1-D3 151), every game same-or-adjacent
    region.

## Remaining / next
- **Surface cross-division results** on team pages (data + `cross_results_for`
  exist; the team rail/box-score linking is the small remaining UI bit).
- **Roster geographic realism** is emergent (P4 national/international, D3 local)
  from homecooking + prestige + the intl knob; worth a calibration pass once
  there's a target distribution to tune against.
- Editor overrides and the legacy single-season `/season` page predate the world
  and should eventually be reconciled with it (the redesign will revisit UI).
