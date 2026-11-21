# AAR — two-row top bar, one-table Clubhouse lineup, Season Hub rebuild, and four display bugs

**Date:** 2026-11-21
**Status:** SHIPPED on `claude/laughing-galileo-tiz0g1` (PR 498).
**Scope:** `base.html` + `static/css/shell.css` (top bar), `my_program.html` +
`state.my_program_view` (Clubhouse), `season.html` + `server.season_hub`
(Season Hub), `_stepper.html` + `state.stage_steps` / `world_stage_key` /
`current_world_stage` (one stage reading), `world.html`, `data_portal.html`,
`dashboard.html`, `server.teams` (Power Index source), `static/css/app.css`
(stepper styles moved out of `world.html`).

## How this was found

A fresh D1 Men save coached as Michigan, advanced six weeks, every page captured
at 1440px and 390px. The findings below are what the screens showed, then traced
to code.

## Bugs fixed

1. **Three pages named three different stages in the same week.** In week 6 with
   the fall portal open, the header said "Review fall portal", the World Hub said
   "regular season in progress" and the Season Hub said **"Season complete"**.
   Cause: each page named the stage from its own if-chain. The Season Hub's had no
   `fall_portal` (or `selection`) branch, so the open portal fell through to the
   `else`. The World Hub hard-coded its sub-label. Fix: `state.STAGE_ORDER` /
   `STAGE_LABELS` / `world_stage_key` / `stage_steps` are now the one reading;
   `world_hub` and the new `current_world_stage` (no `prime()`, one season row per
   active universe) both call it; the Season Hub and World Hub render the same
   stepper from `_stepper.html`; the Season Hub and Data portal status lines gained
   the missing branches. The Season Hub's "2026 Season" was also hard-coded and now
   reads the world year.
2. **The team page showed the design prototype's Power Index.** `server.teams` read
   `rankings_data.get_row`, which looks up the hard-coded `_SEED` sample table from
   the original mockup. Michigan showed 0.7765 there and 0.8403 on Rankings; any
   school the sample did not name showed none. It now reads the live `ranking_rows`
   row it had already computed, and shows nothing before a team has played.
3. **The Dashboard labelled the CTA ranking "Power Index".** "Top Programs" lists
   `ranking_rows` order (ranking points), so its link said "Power Index" over a list
   that Season Hub's Power Index contradicts (Kentucky first vs Pepperdine first).
   The link now says "CTA Rankings". Both orders are legitimate; only the label was
   wrong.
4. **The Clubhouse numbered six singles flights in a ten-flight division.**
   `my_program_view` set `line = i if i <= 6`, so a D1 Clubhouse showed S1-S6 and
   courts 7-10 as bench while the dual fielded ten. It now reads `lineup_size`. This
   is exactly the `range(6)` / `[:6]` the dual-format section of `CLAUDE.md` bans.

## Interface changes

- **Top bar is two rows.** Row one: brand, labelled universe picker, season, week
  and stage, class signed, search, one settings menu (colour scheme plus "Start a
  new league") and the advance control. Row two: the eight menu groups. As one
  fixed-height row the bar needed ~1836px laid out in full, so at 1440px the
  advance button sat against the right edge with pieces shed around it. Row one now
  fits in ~1300px and sheds only the clock cells and search; the advance button
  keeps its label down to 620px. Nav folds into the drawer at 1000px (was 1210px).
- **Clubhouse lineup is one table that is also the editor.** The page showed the
  ladder as a table and then again as ten dropdowns. Each row now has a Move
  button: pick one player, pick another, they trade flights; Save posts the same
  `s1..sN` fields `my_program_lineup` always took, so the route is unchanged. A
  `<noscript>` keeps the slot pickers for no-script use. On phones the record and
  aid columns drop so Move stays on screen; class year stays (AGENTS.md: a
  player's grade appears in every list).
- **Clubhouse header** shows the Power Index and its rank ("0.840, 7 of 64") from
  the same `national_top` the Season Hub lists, plus the program's location. The
  report card and job offers links moved into the next-dual strip.
- **Season Hub** puts the Power Index in the main column as a one-line-per-team
  table (rank, school, conference, record, index), highlights the coached team and
  appends its row when it sits below 15th. It was a 340px side panel where each
  team wrapped to three lines. Latest results and the bubble moved to the side
  column. The "This week" conference filter, which the route already computed but
  the template never rendered (a stray `</form></span>` was all that was left of
  it), is back.

## Verification

- Browser at 1440, 1280 and 390px on the save above: the advance button is fully
  on screen at every width; no page scrolls sideways.
- Lineup editor driven in a browser: S1 swapped with the first bench player, Save,
  page reloads as "Custom lineup" with the swapped order, which is what
  `build_roster` fields.
- No test suite run, by owner request: the owner validates the work after it lands.

## Lessons

- **A stage label written per page will disagree with the others.** Three hand-rolled
  phase chains had drifted; the one missing branch rendered the opposite of the
  truth ("Season complete" in week 6). Derive labels from one table.
- **Prototype seed data outlives the prototype.** `rankings_data._SEED` still backs
  `get_rankings`/`get_row`; nothing else should call them for live numbers.
