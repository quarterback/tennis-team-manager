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
