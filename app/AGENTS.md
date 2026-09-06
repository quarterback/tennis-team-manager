# AGENTS.md — `app/`

The Flask application, world/save state, and every league system: the JHSAA, the college
layer, GTT, development, injuries, coaches and the economy.

## Layout

| Area | Files |
|---|---|
| World & persistence | `world.py`, `db.py`, `dbpath.py`, `worldconfig.py` |
| JHSAA | `jhsaa.py`, `jhsaa_awards.py`, `jhsaa_individuals.py`, `jhsaa_jv_individuals.py`, `jhsaa_jv_state.py` |
| College | NCAA modules, `ita.py`, recruiting, `economy.py` |
| Pro | `gtt_seasonmode.py` |
| Shared systems | `development.py`, `injuries.py`, `coaches.py`, `honors.py`, `individuals.py`, `bracket.py`, `almanac.py` |
| Web | `app/web/` — `server.py` (routes), `state.py`, `rankings_data.py`, `awards.py`, `formatters.py`, `templates/`, `static/` |

## Rules

**One world per save. One clock. One advance surface.** `/world/advance` is the only place
the world moves forward. The offseason is a **ladder** — one advance step per event, never a
bundled "run the offseason" call. "Seed" means three different things in this codebase;
confirm which one you are touching.

**Module-global caches are dangerous under the threaded worker.** The app runs
`--workers 1 --threads 32`. Module-level mutable state has caused two outages. Any cache you
add must be request-scoped or explicitly thread-safe.

**Injuries are the one deliberately non-deterministic system** (`injuries.py`). Everything
else reproduces from a seed. The test suite disables injuries by default for exactly this
reason and the injury tests opt back in, seeded.

**Derive format shapes, never assume them.** Shapes differ by classification and by phase:
league play is 3S/4D, the early non-district window is 5S/2D, most groups play 1S/4D in the
postseason, 8A and 9A play 4S/5D, and 1A runs a 2S/3D pilot. Read the shape.

**Varsity and JV share tables.** Filter on `level == "v"` wherever varsity results are meant.
A missing `level` means varsity (pre-JV seasons). JV must never inflate a varsity record, a
standings row, or an export.

**`classification` is enrollment. `championship_group` is who they play.** These differ for a
handful of programs under permanent play-up exemptions. All competitive logic keys on
`championship_group`.

**Join on `program_id`, never a display name** — roughly 300 of 1,644 programs have been
renamed. **Join players on `player_id`, never name** — names are not unique.

**Never render a player rating.** OVR / `current_grade` / `potential_grade` are calibration
inputs and are invisible in-world. User-facing text describes players by record, flight,
position, honors and results.

## Web layer

**Classification → district is the organizing hierarchy on every page, list and menu.**
Nothing renders a statewide splat. The mental model is Football Manager: dashboards with
tabbed views, dense sortable grids scoped by pickers, entity pages carrying their own stats
in panels.

**A player's grade appears in every list a player appears in**, sortable. No clicking through
to discover someone is a senior.

**No tutorial help text on the pages themselves.**

**Colour and type are token systems.** Components read aliases only, never raw palette values.
A type scale that is not used is not a scale.

**Schedules render the way the game presents them**: sectioned by phase, real dates, vs/at,
type chips rather than raw phase strings, winner-first scorelines.

**Round labels come from the export's own `round_names` where present.** Do not relabel a
bracket by distance-from-final when the source names the rounds — an expanded field prepends
qualifying rounds that are not a continuation of the same single-elimination sequence.
