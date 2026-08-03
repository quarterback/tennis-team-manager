# AAR — Team Scanner: cross-division team board, OVR-first

**Date:** 2026-08-03
**Scope:** New Analytics Bureau page `/intel/teams` — every program in one
sortable board with inline rosters. Linked from the Data Portal tabs, Bureau HQ,
and the sidebar.

## The problem (owner's brief, paraphrased — instructions were loose)
God-mode play: the owner picks teams to build up and pulls buried talent up from
lower divisions. Pain points:
- No team-level scanning surface. Bureau boards are player-keyed; Lineup Lab is
  one conference of one division at a time. Comparing teams meant menu-diving.
- No at-a-glance team strength: neither a starters' average nor a whole-roster
  average existed anywhere.
- **STR is the wrong metric for this** (owner said so twice): it's results-only,
  driven by matches played and opposition faced, so freshmen/new players rate
  below their real ability. The reliable number is current **OVR**, which had no
  team-level visibility — making "who do I pull up" needlessly hard.
- Wanted rosters expandable in place, and **no explanatory microcopy** (a second
  in-session correction: legend/tooltip text was stripped).

## What was built
Additive read layer on `scout_intel.scan` — no engine/sim/economy changes.

**`scout_intel.team_board(gender, division, conf, sort, direction, q)`** — one
row per program, all four divisions in one list. Columns, OVR leading:
`card_ovr` (starters' current OVR, default sort) · `roster_ovr` (whole roster) ·
`ceiling` (top card's true ceiling) · `upside` (ceiling − card_ovr) · `card_str`
(trailing, muted — context only) · `n_buried` (Underplaced-board thresholds,
same constants, not a fork). `direction=asc` = weakest first (rebuild targets).

**`team_rosters`** — per-team expandable roster in **current-OVR order** (talent,
not STR), each player keeping their STR-based `line` so high-OVR/no-line reads
instantly as buried. **`team_board_conferences`** — conference filter values
(note: the scan's ladder stores conference under `tier`).

**Web:** route paginates and fetches rosters only for the visible page. Template
rows are native `<details>` — click a team, roster unfolds. No legend, no
tooltips.

## In-session corrections (the reason for this AAR's shape)
1. First cut led columns with STR and ordered rosters by STR ladder. Owner:
   OVR, not STR. Fixed: OVR-first columns everywhere, rosters talent-ordered,
   STR demoted to a muted trailing column.
2. Owner: no microcopy/explanations. Removed the legend panel and all header
   tooltips.

## Tests
`tests/test_intel_team_scanner.py` — invariants: all divisions in one board;
20–80-scale coherence with `upside ≥ 0`; default sort = current OVR desc;
direction flip; division/conf/query filters; sort lenses order; rosters agree
with the scan (OVR order, full card marked, pids resolve, summary numbers
recompute from the shown roster); route renders + paginates.
