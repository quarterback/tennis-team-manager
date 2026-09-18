# AAR — JHSAA reclassification: the four-season realignment cycle

Owner spec: `docs/DESIGN-jhsaa-reclassification.md`. Models and data:
`docs/REPORT-jhsaa-reclassification-models.md`. Code: `app/jhsaa_reclass.py`
(the cycle), `app/jhsaa_districting.py` (the league redraw, moved out of
`scripts/jhsaa_redistrict.py`), routes under `/jhsaa/reclassification` and
`/jhsaa/realignments`, tests in `tests/test_jhsaa_reclass.py`.

## What was built

- **The hold.** At week 0 of a world-year, before the JHSAA season plays, if
  `cycle` seasons have been archived since the last committed cycle (or the
  save's start), `world.advance_week` opens a proposal and returns
  `jhsaa_reclass_pending` instead of playing. The header button reads "Review
  reclassification" and links to the page. It keeps holding until the proposal
  is committed or dismissed — the fall-portal pattern. "Run reclassification
  now" opens the same hold off-cycle.
- **The score.** One fold per archived season, both genders, school-level:
  finish points off the State bracket (champion 4, finalist 3, semifinalist 2,
  made State 1) and the combined record off the standings rows. Never a
  per-school read of the archive (the title-board rule).
- **The passes.** Geography first: a Group school outside Group territory
  re-enters the A ladder by enrollment; 1A schools in the approved eastern
  areas repatriate into the Groups; ladder schools never enter the Groups on
  territory. Then three sorts on `effective_size = enrollment + points ×
  SUCCESS_PER_POINT − max(0, floor − win_rate) × FUTILITY_PER_UNIT`, one per
  pool (9A-5A, 4A-1A, Groups), cut into equal bands with pinned schools counted
  toward their class's seats. No guard.
- **The page.** Every pooled school with rank, enrollment, points, record, win
  rate, adjustment, effective size, proposed class and resulting league;
  counts before and after; veto / pin-to-class / undo per row; an "add a
  school to a pool" form (Pacific Friends' door back onto the A ladder);
  coefficients and the two area lists editable; Commit, Rebuild, Dismiss.
- **The commit.** Rewrites `data/jhsaa/schools.json` (`classification` and
  `group` together; the seeded `play_up` flag popped on movers), redraws every
  touched class's leagues through the shared clustering, records each move in
  `world_jhsaa_reclass_move` with its evidence, closes the cycle, resets the
  school and web caches. The next week-0 season plays the new map.
- **History.** A Realignments page on the History sub-rail, one block per
  committed cycle; a Reclassifications panel on the program page's History tab;
  `world.reset` clears the cycle tables for a new save.

## Lessons

- **The redistricter needed a position per town, and prep-network is not in
  the app.** The script read `cities.json` from the sibling repo. The generated
  gazetteer (`docs/GAZETTEER-jefferson.md`) already prints every town's
  coordinates to two decimals, so `scripts/build_jhsaa_coords.py` derives
  `data/jhsaa/coords.json` from it; six live towns have none and fall to their
  county centroid, as the script always did. The league-name bank and the
  districting constants likewise moved to `data/jhsaa/districting.json`,
  asserted equal to the importer's (the rivalry-tables idiom). The clustering
  itself moved verbatim into `app/jhsaa_districting.py` and the script imports
  it, so there is one algorithm.
- **Two writers on one SQLite file lock each other.** The commit cleared per-save
  play-up overrides through `overrides`' own connection while its own move
  transaction was open: "database is locked". The clears run first, on their
  own connection; the moves after.
- **Pinned rows count toward the band.** A veto removed from the pool and cut
  around leaves that class one seat heavy. Each class's quota is reduced by the
  schools pinned into it before the free rows are dealt, so the bands stay
  equal with edits on top.
- **The scaled per-pool coefficients read off the live spans.** The design doc
  quoted 16.5 and 1240 for 4A-1A from the 2086 export; on the seed file the 9A-5A
  span is wider (a 378-enrollment school sits in 8A), so the derived numbers are
  13.3 and 1000. They are defaults; the page shows the live values per pool and
  the owner sets a pool's own to override.
- **An off-cycle run on a fresh save is enrollment-only.** With no archive the
  scorer returns nothing and the sort is by enrollment; the button is disabled
  until a season is archived, but the path is legal.
