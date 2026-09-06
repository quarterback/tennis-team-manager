# AGENTS.md — `analytics/`

**The Clinch Report** — a standalone static-site analytics sidecar. It ingests research-export
zips and builds team pages, player career pages, a scouting desk, classification reports and
a metrics library, styled to match the game's design system and written like a state-desk
beat outlet.

## The first rule

**This tool never touches the game's database or app code.** It only reads zips you export
and drop in. Nothing here imports from `app/` or `engine/`. If a change would require reading
the live DB, the change is wrong.

## Commands

```bash
python3 build.py                       # re-render everything already ingested
python3 build.py path/to/export.zip    # ingest new/changed seasons, then render
cd site && python3 -m http.server 8000 # serve
```

`build.py` with no arguments rebuilds from cache. Pass a zip only to add a season or replace
a re-exported one; re-ingesting a scope overwrites it.

**Ingesting and rendering are separate, and past ~10 seasons that matters.** The cache is the
almanac and costs a few MB per season. The site is O(seasons × entities) — one season-gender
is ~250 MB and 13.5k player pages. Fourteen years of both genders is several GB.

```bash
python3 build.py --latest 2 --no-player-pages   # ~54 MB, the practical default
python3 build.py --years 2038-2039
python3 build.py --gender boys
```

`--latest 2`, not 1: movement and development are differences between consecutive seasons, so
a single rendered season has no prior year to diff and every transfer and growth number is
legitimately blank.

**Browse over `http://localhost`, never `file://`.** My Teams and the scouting shortlist use
`localStorage`, which browsers scope per origin; a `file://` page has no real origin and
several browsers give every file its own bucket. Stars vanish between pages. Nothing inside a
static page can work around a browser storage policy.

## Data rules

**Varsity only.** `aggregate.Bundle` filters to `level == "v"` at the one chokepoint
everything downstream reads through. A missing `level` means varsity, not unknown — seasons
exported before the JV season existed have no column and every dual in one is varsity. "Carries
no lines" is **not** a usable substitute for the column; that is also what a varsity dual whose
lines failed to record looks like.

**Join on `program_id`, never a display name.** Roughly 300 of 1,644 programs have been
renamed across the archive, and an id often matches neither the old name nor the new one.

**Join players on `player_id`.** Names are not unique across the association.

**`classification` is enrollment; `championship_group` is who they play.** Six programs
differ, two of them by four classes. Every competitive comparison keys on the group
(`aggregate.program_class`).

**Card shapes are derived, never hard-coded** (`Bundle.regular_shape` / `state_shape`) — the
most common line-count shape seen in each phase bucket. An earlier version hard-coded the
regular format as 5S/2D in the same session the game swapped it to 3S/4D, which would have
rendered every format-lift number backwards.

**Growth curves are refitted, not copied.** The development model has been rebuilt and is
era-gated by entry year; a copied table describes whichever era it was measured in and
mis-scores every other one.

**Re-export any season taken before the JV fix.** For a period `duals.csv` carried JV duals
with nothing marking them, inflating every record and program total. New exports carry
`duals.level`.

## This is the JHSAA desk

College exports still ingest and render results-only pages, but **nothing ability-derived is
computed from one**, and there is no Scouting or Classifications page for them. That is not
only scope: the college export reflects the *current* roster and program config, not a
per-season snapshot, so reading ratings off an old season would price old flights at later
numbers and a movement diff would conclude nobody has ever transferred.
`Bundle.roster_is_snapshot` is the gate.

## Structure

**Classification → district is the organizing hierarchy on every page, list and menu.**
Nothing renders a statewide splat — an early pass listed 861 teams in one table and the
verdict was that it was impossible to parse. The model is Football Manager: dashboards with
tabbed views, dense sortable grids scoped by pickers, entity pages carrying their own stats.

**Geography is a top-level axis in the scouting desk**, not a filter beneath classification.
A cohort build is "the best players within one county", and a class-first tree makes that
query unaskable. The search carries both cascades (area → county → town, and class → league)
and narrows on whichever the question uses.

**A new metric is a new column or view in the Team Stat Center grid, never a new page of
everything.** The seven single-metric pages of the first analytics pass are gone.

**Finders are not capped.** Keeping the best 60 per class reads on screen as "these are the
candidates" while being "these are 60 of 1,022". Only the grid's display limit applies, and
it announces itself.

## Vocabulary

A player plays **matches**, at a **flight** / position / line, in a **dual**. A **court** is
the physical surface — "courts played" is wrong, and so is "the D3 court" (it is the No. 3
doubles flight). Aggregates over flights are **flight share**. The older "court share" wording
survives in `metrics.py`'s tier-1 metric names and is being fixed in surfaces as they are
touched, not swept.

**Never surface a player rating.** Ratings are a legitimate input to `ability.py` and to
xShare / Talent luck; they are never output as a way of describing a player.

## Tests

`python3 -m pytest analytics/tests -q` from the repo root. A synthetic multi-class season is
pushed through the game's own export builder, ingested, rendered, and the assertions read the
resulting HTML — an empty-state test cannot see a page.
