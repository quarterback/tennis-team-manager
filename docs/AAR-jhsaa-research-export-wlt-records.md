# AAR — JHSAA research export rejected W-L-T records

## Incident

A bulk JHSAA research export failed in `_load_archived_jhsaa_season` with
`ValueError: too many values to unpack (expected 2)`. The archive adapter split every
standings record into exactly two values even though a Group 2 showcase can use the
even 3S/3D format, remain level after the established sets-and-games tiebreak ladder,
and produce a legitimate varsity tie. `TeamSeason.record` therefore writes `W-L-T`
when a tie exists while retaining the historical `W-L` representation otherwise.

## Fix

The archive adapter now reuses one small `_record_parts` parser for both overall and
district records. It accepts both archive representations, supplies zero ties for a
legacy `W-L` record, and reports malformed records as the export layer's user-facing
`ExportError` rather than leaking an unpacking exception from the Flask route.

The reconstructed team retains the parsed tie count, and `jhsaa_standings.csv` now
includes a `ties` column. This avoids fixing the download merely by discarding the
third value: the exported standings remain a faithful account of the archive. The
existing injected-season path remains intact, with `getattr(..., 0)` preserving
compatibility for callers whose synthetic team objects predate ties.

The bundle's self-describing domain rules now say that `duals.tied` covers both
even-court JV draws and even-format varsity showcase draws. Previously that contract
incorrectly described JV as the association's only possible drawn result.

## Clinch Report propagation

The producer and its in-repository consumer changed together. The Clinch Report's
leaderboards ingest the optional `ties` column (zero for old exports), calculate
winning percentage as `(wins + 0.5 * ties) / decisions`, and carry ties into team
pages, season rankings and standings, the team index, prose, and scouting-market
team comparisons. Its schedule adapter also distinguishes `duals.tied` from a loss,
so a tied varsity dual renders `T` and does not inflate the loss count. Team metrics
likewise exclude ties from loss-only measures and credit half a win in record luck.

## Deliberately unchanged

- Ingestion, archive lookup, season scoping, roster seeding, bracket data, and bulk
  ZIP construction still use the existing `_load_archived_jhsaa_season`,
  `world.get_jhsaa`, `world.jhsaa_match_dates`, and `export_zip_bulk` paths.
- District records currently remain `W-L`, but they pass through the same parser so
  the adapter will not fail if the persisted representation later gains ties.
- No season is simulated or rewritten during export.

## Regression coverage

The export tests read the rendered `jhsaa_standings.csv` and assert that a varsity
tie survives as separate wins, losses, and ties values. Parser coverage locks both
valid archive shapes and the explicit error for an invalid shape.
The analytics integration fixture then sends a tied showcase through the real
exporter, ZIP ingester, aggregation layer, and site renderer and reads the generated
HTML.
