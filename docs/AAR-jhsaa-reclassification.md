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
  finish points off the State bracket (champion 6, finalist 4, semifinalist 2,
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
- **History.** A Realignments page on the History sub-rail: an INDEX of
  committed cycles (season, moved, owner decisions, cross-ladder, the class
  counts after) and ONE cycle in full — the year picked on the index or the
  switcher, the newest by default — with the move list, the geography pass and
  the league redraw each folded behind a `<details>`. A Reclassifications
  panel on the program page's History tab; `world.reset` clears the cycle
  tables for a new save.
- **The ledger.** Every commit also writes `data/jhsaa/realignments/
  <season>.json` and `<season>.md` (counts, geography pass, every move with
  its evidence grouped from → to, the redraw notes) and regenerates
  `LEDGER.md` over every cycle file in the directory, oldest first. The
  research export carries the same rows as `jhsaa_realignments.csv` (every
  cycle, newest first, gender-blind, `program_id` joined to `programs.csv`).

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
- **The 4A-1A coefficients read off the live spans; the Group ones do NOT.**
  The design doc quoted 16.5 and 1240 for 4A-1A from the 2086 export; on the
  seed file the 9A-5A span is wider (a 378-enrollment school sits in 8A), so
  the derived numbers are 13.3 and 1000. The Group pool was span-scaled too at
  first, and its span is dominated by Group 1 (~1,500 wide against Group 2/3's
  ~340-640), so the derived ~45/pt barely moved anybody where Group schools
  actually move. It now defaults to the 9A-5A numbers × `GROUP_COEFF_SCALE`
  (1.5 — 60/pt, 4,500/unit). All are defaults; the page shows the live values
  per pool and the owner sets a pool's own to override.
- **The history page was built to stack every cycle in full, and the owner
  saw at once that it would not survive a second one** (~400 moves a cycle,
  every four seasons). The index-plus-one-cycle shape is the section's own
  rule — a parent page gets an index of its children, siblings get a
  switcher — applied late. And a database row is not something a model can
  be handed: "track these changes with an LLM across the arc of seasons" is
  what the per-cycle files and the export table are for. `LEDGER.md` is
  regenerated from the cycle files rather than appended, so it cannot drift
  from them.
- **An off-cycle run on a fresh save is enrollment-only.** With no archive the
  scorer returns nothing and the sort is by enrollment; the button is disabled
  until a season is archived, but the path is legal.

## Addendum (2026-09): the map has to outlive the seed file

The owner committed a 406-move cycle, updated the code, and simulated the next
season — and it played on the old map. The export made the cause plain: every
move row's `program_ident` was empty (the commit ran on code from before that
column) while the export itself carried the column, so the code was updated
between the commit and the advance, and the checkout came back with the repo's
`schools.json` while the lab database, outside the repo, kept the cycle. The
commit's only durable effect had been a file in a working tree; nothing raised,
the season simply read the old classes.

- **The map is snapshotted on the cycle row** (`data["map"]`: every school's
  post-commit class, championship group, both league names and play-up flag,
  beside its pre-commit class) and **`jhsaa._rows()` re-applies it** whenever
  the file reads pre-commit — in memory and on disk, with a warning. A cycle
  committed before the snapshot existed is reconstructed from its proposal rows
  and the seeded league redraw (`committed_map`), which reproduces the file the
  commit wrote. The detector is "a moved school still sits in the class the
  cycle moved it out of"; a file the owner has since changed by hand does not
  trip it. The read is one query per cache fill, no schema statement, so it
  cannot take a write lock under the season simulation.
- **The lab advance now holds** like the world advance (`ReclassHold`): a due
  cycle opens on its own and a pending one stops the advance, with the lab page
  saying so. Before this the lab never opened a cycle and would advance straight
  past a committed one.
- **The cycle records the first season it applies to** (`first_season`): at
  week 0 of a college world that is BASE+year+1; a lab world at year N has
  archived that season, so its first new season is one later. The owner's
  existing cycle keeps its 2087 label; the map takes effect from the next season
  played after the repair.
