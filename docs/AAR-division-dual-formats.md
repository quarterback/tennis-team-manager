# AAR — per-division dual formats: the expanded singles cards

**Date:** 2026-07-31
**Status:** Landed. Owner rule 2027-07.
**Scope:** `engine.dual.DualFormat` (new), `ncaa.DUAL_FORMATS` / `dual_format` /
`lineup_size`, `season.coach_lineup` / `doubles_perms` / `_dual_record`,
`bracket.play_dual`, `web/sim.py`, `world.refill_walkons` / `_pick_school` /
preseason portal / fall-portal planner / coach followers, `scout_intel`,
`web/awards._POS_W`, the My Program lineup/doubles editors, the Lineup Lab,
player-card line records, recruit-board roster fit.

## The owner's decision

Real college tennis plays 6 singles + 3 doubles because of court counts and Title
IX roster math. This game has neither constraint. College squash (9 singles, no
doubles, strict ladder) prompted the question; the answer keeps tennis's doubles
but sizes each division's card so DEPTH is a real competitive axis — a blue-blood
that can pay for six pros can no longer overpower a dual it has to field ten deep:

| Division | Shape | Doubles scoring | Points | Clinch |
|---|---|---|---|---|
| D1 | 10 singles + 5 doubles | consolidated → ONE point (majority of the 5) | 11 | 6 |
| D2 | 8 singles + 3 doubles | per line (the real non-D1 "9-point" rule, scaled) | 11 | 6 |
| D3 | 8 singles + 3 doubles | per line | 11 | 6 |
| D4 | 10 singles + 3 doubles | per line | 13 | 7 |

D1 keeps the consolidated doubles point deliberately — it limits doubles
stacking, which the owner favors, and it keeps D1's format identity distinct.
The per-line doubles scoring elsewhere is the construction most real non-D1
divisions (D2, NAIA, JUCO) actually use.

## How it's built

* **`engine.dual.DualFormat`** — n_singles, n_doubles, `doubles_team_point`
  (consolidated vs per-line); `total_points` / `clinch` derived (majority + 1).
  The engine takes the shape as data; `CLASSIC` (6+3 consolidated, 7 points)
  stays the default so bare `simulate_dual` calls — engine tests, the cups —
  are byte-identical to before. `DualResult.doubles_point` is None under
  per-line scoring (there is no consolidated point to attribute).
* **`ncaa.DUAL_FORMATS`** is the single authority; `dual_format(division)` /
  `lineup_size(division)` are the only ways anything should read the shape.
  Everything downstream — ladder depth, roster floor, lineup editors, playing-time
  radar, portal "would they start" checks, award position weights — keys off it.
* **Roster floor = the card.** `world.refill_walkons` floors every roster at its
  division's lineup size. D1's 6-scholarship core (`SCHOLARSHIP_SLOTS`, untouched
  — the recruiting economy is NOT resized) no longer covers its 10-card, so a D1
  program routinely carries generated floor walk-ons on courts 7–10. That is the
  point: the paid core wins you the top courts, the bottom of the card is won by
  depth-building (portal, walk-on luck, development), and dominance dilutes.
* **Cross-division play** (exhibitions) uses the HOME side's format; the cups
  stay on the classic 6+3 (an international team event, not a college dual).
* **Recorded duals are data-shaped**: `lines_json` slots (`S7`, `D5`) flow
  through `player_line_records`, box scores, and player cards untouched. Player
  career cards size their line columns to the division format widened to any
  line actually played, so pre-change seasons (S1–S6 history) and post-change
  seasons render side by side.

## Knock-ons handled (grep the class, in one pass — the roster-floor AAR's rule)

* `coach_lineup`: card size, bench cut, short-roster pad, doubles pin
  (2×n_doubles pids), `doubles_perms(n)` (the owner's five 6-slot pairing heads,
  extended with ladder pairs 7/8, 9/10 for D1's five lines).
* Recruiting playing-time factor (`world._pick_school`): "would they crack the
  card" is now per-division (10th OVR at a D1, 8th at a D2).
* Preseason portal: "in the lineup" / "buried" thresholds scale with the card;
  fall-portal planner (`best_placement`, `highest_fit`) likewise. The top-2
  riser rule and the 30-rider cap are untouched.
* Awards `_POS_W`: the owner's 1–6 weights unchanged; 7–10 taper below them
  (.08/.06/.04/.02), doubles 4–5 at .15/.10 — deep-card wins are worth little
  but never nothing.
* UI: My Program singles/doubles editors render the division's slot count (the
  POST routes validate the same); Lineup Lab plots N columns; recruit-board
  ROSTER FIT compares against the LAST STARTER of the offer school's division
  (stored keys `top6`/`sixth` keep their names — they're read in templates).

## Deliberately NOT changed

* **The recruiting/scholarship economy.** Budgets, star costs, tier floors,
  `SCHOLARSHIP_SLOTS` (6), aid-display caps — all untouched (CLAUDE.md
  invariants). The card grew; the money didn't. That asymmetry is the design.
* **Power 6 / PWR 6** (`ita.power6`, `state._power6/_ability`): still the top-6
  mean. It's a cross-division comparable rating and a branded metric, not a
  lineup; a D1 mean-of-10 vs a D2 mean-of-8 would break comparability.
* **Roster caps** (D1 12 · D2 10 · D3/D4 16) and `RECRUIT_POOL`. D1 now runs
  10 starters on a 12 cap — two bench seats. Tight is intended.
* **GTT** (3+3+3 co-ed) and the **cups** — their own formats.
* **Individual championships** field sizes (`SINGLES_PER_PROGRAM` etc.).

## Watch items (flagged, not retuned)

* **Injuries: retuned to hold the OLD volume (owner call, same day).** The
  calibration target is per TEAM, not per body: `roll_new` scales every roll by
  `EXPOSURE_BASELINE(6) / <competitors this dual>`, and `_mark_retirements`
  scales the per-match retirement roll by baseline/<completed singles>, so a
  team's expected injuries per dual and the season's retirement count sit
  exactly where the 6-court game had them. `BASE_RATE`/`RETIREMENT_RATE`
  themselves are untouched; GTT fields ~6 a dual so the pro league sits at
  scale 1.0 and is unaffected.
* **D3/D4 play-play** now means 8–10 completed singles per dual — fuller stats,
  longer `lines_json` rows. Fine, but sim time per dual rose accordingly
  (~15 lines for a D1 dual vs 9 before): the full suite is measurably slower.
* **Old saves:** historical duals keep their 6+3 box scores (data-shaped, still
  render); new duals in the same save play the new shapes from the next sim.
  Rosters floored at 6 under the old rule get topped to the new card floor at
  the next rollover by `refill_walkons`.

## Rule

**A format is data, not a loop bound.** The 6 and the 3 lived as `range(6)` /
`range(3)` / `[(0,1),(2,3),(4,5)]` in a dozen files; the crash AAR
(roster-floor) already showed what one hidden size-assumption costs. Every count
now flows from ONE table (`ncaa.DUAL_FORMATS`) through two accessors, and the
engine's own `DualFormat` derives scoring and clinch from the shape rather than
stating them separately.
