# AAR — Past winners of the NCAA singles & doubles championships

## The problem
The individual singles and doubles championship winners were being persisted but
never *surfaced*: `world._store_championships` snapshots each year's full draw JSON
(champion and runner-up included) into the `world_championship` table at every year
rollover, but nothing ever listed those winners. The singles/doubles pages only
showed one season at a time (via the `?year=` picker), and the Hall of Fame only
archived team honors (`national_champion` / POTY / COTY from the `honors` table).
So "who won singles in 2027?" was unanswerable from the UI even though the answer
was sitting in the DB.

## What was added (display only — no new persistence)
The data model is untouched; this is a read path over the existing snapshots.

- **`world.past_individual_champions(seed, division, gender)`** (`app/world.py`) —
  year-by-year winners for a universe, newest first:
  `[{"year": <calendar>, "singles": {"champion", "runner_up"}, "doubles": {...}}]`.
  Champion/runner-up are the flattened entry dicts already stored by
  `championship_to_dict` (label / school / conf_abbr / pid / seed). Years convert
  from the stored world-year index via `BASE_YEAR + year`, matching
  `championship_years`.
- **`app.web.state.past_individual_champions`** — thin wrapper (no cache; it's a
  single indexed read of a handful of rows, safe on the request path).
- **Singles page** (`/singles-championship`, `singles.html`) — a "Past Singles
  Champions" table at the bottom: year (links to that season's full draw via the
  existing `?year=` picker), champion (crest + player-page link via `pid`),
  runner-up.
- **Doubles page** (`/doubles-championship`, `doubles.html`) — same, for pairs
  (pair labels aren't linked — a `DoublesEntry` has no single pid).
- **Hall of Fame** (`/hall-of-fame`) — each universe's per-year slot now shows
  Singles Champion and Doubles Champions alongside the team champion / POTY / COTY.
  The archive's year list is the UNION of `honors.years()` and years with stored
  championships, so neither source can hide the other.

## Design decisions
- **The past-winners LISTS read from `world_championship`.** The champion is already
  durably stored per `(world_id, year, division, gender, event)`, so the singles /
  doubles / Hall of Fame archives read the snapshots directly — that works
  retroactively on existing saves with no backfill.
- **Player-page award chips are stamped into `honors` (owner follow-up).** Awards
  `singles_champion` / `doubles_champion` are stamped in `web/awards.py
  honor_records` at the awards phase, alongside POTY/All-American/team titles —
  the doubles title credits BOTH halves of the winning pair (each player's own pid).
  To make that possible, `championship_to_dict` entries now carry a per-player
  `players: [{pid, name}]` list (a `players` property on `SinglesEntry` /
  `DoublesEntry`), and `_hydrate_championship` exposes it (older snapshots without
  the key fall back to the singles entry's `pid`/`label`; a pre-existing doubles
  snapshot can't be split per player, so no chip is stamped from one). Like every
  honor, chips exist from the first awards phase run AFTER this change — past
  seasons show in the archives (snapshot-read) but aren't retro-stamped as chips.
- **Current season joins the list at rollover.** A just-completed season's draw is
  computed live (memoized) until `_store_championships` snapshots it at finalize —
  same lifecycle the year picker already follows. The past-winners table therefore
  only lists finished, snapshotted years; that's the point of a "past winners" list.
- **Empty states are silent.** No world / no snapshots → empty list → the panel and
  HOF rows simply don't render (fresh saves, standalone no-world seasons, tests).

## Tests
- `tests/test_world.py::test_past_individual_champions_reads_snapshots` — inserts
  synthetic snapshots into a tmp world DB and checks ordering (newest first),
  calendar-year keying, both events, runner-up passthrough, and empty results for a
  universe/world with no snapshots.
- Existing `test_web_singles` / `test_web_doubles` / `test_honors` cover the pages
  still rendering (the panel hides when there's no history).