- The ledger files were lost with the checkout too; the Realignments page has a
  "Rewrite the files" action that regenerates them from the database.

The lesson is the one the explorer's action bar already carries from the other
direction: a seed file and a save disagree the moment either is reset, so a
decision has to be recoverable from whichever survives.

## Addendum (2026-10): the cycle learns the Non-Public classes

**Report.** "Realignment just doesn't recognize 11B and 10B — it predates those
classifications." And, in the same breath: "it won't ever let me bypass
reclassification entirely either; it forces me to pick, dismissing doesn't make it
not fire again."

**What was wrong.** Two separate faults, both inherited from the cycle's age.

1. *Privates were sorted as publics.* `build_proposal` pooled every live school by
   `classification`, which for a private is the enrollment class it would hold if
   it were public. So a 10B private with a 7A-sized enrollment sat in the 9A-5A pool,
   was sorted against public 7As, and could be proposed into 6A. The commit then
   moved its `classification` and (via `_move`) its *old group*, and the page and the
   ledger reported a class change for a program whose championship had not moved.
   Read from the Non-Public side, the cycle looked like it kept sweeping privates
   back into the public classes they had come from.
2. *Dismiss did not close anything.* `due()` counted archived seasons since the last
   **committed** cycle. A dismissed proposal left that clock untouched, so the very
   next advance found the cycle still due, built a fresh proposal and held again.
   The only way past a realignment was to commit one.

**The fix.** The privates are a fourth pool, `N`, beside the ladder pools and the
Groups, and like the Groups they are *contained*: pooled by `group` (10B/11B), never
by classification or area; sorted against other privates only, on the same
effective size (enrollment + success − futility) with the same per-pool
coefficients (`success_pp_n` / `futility_pu_n`, span-scaled by default); cut into
two equal bands; the owner's `NONPUBLIC_PLAYUP` names pinned to 10B. `_move` on a
Non-Public class changes `group` only — a private's `classification` is the
enrollment class behind roster depth, the early-participation gate and its old
league, and is not the cycle's to move. One helper, `_cls(r)`, answers "which class
does the cycle sort this row in", and every count, the snapshot, the `reapply`
check and the ledger go through it. 10B and 11B appear in the class counts and are
redrawn when touched, like any class.

A dismissal now closes the cycle: `last_cycle_year` reads committed **or**
dismissed, so Dismiss means "skip this cycle" and the next is due `cycle` seasons
later. A kill switch (`jhsaa_reclass_enabled`, a checkbox on the Coefficients form)
turns automatic cycles off altogether; "Run now" still opens one by hand.

**Two things it shook loose.**

* `ensure_nonpublic` — the standing rule that puts every private in its Non-Public
  class on every load — re-cut every private to the 550-enrollment rule each time.
  That was right when the cut was the only thing that placed a private; with the
  cycle moving them, it undid every committed 10B/11B move the next time the file
  was read. The cut now seeds a private once (a private found in a public group), and
  a private already in 10B/11B stays where the cycle put it; the script's `force`
  path still re-cuts everything.
* A redraw could hand out the name of a league the owner had folded
  (`consolidated_leagues`): the name is in the bank and "unused in the class". The
  load's fold then took it straight back, and the committed map and the loaded map
  disagreed on two leagues — caught by the reapply test the moment the touched set
  changed. `redistrict` now treats every folded name as foreign.

**Validation.** Targeted tests only, by the owner's standing edict: the proposal
pools every private in `N` with both current and proposed in 10B/11B and no
Non-Public class in any public pool; `_move` on a private touches `group` alone; a
dismissal advances `last_cycle_year`; `due()` is false with the switch off; the
commit-and-revert round trips still reproduce the committed map; and the page, the
proposal, the dismiss, the config toggle and the realignments page render through
the Flask client.
