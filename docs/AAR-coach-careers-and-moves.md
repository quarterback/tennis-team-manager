# AAR — Coach careers, moves, and the assistant award

## What changed

Coaches are now full career entities: their profile shows a year-by-year record
**by team**, the players they coached to awards, and their team honors — and they
can be **moved between seats via the editor**. Added **National Assistant Coach
of the Year** (per division × gender) alongside the existing National and
Conference Coach of the Year.

## Per-season coach history

Coaches already had a stable id and a current seat (`coachreg`), but no season
history. Added `coach_history(coach_id, year, season_no, division, gender,
school, role, wins, losses)`, captured at the **awards phase**
(`record_coach_seasons`, called from `stamp_world_honors` before the rollover)
so the record persists by team, year over year — even after a coach moves.

## Career record (head seasons only)

`coach_career_table` renders the season rows (newest first) plus the live current
season, with career totals that count **head-coach seasons only** — an
assistant's team record is shown for context but banks no career wins until they
run a program (per the design). The header shows the career head-coach W-L.

## Players coached to awards

`coach_player_awards` lists every player honor stamped at a program during a
season the coach was on its staff (joined on school + year through the shared
`honors` table), grouped by year.

## National Assistant Coach of the Year

Added to `coach_honor_records` (so it persists/follows the coach and shows on the
awards page and profiles like the head awards). It goes to the top
development-rated lead assistant among the division's strongest programs —
computed per division × gender. Honors stamping is unchanged otherwise.

## Editor: moving coaches

Per the product owner's "just let me move coaches via the editor" option (no
automatic carousel required here): the coach profile has a **Move coach** panel.
`coachreg.swap_seats` is the primitive — it swaps the occupants of two seats
(any role, any program in the universe) and resets both tenures, so no coach is
orphaned. The UI offers one-click promote/demote within a program's staff (e.g.
elevate an assistant over the head coach) and a move-to-another-program form
(destination program + seat). The destination seat is generated if it has never
been viewed, then swapped. Identity is keyed to the coach id, so honors and the
career record follow the coach across the move.

## Verification

- `tests/test_web_coaches.py`: National Assistant COTY is awarded; career record
  counts head seasons only (assistant years flagged, excluded); `swap_seats`
  moves a coach between seats. Also fixed a pre-existing order-dependent failure
  (`test_coach_honors_persist_and_follow_id` now requests the `played_season`
  fixture instead of relying on ambient DB state that `test_coach_carousel`'s
  `start_new()` had wiped).
- Manual: coach profile renders the record table, players-coached panel, and the
  move editor; cross-program and in-staff moves via the web route reassign the
  seat and the record/honors follow the id.
