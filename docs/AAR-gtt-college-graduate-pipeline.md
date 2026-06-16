# AAR — GTT college graduate pipeline

## What changed

The GTT off-season now consumes a durable college graduating class instead of
looking at the latest roster snapshot for still-enrolled seniors. During world
finalization, the engine stores every active-universe senior in
`world_graduates` before `graduate()` removes them from rosters. Each row keeps
the college pid, division, gender, final STR, final OVR, and full Prospect JSON,
so the same identity can continue into GTT.

## Timing fix

The authoritative source is `world_graduates(world_id, year, ...)`, written for
the college year that just ended. GTT reads this table through the caller's open
SQLite connection, preserving the shared-DB/no-second-connection rule and
avoiding transaction deadlocks.

## Selection rule

The pro selector uses tunable constants in `app/gtt_seasonmode.py`:

- `GRAD_D1_SHARE = 0.95`
- `GRAD_FREE_AGENT_SLACK = 4`
- `NON_D1_MIN_STR = 58.0`
- `NON_D1_MIN_OVR = 58.0`

Each off-season signs the open roster need plus slack. D1 graduates are ranked
by STR, while D2/D3 graduates must clear both the STR and OVR pro-competition
bars before they can claim the reserved non-D1 slice. Selected graduates enter
`gtt_players` with `origin='college'`, `joined_year` set to the GTT season, and
the original pid/data intact.

## World linkage

`create_league()` now resolves the league's `world_seed` against the active world
when the caller does not explicitly provide one, and the GTT web hub no longer
forces a `2026` fallback seed for blank league-creation forms. Founders remain
generated only for the inaugural backfill.

## Verification

Focused coverage was added for the selector/persistence path: a temp shared DB
is populated with a world, a persisted graduating class, and a GTT league; the
off-season selector is asserted to prefer top D1 players, admit only qualifying
small-school players, preserve college pids/data, and create free agents beyond
open roster need.
