# AAR — Program Honors & Season Results on school pages

## What shipped
Each school page now carries two new sections below the roster/results:

- **Season Results by Year** — one row per world-year with results: record,
  conference, conference title(s), ITA Indoor result, and NCAA result. Newest first;
  the in-progress year is tagged `live` and its NCAA cell reads "in progress".
- **Program Honors** — an aggregated trophy case: National Championships, ITA Indoor
  National Champions, NCAA Tournament Appearances (+ round reached), ITA Indoor
  Appearances (+ round reached), Regular-Season Conference Titles, and Conference
  Tournament Titles — each with a count and the years.

The ITA Indoor National Championship is also now a **career honor** for players and
the head coach (separate commit), so it shows on player/coach cards too.

## How it works
No new storage was needed — past seasons already persist in the season DB, one per
world-year at `world.year_seed(base, y) = base + 1000*y`.

- `seasonmode.season_program_result(season_id, school)` — one DB pass for a team's
  record, then derives: furthest NCAA round, furthest ITA Indoor round (champion /
  runner-up special-cased), conference-tournament champ (`conf_champions`), and
  regular-season conference champ.
- `state.program_history(division, gender, school)` — walks years `0..current`,
  resolves each season via `find_season(seed=year_seed(...))`, and aggregates the
  per-season rows into the honors dict. Newest-first.

## Round vocabulary
Round-reached labels use the requested bracket vocabulary, mapped from the stored
round name: play-in → **R96**, then **R64 / R32 / Sweet 16 (R16) / Elite 8 (QF) /
Final 4 (SF)**, and the final resolves to **National Champion** or **National
Runner-Up** (`NCAA_ROUND_LABEL` in seasonmode).

## Decisions
- **Shared conference titles.** Regular-season conference champions have *no
  tiebreaker* — every team tied for the best conference win% is a co-champion
  (`_reg_conf_champions` returns the full set), unlike the standings table which
  tiebreaks to a single top row.
- **ITA round** is reported from the Indoor draw (the team championship); the
  Kickoff is the qualifier, not the appearance line.
- **NCAA round** is only resolved once the season is `complete` (otherwise a team
  still alive would look "eliminated" at its latest win).

## Notes
- `program_history` runs on each team-page load; it's a handful of short read
  queries per year, fine for the current world depth.
- A 500 seen while testing was a SQLite lock from a test harness that isolated only
  the season DB (leaving coachreg on the shared file) — not a product issue; all
  subsystems share one `tennis.db` with WAL + busy-timeout in the running app.
