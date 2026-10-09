# JHSAA read-path audit — what one click actually does (2026-09)

Owner directive: stop feature work; profile one request each for the program page,
rankings, a coach page, a player page and the rising-freshman portal; **count, don't
guess**; and for every single-entity page, name every operation whose scope is larger
than that entity and say why it is there.

Tool: `scripts/jhsaa_read_audit.py --db <copy of save>` (reusable; run it on the real
lab save for real numbers). Numbers below are from the session fixture — ONE archived
season, 348 girls' programs — so they are the *shape* of each request. The owner's save
has ~100 seasons and ~860 programs a gender; the scaling column says which costs grow
with which of those. Every page was measured on its SECOND hit, so whatever is
honestly memoised is already warm.

## The table

| page | wall | roster builds | whole-season archive reads (`get_jhsaa`) | `_relabel` nodes | SQLite connects | statements |
|---|---:|---:|---:|---:|---:|---:|
| program page | 0.42 s | 1 | 2 (`jhsaa_school_seasons` + `jhsaa_school_history`) | 157,356 | 68 | ~200 |
| rankings | 0.19 s | 0 | 1 | 74,244 | 36 | 108 |
| coach page | 0.21 s | 0 | 1 per season coached (`jhsaa_season_rows_at`) | 74,244 | 43 | 133 |
| player page | 0.81 s | **9** (`generated_siblings`) | 1 per season played (`player_career`) | 149,056 | 163 | 493 |
| portal page (no proposal) | 0.04 s | 0 | 0 | 0 | 36 | 110 |
| portal BUILD (both genders) | 20.7 s (was 55.8 s) | 614 of 688 | 0 | — | 9,287 | 24,857 |

(The player page's second measurement used a different program than the first, hence 9
roster builds; on the first program it was 39. The count is `town programs × 3 cohorts
× 2 genders`, see below.)

## Larger than the entity, page by page

### Program page (`/jhsaa/school/<school>`)
1. **`get_jhsaa` reads the WHOLE gender-season blob (1.3 MB here, ~3.3 MB at 860
   programs) and `_relabel`s every node (74k here, ~180k real) to answer for ONE
   school — and it has no memo.** It is called twice per page (`jhsaa_school_seasons`
   and `jhsaa_school_history`), **once per archived season each**. Scales with
   seasons × programs: on a 100-season save that is ~200 blob reads and ~36M relabel
   nodes per click, which is minutes. This is the program-page cost. *Why it exists*:
   the archive is stored per (world, year, gender) as one JSON document, and the
   rename relabel is applied on read, so there is no per-school path into it.
2. `jhsaa_program_wins` walks the program's own lines in the dual table (memoised per
   its docstring) — scoped correctly, but the first hit folds every season.
3. `jhsaa_match_dates` dates the whole gender's season (rounds over every dual) to
   date this program's schedule — scoped to a season, larger than the school; ~0.4 s
   cold here, ~1 s real, per season shown.
4. `load_schools` ×6, `sibling_link` ×66, 68 connections — each connection runs
   `PRAGMA journal_mode=WAL` + `busy_timeout` (`dbpath.connect`), a fixed tax of ~0.7 ms
   ×68 here; on a 4 GB file on a laptop disk it is more.

### Rankings
Correct by design: one archived blob, no roster, no ladder. Its only cost is (1)
above — one whole-blob read + relabel per view. On the real save that is one ~3 MB
JSON parse and ~180k-node relabel per click, every click. A memo keyed on
`(world, year, gender)` (an archived season is immutable; cleared by `reset()`) would
make it ~free and would also take the multiplier out of the program and coach pages.

### Coach page (`/jhsaa/coach/<id>`)
`_career_ledger` → `jhsaa_season_rows_at` reads a whole-season blob **per season the
coach has coached** to recover the program's record that year. A 25-year head = 25
blob reads + relabels for one page. Everything else is scoped to the coach. *Why*: the
coach history row stores wins/losses but the ledger wants the season row (finish,
place), which lives only in the blob.

### Player page (`/jhsaa/player/<school>/<pid>`)
1. **`generated_siblings` builds the roster of EVERY program in the player's town for
   the three cohorts after theirs, both genders** (`_town_index` pool × 3 entry years),
   to find younger siblings whose roll points at this pid: 9–39 roster builds here; a
   Port Veles player (41 programs) is ~250 roster builds per click. *Why*: the sibling
   tie is derived on read from the younger seat's roll, so the only way to find
   "who rolled me as their older sibling" is to generate every candidate seat. This is
   the wrong direction of lookup for a page.
2. `player_career` reads one whole-season blob per season played (up to six with early
   participation) — (1) again.
3. `_relabel` 149k nodes for one player.

### Portal
The **page** is cheap. The **build** was the statewide projection the owner described:
`district_teams` on every program of both genders (~1,720 roster builds real, none
memoised), then for every rising freshman off V1 a full re-sort of every candidate
destination's ladder — measured 1.05M `coach_eval` calls / 2.2M overall recomputes on
the fixture — and the same again on every edit and at commit. This session changed it
to build origins first and destinations only when a tier is consulted, with each
ladder a sorted list updated by insertion (85k evals, 614 builds, 20.7 s, byte-identical
slate against the real projection). That is still the wrong unit of work: on the
fixture's compact geography nearly every school is in some consulted tier, and each
consulted destination costs a full roster build. The owner's design is the right one
and is not built yet:

