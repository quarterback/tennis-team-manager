# AGENTS.md — `tests/`

106 test files. Run with `python3 -m pytest tests -q` from the repo root.

## The database rule

**The suite must not share a database with the app.** The root `conftest.py` forces a
separate test DB, and it must happen **before any `app` import**, because
`app.dbpath.resolve_db_path()` reads `$TENNIS_DB_PATH` at import time and otherwise falls
back to the repo's `./tennis.db` — which is a real save. `app.world`'s `WORLD_DB` resolves to
the same file, and `world.reset()` opens with `DELETE FROM world`.

Running the suite deleted the developer's world. Every time. Do not weaken this, and do not
move imports above it.

## Suite-wide fixtures

Two autouse fixtures shape every test:

- **Injuries are disabled by default.** They are the one deliberately non-deterministic
  system and would break replay assertions. Injury tests opt back in, seeded. Production
  ships with them enabled.
- **The junior season is pinned short** (10 weeks instead of 36) so circuit builds stay
  cheap. Restored afterwards.

## Writing tests

**Assertions read the rendered output.** An empty-state test cannot see a page. If a change
produces HTML, the test should read the HTML, not just the return value of the function that
generated it.

**Build fixtures at the real scale when a rule depends on a count.** A fixture that crowns 12
regions will never exercise the 20-region branch — every test passes while the real path has
never run once. This has happened. When a code path is gated on a count, threshold or field
size, construct the case explicitly rather than hoping a generated world produces it.

**Test the shape, not one fixture's output.** For a curve or a table, pin monotonicity,
endpoints, plateaus and boundary behaviour rather than a specific number produced by one
seed.

**Determinism tests must copy their inputs.** Playing a dual credits records, so a second run
against mutated state is a different input. Snapshot before, not after.

**Cover the empty and degenerate cases explicitly**: a district with zero eligible entrants, a
disconnected schedule graph, a program that cannot fill a lineup, a season with no prior year
to diff against.

## Analytics

The sidecar has its own suite: `python3 -m pytest analytics/tests -q`. It pushes a synthetic
multi-class season through the game's own export builder, ingests it, renders it, and asserts
against the resulting HTML.
