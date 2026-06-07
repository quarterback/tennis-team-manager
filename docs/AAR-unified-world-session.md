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

## Remaining — designed, needs your input

### Geography (BLOCKER: need the data)
You said school locations already exist "in the other folders," same system as
the recruit/player hometowns. **That data is not in this repo** — the NCAA JSONs
carry only `name`/`conf`/`teams`, and the only geo vocabulary present is the
US-states/hometowns system in `generators/origins.py` + `app/juniors.py`.

To finish geography I need either (a) that school→location file dropped in (e.g.
`data/ncaa/locations.json` keyed by school → state/region/lat-long), or (b) the
go-ahead to derive each school's state from its conference (conferences are
largely regional) as an interim, reusing the existing US-states vocabulary so it
stays consistent with recruit/player hometowns.

Once locations exist:
- **Recruiting proximity**: add a distance/region term to `program_appeal` so a
  recruit's home state pulls them toward nearby schools.
- See cross-division below.

### Cross-division scheduling (depends on geography)
Captured constraints from this session:
- Adjacent classifications only: **D1↔D2, D2↔D3** (and elite **D3→D1**),
  mostly mid/low-major D1 vs D2 and D2 vs D3.
- **Geography-driven** — nearby schools across classifications play.
- **≤ 3 cross-classification duals per team per year.**
- Higher classification typically hosts; these are non-conference, don't affect
  conference standings (could inform rankings/RPI later).

Architecture note: a cross-division dual spans two universe-seasons, which the
current per-(division×gender) season-mode model doesn't represent. Cleanest fix:
schedule + simulate these at the **world** level (a `world_crossmatch` slate per
year), surfaced on team pages and the world hub, outside the per-universe
season-mode schedules.