- **player-first**: build the ORIGIN only; if V1, done;
- **metadata geography**: county → area → neighbouring areas as name lists (already
  so);
- **cheap elimination**: a per-season, per-program **V1 floor** (the eval of the 11th
  seat on the preseason ladder) and V1 size, written by the rung beside `jhsaa_preseason`
  — a dictionary lookup removes almost every destination before any roster is built;
- **project only the plausible few**, and after a move consumes a seat, re-derive that
  ONE destination's floor.

## What this points at (the owner's principle)

**A read-only page should almost never derive state.** Three costs account for
everything above, and all three are "derive on read" where "write at the rung" was
available:

1. **The season blob is the unit of storage, so every single-entity read pays for the
   whole gender.** Fix in two steps: memoise `get_jhsaa` per `(world, year, gender)`
   (immutable; one clear in `reset()`) so a save's pages stop re-parsing 3 MB per click,
   then persist the per-program season ROW (`_season_row`'s output) at archive time so
   `jhsaa_school_seasons` / `jhsaa_school_history` / `jhsaa_season_rows_at` read ~100
   small rows instead of 100 whole blobs.
2. **Rosters and ladders are recipes re-run on every read.** Persist the preseason
   state the rung already computes — effective roster, coach ladder, V1/V2/V3/JV cut,
   V1 floor, staff effects, Future Value / Program Interest, coach read — per program
   per season. The program page, the portal and the export all read it; only the rung
   writes it. (This is what makes the portal player-first rather than merely lazier.)
3. **Derived-on-read ties that point the wrong way.** `generated_siblings` needs a
   per-town sibling index written by the rung (younger pid → older pid), not a scan.

Cheap and independent: reuse one SQLite connection per request/thread instead of
opening (and `PRAGMA`-ing) 40–160 per page.

## Method notes
- The FIRST run of this audit reported 4,000 `load_schools` calls and 4,185 play-up
  fingerprint queries per player page. That was the **test fixture's own**
  `load_schools` patch calling the real loader ~100 times per call — not the app.
  Memoising the patch removed it. Count against the real save before concluding.
- The page numbers here are second-hit; first hits on this fixture were 2.2 s (program)
  and 6.1 s (player), the difference being caches that are honestly warm after one hit
  (`_upstart_cache`, `_town_index`, era gates).

## After the fixes (same fixture, second hit, one archived season materialised)

| page | before | after | roster builds after |
|---|---:|---:|---:|
| program page | 0.42 s | 0.13 s | 0 (stored roster) |
| rankings | 0.19 s | 0.05 s | 0 |
| coach page | 0.21 s | 0.05 s | 0 |
| player page | 0.81 s | 0.45 s | 7 (uncovered cohort seasons still scan; 0 once the rung has indexed them) |
| portal build (with stored floors) | 55.8 s → 20.7 s (lazy) | 14.3 s | 394 of 688 (origins + confirmed finalists) |

The season-blob parse and relabel are gone from every page (fix #1); the program
and coach pages read stored rows (fix #2, #3); stored-ladder seats agreed with the
live projection in 300 of 300 random trials, and the portal's slate is byte-identical.
The one-time backfill of season rows on this fixture cost 1.5 s a gender; the
provisional next-season state costs the rung one more whole-gender build (22 s here).
Found on the way: the bulk history fold used by the export left `won` out of its
schedule rows, so every exported JV record read 0-N; the stored rows fixed it.


## Addendum 2026-10 — the school page, per tab

Owner report: clicking a team on any schedule could take minutes on the 85-season
save; no warming shell, the browser simply waited on `jhsaa_school_view`.

What was still paid per click, whatever tab was selected:

- `jhsaa_school_individual_champions` → `jhsaa_individual_champions` ×3 (varsity,
  mixed, JV) per archived season, each `json.loads` of every draw of the class
  (~1 MB a season, ~85 MB a click) plus `_relabel` over 128-entry draws. The hero
  shows this count on every tab, so no tab escaped it. Replaced by
  `world._school_champion_index`: one `json_extract` query per gender returning only
  the champion entrant, memoised on the newest archived year.
- `jhsaa_program_wins` (Records only) — a scan of every archived line of the
  program, cached per newest year. Now built only for `view=records`.
- `jhsaa_match_dates` (the whole gender-season layout, memoised) and the schedule
  rows — now Overview/Roster/Schedule only.
- roster + injuries + captains + award badges — Overview/Roster only.
- coach history (`program_head_coaches`, `program_heads_by_year`, COY) and the
  reclass ledger — History only; `program_staff` Overview/Staff only.

`scripts/jhsaa_school_profile.py --db <copy>` times each section and each tab,
cold and warm, across schools. Not yet run on the owner's real save from this
session — run it there to confirm the Overview lands under a second.
