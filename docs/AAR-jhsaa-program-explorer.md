# AAR — the JHSAA program explorer (`/jhsaa/programs`)

**Owner report (2026-09):** "the programs page is too many things at once and it's
not easy to use." Then, asked what would work: a dense table of every program with
grouping, combinable facets, and a persistent multi-selection with a sticky action
bar — "much more like a roster-management console or spreadsheet than an admin form".

## What was wrong

The page was five jobs in a column: a board → type → program directory, a paste-
school-names bulk form, the one-school editor, an unstructured log of edits, and the
tier-definition table. Each obeyed the earlier "narrow before you show" rule and the
page was still tedious, because the directory required you to already know what you
were looking for. It could not answer "every 8A/9A program below Poor" or "Group 2's
coaching and turnout programs" — which is how the owner actually thinks about the
association — and changing twenty schools was twenty form posts or a pasted list.

## What it is now

- **One row per program** (`jhsaa.program_explorer`): School · Class · Archetype ·
  Talent tier · Plays up, plus the flags the page slices on (edited in this save,
  sponsors tennis). ~1,000 rows as one JSON payload; every map is resolved once.
- **Everything else is a slice** in the browser: group by (class / tier / archetype /
  play-up), facet chips that combine across facets (OR within, AND across), a name
  search, sortable columns.
- **Persistent selection** in `localStorage`: check 12, change filters, check 8 more,
  and the 20 are still selected — through a reload and through every save's POST →
  redirect. "Show only these" makes the selection the sole filter (on top of the
  facets it hid most of what you had gathered).
- **Sticky action bar** while anything is selected: Set tier · Set archetype · Plays up
  · Clear, each confirmed with the count, posting to `/editor/jhsaa-programs-bulk`.
- **Side panel** off a row for the single-program controls (per-save overrides, Reset).
- **Tier settings** on its own page, `/jhsaa/programs/tiers`.

## Decisions the owner made (asked before building)

1. **The action bar writes the SEED FILES**, as the retired paste forms did: the owner
   starts fresh databases and a per-save override cannot survive that. A touched
   school's per-save override is cleared so the row reflects the pass. The panel keeps
   the reversible per-save override for a one-off.
2. **Play-up is a bulk action** — ineligible (5A-and-up) programs are skipped and
   counted in the flash, never written. `bulk_edit_playup_seed` sets/drops the
   `play_up` flag on the school's row in `schools.json`.
3. **Tier table on a sub-page; paste-names forms retired** — a selection is the list.
4. **Side panel, not a separate view** — the table, filters and selection stay on screen.
5. **No geography columns.** League, county and area are "not relevant information" on
   this page; class was only named to assess play-up and the bands.

## Traps

- **A Reset button that shares its field name with the select in the same form
  posts the SELECT's value** — Flask's `form.get` returns the first. The panel disables
  the select on a Reset click. The old page had the same shape and the same latent bug.
- **A cookie flash must be deleted on the read**, or "3 applied" greets the next visit.
- **`_sponsors_any` gates the default view**: 109 rows have stopped sponsoring and
  keep their page (`former_school`) and their tier; they are behind a switch, not
  hidden and not the default.
- **The test client returns 200 on a POST when the world is not primed** — the
  `_prime_world` loader answers instead of the route. Stub `world.is_primed`/`prime`
  (the `warm_client` idiom) before exercising an editor POST.
