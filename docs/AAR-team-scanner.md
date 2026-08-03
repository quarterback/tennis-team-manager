# AAR — Team Scanner: a cross-division TEAM board for god-mode roster scanning

**Date:** 2026-08-03
**Scope:** New Analytics Bureau page (`/intel/teams`) that lists every program in
one sortable, filterable board — both rating lenses per team, expandable rosters
inline — linked from the Data Portal and Bureau HQ.

## The problem, as understood
The owner plays god-mode: they pick teams around the divisions and build them up,
and they pull buried talent up from lower divisions. The request (paraphrased from
a deliberately loose brief):

- There was **no team-level scanning surface**. The Bureau's boards (Underplaced
  Talent, Portal Search, Scholarship Watch) are all *player*-keyed; the Lineup Lab
  is team-keyed but scoped to **one conference of one division** at a time. To
  compare teams across a league — let alone across divisions — you ended up
  clicking through menus team by team.
- Nothing showed a team's **current top-6 (card) STR** or an **average of actual
  roster strength** at a glance, per league or across leagues.
- **STR is a misleading strength metric** for exactly this use: it's the live
  results rating, so freshmen and new arrivals sit below what their real ability
  warrants until matches accumulate. The engine's honest number — current
  OVERALL — had **no team-level visibility anywhere**, which also made "who do I
  pull up from a lower division" harder than it should be.
- Preference for a **roster toggle**: see a team's full roster inline, without
  navigating away, and generally a better way to view this "across teams,
  divisions, etc."

## What was built
Everything is an additive read layer on the existing god-mode scan
(`scout_intel.scan`) — no engine, sim, or economy changes.

### `app/scout_intel.py` — `team_board` / `team_rosters` / `team_board_conferences`
`team_board(gender, division, conf, sort, direction, q)` folds the scan's
`team_ladder` + players into one row per program, every division in one list:

| column | meaning |
|---|---|
| `card_str` | avg live results STR of the actual starters (`line` ≤ the division's card — `ncaa.lineup_size`, never a hardcoded 6) |
| `card_ovr` | avg **current** OVERALL (20–80) of the talent top card — "how good are they NOW", immune to the freshman STR lag. **Default sort.** |
| `roster_ovr` | avg current OVERALL of the whole roster (depth included) |
| `ceiling` | avg true ceiling of the top card — the program's talent level, the same number the cross-division ladder ranks on |
| `upside` | `ceiling − card_ovr` — a maxed-out senior core vs a young one still growing |
| `n_buried` | players on the roster who qualify for the Underplaced board (same `UNDERPLACED_MIN_GAP`/`MIN_TRUE` thresholds — one definition, not a fork) |

Sorts cover each lens plus `buried` and `best` (best single player); `direction=asc`
flips to **weakest-first** — the "which team do I want to make good" cut. Filters:
division (`All` = the cross-division view), conference (within a division),
school/conference text search.

`team_rosters(gender, schools)` returns full rosters in singles-ladder order for
the expandable per-team view — each player carrying STR, current OVERALL, ceiling,
upside, class, walk-on/aid, and a `buried` flag. Ordering quirk: the scan
re-sorts its global player list by ceiling, so re-sorting a school's players by
STR could flip STR-tied starters relative to the lines the scan dealt; starters
are therefore ordered by their stored `line`, then depth by STR.

### Web layer
- `GET /intel/teams` (`app/web/server.py`): filters from query args, paginates,
  and fetches rosters **only for the page on screen** (embedding ~1k teams'
  rosters in one response would swamp the HTML).
- `intel_teams.html`: each team row is a native `<details>` — click to unfold the
  roster inline (the requested toggle), no JS state. Header/legend tooltips spell
  out STR-vs-NOW-vs-CEIL so the board teaches its own metrics. Per-player links
  to the player page (universe-correct `u=<div>-<gender>`) and the Fit Finder.
- Nav: "Team Scanner" under Analytics Bureau; KPI card on Bureau HQ; a tab on the
  Data Portal hero (the surface the request named).

## Why it lives in the Bureau (not the public Data Portal page)
The board's whole point is engine truth — current/ceiling OVERALL with zero
scouting fog — which is exactly the Analytics Bureau's charter ("god mode ·
all-seeing · no noise"). The Data Portal is the ATP/WTA-style *public* feed
(rankings, scores, STR leaders) and its JSON export feeds an external hub, so
leaking hidden-truth grades there would blur that line (and bloat the feed).
The portal links prominently to the scanner instead.

## Tests
`tests/test_intel_team_scanner.py` — invariants, not goldens: all four divisions
in one board; metrics coherent on the 20–80 scale with `upside ≥ 0`; default sort
= current ability desc; direction flip; division/conf/query filters; each sort
lens actually orders; rosters agree with the scan (line assignment, pid
resolution, and the summary row's numbers recomputed from exactly the roster
shown); route renders + paginates. Full suite green.

## Gotchas hit (for the next agent)
- The scan's `team_ladder` entries keep the conference under **`tier`** (a stored
  name, like `top6_cur`) — `team_board` re-exposes it as `conf`, but anything
  reading the raw ladder must use `tier`.
- `top6_cur` is the *talent* top card (build_roster order), while `line` follows
  live STR — they can differ; `card_ovr`/`ceiling`/`upside` all key off the same
  talent card so they stay mutually coherent.
