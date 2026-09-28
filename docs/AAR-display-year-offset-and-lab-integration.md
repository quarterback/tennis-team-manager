# AAR — the display-year offset and the lab-to-college integration

Owner request 2026-09: after ~73 lab seasons the JHSAA history is folded into a
full college save that STARTS IN 2026 — the final lab season renders as the
2026-27 school year and the decades of high-school history read backdated behind
it. `world.attach_college` + `scripts/integrate_lab_world.py` +
`world.display_offset()` / `display_base_year()` / `display_year()` / the `|cal`
Jinja filter.

## The one design decision everything follows from

**The archive cannot be renumbered; only the display can.** A JHSAA player is
regenerated from (school, gender, ENTRY YEAR, seat) under the save's salt, and
the era gates, talent pins, transfers, reclass cycles and season archives all
key on calendar years. Move the numbers and every archived person regenerates
as someone else, silently. So every year keeps its IDENTITY internally and a
per-save offset is subtracted at the display edge. Offset 0 (every ordinary
save) is the identity function everywhere — pinned.

## The conventions (where a year converts, and where it must not)

- **Idx-based display sites** (`BASE_YEAR + world_year` renders; URL year −
  base parses) read `display_base_year()`. Both directions swap together, so
  round-trips hold by construction.
- **College-side stores born at/after the merge** (honors stamps,
  `rankings_archive`, cup returns, GTT calendar years) swap writer AND reader
  onto the display base — they are empty at integration, so rows are born on
  the display calendar and never mix conventions inside one save.
- **JHSAA stores stay IDENTITY** (season archives, reclass `first_season`,
  transfer ledgers, coach histories, era gates, talent pins): readers convert
  with `display_year()` in the view, or templates convert with `|cal`. The
  `_jh_scope.season_year` a view carries is identity — it feeds `build_roster`
  and forms.
- **Forms speak DISPLAYED years** (transfer/family `jh_year`/`jh_entry`/
  `jh_undo_year`/`player_season`, the research-export year): prefill with
  `|cal`, and the POST route adds `display_offset()` back ONCE. ‼️ A form
  value rendered raw while its route converts corrupts silently — the undo
  form posted identity 2093, the route made it 2159, `clear_jhsaa_transfer`
  matched nothing and the flash still said "Move undone".
- **The research-export CORPUS stays identity** (zips, directory names, rows,
  the clinch report) so the owner's 70+ lab exports stay one continuous
  series; the export form takes displayed years and the route validates the
  bounds on the IDENTITY year (`year + offset`), never the typed number — a
  backdated save's earliest seasons display well before 2020.
- **Identity compares stay on `BASE_YEAR`**: `recruiting_grad_year` (a recruit
  class KEY — it seeds `board_class`), the alumni grad-year gate,
  `parastate_blurb`'s pilot-year input, `jhsaa_match_dates`' season_year (every
  caller must feed the same value or the two schools' cards disagree on the
  weekday — the one-date-per-dual rule).

## The integration itself

`attach_college(seed)` builds the college universes INTO the existing
jhsaa-only world at its CURRENT year (same `_build_universe` path, the world's
own salt — the archive is only readable inside the save that wrote it, so a
fresh save can never work), sets the offset to that year, pre-stamps
`pros_rolled_year`, and refuses to run twice. The week-0 JHSAA rung skips
itself (the lab archived the season), and the lab's final senior class IS the
first college recruiting class.

`scripts/integrate_lab_world.py` is read-only without `--apply`, refuses to
overwrite a target, requires exactly one world row and `archive max ==
world.year`, and never touches the lab file. ‼️ **The copy is the SQLite
backup API, never `shutil.copy2`**: under WAL, committed rows sit in the
`-wal` file until a checkpoint, so a file copy can hand the target fewer
archive rows than the preflight just reported — an incomplete save with
nothing raised.

## Traps this pass hit (don't re-hit them)

- **The anchor is self-computing** (offset = world year at attach). Quoting a
  displayed start year from an earlier state of the save goes stale the moment
  another season is simmed — the ENDPOINT is pinned at 2027, the start moves.
- **`|cal` must tolerate Jinja Undefined** — an empty-state page pipes missing
  attributes through the filter and must render empty, never 500.
- **A span STRING can't take the template filter** ("2085–93"): convert
  first/last with `display_year()` before formatting, in the view.
- **Each rebase re-opens the sweep**: any new surface that renders a stored
  year (the coaches pages did it twice) needs `|cal` or it prints identity
  years beside backdated ones. Grep `season_year`/`since`/`grad_year` renders
  without `|cal` after merging main.
- **Double conversion is as wrong as none**: a view that already returns
  displayed years (`_jh_reclass_lines`, the match center's `season_disp`)
  must NOT get `|cal` on top.

Tests: `tests/test_display_year_offset.py` (offset-0 identity, reset clears,
attach semantics, and a RENDERED front page under a nonzero offset).
