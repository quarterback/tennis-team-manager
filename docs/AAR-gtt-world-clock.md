# AAR — GTT runs on the college world's clock (lockstep)

**Date:** 2027-07-17
**Scope:** `gtt_seasonmode` (`BASE_YEAR`, `advance` off-season gate,
`_world_year`, `can_start_next`, `on_world_rollover`), `world._finalize_year`
(post-commit hook), GTT hub (waiting state instead of the button).

## The problem (owner report)

The pro league ran on its own free clock: it could sim seasons ahead of the
college game (stamping 2028 titles while college played 2027), and its
off-season could run BEFORE the college season finalized — at which point the
graduating class doesn't exist yet, so intake found nothing and rosters filled
with rookies. "Two self-contained systems."

## Owner's rule (locked): one universe, one clock

- **GTT season index i is played CONCURRENT with college calendar 2026+i**
  (`BASE_YEAR` 2027→2026). The class graduating college year y joins the GTT
  for season index y+1 — the next calendar year, like real life.
- **The GTT off-season is GATED on the college finalize:** `advance` on a
  completed league holds (`waiting_on_college`) until `world.year ≥ league.year
  + 1`. The hub shows a waiting pill explaining what to do instead of the
  Start-next-season button. The pro league can never sim ahead of the universe
  it draws from.
- **The college finalize DRIVES the pro off-season:** `world._finalize_year`,
  after its commit (graduates written, year advanced), calls
  `gtt.on_world_rollover()` — every bound league whose season is complete rolls
  its off-season right there and drafts the class that just walked. Mid-season
  leagues are left alone; their off-season unlocks when they finish.
- Standalone leagues (a DB with no world) keep their own clock — the gate
  only binds when a world exists.

## Sequencing invariant

The hook runs POST-COMMIT on its own connections — never inside the rollover
transaction (the shared SQLite file: a second writer mid-transaction locks; see
AAR-davis-bjk-cups "stamp through the caller's connection" for the same trap).
It must also stay AFTER `_save_graduates` + the year bump, or the intake reads
last year's class.

## Verified

League completes while college year unfinalized → `advance` returns
`waiting_on_college`, `can_start_next` False. Simulated finalize (graduates
written, year bumped, hook called) → league auto-rolls, rosters go 100%
college-origin with the just-graduated names, calendar labels aligned.

## Watch-outs

- A league left unrolled across TWO college finalizes only sees the LATEST
  class at its next off-season (`_world_graduates` reads MAX(year)) — the
  skipped class is gone. Roll leagues every year (the hook does).
- Honors stamped before the BASE_YEAR realignment carry the old +1 calendar
  (e.g. a "2028" GTT title earned during college 2027). Cosmetic; new stamps
  are aligned.
- The cups (`_store_world_cups`) and this hook both live in the finalize —
  that is the ONE integration point for concurrent-universe systems. Add new
  cross-system events there, post-commit, own connections.
