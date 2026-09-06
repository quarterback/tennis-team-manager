# AAR — the JHSAA front page and its story desk

Owner brief, 2026-09: opening the JHSAA "defaults to 9A boys results each time,
there's no home screen". What they do first is *scan what happened across the
universe* — they feed the exports to models right after simming and then browse.
They asked for "a more newspaper style dashboard, basically newspaper meets
thepudding.cool", both seasons on one page, doors into the five buckets (classes ·
team tournaments · individual tournaments · honors · data), and — stated twice —
**no AI slop microcopy anywhere**. Rejected on the way: a state-champions grid on
the front ("Honors has it"), repeat runs, JV, firsts/droughts, rankings as content.

## 1. What shipped

`/jhsaa` is now the **front page** (`jhsaa_front`, `templates/jhsaa_front.html`);
the class hub that used to be `/jhsaa` is `/jhsaa/class` under its old endpoint
name `jhsaa_page`, so every link and every scope fallback still resolves. The
section header's eyebrow links home from every page and the tab rail gained a
"Front Page" entry; the front page passes `classless=true` to `jh_header`, which
hides the class rail — the class becomes relevant when you enter a class.

The page, top to bottom: a **facts strip** (six counts, large type, no panels) ·
**one lead story** at three times any other's size · a **feed** of up to six
stories, no more than two of one kind · **Players of the Year** for both genders
and every class, then the freshman No. 1 champions · a **Programs** desk of three ·
the **record book** heads · one **Data Desk** chart (seed against outcome: the
favourite's win rate by seed gap, and each class champion's seed) · the **doors**.

## 2. The story desk (`app/jhsaa_desk.py`)

Every headline is a deterministic **detector** over the archive, ranked by a
`salience` number; the feed is the top of that order. Ten kinds: `cinderella`
(the lowest seed to reach a final or semifinal), `chalk` (top-4-seed champions
against the lower-seed win rate in State duals), `nailbiter` (a final or semi
decided on the last flight), `freshman_champ` (a ninth-grader winning S1/D1),
`undefeated`, `missed_state` (the best-ranked non-qualifier), `disagreement` (the
team the nine computer systems disagree about most), `one_flight` (the best record
in one-flight duals past a sample), `sweep` (one school, both titles), `riser`
(the biggest class-rank rise on last season).

- **Detectors are pure** and take the loaded season; `load_season` is the only
  I/O — two archive blobs, the previous season's, one GROUP BY over
  `world_jhsaa_dual` for one-flight records (varsity only, the `level` rule), the
  S1/D1 champions via the `json_extract` idiom, and the record-book heads.
  `front_page` memoises on the archive's own stamp (`COUNT`, `MAX(rowid)` of the
  season's rows) so a lab regenerate invalidates it; `world.reset` clears it.
- **One broken detector never sinks the page** — `compile_desk` catches per
  detector. The page is the sum of what could be read.

### ‼️ The headline register

A headline leads with a **number or a name**, carries **no adjective and no verb
of opinion**, is one line, and links into the page that owns the detail:

> `No. 7 seed G reached the 9A final` · `2 of 2 girls' champions were top-4
> seeds` · `Mia Ortiz won 9A No. 1 Singles as a freshman` · `G went 9–1 in
> one-flight duals`

The agent brief the owner forwarded had sample ledes like *"The titles were
chalk. The tournament wasn't."* — that is exactly the copy the owner cannot read,
and it is the one place its advice was not taken. `tests/test_jhsaa_desk.py` pins
the register (first token a digit, "No." or a capitalised name; an adjective
blocklist over headline and dek). If a template needs a word to sound better,
the word is wrong.

### What was deliberately left out

- **No champions grid.** The brief's "Across the JHSAA" strip is the twelve
  champions; the owner had just rejected it. The class DOORS remain (twelve links)
  with no names on them.
- **No season phases.** The brief describes a front page that changes across
  preseason / regular / road / State. A JHSAA season is simulated whole at week 0,
  so on this save every season is complete when it is looked at; the season
  dropdown is what changes the mix. Nothing was built for phases that do not
  occur here.
- **No streaks, dynasties, droughts, JV, or rankings-as-content** (owner).

## 3. Truncation — one rule, not a width per table

"Either names or records constantly get truncated." The stylesheet had ~40 rules
of `white-space: nowrap; overflow: hidden; text-overflow: ellipsis` and fixed
pixel columns sized for the pre-raise type, so every row was a fight over width
and the last cell lost — "Timber Valle", "18-1(", "Eastern Oregon League · 2nd in
distri…". The rule now: **numbers never shrink, names wrap.** In a `nowrap`
ledger every fixed column is a number sized to its widest value (`Rec` 72,
`Dist` 66, TOSS/ATR 64, Finish 84…), and the one unsized column carries
`td.nm`, which wraps (`overflow-wrap: anywhere`) rather than clipping. Rail rows
(`.jh-modrow .n/.s`) and school cells wrap the same way. And the owner's
simpler answer was taken where it applied: **district names are gone from every
secondary line** — the rankings and computer-ratings tables, the players
directory, the hub rail, the TOC and bracket field lists, the POY sub-line. The
district record stays; the name is one click away on the school page.

One smaller layout call from the same pass: rankings rows carry a **finish
marker** (CHAMP / F / SF chips) so the list reads as who converted, not just who
was ranked. (A one-row-per-year trophies ledger was built here too and then
dropped at the merge — main's Program HQ design pass had already replaced that
pane with the gym-banner wall, which answers the same complaint better.)

## 4. Lessons

- **Discuss the shape before drawing it.** The owner asked to talk first; three
  rounds of "which of these would you read" removed five of the first eight ideas
  before any code. The first proposal — champions grid, TOC hero, season status —
  would have been built and thrown away.
- **A forwarded brief is direction, not a spec.** The agent brief the owner
  shared was mostly right (hierarchy, one lead, deterministic detectors, the data
  desk) and wrong in exactly the ways the owner's own rules already forbade (the
  copy register, the champions strip, phases the sim does not have). Take the
  structure, keep the owner's rules.
- **Truncation is a rule problem.** Nudging column widths one table at a time
  is how it got here; a single rule — what may shrink and what may wrap — fixes
  every table at once and tells the next table what to do.
